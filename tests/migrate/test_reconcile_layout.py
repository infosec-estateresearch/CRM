"""CRM-002-W: ``migrate.sh reconcile`` accepts both sealed snapshot layouts.

The real ``snapshot_root`` and ``cmd_reconcile`` functions are extracted from
``scripts/migrate.sh`` and run under bash against temporary snapshot trees. ``require``,
``new_run_dir``, ``compose_run``, ``finish``, ``chown`` and ``docker`` are stubs that record
what the wrapper would do. No root, no Docker, no network.
"""

import os
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

from . import SCRIPT_PATH

CUR = "20261110T120000Z-extract"
PREV = "20261109T120000Z-extract"

HARNESS = r"""
set -euo pipefail
umask 077
export LC_ALL=C
SNAPSHOTS={snapshots}
LOG={log}
RUN_DIR=""
RUN_UID=64021
RUN_GID=64021
die() {{ printf 'migrate.sh: refused: %s\n' "$*" >&2; exit 1; }}
usage() {{ printf 'usage\n' >&2; exit 2; }}
require() {{ printf 'require %s\n' "$*" >>"$LOG"; }}
docker() {{ :; }}
chown() {{ :; }}
new_run_dir() {{ RUN_DIR={run_dir}; mkdir -m 0700 -- "$RUN_DIR"; }}
compose_run() {{
    printf 'compose %s\n' "$*" >>"$LOG"
    (cd "$RUN_DIR/input" && find . -mindepth 1 | sort | sed 's/^/tree /') >>"$LOG"
}}
finish() {{ printf 'finish %s\n' "$*" >>"$LOG"; exit "$3"; }}
{functions}
cmd_reconcile "$@"
"""


def extract_function(text, name):
    m = re.search(r"^%s\(\) \{\n.*?^\}\n" % re.escape(name), text, re.M | re.S)
    if not m:
        raise AssertionError(f"function {name} not found in migrate.sh")
    return m.group(0)


def write(path, data="{}\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(data)


def make_cc(root):
    """Client-credentials layout: manifest.json at the top."""
    write(os.path.join(root, "manifest.json"), '{"layout": "cc"}\n')
    write(os.path.join(root, "objects", "Account.jsonl.gz"), "x\n")
    write(os.path.join(root, "extract.json"))


def make_legacy(root, waiver=True):
    """Legacy (soap-legacy) layout: run/manifest.json plus input/waiver.json."""
    write(os.path.join(root, "run", "manifest.json"), '{"layout": "legacy"}\n')
    write(os.path.join(root, "run", "objects", "Account.jsonl.gz"), "x\n")
    write(os.path.join(root, "run", "extract.json"))
    if waiver:
        write(os.path.join(root, "input", "waiver.json"), '{"waiver": true}\n')


class ReconcileLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SCRIPT_PATH, encoding="utf-8") as fh:
            cls.script = fh.read()
        cls.functions = extract_function(cls.script, "snapshot_root") + extract_function(cls.script, "cmd_reconcile")
        cls.bash = shutil.which("bash")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="crm-002-w-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.snapshots = os.path.join(self.tmp, "snapshots")
        os.mkdir(self.snapshots)
        self.log = os.path.join(self.tmp, "log")
        self.run_dir = os.path.join(self.snapshots, "20261110T130000Z-reconcile")

    def snap(self, sid):
        path = os.path.join(self.snapshots, sid)
        os.makedirs(path, exist_ok=True)
        return path

    def run_reconcile(self, *ids):
        harness = HARNESS.format(snapshots=shlex.quote(self.snapshots), log=shlex.quote(self.log),
                                 run_dir=shlex.quote(self.run_dir), functions=self.functions)
        proc = subprocess.run([self.bash, "-c", harness, "migrate.sh", *ids], capture_output=True,
                              text=True, timeout=30, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})
        log = []
        if os.path.exists(self.log):
            with open(self.log, encoding="utf-8") as fh:
                log = fh.read().splitlines()
        return proc, log

    def assert_ran(self, proc, log):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(any(ln.startswith("compose crm-migrate-selftest reconcile") for ln in log), log)
        self.assertIn(f"finish {self.run_dir} {self.run_dir}/report 0", log)
        self.assertFalse(os.path.exists(os.path.join(self.run_dir, "input")), "input copy not removed")

    def assert_refused(self, proc, log, needle="refused"):
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(needle, proc.stderr)
        self.assertFalse(any(ln.startswith("compose") for ln in log), log)
        self.assertFalse(os.path.exists(self.run_dir), "run directory created for a refused input")

    @staticmethod
    def tree(log, which):
        return sorted(ln[len("tree ./" + which):] for ln in log if ln.startswith("tree ./" + which + "/"))

    EXPECTED_TREE = ["/extract.json", "/manifest.json", "/objects", "/objects/Account.jsonl.gz"]

    # ------------------------------------------------------------ accepted layouts
    def test_client_credentials_layout_reconciles(self):
        make_cc(self.snap(CUR))
        proc, log = self.run_reconcile(CUR)
        self.assert_ran(proc, log)
        self.assertIn(f"require verify-manifest {self.snapshots}/{CUR}", log)
        self.assertIn(f"require sealed {self.snapshots}/{CUR}", log)
        self.assertEqual(self.tree(log, "current"), self.EXPECTED_TREE)
        self.assertIn("compose crm-migrate-selftest reconcile --snapshot /out/input/current --out /out/report", log)

    def test_legacy_layout_reconciles_without_the_waiver(self):
        make_legacy(self.snap(CUR))
        proc, log = self.run_reconcile(CUR)
        self.assert_ran(proc, log)
        self.assertIn(f"require verify-manifest {self.snapshots}/{CUR}/run", log)
        self.assertIn(f"require sealed {self.snapshots}/{CUR}", log)
        self.assertEqual(self.tree(log, "current"), self.EXPECTED_TREE)
        self.assertFalse([ln for ln in log if "waiver" in ln], log)

    def test_legacy_layout_without_input_reconciles(self):
        make_legacy(self.snap(CUR), waiver=False)
        proc, log = self.run_reconcile(CUR)
        self.assert_ran(proc, log)
        self.assertIn(f"require verify-manifest {self.snapshots}/{CUR}/run", log)
        self.assertEqual(self.tree(log, "current"), self.EXPECTED_TREE)

    def test_previous_snapshot_with_either_layout(self):
        for cur_make, prev_make in ((make_legacy, make_cc), (make_cc, make_legacy),
                                    (make_legacy, make_legacy), (make_cc, make_cc)):
            with self.subTest(current=cur_make.__name__, previous=prev_make.__name__):
                shutil.rmtree(self.snapshots)
                os.mkdir(self.snapshots)
                if os.path.exists(self.log):
                    os.unlink(self.log)
                cur_make(self.snap(CUR))
                prev_make(self.snap(PREV))
                proc, log = self.run_reconcile(CUR, PREV)
                self.assert_ran(proc, log)
                self.assertIn("compose crm-migrate-selftest reconcile --snapshot /out/input/current "
                              "--out /out/report --previous /out/input/previous", log)
                self.assertEqual(self.tree(log, "current"), self.EXPECTED_TREE)
                self.assertEqual(self.tree(log, "previous"), self.EXPECTED_TREE)
                suffix = {make_cc: "", make_legacy: "/run"}
                self.assertIn(f"require verify-manifest {self.snapshots}/{CUR}{suffix[cur_make]}", log)
                self.assertIn(f"require verify-manifest {self.snapshots}/{PREV}{suffix[prev_make]}", log)
                self.assertFalse([ln for ln in log if "waiver" in ln], log)

    # ------------------------------------------------------------ refused layouts
    def test_refused_layouts(self):
        def both(d):
            make_legacy(d)
            write(os.path.join(d, "manifest.json"))

        def both_without_input(d):
            make_cc(d)
            write(os.path.join(d, "run", "manifest.json"))

        def cc_with_input(d):
            make_cc(d)
            write(os.path.join(d, "input", "waiver.json"))

        def cc_with_empty_run(d):
            make_cc(d)
            os.mkdir(os.path.join(d, "run"))

        def legacy_extra_file(d):
            make_legacy(d)
            write(os.path.join(d, "notes.txt"))

        def legacy_extra_hidden(d):
            make_legacy(d)
            write(os.path.join(d, ".extra"))

        def legacy_extra_dir(d):
            make_legacy(d)
            os.mkdir(os.path.join(d, "objects"))

        def legacy_missing_manifest(d):
            make_legacy(d)
            os.unlink(os.path.join(d, "run", "manifest.json"))

        def input_only(d):
            write(os.path.join(d, "input", "waiver.json"))

        def empty(d):
            pass

        def objects_without_manifest(d):
            make_cc(d)
            os.unlink(os.path.join(d, "manifest.json"))

        def run_is_file(d):
            write(os.path.join(d, "run"))

        def run_is_symlink(d):
            other = os.path.join(self.tmp, "elsewhere")
            make_legacy(other, waiver=False)
            os.symlink(os.path.join(other, "run"), os.path.join(d, "run"))

        def run_manifest_is_dir(d):
            make_legacy(d)
            os.unlink(os.path.join(d, "run", "manifest.json"))
            os.mkdir(os.path.join(d, "run", "manifest.json"))

        def run_manifest_is_symlink(d):
            make_legacy(d)
            os.unlink(os.path.join(d, "run", "manifest.json"))
            os.symlink(os.path.join(d, "run", "extract.json"), os.path.join(d, "run", "manifest.json"))

        def top_manifest_is_symlink(d):
            make_cc(d)
            os.unlink(os.path.join(d, "manifest.json"))
            os.symlink(os.path.join(d, "extract.json"), os.path.join(d, "manifest.json"))

        def input_is_file(d):
            make_legacy(d, waiver=False)
            write(os.path.join(d, "input"))

        def input_is_symlink(d):
            make_legacy(d, waiver=False)
            os.symlink(os.path.join(d, "run"), os.path.join(d, "input"))

        cases = [both, both_without_input, cc_with_input, cc_with_empty_run, legacy_extra_file,
                 legacy_extra_hidden, legacy_extra_dir, legacy_missing_manifest, input_only, empty,
                 objects_without_manifest, run_is_file, run_is_symlink, run_manifest_is_dir,
                 run_manifest_is_symlink, top_manifest_is_symlink, input_is_file, input_is_symlink]
        for build in cases:
            for position in ("current", "previous"):
                with self.subTest(build.__name__, position=position):
                    shutil.rmtree(self.snapshots)
                    os.mkdir(self.snapshots)
                    if os.path.exists(self.log):
                        os.unlink(self.log)
                    if position == "current":
                        build(self.snap(CUR))
                        make_cc(self.snap(PREV))
                    else:
                        make_legacy(self.snap(CUR))
                        build(self.snap(PREV))
                    proc, log = self.run_reconcile(CUR, PREV)
                    self.assert_refused(proc, log, "snapshot layout not recognised")

    def test_missing_snapshot_refused(self):
        proc, log = self.run_reconcile(CUR)
        self.assert_refused(proc, log, "snapshot not found")

    def test_run_id_rule_unchanged(self):
        for sid in ("20261110T120000Z-count", "20261110T120000Z-reconcile"):
            with self.subTest(sid):
                make_legacy(self.snap(sid))
                proc, log = self.run_reconcile(sid)
                self.assert_refused(proc, log, "reconcile inputs must be extract snapshots")
        make_cc(self.snap(CUR))
        proc, log = self.run_reconcile(CUR, "20261110T120000Z-count")
        self.assert_refused(proc, log, "reconcile inputs must be extract snapshots")

    def test_harness_detects_whole_snapshot_copy(self):
        # Non-vacuity guard for the harness itself: the pre-CRM-002-W behaviour (verify and
        # copy <id>) would be visible in the recorded tree.
        broken = self.functions.replace('cp -R -P -- "${roots[0]}"', 'cp -R -P -- "$SNAPSHOTS/$1"')
        self.assertNotEqual(broken, self.functions)
        make_legacy(self.snap(CUR))
        saved = self.functions
        try:
            type(self).functions = broken
            proc, log = self.run_reconcile(CUR)
        finally:
            type(self).functions = saved
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("tree ./current/input/waiver.json", log)
        self.assertNotEqual(self.tree(log, "current"), self.EXPECTED_TREE)


if __name__ == "__main__":
    unittest.main()
