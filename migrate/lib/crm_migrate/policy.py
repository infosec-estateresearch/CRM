"""Read-only request allowlist and origin rules.

``RequestPolicy.check`` is called by ``SalesforceClient`` before a request reaches a
transport, and again by ``HttpsTransport`` itself (defence in depth). Anything not
explicitly permitted raises ``RefusedRequest`` or ``OriginError``.

Permitted, with ``vNN.N`` equal to the configured API version:

* ``POST {origin}/services/oauth2/token`` with exactly ``grant_type=client_credentials``,
  ``client_id`` and ``client_secret`` in a form body, no query string, no Authorization.
* ``GET  {origin}/services/data/vNN.N/query/?q=<generated SOQL>``
* ``GET  {origin}/services/data/vNN.N/queryAll/?q=<generated SOQL>``
* ``GET  {origin}/services/data/vNN.N/query/<locator>`` (a server ``nextRecordsUrl``)
* ``GET  {origin}/services/data/vNN.N/sobjects/<ContractObject>/describe/``
* ``GET  {origin}/services/data/vNN.N/sobjects/<ContractObject>/deleted/?start=&end=``
* ``GET  {origin}/services/data/vNN.N/limits/``
"""

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlsplit

from .contract import parse_soql
from .errors import OriginError, RefusedRequest
from .messages import Request

ORIGIN_RE = re.compile(r"^https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.sandbox)?\.my\.salesforce\.com$")
API_VERSION_RE = re.compile(r"^\d{2,3}\.\d$")
NEXT_RECORDS_RE = re.compile(r"^/services/data/v\d+\.\d+/query/[A-Za-z0-9-]+$")
ISO_PARAM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|\+00:00)$")

_TOKEN_PATH = "/services/oauth2/token"
_DATA = r"^/services/data/v(?P<version>\d+\.\d+)/"
_QUERY_RE = re.compile(_DATA + r"(?P<kind>query|queryAll)/?$")
_NEXT_RE = re.compile(_DATA + r"query/(?P<locator>[A-Za-z0-9-]+)$")
_DESCRIBE_RE = re.compile(_DATA + r"sobjects/(?P<object>[A-Za-z][A-Za-z0-9_]*)/describe/?$")
_DELETED_RE = re.compile(_DATA + r"sobjects/(?P<object>[A-Za-z][A-Za-z0-9_]*)/deleted/?$")
_LIMITS_RE = re.compile(_DATA + r"limits/?$")
_ALLOWED_HEADERS = {"accept", "authorization", "content-type", "user-agent"}
_FORM = "application/x-www-form-urlencoded"
_CTL_RE = re.compile(r"[\x00-\x20\x7f]")


def validate_origin(origin):
    """Exact ``https://<mydomain>.my.salesforce.com`` or ``...sandbox.my.salesforce.com``."""
    if not isinstance(origin, str) or not ORIGIN_RE.match(origin):
        raise OriginError("origin_refused", detail="origin must be https://<mydomain>[.sandbox].my.salesforce.com")
    return origin


def validate_api_version(version):
    if not isinstance(version, str) or not API_VERSION_RE.match(version):
        raise OriginError("api_version_refused", detail="expected NN.N")
    return version


@dataclass(frozen=True)
class Checked:
    kind: str            # token | query | queryAll | next | describe | deleted | limits
    object: str = ""


def _parse_params(query):
    if not query:
        return {}
    try:
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        raise RefusedRequest(detail="malformed query string") from None
    params = {}
    for key, value in pairs:
        if key in params:
            raise RefusedRequest(detail="repeated parameter")
        params[key] = value
    return params


class RequestPolicy:
    def __init__(self, origin, api_version, contract_fields):
        self.origin = validate_origin(origin)
        self.api_version = validate_api_version(api_version)
        self._host = urlsplit(self.origin).netloc
        self._fields = {k: frozenset(v) for k, v in dict(contract_fields).items()}

    # -- helpers
    def _refuse(self, detail):
        raise RefusedRequest(detail=detail)

    def _contract_object(self, name):
        if name not in self._fields:
            self._refuse("object not in contract")
        return name

    def check_next_records_url(self, value):
        """A server-supplied nextRecordsUrl: relative, exact pattern, configured version."""
        if not isinstance(value, str) or not NEXT_RECORDS_RE.match(value):
            raise RefusedRequest("next_records_url_refused", detail="nextRecordsUrl must be a relative query locator")
        if not value.startswith(f"/services/data/v{self.api_version}/"):
            raise RefusedRequest("next_records_url_refused", detail="nextRecordsUrl version mismatch")
        return value

    def check(self, request):
        if not isinstance(request, Request):
            self._refuse("not a Request")
        method = request.method
        if method not in ("GET", "POST"):
            self._refuse("method not permitted")
        url = request.url
        if not isinstance(url, str) or _CTL_RE.search(url) or "\\" in url:
            self._refuse("malformed url")
        try:
            parts = urlsplit(url)
            port = parts.port
        except ValueError:
            raise RefusedRequest(detail="malformed url") from None
        if parts.scheme != "https":
            raise OriginError(detail="scheme must be https")
        if parts.netloc != self._host or port is not None or parts.username or parts.password:
            raise OriginError(detail="host is not the configured origin")
        if parts.fragment or url.endswith("#") or url.endswith("?"):
            self._refuse("fragment or empty query")
        rebuilt = self.origin + parts.path + (("?" + parts.query) if parts.query else "")
        if rebuilt != url:
            self._refuse("url is not origin plus path")
        path = parts.path
        if "%" in path or "//" in path or "/." in path or ";" in path:
            self._refuse("path encoding refused")
        self._check_headers(request, path)
        params = _parse_params(parts.query)

        if method == "POST":
            if path != _TOKEN_PATH or params:
                self._refuse("POST permitted only to the token endpoint")
            self._check_token_body(request)
            return Checked("token")

        # GET from here on
        if request.body:
            self._refuse("GET with body")
        if path.startswith("/services/oauth2/") or "/Soap/" in path or "/soap/" in path.lower():
            self._refuse("endpoint not permitted")
        for regex, handler in (
            (_QUERY_RE, self._query),
            (_NEXT_RE, self._next),
            (_DESCRIBE_RE, self._describe),
            (_DELETED_RE, self._deleted),
            (_LIMITS_RE, self._limits),
        ):
            m = regex.match(path)
            if m:
                if m.group("version") != self.api_version:
                    self._refuse("api version mismatch")
                return handler(m, params, path)
        self._refuse("endpoint not permitted")

    def _check_headers(self, request, path):
        seen = set()
        for item in request.headers:
            if not (isinstance(item, tuple) and len(item) == 2):
                self._refuse("malformed header")
            name, value = item
            lname = str(name).lower()
            if lname not in _ALLOWED_HEADERS or lname in seen:
                self._refuse("header not permitted")
            if not isinstance(value, str) or "\r" in value or "\n" in value:
                self._refuse("malformed header")
            seen.add(lname)
            if lname == "authorization" and (path == _TOKEN_PATH or not value.startswith("Bearer ")):
                self._refuse("authorization header not permitted here")

    def _check_token_body(self, request):
        ctype = dict((k.lower(), v) for k, v in request.headers).get("content-type")
        if ctype != _FORM:
            self._refuse("token request must be form encoded")
        body = request.body
        if not isinstance(body, bytes):
            self._refuse("token request without body")
        try:
            pairs = parse_qsl(body.decode("ascii"), keep_blank_values=True, strict_parsing=True)
        except (UnicodeDecodeError, ValueError):
            raise RefusedRequest(detail="malformed token body") from None
        keys = [k for k, _ in pairs]
        if sorted(keys) != ["client_id", "client_secret", "grant_type"]:
            self._refuse("token body must hold exactly grant_type, client_id, client_secret")
        values = dict(pairs)
        if values["grant_type"] != "client_credentials":
            raise RefusedRequest("grant_type_refused", detail="only client_credentials is permitted")
        if not values["client_id"] or not values["client_secret"]:
            self._refuse("empty client credentials")

    def _query(self, m, params, path):
        if set(params) != {"q"}:
            self._refuse("query takes exactly one parameter q")
        parsed = parse_soql(params["q"])
        if parsed is None:
            self._refuse("SOQL is not a generated shape")
        allowed = self._fields.get(self._contract_object(parsed.object))
        for name in parsed.fields:
            if name not in allowed:
                self._refuse("SOQL field not in contract")
        return Checked(m.group("kind"), parsed.object)

    def _next(self, m, params, path):
        if params:
            self._refuse("nextRecordsUrl takes no parameters")
        self.check_next_records_url(path)
        return Checked("next")

    def _describe(self, m, params, path):
        if params:
            self._refuse("describe takes no parameters")
        return Checked("describe", self._contract_object(m.group("object")))

    def _deleted(self, m, params, path):
        if set(params) != {"start", "end"}:
            self._refuse("deleted takes exactly start and end")
        for key in ("start", "end"):
            if not ISO_PARAM_RE.match(params[key]):
                self._refuse("deleted start/end must be ISO-8601 UTC")
        return Checked("deleted", self._contract_object(m.group("object")))

    def _limits(self, m, params, path):
        if params:
            self._refuse("limits takes no parameters")
        return Checked("limits")
