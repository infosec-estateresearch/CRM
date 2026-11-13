"""``HttpsTransport`` with ``http.client.HTTPSConnection`` replaced by a recording stub."""

import http.client
import ssl
import unittest

from crm_migrate.contract import soql_select
from crm_migrate.errors import OriginError, RedirectRefused, RefusedRequest, ResponseTooLarge
from crm_migrate.messages import Request
from crm_migrate.policy import RequestPolicy
from crm_migrate.transport import HttpsTransport

from .fake_salesforce import FAKE_API_VERSION, FAKE_ORIGIN, contract

AUTH = (("Accept", "application/json"), ("Authorization", "Bearer x"))


class StubResponse:
    def __init__(self, status, headers, body):
        self.status, self._headers, self._body = status, headers, body

    def getheader(self, name):
        for k, v in self._headers:
            if k.lower() == name.lower():
                return v
        return None

    def getheaders(self):
        return list(self._headers)

    def read(self, n=-1):
        return self._body if n < 0 else self._body[:n]


class RecordingConnection:
    instances = []
    next_response = (200, [("Date", "Tue, 10 Nov 2026 09:00:00 GMT")], b"{}")

    def __init__(self, host, port=None, *, timeout=None, context=None, **kw):
        self.host, self.port, self.timeout, self.context, self.extra = host, port, timeout, context, kw
        self.requests = []
        self.closed = False
        RecordingConnection.instances.append(self)

    def set_tunnel(self, *a, **k):  # a proxy tunnel must never be configured
        raise AssertionError("set_tunnel called")

    def request(self, method, target, body=None, headers=None):
        self.requests.append((method, target, body, headers))

    def getresponse(self):
        return StubResponse(*RecordingConnection.next_response)

    def close(self):
        self.closed = True


class HttpsTransportTest(unittest.TestCase):
    def setUp(self):
        RecordingConnection.instances = []
        RecordingConnection.next_response = (200, [("Date", "Tue, 10 Nov 2026 09:00:00 GMT")], b"{}")
        self.policy = RequestPolicy(FAKE_ORIGIN, FAKE_API_VERSION, contract().fields_by_object())
        self.t = HttpsTransport(self.policy, connection_factory=RecordingConnection, max_bytes=1000)

    def url(self, path):
        return f"{FAKE_ORIGIN}/services/data/v{FAKE_API_VERSION}/{path}"

    def test_default_factory_is_https_connection(self):
        self.assertIs(HttpsTransport(self.policy)._factory, http.client.HTTPSConnection)

    def test_tls_context(self):
        ctx = self.t.tls_context
        self.assertGreaterEqual(ctx.minimum_version, ssl.TLSVersion.TLSv1_2)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)

    def test_permitted_request_uses_origin_host_443_and_context(self):
        acc = contract().object("Account")
        from urllib.parse import quote
        q = quote(soql_select(acc, ("Id",)), safe="")
        resp = self.t.send(Request("GET", self.url(f"query/?q={q}"), AUTH))
        self.assertEqual(resp.status, 200)
        (conn,) = RecordingConnection.instances
        self.assertEqual((conn.host, conn.port), ("example.my.salesforce.com", 443))
        self.assertIs(conn.context, self.t.tls_context)
        self.assertEqual(conn.requests[0][0], "GET")
        self.assertTrue(conn.requests[0][1].startswith(f"/services/data/v{FAKE_API_VERSION}/query/?q="))
        self.assertTrue(conn.closed)

    def test_refusal_happens_before_construction(self):
        for req in (
            Request("DELETE", self.url("sobjects/Account/001S70000000001AAA"), AUTH),
            Request("POST", self.url("composite/"), AUTH, b"{}"),
            Request("GET", "https://other.my.salesforce.com/services/data/v62.0/limits/", AUTH),
            Request("GET", "http://example.my.salesforce.com/services/data/v62.0/limits/", AUTH),
            Request("GET", self.url("sobjects/Account/describe/?a=1"), AUTH),
            Request("GET", f"{FAKE_ORIGIN}/services/Soap/u/62.0", AUTH),
        ):
            with self.subTest(req=req.method + " " + req.url):
                with self.assertRaises((RefusedRequest, OriginError)):
                    self.t.send(req)
        self.assertEqual(RecordingConnection.instances, [])

    def test_redirect_is_an_error(self):
        for status in (301, 302, 303, 307, 308):
            RecordingConnection.next_response = (status, [("Location", "https://elsewhere.example.test/")], b"")
            with self.subTest(status=status), self.assertRaises(RedirectRefused):
                self.t.send(Request("GET", self.url("limits/"), AUTH))
        self.assertTrue(all(c.closed for c in RecordingConnection.instances))
        self.assertTrue(all(len(c.requests) == 1 for c in RecordingConnection.instances))

    def test_size_limits(self):
        RecordingConnection.next_response = (200, [("Content-Length", "5000")], b"{}")
        with self.assertRaises(ResponseTooLarge):
            self.t.send(Request("GET", self.url("limits/"), AUTH))
        RecordingConnection.next_response = (200, [], b"x" * 1001)
        with self.assertRaises(ResponseTooLarge):
            self.t.send(Request("GET", self.url("limits/"), AUTH))

    def test_requires_policy(self):
        with self.assertRaises(TypeError):
            HttpsTransport(object())


if __name__ == "__main__":
    unittest.main()
