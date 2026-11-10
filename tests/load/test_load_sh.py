"""scripts/load.sh guard tests (CRM-006 item 7), in the style of the CRM-001 script tests.

The script's four fixed-path lines are rewritten in a temporary copy (the caller's uid
instead of root, temporary snapshot and runtime bases, the real repository); everything
else runs unchanged. crm-load really runs: with a closed loopback port it passes the gate
and fails at the transport (exit 4), which proves every shell guard let it through.
"""

import os
import re
import shutil
import socket
import stat
import subprocess
import tempfile
import unittest

from tests.load import fixtures as fx
from tests.load.fixtures import SENTINEL, write_snapshot

ROOT = fx.ROOT
SCRIPT = os.path.join(ROOT, "scripts", "load.sh")
KEY = "test-api-key-" + SENTINEL


def _closed_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def seal(root):
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            os.chmod(os.path.join(dirpath, name), 0o400)
        os.chmod(dirpath, 0o700)


def unseal(root):
    for dirpath, dirnames, filenames in os.walk(root):
        os.chmod(dirpath, 0o700)
        for name in filenames:
            os.chmod(os.path.join(dirpath, name), 0o600)


class LoadShBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir=os.environ.get("TMPDIR"))
        self.addCleanup(self._cleanup)
        self.base = os.path.join(self.tmp, "snapshots")
        self.runtime = os.path.join(self.tmp, "runtime")
        self.outs = os.path.join(self.tmp, "outs")
        for d in (self.base, self.outs, os.path.join(self.runtime, "dev"), os.path.join(self.runtime, "beta")):
            os.makedirs(d, mode=0o700)
            os.chmod(d, 0o700)
        with open(SCRIPT) as fh:
            text = fh.read()
        subs = {"REQUIRED_UID": str(os.geteuid()), "SNAPSHOT_BASE": self.base, "RUNTIME_BASE": self.runtime,
                "REPO_DIR": ROOT}
        for name, value in subs.items():
            text, n = re.subn(rf"^{name}=.*$", f"{name}={value}", text, count=1, flags=re.M)
            self.assertEqual(n, 1, name)
        self.script = os.path.join(self.tmp, "load.sh")
        with open(self.script, "w") as fh:
            fh.write(text)
        self.synthetic = self.snapshot("synth", synthetic=True)
        self.real = self.snapshot("real", synthetic=False)
        self.port = _closed_port()
        for target in ("dev", "beta"):
            self.write_env(target)

    def _cleanup(self):
        for dirpath, dirnames, _ in os.walk(self.tmp):
            for d in dirnames:
                os.chmod(os.path.join(dirpath, d), 0o700)
        shutil.rmtree(self.tmp, True)

    def snapshot(self, name, synthetic, **kw):
        """``<base>/<name>-selftest/run-1`` (sealed parent) or ``<base>/<name>-extract``."""
        root = write_snapshot(os.path.join(self.base, name), synthetic=synthetic, **kw)
        seal(os.path.dirname(root) if synthetic else root)
        return root

    def rec_for(self, snapshot, **override):
        """A sealed reconcile run bound to ``snapshot``, directly under the snapshots base."""
        tag = os.path.basename(snapshot)
        if tag in ("run-1", "run-2"):
            tag = os.path.basename(os.path.dirname(snapshot)) + "-" + tag
        name = tag + "-reconcile"
        root = os.path.join(self.base, name)
        if override:
            name = name[:-len("-reconcile")] + f"-{len(os.listdir(self.base))}-reconcile"
            root = os.path.join(self.base, name)
        if not os.path.exists(root):
            fx.write_reconcile_run(root, {"objects": {}}, snapshot=fx.snapshot_ref(snapshot, **override))
            seal(root)
        return root

    def write_env(self, target, lines=None, mode=0o600):
        path = os.path.join(self.runtime, target, "load.env")
        if os.path.exists(path):
            os.chmod(path, 0o600)
        if lines is None:
            lines = ["# synthetic", "CRM_LOAD_HOST=127.0.0.1", f"CRM_LOAD_PORT={self.port}",
                     f"CRM_LOAD_API_KEY={KEY}"]
        with open(path, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        os.chmod(path, mode)
        return path

    def run_sh(self, *args, script=None):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": self.tmp,
               # Must not leak into crm-load: the script runs it with env -i.
               "CRM_LOAD_HOST": "example.test", "PYTHONPATH": "/nonexistent"}
        res = subprocess.run(["bash", script or self.script, *args], capture_output=True, text=True, env=env,
                             timeout=60)
        self.assertNotIn(KEY, res.stdout + res.stderr, "API key printed")
        self.assertNotIn(SENTINEL, res.stdout + res.stderr, "record content printed")
        return res

    def out(self, name="o1"):
        return os.path.join(self.outs, name)

    def assertRefused(self, res, fragment, out=None):
        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertIn("refusing to run", res.stderr)
        self.assertIn(fragment, res.stderr)
        self.assertNotIn("crm-load event=", res.stderr)       # crm-load never started
        if out:
            self.assertFalse(os.path.exists(out))


class TestShippedScript(unittest.TestCase):
    def test_fixed_paths(self):
        with open(SCRIPT) as fh:
            text = fh.read()
        self.assertRegex(text, r"(?m)^REQUIRED_UID=0$")
        self.assertRegex(text, r"(?m)^SNAPSHOT_BASE=/srv/CRM/runtime/migrate/snapshots$")
        self.assertRegex(text, r"(?m)^RUNTIME_BASE=/srv/CRM/runtime$")
        self.assertIn('python3 -I -B "$REPO_DIR/load/bin/crm-load.py"', text)
        self.assertNotRegex(text, r"(?m)^[^#]*env -i")            # env -i NAME=value puts the key in argv
        self.assertNotRegex(text, r'CRM_LOAD_API_KEY="\$')       # never expanded onto a command line
        self.assertIn("export PATH LANG CRM_LOAD_HOST CRM_LOAD_PORT CRM_LOAD_API_KEY", text)
        self.assertNotRegex(text, r"(?m)^\s*(\.|source)\s")       # the env file is parsed, never sourced

    def test_bash_n(self):
        self.assertEqual(subprocess.run(["bash", "-n", SCRIPT]).returncode, 0)

    def test_non_root_refused(self):
        if os.geteuid() == 0:
            self.skipTest("running as root")
        res = subprocess.run(["bash", SCRIPT, "dev", "/srv/CRM/runtime/migrate/snapshots/x", "/nonexistent/o"],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 2)
        self.assertIn("must be run as root", res.stderr)


class TestLoadShGuards(LoadShBase):
    def test_dev_synthetic_passes_every_guard_and_runs_crm_load(self):
        out = self.out()
        res = self.run_sh("dev", self.synthetic, out)
        self.assertEqual(res.returncode, 4, res.stderr)                # transport: nothing listens
        self.assertIn("code=connection_failed", res.stderr)
        self.assertEqual(stat.S_IMODE(os.stat(out).st_mode), 0o700)
        for name in os.listdir(out):
            self.assertEqual(stat.S_IMODE(os.stat(os.path.join(out, name)).st_mode), 0o600, name)

    def test_beta_real_passes_every_guard(self):
        res = self.run_sh("--reconciliation", self.rec_for(self.real), "beta", self.real, self.out())
        self.assertEqual(res.returncode, 4, res.stderr)
        self.assertIn("code=connection_failed", res.stderr)

    def test_dev_refuses_real_and_beta_refuses_synthetic(self):
        self.assertRefused(self.run_sh("dev", self.real, self.out("a")), "dev takes only", self.out("a"))
        self.assertRefused(self.run_sh("--reconciliation", self.rec_for(self.synthetic), "beta", self.synthetic,
                                       self.out("b")), "beta refuses anything under a *-selftest", self.out("b"))
        parent = os.path.dirname(self.synthetic)
        self.assertRefused(self.run_sh("--reconciliation", self.rec_for(self.real), "beta", parent, self.out("c")),
                           "beta refuses", self.out("c"))
        self.assertRefused(self.run_sh("dev", parent, self.out("d")), "dev takes only", self.out("d"))

    def test_dev_parent_mode_checked_by_crm_load(self):
        # the shell guards pass; crm-load refuses because the parent manifest is not mode selftest
        parent = os.path.dirname(self.synthetic)
        unseal(parent)
        fx.write_selftest_manifest(parent)
        path = os.path.join(parent, "manifest.json")
        with open(path) as fh:
            doc = fh.read().replace('"mode": "selftest"', '"mode": "extract"')
        with open(path, "w") as fh:
            fh.write(doc)
        seal(parent)
        res = self.run_sh("dev", self.synthetic, self.out())
        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertIn("code=target_dev_requires_synthetic", res.stderr)
        self.assertFalse(os.path.exists(self.out()))

    def test_beta_marker_refused_by_crm_load(self):
        marked = write_snapshot(os.path.join(self.base, "marked"), data=fx.org(), synthetic=False)
        seal(marked)
        res = self.run_sh("--reconciliation", self.rec_for(marked), "beta", marked, self.out())
        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertIn("code=synthetic_content_in_beta", res.stderr)

    def test_api_key_only_in_the_environment(self):
        stub_repo = os.path.join(self.tmp, "stubrepo")
        os.makedirs(os.path.join(stub_repo, "load", "bin"))
        with open(os.path.join(stub_repo, "load", "bin", "crm-load.py"), "w") as fh:
            fh.write("import os, sys\n"
                     f"key = {KEY!r}\n"
                     "sys.stderr.write('ENV=' + ','.join(sorted(os.environ)) + '\\n')\n"
                     "sys.stderr.write('KEY_OK=' + str(os.environ.get('CRM_LOAD_API_KEY') == key) + '\\n')\n"
                     "args = open('/proc/%d/cmdline' % os.getppid() if False else '/proc/self/cmdline', 'rb').read()\n"
                     "sys.stderr.write('ARGV_HAS_KEY=' + str(key.encode() in args) + '\\n')\n")
        with open(self.script) as fh:
            text = fh.read()
        text = re.sub(r"(?m)^REPO_DIR=.*$", f"REPO_DIR={stub_repo}", text, count=1)
        script = os.path.join(self.tmp, "load-stub.sh")
        with open(script, "w") as fh:
            fh.write(text)
        res = self.run_sh("dev", self.synthetic, self.out(), script=script)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("KEY_OK=True", res.stderr)
        self.assertIn("ARGV_HAS_KEY=False", res.stderr)
        env = res.stderr.split("ENV=", 1)[1].splitlines()[0].split(",")
        self.assertEqual(set(env) - {"SHLVL"}, {"CRM_LOAD_API_KEY", "CRM_LOAD_HOST", "CRM_LOAD_PORT", "LANG", "PATH"})

    def test_target_and_arguments(self):
        for args in ((), ("dev",), ("dev", self.synthetic), ("prod", self.synthetic, self.out()),
                     ("", self.synthetic, self.out()), ("dev", self.synthetic, self.out(), "extra")):
            with self.subTest(args=args):
                self.assertRefused(self.run_sh(*args), "", self.out())

    def test_snapshot_location(self):
        parent = os.path.dirname(self.synthetic)
        other = os.path.join(self.tmp, "elsewhere-selftest", "run-1")
        os.makedirs(other, mode=0o700)
        os.chmod(os.path.dirname(other), 0o700)
        deeper = os.path.join(self.base, "deeper")
        os.makedirs(os.path.join(deeper, "x-selftest", "run-1"), mode=0o700)
        os.chmod(deeper, 0o700)
        os.chmod(os.path.join(deeper, "x-selftest"), 0o700)
        link = os.path.join(self.base, "link-selftest")
        os.symlink(parent, link)
        for snap, frag in ((other, "directly under"), (os.path.join(deeper, "x-selftest", "run-1"), "directly under"),
                           (os.path.join(self.synthetic, "objects"), "dev takes only"),
                           (os.path.join(parent, "run-3"), "dev takes only"),
                           (os.path.join(link, "run-1"), "not a directory"),
                           (os.path.join(self.base, "synth-selftest", "..", "synth-selftest", "run-1"), "not canonical"),
                           ("relative/path", "absolute"),
                           (os.path.join(self.base, "missing-selftest", "run-1"), "not a directory")):
            with self.subTest(snap=snap):
                self.assertRefused(self.run_sh("dev", snap, self.out()), frag, self.out())
        unseal(parent)
        os.rename(self.synthetic, os.path.join(parent, "real-run"))
        os.symlink(os.path.join(parent, "real-run"), self.synthetic)
        self.assertRefused(self.run_sh("dev", self.synthetic, self.out()), "sealed", self.out())
        rec = self.rec_for(self.real)
        for snap, frag in ((os.path.join(self.base, "plain"), "beta takes only"),
                           (os.path.join(self.base, "a", "b-extract"), "directly under")):
            os.makedirs(snap, mode=0o700, exist_ok=True)
            os.chmod(os.path.dirname(snap), 0o700)
            with self.subTest(snap=snap):
                self.assertRefused(self.run_sh("--reconciliation", rec, "beta", snap, self.out()), frag, self.out())

    def test_snapshot_must_be_sealed(self):
        parent = os.path.dirname(self.synthetic)
        cases = (
            ("../manifest.json", 0o600),
            ("../run-2", 0o750),
            ("..", 0o755),
            ("objects/Account.jsonl.gz", 0o600),
            ("objects/Account.jsonl.gz", 0o440),
            ("manifest.json", 0o644),
            ("objects", 0o750),
            ("", 0o755),
        )
        for rel, mode in cases:
            with self.subTest(rel=rel, mode=oct(mode)):
                path = os.path.join(self.synthetic, rel)
                old = stat.S_IMODE(os.stat(path).st_mode)
                os.chmod(path, mode)
                try:
                    self.assertRefused(self.run_sh("dev", self.synthetic, self.out()), "sealed", self.out())
                finally:
                    os.chmod(path, old)
        os.chmod(self.synthetic, 0o700)
        os.chmod(os.path.join(self.synthetic, "objects"), 0o700)
        os.symlink("/etc/hostname", os.path.join(self.synthetic, "objects", "planted"))
        self.assertRefused(self.run_sh("dev", self.synthetic, self.out()), "sealed", self.out())

    def test_snapshot_base_must_be_0700(self):
        os.chmod(self.base, 0o755)
        self.assertRefused(self.run_sh("dev", self.synthetic, self.out()), "0700", self.out())

    def test_output_directory(self):
        existing = self.out("exists")
        os.mkdir(existing, 0o700)
        self.assertRefused(self.run_sh("dev", self.synthetic, existing), "already exists")
        os.symlink("/nonexistent", self.out("dangling"))
        self.assertRefused(self.run_sh("dev", self.synthetic, self.out("dangling")), "already exists")
        self.assertRefused(self.run_sh("dev", self.synthetic, "rel/out"), "absolute")
        self.assertRefused(self.run_sh("dev", self.synthetic, os.path.join(self.tmp, "nope", "o")),
                           "parent is not a directory")
        open_parent = os.path.join(self.tmp, "open")
        os.mkdir(open_parent, 0o755)
        os.chmod(open_parent, 0o755)
        self.assertRefused(self.run_sh("dev", self.synthetic, os.path.join(open_parent, "o")), "0700")
        under_base = os.path.join(self.base, "o")
        self.assertRefused(self.run_sh("dev", self.synthetic, under_base), "must not be under", under_base)
        unseal(os.path.dirname(self.synthetic))
        inside = os.path.join(self.synthetic, "out")
        res = self.run_sh("dev", self.synthetic, inside)
        self.assertRefused(res, "sealed")                    # an unsealed snapshot is refused first
        self.assertFalse(os.path.exists(inside))

    def test_env_file_rules(self):
        good = ["CRM_LOAD_HOST=127.0.0.1", f"CRM_LOAD_PORT={self.port}", f"CRM_LOAD_API_KEY={KEY}"]
        cases = (
            (None, 0o640, "0600"),
            (None, 0o644, "0600"),
            (good[:2], 0o600, "CRM_LOAD_API_KEY missing"),
            (good[1:], 0o600, "CRM_LOAD_HOST missing"),
            (["CRM_LOAD_HOST=localhost"] + good[1:], 0o600, "must be 127.0.0.1"),
            (good[:1] + ["CRM_LOAD_PORT=80x"] + good[2:], 0o600, "must be a number"),
            (good + ["CRM_LOAD_HOST=127.0.0.1"], 0o600, "assigned twice"),
            (good + ["PATH=/tmp"], 0o600, "unexpected variable"),
            (good + ["$(touch /tmp/x)"], 0o600, "malformed line"),
        )
        for lines, mode, frag in cases:
            with self.subTest(frag=frag, mode=oct(mode)):
                self.write_env("dev", lines, mode)
                self.assertRefused(self.run_sh("dev", self.synthetic, self.out()), frag, self.out())
        os.remove(os.path.join(self.runtime, "dev", "load.env"))
        self.assertRefused(self.run_sh("dev", self.synthetic, self.out()), "env file missing", self.out())

    def test_env_file_is_per_target(self):
        os.remove(os.path.join(self.runtime, "beta", "load.env"))
        self.assertRefused(self.run_sh("--reconciliation", self.rec_for(self.real), "beta", self.real, self.out()),
                           "env file missing", self.out())
        res = self.run_sh("dev", self.synthetic, self.out())
        self.assertEqual(res.returncode, 4, res.stderr)


DRIFT_URL = "https://github.com/infosec-estateresearch/CRM/issues/9#issuecomment-123456"


class TestLoadShLayout(LoadShBase):
    def test_legacy_layout_passes_every_guard(self):
        legacy = self.snapshot("legacy", synthetic=False, layout="legacy")
        res = self.run_sh("--reconciliation", self.rec_for(legacy), "beta", legacy, self.out())
        self.assertEqual(res.returncode, 4, res.stderr)
        self.assertIn("code=connection_failed", res.stderr)
        synth = self.snapshot("legacy-synth", synthetic=True, layout="legacy")
        res = self.run_sh("dev", synth, self.out("o2"))
        self.assertEqual(res.returncode, 4, res.stderr)

    def test_layout_refusals(self):
        both = self.snapshot("both", synthetic=False, layout="legacy")
        unseal(both)
        shutil.copy(os.path.join(both, "run", "manifest.json"), os.path.join(both, "manifest.json"))
        seal(both)
        self.assertRefused(self.run_sh("beta", both, self.out()), "ambiguous", self.out())
        flat_run = self.snapshot("flatrun", synthetic=False)
        os.chmod(flat_run, 0o700)
        os.mkdir(os.path.join(flat_run, "run"), 0o700)
        os.chmod(os.path.join(flat_run, "run"), 0o700)
        self.assertRefused(self.run_sh("beta", flat_run, self.out()), "ambiguous", self.out())
        extra = self.snapshot("extra", synthetic=False, layout="legacy")
        os.mkdir(os.path.join(extra, "other"), 0o700)
        os.chmod(os.path.join(extra, "other"), 0o700)
        self.assertRefused(self.run_sh("beta", extra, self.out()), "layout unknown", self.out())
        no_manifest = self.snapshot("nomanifest", synthetic=False, layout="legacy")
        os.chmod(os.path.join(no_manifest, "run"), 0o700)
        os.remove(os.path.join(no_manifest, "run", "manifest.json"))
        self.assertRefused(self.run_sh("beta", no_manifest, self.out()), "no manifest.json", self.out())
        only_run = self.snapshot("onlyrun", synthetic=False, layout="legacy")
        shutil.rmtree(os.path.join(only_run, "input"))
        self.assertRefused(self.run_sh("beta", only_run, self.out()), "layout unknown", self.out())


class TestLoadShOptions(LoadShBase):
    def test_accept_drift_passed_through(self):
        drift = self.snapshot("drift", synthetic=False, status="RECONCILED_WITH_DRIFT")
        res = self.run_sh("--accept-drift", DRIFT_URL, "--reconciliation", self.rec_for(drift), "beta", drift,
                          self.out())
        self.assertEqual(res.returncode, 4, res.stderr)              # gate accepted it
        self.assertIn("code=connection_failed", res.stderr)

    def test_accept_drift_required_only_for_drift(self):
        drift = self.snapshot("drift", synthetic=False, status="RECONCILED_WITH_DRIFT")
        res = self.run_sh("--reconciliation", self.rec_for(drift), "beta", drift, self.out("a"))
        self.assertEqual(res.returncode, 3, res.stderr)
        self.assertIn("code=drift_not_accepted", res.stderr)
        self.assertFalse(os.path.exists(self.out("a")))
        res = self.run_sh("--accept-drift", DRIFT_URL, "--reconciliation", self.rec_for(self.real), "beta", self.real,
                          self.out("b"))
        self.assertEqual(res.returncode, 3, res.stderr)
        self.assertIn("code=accept_drift_not_applicable", res.stderr)
        self.assertFalse(os.path.exists(self.out("b")))

    def test_accept_drift_url_format(self):
        drift = self.snapshot("drift", synthetic=False, status="RECONCILED_WITH_DRIFT")
        for url in ("https://github.com/infosec-estateresearch/CRM/issues/9#issuecomment-",
                    "https://github.com/infosec-estateresearch/CRM/issues/8#issuecomment-1",
                    "http://github.com/infosec-estateresearch/CRM/issues/9#issuecomment-1",
                    "https://github.com/other/CRM/issues/9#issuecomment-1",
                    DRIFT_URL + "x", DRIFT_URL + "\n", " " + DRIFT_URL, "https://example.test/9#issuecomment-1", ""):
            with self.subTest(url=url):
                self.assertRefused(self.run_sh("--accept-drift", url, "beta", drift, self.out()),
                                   "Issue #9 comment URL", self.out())

    def test_option_rules(self):
        for args in (("--accept-drift", DRIFT_URL, "--accept-drift", DRIFT_URL, "beta", self.real, self.out()),
                     ("--resume", self.out("x"), "--resume", self.out("x"), "dev", self.synthetic, self.out()),
                     ("--bogus", "dev", self.synthetic, self.out()),
                     ("dev", self.synthetic, self.out(), "--accept-drift", DRIFT_URL),
                     ("--accept-drift",)):
            with self.subTest(args=args):
                self.assertRefused(self.run_sh(*args), "", self.out())

    def _interrupted_output(self):
        # nothing listens: crm-load writes run.json and progress.jsonl, then fails at the index
        first = self.out("first")
        res = self.run_sh("dev", self.synthetic, first)
        self.assertEqual(res.returncode, 4, res.stderr)
        self.assertEqual(sorted(os.listdir(first)), ["progress.jsonl", "run.json"])
        return first

    def test_resume_passes_through(self):
        first = self._interrupted_output()
        res = self.run_sh("--resume", first, "dev", self.synthetic, self.out("second"))
        self.assertEqual(res.returncode, 4, res.stderr)
        self.assertIn("resumed=true", res.stderr)
        self.assertTrue(os.path.isdir(self.out("second")))

    def test_phone_refusals_passes_through_and_is_guarded(self):
        good = self.out("refusals.json")
        with open(good, "w") as fh:
            fh.write("[]\n")
        os.chmod(good, 0o600)
        res = self.run_sh("--phone-refusals", good, "dev", self.synthetic, self.out("p1"))
        self.assertEqual(res.returncode, 4, res.stderr)              # reached crm-load (no server here)
        bad = self.out("bad.json")
        with open(bad, "w") as fh:
            fh.write('["not-a-hash"]\n')
        os.chmod(bad, 0o600)
        res = self.run_sh("--phone-refusals", bad, "dev", self.synthetic, self.out("p2"))
        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertIn("code=phone_refusals_invalid", res.stderr)
        # the parent must be root-owned 0700 (the --resume rule)
        loose = os.path.join(self.tmp, "loose")
        os.makedirs(loose)
        os.chmod(loose, 0o755)
        in_loose = os.path.join(loose, "refusals.json")
        with open(in_loose, "w") as fh:
            fh.write("[]\n")
        os.chmod(in_loose, 0o600)
        res = self.run_sh("--phone-refusals", in_loose, "dev", self.synthetic, self.out("p4"))
        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertIn("phone refusals parent must be root-owned 0700", res.stderr)
        self.assertFalse(os.path.exists(self.out("p4")))
        os.chmod(good, 0o644)
        for path, frag in (("relative.json", "absolute"), (self.out("none.json"), "not a regular file"),
                           (good, "0600")):
            with self.subTest(path=path):
                res = self.run_sh("--phone-refusals", path, "dev", self.synthetic, self.out("p3"))
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(frag, res.stderr)

    def test_resume_requires_same_snapshot_sha(self):
        first = self._interrupted_output()
        other = self.snapshot("synth2", synthetic=True, extra={"t_start": "2026-11-02T00:00:00Z"})
        res = self.run_sh("--resume", first, "dev", other, self.out("second"))
        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertIn("code=resume_snapshot_mismatch", res.stderr)
        self.assertFalse(os.path.exists(self.out("second")))

    def test_resume_directory_guards(self):
        first = self._interrupted_output()
        cases = [("relative/dir", "absolute"), (self.out("missing"), "not a directory"),
                 (first + "/../first", "not canonical"), (self.out("o1"), "already exists")]
        os.mkdir(self.out("o1"), 0o700)
        os.chmod(self.out("o1"), 0o700)
        for path, frag in cases:
            with self.subTest(path=path):
                out = self.out("o1") if frag == "already exists" else self.out("second")
                res = self.run_sh("--resume", path, "dev", self.synthetic, out)
                self.assertRefused(res, frag)
        os.rmdir(self.out("o1"))
        os.chmod(first, 0o755)
        self.assertRefused(self.run_sh("--resume", first, "dev", self.synthetic, self.out("s")), "sealed",
                           self.out("s"))
        os.chmod(first, 0o700)
        os.chmod(os.path.join(first, "run.json"), 0o644)
        self.assertRefused(self.run_sh("--resume", first, "dev", self.synthetic, self.out("s")), "sealed",
                           self.out("s"))
        os.chmod(os.path.join(first, "run.json"), 0o600)
        os.symlink("/etc/hostname", os.path.join(first, "planted"))
        self.assertRefused(self.run_sh("--resume", first, "dev", self.synthetic, self.out("s")), "sealed",
                           self.out("s"))

    def test_reconciliation_passes_through(self):
        rec = self.rec_for(self.synthetic)
        res = self.run_sh("--reconciliation", rec, "dev", self.synthetic, self.out())
        self.assertEqual(res.returncode, 4, res.stderr)
        self.assertIn("reconciliation=true", res.stderr)

    def test_reconciliation_optional_for_dev_required_for_beta(self):
        res = self.run_sh("dev", self.synthetic, self.out("a"))
        self.assertEqual(res.returncode, 4, res.stderr)
        self.assertIn("reconciliation=false", res.stderr)
        self.assertRefused(self.run_sh("beta", self.real, self.out("b")), "beta requires --reconciliation",
                           self.out("b"))

    def test_reconciliation_must_name_the_snapshot(self):
        for key, value in (("t_start", "2026-10-01T00:00:00Z"), ("contract_sha256", "1" * 64)):
            with self.subTest(key=key):
                rec = self.rec_for(self.real, **{key: value})
                res = self.run_sh("--reconciliation", rec, "beta", self.real, self.out())
                self.assertEqual(res.returncode, 3, res.stderr)
                self.assertIn("code=reconciliation_snapshot_mismatch", res.stderr)
                self.assertFalse(os.path.exists(self.out()))

    def test_reconciliation_guards(self):
        rec = self.rec_for(self.synthetic)
        os.chmod(os.path.join(rec, "report", "manifest.json"), 0o600)
        self.assertRefused(self.run_sh("--reconciliation", rec, "dev", self.synthetic, self.out()),
                           "reconciliation run is not sealed", self.out())
        elsewhere = fx.write_reconcile_run(os.path.join(self.tmp, "elsewhere-reconcile"), {"objects": {}},
                                           snapshot=fx.snapshot_ref(self.synthetic))
        seal(elsewhere)
        self.assertRefused(self.run_sh("--reconciliation", elsewhere, "dev", self.synthetic, self.out()),
                           "directly under", self.out())
        self.assertRefused(self.run_sh("--reconciliation", os.path.dirname(self.synthetic), "dev", self.synthetic,
                                       self.out()), "must not be the snapshot", self.out())
        self.assertRefused(self.run_sh("--reconciliation", self.synthetic, "dev", self.synthetic, self.out()),
                           "directly under", self.out())
        res = self.run_sh("--reconciliation", self.real, "dev", self.synthetic, self.out())
        self.assertEqual(res.returncode, 3, res.stderr)              # crm-load: not a reconcile layout
        self.assertIn("code=reconciliation_layout_unknown", res.stderr)

if __name__ == "__main__":
    unittest.main()
