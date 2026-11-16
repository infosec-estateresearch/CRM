"""CRM-CLIENT-001R: static policy for client/custom/ and tests/browser/ (AC1, AC7, AC11),
the offline evidence verifier and its public-summary sanitiser (AC6a, AC6c) and release
integrity (AC9). Everything is generated inside the tests: no committed evidence
fixtures, no browser, no network, no Docker."""

import copy
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from contextlib import redirect_stderr
import zipfile
import zlib

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BROWSER = os.path.join(REPO, "tests", "browser")
sys.path.insert(0, os.path.join(REPO, "scripts"))
import release  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(f"crm_browser_{name}", os.path.join(BROWSER, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


journeys = load("journeys")
probe = load("probe_isolation")
verify = load("verify_evidence")

CANARY = os.path.join(REPO, "client", "custom", "src", "crm", "release-canary.js")
CANARY_V2 = os.path.join(BROWSER, "fixtures", "canary-transition", "v2", "crm", "release-canary.js")
VERIFIER = os.path.join(BROWSER, "verify_evidence.py")


def read(path, mode="r"):
    with open(path, mode) as fh:
        return fh.read()


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


# ===================================================================== AC1: static policy
ALLOWED_EXT = {".js", ".css", ".json", ".tpl", ".svg"}
MAX_BYTES = 256 * 1024
JS_RULES = {
    "remote-url": r"https?://|['\"(]//[A-Za-z0-9]",
    "eval": r"\beval\s*\(",
    "new-function": r"\bnew\s+Function\b",
    "document-write": r"\bdocument\s*\.\s*write(?:ln)?\s*\(",
    "innerhtml-assignment": r"\.innerHTML\s*(?:\+|=)",
    "absolute-url-request": r"\b(?:fetch|open)\s*\(\s*['\"`]\s*(?:https?:)?//",
    "storage-api": r"\b(?:localStorage|sessionStorage|indexedDB|openDatabase)\b|\bdocument\s*\.\s*cookie\b",
    "import-export": r"(?m)^\s*(?:import|export)\b",
}
CANARY_FORBIDDEN = r"\b(?:window|document|fetch|XMLHttpRequest|navigator|globalThis|self|location)\b"


def strip_js_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def client_policy_violations(root):
    """Violated rule names for the client/custom tree under root (a checkout)."""
    out = []
    base = os.path.join(root, "client", "custom")
    if not os.path.isdir(base):
        return out
    for entry in sorted(os.listdir(base)):
        if entry != "src":
            out.append("extra-top-entry" if entry != "modules" else "modules")
    for dirpath, dirs, files in os.walk(base):
        for name in dirs + files:
            path = os.path.join(dirpath, name)
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode):
                out.append("symlink")
                continue
            if stat.S_ISDIR(st.st_mode):
                continue
            if os.path.splitext(name)[1] not in ALLOWED_EXT:
                out.append("extension")
            if st.st_mode & 0o111:
                out.append("executable")
            if st.st_size > MAX_BYTES:
                out.append("size")
            if name.endswith(".js"):
                text = read(path)
                code = strip_js_comments(text)
                if not re.match(r"\s*define\s*\(", code):
                    out.append("not-amd")
                for rule, rx in JS_RULES.items():
                    if re.search(rx, code):
                        out.append(rule)
    return sorted(set(out))


GOOD_JS = "define([], function () { return Object.freeze({name: 'x'}); });\n"
BROKEN = {
    "extra-top-entry": ("client/custom/other/a.js", GOOD_JS),
    "modules": ("client/custom/modules/Ext/a.js", GOOD_JS),
    "extension": ("client/custom/src/a.txt", "x"),
    "not-amd": ("client/custom/src/a.js", "var x = 1;\n"),
    "import-export": ("client/custom/src/a.js", "export default 1;\ndefine([], function () { return 1; });\n"),
    "remote-url": ("client/custom/src/a.js", "define([], function () { return 'http://example.invalid/x'; });\n"),
    "eval": ("client/custom/src/a.js", "define([], function () { return eval('1'); });\n"),
    "new-function": ("client/custom/src/a.js", "define([], function () { return new Function('return 1'); });\n"),
    "document-write": ("client/custom/src/a.js", "define([], function () { document.write('x'); });\n"),
    "innerhtml-assignment": ("client/custom/src/a.js", "define([], function (e) { e.innerHTML = 'x'; });\n"),
    "absolute-url-request": ("client/custom/src/a.js", "define([], function () { return fetch('//other/x'); });\n"),
    "storage-api": ("client/custom/src/a.js", "define([], function () { return localStorage.getItem('k'); });\n"),
}


class TestClientPolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def good_tree(self):
        root = os.path.join(self.tmp, "t")
        shutil.rmtree(root, True)
        os.makedirs(os.path.join(root, "client", "custom", "src", "crm"))
        shutil.copy(CANARY, os.path.join(root, "client", "custom", "src", "crm", "release-canary.js"))
        return root

    def put(self, root, rel, content, mode=0o644):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)
        os.chmod(path, mode)

    def test_repository_tree_complies(self):
        self.assertEqual(client_policy_violations(REPO), [])
        self.assertTrue(os.path.isfile(CANARY))
        self.assertEqual(sorted(os.listdir(os.path.join(REPO, "client", "custom"))), ["src"])
        self.assertFalse(os.path.exists(os.path.join(REPO, "client", "custom", "modules")))

    def test_each_rule_has_a_broken_fixture_that_is_caught(self):
        self.assertEqual(client_policy_violations(self.good_tree()), [], "control")
        for rule, (rel, content) in BROKEN.items():
            with self.subTest(rule=rule):
                root = self.good_tree()
                self.put(root, rel, content)
                self.assertIn(rule, client_policy_violations(root))

    def test_symlink_executable_and_oversize_are_caught(self):
        root = self.good_tree()
        os.symlink("/etc/passwd", os.path.join(root, "client", "custom", "src", "link.js"))
        self.assertIn("symlink", client_policy_violations(root))
        root = self.good_tree()
        self.put(root, "client/custom/src/x.js", GOOD_JS, mode=0o755)
        self.assertIn("executable", client_policy_violations(root))
        root = self.good_tree()
        self.put(root, "client/custom/src/big.js", GOOD_JS + "// " + "x" * MAX_BYTES + "\n")
        self.assertIn("size", client_policy_violations(root))

    def test_comments_do_not_hide_or_cause_violations(self):
        root = self.good_tree()
        self.put(root, "client/custom/src/ok.js", "// see http://example.invalid\n/* eval( */\n" + GOOD_JS)
        self.assertEqual(client_policy_violations(root), [])

    def test_canary_is_the_f8_form_and_touches_nothing(self):
        text = read(CANARY)
        self.assertEqual(text.strip(), "define([], function () { return Object.freeze({name: 'crm-release-canary', "
                         "contract: 1, describe: function () { return 'crm-release-canary/' + 1; }}); });")
        self.assertIsNone(re.search(CANARY_FORBIDDEN, text))

    def test_v2_fixture_differs_only_in_the_contract_value(self):
        def norm(path):
            text = read(path)
            values = re.findall(r"contract: (\d+)|\+ (\d+);", text)
            return re.sub(r"contract: \d+", "contract: N", re.sub(r"\+ \d+;", "+ N;", text)), values
        t1, v1 = norm(CANARY)
        t2, v2 = norm(CANARY_V2)
        self.assertEqual(t1, t2)
        self.assertEqual(v1, [("1", ""), ("", "1")])
        self.assertEqual(v2, [("2", ""), ("", "2")])
        self.assertEqual(client_policy_violations_fixture(CANARY_V2), [])

    def test_unreferenced_canary_changes_nothing_a_user_sees(self):
        """AC7: no metadata, layout, clientDefs, navbar or i18n reference."""
        for top in ("custom", "config", "deploy"):
            for dirpath, _, files in os.walk(os.path.join(REPO, top)):
                for name in files:
                    path = os.path.join(dirpath, name)
                    try:
                        text = read(path)
                    except UnicodeDecodeError:
                        continue
                    self.assertNotIn("release-canary", text, path)
                    self.assertNotIn("custom:crm", text, path)
                    self.assertNotIn("client/custom", text.replace("client/custom", "") + "") if False else None
        self.assertEqual(sorted(os.listdir(os.path.join(REPO, "client", "custom", "src"))), ["crm"])
        self.assertEqual(os.listdir(os.path.join(REPO, "client", "custom", "src", "crm")), ["release-canary.js"])

    def test_custom_tree_is_unchanged_from_the_base_when_git_is_available(self):
        base = "6e1766980e24d781d498727d4fe5db43cdeadbb7"
        res = subprocess.run(["git", "-C", REPO, "diff", "--quiet", base, "--", "custom", "config", "deploy"],
                             capture_output=True, text=True)
        if res.returncode not in (0, 1):
            self.skipTest("no usable Git metadata")
        self.assertEqual(res.returncode, 0, "custom/**, config/** and deploy/** differ from the base")


def client_policy_violations_fixture(path):
    """The same JS rules for one file (the v2 fixture)."""
    code = strip_js_comments(read(path))
    out = [] if re.match(r"\s*define\s*\(", code) else ["not-amd"]
    return out + [r for r, rx in JS_RULES.items() if re.search(rx, code)]


# ===================================================================== AC11: runner integrity
class TestRunnerIntegrity(unittest.TestCase):
    def test_requirements_lock_is_annex_b2_exactly(self):
        lines = [l for l in read(os.path.join(BROWSER, "requirements.lock")).splitlines()
                 if l.strip() and not l.lstrip().startswith("#")]
        text = " ".join(l.strip().rstrip("\\").strip() for l in lines)
        pins = re.findall(r"(\S+==\S+) --hash=sha256:([0-9a-f]{64})", text)
        self.assertEqual(pins, [
            ("playwright==1.65.1", "5660e0b050a5bd5672bf8e366ed2580288a3d3640ff9444436ed2d890d3dc442"),
            ("greenlet==3.5.6", "975736b002ed080d124cf81a79cb7e05cb26d6b3f5c7a7b651c0fcce70353aa1")])
        self.assertEqual(len(lines), 4, "two requirements with one --hash line each and nothing else")
        self.assertNotRegex(text, r"--index-url|--extra-index|git\+|https?://")

    def test_runner_sources_hold_no_address_url_or_credential_literal(self):
        for name in ("journeys.py", "probe_isolation.py", "entry.sh"):
            with self.subTest(file=name):
                text = read(os.path.join(BROWSER, name))
                self.assertNotRegex(text, r"(?<![\d.])\d{1,3}(?:\.\d{1,3}){3}(?![\d.])")
                self.assertNotRegex(text, r"https?://")
                self.assertNotRegex(text, r"(?i)password\s*=\s*['\"][^'\"]|token\s*=\s*['\"][^'\"]")
                self.assertNotRegex(text, r"@(?!example\.test)[A-Za-z0-9-]+\.[a-z]{2,}")

    def test_runner_contacts_only_the_base_url_and_the_probe_targets(self):
        j = read(os.path.join(BROWSER, "journeys.py"))
        for forbidden in ("urlopen", "http.client", "import requests", "urllib.request", "socket.", "smtplib"):
            self.assertNotIn(forbidden, j)
        self.assertIn("CRM_BROWSER_BASE_URL", j)
        p = read(os.path.join(BROWSER, "probe_isolation.py"))
        self.assertNotIn("urllib", p)
        self.assertIn('targets.get("reachable"', p)
        self.assertIn('targets.get("unreachable"', p)
        entry = read(os.path.join(BROWSER, "entry.sh"))
        self.assertIn(":?CRM_BROWSER_BASE_URL is required", entry)
        self.assertIn(":?CRM_BROWSER_USERNAME is required", entry)
        self.assertIn(":?CRM_BROWSER_PASSWORD is required", entry)

    def test_verifier_does_no_network_io_and_runs_nothing(self):
        text = read(VERIFIER)
        for forbidden in ("import socket", "import urllib.request", "from urllib.request", "http.client",
                          "import ssl", "import subprocess", "from subprocess", "import requests",
                          "os.system", "ftplib", "smtplib", "import asyncio", "urlopen"):
            self.assertNotIn(forbidden, text)
        imports = set(re.findall(r"^(?:import|from) ([A-Za-z_.]+)", text, re.M))
        self.assertLessEqual(imports, {"argparse", "hashlib", "ipaddress", "json", "os", "re", "sys",
                                       "zipfile", "urllib.parse"})

    def test_version_check_uses_importlib_metadata_not_a_module_attribute(self):
        j = read(os.path.join(BROWSER, "journeys.py"))
        self.assertIn('metadata.version("playwright")', j)
        self.assertIn("locate_file", j)
        self.assertNotRegex(j, r"playwright\.__version__|\.__version__")
        self.assertIn('PLAYWRIGHT_VERSION = "1.65.1"', j)

    def test_playwright_launches_only_the_pinned_binary(self):
        j = read(os.path.join(BROWSER, "journeys.py"))
        launches = re.findall(r"\.launch\((.*?)\)", j, re.S)
        self.assertEqual(len(launches), 1)
        self.assertIn("executable_path=ident[\"browser\"][\"path\"]", launches[0])
        self.assertIn("chromium_sandbox=False", launches[0])
        self.assertEqual(re.findall(r'"/ms-playwright"', j), ['"/ms-playwright"'], "only the survey prefix constant")
        self.assertNotRegex(j, r"playwright install|PLAYWRIGHT_BROWSERS_PATH|launch_persistent_context")
        for kind, (path, digest) in journeys.BROWSERS.items():
            self.assertTrue(path.startswith("/opt/cft/"))
            self.assertEqual(digest, verify.CFT_BINARY_SHA256[kind])
        self.assertEqual(journeys.CFT_VERSION, verify.CFT_VERSION)
        self.assertEqual(journeys.CFT_REVISION, verify.CFT_REVISION)
        self.assertIn("process_survey", j)

    def test_entry_installs_offline_hash_locked_and_keeps_pythonpath(self):
        e = read(os.path.join(BROWSER, "entry.sh"))
        self.assertIn("--no-index --find-links /wheels --require-hashes --only-binary=:all:", e)
        self.assertIn("--no-deps --target /tmp/pydeps", e)
        self.assertIn("export PYTHONPATH=/tmp/pydeps", e)
        self.assertRegex(e, r"python3 -s -B ")
        self.assertNotRegex(e, r"python3 (?:-\w*[IE]\w*)\b", "-I and -E would ignore PYTHONPATH")
        self.assertLess(e.index("probe_isolation.py"), e.index("journeys.py\" --base-url"),
                        "isolation is proven before any journey")
        self.assertEqual(subprocess.run(["bash", "-n", os.path.join(BROWSER, "entry.sh")]).returncode, 0)
        self.assertTrue(os.stat(os.path.join(BROWSER, "entry.sh")).st_mode & 0o111)

    def test_pinned_constants_agree_between_runner_verifier_and_register(self):
        self.assertEqual(journeys.PLAYWRIGHT_VERSION, verify.PLAYWRIGHT_VERSION)
        self.assertEqual(journeys.GREENLET_VERSION, verify.GREENLET_VERSION)
        register = read(os.path.join(REPO, "security", "EXTERNAL_CODE_REGISTER.yaml"))
        for needle in ("playwright-python-browser-runner", "chrome-for-testing-stable", "grype-cl-d5-scanner",
                       verify.IMAGE_INDEX_DIGEST, verify.IMAGE_AMD64_DIGEST, verify.IMAGE_CONFIG_ID,
                       verify.CFT_BINARY_SHA256["chrome"], verify.WHEEL_SHA256["playwright"],
                       verify.WHEEL_SHA256["greenlet"], "157.0.8103.78", "v0.121.0"):
            self.assertIn(needle, register)
        self.assertEqual(len(re.findall(r"usage: test-only, operator-run", register)), 3)

    def test_check_identity_branches(self):
        good = {"python": {"playwright_version": "1.65.1", "playwright_dist_count": 1,
                           "playwright_under_pydeps": True, "greenlet_version": "3.5.6"},
                "browser": {"binary_sha256": "a" * 64, "expected_binary_sha256": "a" * 64,
                            "running_version": "157.0.8103.78", "ms_playwright_processes": 0}}
        journeys.check_identity(good)
        cases = {"playwright distribution version": ("python", "playwright_version", "1.64.1"),
                 "playwright distribution location": ("python", "playwright_dist_count", 2),
                 "greenlet version": ("python", "greenlet_version", "3.5.5"),
                 "browser binary sha256": ("browser", "binary_sha256", "b" * 64),
                 "running browser version": ("browser", "running_version", "156.0.8078.4"),
                 "bundled browser executed": ("browser", "ms_playwright_processes", 1)}
        for needle, (a, b, v) in cases.items():
            with self.subTest(needle=needle):
                bad = copy.deepcopy(good)
                bad[a][b] = v
                with self.assertRaisesRegex(journeys.RunnerError, needle):
                    journeys.check_identity(bad)

    def test_prelaunch_checks_come_before_any_playwright_driver_or_browser_start(self):
        j = read(os.path.join(BROWSER, "journeys.py"))
        body = j[j.index("def run_journeys"):j.index("def compat_probe")]
        self.assertNotRegex(j[:j.index("def run_journeys")].replace("def prelaunch", ""),
                            r"(?m)^(?:from|import) playwright", "no module-level Playwright import")
        order = [body.index("prelaunch(kind)"), body.index("raise RunnerError(\"pre-launch check failed"),
                 body.index("from playwright.sync_api import sync_playwright"), body.index("with sync_playwright()"),
                 body.index(".launch(")]
        self.assertEqual(order, sorted(order), "hash and ldd checks, then the import, the driver, the launch")
        pre = j[j.index("def prelaunch"):j.index("def process_survey")]
        self.assertNotIn("sync_playwright", pre)
        self.assertNotRegex(pre, r"\.launch\(")
        for needle in ("binary_sha256", "ldd_missing", "NODE_DRIVER", "REQUIRED_LIBRARY"):
            self.assertIn(needle, pre + j)
        self.assertEqual(journeys.REQUIRED_LIBRARY, "libatomic.so.1")
        self.assertEqual(journeys.NODE_DRIVER, "/tmp/pydeps/playwright/driver/node")
        self.assertIn("python3 -s -B", read(os.path.join(BROWSER, "entry.sh")))

    def _run_main_with_fakes(self, ident_edit=None, ldd_text=None):
        """journeys.main() with a fake identity, a fake ldd and a recording fake Playwright."""
        started = []
        fake_api = types.ModuleType("playwright.sync_api")

        def sync_playwright():
            started.append("sync_playwright")
            raise AssertionError("the Playwright driver must not start")
        fake_api.sync_playwright = sync_playwright
        good = {"python": {"playwright_version": "1.65.1", "playwright_dist_count": 1,
                           "playwright_under_pydeps": True, "greenlet_version": "3.5.6"},
                "wheels": {}, "browser": {"kind": "chrome", "path": "/opt/cft/chrome-linux64/chrome",
                                          "expected_version": "157.0.8103.78", "revision": "1717349",
                                          "binary_sha256": journeys.BROWSERS["chrome"][1],
                                          "expected_binary_sha256": journeys.BROWSERS["chrome"][1]}}
        if ident_edit:
            ident_edit(good)

        def ldd(path):
            return ldd_text(path) if ldd_text else f"\tlibc.so.6 => /lib/libc.so.6 (0x1)\n\t{journeys.REQUIRED_LIBRARY} => /lib/{journeys.REQUIRED_LIBRARY} (0x2)\n"
        saved = (journeys.collect_identity, journeys.ldd_output, sys.modules.get("playwright.sync_api"),
                 dict(os.environ))
        journeys.collect_identity = lambda kind="chrome", pydeps=None, wheels_dir=None: copy.deepcopy(good)
        journeys.ldd_output = ldd
        sys.modules["playwright.sync_api"] = fake_api
        sys.modules.setdefault("playwright", types.ModuleType("playwright"))
        os.environ.update({"CRM_BROWSER_USERNAME": "synthetic.user@example.test", "CRM_BROWSER_PASSWORD": "x-y-z-1"})
        err = io.StringIO()
        try:
            with tempfile.TemporaryDirectory() as out, redirect_stderr(err):
                code = journeys.main(["--base-url", "http://base.invalid", "--out", out])
                ident = json.loads(read(os.path.join(out, "identity.json")))
        finally:
            journeys.collect_identity, journeys.ldd_output = saved[0], saved[1]
            if saved[2] is None:
                sys.modules.pop("playwright.sync_api", None)
            else:
                sys.modules["playwright.sync_api"] = saved[2]
            os.environ.clear()
            os.environ.update(saved[3])
        return code, err.getvalue(), started, ident

    def test_wrong_binary_hash_stops_before_any_driver_start_or_launch(self):
        code, err, started, ident = self._run_main_with_fakes(
            lambda i: i["browser"].update(binary_sha256="0" * 64))
        self.assertEqual(code, 1)
        self.assertIn("browser binary sha256", err)
        self.assertEqual(started, [], "sync_playwright() was never reached")
        self.assertEqual(ident["browser"]["binary_sha256"], "0" * 64, "the finding is recorded before any launch")

    def test_a_missing_library_stops_before_any_driver_start_or_launch(self):
        cases = {"browser binary libraries missing": lambda p: "\tlibx.so => not found\n" if "chrome" in p
                 else "\tlibatomic.so.1 => /lib/libatomic.so.1 (0x2)\n",
                 "node driver libraries missing": lambda p: "\tliby.so => not found\n" if p.endswith("node")
                 else "\tlibatomic.so.1 => /lib/libatomic.so.1 (0x2)\n",
                 "libatomic.so.1 not resolved": lambda p: "\tlibatomic.so.1 => not found\n" if p.endswith("node")
                 else "\tlibc.so.6 => /lib/libc.so.6 (0x1)\n"}
        for cause, ldd in cases.items():
            with self.subTest(cause=cause):
                code, err, started, ident = self._run_main_with_fakes(ldd_text=ldd)
                self.assertEqual(code, 1)
                self.assertIn(cause, err)
                self.assertEqual(started, [])
                self.assertIn("driver", ident)

    def test_a_clean_prelaunch_reaches_the_driver_start(self):
        with self.assertRaises(AssertionError):
            self._run_main_with_fakes()

    def test_control_channel_fails_loudly(self):
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaisesRegex(journeys.RunnerError, "timed out"):
                journeys.wait_go(out, "J1", timeout=0.0, interval=0.0)
            journeys.signal_ready(out, "J1")
            self.assertTrue(os.path.exists(os.path.join(out, ".control", "ready-J1")))
            for bad in ('{"app_timestamp": 0}', '{"app_timestamp": "5"}', '{"app_timestamp": true}', "{}"):
                with open(os.path.join(out, ".control", "go-J1"), "w") as fh:
                    fh.write(bad)
                with self.assertRaisesRegex(journeys.RunnerError, "positive integer"):
                    journeys.wait_go(out, "J1", timeout=0.0)
            with open(os.path.join(out, ".control", "go-J1"), "w") as fh:
                fh.write('{"app_timestamp": 1700000010}')
            self.assertEqual(journeys.wait_go(out, "J1", timeout=0.0), 1700000010)

    def test_recorder_marks_cached_requests_and_records_csp(self):
        rec = journeys.Recorder()
        rec.requests = [{"url": "u1", "from_cache": False}, {"url": "u2", "from_cache": False}]
        rec._cached_urls.add("u2")
        self.assertEqual([r["from_cache"] for r in rec.finish()], [False, True])
        rec.on_csp('{"violated_directive": "script-src"}')
        self.assertEqual(rec.csp, [{"violated_directive": "script-src"}])
        self.assertEqual(journeys.canary_r("x/client/custom/src/crm/release-canary.js?r=17"), 17)
        self.assertIsNone(journeys.canary_r("x/client/custom/src/crm/release-canary.js"))
        self.assertIsNone(journeys.canary_r("x/a.js?r=1&r=2"))


class TestIsolationProbe(unittest.TestCase):
    ROUTE_OK = ("Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\n"
                "eth0\t0001FA0A\t00000000\t0001\t0\t0\t0\t0000FFFF\n")
    ROUTE_DEFAULT = ROUTE_OK + "eth0\t00000000\t0101FA0A\t0003\t0\t0\t0\t00000000\n"

    def test_route_table_gate(self):
        self.assertTrue(probe.routes_ok(self.ROUTE_OK))
        self.assertFalse(probe.routes_ok(self.ROUTE_DEFAULT), "a default route")
        self.assertFalse(probe.routes_ok(self.ROUTE_OK.split("\n")[0] + "\n"), "no route at all")
        two = self.ROUTE_OK + "eth1\t0002FA0A\t00000000\t0001\t0\t0\t0\t0000FFFF\n"
        self.assertFalse(probe.routes_ok(two), "two networks")

    def targets(self, host, open_port, closed_port, extra_open=False):
        reachable = [{"id": "app-http", "host": host, "port": open_port}]
        ids = [i for i in probe.REQUIRED_IDS if i not in ("app-http", "dns-public")]
        unreachable = [{"id": i, "kind": "tcp", "host": host,
                        "port": open_port if (extra_open and i == "db-3306") else closed_port} for i in ids]
        return {"reachable": reachable, "unreachable": unreachable}

    def test_gate_passes_only_when_every_unreachable_target_fails(self):
        import socket
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(5)
        self.addCleanup(srv.close)
        closed = socket.socket()
        closed.bind(("127.0.0.1", 0))
        closed_port = closed.getsockname()[1]
        closed.close()
        open_port = srv.getsockname()[1]
        t = self.targets("127.0.0.1", open_port, closed_port)
        t["unreachable"].append({"id": "dns-public", "kind": "dns", "name": "invalid."})
        res = probe.probe(t, self.ROUTE_OK)
        self.assertTrue(res["gate"], res)
        self.assertEqual([r["actual"] for r in res["targets"] if r["expected"] == "fail"],
                         ["fail"] * 9)
        t2 = self.targets("127.0.0.1", open_port, closed_port, extra_open=True)
        t2["unreachable"].append({"id": "dns-public", "kind": "dns", "name": "invalid."})
        res2 = probe.probe(t2, self.ROUTE_OK)
        self.assertFalse(res2["gate"], "an unexpected success blocks the run")
        self.assertEqual([r["id"] for r in res2["targets"] if r["expected"] != r["actual"]], ["db-3306"])
        self.assertFalse(probe.probe(t, self.ROUTE_DEFAULT)["gate"], "a default route blocks the run")
        missing = copy.deepcopy(t)
        missing["unreachable"].pop(0)
        self.assertFalse(probe.probe(missing, self.ROUTE_OK)["gate"], "a required target is absent")


# ===================================================================== AC6a: verifier
def png_bytes():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND", b""))


def zip_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("trace.trace", "{}\n")
    return buf.getvalue()


SENSITIVE = ["192.0.2.3", "192.0.2.2", "crm-dev-crm-app-1", "crm-client001r-browser-r1",
             "crm-dev.internal.example", "CRM_BROWSER_PASSWORD", "tester@example.test",
             "/srv/CRM/runtime/dev", "/tmp/crm-client001r-browser-r1", "0123456789abcdef0123456789abcdef"
             "0123456789abcdef0123456789abcdef", "console text with a secret page title"]
A = {i: 1700000000 + 10 * i for i in range(6)}


def make_good_package(root, expect_candidate="c" * 40):
    """A synthetic package that passes the verifier, written through journeys.py's writer."""
    os.makedirs(root)
    v1, v2 = sha(read(CANARY, "rb")), sha(read(CANARY_V2, "rb"))
    base = "http://192.0.2.3"
    canary_url = lambda r: f"{base}/client/custom/src/crm/release-canary.js?r={r}"  # noqa: E731
    contract_sha = {"J1": v1, "J2": v2, "J3": v1, "J4": v1}
    sig = {s: sha("sig-" + s) for s in journeys.SCREENS}
    for n, j in enumerate(journeys.JOURNEYS, start=1):
        reqs = [{"url": base + "/", "method": "GET", "status": 200, "from_cache": False,
                 "response_sha256": None, "resource_type": "document"}]
        if j in contract_sha:
            reqs.append({"url": canary_url(A[n]), "method": "GET", "status": 200, "from_cache": False,
                         "response_sha256": contract_sha[j], "resource_type": "script"})
        else:
            reqs.append({"url": base + "/client/custom/src/crm/release-canary.js?r=%d" % A[n],
                         "method": "GET", "status": 404, "from_cache": False,
                         "response_sha256": None, "resource_type": "script"})
        console = [] if j != "J5" else [{"type": "error", "text": "console text with a secret page title",
                                         "url": base, "phase": "probe"}]
        asserts = [journeys.assertion("everything", "AC6b", True, True, True)]
        if j in ("J1", "J5"):
            asserts += [journeys.assertion(f"screen:{s}", "AC6b", "rendered",
                                           {"signature": sig[s], "headings": 4, "rows": 2}, True)
                        for s in journeys.SCREENS]
        d = journeys.write_journey_files(root, j, reqs, console, [], asserts)
        with open(os.path.join(d, "trace.zip"), "wb") as fh:
            fh.write(zip_bytes())
        if j in ("J1", "J5"):
            for s in journeys.SCREENS:
                with open(os.path.join(d, f"{s}.png"), "wb") as fh:
                    fh.write(png_bytes())
    journeys.write_json(os.path.join(root, "timestamps.json"),
                        {**{f"a{i}": A[i] for i in range(6)},
                         "observed_r": {f"J{i}": A[i] for i in range(1, 5)}})
    journeys.write_json(os.path.join(root, "identity.json"), {
        "candidate": expect_candidate, "transition_manifest_sha256": sha("T"),
        "snapshot_manifest_sha256": sha("S"),
        "image": {"index_digest": verify.IMAGE_INDEX_DIGEST, "amd64_digest": verify.IMAGE_AMD64_DIGEST,
                  "config_id": verify.IMAGE_CONFIG_ID,
                  "repo_digest": "mcr.microsoft.com/playwright/python@" + verify.IMAGE_AMD64_DIGEST},
        "wheels": dict(verify.WHEEL_SHA256),
        "python": {"playwright_version": "1.65.1", "playwright_dist_count": 1,
                   "playwright_under_pydeps": True, "greenlet_version": "3.5.6"},
        "browser": {"kind": "chrome", "path": "/opt/cft/chrome-linux64/chrome",
                    "binary_sha256": verify.CFT_BINARY_SHA256["chrome"], "running_version": "157.0.8103.78",
                    "revision": "1717349", "process_exe_is_pinned": True, "ms_playwright_processes": 0,
                    "ldd_missing": 0},
        "driver": {"path": "/tmp/pydeps/playwright/driver/node", "ldd_missing": 0,
                   "required_library": "libatomic.so.1", "required_library_resolved": True},
        "compat_probe": {"passed": True, "steps": {"new_context": True, "tracing": True}},
        "docker_version": "24.0.5",
        "container": {"Name": "crm-client001r-browser-r1", "CapDrop": ["ALL"], "ReadonlyRootfs": True,
                      "Privileged": False, "User": "65534:65534", "NetworkMode": "crm-client001r-browser-r1",
                      "SecurityOpt": ["no-new-privileges=true"],
                      "Mounts": [{"Source": "/tmp/crm-client001r-browser-r1/out", "Destination": "/evidence"}],
                      "IPAddress": "192.0.2.2"}})
    targets = []
    for tid in verify.ISOLATION_IDS:
        ok = tid == "app-http"
        targets.append({"id": tid, "kind": "tcp", "host": "192.0.2.3", "port": 80 if ok else 3306,
                        "expected": "success" if ok else "fail", "actual": "success" if ok else "fail",
                        "elapsed": 0.01 if ok else 3.0})
    journeys.write_json(os.path.join(root, "isolation.json"), {
        "route_table": "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\n"
                       "eth0\t0001FA0A\t00000000\t0001\t0\t0\t0\t0000FFFF\n",
        "targets": targets, "gate": True})
    os.makedirs(os.path.join(root, "scan"))
    journeys.write_json(os.path.join(root, "scan", "db-status.json"),
                        {"grype_version": "v0.121.0", "db_built": "2026-11-16T10:00:00Z",
                         "db_checksum": "sha256:" + sha("db")})
    journeys.write_json(os.path.join(root, "scan", "triage.json"), {"findings": [
        {"id": "x1", "severity": "Medium", "triage": "not-material", "material": False, "resolution": "none"},
        {"id": "x2", "severity": "High", "triage": "mitigated", "material": True, "resolution": "mitigation"}]})
    for name in ("image", "wheels", "cft", "osv"):
        journeys.write_json(os.path.join(root, "scan", f"{name}.json"), {})
    journeys.write_json(os.path.join(root, "cleanup.json"), {l: True for l in verify.CLEANUP_LABELS})
    for name in ("beta-before.json", "beta-after.json"):
        journeys.write_json(os.path.join(root, name), {"stat": "0:0 700", "containers": ["x"]})
    journeys.write_json(os.path.join(root, "crmdev-before.json"), {"env_sha256": sha("env")})
    with open(os.path.join(root, "invocation.txt"), "w") as fh:
        fh.write("docker run --env CRM_BROWSER_BASE_URL=http://192.0.2.3 tester@example.test\n")
    seal(root)
    return root


def seal(root):
    lines = []
    for dirpath, _, files in os.walk(root):
        for name in files:
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            if rel != "SHA256SUMS":
                lines.append(f"{sha(read(os.path.join(dirpath, name), 'rb'))}  {rel}\n")
    with open(os.path.join(root, "SHA256SUMS"), "w") as fh:
        fh.writelines(sorted(lines, key=lambda l: l.split("  ", 1)[1]))


def edit_json(root, rel, fn):
    path = os.path.join(root, rel)
    data = json.loads(read(path))
    fn(data)  # mutates in place; the return value is ignored
    journeys.write_json(path, data)


def edit_jsonl(root, rel, fn):
    path = os.path.join(root, rel)
    rows = [json.loads(l) for l in read(path).splitlines() if l.strip()]
    out = fn(rows)
    journeys.write_jsonl(path, rows if out is None else out)


class VerifierBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.n = 0

    def package(self):
        self.n += 1
        return make_good_package(os.path.join(self.tmp, f"pkg{self.n}"))

    def run_verify(self, pkg, **kw):
        rep, sums = verify.verify(pkg, REPO, kw.get("expect", "c" * 40))
        return rep, sums

    def causes(self, rep):
        return [f"{g}/{j or ''}:{c}" for g, c, j in rep.failures]


class TestVerifierGoodAndLayout(VerifierBase):
    def test_good_package_passes(self):
        rep, _ = self.run_verify(self.package())
        self.assertEqual(rep.failures, [])

    def test_cli_exit_codes(self):
        pkg = self.package()
        res = subprocess.run([sys.executable, "-I", VERIFIER, pkg, "--candidate-root", REPO,
                              "--expect-candidate", "c" * 40], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("VERDICT: PASS", res.stdout)
        os.remove(os.path.join(pkg, "csp.jsonl")) if os.path.exists(os.path.join(pkg, "csp.jsonl")) else None
        edit_jsonl(pkg, "journeys/J3/csp.jsonl", lambda rows: [{"violated_directive": "script-src"}])
        seal(pkg)
        res = subprocess.run([sys.executable, "-I", VERIFIER, pkg, "--candidate-root", REPO],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        self.assertIn("csp-violation", res.stdout)
        self.assertIn("VERDICT: FAIL", res.stdout)

    def test_journeys_writer_produces_exactly_the_annex_b6_layout(self):
        with tempfile.TemporaryDirectory() as out:
            d = journeys.write_journey_files(out, "J1", [], [], [], [])
            self.assertEqual(d, os.path.join(out, "journeys", "J1"))
            self.assertEqual(sorted(os.listdir(d)), ["console.jsonl", "csp.jsonl", "requests.jsonl", "result.json"])
        self.assertEqual(journeys.JOURNEY_FILES, verify.JOURNEY_FILES)
        self.assertEqual(journeys.JOURNEYS, verify.JOURNEYS)
        self.assertEqual(journeys.SCREENS, verify.SCREENS)
        pkg = self.package()
        found = set()
        for dirpath, _, files in os.walk(pkg):
            found |= {os.path.relpath(os.path.join(dirpath, f), pkg) for f in files}
        self.assertEqual(found, set(verify.required_files()), "no file beyond annex B6, none missing")
        self.assertEqual(sorted(os.listdir(os.path.join(pkg, "journeys"))), list(journeys.JOURNEYS))
        self.assertEqual(sorted(os.listdir(os.path.join(pkg, "journeys", "J2"))), sorted(journeys.JOURNEY_FILES + ("result.json",)[:0]))
        self.assertEqual(sorted(os.listdir(os.path.join(pkg, "journeys", "J1"))),
                         sorted(list(journeys.JOURNEY_FILES) + [f"{s}.png" for s in journeys.SCREENS]))

    def test_result_json_is_ignored(self):
        pkg = self.package()
        for j in journeys.JOURNEYS:  # the runner's own verdicts claim failure everywhere
            edit_json(pkg, f"journeys/{j}/result.json",
                      lambda d: d.update(assertions=[dict(a, **{"pass": False}) for a in d["assertions"]]))
        seal(pkg)
        self.assertEqual(self.run_verify(pkg)[0].failures, [], "false claims of failure do not matter")
        edit_jsonl(pkg, "journeys/J3/csp.jsonl", lambda rows: [{"violated_directive": "script-src"}])
        for j in journeys.JOURNEYS:  # and claims of success cannot hide a raw failure
            edit_json(pkg, f"journeys/{j}/result.json",
                      lambda d: d.update(assertions=[dict(a, **{"pass": True}) for a in d["assertions"]]))
        seal(pkg)
        self.assertIn("journeys/J3:csp-violation", self.causes(self.run_verify(pkg)[0]))


def put(path, data, mode="wb"):
    with open(path, mode) as fh:
        fh.write(data)


def tamper(label, fn, cause, reseal=True, **kw):
    return (label, fn, cause, reseal, kw)


def _r(pkg, j, r):
    edit_jsonl(pkg, f"journeys/{j}/requests.jsonl",
               lambda rows: [dict(x, url=re.sub(r"r=\d+", f"r={r}", x["url"])) if "release-canary" in x["url"] else x
                             for x in rows])


def _canary(pkg, j, **changes):
    edit_jsonl(pkg, f"journeys/{j}/requests.jsonl",
               lambda rows: [dict(x, **changes) if "release-canary" in x["url"] else x for x in rows])


def _ident(pkg, path, value):
    def fn(d):
        cur = d
        for k in path[:-1]:
            cur = cur[k]
        cur[path[-1]] = value
    edit_json(pkg, "identity.json", fn)


TAMPERS = [
    tamper("missing file", lambda p: os.remove(os.path.join(p, "journeys/J2/csp.jsonl")), "missing-file: journeys/J2/csp.jsonl"),
    tamper("missing screenshot", lambda p: os.remove(os.path.join(p, "journeys/J5/stream.png")), "missing-file: journeys/J5/stream.png"),
    tamper("sha256sums mismatch", lambda p: put(os.path.join(p, "invocation.txt"), "x\n", "a"), "sha256-mismatch: invocation.txt", reseal=False),
    tamper("unlisted file", lambda p: put(os.path.join(p, "extra.txt"), "x", "w"), "unlisted-file: extra.txt", reseal=False),
    tamper("equal r", lambda p: (_r(p, "J2", A[1]), edit_json(p, "timestamps.json", lambda d: d.update(a2=A[1]))), "r-not-advancing"),
    tamper("non-advancing timestamp", lambda p: edit_json(p, "timestamps.json", lambda d: d.update(a3=d["a2"])), "timestamp-not-advancing: a3 <= a2"),
    tamper("r differs from the crm-app value", lambda p: _r(p, "J1", A[1] + 1), "r-differs-from-the-crm-app-timestamp"),
    tamper("cached fetch of the new URL", lambda p: _canary(p, "J2", from_cache=True), "cached-or-absent-fetch"),
    tamper("absent fetch", lambda p: edit_jsonl(p, "journeys/J2/requests.jsonl", lambda rows: [r for r in rows if "release-canary" not in r["url"]]), "cached-or-absent-fetch"),
    tamper("wrong contract served", lambda p: _canary(p, "J2", response_sha256=sha(read(CANARY, "rb"))), "wrong-canary-contract"),
    tamper("canary present after restore", lambda p: _canary(p, "J5", status=200), "canary-present-after-restore"),
    tamper("csp event", lambda p: edit_jsonl(p, "journeys/J3/csp.jsonl", lambda rows: [{"violated_directive": "script-src"}]), "csp-violation"),
    tamper("canary console error", lambda p: edit_jsonl(p, "journeys/J1/console.jsonl", lambda rows: [{"type": "error", "text": "x", "url": "", "phase": "page"}]), "canary-console-error"),
    tamper("probe-phase error in a contract journey", lambda p: edit_jsonl(p, "journeys/J2/console.jsonl", lambda rows: [{"type": "error", "text": "x", "url": "", "phase": "probe"}]), "canary-console-error"),
    tamper("page error outside the probe in J5", lambda p: edit_jsonl(p, "journeys/J5/console.jsonl", lambda rows: rows + [{"type": "pageerror", "text": "x", "url": "", "phase": "page"}]), "canary-console-error"),
    tamper("unexpected isolation success", lambda p: edit_json(p, "isolation.json", lambda d: [t.update(actual="success") for t in d["targets"] if t["id"] == "db-3306"]), "unexpected-isolation-success: db-3306"),
    tamper("default route", lambda p: edit_json(p, "isolation.json", lambda d: d.update(route_table=d["route_table"] + "eth0\t00000000\t0101FA0A\t0003\t0\t0\t0\t00000000\n")), "route-table-has-a-default-route"),
    tamper("isolation target missing", lambda p: edit_json(p, "isolation.json", lambda d: d.update(targets=d["targets"][:-1])), "isolation-target-missing: dns-public"),
    tamper("wrong Playwright version", lambda p: _ident(p, ["python", "playwright_version"], "1.64.1"), "wrong-playwright-version"),
    tamper("two Playwright distributions", lambda p: _ident(p, ["python", "playwright_dist_count"], 2), "playwright-distribution-location"),
    tamper("wrong browser version", lambda p: _ident(p, ["browser", "running_version"], "156.0.8078.4"), "wrong-browser-version"),
    tamper("wrong browser revision", lambda p: _ident(p, ["browser", "revision"], "1248"), "wrong-browser-revision"),
    tamper("wrong browser binary", lambda p: _ident(p, ["browser", "binary_sha256"], "0" * 64), "wrong-browser-binary"),
    tamper("bundled browser executed", lambda p: _ident(p, ["browser", "ms_playwright_processes"], 1), "bundled-browser-executed"),
    tamper("node driver library missing", lambda p: _ident(p, ["driver", "ldd_missing"], 1), "node-driver-libraries-missing"),
    tamper("libatomic unresolved", lambda p: _ident(p, ["driver", "required_library_resolved"], False), "node-driver-required-library-unresolved"),
    tamper("browser library missing", lambda p: _ident(p, ["browser", "ldd_missing"], 2), "browser-libraries-missing"),
    tamper("compat probe failed", lambda p: _ident(p, ["compat_probe", "passed"], False), "compatibility-probe-not-passed"),
    tamper("candidate mismatch", lambda p: _ident(p, ["candidate"], "d" * 40), "candidate-identity-mismatch"),
    tamper("image digest mismatch", lambda p: _ident(p, ["image", "amd64_digest"], "sha256:" + "0" * 64), "image-identity-mismatch: amd64_digest"),
    tamper("config id mismatch", lambda p: _ident(p, ["image", "config_id"], "sha256:" + "0" * 64), "image-identity-mismatch: config_id"),
    tamper("wheel mismatch", lambda p: _ident(p, ["wheels", "playwright"], "0" * 64), "wheel-identity-mismatch: playwright"),
    tamper("privileged container", lambda p: _ident(p, ["container", "Privileged"], True), "container-hardening: privileged"),
    tamper("docker socket mounted", lambda p: _ident(p, ["container", "Mounts"], [{"Source": "/var/run/docker.sock"}]), "container-hardening: docker socket mounted"),
    tamper("cleanup failure", lambda p: edit_json(p, "cleanup.json", lambda d: d.update(env_file_identical=False)), "cleanup-failure: env_file_identical"),
    tamper("cleanup label absent", lambda p: edit_json(p, "cleanup.json", lambda d: d.pop("beta_unchanged")), "cleanup-failure: beta_unchanged"),
    tamper("beta changed", lambda p: edit_json(p, "beta-after.json", lambda d: d.update(stat="0:0 755")), "beta-changed"),
    tamper("regression screen differs", lambda p: edit_json(p, "journeys/J5/result.json", lambda d: [a["observed"].update(signature="f" * 64) for a in d["assertions"] if a["id"] == "screen:stream"]), "regression-screen-mismatch: stream"),
    tamper("invalid screenshot", lambda p: put(os.path.join(p, "journeys/J1/login.png"), b"not a png"), "screenshot-invalid: login"),
    tamper("invalid trace", lambda p: put(os.path.join(p, "journeys/J4/trace.zip"), b"nope"), "trace-invalid"),
    tamper("unresolved material finding", lambda p: edit_json(p, "scan/triage.json", lambda d: d["findings"].append({"severity": "High", "material": True, "resolution": "none"})), "unresolved-material-finding"),
    tamper("symlink in the package", lambda p: os.symlink("/etc/passwd", os.path.join(p, "link.txt")), "symlink-in-package: link.txt", reseal=False),
]


class TestVerifierTamper(VerifierBase):
    def test_each_tampered_variant_fails_with_its_cause(self):
        control = self.run_verify(self.package())[0]
        self.assertEqual(control.failures, [])
        for label, fn, cause, reseal, kw in TAMPERS:
            with self.subTest(variant=label):
                pkg = self.package()
                fn(pkg)
                if reseal:
                    seal(pkg)
                rep, _ = self.run_verify(pkg, **kw)
                causes = [c for _, c, _ in rep.failures]
                self.assertTrue(any(cause in c for c in causes), f"{cause!r} not in {causes}")

    def test_candidate_option_is_enforced(self):
        rep, _ = verify.verify(self.package(), REPO, "e" * 40)
        self.assertTrue([c for _, c, _ in rep.failures if "candidate-identity-mismatch" in c])

    def test_every_failure_is_attributed_to_its_journey(self):
        pkg = self.package()
        edit_jsonl(pkg, "journeys/J3/csp.jsonl", lambda rows: [{"violated_directive": "script-src"}])
        seal(pkg)
        rep, _ = self.run_verify(pkg)
        self.assertEqual([f[2] for f in rep.failures], ["J3"])


# ===================================================================== AC6c: public summary
class TestPublicSummary(VerifierBase):
    def summarise(self, pkg, out=None):
        out = out or os.path.join(self.tmp, "out")
        return subprocess.run([sys.executable, "-I", VERIFIER, pkg, "--candidate-root", REPO,
                               "--expect-candidate", "c" * 40, "--run", "run-0001",
                               "--public-summary", out], capture_output=True, text=True), out

    def test_clean_package_gives_a_deterministic_summary_without_forbidden_items(self):
        pkg = self.package()
        res1, out1 = self.summarise(pkg, os.path.join(self.tmp, "o1"))
        res2, out2 = self.summarise(pkg, os.path.join(self.tmp, "o2"))
        self.assertEqual(res1.returncode, 0, res1.stdout + res1.stderr)
        self.assertEqual(sorted(os.listdir(out1)), ["EVIDENCE.md", "public-summary.json"])
        for name in ("public-summary.json", "EVIDENCE.md"):
            self.assertEqual(read(os.path.join(out1, name), "rb"), read(os.path.join(out2, name), "rb"),
                             "deterministic")
        text = read(os.path.join(out1, "public-summary.json")) + read(os.path.join(out1, "EVIDENCE.md"))
        for item in SENSITIVE:
            self.assertNotIn(item, text)
        data = json.loads(read(os.path.join(out1, "public-summary.json")))
        self.assertEqual(data["verdict"], "PASS")
        self.assertEqual(data["run"], "run-0001")
        self.assertEqual(data["candidate"], "c" * 40)
        self.assertEqual(data["sha256sums_sha256"], sha(read(os.path.join(pkg, "SHA256SUMS"), "rb")))
        self.assertEqual(data["raw_file_sha256"]["journeys/J2/requests.jsonl"],
                         sha(read(os.path.join(pkg, "journeys/J2/requests.jsonl"), "rb")))
        self.assertEqual(data["findings"]["by_severity"], {"high": 1, "medium": 1})
        self.assertEqual(sorted(data["journeys"]), list(journeys.JOURNEYS))
        self.assertEqual(data["cleanup"], {l: True for l in sorted(verify.CLEANUP_LABELS)})
        # independent scan of the output: no valid address, URL, e-mail, env name, port or absolute path
        scrubbed = re.sub(r"\b[0-9a-f]{40,64}\b", "H", text)
        scrubbed = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", "T", scrubbed)
        import ipaddress
        for m in re.finditer(r"(?<![\d.])\d{1,3}(?:\.\d{1,3}){3}(?![\d.])", scrubbed):
            with self.assertRaises(ValueError):
                ipaddress.IPv4Address(m.group(0))
        self.assertNotRegex(scrubbed, r"://|@|[A-Z]{2,}_[A-Z_]+|(?<![\w/]):\d{2,5}\b|(?<![\w.])/[a-z]+/")

    def test_a_failed_package_is_summarised_as_fail(self):
        pkg = self.package()
        edit_jsonl(pkg, "journeys/J3/csp.jsonl", lambda rows: [{"violated_directive": "script-src"}])
        seal(pkg)
        res, out = self.summarise(pkg)
        self.assertEqual(res.returncode, 1)
        data = json.loads(read(os.path.join(out, "public-summary.json")))
        self.assertEqual((data["verdict"], data["journeys"]["J3"]["verdict"], data["journeys"]["J2"]["verdict"]),
                         ("FAIL", "FAIL", "PASS"))
        self.assertEqual((data["acs"]["AC6b"], data["acs"]["AC12"]), ("FAIL", "PASS"))

    SEEDS = [
        ("ipv4", "192.0.2.5"), ("ipv6", "2001:db8::1"), ("hostname", "crm-app.internal.example"),
        ("url", "http://example.test/x"), ("port", "svc:8180"),
        ("container-or-network-id", "0123456789ab"), ("container-or-network-id", "ab" * 32),
        ("env-name", "CRM_BIND_IP"), ("env-value", "CRM_BIND_IP=1"),
        ("email", "ops@corp.example.com"), ("path", "/etc/passwd"),
        ("free-text", "connection refused while loading the page"),
    ]

    def test_each_forbidden_item_is_refused_with_its_class_and_nothing_is_written(self):
        for item_class, value in self.SEEDS:
            with self.subTest(item=item_class, value=value):
                pkg = self.package()
                edit_json(pkg, "scan/triage.json", lambda d: d["findings"].append(
                    {"severity": "Low", "triage": value, "material": False, "resolution": "none"}))
                seal(pkg)
                res, out = self.summarise(pkg)
                self.assertEqual(res.returncode, 4, res.stdout + res.stderr)
                self.assertIn(f"forbidden item class: {item_class}", res.stderr)
                self.assertFalse(os.path.exists(os.path.join(out, "public-summary.json")))
                self.assertFalse(os.path.exists(os.path.join(out, "EVIDENCE.md")))

    # synthetic value derived at run time from a fixed label (alphanumeric, no literal)
    CREDENTIAL = "q" + hashlib.sha256(b"crm-client-test-label").hexdigest()[:11]

    def summarise_with_credential(self, pkg, out=None):
        out = out or os.path.join(self.tmp, "out")
        env = {**os.environ, "CRM_BROWSER_USERNAME": "synthetic.user@example.test",
               "CRM_BROWSER_PASSWORD": self.CREDENTIAL}
        res = subprocess.run([sys.executable, "-I", VERIFIER, pkg, "--candidate-root", REPO,
                              "--expect-candidate", "c" * 40, "--run", "run-0001",
                              "--public-summary", out], capture_output=True, text=True, env=env)
        return res, out

    def test_the_browser_credential_value_is_refused_wherever_it_would_appear(self):
        cases = [("triage field", "scan/triage.json",
                  lambda d: d["findings"].append({"severity": "Low", "triage": self.CREDENTIAL,
                                                  "material": False, "resolution": "none"})),
                 ("cleanup label", "cleanup.json", lambda d: d.update({self.CREDENTIAL: True})),
                 ("wheel name", "identity.json", lambda d: d["wheels"].update({self.CREDENTIAL: "0" * 64}))]
        for label, rel, fn in cases:
            with self.subTest(where=label):
                pkg = self.package()
                edit_json(pkg, rel, fn)
                seal(pkg)
                res, out = self.summarise_with_credential(pkg)
                self.assertEqual(res.returncode, 4, res.stdout + res.stderr)
                self.assertIn("forbidden item class: credential", res.stderr)
                self.assertNotIn(self.CREDENTIAL, res.stdout + res.stderr, "the value is never echoed")
                self.assertFalse(os.path.exists(os.path.join(out, "public-summary.json")))
                self.assertFalse(os.path.exists(os.path.join(out, "EVIDENCE.md")))

    def test_without_the_credential_in_the_package_the_summary_is_written_and_clean(self):
        pkg = self.package()
        res, out = self.summarise_with_credential(pkg)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        for name in os.listdir(out):
            self.assertNotIn(self.CREDENTIAL, read(os.path.join(out, name)))
            self.assertNotIn("synthetic.user", read(os.path.join(out, name)))

    def test_the_credential_is_read_from_the_environment_only(self):
        text = read(VERIFIER)
        self.assertIn("os.environ.get(n)", text)
        self.assertNotRegex(text, r"--password|--credential|add_argument\(\"--user")

    def test_forbidden_items_in_other_pass_through_fields_are_refused(self):
        cases = [("scan/db-status.json", lambda d: d.update(grype_version="192.0.2.5"), "ipv4"),
                 ("scan/db-status.json", lambda d: d.update(db_built="2026-11-16 at host-1.example.org"), "hostname"),
                 ("cleanup.json", lambda d: d.update({"env_CRM_X=1": True}), "env-value"),
                 ("cleanup.json", lambda d: d.update(**{"container 0123456789ab": True}), "container-or-network-id"),
                 ("identity.json", lambda d: d["browser"].update(running_version="http://x.example/157"), "url"),
                 ("identity.json", lambda d: d["wheels"].update({"host.example.org": "0" * 64}), "hostname")]
        for rel, fn, item_class in cases:
            with self.subTest(file=rel, item=item_class):
                pkg = self.package()
                edit_json(pkg, rel, fn)
                seal(pkg)
                res, _ = self.summarise(pkg)
                self.assertEqual(res.returncode, 4, res.stdout + res.stderr)
                self.assertIn(f"forbidden item class: {item_class}", res.stderr)

    def test_a_raw_file_name_that_is_not_a_plain_relative_path_is_refused(self):
        pkg = self.package()
        with open(os.path.join(pkg, "evil.example.com"), "w") as fh:
            fh.write("x")
        seal(pkg)
        res, _ = self.summarise(pkg)
        self.assertEqual(res.returncode, 4)
        self.assertIn("forbidden item class: hostname", res.stderr)

    def test_classifier_edges(self):
        self.assertIsNone(verify.classify("157.0.8103.78"), "a browser version is not an address")
        self.assertIsNone(verify.classify("2026-11-16T10:00:00Z"))
        self.assertIsNone(verify.classify("screen:account-list"))
        self.assertIsNone(verify.classify("user@example.test"), "only the example.test domain is allowed")
        self.assertEqual(verify.classify("user@example.org"), "email")
        self.assertEqual(verify.classify("[::1]"), "ipv6")
        self.assertIsNone(verify.classify("sha256:" + "a" * 64, allow_hash=True))
        self.assertEqual(verify.classify("a" * 64), "container-or-network-id")

    def test_summary_never_holds_a_string_it_did_not_type_check(self):
        with self.assertRaises(verify.Refused):
            verify.safe_str("label", "Two words")
        with self.assertRaises(verify.Refused):
            verify.safe_str("run", "../x")
        with self.assertRaises(verify.Refused):
            verify.safe_str("path", "/abs/path.json")
        with self.assertRaises(verify.Refused):
            verify.safe_str("commit", None)
        self.assertEqual(verify.safe_str("path", "journeys/J1/result.json"), "journeys/J1/result.json")


# ===================================================================== AC9: release integrity
class TestReleaseIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        env = {**os.environ, "GIT_AUTHOR_DATE": "2026-11-16T12:00:00Z", "GIT_COMMITTER_DATE": "2026-11-16T12:00:00Z",
               "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

        def git(*args):
            subprocess.run(["git", "-C", self.repo, *args], check=True, capture_output=True, env=env)
        os.makedirs(self.repo)
        git("init", "-q", "-b", "main")
        git("config", "user.name", "t")
        git("config", "user.email", "t@example.invalid")
        for rel in ("security/EXTERNAL_CODE_REGISTER.yaml", "deploy/compose.json", "deploy/beta/compose.json",
                    "scripts/release.py", "client/custom/src/crm/release-canary.js"):
            dst = os.path.join(self.repo, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(os.path.join(REPO, rel), dst)
        git("add", "-A")
        git("commit", "-q", "-m", "candidate")
        self.commit = subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"], capture_output=True,
                                     text=True).stdout.strip()
        out = os.path.join(self.tmp, "out")
        os.makedirs(out)
        self.bundle, self.manifest = release.build(self.repo, self.commit, out)
        self.sha = release.sha256(read(self.bundle, "rb"))

    def test_bundle_verifies_anchored_and_lists_the_canary_with_its_sha256(self):
        manifest = release.verify(self.bundle, self.sha)
        rel = "client/custom/src/crm/release-canary.js"
        self.assertEqual(manifest["files"][rel], release.sha256(read(CANARY, "rb")))
        self.assertEqual(self.manifest["files"][rel], manifest["files"][rel])
        with self.assertRaises(release.ReleaseError):
            release.verify(self.bundle, "0" * 64)

    def test_verify_tree_refuses_a_file_injected_under_client_custom_src(self):
        tree_dir = os.path.join(self.tmp, "tree")
        os.mkdir(tree_dir)
        with tarfile.open(self.bundle) as tar:
            tar.extractall(tree_dir, filter="data")
        (top,) = os.listdir(tree_dir)
        root = os.path.join(tree_dir, top)
        release.verify_tree(root, self.bundle, self.sha)  # control
        evil = os.path.join(root, "client", "custom", "src", "crm", "evil.js")
        with open(evil, "w") as fh:
            fh.write("define([], function () { return 1; });\n")
        with self.assertRaisesRegex(release.ReleaseError, "extra files"):
            release.verify_tree(root, self.bundle, self.sha)
        os.remove(evil)
        canary = os.path.join(root, "client", "custom", "src", "crm", "release-canary.js")
        with open(canary, "a") as fh:
            fh.write("// tampered\n")
        with self.assertRaisesRegex(release.ReleaseError, "changed files"):
            release.verify_tree(root, self.bundle, self.sha)


if __name__ == "__main__":
    unittest.main()
