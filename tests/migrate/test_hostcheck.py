"""Pure host-check functions (AC10), tested without root."""

import io
import os
import stat
import unittest
from collections import namedtuple

from crm_migrate import hostcheck as hc

from . import ENV_EXAMPLE_PATH
from .fake_salesforce import TempDirMixin

St = namedtuple("St", "st_mode st_uid st_gid")
DIR, REG, LNK, FIFO = stat.S_IFDIR, stat.S_IFREG, stat.S_IFLNK, stat.S_IFIFO


def st(kind, mode, uid=0, gid=0):
    return St(kind | mode, uid, gid)


class HostcheckPureTest(unittest.TestCase):
    def test_target(self):
        self.assertEqual(hc.check_target("migrate"), [])
        for bad in ("dev", "prod", "", "migrate ", "../migrate"):
            self.assertTrue(hc.check_target(bad), bad)

    def test_runtime_path(self):
        self.assertEqual(hc.check_runtime_path("/srv/CRM/runtime/migrate"), [])
        self.assertTrue(hc.check_runtime_path("/srv/CRM/runtime/dev"))

    def test_root_private_dir(self):
        self.assertEqual(hc.check_root_private_dir(st(DIR, 0o700), "x"), [])
        for bad in (None, st(DIR, 0o755), st(DIR, 0o750), st(DIR, 0o700, uid=1000), st(DIR, 0o700, gid=1000),
                    st(LNK, 0o777), st(REG, 0o700), st(DIR, 0o1700)):
            with self.subTest(bad=bad):
                self.assertTrue(hc.check_root_private_dir(bad, "x"))

    def test_env_file_stat(self):
        self.assertEqual(hc.check_env_file_stat(st(REG, 0o600)), [])
        for bad in (None, st(REG, 0o640), st(REG, 0o644), st(REG, 0o600, uid=64021), st(LNK, 0o600),
                    st(DIR, 0o600)):
            with self.subTest(bad=bad):
                self.assertTrue(hc.check_env_file_stat(bad))

    def test_env_keys(self):
        names = ["A", "B"]
        self.assertEqual(hc.check_env_keys(hc.parse_env_keys("A=1\nB=2\n"), names), [])
        self.assertTrue(hc.check_env_keys(hc.parse_env_keys("A=1\n"), names))
        self.assertTrue(hc.check_env_keys(hc.parse_env_keys("A=1\nB=2\nC=3\n"), names))
        self.assertTrue(hc.check_env_keys(hc.parse_env_keys("A=1\nA=2\nB=3\n"), names))
        self.assertTrue(hc.check_env_keys(hc.parse_env_keys("A=1\ngarbage\nB=1\n"), names))
        errors = hc.check_env_keys(hc.parse_env_keys("A=supersecret\n"), names)
        self.assertNotIn("supersecret", " ".join(errors))

    def test_no_exported_secrets(self):
        names = ["CRM_SF_CLIENT_SECRET", "CRM_SF_ORIGIN"]
        self.assertEqual(hc.check_no_exported({"PATH": "/usr/bin"}, names), [])
        errors = hc.check_no_exported({"CRM_SF_CLIENT_SECRET": "value-not-shown"}, names)
        self.assertEqual(len(errors), 1)
        self.assertIn("CRM_SF_CLIENT_SECRET", errors[0])
        self.assertNotIn("value-not-shown", errors[0])
        self.assertTrue(hc.check_no_exported({"CRM_SF_ORIGIN": ""}, names))   # even empty is refused

    def test_uid_free(self):
        self.assertEqual(hc.check_uid_free("", ""), [])
        self.assertTrue(hc.check_uid_free("svc:x:64021:64021::/nonexistent:/usr/sbin/nologin", ""))
        self.assertTrue(hc.check_uid_free("", "svc:x:64021:"))

    def test_run_id(self):
        self.assertEqual(hc.check_run_id("20261110T170000Z-extract"), [])
        for bad in ("20261110T170000Z-other", "../20261110T170000Z-extract", "20261110T170000Z-extract/x",
                    "2026-11-10-extract", "", None):
            with self.subTest(bad=bad):
                self.assertTrue(hc.check_run_id(bad))

    def test_run_dir_absent_and_prepared(self):
        self.assertEqual(hc.check_run_dir_absent(None), [])
        self.assertTrue(hc.check_run_dir_absent(st(DIR, 0o700)))
        good = st(DIR, 0o700, 64021, 64021)
        self.assertEqual(hc.check_run_dir_prepared(good, []), [])
        for bad, entries in ((good, ["x"]), (st(DIR, 0o755, 64021, 64021), []), (st(DIR, 0o700), []),
                             (st(LNK, 0o700, 64021, 64021), []), (None, [])):
            with self.subTest(bad=bad):
                self.assertTrue(hc.check_run_dir_prepared(bad, entries))

    def test_sealed(self):
        sealed = [("", st(DIR, 0o700)), ("objects", st(DIR, 0o700)), ("manifest.json", st(REG, 0o400)),
                  ("objects/Account.jsonl.gz", st(REG, 0o400))]
        self.assertEqual(hc.check_sealed(sealed), [])
        broken = {
            "file still 64021": [("", st(DIR, 0o700)), ("a", st(REG, 0o400, 64021, 64021))],
            "dir still 64021": [("", st(DIR, 0o700, 64021, 64021))],
            "file writable": [("", st(DIR, 0o700)), ("a", st(REG, 0o600))],
            "file world readable": [("", st(DIR, 0o700)), ("a", st(REG, 0o444))],
            "dir open": [("", st(DIR, 0o755))],
            "symlink": [("", st(DIR, 0o700)), ("a", st(LNK, 0o777))],
            "fifo": [("", st(DIR, 0o700)), ("a", st(FIFO, 0o400))],
            "missing": [],
        }
        for name, entries in broken.items():
            with self.subTest(name):
                self.assertTrue(hc.check_sealed(entries))

    def test_manifest_problems(self):
        self.assertEqual(hc.check_manifest_problems([]), [])
        self.assertTrue(hc.check_manifest_problems(["checksum_mismatch"]))


class HostcheckCliTest(TempDirMixin, unittest.TestCase):
    def run_hc(self, *argv, environ=None):
        out = io.StringIO()
        rc = hc.main(list(argv), environ or {}, out)
        return rc, out.getvalue()

    def test_env_names_and_clean(self):
        rc, out = self.run_hc("env-names", ENV_EXAMPLE_PATH)
        self.assertEqual((rc, out.split()), (0, ["CRM_SF_ORIGIN", "CRM_SF_CLIENT_ID", "CRM_SF_CLIENT_SECRET",
                                                 "CRM_SF_API_VERSION"]))
        self.assertEqual(self.run_hc("env-clean", ENV_EXAMPLE_PATH)[0], 0)
        rc, out = self.run_hc("env-clean", ENV_EXAMPLE_PATH, environ={"CRM_SF_CLIENT_ID": "hidden-value"})
        self.assertEqual(rc, 1)
        self.assertNotIn("hidden-value", out)

    def test_runtime_and_env_file_absent_here(self):
        # This sandbox has no /srv/CRM/runtime/migrate: both checks must refuse.
        if os.path.exists(hc.RUNTIME):
            self.skipTest("runtime exists on this host")
        self.assertEqual(self.run_hc("runtime-dirs")[0], 1)
        self.assertEqual(self.run_hc("env-file", ENV_EXAMPLE_PATH)[0], 1)

    def test_sealed_refuses_non_root_tree(self):
        d = self.tmp()
        with open(os.path.join(d, "f"), "w") as fh:
            fh.write("x")
        os.chmod(os.path.join(d, "f"), 0o400)
        os.chmod(d, 0o700)
        rc, out = self.run_hc("sealed", d)
        if os.geteuid() != 0:
            self.assertEqual(rc, 1)
            self.assertIn("not owned root:root", out)

    def test_verify_manifest_ok_and_tampered(self):
        from crm_migrate.log import CountsLog
        from crm_migrate.manifest import OutputDir
        from crm_migrate.selftest import run_selftest
        from .fake_salesforce import contract
        d = os.path.join(self.tmp(), "st")
        run_selftest(contract(), OutputDir(d), CountsLog(), quick=True)
        self.assertEqual(self.run_hc("verify-manifest", d), (0, ""))
        with open(os.path.join(d, "run-1", "objects", "User.jsonl.gz"), "ab") as fh:
            fh.write(b"x")
        rc, out = self.run_hc("verify-manifest", d)
        self.assertEqual(rc, 1)
        self.assertIn("checksum_mismatch", out)
        self.assertEqual(self.run_hc("verify-manifest", self.tmp())[0], 1)     # no manifest

    def test_run_dir_checks(self):
        d = self.tmp()
        self.assertEqual(self.run_hc("run-dir-absent", os.path.join(d, "new"))[0], 0)
        self.assertEqual(self.run_hc("run-dir-absent", d)[0], 1)
        rc, out = self.run_hc("run-dir-prepared", d)
        if os.geteuid() != 64021:
            self.assertEqual(rc, 1)
            self.assertIn("64021", out)

    def test_unknown_check(self):
        self.assertEqual(self.run_hc("rm", "-rf", "/")[0], 1)
        self.assertEqual(self.run_hc()[0], 2)
        self.assertEqual(self.run_hc("uid-free", "", "")[0], 0)
        self.assertEqual(self.run_hc("target", "dev")[0], 1)


if __name__ == "__main__":
    unittest.main()
