"""CRM-002-S round 3: logout template byte-identity, fixed faultcode / errorCode vocabularies,
stdin size and UTF-8 checks, no environment credential fallback, legacy env unclosed quotes.
In-process, no sockets."""

import io
import json
import logging
import os
import unittest
from unittest import mock

from crm_migrate import auth_soap, cli, client as client_mod, errors as errors_mod, hostcheck as hc
from crm_migrate.errors import ConfigError, RefusedRequest
from crm_migrate.log import LOGGER_NAME
from crm_migrate.messages import Request
from crm_migrate.transport import HttpsTransport

from .fake_salesforce import (FAKE_API_VERSION, FAKE_ORG_ID, FAKE_ORIGIN, FAKE_PASSWORD, FAKE_SESSION,
                              FAKE_USERNAME, SENTINEL, TempDirMixin, contract, make_fake)
from .test_soap_legacy import ENV, TODAY, Capture, Spy, assert_no_secret, policy

LOGOUT_URL = f"{FAKE_ORIGIN}/services/Soap/u/{FAKE_API_VERSION}/{FAKE_ORG_ID}"
NOT_TEMPLATE = "SOAP logout body is not the fixed template"
SESSION_XML = f"<urn:sessionId>{FAKE_SESSION}</urn:sessionId>"
SESSION_HEADER = f"<urn:SessionHeader>{SESSION_XML}</urn:SessionHeader>"


def logout_variants():
    """(name, body): each keeps a parseable Envelope, exactly one ``urn:logout`` in the Body and a
    valid session id at Header/SessionHeader/sessionId, so only the byte-identity rule refuses it."""
    t = auth_soap.render_logout_body(FAKE_SESSION).decode("utf-8")
    pairs = (
        # extra elements
        ("extra header element", SESSION_HEADER, SESSION_HEADER + "<urn:CallOptions><urn:client>x</urn:client></urn:CallOptions>"),
        ("extra element in SessionHeader", SESSION_XML, SESSION_XML + "<urn:extra>x</urn:extra>"),
        ("child inside logout", "<urn:logout/>", "<urn:logout><urn:sessionId>x</urn:sessionId></urn:logout>"),
        ("text inside logout", "<urn:logout/>", "<urn:logout>x</urn:logout>"),
        ("comment in body", "<urn:logout/>", "<urn:logout/><!-- c -->"),
        # a different operation inside a logout envelope
        ("delete in header", SESSION_HEADER, SESSION_HEADER + "<urn:delete><urn:ids>001000000000001</urn:ids></urn:delete>"),
        ("create in SessionHeader", SESSION_XML, SESSION_XML + "<urn:create><urn:sObjects/></urn:create>"),
        ("query in logout", "<urn:logout/>", "<urn:logout><urn:query><urn:queryString>SELECT Id FROM User</urn:queryString></urn:query></urn:logout>"),
        # a different session-header shape
        ("mustUnderstand attribute", "<urn:SessionHeader>", '<urn:SessionHeader soapenv:mustUnderstand="1">'),
        ("other prefix", "<urn:SessionHeader>" + SESSION_XML + "</urn:SessionHeader>",
         '<p:SessionHeader xmlns:p="urn:partner.soap.sforce.com"><p:sessionId>' + FAKE_SESSION +
         "</p:sessionId></p:SessionHeader>"),
        ("default namespace", "<urn:SessionHeader>" + SESSION_XML + "</urn:SessionHeader>",
         '<SessionHeader xmlns="urn:partner.soap.sforce.com"><sessionId>' + FAKE_SESSION +
         "</sessionId></SessionHeader>"),
        ("whitespace after sessionId", SESSION_XML, SESSION_XML + " "),
        ("second header", "</soapenv:Header>", "</soapenv:Header><soapenv:Header><urn:x/></soapenv:Header>"),
        # envelope-level serialisation differences
        ("extra namespace", 'xmlns:urn="', 'xmlns:x="urn:x" xmlns:urn="'),
        ("envelope attribute", "<soapenv:Envelope ", '<soapenv:Envelope id="a" '),
        ("lower-case encoding", 'encoding="UTF-8"', 'encoding="utf-8"'),
        ("single-quoted declaration", '<?xml version="1.0" encoding="UTF-8"?>', "<?xml version='1.0' encoding='UTF-8'?>"),
        ("no declaration", '<?xml version="1.0" encoding="UTF-8"?>', ""),
        ("whitespace between elements", "<soapenv:Body>", "<soapenv:Body>\n"),
        ("expanded empty element", "<urn:logout/>", "<urn:logout></urn:logout>"),
    )
    out = []
    for name, old, new in pairs:
        assert old in t, name
        out.append((name, t.replace(old, new, 1).encode("utf-8")))
    out.append(("trailing newline", (t + "\n").encode("utf-8")))
    out.append(("leading BOM", b"\xef\xbb\xbf" + t.encode("utf-8")))
    return out


class LogoutTemplateTest(unittest.TestCase):
    def test_variants_reach_only_the_template_rule(self):
        template = auth_soap.render_logout_body(FAKE_SESSION)
        auth_soap.check_logout_body(template)                       # the template itself passes
        for name, body in logout_variants():
            with self.subTest(variant=name):
                self.assertNotEqual(body, template)
                root = auth_soap.parse_xml(body)
                self.assertEqual(auth_soap._body_child(root).tag, f"{{{auth_soap.NS_PARTNER}}}logout")
                with self.assertRaises(RefusedRequest) as cm:
                    auth_soap.check_logout_body(body)
                self.assertEqual(cm.exception.detail, NOT_TEMPLATE)

    def test_logout_action_with_non_template_body_never_sent(self):
        self.assertEqual(policy().check(Request("POST", LOGOUT_URL, auth_soap.soap_headers("logout"),
                                                auth_soap.render_logout_body(FAKE_SESSION))).kind, "soap_logout")
        for name, body in logout_variants():
            request = Request("POST", LOGOUT_URL, auth_soap.soap_headers("logout"), body)
            with self.subTest(variant=name):
                with self.assertRaises(RefusedRequest):
                    policy().check(request)
                spy = Spy()
                client = client_mod.SalesforceClient(FAKE_ORIGIN, FAKE_API_VERSION, spy, contract(),
                                                     soap_login_host=auth_soap.LOGIN_HOST)
                with self.assertRaises(RefusedRequest):
                    client._send_soap(request)
                with self.assertRaises(RefusedRequest):
                    HttpsTransport(policy(), connection_factory=lambda *a, **k: self.fail("connected")).send(request)
                self.assertEqual(spy.calls, 0)


def fault_xml(faultcode, exception_code="INVALID_LOGIN"):
    return ('<?xml version="1.0" encoding="UTF-8"?><soapenv:Envelope xmlns:soapenv="' + auth_soap.NS_ENV + '" '
            'xmlns:sf="urn:fault.partner.soap.sforce.com"><soapenv:Body><soapenv:Fault>'
            "<faultcode>" + faultcode + "</faultcode><faultstring>" + SENTINEL + "</faultstring>"
            "<detail><sf:LoginFault><sf:exceptionCode>" + exception_code + "</sf:exceptionCode></sf:LoginFault>"
            "</detail></soapenv:Fault></soapenv:Body></soapenv:Envelope>").encode("utf-8")


def raise_fault(body):
    try:
        auth_soap._raise_if_fault(auth_soap.parse_xml(body), 500)
    except auth_soap.SoapFault as exc:
        return exc
    raise AssertionError("no SoapFault raised")


PASSWORD_SHAPED = ("sf:Hunter2-Spring.2026", "Tr0ub4dor_and_3", "sf:INVALID_LOGIN_" + "Hunter2pw",
                   "soapenv:" + "S3cretPass", "sf:invalid_login", "sf:INVALID_LOGIN.x", "UNKNOWN")


class FaultcodeVocabularyTest(unittest.TestCase):
    def test_known_faultcodes_printed(self):
        self.assertEqual(len(auth_soap.FAULTCODES), 10)
        for code in sorted(auth_soap.FAULTCODES):
            with self.subTest(code=code):
                exc = raise_fault(fault_xml(code))
                self.assertEqual(exc.detail, f"faultcode={code}")
                self.assertIn(f"detail=faultcode={code}", str(exc))

    def test_other_faultcodes_unrecognised(self):
        for code in PASSWORD_SHAPED + ("", "sf:" + "A" * 70):
            with self.subTest(code=code):
                exc = raise_fault(fault_xml(code))
                self.assertEqual(exc.detail, "faultcode=unrecognised")
                text = str(exc) + repr(exc.args) + repr(vars(exc))
                if code and code != "UNKNOWN":
                    self.assertNotIn(code, text)
                assert_no_secret(self, text)

    def test_password_shaped_exception_code_not_echoed(self):
        for token in ("Hunter2pw", "HUNTER2_SPRING", "S3CRET"):
            with self.subTest(token=token):
                exc = raise_fault(fault_xml("sf:INVALID_LOGIN", token + " trailing"))
                self.assertEqual(exc.sf_error, "UNKNOWN")
                self.assertNotIn(token, str(exc) + repr(vars(exc)))
        self.assertEqual(raise_fault(fault_xml("sf:INVALID_LOGIN", "INVALID_LOGIN x")).sf_error, "INVALID_LOGIN")


class RestErrorCodeVocabularyTest(unittest.TestCase):
    def test_known_codes_kept(self):
        for code in ("INVALID_SESSION_ID", "MALFORMED_QUERY", "INVALID_FIELD", "REQUEST_LIMIT_EXCEEDED"):
            with self.subTest(code=code):
                self.assertEqual(client_mod._error_code(json.dumps([{"errorCode": code}]).encode()), code)
        self.assertEqual(client_mod._error_code(json.dumps({"error": "invalid_grant"}).encode()), "INVALID_GRANT")

    def test_unknown_codes_not_echoed(self):
        for code in ("HUNTER2_PASSWORD", "S3CRET", "PASSWORD", "INVALID_SESSION_IDX", "A" * 64):
            with self.subTest(code=code):
                self.assertEqual(client_mod._error_code(json.dumps([{"errorCode": code}]).encode()), "UNKNOWN")
                self.assertEqual(client_mod._error_code(json.dumps({"error": code.lower()}).encode()), "UNKNOWN")
                exc = client_mod.HttpError(status=400, sf_error=code)
                self.assertEqual(exc.sf_error, "UNKNOWN")
                self.assertNotIn(code, str(exc))
        self.assertTrue(all(errors_mod._SF_ERROR_RE.fullmatch(c) for c in errors_mod.SF_ERROR_CODES))


class StdinRound3Test(unittest.TestCase):
    def test_valid_json_past_size_limit_refused(self):
        doc = json.dumps({"username": FAKE_USERNAME, "password": FAKE_PASSWORD})
        raw = (doc + " " * (cli.MAX_STDIN_BYTES + 64 - len(doc))).encode("utf-8")
        self.assertGreater(len(raw), cli.MAX_STDIN_BYTES)
        self.assertEqual(json.loads(raw), {"username": FAKE_USERNAME, "password": FAKE_PASSWORD})
        self.assertEqual(json.loads(raw[:cli.MAX_STDIN_BYTES + 1])["password"], FAKE_PASSWORD)  # still valid if cut
        with self.assertRaises(ConfigError) as cm:
            cli.read_stdin_credentials(io.BytesIO(raw))
        self.assertEqual((cm.exception.code, cm.exception.detail),
                         ("credentials_stdin", "credentials on stdin exceed 4 KiB"))
        assert_no_secret(self, str(cm.exception))
        exact = (doc + " " * (cli.MAX_STDIN_BYTES - len(doc))).encode("utf-8")   # boundary: 4096 is accepted
        self.assertEqual(cli.read_stdin_credentials(io.BytesIO(exact)), (FAKE_USERNAME, FAKE_PASSWORD))

    def test_non_utf8_encodable_credentials_refused(self):
        lone = "\\ud800"                                              # JSON escape -> lone surrogate
        for user, pw in ((FAKE_USERNAME, FAKE_PASSWORD + lone), (FAKE_USERNAME + lone, FAKE_PASSWORD),
                         (FAKE_USERNAME, "\\udfff" + SENTINEL)):
            raw = ('{"username": "' + user + '", "password": "' + pw + '"}').encode("ascii")
            with self.subTest(raw=raw[-20:]), self.assertRaises(ConfigError) as cm:
                cli.read_stdin_credentials(io.BytesIO(raw))
            exc = cm.exception
            self.assertEqual(exc.code, "credentials_invalid")
            self.assertIsNone(exc.__context__)
            self.assertIsNone(exc.__cause__)
            assert_no_secret(self, str(exc) + repr(exc.args) + repr(vars(exc)))
        ok = json.dumps({"username": FAKE_USERNAME, "password": "pässwörd-€"}).encode()
        self.assertEqual(cli.read_stdin_credentials(io.BytesIO(ok))[1], "pässwörd-€")


ENV_CREDS = {"NIF_SRC_SALESFORCE_USER": FAKE_USERNAME, "NIF_SRC_SALESFORCE_PASS": FAKE_PASSWORD,
             "CRM_SF_USERNAME": FAKE_USERNAME, "CRM_SF_PASSWORD": FAKE_PASSWORD,
             "CRM_SF_ORIGIN": FAKE_ORIGIN, "CRM_SF_API_VERSION": FAKE_API_VERSION}


class EnvFallbackTest(TempDirMixin, unittest.TestCase):
    def test_legacy_client_reads_os_environ_but_never_credentials(self):
        fake = make_fake(contract())
        with mock.patch.dict(os.environ, ENV_CREDS):
            with self.assertRaises(ConfigError) as cm:
                cli.legacy_client(os.environ, contract(), io.BytesIO(b""), transport=fake)
        self.assertEqual(cm.exception.code, "credentials_stdin")
        self.assertEqual(fake.soap_requests, [])
        assert_no_secret(self, str(cm.exception))

    def test_cli_main_with_patched_environ_refuses(self):
        fake = make_fake(contract())
        out, err, cap = io.StringIO(), io.StringIO(), Capture()
        logger = logging.getLogger(LOGGER_NAME)
        logger.addHandler(cap)
        argv = ["contract-check", "--out", os.path.join(self.tmp(), "out"), "--auth", "soap-legacy",
                "--credentials-stdin"]
        try:
            with mock.patch.dict(os.environ, ENV_CREDS):
                rc = cli.main(argv, transport=fake, stdout=out, stderr=err, stdin=io.BytesIO(b""), today=TODAY)
        finally:
            logger.removeHandler(cap)
        text = out.getvalue() + err.getvalue() + "\n".join(cap.lines)
        self.assertNotEqual(rc, 0)
        self.assertIn("credentials_stdin", text)
        self.assertEqual(fake.soap_requests, [])
        assert_no_secret(self, text)
        self.assertEqual(ENV, {"CRM_SF_ORIGIN": FAKE_ORIGIN, "CRM_SF_API_VERSION": FAKE_API_VERSION})


class LegacyEnvUnclosedQuoteTest(unittest.TestCase):
    CREDS = "NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS=p\n"

    def test_quote_spanning_lines_refuses_whole_file(self):
        # CRM-002-T: the consumer reads line by line with no quote processing, and WO item 3
        # says other lines are not interpreted beyond the CR and continuation checks. A quote
        # left open on another line no longer refuses the file; the targets read literally.
        for text in ('OTHER="abc\n' + self.CREDS + 'X=y"\n',
                     "OTHER='abc\n" + self.CREDS + "X=y'\n",
                     "export OTHER=pre\"fix\n" + self.CREDS + "END=\"\n",
                     self.CREDS + "TAIL='" + SENTINEL + "\n"):
            with self.subTest(text=text[:16]):
                self.assertEqual(hc.parse_legacy_env(text), ({"username": "u", "password": "p"}, []))
        creds, errors = hc.parse_legacy_env("NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS='" + SENTINEL + "\n")
        self.assertIsNone(creds)                       # an open quote in a target value is refused
        self.assertEqual(errors, ["legacy env file line 2: refused-character"])

    def test_closed_quotes_comments_and_escapes_still_parse(self):
        for text in ('OTHER="a#b \'c"\n' + self.CREDS,
                     "OTHER='a\"b'\n" + self.CREDS,
                     "OTHER=x # it's a comment\n" + self.CREDS,
                     "# it's a comment line\n" + self.CREDS,
                     'OTHER=a\\"b\n' + self.CREDS,
                     'OTHER="a\\"b"\n' + self.CREDS):
            with self.subTest(text=text[:16]):
                self.assertEqual(hc.parse_legacy_env(text), ({"username": "u", "password": "p"}, []))


if __name__ == "__main__":
    unittest.main()
