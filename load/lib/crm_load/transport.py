"""Transports. Tests inject a fake; the real run uses ``HttpsTransport``.

``HttpsTransport`` (named for the brief; it speaks plain HTTP) talks only to
``http://127.0.0.1:<port>/api/v1/``: any other scheme or host is refused at construction,
and redirects are never followed (``http.client`` does not follow them; a 3xx is an error).
Response bodies of errors are never logged or returned to the caller.
"""

import http.client
import json
import re
import urllib.parse

from .errors import TransportError

API_PREFIX = "/api/v1/"
ALLOWED_HEADERS = {"X-Skip-Duplicate-Check": "true"}
_ENTITY_PATH = re.compile(r"\A[A-Z][A-Za-z]{1,40}(?:/[A-Za-z0-9]{1,40})?\Z")


class Transport:
    def send(self, method, path, query=None, body=None, headers=None):  # pragma: no cover - interface
        """Returns (status, parsed JSON or None)."""
        raise NotImplementedError


class HttpsTransport(Transport):
    def __init__(self, host, port, api_key, timeout=60):
        if host != "127.0.0.1":
            raise TransportError("host_refused")
        if type(port) is not int or not 0 < port < 65536:
            raise TransportError("port_invalid")
        if not isinstance(api_key, str) or not api_key or any(c in api_key for c in "\r\n"):
            raise TransportError("api_key_missing")
        self.host, self.port, self._key, self.timeout = host, port, api_key, timeout

    def send(self, method, path, query=None, body=None, headers=None):
        if method not in ("GET", "POST", "PUT") or not _ENTITY_PATH.fullmatch(path):
            raise TransportError("request_refused")
        extra = dict(headers or {})
        if any(extra.get(k) != v for k, v in ALLOWED_HEADERS.items() if k in extra) or set(extra) - set(ALLOWED_HEADERS):
            raise TransportError("request_refused")
        url = API_PREFIX + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        headers = dict(extra, **{"X-Api-Key": self._key, "Accept": "application/json"})
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            conn.request(method, url, body=data, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            status = resp.status
        except (OSError, http.client.HTTPException):
            raise TransportError("connection_failed") from None
        finally:
            conn.close()
        if 300 <= status < 400:
            raise TransportError("redirect_refused", status)
        if status >= 400:
            return status, None
        try:
            return status, json.loads(raw.decode("utf-8")) if raw else None
        except (ValueError, UnicodeDecodeError):
            raise TransportError("response_unparseable", status) from None
