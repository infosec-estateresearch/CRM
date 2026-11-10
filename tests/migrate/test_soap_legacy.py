"""CRM-002-S: temporary SOAP legacy-credential adapter. In-process, no sockets."""

import datetime as _dt
import io
import json
import logging
import os
import re
import unittest
from collections import namedtuple

from crm_migrate import auth_soap, cli, hostcheck as hc, waiver as wv
from crm_migrate.client import SalesforceClient
from crm_migrate.contract import parse_soql
from crm_migrate.errors import ConfigError, MigrateError, OriginError, ProtocolError, RefusedRequest
from crm_migrate.log import LOGGER_NAME
from crm_migrate.messages import Request
from crm_migrate.metadata import evaluate_gate, run_gate
from crm_migrate.policy import (API_VERSION_RE, ISO_PARAM_RE, NEXT_RECORDS_RE, ORIGIN_RE, RequestPolicy,
                                validate_api_version, validate_origin)
from crm_migrate.transport import HttpsTransport

from .fake_salesforce import (FAKE_API_VERSION, FAKE_ORG_ID, FAKE_ORIGIN, FAKE_PASSWORD, FAKE_SESSION,
                              FAKE_USERNAME, SENTINEL, SOAP_SUCCESS_TEMPLATE, WRITE_CAPABLE, TempDirMixin,
                              contract, make_fake)

TODAY = _dt.date(2026, 11, 10)
WAIVER_URL = wv.ISSUE_COMMENT_PREFIX + "1234567"
LOGIN = auth_soap.LOGIN_HOST
SECRETS = (FAKE_PASSWORD, FAKE_SESSION, SENTINEL)
ENV = {"CRM_SF_ORIGIN": FAKE_ORIGIN, "CRM_SF_API_VERSION": FAKE_API_VERSION}
CREDS = json.dumps({"username": FAKE_USERNAME, "password": FAKE_PASSWORD}).encode()
St = namedtuple("St", "st_mode st_uid st_gid")


def policy(login_host=LOGIN):
    return RequestPolicy(FAKE_ORIGIN, FAKE_API_VERSION, contract().fields_by_object(), soap_login_host=login_host)


def login_request(host=LOGIN, action="login", body=None, path=None, headers=None):
    return Request("POST", f"https://{host}" + (path or f"/services/Soap/u/{FAKE_API_VERSION}/"),
                   headers or auth_soap.soap_headers(action),
                   body if body is not None else auth_soap.render_login_body(FAKE_USERNAME, FAKE_PASSWORD))


def envelope(op_xml, header=""):
    return ('<?xml version="1.0" encoding="UTF-8"?><soapenv:Envelope xmlns:soapenv="' + auth_soap.NS_ENV +
            '" xmlns:urn="urn:partner.soap.sforce.com">' + header + "<soapenv:Body>" + op_xml +
            "</soapenv:Body></soapenv:Envelope>").encode()


def soap_client(fake, login_host=LOGIN):
    return SalesforceClient(FAKE_ORIGIN, FAKE_API_VERSION, fake, contract(), soap_login_host=login_host)


class Spy:
    def __init__(self):
        self.calls = 0

    def send(self, request):
        self.calls += 1
        raise AssertionError("transport must not be reached")


def assert_no_secret(case, text):
    for s in SECRETS:
        case.assertNotIn(s, text)


class SoapRefusalMatrixTest(unittest.TestCase):
    OPS = ("query", "queryAll", "create", "update", "delete", "upsert", "merge", "undelete", "emptyRecycleBin",
           "setPassword", "resetPassword", "retrieve", "search", "convertLead", "describeGlobal",
           "executeanonymous", "compileClasses", "deploy", "createMetadata")

    def refuse(self, request, exc=(RefusedRequest, OriginError)):
        spy = Spy()
        client = SalesforceClient(FAKE_ORIGIN, FAKE_API_VERSION, spy, contract(), soap_login_host=LOGIN)
        with self.assertRaises(exc):
            client._send_soap(request)
        with self.assertRaises(exc):
            HttpsTransport(policy(), connection_factory=lambda *a, **k: self.fail("connected")).send(request)
        self.assertEqual(spy.calls, 0)

    def test_login_and_logout_templates_pass(self):
        self.assertEqual(policy().check(login_request()).kind, "soap_login")
        logout = Request("POST", f"{FAKE_ORIGIN}/services/Soap/u/{FAKE_API_VERSION}/{FAKE_ORG_ID}",
                         auth_soap.soap_headers("logout"), auth_soap.render_logout_body(FAKE_SESSION))
        self.assertEqual(policy().check(logout).kind, "soap_logout")

    def test_every_other_operation_refused(self):
        for op in self.OPS:
            for action in (op, "login", "logout"):
                with self.subTest(op=op, action=action):
                    self.refuse(login_request(action=action, body=envelope(f"<urn:{op}/>")))
                    self.refuse(Request("POST", f"{FAKE_ORIGIN}/services/Soap/u/{FAKE_API_VERSION}/{FAKE_ORG_ID}",
                                        auth_soap.soap_headers(action), envelope(f"<urn:{op}/>")))

    def test_apex_metadata_enterprise_endpoints_refused(self):
        for path in ("/services/Soap/s/62.0", "/services/Soap/m/62.0", "/services/Soap/c/62.0/",
                     "/services/Soap/T/62.0", "/services/Soap/u/62.0/extra/x", "/services/Soap/u/62.0"):
            with self.subTest(path=path):
                self.refuse(login_request(path=path))

    def test_wrong_soap_action_and_headers(self):
        for action in ("", "query", "LOGIN", '"login"', "logout"):
            with self.subTest(action=action):
                self.refuse(login_request(action=action))
        self.refuse(login_request(headers=auth_soap.soap_headers("login") + (("Authorization", "Bearer x"),)))
        self.refuse(login_request(headers=(("Content-Type", "application/json"), ("SOAPAction", "login"))))

    def test_foreign_login_hosts(self):
        for host in ("evil.example.test", "test.salesforce.com", "example.my.salesforce.com", "login.salesforce.com:443"):
            with self.subTest(host=host):
                self.refuse(login_request(host=host))
        self.assertEqual(policy(auth_soap.SANDBOX_LOGIN_HOST).check(login_request(host="test.salesforce.com")).kind,
                         "soap_login")
        with self.assertRaises(OriginError):
            policy("evil.example.test")

    def test_non_template_bodies_refused(self):
        good = auth_soap.render_login_body(FAKE_USERNAME, FAKE_PASSWORD)
        for body in (good.replace(b"<?xml", b"<!DOCTYPE x><?xml"), good + b" ", good.replace(b"urn:login", b"urn:query"),
                     good.replace(b"</urn:password>", b"</urn:password><urn:extra>1</urn:extra>"),
                     envelope("<urn:login/><urn:delete/>")):
            with self.subTest(body=body[:40]):
                self.refuse(login_request(body=body))

    def test_soap_disabled_in_client_credentials_mode(self):
        p = RequestPolicy(FAKE_ORIGIN, FAKE_API_VERSION, contract().fields_by_object())
        with self.assertRaises(RefusedRequest):
            p.check(login_request())

    def test_version_range(self):
        for v in ("30.0", "64.1", "65.0", "9.0", "59.0\n", "٥٩.0"):
            with self.subTest(v=v), self.assertRaises(MigrateError):
                auth_soap.validate_soap_version(v)
        self.assertEqual(auth_soap.validate_soap_version("31.0"), "31.0")
        self.assertEqual(auth_soap.validate_soap_version("64.0"), "64.0")


class SoapParsingTest(unittest.TestCase):
    def test_dtd_and_entity_refused(self):
        ok = SOAP_SUCCESS_TEMPLATE.format(server_url=FAKE_ORIGIN, session=FAKE_SESSION).encode()
        for bad in (b'<!DOCTYPE x [<!ENTITY a "b">]>' + ok, b"<!entity a>" + ok, b"<!doctype x>" + ok):
            with self.subTest(bad=bad[:20]), self.assertRaises(ProtocolError) as cm:
                auth_soap.parse_xml(bad)
            self.assertEqual(cm.exception.code, "soap_dtd_refused")

    def test_size_limit(self):
        with self.assertRaises(ProtocolError):
            auth_soap.parse_xml(b" " * (auth_soap.MAX_SOAP_RESPONSE + 1))

    def test_fault_reduced_to_code(self):
        fake = make_fake(contract())
        client = soap_client(fake)
        with self.assertRaises(auth_soap.SoapFault) as cm:
            client.authenticate_soap(FAKE_USERNAME, "wrong-" + SENTINEL)
        self.assertEqual(cm.exception.sf_error, "INVALID_LOGIN")
        self.assertEqual(cm.exception.detail, "faultcode=sf:INVALID_LOGIN")
        assert_no_secret(self, str(cm.exception) + repr(cm.exception.args))

    def test_server_url_shapes(self):
        v = FAKE_API_VERSION
        good = f"{FAKE_ORIGIN}/services/Soap/u/{v}/{FAKE_ORG_ID}"
        self.assertEqual(auth_soap.origin_of_server_url(good, v)[0], FAKE_ORIGIN)
        for bad in (good + "\n", good.replace("https", "http"), good.replace(".com", ".com:8443"),
                    good + "?x=1", "https://example.salesforce.com/services/Soap/u/62.0/" + FAKE_ORG_ID,
                    good.replace("/u/", "/c/"), good.replace(v, "59.0"), "https://a@example.my.salesforce.com/x"):
            with self.subTest(bad=bad), self.assertRaises(OriginError):
                auth_soap.origin_of_server_url(bad, v)

    def test_xml_escaping(self):
        body = auth_soap.render_login_body("a&b<c>@example.test", "p'\"<&>")
        self.assertIn(b"a&amp;b&lt;c&gt;@example.test", body)
        self.assertIn(b"p&apos;&quot;&lt;&amp;&gt;", body)
        auth_soap.check_login_body(body)
        for bad in ("", " lead", "new\nline", "x" * 2000):
            with self.subTest(bad=bad[:8]), self.assertRaises(ConfigError) as cm:
                auth_soap.render_login_body(bad, "p")
            self.assertNotIn(bad or "\x00", str(cm.exception)) if bad else None


class SoapOriginBindingTest(unittest.TestCase):
    def test_login_then_rest_uses_session(self):
        fake = make_fake(contract())
        client = soap_client(fake)
        client.authenticate_soap(FAKE_USERNAME, FAKE_PASSWORD)
        self.assertEqual(client.auth_mode, "soap-legacy")
        self.assertNotIn(FAKE_SESSION, repr(client._soap_session))
        client.describe("Account")
        client.logout_soap()
        self.assertEqual([a for a, _ in fake.soap_requests], ["login", "logout"])
        self.assertEqual(fake.write_requests, 0)

    def test_origin_mismatch_aborts_before_rest(self):
        for url in ("https://other.my.salesforce.com/services/Soap/u/62.0/" + FAKE_ORG_ID,
                    "https://example.sandbox.my.salesforce.com/services/Soap/u/62.0/" + FAKE_ORG_ID,
                    "https://evil.example.test/services/Soap/u/62.0/" + FAKE_ORG_ID):
            with self.subTest(url=url):
                fake = make_fake(contract(), soap_server_url=url)
                client = soap_client(fake)
                with self.assertRaises(OriginError):
                    client.authenticate_soap(FAKE_USERNAME, FAKE_PASSWORD)
                self.assertIsNone(client._token)
                self.assertEqual([p for _, p in fake.requests if "/services/data/" in p], [])


def write_capable_fake(**kw):
    return make_fake(contract(), org_kwargs={"describe_overrides": {o.name: dict(WRITE_CAPABLE)
                                                                     for o in contract().objects}}, **kw)


class WaiverTest(unittest.TestCase):
    def doc(self, **over):
        d = {"authorisation": WAIVER_URL, "identity": "legacy-eric", "expires": "2026-11-30"}
        d.update(over)
        return json.dumps(d).encode()

    def test_valid(self):
        self.assertEqual(wv.parse_waiver(self.doc(), TODAY)["authorisation"], WAIVER_URL)
        self.assertEqual(wv.parse_waiver(self.doc(expires="2026-12-10"), TODAY)["expires"], "2026-12-10")
        self.assertEqual(wv.parse_waiver(self.doc(expires="2026-11-10"), TODAY)["expires"], "2026-11-10")

    def test_broken_waivers(self):
        cases = [b"", b"{", b"[]", self.doc(expires="2026-11-09"), self.doc(expires="2026-12-11"),
                 self.doc(expires="2026-11-30\n"), self.doc(expires="30/11/2026"), self.doc(expires="2026-02-30"),
                 self.doc(identity="other"), self.doc(authorisation=WAIVER_URL + "\n"),
                 self.doc(authorisation=WAIVER_URL.replace("issues/9", "issues/10")),
                 self.doc(authorisation="https://evil.example.test/issues/9#issuecomment-1"),
                 self.doc(extra=1), b'{"authorisation": "x", "authorisation": "y"}', b"x" * 5000]
        for raw in cases:
            with self.subTest(raw=raw[:60]), self.assertRaises(ConfigError):
                wv.parse_waiver(raw, TODAY)
        with self.assertRaises(ConfigError):
            wv.load_waiver("/nonexistent/waiver.json", TODAY)

    def test_gate_pure(self):
        fake = write_capable_fake()
        describes = {o.name: fake.org.describe(o.name) for o in contract().objects}
        failed = evaluate_gate(contract(), describes)
        self.assertFalse(failed.ok)
        self.assertEqual(failed.report["identity"], "write-capable")
        waived = evaluate_gate(contract(), describes, wv.parse_waiver(self.doc(), TODAY))
        self.assertTrue(waived.ok)
        self.assertEqual(waived.report["identity"], f"write-capable (waived: {WAIVER_URL})")
        self.assertEqual(waived.report["writable_objects"], len(contract().objects))
        # every other gate rule unchanged under the waiver
        describes["Account"] = dict(describes["Account"], queryable=False)
        self.assertFalse(evaluate_gate(contract(), describes, wv.parse_waiver(self.doc(), TODAY)).ok)

    def test_client_credentials_ignores_waiver(self):
        from .fake_salesforce import client_for
        fake = write_capable_fake()
        client = client_for(fake)
        client.write_waiver = wv.parse_waiver(self.doc(), TODAY)   # even if injected, it is ignored
        self.assertFalse(run_gate(client, contract()).ok)
        with self.assertRaises(ConfigError):
            client.set_write_waiver(client.write_waiver)


class StdinTest(unittest.TestCase):
    def test_valid_and_closed(self):
        stream = io.BytesIO(CREDS)
        self.assertEqual(cli.read_stdin_credentials(stream), (FAKE_USERNAME, FAKE_PASSWORD))
        self.assertTrue(stream.closed)

    def test_broken(self):
        for raw in (b"", b"x" * 4097, b"[]", b"{}", b"not json " + FAKE_PASSWORD.encode(),
                    json.dumps({"username": FAKE_USERNAME}).encode(),
                    json.dumps({"username": FAKE_USERNAME, "password": FAKE_PASSWORD, "x": 1}).encode(),
                    json.dumps({"username": FAKE_USERNAME, "password": 1}).encode(),
                    json.dumps({"username": "", "password": FAKE_PASSWORD}).encode(),
                    b'{"username": "a", "username": "b", "password": "c"}', b"\xff\xfe"):
            with self.subTest(raw=raw[:30]), self.assertRaises(ConfigError) as cm:
                cli.read_stdin_credentials(io.BytesIO(raw))
            assert_no_secret(self, str(cm.exception))
            self.assertIsNone(cm.exception.__context__ if cm.exception.__suppress_context__ is False else None)

    def test_no_environment_fallback(self):
        env = dict(ENV, NIF_SRC_SALESFORCE_USER=FAKE_USERNAME, NIF_SRC_SALESFORCE_PASS=FAKE_PASSWORD,
                   CRM_SF_USERNAME=FAKE_USERNAME, CRM_SF_PASSWORD=FAKE_PASSWORD)
        with self.assertRaises(ConfigError):
            cli.legacy_client(env, contract(), io.BytesIO(b""), transport=make_fake(contract()))

    def test_client_secret_names_refused(self):
        with self.assertRaises(ConfigError):
            cli.load_legacy_config(dict(ENV, CRM_SF_CLIENT_SECRET="x"))
        self.assertEqual(cli.load_legacy_config({"CRM_SF_ORIGIN": FAKE_ORIGIN})["CRM_SF_API_VERSION"], "59.0")


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(self.format(record))


class CliSoapTest(TempDirMixin, unittest.TestCase):
    def run_cli(self, argv, fake, stdin=CREDS, environ=ENV):
        out, err, cap = io.StringIO(), io.StringIO(), Capture()
        logger = logging.getLogger(LOGGER_NAME)
        logger.addHandler(cap)
        try:
            rc = cli.main(argv, environ=dict(environ), transport=fake, stdout=out, stderr=err,
                          stdin=io.BytesIO(stdin), today=TODAY)
        finally:
            logger.removeHandler(cap)
        text = out.getvalue() + err.getvalue() + "\n".join(cap.lines)
        assert_no_secret(self, text)
        return rc, out.getvalue(), text

    def files_text(self, root):
        chunks = []
        for d, _, names in os.walk(root):
            for n in names:
                with open(os.path.join(d, n), "rb") as fh:
                    chunks.append(fh.read().decode("latin-1"))
        return "\n".join(chunks)

    def legacy(self, mode, *extra):
        out = os.path.join(self.tmp(), "out")
        return out, [mode, "--out", out, "--auth", "soap-legacy", "--credentials-stdin", *extra]

    def write_waiver(self, expires="2026-11-30"):
        path = os.path.join(self.tmp(), "waiver.json")
        with open(path, "w") as fh:
            json.dump({"authorisation": WAIVER_URL, "identity": "legacy-eric", "expires": expires}, fh)
        return path

    def test_end_to_end_reconciled_under_soap(self):
        fake = write_capable_fake()
        out, argv = self.legacy("extract", "--waiver", self.write_waiver())
        rc, stdout, _ = self.run_cli(argv, fake)
        self.assertEqual(rc, 0, stdout)
        self.assertIn("status=RECONCILED", stdout)
        with open(os.path.join(out, "manifest.json")) as fh:
            manifest = json.load(fh)
        self.assertEqual(manifest["identity"], f"write-capable (waived: {WAIVER_URL})")
        self.assertEqual(manifest["writable_objects"], len(contract().objects))
        assert_no_secret(self, self.files_text(out))
        self.assertEqual(fake.write_requests, 0)
        self.assertEqual([a for a, _ in fake.soap_requests], ["login", "logout"])

    def test_write_capable_without_waiver_fails_with_no_data_query(self):
        for extra in ((), ("--waiver", self.write_waiver("2026-11-01")), ("--waiver", "/nonexistent/w.json")):
            with self.subTest(extra=extra):
                fake = write_capable_fake()
                out, argv = self.legacy("contract-check", *extra)
                rc, stdout, _ = self.run_cli(argv, fake)
                self.assertIn(rc, (2, 3))
                self.assertEqual([p for _, p in fake.requests if "/query" in p], [])
                if not extra:
                    self.assertIn("identity: write-capable", stdout)

    def test_contract_check_with_waiver_reports_identity(self):
        fake = write_capable_fake()
        out, argv = self.legacy("contract-check", "--waiver", self.write_waiver())
        rc, stdout, _ = self.run_cli(argv, fake)
        self.assertEqual(rc, 0)
        self.assertIn(f"identity: write-capable (waived: {WAIVER_URL})", stdout)

    def test_failures_leak_nothing(self):
        cases = [(make_fake(contract()), b'{"username": "user@example.test", "password": "bad-' + SENTINEL.encode() + b'"}'),
                 (make_fake(contract(), soap_server_url="https://other.my.salesforce.com/services/Soap/u/62.0/"
                            + FAKE_ORG_ID), CREDS),
                 (make_fake(contract()), b"x" * 5000)]
        for fake, stdin in cases:
            with self.subTest():
                out, argv = self.legacy("count")
                rc, _, text = self.run_cli(argv, fake, stdin=stdin)
                self.assertNotEqual(rc, 0)
                if os.path.isdir(out):
                    assert_no_secret(self, self.files_text(out))
                self.assertEqual([p for _, p in fake.requests if "/services/data/" in p], [])

    def test_flag_combinations(self):
        out = os.path.join(self.tmp(), "o")
        for argv in (["count", "--out", out, "--auth", "soap-legacy"],
                     ["count", "--out", out, "--credentials-stdin"],
                     ["count", "--out", out, "--waiver", "/x"]):
            with self.subTest(argv=argv):
                rc, _, _ = self.run_cli(argv, make_fake(contract()))
                self.assertEqual(rc, 2)


class LegacyEnvParserTest(unittest.TestCase):
    FIXTURE = (
        "# synthetic ELT env file\n"
        "NIF_DB_HOST=db.example.test\n"
        "NIF_SRC_SALESFORCE_USER=user@example.test\n"           # CRM-002-T: no export, no quotes
        "  NIF_SRC_SALESFORCE_PASS = " + FAKE_PASSWORD + "  \n"
        "OTHER_SECRET=\"unrelated value with spaces\"\n"
        "\n"
        "NIF_SRC_SALESFORCE_TOKEN=ignored\n"
        "UNRELATED_CMD=$(not parsed) with spaces\n"
        "UNRELATED_CMD=duplicate of an unrelated name is ignored\n"
    )

    def test_reads_only_the_two_names(self):
        creds, errors = hc.parse_legacy_env(self.FIXTURE)
        self.assertEqual(errors, [])
        self.assertEqual(creds, {"username": FAKE_USERNAME, "password": FAKE_PASSWORD})
        self.assertEqual(json.loads(hc.legacy_credentials_json(creds)), creds)

    def test_quoting(self):
        # CRM-002-T: the consumer keeps quotes literally, so a quoted target value is refused.
        for raw in ('"p#w!"', "'p$w\\x'", "'pw'"):
            text = f"NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS={raw}\n"
            self.assertIsNone(hc.parse_legacy_env(text)[0])
        text = "NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS=plain\n"
        self.assertEqual(hc.parse_legacy_env(text)[0]["password"], "plain")

    def test_broken(self):
        base = "NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS=p\n"
        cases = {
            "duplicate": base + "NIF_SRC_SALESFORCE_PASS=q\n",
            "missing": "NIF_SRC_SALESFORCE_USER=u\n",
            "empty": "NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS=\n",
            "unbalanced": "NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS=\"p\n",
            "expansion": "NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS=p$HOME\n",
            "dq_expansion": "NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS=\"p$x\"\n",
            "space": "NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS=p q\n",
            # CRM-002-T: "garbage line" and "NAME = u" are no longer refused (the consumer skips
            # the one and strips the other); they are replaced by refused target lines.
            "export_target": "export NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS=p\n",
            "quoted_target": "NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS='p'\n",
        }
        for name, text in cases.items():
            with self.subTest(name):
                creds, errors = hc.parse_legacy_env(text.replace("=p", "=" + "s" + SENTINEL, 1) if name == "duplicate" else text)
                self.assertIsNone(creds)
                self.assertTrue(errors)
                assert_no_secret(self, " ".join(errors))

    def test_fingerprint_and_unchanged(self):
        st = os.stat(__file__)
        a = hc.fingerprint(b"x", st)
        self.assertEqual(hc.check_unchanged(a, hc.fingerprint(b"x", st)), [])
        self.assertTrue(hc.check_unchanged(a, hc.fingerprint(b"y", st)))
        st2 = os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, st.st_uid, st.st_gid, st.st_size,
                              st.st_atime, st.st_mtime + 1, st.st_ctime))
        self.assertNotEqual(a.split()[1], hc.fingerprint(b"x", st2).split()[1]) if st2.st_mtime_ns != st.st_mtime_ns else None

    def test_unconfigured_path_refuses(self):
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(hc.legacy_main("legacy-credentials", "", out, err), 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("refused", err.getvalue())

    def test_legacy_main_on_synthetic_file(self):
        import tempfile
        me = os.getuid()                              # tests run unprivileged: "root" is the test user
        with tempfile.TemporaryDirectory() as d:
            d = os.path.realpath(d)
            path = os.path.join(d, "elt.env")
            with open(path, "w") as fh:
                fh.write(self.FIXTURE)
            os.chmod(path, 0o600)
            before = os.stat(path)
            out, err = io.StringIO(), io.StringIO()
            self.assertEqual(hc.legacy_main("legacy-credentials", path, out, err, owner_uid=me), 0)
            self.assertEqual(json.loads(out.getvalue())["password"], FAKE_PASSWORD)
            fp1, fp2 = io.StringIO(), io.StringIO()
            hc.legacy_main("legacy-fingerprint", path, fp1, err, owner_uid=me)
            hc.legacy_main("legacy-fingerprint", path, fp2, err, owner_uid=me)
            self.assertEqual(fp1.getvalue(), fp2.getvalue())
            self.assertNotIn(FAKE_PASSWORD, fp1.getvalue())
            self.assertEqual(os.stat(path).st_mtime_ns, before.st_mtime_ns)
            link = os.path.join(d, "link.env")
            os.symlink(path, link)
            self.assertEqual(hc.legacy_main("legacy-credentials", link, io.StringIO(), err, owner_uid=me), 1)
            # the real default owner (root) refuses a file the test user owns
            if me != 0:
                self.assertEqual(hc.legacy_main("legacy-credentials", path, io.StringIO(), io.StringIO()), 1)

    def test_waiver_file_stat(self):
        import stat as S
        self.assertEqual(hc.check_waiver_file_stat(St(S.S_IFREG | 0o600, 0, 0)), [])
        self.assertEqual(hc.check_waiver_file_stat(None), [])
        for bad in (St(S.S_IFREG | 0o644, 0, 0), St(S.S_IFREG | 0o600, 1000, 0), St(S.S_IFLNK | 0o600, 0, 0)):
            self.assertTrue(hc.check_waiver_file_stat(bad))


class RuntimePathTest(unittest.TestCase):
    def test_checks_the_given_path(self):
        self.assertEqual(hc.check_runtime_path(hc.RUNTIME, realpath=lambda p: p), [])
        self.assertTrue(hc.check_runtime_path("/tmp/elsewhere", realpath=lambda p: p))
        self.assertTrue(hc.check_runtime_path(hc.RUNTIME, realpath=lambda p: "/tmp/elsewhere"))
        out = io.StringIO()
        self.assertEqual(hc.main(["runtime-dirs", "/tmp/elsewhere"], {}, out), 1)
        self.assertIn("runtime must be", out.getvalue())


class TrailingNewlineTest(unittest.TestCase):
    def test_dollar_anchor_cases(self):
        with self.assertRaises(OriginError):
            validate_origin(FAKE_ORIGIN + "\n")
        for v in ("62.0\n", "٦٢.٠", "62.0 "):
            with self.subTest(v=v), self.assertRaises(OriginError):
                validate_api_version(v)
        self.assertIsNone(NEXT_RECORDS_RE.fullmatch("/services/data/v62.0/query/01gS7-7\n"))
        self.assertIsNone(ISO_PARAM_RE.fullmatch("2026-11-10T09:00:00Z\n"))
        self.assertIsNone(parse_soql("SELECT COUNT() FROM Account\n"))
        self.assertIsNotNone(parse_soql("SELECT COUNT() FROM Account"))
        p = RequestPolicy(FAKE_ORIGIN, FAKE_API_VERSION, contract().fields_by_object())
        with self.assertRaises(RefusedRequest):
            p.check_next_records_url("/services/data/v62.0/query/01gS7-7\n")
        for rx in (ORIGIN_RE, API_VERSION_RE):
            self.assertTrue(rx.pattern.startswith("\\A") and rx.pattern.endswith("\\Z"))


class SoapWriteFreeTest(unittest.TestCase):
    def test_fake_counts_unknown_soap_as_write(self):
        from .fake_salesforce import FakeWriteAttempt, FakeSalesforceTransport
        fake = make_fake(contract())
        before = FakeSalesforceTransport.total_write_requests
        with self.assertRaises(FakeWriteAttempt):
            fake.send(Request("POST", FAKE_ORIGIN + "/services/Soap/u/62.0/" + FAKE_ORG_ID,
                              auth_soap.soap_headers("delete"), b"<x/>"))
        FakeSalesforceTransport.total_write_requests = before       # keep the suite-wide zero-write check honest
        self.assertEqual(fake.write_requests, 1)


if __name__ == "__main__":
    unittest.main()
