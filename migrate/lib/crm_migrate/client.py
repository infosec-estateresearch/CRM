"""``SalesforceClient``: the single gateway for every Salesforce request.

All requests are built here and checked against ``RequestPolicy`` before the injected
transport is called. The client attaches the ``Authorization`` header itself and only to
requests for the configured origin. Any 3xx response is an error; error bodies are
never kept, only the HTTP status and the Salesforce ``errorCode``.
"""

import email.utils
import json
from urllib.parse import quote, urlencode

from .auth import build_token_request, parse_token_response
from .errors import (HttpError, ProtocolError, RedirectRefused, ResponseTooLarge,
                     safe_sf_error_code)
from .messages import Request, Response
from .policy import RequestPolicy
from .transport import DEFAULT_MAX_BYTES

MAX_PAGES = 200000


def _error_code(body):
    try:
        doc = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, AttributeError):
        return "UNKNOWN"
    code = None
    if isinstance(doc, list) and doc and isinstance(doc[0], dict):
        code = doc[0].get("errorCode")
    elif isinstance(doc, dict):
        code = doc.get("errorCode") or doc.get("error")
    if isinstance(code, str):
        code = code.upper()
    return safe_sf_error_code(code)


def parse_http_date(value):
    if not isinstance(value, str):
        raise ProtocolError("server_date_missing", detail="no Date header")
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        raise ProtocolError("server_date_invalid", detail="Date header unparseable") from None
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ProtocolError("server_date_invalid", detail="Date header must be GMT")
    return parsed


class SalesforceClient:
    def __init__(self, origin, api_version, transport, contract, *, max_bytes=DEFAULT_MAX_BYTES):
        self.policy = RequestPolicy(origin, api_version, contract.fields_by_object())
        self.origin = self.policy.origin
        self.api_version = self.policy.api_version
        self.contract = contract
        self._transport = transport
        self._max_bytes = int(max_bytes)
        self._token = None
        self.request_count = 0
        self.last_server_time = None

    @property
    def base(self):
        return f"/services/data/v{self.api_version}/"

    # ------------------------------------------------------------- core
    def _send(self, request):
        self.policy.check(request)                       # refuse before the transport
        self.request_count += 1
        resp = self._transport.send(request)
        if not isinstance(resp, Response):
            raise ProtocolError("transport_response", detail="transport returned no Response")
        status = resp.status
        if 300 <= status < 400:
            raise RedirectRefused(status=status)
        if len(resp.body) > self._max_bytes:
            raise ResponseTooLarge(status=status)
        if not 200 <= status < 300:
            raise HttpError(status=status, sf_error=_error_code(resp.body))
        date = resp.headers.get("date")
        if date is not None:
            self.last_server_time = parse_http_date(date)
        return resp

    @staticmethod
    def _json(resp):
        try:
            return json.loads(resp.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ProtocolError("response_not_json", status=resp.status) from None

    def authenticate(self, client_id, client_secret):
        resp = self._send(build_token_request(self.origin, client_id, client_secret))
        self._token = parse_token_response(self._json(resp), self.origin)

    def _get(self, path, params=None):
        if self._token is None:
            raise ProtocolError("not_authenticated")
        url = self.origin + path
        if params:
            url += "?" + urlencode(list(params.items()), quote_via=quote, safe="")
        req = Request(
            method="GET",
            url=url,
            headers=(("Accept", "application/json"), ("Authorization", "Bearer " + self._token)),
        )
        resp = self._send(req)
        return self._json(resp), resp

    # ------------------------------------------------------------- resources
    def server_time(self):
        """Server time from the ``Date`` header of a ``limits`` call (never the local clock)."""
        doc, resp = self._get(self.base + "limits/")
        when = parse_http_date(resp.headers.get("date"))
        remaining = None
        if isinstance(doc, dict) and isinstance(doc.get("DailyApiRequests"), dict):
            value = doc["DailyApiRequests"].get("Remaining")
            remaining = value if isinstance(value, int) else None
        return when, remaining

    def describe(self, object_name):
        doc, _ = self._get(self.base + f"sobjects/{object_name}/describe/")
        if not isinstance(doc, dict):
            raise ProtocolError("describe_shape", detail=object_name)
        return doc

    def _resource(self, all_rows):
        return "queryAll/" if all_rows else "query/"

    def count(self, soql, all_rows):
        doc, _ = self._get(self.base + self._resource(all_rows), {"q": soql})
        total = doc.get("totalSize") if isinstance(doc, dict) else None
        if not isinstance(total, int) or total < 0:
            raise ProtocolError("count_shape")
        return total

    def iter_pages(self, soql, all_rows):
        """Yield lists of records, following only validated relative ``nextRecordsUrl`` values."""
        doc, _ = self._get(self.base + self._resource(all_rows), {"q": soql})
        pages = 0
        while True:
            if not isinstance(doc, dict) or not isinstance(doc.get("records"), list):
                raise ProtocolError("query_shape")
            pages += 1
            yield doc["records"]
            if doc.get("done") is True:
                return
            if pages >= MAX_PAGES:
                raise ProtocolError("too_many_pages")
            nxt = self.policy.check_next_records_url(doc.get("nextRecordsUrl"))
            doc, _ = self._get(nxt)

    def deleted(self, object_name, start, end):
        doc, _ = self._get(self.base + f"sobjects/{object_name}/deleted/", {"start": start, "end": end})
        if not isinstance(doc, dict) or not isinstance(doc.get("deletedRecords"), list):
            raise ProtocolError("deleted_shape", detail=object_name)
        return doc
