"""Isolated-mode import (AC9): the mounted package runs; planted modules are never imported."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from . import MIGRATE

PLANT = """import pathlib
pathlib.Path({marker!r}).write_text("imported")
raise SystemExit("planted module imported")
"""


class IsolatedModeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="crm-migrate-iso-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.copy = os.path.join(self.tmp, "mount")
        shutil.copytree(MIGRATE, self.copy, ignore=shutil.ignore_patterns("__pycache__"))
        self.cwd = os.path.join(self.tmp, "unrelated-cwd")
        os.mkdir(self.cwd)
        self.markers = []
        for where in (self.cwd, os.path.join(self.copy, "bin")):
            pkg = os.path.join(where, "crm_migrate")
            os.mkdir(pkg)
            m1 = os.path.join(self.tmp, f"marker-pkg-{len(self.markers)}")
            with open(os.path.join(pkg, "__init__.py"), "w") as fh:
                fh.write(PLANT.format(marker=m1))
            m2 = os.path.join(self.tmp, f"marker-json-{len(self.markers)}")
            with open(os.path.join(where, "json.py"), "w") as fh:
                fh.write(PLANT.format(marker=m2))
            self.markers += [m1, m2]

    def run_entry(self, *flags, mode=("selftest", "--quick")):
        out = os.path.join(self.tmp, "out")
        env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": self.cwd, "PYTHONSTARTUP": os.path.join(self.cwd, "json.py")}
        proc = subprocess.run([sys.executable, *flags, os.path.join(self.copy, "bin", "crm-migrate.py"), *mode,
                               "--out", out], cwd=self.cwd, env=env, capture_output=True, text=True, timeout=120)
        return proc, out

    def test_selftest_runs_from_the_copy_and_ignores_planted_modules(self):
        proc, out = self.run_entry("-I", "-B")
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        for marker in self.markers:
            self.assertFalse(os.path.exists(marker), f"planted module imported: {marker}")
        with open(os.path.join(out, "selftest.json")) as fh:
            self.assertEqual(json.load(fh)["status"], "RECONCILED")
        self.assertIn("status=RECONCILED", proc.stdout)
        self.assertFalse(any("__pycache__" in d for d, _, _ in os.walk(self.copy)), "bytecode written")

    def test_refuses_without_isolated_flags(self):
        proc, _ = self.run_entry("-B")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("must be run as python -I -B", proc.stderr)
        for marker in self.markers:
            self.assertFalse(os.path.exists(marker))

    def test_library_path_is_first_and_unique(self):
        probe = os.path.join(self.copy, "lib", "crm_migrate", "probe_path.py")
        with open(probe, "w") as fh:
            fh.write("import sys\n")
        code = (
            "import runpy, sys\n"
            f"sys.argv = [{os.path.join(self.copy, 'bin', 'crm-migrate.py')!r}]\n"
            f"g = runpy.run_path(sys.argv[0], run_name='probe')\n"
            "g['_bootstrap']()\n"
            "print(sys.path[0])\n"
            f"print(sum(1 for p in sys.path if p == {os.path.join(self.copy, 'lib')!r}))\n"
        )
        proc = subprocess.run([sys.executable, "-I", "-B", "-c", code], cwd=self.cwd, capture_output=True,
                              text=True, timeout=60, env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        first, count = proc.stdout.split()
        self.assertEqual(first, os.path.join(self.copy, "lib"))
        self.assertEqual(count, "1")

    def test_missing_library_refused(self):
        shutil.rmtree(os.path.join(self.copy, "lib"))
        proc, _ = self.run_entry("-I", "-B")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("library directory not found", proc.stderr)
        for marker in self.markers:
            self.assertFalse(os.path.exists(marker))


if __name__ == "__main__":
    unittest.main()
