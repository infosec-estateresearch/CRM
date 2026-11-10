"""CRM-002-S round 2: SOAP DTD/encoding hardening, logout containment, request redaction,
anchors, fake write classification, legacy env metacharacters and the configured legacy path.
In-process, no sockets."""

import io
import json
import logging
import os
import re
import stat as S
import tempfile
import traceback
import unittest
import xml.etree.ElementTree as ET
from collections import namedtuple
from unittest import mock

from crm_migrate import auth_soap, cli, contract as contract_mod, errors as errors_mod, extract as extract_mod
from crm_migrate import hostcheck as hc, log as log_mod, manifest as manifest_mod
from crm_migrate.client import SalesforceClient
from crm_migrate.errors import MigrateError, OutputError, ProtocolError
from crm_migrate.log import LOGGER_NAME, CountsLog
from crm_migrate.messages import Request
from crm_migrate.synthetic import soap_body_operation

from .fake_salesforce import (FAKE_API_VERSION, FAKE_ORG_ID, FAKE_ORIGIN, FAKE_PASSWORD, FAKE_SESSION,
                              FAKE_USERNAME, SENTINEL, SOAP_SUCCESS_TEMPLATE, FakeSalesforceTransport,
                              FakeWriteAttempt, TempDirMixin, contract, make_fake)
from .test_soap_legacy import CREDS, ENV, TODAY, WAIVER_URL, Capture, write_capable_fake

St = namedtuple("St", "st_mode st_uid st_gid")
SERVER_URL = f"{FAKE_ORIGIN}/services/Soap/u/{FAKE_API_VERSION}/{FAKE_ORG_ID}"
ENTITY_SESSION = "00DS70000000001!entity.defined." + SENTINEL
_DECL = '<?xml version="1.0" encoding="UTF-8"?>'


def body_without_decl(session="&s;"):
    doc = SOAP_SUCCESS_TEMPLATE.format(server_url=SERVER_URL, session=session)
    assert doc.startswith(_DECL)
    return doc[len(_DECL):]


def evil(encoding_decl=None):
    """A loginResponse whose session id comes from an internal entity."""
    decl = f'<?xml version="1.0" encoding="{encoding_decl}"?>' if encoding_decl else ""
    return decl + f'<!DOCTYPE e [<!ENTITY s "{ENTITY_SESSION}">]>' + body_without_decl()


def encoded_attacks():
    """(name, bytes): every one must be refused by parse_xml."""
    out = []
    for codec, bom in (("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff"),
                       ("utf-32-le", b"\xff\xfe\x00\x00"), ("utf-32-be", b"\x00\x00\xfe\xff")):
        label = codec.rsplit("-", 1)[0].upper()                    # "UTF-16" / "UTF-32"
        for with_decl in (True, False):
            text = evil(label if with_decl else None)
            raw = text.encode(codec)
            out.append((f"{codec} no BOM decl={with_decl}", raw))
            out.append((f"{codec} BOM decl={with_decl}", bom + raw))
    out.append(("utf-16 codec (native BOM)", evil("UTF-16").encode("utf-16")))
    out.append(("utf-32 codec (native BOM)", evil("UTF-32").encode("utf-32")))
    return out


class PermissiveParser:
    """Stand-in for layer 3 in mutation tests: plain ElementTree, which expands entities."""

    def parse(self, data):
        return ET.fromstring(data)


def permissive_decode(body):
    """Stand-in for layer 1 in mutation tests: accept any BOM-detected encoding."""
    for bom, codec in ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe\x00\x00", "utf-32"),
                       (b"\x00\x00\xfe\xff", "utf-32"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
        if body.startswith(bom):
            return body.decode(codec)
    return body.decode("utf-8", "replace")


NEVER = re.compile(r"(?!)")


class SoapEncodingDtdTest(unittest.TestCase):
    def refused(self, raw, code=None):
        with self.assertRaises(ProtocolError) as cm:
            auth_soap.parse_login_response(200, raw, FAKE_ORIGIN, FAKE_API_VERSION)
        if code:
            self.assertEqual(cm.exception.code, code)
        self.assertNotIn(SENTINEL, str(cm.exception))
        return cm.exception

    def test_attack_is_real_without_the_hardening(self):
        # Non-vacuity of the inputs: plain ElementTree expands the entity into the session id.
        # Every UTF-16 variant (with or without BOM / declaration) is a working exploit; UTF-32 is
        # not parseable by expat at all, but is still refused explicitly by layer 1.
        exploits = [(n, r) for n, r in encoded_attacks() if "utf-16" in n] + [("utf-8", evil().encode())]
        self.assertEqual(len(exploits), 10)
        for name, raw in exploits:
            with self.subTest(name):
                root = ET.fromstring(raw)
                self.assertIn(ENTITY_SESSION, ET.tostring(root, encoding="unicode"))

    def test_utf16_utf32_refused_with_and_without_bom(self):
        for name, raw in encoded_attacks():
            with self.subTest(name):
                self.refused(raw, "soap_encoding_refused")

    def test_declared_non_utf8_encoding_refused(self):
        for enc in ("utf-16", "UTF-16", "iso-8859-1", "us-ascii", "utf-8 "):
            with self.subTest(enc=enc):
                raw = (f'<?xml version="1.0" encoding="{enc}"?>' + body_without_decl(FAKE_SESSION)).encode()
                self.refused(raw, "soap_encoding_refused")
        raw = ("<?xml version='1.0' encoding='utf-16'?>" + body_without_decl(FAKE_SESSION)).encode()
        self.refused(raw, "soap_encoding_refused")

    def test_invalid_utf8_and_stray_bom_refused(self):
        good = SOAP_SUCCESS_TEMPLATE.format(server_url=SERVER_URL, session=FAKE_SESSION).encode()
        for name, raw in (("invalid byte", good.replace(b"false", b"f\xffalse")),
                          ("overlong", good.replace(b"false", b"\xc0\xafalse")),
                          ("double BOM", b"\xef\xbb\xbf" + "﻿".encode() + good),
                          ("NUL", good.replace(b"false", b"fa\x00lse"))):
            with self.subTest(name):
                self.refused(raw, "soap_encoding_refused")

    def test_dtd_in_utf8_any_case_refused(self):
        for raw in (evil().encode(), evil("UTF-8").encode(), b"\xef\xbb\xbf" + evil("utf-8").encode(),
                    evil().replace("<!DOCTYPE", "<!doctype").encode(),
                    evil().replace("<!DOCTYPE", "<!DocType").replace("<!ENTITY", "<!eNtItY").encode(),
                    ('<!DOCTYPE e SYSTEM "file:///etc/passwd">' + body_without_decl(FAKE_SESSION)).encode()):
            with self.subTest(raw=raw[:30]):
                self.refused(raw, "soap_dtd_refused")

    def test_valid_utf8_still_parses(self):
        body = body_without_decl(FAKE_SESSION)
        for raw in (_DECL.encode() + body.encode(), b"\xef\xbb\xbf" + _DECL.encode() + body.encode(),
                    ("<?xml version='1.0' encoding='utf-8'?>" + body).encode(), body.encode(),
                    ('<?xml version="1.0"?>' + body).encode()):
            with self.subTest(raw=raw[:20]):
                session = auth_soap.parse_login_response(200, raw, FAKE_ORIGIN, FAKE_API_VERSION)
                self.assertEqual(session.session_id, FAKE_SESSION)

    def test_refused_before_any_value_is_used_end_to_end(self):
        attacks = encoded_attacks() + [("utf-8 dtd", evil().encode()), ("doctype lower", evil().replace(
            "<!DOCTYPE", "<!doctype").encode())]
        for name, raw in attacks:
            with self.subTest(name):
                fake = make_fake(contract(), soap_response=raw)
                client = SalesforceClient(FAKE_ORIGIN, FAKE_API_VERSION, fake, contract(),
                                          soap_login_host=auth_soap.LOGIN_HOST)
                with self.assertRaises(ProtocolError):
                    client.authenticate_soap(FAKE_USERNAME, FAKE_PASSWORD)
                self.assertIsNone(client._soap_session)
                self.assertIsNone(client._token)
                self.assertEqual([p for _, p in fake.requests if "/services/data/" in p], [])


class SoapLayerMutationTest(unittest.TestCase):
    """Each layer refuses on its own when the other two are disabled; with all three disabled
    the entity-defined session id is accepted (so the layers are what refuse)."""

    def login(self, raw):
        return auth_soap.parse_login_response(200, raw, FAKE_ORIGIN, FAKE_API_VERSION)

    def test_all_layers_disabled_accepts_entity_session(self):
        with mock.patch.object(auth_soap, "_decode_strict_utf8", permissive_decode), \
                mock.patch.object(auth_soap, "_DTD_TEXT_RE", NEVER), \
                mock.patch.object(auth_soap, "_hardened_parser", PermissiveParser):
            for raw in (evil().encode(), b"\xff\xfe" + evil().encode("utf-16-le")):
                self.assertEqual(self.login(raw).session_id, ENTITY_SESSION)

    def test_layer1_alone_refuses_wide_encodings(self):
        with mock.patch.object(auth_soap, "_DTD_TEXT_RE", NEVER), \
                mock.patch.object(auth_soap, "_hardened_parser", PermissiveParser):
            for name, raw in encoded_attacks():
                with self.subTest(name), self.assertRaises(ProtocolError) as cm:
                    self.login(raw)
                self.assertEqual(cm.exception.code, "soap_encoding_refused")

    def test_layer2_alone_refuses_dtd_text(self):
        with mock.patch.object(auth_soap, "_decode_strict_utf8", permissive_decode), \
                mock.patch.object(auth_soap, "_hardened_parser", PermissiveParser):
            for raw in (evil().encode(), evil().replace("<!DOCTYPE", "<!doctype").encode(),
                        b"\xff\xfe" + evil().encode("utf-16-le")):
                with self.subTest(raw=raw[:12]), self.assertRaises(ProtocolError) as cm:
                    self.login(raw)
                self.assertEqual(cm.exception.code, "soap_dtd_refused")

    def test_layer3_alone_refuses_dtd_and_external_entities(self):
        with mock.patch.object(auth_soap, "_decode_strict_utf8", permissive_decode), \
                mock.patch.object(auth_soap, "_DTD_TEXT_RE", NEVER):
            for raw in (evil().encode(), b"\xff\xfe" + evil().encode("utf-16-le"),
                        ('<!DOCTYPE e SYSTEM "x.dtd">' + body_without_decl(FAKE_SESSION)).encode(),
                        ('<!DOCTYPE e [<!ENTITY s SYSTEM "x.txt">]>' + body_without_decl()).encode(),
                        ('<!DOCTYPE e [<!ENTITY u SYSTEM "x" NDATA n>]>' + body_without_decl(FAKE_SESSION)).encode()):
                with self.subTest(raw=raw[:30]), self.assertRaises(ProtocolError) as cm:
                    self.login(raw)
                self.assertEqual(cm.exception.code, "soap_dtd_refused")
            # an undeclared entity reference is not resolvable either
            with self.assertRaises(ProtocolError):
                self.login(body_without_decl().encode())

    def test_layer3_parser_handlers_raise(self):
        p = auth_soap._hardened_parser().parser
        for handler in ("StartDoctypeDeclHandler", "EntityDeclHandler", "ExternalEntityRefHandler"):
            with self.subTest(handler), self.assertRaises(ProtocolError):
                getattr(p, handler)("x", None, None, None)


class LogoutContainmentTest(TempDirMixin, unittest.TestCase):
    def run_cli(self, argv, fake):
        out, err, cap = io.StringIO(), io.StringIO(), Capture()
        logger = logging.getLogger(LOGGER_NAME)
        logger.addHandler(cap)
        try:
            rc = cli.main(argv, environ=dict(ENV), transport=fake, stdout=out, stderr=err,
                          stdin=io.BytesIO(CREDS), today=TODAY)
        finally:
            logger.removeHandler(cap)
        return rc, err.getvalue(), cap.lines

    def argv(self, mode, *extra):
        return [mode, "--out", os.path.join(self.tmp(), "out"), "--auth", "soap-legacy",
                "--credentials-stdin", *extra]

    def waiver(self):
        path = os.path.join(self.tmp(), "waiver.json")
        with open(path, "w") as fh:
            json.dump({"authorisation": WAIVER_URL, "identity": "legacy-eric", "expires": "2026-11-30"}, fh)
        return path

    def test_any_logout_exception_is_contained(self):
        for exc in (ValueError("value " + SENTINEL), RuntimeError(FAKE_SESSION), KeyError(FAKE_PASSWORD),
                    ProtocolError("soap_response")):
            for argv, expected in ((self.argv("contract-check", "--waiver", self.waiver()), 0),
                                   (self.argv("contract-check"), 3)):
                with self.subTest(exc=type(exc).__name__, expected=expected):
                    with mock.patch.object(SalesforceClient, "logout_soap", side_effect=exc):
                        rc, err, lines = self.run_cli(argv, write_capable_fake())
                    self.assertEqual(rc, expected)
                    text = err + "\n".join(lines)
                    for secret in (SENTINEL, FAKE_SESSION, FAKE_PASSWORD):
                        self.assertNotIn(secret, text)
                    logout = [line for line in lines if "event=soap_logout" in line]
                    self.assertEqual(logout, [f"crm-migrate event=soap_logout code={type(exc).__name__} ok=false"])
                    self.assertNotIn("internal error", err)

    def test_successful_logout_logged(self):
        rc, _, lines = self.run_cli(self.argv("contract-check", "--waiver", self.waiver()), write_capable_fake())
        self.assertEqual(rc, 0)
        self.assertIn("crm-migrate event=soap_logout ok=true", lines)

    def test_logout_helper_never_raises(self):
        class Broken:
            @property
            def auth_mode(self):
                raise RuntimeError(SENTINEL)

        class BadLog:
            def allow(self, *a):
                raise RuntimeError(SENTINEL)

            def event(self, *a, **k):
                raise RuntimeError(SENTINEL)

        cli._logout(Broken(), CountsLog())
        client = mock.Mock(auth_mode="soap-legacy")
        client.logout_soap.side_effect = OSError(SENTINEL)
        cli._logout(client, BadLog())
        client.logout_soap.side_effect = None
        cli._logout(client, BadLog())
        cli._logout(None, BadLog())


class RequestRedactionTest(unittest.TestCase):
    def request(self):
        return Request("POST", FAKE_ORIGIN + "/services/Soap/u/59.0/" + FAKE_ORG_ID + "?sid=" + FAKE_SESSION,
                       (("Authorization", "Bearer " + FAKE_SESSION), ("SOAPAction", "logout")),
                       auth_soap.render_login_body(FAKE_USERNAME, FAKE_PASSWORD))

    def test_repr_and_str_show_method_and_path_only(self):
        req = self.request()
        for text in (repr(req), str(req), f"{req}", repr([req]), repr({"r": req})):
            with self.subTest(text=text[:20]):
                for secret in (FAKE_SESSION, FAKE_PASSWORD, FAKE_USERNAME, "sid=", "Bearer"):
                    self.assertNotIn(secret, text)
                self.assertIn("POST", text)
                self.assertIn("/services/Soap/u/59.0/" + FAKE_ORG_ID, text)

    def test_traceback_never_shows_a_value(self):
        req = self.request()
        try:
            raise ValueError(req)
        except ValueError as exc:
            text = "".join(traceback.format_exception(exc))
        for secret in (FAKE_SESSION, FAKE_PASSWORD):
            self.assertNotIn(secret, text)

    def test_odd_urls_do_not_break_repr(self):
        for url in ("https://[bad", None, 42):
            self.assertIn("redacted", repr(Request("GET", url)))

    def test_fields_and_equality_unchanged(self):
        a, b = self.request(), self.request()
        self.assertEqual(a, b)
        self.assertEqual(a.body, auth_soap.render_login_body(FAKE_USERNAME, FAKE_PASSWORD))


class AnchorTrailingNewlineTest(unittest.TestCase):
    def test_compiled_patterns_are_absolute(self):
        for rx in (errors_mod._DETAIL_RE, errors_mod._SF_ERROR_RE, log_mod._KEY_RE, log_mod._EVENT_RE,
                   log_mod._SF_ERROR_RE, log_mod._CODE_RE, extract_mod._ID_RE, extract_mod._SF_DT_RE,
                   manifest_mod._REL_RE, hc.RUN_ID_RE, hc._NAME_RE, contract_mod.NAME_RE):
            with self.subTest(rx=rx.pattern[:30]):
                self.assertTrue(rx.pattern.startswith("\\A") and rx.pattern.endswith("\\Z"))
                self.assertNotIn("$", rx.pattern.replace("\\$", ""))

    def test_errors(self):
        self.assertEqual(errors_mod.safe_sf_error_code("INVALID_SESSION_ID\n"), "UNKNOWN")
        self.assertEqual(errors_mod.safe_sf_error_code("INVALID_SESSION_ID"), "INVALID_SESSION_ID")
        self.assertEqual(MigrateError(detail="ok\n").detail, "<redacted>")
        self.assertEqual(MigrateError(detail="ok").detail, "ok")

    def test_log(self):
        lines = []
        logger = logging.getLogger("crm_migrate.test_anchor")
        logger.propagate = False
        handler = Capture()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            log = CountsLog(logger)
            log.allow("Word\n")
            log.event("evt\n", code="bad\n", sf_error="BAD\n", **{"key\n": 1}, error="good_code")
            log.event("evt", code="fine", sf_error="FINE", text="Word\n")
            lines = handler.lines
        finally:
            logger.removeHandler(handler)
        self.assertEqual(lines[0], "crm-migrate event=invalid_event code=<redacted> error=good_code sf_error=<redacted>")
        self.assertEqual(lines[1], "crm-migrate event=evt code=fine sf_error=FINE text=<redacted>")

    def test_extract(self):
        self.assertIsNone(extract_mod.parse_sf_datetime("2026-11-10T09:00:00.000Z\n"))
        self.assertIsNotNone(extract_mod.parse_sf_datetime("2026-11-10T09:00:00.000Z"))
        with self.assertRaises(ProtocolError):
            extract_mod._row_key({"Id": "001S7000000000001\n", "SystemModstamp": "2026-11-10T09:00:00.000Z"},
                                 "SystemModstamp")

    def test_manifest_file_names(self):
        self.assertEqual(manifest_mod._check_rel("a/b.json"), "a/b.json")
        for rel in ("a/b.json\n", "a\n/b.json"):
            with self.assertRaises(OutputError):
                manifest_mod._check_rel(rel)

    def test_hostcheck(self):
        self.assertEqual(hc.check_run_id("20261110T090000Z-extract"), [])
        self.assertTrue(hc.check_run_id("20261110T090000Z-extract\n"))
        names, errors = hc.parse_env_names("CRM_SF_ORIGIN=\n")
        self.assertEqual((names, errors), (["CRM_SF_ORIGIN"], []))
        self.assertIsNone(hc._NAME_RE.fullmatch("CRM_SF_ORIGIN\n"))
        self.assertEqual(hc.check_env_keys(["CRM_SF_ORIGIN\n"], ["CRM_SF_ORIGIN"])[-1],
                         "env file has unexpected names: <invalid>")

    def test_contract(self):
        self.assertEqual(contract_mod.check_name("Account"), "Account")
        with self.assertRaises(MigrateError):
            contract_mod.check_name("Account\n")


class FakeWriteClassificationTest(unittest.TestCase):
    def send(self, action, body, path=None):
        fake = make_fake(contract())
        before = FakeSalesforceTransport.total_write_requests
        try:
            fake.send(Request("POST", "https://" + auth_soap.LOGIN_HOST + (path or "/services/Soap/u/59.0/"),
                              auth_soap.soap_headers(action), body))
        except FakeWriteAttempt:
            return True
        finally:
            FakeSalesforceTransport.total_write_requests = before   # keep the suite-wide check honest
        return False

    def envelope(self, op):
        return (_DECL + '<soapenv:Envelope xmlns:soapenv="' + auth_soap.NS_ENV + '" xmlns:urn="' +
                auth_soap.NS_PARTNER + '"><soapenv:Body>' + op + "</soapenv:Body></soapenv:Envelope>").encode()

    def test_login_and_logout_bodies_are_not_writes(self):
        self.assertFalse(self.send("login", auth_soap.render_login_body(FAKE_USERNAME, FAKE_PASSWORD)))
        self.assertFalse(self.send("logout", auth_soap.render_logout_body(FAKE_SESSION),
                                   "/services/Soap/u/59.0/" + FAKE_ORG_ID))

    def test_other_body_operations_count_as_writes(self):
        for action, body in (("login", self.envelope("<urn:create><urn:sObjects/></urn:create>")),
                             ("logout", self.envelope("<urn:delete><urn:ids>x</urn:ids></urn:delete>")),
                             ("login", self.envelope("<urn:logout/>")),       # body/action mismatch
                             ("login", self.envelope("<other:login xmlns:other='urn:x'/>")),
                             ("login", self.envelope("<urn:login/><urn:create/>")),
                             ("login", b"<login/>"), ("login", b"not xml"), ("login", None),
                             ("login", evil().encode())):
            with self.subTest(body=(body or b"")[-40:]):
                self.assertTrue(self.send(action, body))

    def test_classifier(self):
        self.assertEqual(soap_body_operation(auth_soap.render_login_body(FAKE_USERNAME, FAKE_PASSWORD)), "login")
        self.assertIsNone(soap_body_operation(self.envelope("<urn:update/>")))


class LegacyEnvMetacharTest(unittest.TestCase):
    def parse(self, raw):
        return hc.parse_legacy_env(f"NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS={raw}\n")

    def test_unquoted_metacharacters_refused(self):
        for ch in list(";&|<>()$`") + [" ", "\t", " ", "\\", "'", '"']:
            with self.subTest(ch=ch):
                creds, errors = self.parse(f"p{ch}w")
                self.assertIsNone(creds)
                self.assertTrue(errors)

    def test_quoted_values_must_close_cleanly(self):
        for raw in ('"pw"x', "'pw'x", '"pw" ', "'pw' #c", '"p"w"', "'p'w'", '"pw', "'pw", '"', "''", '""'):
            with self.subTest(raw=raw):
                self.assertIsNone(self.parse(raw)[0])

    def test_quoted_metacharacters_allowed(self):
        self.assertEqual(self.parse("'a;b&c|d<e>f(g)h$i`j k'")[0]["password"], "a;b&c|d<e>f(g)h$i`j k")
        self.assertEqual(self.parse('"a;b&c|d<e>f(g)h k"')[0]["password"], "a;b&c|d<e>f(g)h k")
        self.assertEqual(self.parse("plain-pw_1.!@#%^*+=")[0]["password"], "plain-pw_1.!@#%^*+=")


class LegacyPathConfigTest(unittest.TestCase):
    def test_example_lists_the_name_without_a_value(self):
        from . import REPO
        with open(os.path.join(REPO, "deploy", "migrate", "env.legacy.example"), encoding="utf-8") as fh:
            names, errors = hc.parse_env_names(fh.read())
        self.assertEqual(errors, [])
        self.assertEqual(names, ["CRM_SF_ORIGIN", "CRM_SF_API_VERSION", "CRM_LEGACY_ENV_FILE"])
        self.assertFalse(hasattr(hc, "LEGACY_ENV_FILE"))          # no committed path

    def test_parse_legacy_path(self):
        self.assertEqual(hc.parse_legacy_path("CRM_SF_ORIGIN=x\nCRM_LEGACY_ENV_FILE=/a/b.env\n"), ("/a/b.env", []))
        self.assertEqual(hc.parse_legacy_path("CRM_SF_ORIGIN=x\nCRM_LEGACY_ENV_FILE=\n"), ("", []))
        self.assertEqual(hc.parse_legacy_path("CRM_SF_ORIGIN=x\n"), ("", []))
        path, errors = hc.parse_legacy_path("CRM_LEGACY_ENV_FILE=/a\nCRM_LEGACY_ENV_FILE=/b\n")
        self.assertEqual(path, "")
        self.assertTrue(errors)

    def test_check_legacy_env_path(self):
        ident = lambda p: p  # noqa: E731
        self.assertEqual(hc.check_legacy_env_path("/srv/elt/.env", ident), [])
        self.assertIn("not configured", hc.check_legacy_env_path("", ident)[0])
        self.assertIn("not configured", hc.check_legacy_env_path(None, ident)[0])
        for bad in ("relative/.env", "./x", "/srv/elt/.env\n", "/srv/elt/\x00x"):
            with self.subTest(bad=bad):
                self.assertIn("absolute", hc.check_legacy_env_path(bad, ident)[0])
        self.assertTrue(hc.check_legacy_env_path("/srv/link/.env", lambda p: "/srv/real/.env"))
        self.assertTrue(hc.check_legacy_env_path("/srv/elt/../elt/.env"))

    def test_check_legacy_env_stat(self):
        self.assertEqual(hc.check_legacy_env_stat(St(S.S_IFREG | 0o600, 0, 0)), [])
        self.assertEqual(hc.check_legacy_env_stat(St(S.S_IFREG | 0o644, 0, 1000)), [])
        self.assertEqual(hc.check_legacy_env_stat(St(S.S_IFREG | 0o640, 0, 1000)), [])
        for bad in (St(S.S_IFREG | 0o620, 0, 0), St(S.S_IFREG | 0o602, 0, 0), St(S.S_IFREG | 0o600, 1000, 0),
                    St(S.S_IFLNK | 0o600, 0, 0), St(S.S_IFDIR | 0o700, 0, 0), None):
            with self.subTest(bad=bad):
                self.assertTrue(hc.check_legacy_env_stat(bad))

    def test_symlinked_component_refused_on_disk(self):
        me = os.getuid()
        with tempfile.TemporaryDirectory() as d:
            d = os.path.realpath(d)
            real = os.path.join(d, "real")
            os.mkdir(real)
            path = os.path.join(real, "elt.env")
            with open(path, "w") as fh:
                fh.write("NIF_SRC_SALESFORCE_USER=u\nNIF_SRC_SALESFORCE_PASS=p\n")
            os.chmod(path, 0o600)
            os.symlink(real, os.path.join(d, "linkdir"))
            self.assertEqual(hc.legacy_main("legacy-fingerprint", path, io.StringIO(), io.StringIO(), owner_uid=me), 0)
            err = io.StringIO()
            via = os.path.join(d, "linkdir", "elt.env")
            self.assertEqual(hc.legacy_main("legacy-credentials", via, io.StringIO(), err, owner_uid=me), 1)
            self.assertIn("symlink", err.getvalue())
            os.chmod(path, 0o620)
            err = io.StringIO()
            self.assertEqual(hc.legacy_main("legacy-credentials", path, io.StringIO(), err, owner_uid=me), 1)
            self.assertIn("group- or world-writable", err.getvalue())

    def test_configured_path_from_runtime_env(self):
        with tempfile.TemporaryDirectory() as d:
            env = os.path.join(d, "env")
            with open(env, "w") as fh:
                fh.write("CRM_SF_ORIGIN=x\nCRM_SF_API_VERSION=59.0\nCRM_LEGACY_ENV_FILE=/srv/elt/.env\n")
            os.chmod(env, 0o600)
            root_st = mock.Mock(st_mode=S.S_IFREG | 0o600, st_uid=0, st_gid=0)
            with mock.patch.object(hc, "_lstat", return_value=root_st):
                self.assertEqual(hc.configured_legacy_path(env), ("/srv/elt/.env", []))
            # the unprivileged test user's file is not root-owned: refused before reading
            if os.getuid() != 0:
                path, errors = hc.configured_legacy_path(env)
                self.assertEqual(path, "")
                self.assertIn("env file must be owned root:root", errors)

    def test_main_refuses_when_not_configured(self):
        err = io.StringIO()
        with mock.patch.object(hc, "configured_legacy_path", return_value=("", [])), \
                mock.patch("sys.stderr", err):
            out = io.StringIO()
            self.assertEqual(hc.main(["legacy-credentials"], {}, out), 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("CRM_LEGACY_ENV_FILE is not configured", err.getvalue())
        err = io.StringIO()
        with mock.patch.object(hc, "configured_legacy_path", return_value=("", ["runtime env repeats x"])), \
                mock.patch("sys.stderr", err):
            self.assertEqual(hc.main(["legacy-fingerprint"], {}, io.StringIO()), 1)
        self.assertIn("repeats", err.getvalue())

    def test_script_refuses_exported_legacy_path(self):
        from . import SCRIPT_PATH
        with open(SCRIPT_PATH, encoding="utf-8") as fh:
            script = fh.read()
        self.assertIn("NIF_SRC_SALESFORCE_USER NIF_SRC_SALESFORCE_PASS CRM_LEGACY_ENV_FILE", script)
        self.assertNotRegex(script, r"CRM_LEGACY_ENV_FILE=\S")


if __name__ == "__main__":
    unittest.main()
