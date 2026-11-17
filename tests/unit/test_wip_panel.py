"""WIP panel tests (WO CRM-WIP-INT-001R2, Part B).

TestMetadata checks the files in the repository. TestLoader runs the real
WipLoader.php under php, against a stub WIP API on loopback and stubs of the few
EspoCRM classes the loader touches. The PHP tests are NOT skipped when php is
present; when php is missing they fail loudly (a skip would prove nothing).
"""

import json
import os
import re
import shutil
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import access_policy as policy

REPO = policy.REPO
RES = policy.RES
LOADER = os.path.join(REPO, "custom", "Espo", "Custom", "Classes", "FieldProcessing", "Account",
                      "WipLoader.php")
SFID = "001AAAAAAAAAAAAAAA"          # synthetic, 18 characters
TOKEN = "synthetic-test-token-0123"  # synthetic
CONTRACT_CASE = {"reference": "SYN-001", "name": "Matter A", "type": "Advisory", "status": "Open",
                 "openedAt": "2026-01-12", "wip": "10250.00", "feesInvoiced": "2500.00",
                 "estimatedYield": "12000.00", "actualYield": None, "asOf": "2026-05-31"}


def contract(cases=None, **over):
    doc = {"salesforceAccountId": SFID, "companyName": "Synthetic Firm LLP", "truncated": False,
           "cases": [dict(CONTRACT_CASE)] if cases is None else cases}
    doc.update(over)
    return doc


def load(*parts):
    with open(os.path.join(RES, *parts), encoding="utf-8") as fh:
        return json.load(fh)


class TestMetadata(unittest.TestCase):
    def test_json_files_are_valid(self):
        for parts in [("metadata", "recordDefs", "Account.json"),
                      ("metadata", "entityDefs", "Account.json"),
                      ("metadata", "scopes", "WipSummary.json"),
                      ("layouts", "Account", "detail.json"),
                      ("i18n", "en_US", "Account.json"), ("i18n", "en_US", "Global.json")]:
            load(*parts)

    def test_loader_is_registered_and_exists(self):
        defs = load("metadata", "recordDefs", "Account.json")
        self.assertEqual(defs["readLoaderClassNameList"],
                         ["Espo\\Custom\\Classes\\FieldProcessing\\Account\\WipLoader"])
        self.assertTrue(os.path.isfile(LOADER))
        # no list loader, no save hook: nothing runs outside a single read
        self.assertEqual({k for k in defs if "oader" in k}, {"readLoaderClassNameList"})

    def test_fields_are_read_only_not_stored_and_off_every_surface(self):
        fields = load("metadata", "entityDefs", "Account.json")["fields"]
        self.assertEqual({"wipStatus": "varchar", "wipCases": "text"},
                         {n: fields[n]["type"] for n in ("wipStatus", "wipCases")})
        for name in ("wipStatus", "wipCases"):
            for flag in ("readOnly", "notStorable", "directUpdateDisabled", "layoutListDisabled",
                         "layoutFiltersDisabled", "layoutMassUpdateDisabled", "massUpdateDisabled",
                         "exportDisabled", "importDisabled", "textFilterDisabled"):
                self.assertIs(fields[name].get(flag), True, f"{name}.{flag}")
            self.assertIs(fields[name].get("audited"), False)

    def test_panel_names_only_existing_fields_and_hides_when_empty(self):
        layout = load("layouts", "Account", "detail.json")
        fields = set(load("metadata", "entityDefs", "Account.json")["fields"])
        panel = layout[-1]
        self.assertEqual(panel["name"], "wip")
        names = {c["name"] for row in panel["rows"] for c in row if c}
        self.assertEqual(names, {"wipStatus", "wipCases"})
        self.assertLessEqual(names, fields)
        self.assertEqual(panel["dynamicLogicVisible"],
                         {"conditionGroup": [{"type": "isNotEmpty", "attribute": "wipStatus"}]})
        # the earlier panels are not touched
        self.assertEqual([p["label"] for p in layout[:-1]], ["Overview", "Salesforce"])
        # the WIP fields appear in no other layout
        for kind in ("detail", "list"):
            path = os.path.join(RES, "layouts", "Account", kind + ".json")
            if os.path.exists(path) and kind != "detail":
                with open(path, encoding="utf-8") as fh:
                    self.assertNotIn("wip", fh.read())

    def test_scope_has_the_core_boolean_shape(self):
        self.assertEqual(load("metadata", "scopes", "WipSummary.json"),
                         {"entity": False, "layouts": False, "tab": False, "acl": "boolean"})

    def test_every_role_lists_the_scope_as_false(self):
        roles = policy.load_access()["roles"]
        self.assertTrue(roles)
        for role in roles:
            self.assertIs(role["data"].get("WipSummary"), False, role["name"])
        self.assertIn("WipSummary", policy.ACL_BOOLEAN_SCOPES)
        self.assertIs(policy.HUMAN_BOOLEAN["WipSummary"], False)
        self.assertIs(policy.IMPORT_BOOLEAN["WipSummary"], False)

    def test_labels_exist(self):
        acct = load("i18n", "en_US", "Account.json")
        self.assertIn("wipStatus", acct["fields"])
        self.assertIn("wipCases", acct["fields"])
        self.assertIn("WipSummary", load("i18n", "en_US", "Global.json")["scopeNames"])

    def test_compose_and_env_example_carry_the_optional_names(self):
        with open(os.path.join(REPO, "deploy", "compose.json"), encoding="utf-8") as fh:
            env = json.load(fh)["services"]["crm-app"]["environment"]
        self.assertEqual(env["CRM_WIP_API_URL"], "${CRM_WIP_API_URL:-}")
        self.assertEqual(env["CRM_WIP_API_TOKEN"], "${CRM_WIP_API_TOKEN:-}")
        with open(os.path.join(REPO, "deploy", "env.example"), encoding="utf-8") as fh:
            lines = [l.rstrip("\n") for l in fh]
        self.assertIn("CRM_WIP_API_URL=", lines)
        self.assertIn("CRM_WIP_API_TOKEN=", lines)

    def test_loader_source_holds_no_url_token_or_redirect_following(self):
        with open(LOADER, encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotRegex(src, r"https?://")
        self.assertIn("CURLOPT_FOLLOWLOCATION => false", src)
        self.assertEqual(len(re.findall(r"getenv\(", src)), 2)

    def test_seed_is_public_safe(self):
        with open(os.path.join(REPO, "tests", "fixtures", "wip_proof_seed.sql"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("SYN", text)
        self.assertNotRegex(text, r"(?i)password|secret|token|@[a-z0-9-]+\.[a-z]")


# ---------------------------------------------------------------------------
# PHP loader
# ---------------------------------------------------------------------------

STUBS = r"""<?php
namespace Espo\Core { class Acl { public function __construct(public bool $grant, public ?string $boom = null) {}
    public function checkScope(string $s): bool {
        if ($this->boom !== null) { throw new \RuntimeException($this->boom); }
        return $s === 'WipSummary' && $this->grant; } } }
namespace Espo\Core\FieldProcessing { interface Loader {} }
namespace Espo\Core\FieldProcessing\Loader { class Params {} }
namespace Espo\Core\Utils { class Log { public array $lines = [];
    public function warning(string $m): void { $this->lines[] = $m; } } }
namespace Espo\ORM { class Entity { public array $set = []; public function __construct(public $sfId) {}
    public function get(string $n) { return $n === 'sfId' ? $this->sfId : null; }
    public function set(string $n, $v): void { $this->set[$n] = $v; } } }
"""

HARNESS = STUBS + r"""namespace {
    $cfg = json_decode($argv[2], true);
    foreach (['CRM_WIP_API_URL', 'CRM_WIP_API_TOKEN'] as $k) {
        if (array_key_exists($k, $cfg['env'])) { putenv($k . '=' . $cfg['env'][$k]); } else { putenv($k); }
    }
    require $argv[1];
    $log = new \Espo\Core\Utils\Log();
    $loader = new \Espo\Custom\Classes\FieldProcessing\Account\WipLoader(
        new \Espo\Core\Acl($cfg['grant'], $cfg['boom'] ?? null), $log);
    $entity = new \Espo\ORM\Entity($cfg['sfId']);
    $t = microtime(true);
    $loader->process($entity, new \Espo\Core\FieldProcessing\Loader\Params());
    echo json_encode(['set' => (object) $entity->set, 'logs' => $log->lines,
                      'secs' => microtime(true) - $t]);
}
"""

# Calls the private buildUrl() by reflection (PHP 8.4: no setAccessible needed).
BUILD_HARNESS = STUBS + r"""namespace {
    require $argv[1];
    $loader = new \Espo\Custom\Classes\FieldProcessing\Account\WipLoader(
        new \Espo\Core\Acl(true), new \Espo\Core\Utils\Log());
    $method = new \ReflectionMethod($loader, 'buildUrl');
    $out = [];
    foreach (json_decode($argv[2], true) as $u) { $out[] = $method->invoke($loader, $u, $argv[3]); }
    echo json_encode($out);
}
"""


class StubWip:
    """A WIP API stand-in on loopback that records every request it receives."""

    def __init__(self, tls=None):
        self.requests = []
        self.reply = (200, b"{}", {}, 0)
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                stub.requests.append((self.path, self.headers.get("Authorization")))
                status, body, headers, delay = stub.reply
                if self.path.startswith("/other"):
                    status, body, headers, delay = 200, b"{}", {}, 0
                time.sleep(delay)
                try:
                    self.send_response(status)
                    for k, v in headers.items():
                        self.send_header(k, v)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        scheme = "http"
        if tls:  # (certificate file, key file): an HTTPS stub for the TLS checks
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(*tls)
            self.server.socket = ctx.wrap_socket(self.server.socket, server_side=True)
            scheme = "https"
        self.port = self.server.server_address[1]
        self.url = "%s://127.0.0.1:%d" % (scheme, self.port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class TestLoader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stub = StubWip()
        cls.tmp = tempfile.mkdtemp()
        cls.harness = os.path.join(cls.tmp, "harness.php")
        with open(cls.harness, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        cls.build_harness = os.path.join(cls.tmp, "build.php")
        with open(cls.build_harness, "w", encoding="utf-8") as fh:
            fh.write(BUILD_HARNESS)

    @classmethod
    def tearDownClass(cls):
        cls.stub.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        # Not a skip: without php the loader tests prove nothing, so they must fail.
        self.assertIsNotNone(shutil.which("php"), "php is required to run the WIP loader tests")
        self.stub.requests.clear()

    def run_loader(self, reply=None, grant=True, sfid=SFID, env=True, loader=LOADER, url=None,
                   boom=None, extra_env=None):
        if reply is not None:
            body = reply[1] if isinstance(reply[1], bytes) else json.dumps(reply[1]).encode()
            self.stub.reply = (reply[0], body, reply[2] if len(reply) > 2 else {},
                               reply[3] if len(reply) > 3 else 0)
        cfg = {"grant": grant, "sfId": sfid, "boom": boom,
               "env": {"CRM_WIP_API_URL": url or self.stub.url, "CRM_WIP_API_TOKEN": TOKEN}
               if env else {}}
        res = subprocess.run(["php", "-d", "display_errors=stderr", self.harness, loader,
                              json.dumps(cfg)], capture_output=True, text=True, timeout=30,
                             env=dict(os.environ, **(extra_env or {})))
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        out = json.loads(res.stdout)
        blob = res.stdout + res.stderr
        self.assertNotIn(TOKEN, blob)
        if boom:
            self.assertNotIn(boom, blob)
        self.assertNotIn(sfid or "-", "".join(out["logs"]) if sfid else "")
        self.assertNotIn(self.stub.url, "".join(out["logs"]))
        return out

    def status(self, out):
        return out["set"].get("wipStatus")

    # --- the amendment §5 statuses ------------------------------------------------
    def test_available_with_cases_and_a_request_shape(self):
        out = self.run_loader((200, contract()))
        self.assertEqual(self.status(out), "WIP data available")
        self.assertEqual(self.stub.requests, [(f"/api/v1/accounts/{SFID}/wip", f"Bearer {TOKEN}")])
        line = out["set"]["wipCases"]
        for want in ("SYN-001", "Matter A", "WIP value 10250.00", "Fees invoiced 2500.00",
                     "Estimated yield 12000.00", "as of 2026-05-31",
                     "Revised or actual yield (source value) —"):
            self.assertIn(want, line)
        self.assertNotIn("source value) 0", line)  # the blank is a dash, not zero

    def test_no_cases(self):
        out = self.run_loader((200, contract(cases=[])))
        self.assertEqual(out["set"], {"wipStatus": "No current WIP cases", "wipCases": ""})

    def test_truncated_adds_a_note(self):
        out = self.run_loader((200, contract(truncated=True)))
        self.assertIn("More current cases exist", out["set"]["wipCases"])

    def test_404_is_firm_not_found(self):
        out = self.run_loader((404, {"error": "not found"}))
        self.assertEqual(out["set"], {"wipStatus": "Firm not found in WIP", "wipCases": ""})

    def test_other_statuses_are_unavailable(self):
        for code in (401, 409, 422, 500, 503, 204, 201):
            with self.subTest(code=code):
                out = self.run_loader((code, {"error": "x"}))
                self.assertEqual(out["set"], {"wipStatus": "WIP unavailable", "wipCases": ""})
                self.assertTrue(out["logs"])
                self.assertIn(str(code), out["logs"][0])
                self.assertNotIn("x", out["logs"][0].replace("HttpStatus", "").replace("WIP loader", ""))

    # --- C1: authorisation first -----------------------------------------------------
    def test_c1_without_the_scope_nothing_is_set_and_nothing_is_sent(self):
        for sfid in (SFID, "", None, "A" * 15, "A" * 19, "001AAAAAAAAAAAAAA-"):
            with self.subTest(sfid=sfid):
                self.stub.requests.clear()
                out = self.run_loader((200, contract()), grant=False, sfid=sfid)
                self.assertEqual(out["set"], {})
                self.assertEqual(out["logs"], [])
                self.assertEqual(self.stub.requests, [])

    def test_c1_authorised_without_a_valid_sfid_gets_the_fixed_status_and_no_request(self):
        for sfid in ("", None, "A" * 15, "A" * 19, "001AAAAAAAAAAAAAA-", "../../etc/passwd",
                     SFID + "\n"):
            with self.subTest(sfid=sfid):
                out = self.run_loader((200, contract()), sfid=sfid)
                self.assertEqual(out["set"], {"wipStatus": "No Salesforce ID on this Account",
                                              "wipCases": ""})
                self.assertEqual(self.stub.requests, [])

    # --- configuration, redirects, hostile replies -------------------------------------
    def test_not_configured_is_unavailable_without_a_request(self):
        out = self.run_loader((200, contract()), env=False)
        self.assertEqual(self.status(out), "WIP unavailable")
        self.assertEqual(self.stub.requests, [])

    def test_bad_urls_are_refused(self):
        for url in ("ftp://127.0.0.1/x", "file:///etc/passwd", "http://user:pw@127.0.0.1:1",
                    self.stub.url + "?a=b", "not a url", "gopher://127.0.0.1"):
            with self.subTest(url=url):
                out = self.run_loader((200, contract()), url=url)
                self.assertEqual(self.status(out), "WIP unavailable")
                self.assertEqual(self.stub.requests, [])

    def test_f2_credentials_in_the_url_are_refused_before_any_request(self):
        # Pointed at the live stub: a dead port would fail whatever the guard does.
        control = self.run_loader((200, contract()))
        self.assertEqual(self.status(control), "WIP data available")
        self.assertEqual(len(self.stub.requests), 1)
        host = "127.0.0.1:%d" % self.stub.port
        for url in (f"http://user:pw@{host}", f"http://user@{host}", f"http://:pw@{host}"):
            with self.subTest(url=url):
                self.stub.requests.clear()
                out = self.run_loader((200, contract()), url=url)
                self.assertEqual(out["set"], {"wipStatus": "WIP unavailable", "wipCases": ""})
                self.assertIn("BadConfiguredUrl", out["logs"][0])
                self.assertEqual(self.stub.requests, [])

    def build_urls(self, urls):
        res = subprocess.run(["php", "-d", "display_errors=stderr", self.build_harness, LOADER,
                              json.dumps(urls), SFID], capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        return json.loads(res.stdout)

    def test_f3_scheme_check_in_build_url_stands_on_its_own(self):
        # buildUrl() is called directly, so CURLOPT_PROTOCOLS (a second, redundant layer) cannot
        # mask the scheme check. Removing only CURLOPT_PROTOCOLS is an equivalent mutant.
        bad = ["ftp://127.0.0.1/x", "file:///etc/passwd", "gopher://127.0.0.1", "javascript:alert(1)",
               "127.0.0.1:8080/x", "not a url", "FTP://127.0.0.1"]
        self.assertEqual(self.build_urls(bad), [None] * len(bad))
        good = self.build_urls(["http://127.0.0.1:8080", "https://wip.example.invalid/base/"])
        for url in good:
            self.assertIsNotNone(url)
            self.assertIn(SFID, url)
        self.assertEqual(good[0], f"http://127.0.0.1:8080/api/v1/accounts/{SFID}/wip")
        self.assertEqual(good[1], f"https://wip.example.invalid/base/api/v1/accounts/{SFID}/wip")

    def test_f4_tls_verification_refuses_an_untrusted_certificate(self):
        # A self-signed certificate generated now; nothing is committed. If openssl is missing
        # this fails loudly (no skip).
        self.assertIsNotNone(shutil.which("openssl"), "openssl is required to run the TLS test")
        cert, key = os.path.join(self.tmp, "stub.crt"), os.path.join(self.tmp, "stub.key")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-keyout", key, "-out", cert, "-subj", "/CN=wip-stub",
                        "-addext", "subjectAltName=IP:127.0.0.1"],
                       check=True, capture_output=True, timeout=60)
        tls = StubWip(tls=(cert, key))
        self.addCleanup(tls.close)
        # Control: the HTTPS stub really answers a client that trusts its certificate.
        with urllib.request.urlopen(tls.url + "/probe", timeout=10,
                                    context=ssl.create_default_context(cafile=cert)) as reply:
            self.assertEqual(reply.status, 200)
        tls.requests.clear()
        out = self.run_loader((200, contract()), url=tls.url)
        self.assertEqual(out["set"], {"wipStatus": "WIP unavailable", "wipCases": ""})
        self.assertEqual(tls.requests, [])
        self.assertIn("Transport", out["logs"][0])

    # --- A1: an ACL check that throws fails closed ------------------------------------------
    def test_a1_acl_exception_sets_no_field_sends_no_request_and_logs_only_the_class(self):
        marker = "ACL-BOOM-MARKER-7c1e"
        out = self.run_loader((200, contract()), boom=marker)  # also checks stdout and stderr
        self.assertEqual(out["set"], {})
        self.assertEqual(self.stub.requests, [])
        self.assertEqual(out["logs"], ["WIP loader: RuntimeException"])
        self.assertNotIn(marker, json.dumps(out))

    def test_redirects_are_not_followed(self):
        out = self.run_loader((302, b"", {"Location": self.stub.url + "/other"}))
        self.assertEqual(self.status(out), "WIP unavailable")
        self.assertEqual(len(self.stub.requests), 1)
        self.assertFalse(any(p.startswith("/other") for p, _ in self.stub.requests))

    def test_oversize_reply_is_unavailable(self):
        big = json.dumps(contract(companyName="x" * 300000)).encode()
        out = self.run_loader((200, big))
        self.assertEqual(self.status(out), "WIP unavailable")
        self.assertEqual(out["set"]["wipCases"], "")

    def test_f1_body_cap_is_the_only_reason_a_valid_reply_is_refused(self):
        # The reply is otherwise valid (right contract, echoes the Account's id) and is padded
        # with trailing whitespace, so it stays valid JSON. Only the size cap can refuse it.
        with open(LOADER, encoding="utf-8") as fh:
            self.assertIn("MAX_BODY = 262144;", fh.read())
        limit = 262144
        base = json.dumps(contract()).encode()
        control = self.run_loader((200, base))
        self.assertEqual(self.status(control), "WIP data available")  # unpadded: accepted
        at_limit = self.run_loader((200, base + b" " * (limit - len(base))))
        self.assertEqual(self.status(at_limit), "WIP data available")  # exactly MAX_BODY bytes
        for size in (limit + 1, limit * 2):
            with self.subTest(size=size):
                self.assertEqual(json.loads(base + b" " * (size - len(base)))["companyName"],
                                 "Synthetic Firm LLP")  # the padded body is itself valid
                out = self.run_loader((200, base + b" " * (size - len(base))))
                self.assertEqual(out["set"], {"wipStatus": "WIP unavailable", "wipCases": ""})
                self.assertIn("BodyTooLarge", out["logs"][0])

    def test_malformed_and_wrong_shape_replies_are_unavailable(self):
        bad_case = dict(CONTRACT_CASE)
        replies = {
            "not json": b"<html>nope</html>",
            "empty": b"",
            "list": b"[]",
            "scalar": b"7",
            "missing key": json.dumps({k: v for k, v in contract().items() if k != "truncated"}).encode(),
            "extra top key": json.dumps(contract(extra=1)).encode(),
            "wrong sfid": json.dumps(contract(salesforceAccountId="001BBBBBBBBBBBBBBB")).encode(),
            "truncated not bool": json.dumps(contract(truncated="no")).encode(),
            "cases not list": json.dumps(contract(cases={"a": 1})).encode(),
            "51 cases": json.dumps(contract(cases=[bad_case] * 51)).encode(),
            "extra case key": json.dumps(contract(cases=[dict(bad_case, id=5)])).encode(),
            "missing case key": json.dumps(contract(
                cases=[{k: v for k, v in bad_case.items() if k != "asOf"}])).encode(),
            "float amount": json.dumps(contract(cases=[dict(bad_case, wip=10250.0)])).encode(),
            "bad amount text": json.dumps(contract(cases=[dict(bad_case, wip="1e5")])).encode(),
            "bad date": json.dumps(contract(cases=[dict(bad_case, asOf="31/05/2026")])).encode(),
            "long string": json.dumps(contract(cases=[dict(bad_case, name="n" * 256)])).encode(),
            "null reference": json.dumps(contract(cases=[dict(bad_case, reference=None)])).encode(),
            "truncated with no cases": json.dumps(contract(cases=[], truncated=True)).encode(),
        }
        for label, body in replies.items():
            with self.subTest(reply=label):
                out = self.run_loader((200, body))
                self.assertEqual(out["set"], {"wipStatus": "WIP unavailable", "wipCases": ""})

    def test_exactly_fifty_cases_are_accepted_and_nulls_show_as_dashes(self):
        case = dict(CONTRACT_CASE, wip=None, feesInvoiced=None, estimatedYield=None, name=None,
                    openedAt=None)
        out = self.run_loader((200, contract(cases=[case] * 50)))
        self.assertEqual(self.status(out), "WIP data available")
        self.assertEqual(len(out["set"]["wipCases"].split("\n")), 50)
        self.assertIn("WIP value —", out["set"]["wipCases"])

    def test_output_is_plain_text(self):
        case = dict(CONTRACT_CASE, name="<b>x</b>\r\nINJECT\x00")
        out = self.run_loader((200, contract(cases=[case])))
        cases = out["set"]["wipCases"]
        self.assertEqual(len(cases.split("\n")), 1)
        self.assertNotRegex(cases, r"[\x00-\x09\x0b-\x1f]")

    def test_timeout_is_unavailable_within_the_bound(self):
        out = self.run_loader((200, contract(), {}, 5))
        self.assertEqual(self.status(out), "WIP unavailable")
        self.assertLess(out["secs"], 4.5)
        self.assertIn("Timeout", out["logs"][0])

    def test_refused_connection_is_unavailable(self):
        out = self.run_loader((200, contract()), url="http://127.0.0.1:1")
        self.assertEqual(out["set"], {"wipStatus": "WIP unavailable", "wipCases": ""})

    def test_no_token_in_logs_or_output_on_any_failure(self):
        for code in (401, 500):
            out = self.run_loader((code, TOKEN.encode()))  # a hostile body echoing the token
            self.assertNotIn(TOKEN, json.dumps(out))

    # --- the harness can fail --------------------------------------------------------------
    def mutated(self, *pairs):
        with open(LOADER, encoding="utf-8") as fh:
            src = fh.read()
        for old, new in pairs:
            self.assertIn(old, src)
            src = src.replace(old, new, 1)
        path = os.path.join(self.tmp, "Mutant.php")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(src)
        return path

    def test_harness_detects_a_loader_that_skips_the_acl_check(self):
        path = self.mutated(("if (!$granted) {", "if (false && !$granted) {"))
        out = self.run_loader((200, contract()), grant=False, loader=path)
        self.assertNotEqual(out["set"], {})

    def test_harness_detects_a_loader_that_follows_redirects(self):
        path = self.mutated(("CURLOPT_FOLLOWLOCATION => false,\n            CURLOPT_MAXREDIRS => 0,",
                             "CURLOPT_FOLLOWLOCATION => true,\n            CURLOPT_MAXREDIRS => 5,"),
                            ("CURLOPT_REDIR_PROTOCOLS => 0", "CURLOPT_REDIR_PROTOCOLS => CURLPROTO_HTTP"))
        self.run_loader((302, b"", {"Location": self.stub.url + "/other"}), loader=path)
        self.assertTrue(any(p.startswith("/other") for p, _ in self.stub.requests))

    def test_harness_detects_a_loader_that_calls_without_a_valid_sfid(self):
        path = self.mutated(("preg_match('/^[A-Za-z0-9]{18}$/D', $sfId) !== 1", "false"))
        self.run_loader((200, contract()), sfid="A" * 15, loader=path)
        self.assertTrue(self.stub.requests)


if __name__ == "__main__":
    unittest.main()
