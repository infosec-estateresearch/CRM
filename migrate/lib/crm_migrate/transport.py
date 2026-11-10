"""The only real transport: ``http.client.HTTPSConnection``, no redirects, no proxies.

``urllib.request`` is deliberately not used: it honours proxy environment variables and
follows redirects. ``HTTPSConnection`` does neither unless ``set_tunnel`` is called,
which this module never does. The policy check is repeated here before a connection
object is even constructed.
"""

import http.client
import ssl
from urllib.parse import urlsplit

from .errors import RedirectRefused, ResponseTooLarge
from .messages import Response
from .policy import RequestPolicy

DEFAULT_MAX_BYTES = 64 * 1024 * 1024
DEFAULT_TIMEOUT = 60.0


def make_tls_context():
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


class HttpsTransport:
    def __init__(self, policy, *, timeout=DEFAULT_TIMEOUT, max_bytes=DEFAULT_MAX_BYTES,
                 connection_factory=None, tls_context=None):
        if not isinstance(policy, RequestPolicy):
            raise TypeError("HttpsTransport needs a RequestPolicy")
        self._policy = policy
        self._timeout = float(timeout)
        self._max_bytes = int(max_bytes)
        self._factory = connection_factory or http.client.HTTPSConnection
        self.tls_context = tls_context or make_tls_context()

    def send(self, request):
        self._policy.check(request)            # defence in depth: before any construction
        parts = urlsplit(request.url)
        target = parts.path + (("?" + parts.query) if parts.query else "")
        conn = self._factory(parts.hostname, 443, timeout=self._timeout, context=self.tls_context)
        try:
            conn.request(request.method, target, body=request.body, headers=dict(request.headers))
            resp = conn.getresponse()
            status = int(resp.status)
            if 300 <= status < 400:
                raise RedirectRefused(status=status)
            length = resp.getheader("Content-Length")
            if length is not None and length.isdigit() and int(length) > self._max_bytes:
                raise ResponseTooLarge(status=status)
            body = resp.read(self._max_bytes + 1)
            if len(body) > self._max_bytes:
                raise ResponseTooLarge(status=status)
            headers = {str(k).lower(): v for k, v in resp.getheaders()}
            return Response(status, headers, body)
        finally:
            conn.close()
