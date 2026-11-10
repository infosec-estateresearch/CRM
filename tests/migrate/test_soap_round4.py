"""CRM-002-S round 4: no secret reachable through exception chaining (stdin credentials, waiver,
SOAP login response, legacy env), CountsLog ``sf_error`` re-check, legacy env continuation / CR
refusal, literal stdin boundary, User updateable finding under an identity waiver.
In-process, no sockets."""

import io
import json
import logging
import os
import tempfile
import traceback
import unittest

from crm_migrate import auth_soap, cli, hostcheck as hc, waiver as wv
from crm_migrate.errors import ConfigError, MigrateError
from crm_migrate.log import CountsLog
from crm_migrate.metadata import evaluate_gate
from crm_migrate.synthetic import SOAP_SUCCESS_TEMPLATE

from .fake_salesforce import (FAKE_API_VERSION, FAKE_ORG_ID, FAKE_ORIGIN, FAKE_PASSWORD, FAKE_SESSION,
                              FAKE_USERNAME, SENTINEL, contract)
from .test_soap_legacy import TODAY, WAIVER_URL, Capture, write_capable_fake

SERVER_URL = f"{FAKE_ORIGIN}/services/Soap/u/{FAKE_API_VERSION}/{FAKE_ORG_ID}"
USER_FINDING = "User updateable: L1 finding for Architect decision, not waived"


def login_body(session=FAKE_SESSION, server_url=SERVER_URL):
    return SOAP_SUCCESS_TEMPLATE.format(server_url=server_url, session=session).encode("utf-8")


class NoChainMixin:
    def assert_unchained(self, exc, *sentinels):
        self.assertIsInstance(exc, MigrateError)
        self.assertIsNone(exc.__cause__)
        self.assertIsNone(exc.__context__)
        rendered = repr(exc) + str(exc) + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        for s in sentinels + (SENTINEL,):
            self.assertNotIn(s, rendered)


class StdinExceptionContextTest(NoChainMixin, unittest.TestCase):
    def test_utf8_json_and_duplicate_failures_carry_no_context(self):
        pw = FAKE_PASSWORD
        cases = {
            "not utf-8": b'{"username": "u", "password": "' + pw.encode() + b'\xff"}',
            "truncated json": ('{"username": "u", "password": "' + pw + '"').encode(),
            "trailing data": ('{"username": "u", "password": "' + pw + '"} x').encode(),
            "duplicate key": ('{"username": "u", "password": "' + pw + '", "password": "x"}').encode(),
        }
        for name, raw in cases.items():
            with self.subTest(name), self.assertRaises(ConfigError) as cm:
                cli.read_stdin_credentials(io.BytesIO(raw))
            self.assertEqual(cm.exception.code, "credentials_stdin")
            self.assert_unchained(cm.exception, pw)
        with self.assertRaises(ConfigError) as cm:
            cli.read_stdin_credentials(io.BytesIO(cases["duplicate key"]))
        self.assertEqual(cm.exception.detail, "credentials JSON repeats a key")

    def test_every_refusal_is_unchained(self):
        for raw in (b"", b"[]", b'{"username": "u"}', b'{"username": "", "password": "p"}',
                    ('{"username": "u", "password": "' + FAKE_PASSWORD + '\\ud800"}').encode(),
                    b" " * (cli.MAX_STDIN_BYTES + 1)):
            with self.subTest(raw=raw[:20]), self.assertRaises(ConfigError) as cm:
                cli.read_stdin_credentials(io.BytesIO(raw))
            self.assert_unchained(cm.exception, FAKE_PASSWORD)

    def test_literal_boundary(self):
        self.assertEqual(cli.MAX_STDIN_BYTES, 4096)
        doc = json.dumps({"username": FAKE_USERNAME, "password": FAKE_PASSWORD})
        exact = (doc + " " * (4096 - len(doc))).encode("utf-8")
        over = (doc + " " * (4097 - len(doc))).encode("utf-8")
        self.assertEqual((len(exact), len(over)), (4096, 4097))
        for raw in (exact, over):
            self.assertEqual(json.loads(raw), {"username": FAKE_USERNAME, "password": FAKE_PASSWORD})
        self.assertEqual(cli.read_stdin_credentials(io.BytesIO(exact)), (FAKE_USERNAME, FAKE_PASSWORD))
        with self.assertRaises(ConfigError) as cm:
            cli.read_stdin_credentials(io.BytesIO(over))
        self.assertEqual(cm.exception.detail, "credentials on stdin exceed 4 KiB")
        self.assert_unchained(cm.exception, FAKE_PASSWORD)


class WaiverExceptionContextTest(NoChainMixin, unittest.TestCase):
    def test_parse_failures_carry_no_context(self):
        good = {"authorisation": WAIVER_URL, "identity": "legacy-eric", "expires": "2026-11-30"}
        cases = [
            b'{"authorisation": "' + SENTINEL.encode() + b'\xff"}',
            ('{"authorisation": "' + SENTINEL + '"').encode(),
            ('{"authorisation": "' + SENTINEL + '", "authorisation": "y"}').encode(),
            json.dumps(dict(good, expires="2026-02-30")).encode(),
            json.dumps(dict(good, identity=SENTINEL)).encode(),
        ]
        for raw in cases:
            with self.subTest(raw=raw[:30]), self.assertRaises(ConfigError) as cm:
                wv.parse_waiver(raw, TODAY)
            self.assertEqual(cm.exception.code, "waiver_invalid")
            self.assert_unchained(cm.exception)

    def test_unreadable_file_carries_no_context(self):
        with self.assertRaises(ConfigError) as cm:
            wv.load_waiver("/nonexistent/" + SENTINEL + "/waiver.json", TODAY)
        self.assertEqual(cm.exception.detail, "waiver file cannot be read")
        self.assert_unchained(cm.exception)


class SoapLoginResponseContextTest(NoChainMixin, unittest.TestCase):
    def parse(self, body):
        return auth_soap.parse_login_response(200, body, FAKE_ORIGIN, FAKE_API_VERSION)

    def test_valid_response_still_parses(self):
        self.assertEqual(self.parse(login_body()).session_id, FAKE_SESSION)

    def test_failures_carry_no_context(self):
        cases = {
            "not utf-8": login_body().replace(b"<userName>", b"<userName>\xff"),
            "not well-formed": login_body().replace(b"</sessionId>", b"</sessionIdX>"),
            "bad port": login_body(server_url=f"{FAKE_ORIGIN}:99999/services/Soap/u/{FAKE_API_VERSION}/{FAKE_ORG_ID}"),
        }
        for name, body in cases.items():
            self.assertIn(FAKE_SESSION.encode(), body)
            with self.subTest(name), self.assertRaises(MigrateError) as cm:
                self.parse(body)
            self.assert_unchained(cm.exception, FAKE_SESSION)

    def test_expat_wrapper_error_carries_no_context(self):
        import xml.etree.ElementTree as ET
        with self.assertRaises(ET.ParseError) as cm:
            auth_soap._hardened_parser().parse(login_body().replace(b"</sessionId>", b"</sessionIdX>"))
        self.assertIsNone(cm.exception.__context__)
        self.assertIsNone(cm.exception.__cause__)

    def test_login_body_check_carries_no_context(self):
        body = auth_soap.render_login_body(FAKE_USERNAME, FAKE_PASSWORD)
        for bad in (body + b"\xff", body.replace(b"</soapenv:Envelope>", b"")):
            with self.subTest(bad=bad[-12:]), self.assertRaises(MigrateError) as cm:
                auth_soap.check_login_body(bad)
            self.assert_unchained(cm.exception, FAKE_PASSWORD)


class TokenResponseContextTest(NoChainMixin, unittest.TestCase):
    def test_non_json_token_response_carries_no_context(self):
        from crm_migrate.client import SalesforceClient
        from crm_migrate.messages import Response
        from crm_migrate.synthetic import FAKE_TOKEN
        for body in (b'{"access_token": "' + FAKE_TOKEN.encode() + b'\xff"}',
                     b'{"access_token": "' + FAKE_TOKEN.encode() + b'"'):
            with self.subTest(body=body[-8:]), self.assertRaises(MigrateError) as cm:
                SalesforceClient._json(Response(status=200, headers={}, body=body))
            self.assertEqual(cm.exception.code, "response_not_json")
            self.assert_unchained(cm.exception, FAKE_TOKEN)


class LegacyEnvNoRaiseTest(unittest.TestCase):
    """The legacy env readers return errors and never raise, so nothing can chain a value."""

    def test_non_utf8_file_refused_without_value(self):
        me = os.getuid()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(os.path.realpath(d), "elt.env")
            with open(path, "wb") as fh:
                fh.write(b"NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS=" + SENTINEL.encode() + b"\xff\n")
            os.chmod(path, 0o600)
            out, err = io.StringIO(), io.StringIO()
            self.assertEqual(hc.legacy_main("legacy-credentials", path, out, err, owner_uid=me), 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("not UTF-8", err.getvalue())
        self.assertNotIn(SENTINEL, err.getvalue())


class LegacyEnvContinuationAndCrTest(unittest.TestCase):
    CREDS = "NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS=" + SENTINEL + "\n"
    CONT = r"\Alegacy env file line ([0-9]+) ends with a line continuation; file refused\Z"
    CR = r"\Alegacy env file line ([0-9]+) holds a carriage return; file refused\Z"

    def refused(self, text, pattern, line):
        creds, errors = hc.parse_legacy_env(text)
        self.assertIsNone(creds)
        self.assertEqual(len(errors), 1)
        self.assertRegex(errors[0], pattern)
        self.assertEqual(int(errors[0].split()[4]), line)
        self.assertNotIn(SENTINEL, errors[0])

    def test_continuation_refuses_whole_file(self):
        cases = (
            ("OTHER=abc\\\n" + self.CREDS, 1),                         # unrelated line before PASS
            ("export OTHER=abc\\\n" + self.CREDS, 1),
            ("A=1\nOTHER=\"abc\\\n" + self.CREDS, 2),                  # inside double quotes
            ("NIF_SRC_SALESFORCE_USER=u\\\nNIF_SRC_SALESFORCE_PASS=" + SENTINEL + "\n", 1),
            (self.CREDS + "TAIL=x\\", 3),                              # last line, no newline
            ("OTHER='a'b\\\n" + self.CREDS, 1),                        # after a closed single quote
            ("OTHER=a\\\\\\\n" + self.CREDS, 1),                       # \\ then \ at end
        )
        for text, line in cases:
            with self.subTest(text=text[:20]):
                self.refused(text, self.CONT, line)

    def test_cr_refuses_whole_file(self):
        cases = (
            (self.CREDS.replace("\n", "\r\n"), 1),
            ("OTHER=x\r\n" + self.CREDS, 1),
            ("A=1\nB=2\nOTHER=a\rb\n" + self.CREDS, 3),
            (self.CREDS + "# comment\r\n", 3),
            ("# comment\r\n" + self.CREDS, 1),
        )
        for text, line in cases:
            with self.subTest(text=text[:20]):
                self.refused(text, self.CR, line)

    def test_not_a_continuation(self):
        ok = {"username": "u", "password": SENTINEL}
        for text in ("# comment ends with \\\n" + self.CREDS,
                     "  # indented comment \\\n" + self.CREDS,
                     "OTHER='abc\\'\n" + self.CREDS,                 # backslash inside single quotes
                     "OTHER=a\\\\\n" + self.CREDS,                   # escaped backslash
                     "OTHER=x # trailing comment \\\n" + self.CREDS,
                     "OTHER=a\\b\n" + self.CREDS):
            with self.subTest(text=text[:20]):
                self.assertEqual(hc.parse_legacy_env(text), (ok, []))


class CountsLogSfErrorTest(unittest.TestCase):
    def lines(self, **fields):
        logger = logging.getLogger("crm_migrate.test_round4")
        logger.propagate = False
        handler = Capture()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            log = CountsLog(logger)
            log.allow("SENTINEL_7F3A")                    # even an allowed word is not a valid sf_error
            log.event("evt", **fields)
            return handler.lines
        finally:
            logger.removeHandler(handler)

    def test_unknown_sf_error_rendered_unknown(self):
        self.assertEqual(self.lines(sf_error="SENTINEL_7F3A"), ["crm-migrate event=evt sf_error=UNKNOWN"])
        self.assertEqual(self.lines(sf_error=7), ["crm-migrate event=evt sf_error=UNKNOWN"])

    def test_known_sf_error_and_none(self):
        self.assertEqual(self.lines(sf_error="INVALID_LOGIN"), ["crm-migrate event=evt sf_error=INVALID_LOGIN"])
        self.assertEqual(self.lines(sf_error=None), ["crm-migrate event=evt sf_error=none"])


class IdentityWaiverUserFindingTest(unittest.TestCase):
    def test_finding_reported_under_identity_waiver(self):
        fake = write_capable_fake()
        describes = {o.name: fake.org.describe(o.name) for o in contract().objects}
        self.assertIs(describes["User"]["updateable"], True)
        waiver = wv.parse_waiver(json.dumps({"authorisation": WAIVER_URL, "identity": "legacy-eric",
                                             "expires": "2026-11-30"}).encode(), TODAY)
        waived = evaluate_gate(contract(), describes, waiver)
        self.assertTrue(waived.ok)                                     # the gate decision is waived
        user = waived.report["objects"]["User"]
        self.assertIn("updateable:identity", user["waived"])
        self.assertEqual(waived.report["findings"].count(USER_FINDING), 1)  # but the finding is reported
        failed = evaluate_gate(contract(), describes)
        self.assertFalse(failed.ok)
        self.assertEqual(failed.report["findings"].count(USER_FINDING), 1)

    def test_no_finding_when_user_not_updateable(self):
        fake = write_capable_fake()
        describes = {o.name: fake.org.describe(o.name) for o in contract().objects}
        describes["User"] = dict(describes["User"], updateable=False)
        waiver = wv.parse_waiver(json.dumps({"authorisation": WAIVER_URL, "identity": "legacy-eric",
                                             "expires": "2026-11-30"}).encode(), TODAY)
        self.assertNotIn(USER_FINDING, evaluate_gate(contract(), describes, waiver).report["findings"])


if __name__ == "__main__":
    unittest.main()
