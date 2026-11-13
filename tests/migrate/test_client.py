"""Read-only refusal matrix, origin, redirect and authentication rules (AC3)."""

import os
import re
import unittest
from urllib.parse import quote

from crm_migrate.auth import build_token_request, parse_token_response
from crm_migrate.client import SalesforceClient
from crm_migrate.contract import soql_select
from crm_migrate.errors import (HttpError, OriginError, ProtocolError, RedirectRefused, RefusedRequest,
                                ResponseTooLarge)
from crm_migrate.messages import Request, Response
from crm_migrate.policy import RequestPolicy, validate_origin

from . import LIB
from .fake_salesforce import (FAKE_API_VERSION, FAKE_CLIENT_ID, FAKE_CLIENT_SECRET, FAKE_ORIGIN, SENTINEL,
                              client_for, contract, make_fake)

O = FAKE_ORIGIN
D = f"{O}/services/data/v{FAKE_API_VERSION}"
AUTH = (("Accept", "application/json"), ("Authorization", "Bearer x"))
FORM = (("Accept", "application/json"), ("Content-Type", "application/x-www-form-urlencoded"))
GOOD_BODY = f"grant_type=client_credentials&client_id=a&client_secret=b".encode()


class CountingTransport:
    def __init__(self):
        self.sent = 0

    def send(self, request):
        self.sent += 1
        return Response(200, {"date": "Tue, 10 Nov 2026 09:00:00 GMT"}, b"{}")


def q(soql):
    return "q=" + quote(soql, safe="")


class RefusalMatrixTest(unittest.TestCase):
    def setUp(self):
        self.transport = CountingTransport()
        self.client = SalesforceClient(O, FAKE_API_VERSION, self.transport, contract())
        acc = contract().object("Account")
        self.good_q = q(soql_select(acc, ("Id", "Name")))

    def refused(self, method, url, headers=AUTH, body=None, exc=(RefusedRequest, OriginError)):
        with self.assertRaises(exc):
            self.client._send(Request(method, url, headers, body))
        self.assertEqual(self.transport.sent, 0, f"transport called for {method} {url}")

    def test_permitted_requests_reach_the_transport(self):
        for method, url, headers, body in (
            ("POST", f"{O}/services/oauth2/token", FORM, GOOD_BODY),
            ("GET", f"{D}/query/?{self.good_q}", AUTH, None),
            ("GET", f"{D}/queryAll/?{self.good_q}", AUTH, None),
            ("GET", f"{D}/query/01gS7000001-2000", AUTH, None),
            ("GET", f"{D}/sobjects/Account/describe/", AUTH, None),
            ("GET", f"{D}/sobjects/Account/deleted/?start=2026-11-01T00:00:00Z&end=2026-11-10T00:00:00Z", AUTH, None),
            ("GET", f"{D}/limits/", AUTH, None),
        ):
            self.client._send(Request(method, url, headers, body))
        self.assertEqual(self.transport.sent, 7)

    def test_write_methods_on_data_urls(self):
        for method in ("POST", "PATCH", "PUT", "DELETE", "HEAD", "OPTIONS"):
            for path in ("/sobjects/Account/", "/sobjects/Account/001S70000000001AAA", f"/query/?{self.good_q}",
                         "/sobjects/Account/describe/"):
                with self.subTest(method=method, path=path):
                    self.refused(method, D + path, body=b"{}" if method != "HEAD" else None)

    def test_forbidden_apis(self):
        for path in (
            f"/services/data/v{FAKE_API_VERSION}/composite/",
            f"/services/data/v{FAKE_API_VERSION}/composite/sobjects",
            f"/services/data/v{FAKE_API_VERSION}/composite/batch",
            f"/services/data/v{FAKE_API_VERSION}/jobs/ingest",
            f"/services/data/v{FAKE_API_VERSION}/jobs/query",
            "/services/async/62.0/job",
            "/services/Soap/u/62.0",
            "/services/Soap/c/62.0",
            "/services/apexrest/anything",
            f"/services/data/v{FAKE_API_VERSION}/tooling/query/",
            f"/services/data/v{FAKE_API_VERSION}/sobjects/Account/001S70000000001AAA",
            f"/services/data/v{FAKE_API_VERSION}/sobjects/",
            f"/services/data/v{FAKE_API_VERSION}/search/",
            f"/services/data/v{FAKE_API_VERSION}/sobjects/Account/updated/",
            "/services/oauth2/authorize",
            "/services/oauth2/revoke",
            "/services/oauth2/userinfo",
        ):
            for method in ("GET", "POST"):
                with self.subTest(method=method, path=path):
                    self.refused(method, O + path, body=b"{}" if method == "POST" else None)

    def test_parameter_rules(self):
        cases = [
            f"{D}/sobjects/Account/describe/?x=1",
            f"{D}/sobjects/Case/describe/",
            f"{D}/sobjects/account/describe/",
            f"{D}/query/?{self.good_q}&batchSize=1",
            f"{D}/query/?{self.good_q}&{self.good_q}",
            f"{D}/query/",
            f"{D}/query/?" + q("SELECT Id FROM Account WHERE Name = 'x' ORDER BY Id"),
            f"{D}/query/?" + q("SELECT FIELDS(ALL) FROM Account ORDER BY Id"),
            f"{D}/query/?" + q("SELECT HtmlBody FROM EmailMessage ORDER BY Id"),
            f"{D}/query/?" + q("SELECT Id FROM Case ORDER BY Id"),
            f"{D}/query/01gS7000001-2000?x=1",
            f"{D}/sobjects/Account/deleted/?start=2026-11-01T00:00:00Z",
            f"{D}/sobjects/Account/deleted/?start=2026-11-01&end=2026-11-10",
            f"{D}/sobjects/Account/deleted/?start=2026-11-01T00:00:00Z&end=2026-11-10T00:00:00Z&x=1",
            f"{D}/limits/?x=1",
            f"{O}/services/data/v61.0/limits/",
        ]
        for url in cases:
            with self.subTest(url=url):
                self.refused("GET", url)

    def test_token_rules(self):
        tok = f"{O}/services/oauth2/token"
        for body in (b"grant_type=password&client_id=a&client_secret=b",
                     b"grant_type=client_credentials&client_id=a&client_secret=b&username=u",
                     b"grant_type=client_credentials&client_id=a&client_secret=b&password=p",
                     b"grant_type=refresh_token&client_id=a&client_secret=b",
                     b"grant_type=client_credentials&client_id=a", b"", None):
            with self.subTest(body=body):
                self.refused("POST", tok, FORM, body)
        self.refused("POST", tok + "?grant_type=client_credentials", FORM, GOOD_BODY)
        self.refused("POST", tok, FORM + (("Authorization", "Bearer x"),), GOOD_BODY)
        self.refused("POST", tok, (("Content-Type", "application/json"),), GOOD_BODY)
        self.refused("GET", tok)
        with self.assertRaises(RefusedRequest):
            build_token_request(O, "a", "b", grant_type="password")

    def test_origin_and_url_rules(self):
        path = "/services/data/v62.0/limits/"
        for url in (
            "http://example.my.salesforce.com" + path,
            "https://other.my.salesforce.com" + path,
            "https://example.my.salesforce.com:443" + path,
            "https://user@example.my.salesforce.com" + path,
            "https://example.my.salesforce.com.attacker.example.test" + path,
            "https://login.salesforce.com" + path,
            O + path + "#frag",
            O + "/services/data/v62.0/%2e%2e/limits/",
            O + "/services/data/v62.0//limits/",
            O + "/services/data/v62.0/./limits/",
            O + "/services/data/v62.0/limits/;x",
            O + "/services/data/v62.0/limits/ ",
            "/services/data/v62.0/limits/",
        ):
            with self.subTest(url=url):
                self.refused("GET", url)

    def test_header_rules(self):
        url = f"{D}/limits/"
        for headers in ((("Cookie", "a=b"),), (("Accept", "a\r\nX: y"),), (("Accept", "a"), ("accept", "b")),
                        (("Authorization", "Basic abc"),), (("X-SFDC-Session", "x"),)):
            with self.subTest(headers=headers):
                self.refused("GET", url, headers)


class OriginValidationTest(unittest.TestCase):
    def test_accepted(self):
        for origin in ("https://example.my.salesforce.com", "https://example.sandbox.my.salesforce.com",
                       "https://ex-ample--uat.sandbox.my.salesforce.com"):
            self.assertEqual(validate_origin(origin), origin)

    def test_refused(self):
        for origin in ("http://example.my.salesforce.com", "https://login.salesforce.com",
                       "https://test.salesforce.com", "https://example.salesforce.com",
                       "https://example.lightning.force.com", "https://my.salesforce.com",
                       "https://example.my.salesforce.com/", "https://example.my.salesforce.com:8443",
                       "https://Example.my.salesforce.com", "https://example.my.salesforce.com.example.test",
                       "https://example.my.salesforce.com/services", "", None):
            with self.subTest(origin=origin), self.assertRaises(OriginError):
                SalesforceClient(origin, FAKE_API_VERSION, CountingTransport(), contract())

    def test_api_version_refused(self):
        for version in ("v62.0", "62", "62.0.1", "../62.0"):
            with self.subTest(version=version), self.assertRaises(OriginError):
                RequestPolicy(O, version, {})


class LiveFlowRulesTest(unittest.TestCase):
    def test_instance_url_mismatch_aborts(self):
        fake = make_fake(contract(), instance_url="https://other.my.salesforce.com")
        client = client_for(fake, authenticate=False)
        with self.assertRaises(OriginError):
            client.authenticate(FAKE_CLIENT_ID, FAKE_CLIENT_SECRET)
        with self.assertRaises(ProtocolError):
            client.describe("Account")                  # never authenticated: no data request
        self.assertEqual([p for _, p in fake.requests], ["/services/oauth2/token"])

    def test_parse_token_response(self):
        self.assertEqual(parse_token_response({"access_token": "t", "instance_url": O}, O), "t")
        for doc in ({"access_token": "t", "instance_url": O + "/"}, {"access_token": "t"},
                    {"instance_url": O}, {"access_token": "t", "instance_url": O, "token_type": "MAC"}, []):
            with self.subTest(doc=doc), self.assertRaises((OriginError, ProtocolError)):
                parse_token_response(doc, O)

    def test_redirect_on_token_and_data(self):
        fake = make_fake(contract(), redirect_paths=(r"/oauth2/token",))
        with self.assertRaises(RedirectRefused):
            client_for(fake)
        fake = make_fake(contract(), redirect_paths=(r"/describe/",))
        client = client_for(fake)
        with self.assertRaises(RedirectRefused):
            client.describe("Account")
        self.assertEqual(len(fake.requests), 2)        # token + one describe, nothing followed

    def _first_pages(self, fake):
        client = client_for(fake)
        acc = contract().object("Account")
        return client, list(client.iter_pages(soql_select(acc, ("Id", "SystemModstamp")), all_rows=True))

    def test_absolute_next_records_url_refused_before_transport(self):
        fake = make_fake(contract(), absolute_next=True)
        with self.assertRaises(RefusedRequest) as ctx:
            self._first_pages(fake)
        self.assertEqual(ctx.exception.code, "next_records_url_refused")
        self.assertFalse(any(re.search(r"/query/01g", p) for _, p in fake.requests))

    def test_foreign_next_records_url_refused(self):
        fake = make_fake(contract(), foreign_next=True)
        with self.assertRaises(RefusedRequest):
            self._first_pages(fake)
        self.assertEqual(sum(1 for _, p in fake.requests if p.endswith("/describe")), 0)

    def test_next_records_url_paging_works(self):
        fake = make_fake(contract())
        _, pages = self._first_pages(fake)
        self.assertEqual(len(pages), 4)
        self.assertEqual(sum(len(p) for p in pages), 24)

    def test_error_body_never_kept(self):
        fake = make_fake(contract(), error_paths=(r"/limits",))
        client = client_for(fake)
        with self.assertRaises(HttpError) as ctx:
            client.server_time()
        exc = ctx.exception
        self.assertEqual((exc.status, exc.sf_error), (500, "UNKNOWN_EXCEPTION"))
        self.assertNotIn(SENTINEL.lower(), str(exc).lower())
        self.assertNotIn(SENTINEL.lower(), repr(exc.args).lower())

    def test_bad_credentials_error_code_only(self):
        fake = make_fake(contract())
        client = client_for(fake, authenticate=False)
        with self.assertRaises(HttpError) as ctx:
            client.authenticate("wrong-id", "wrong-secret")
        self.assertEqual(ctx.exception.sf_error, "INVALID_CLIENT")
        self.assertNotIn("wrong-secret", str(ctx.exception))

    def test_server_time_requires_date_header(self):
        fake = make_fake(contract(), drop_date=True)
        with self.assertRaises(ProtocolError):
            client_for(fake).server_time()

    def test_response_size_limit(self):
        fake = make_fake(contract())
        client = SalesforceClient(O, FAKE_API_VERSION, fake, contract(), max_bytes=200)
        client.authenticate(FAKE_CLIENT_ID, FAKE_CLIENT_SECRET)
        with self.assertRaises(ResponseTooLarge):
            client.describe("Account")

    def test_authorization_attached_only_by_client_to_origin(self):
        seen = []

        class Recorder:
            def __init__(self, inner):
                self.inner = inner

            def send(self, request):
                seen.append(request)
                return self.inner.send(request)

        fake = make_fake(contract())
        client = SalesforceClient(O, FAKE_API_VERSION, Recorder(fake), contract())
        client.authenticate(FAKE_CLIENT_ID, FAKE_CLIENT_SECRET)
        client.describe("Account")
        client.server_time()
        token_req, *data_reqs = seen
        self.assertNotIn("authorization", {k.lower() for k, _ in token_req.headers})
        for req in data_reqs:
            self.assertTrue(req.url.startswith(O + "/"))
            self.assertIn(("Authorization", "Bearer synthetic-token-" + SENTINEL), req.headers)
        self.assertEqual(fake.write_requests, 0)

    def test_redirect_status_from_any_transport_is_an_error(self):
        class Redirecting:
            def send(self, request):
                return Response(301, {"location": "https://elsewhere.example.test/"}, b"")

        client = SalesforceClient(O, FAKE_API_VERSION, Redirecting(), contract())
        with self.assertRaises(RedirectRefused):
            client.authenticate("a", "b")


class SourceScanTest(unittest.TestCase):
    """No proxy-aware or alternative HTTP stack anywhere in the package."""

    FORBIDDEN_MODULES = {"urllib.request", "socket", "requests", "subprocess", "urllib3", "httpx", "ftplib",
                         "smtplib", "xmlrpc.client", "asyncio"}
    FORBIDDEN_ATTRS = {"set_tunnel", "urlopen", "HTTPConnection", "_create_unverified_context", "CERT_NONE"}

    def test_no_urllib_request_or_sockets(self):
        import ast
        pkg = os.path.join(LIB, "crm_migrate")
        files = sorted(n for n in os.listdir(pkg) if n.endswith(".py"))
        self.assertIn("transport.py", files)
        for name in files:
            with open(os.path.join(pkg, name), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                with self.subTest(file=name, line=getattr(node, "lineno", 0)):
                    if isinstance(node, ast.Import):
                        self.assertFalse({a.name for a in node.names} & self.FORBIDDEN_MODULES)
                    elif isinstance(node, ast.ImportFrom):
                        mod = node.module or ""
                        self.assertNotIn(mod, self.FORBIDDEN_MODULES)
                        self.assertFalse(mod == "urllib" and any(a.name == "request" for a in node.names))
                    elif isinstance(node, ast.Attribute):
                        self.assertNotIn(node.attr, self.FORBIDDEN_ATTRS)
                    elif isinstance(node, ast.keyword) and node.arg == "check_hostname":
                        self.fail("check_hostname keyword")
                    elif isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Attribute) and target.attr == "check_hostname":
                                self.assertIs(getattr(node.value, "value", None), True)

    def test_scan_catches_a_forbidden_import(self):
        import ast
        tree = ast.parse("import urllib.request\nfrom socket import create_connection\nc.set_tunnel('x')\n")
        hits = [n for n in ast.walk(tree)
                if (isinstance(n, ast.Import) and {a.name for a in n.names} & self.FORBIDDEN_MODULES)
                or (isinstance(n, ast.ImportFrom) and n.module in self.FORBIDDEN_MODULES)
                or (isinstance(n, ast.Attribute) and n.attr in self.FORBIDDEN_ATTRS)]
        self.assertEqual(len(hits), 3)


if __name__ == "__main__":
    unittest.main()
