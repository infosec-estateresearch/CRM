"""CRM-007R unit tests: crm-beta / crm-dev isolation follow-up.

1. Backups are bound to their environment (TARGET marker, constant backup dir,
   crm-<target>-<stamp> directly under it); cross-environment restores are
   refused in both directions before any docker call. Dev only: a legacy
   unmarked backup needs --legacy-unmarked.
2. Provisioning is pinned to its target's own base URL.
3. The deploy root is constant and must be root-owned, not group/other-writable.
4. A deploy refuses to start without the provisioning and acceptance inputs.
5. Beta Compose networks: only {}, driver bridge, internal true.

The round-3 reviewers' probes (probe_cross.py, probe_deployroot.py,
r5/allow_probe.py) are cases here. In-process only: fake docker, no network."""

import copy
import glob
import io
import json
import os
import shutil
import subprocess
import unittest
import unittest.mock

import test_beta as tb
import test_scripts as ts
from test_beta import BIND, REPO, SCRIPTS, ca, make_backup, read

import provision_access  # noqa: E402  (scripts/ is on sys.path via test_beta)
import provision_users  # noqa: E402

STAMP = "20261110T000000Z"
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


# --- 1. backups bound to their environment -----------------------------------

class TestBetaRestoreRefusesForeignBackups(tb.BetaStackEnv):
    """probe_cross.py: restore.sh beta with a crm-dev backup (and the reverse
    marker games) is refused before any docker call."""

    def setUp(self):
        super().setUp()
        for d in ("db", "data", "custom", "client/custom"):
            os.makedirs(os.path.join(self.runtime, d), exist_ok=True)
        self.backups = os.path.join(self.runtime, "backups")
        os.mkdir(self.backups, 0o700)
        self.stdin = os.path.join(self.tmp, "stdin.sql")
        res = self.run_beta("up.sh")  # renders the edge config, as in probe_cross.py
        self.assertEqual(res.returncode, 0, res.stderr)

    def restore(self, *args, extra=None):
        open(self.log, "w").close()
        return self.run_beta("restore.sh", *args,
                             extra={"FAKE_DOCKER_STDIN": self.stdin, **(extra or {})})

    def assert_refused(self, res, needle):
        self.assertNotEqual(res.returncode, 0, res.stdout)
        self.assertIn(needle, res.stderr)
        self.assertEqual(self.docker_calls(), [], "refused before any docker call")
        self.assertFalse(os.path.exists(self.stdin), "nothing piped into crm-db")
        self.assertFalse([n for n in os.listdir(self.runtime) if ".replaced-" in n])

    def dev_backup(self, **kw):
        parent = os.path.join(self.tmp, "runtime", "dev", "backups")
        os.makedirs(parent, exist_ok=True)
        return make_backup(parent, f"crm-dev-{STAMP}", **kw)

    def test_own_marked_backup_restores(self):
        backup = make_backup(self.backups, f"crm-beta-{STAMP}")
        res = self.restore(os.path.basename(backup))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("restore completed", res.stdout)
        self.assertTrue(all("-p crm-beta " in c for c in self.docker_calls()))

    def test_dev_backup_by_path_refused(self):  # probe_cross.py
        self.assert_refused(self.restore(self.dev_backup()), "named crm-beta-<UTC stamp>")

    def test_dev_backup_restoretest_refused(self):  # probe_cross.py (--restoretest)
        res = self.restore("--restoretest", self.dev_backup(), extra={
            "CRM_RESTORETEST_DIR": os.path.join(self.tmp, "runtime", "beta-restoretest")})
        self.assert_refused(res, "named crm-beta-<UTC stamp>")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "runtime", "beta-restoretest")))

    def test_dev_backup_copied_and_renamed_into_beta_backups_refused(self):
        src = self.dev_backup()
        dst = os.path.join(self.backups, f"crm-beta-{STAMP}")
        shutil.copytree(src, dst)
        self.assert_refused(self.restore(os.path.basename(dst)), "TARGET marker is not 'beta'")

    def test_marker_edited_without_rechecksumming_refused(self):
        backup = make_backup(self.backups, f"crm-beta-{STAMP}", marker="dev\n")
        with open(os.path.join(backup, "TARGET"), "w") as fh:
            fh.write("beta\n")
        self.assert_refused(self.restore(os.path.basename(backup)), "checksum mismatch")

    def test_unmarked_backup_refused_even_with_the_legacy_flag(self):
        backup = make_backup(self.backups, f"crm-beta-{STAMP}", marker=None)
        self.assert_refused(self.restore(os.path.basename(backup)), "no TARGET marker")
        res = self.restore("--legacy-unmarked", os.path.basename(backup))
        self.assertEqual(res.returncode, 2)
        self.assertIn("for dev only", res.stderr)
        self.assertEqual(self.docker_calls(), [])

    def test_marker_not_listed_in_sha256sums_refused(self):
        backup = make_backup(self.backups, f"crm-beta-{STAMP}", marker=None)
        with open(os.path.join(backup, "TARGET"), "w") as fh:
            fh.write("beta\n")
        self.assert_refused(self.restore(os.path.basename(backup)), "not a checksummed file")

    def test_marker_with_other_text_refused(self):
        for text in ("beta", "beta\n\n", "BETA\n", "dev\n", "beta dev\n"):
            with self.subTest(marker=text):
                backup = make_backup(self.backups, f"crm-beta-{STAMP}", marker=text)
                self.assert_refused(self.restore(os.path.basename(backup)), "TARGET marker")
                shutil.rmtree(backup)

    def test_location_and_name_rules(self):
        good = make_backup(self.backups, f"crm-beta-{STAMP}")
        nested = os.path.join(self.backups, "sub")
        os.mkdir(nested)
        cases = {
            "nested": (make_backup(nested, f"crm-beta-{STAMP}"), "directly under"),
            "outside": (make_backup(self.tmp, f"crm-beta-{STAMP}"), "directly under"),
            "bad name": (make_backup(self.backups, "crm-beta-latest", marker="beta\n"),
                         "named crm-beta-<UTC stamp>"),
        }
        link = os.path.join(self.backups, "crm-beta-20261111T000000Z")
        os.symlink(good, link)
        cases["symlink"] = (link, "symlink")
        # Last: it restores (a non-canonical spelling of the right place).
        cases["dotdot"] = (os.path.join(self.backups, "..", "backups", os.path.basename(good)), None)
        for label, (path, needle) in cases.items():
            with self.subTest(case=label):
                res = self.restore(path)
                if needle is None:  # a non-canonical spelling of the right place is fine
                    self.assertEqual(res.returncode, 0, res.stderr)
                    continue
                self.assert_refused(res, needle)

    def test_backup_writes_the_beta_marker(self):
        res = self.run_beta("backup.sh")
        self.assertEqual(res.returncode, 0, res.stderr)
        [name] = os.listdir(self.backups)
        self.assertRegex(name, r"^crm-beta-\d{8}T\d{6}Z$")
        self.assertEqual(read(os.path.join(self.backups, name, "TARGET")), "beta\n")
        self.assertRegex(read(os.path.join(self.backups, name, "SHA256SUMS")),
                         r"(?m)^[0-9a-f]{64}  TARGET$")

    def test_overridden_backup_dir_refused(self):
        other = os.path.join(self.tmp, "runtime", "dev", "backups")
        for script, args in (("backup.sh", ()), ("export.sh", ()),
                             ("restore.sh", (f"crm-beta-{STAMP}",))):
            with self.subTest(script=script):
                open(self.log, "w").close()
                res = self.run_beta(script, *args, extra={"CRM_BACKUP_DIR": other,
                                                          "CRM_BASE_URL": "http://127.0.0.1:8280"})
                self.assertEqual(res.returncode, 2, res.stdout)
                self.assertIn("unset CRM_BACKUP_DIR", res.stderr)
                self.assertEqual(self.docker_calls(), [])
                self.assertFalse(os.path.exists(other))


class TestDevRestoreRefusesForeignBackups(ts.ScriptEnv):
    """The reverse direction, and dev's legacy rule."""

    def setUp(self):
        super().setUp()
        self.backups = os.path.join(self.runtime, "backups")
        os.mkdir(self.backups)

    def restore(self, *args, extra=None):
        open(self.log, "w").close()
        return self.run_script("restore.sh", "dev", *args, extra_env=extra)

    def assert_refused(self, res, needle):
        self.assertNotEqual(res.returncode, 0, res.stdout)
        self.assertIn(needle, res.stderr)
        self.assertEqual(self.docker_calls(config=True), [], "refused before any docker call")
        self.assertFalse(os.path.exists(self.stdin))

    def test_beta_backup_by_path_refused(self):
        parent = os.path.join(self.tmp.name, "runtime", "beta", "backups")
        os.makedirs(parent)
        self.assert_refused(self.restore(make_backup(parent, f"crm-beta-{STAMP}")),
                            "named crm-dev-<UTC stamp>")

    def test_beta_backup_renamed_into_dev_backups_refused(self):
        backup = make_backup(self.backups, f"crm-dev-{STAMP}", marker="beta\n")
        self.assert_refused(self.restore(os.path.basename(backup)), "TARGET marker is not 'dev'")
        self.assert_refused(self.restore("--legacy-unmarked", os.path.basename(backup)),
                            "TARGET marker is not 'dev'")

    def test_legacy_unmarked_dev_backup_needs_the_flag(self):
        backup = make_backup(self.backups, f"crm-dev-{STAMP}", marker=None)
        self.assert_refused(self.restore(os.path.basename(backup)), "--legacy-unmarked")
        res = self.restore("--legacy-unmarked", os.path.basename(backup))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("legacy dev backup with no TARGET marker", res.stderr)
        self.assertIn("restore completed", res.stdout)

    def test_legacy_flag_still_needs_the_dev_backups_dir_and_name(self):
        outside = make_backup(os.path.join(self.tmp.name), f"crm-dev-{STAMP}", marker=None)
        self.assert_refused(self.restore("--legacy-unmarked", outside), "directly under")
        badname = make_backup(self.backups, "dev-backup-old", marker=None)
        self.assert_refused(self.restore("--legacy-unmarked", badname), "named crm-dev-<UTC stamp>")

    def test_backup_then_restore_round_trip_uses_the_marker(self):
        res = self.run_script("backup.sh", "dev")
        self.assertEqual(res.returncode, 0, res.stderr)
        [name] = os.listdir(self.backups)
        self.assertEqual(read(os.path.join(self.backups, name, "TARGET")), "dev\n")
        res = self.restore(name)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_overridden_backup_dir_refused(self):
        other = os.path.join(self.tmp.name, "elsewhere")
        for script, args in (("backup.sh", ()), ("export.sh", ()),
                             ("restore.sh", (f"crm-dev-{STAMP}",))):
            with self.subTest(script=script):
                open(self.log, "w").close()
                res = self.run_script(script, "dev", *args, extra_env={"CRM_BACKUP_DIR": other})
                self.assertEqual(res.returncode, 2, res.stdout)
                self.assertIn("unset CRM_BACKUP_DIR", res.stderr)
                self.assertEqual(self.docker_calls(config=True), [])
                self.assertFalse(os.path.exists(other))
        # The constant itself, spelled out, is accepted.
        res = self.run_script("backup.sh", "dev", extra_env={"CRM_BACKUP_DIR": self.backups})
        self.assertEqual(res.returncode, 0, res.stderr)


# --- 2. provisioning pinned to its target -------------------------------------

class CountingTransport:
    def __init__(self):
        self.calls = []

    def request(self, method, url, headers, body):
        self.calls.append((method, url))
        if method == "GET":
            return 200, json.dumps({"total": 0, "list": []}).encode()
        return 200, json.dumps({"id": "x1", "apiKey": "unit-key"}).encode()


class TestProvisionPinnedUrl(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        for target, text in (("dev", f"CRM_BIND_IP={BIND}\n"), ("beta", "CRM_BETA_APP_PORT=8280\n")):
            os.makedirs(os.path.join(self.root, target))
            with open(os.path.join(self.root, target, "env"), "w") as fh:
                fh.write(text)
        self.dev_url = f"http://{BIND}:8180"
        self.beta_url = "http://127.0.0.1:8280"

    def env(self, target, url, **over):
        e = {"CRM_ADMIN_USERNAME": "admin", "CRM_ADMIN_PASSWORD": "pw", "CRM_BASE_URL": url}
        if target == "beta":
            e["CRM_TEST_ROOT"] = self.root
        else:
            e["CRM_RUNTIME_DIR"] = os.path.join(self.root, "dev")
        e.update(over)
        return {k: v for k, v in e.items() if v is not None}

    def run_both(self, target, url, **over):
        """[(rc, stderr, calls)] for provision_access and provision_users."""
        out = []
        for main, argv in ((provision_access.main,
                            [target, "--key-file", os.path.join(self.root, "k.env")]),
                           (provision_users.main, [target, "--report-never-logged-in"])):
            t, err = CountingTransport(), io.StringIO()
            with unittest.mock.patch("sys.stderr", err), \
                    unittest.mock.patch("sys.stdout", io.StringIO()):
                rc = main(argv, environ=self.env(target, url, **over), transport=t)
            out.append((rc, err.getvalue(), t.calls))
        return out

    def assert_refused(self, results):
        for rc, err, calls in results:
            self.assertEqual(rc, 2, err)
            self.assertIn("refusing to run", err)
            self.assertEqual(calls, [], "no HTTP request")
            self.assertNotIn(BIND, err, "the bind address is not printed")
        self.assertFalse(os.path.exists(os.path.join(self.root, "k.env")))

    def test_own_url_accepted(self):
        for target, url in (("dev", self.dev_url), ("beta", self.beta_url)):
            with self.subTest(target=target):
                for rc, err, calls in self.run_both(target, url):
                    self.assertNotEqual(rc, 2, err)
                    self.assertTrue(calls)
                    self.assertTrue(all(u.startswith(url + "/") for _, u in calls))
                if os.path.exists(os.path.join(self.root, "k.env")):
                    os.unlink(os.path.join(self.root, "k.env"))

    def test_beta_with_a_dev_url_refused(self):  # probe_cross.py ProbeProvision
        for url in (self.dev_url, "http://127.0.0.1:8180", f"http://{BIND}:8280"):
            with self.subTest(url=url):
                self.assert_refused(self.run_both("beta", url))

    def test_beta_without_the_test_seam_uses_the_real_runtime_and_refuses(self):
        # The probe's environment: no runtime seam, so /srv/CRM/runtime/beta/env
        # is the file read; unreadable here, it refuses.
        self.assert_refused(self.run_both("beta", self.beta_url, CRM_TEST_ROOT=None))

    def test_dev_with_a_beta_url_refused(self):
        for url in (self.beta_url, f"http://{BIND}:8280", f"http://{BIND}:8181",
                    "http://127.0.0.1:8180", f"http://{BIND}:8180/", f"https://{BIND}:8180", ""):
            with self.subTest(url=url):
                self.assert_refused(self.run_both("dev", url))

    def test_target_env_file_rules(self):
        cases = {
            "dev runtime named beta": ("dev", self.dev_url,
                                       {"CRM_RUNTIME_DIR": os.path.join(self.root, "beta")}),
            "dev env file elsewhere": ("dev", self.dev_url, {"CRM_ENV_FILE": "/etc/x"}),
            "beta runtime override": ("beta", self.beta_url,
                                      {"CRM_RUNTIME_DIR": os.path.join(self.root, "dev")}),
        }
        for label, (target, url, over) in cases.items():
            with self.subTest(case=label):
                self.assert_refused(self.run_both(target, url, **over))
        with open(os.path.join(self.root, "beta", "env"), "a") as fh:
            fh.write("CRM_BETA_APP_PORT=8281\n")
        self.assert_refused(self.run_both("beta", self.beta_url))

    def test_pinned_base_url_unit(self):
        self.assertEqual(ca.pinned_base_url("beta", {"CRM_TEST_ROOT": self.root}),
                         (self.beta_url, None))
        self.assertEqual(ca.pinned_base_url("dev", {"CRM_RUNTIME_DIR": os.path.join(self.root, "dev")}),
                         (self.dev_url, None))
        for port in ("80", "99999", "08280", '"8280"', ""):
            with self.subTest(port=port):
                with open(os.path.join(self.root, "beta", "env"), "w") as fh:
                    fh.write(f"CRM_BETA_APP_PORT={port}\n")
                url, why = ca.pinned_base_url("beta", {"CRM_TEST_ROOT": self.root})
                if port == '"8280"':  # read_env_values unquotes, as check_access does
                    self.assertEqual(url, self.beta_url)
                    continue
                self.assertIsNone(url)
                self.assertTrue(why)
        with open(os.path.join(self.root, "dev", "env"), "w") as fh:
            fh.write("CRM_BIND_IP=127.0.0.1\n")
        url, why = ca.pinned_base_url("dev", {"CRM_RUNTIME_DIR": os.path.join(self.root, "dev")})
        self.assertIsNone(url)
        self.assertIn("loopback", why)


# --- 3 and 4. deploy root and mandatory inputs --------------------------------

class TestDeployRootAndInputs(tb.TestDeployRelease):
    """Reuses TestDeployRelease's bundle; its own tests are not re-run here."""

    def droot(self):
        return os.path.join(self.tmp, "runtime", "deploy")

    def test_deploy_root_override_refused(self):  # probe_deployroot.py
        outside = os.path.join(self.tmp, "outside-tmp", "deploy")
        for value in (outside, "/srv/CRM/deploy", self.droot() + "/"):
            with self.subTest(root=value):
                res = self.deploy(env={"CRM_DEPLOY_ROOT": value})
                self.assertNotEqual(res.returncode, 0)
                self.assertIn("the deploy root is", res.stderr)
                self.assertFalse(os.path.exists(os.path.dirname(outside)))
                self.assertFalse(os.path.exists(self.droot()))
                self.assertEqual(self.docker_calls(), [])
        res = self.deploy(env={"CRM_DEPLOY_ROOT": self.droot()})  # the pinned value itself
        self.assertNotIn("the deploy root is", res.stderr)

    def test_deploy_root_must_be_root_owned_and_not_writable(self):
        os.makedirs(self.droot())
        for mode in (0o775, 0o757, 0o777):
            with self.subTest(mode=oct(mode)):
                os.chmod(self.droot(), mode)
                res = self.deploy()
                self.assertNotEqual(res.returncode, 0)
                self.assertIn("group- or other-writable", res.stderr)
                self.assertEqual(os.listdir(self.droot()), [])
        os.chmod(self.droot(), 0o755)
        res = self.deploy(root=False)  # not root-owned (fake stat plays root only under runtime/)
        self.assertNotEqual(res.returncode, 0)

    def test_upgrade_refuses_a_writable_existing_release_before_verify_tree(self):
        res = self.deploy()
        self.assertTrue(os.path.isdir(self.deploy_dir()), res.stderr)
        os.chmod(self.deploy_dir(), 0o775)
        self.addCleanup(self.make_writable)
        res = self.deploy("--upgrade")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn(f"{self.deploy_dir()} is group- or other-writable", res.stderr)
        self.assertNotIn("differs from the bundle", res.stderr)

    def test_missing_inputs_refuse_before_step_1(self):
        for missing in ("CRM_ADMIN_USERNAME", "CRM_ADMIN_PASSWORD", "CRM_PROVISION_KEY_FILE"):
            with self.subTest(missing=missing):
                env = dict(tb.DEPLOY_INPUTS(self.tmp))
                env[missing] = ""
                res = self.deploy(env=env)
                self.assert_nothing_done(res)
                self.assertIn(f"{missing} is required", res.stderr)
        res = self.deploy("--upgrade", env={"CRM_BETA_SAFE_KEY_FILE": os.path.join(self.tmp, "nope")})
        self.assert_nothing_done(res)
        self.assertIn("required with --upgrade", res.stderr)


for _name in [n for n in dir(tb.TestDeployRelease) if n.startswith("test_")]:
    setattr(TestDeployRootAndInputs, _name, None)


# --- 5. Compose network specs --------------------------------------------------

class TestBetaNetworkSpecs(unittest.TestCase):
    def base(self):
        with open(ca.BETA_COMPOSE_PATH) as fh:
            return json.load(fh)

    def with_net(self, spec):
        d = self.base()
        d["networks"]["crm-beta-net"] = spec
        return ca.check_beta_compose(d)

    def test_allowed_specs(self):
        for spec in (None, {}, {"driver": "bridge"}, {"internal": True},
                     {"driver": "bridge", "internal": True}):
            with self.subTest(spec=spec):
                self.assertEqual(self.with_net(spec), [])

    def test_refused_specs(self):  # r5/allow_probe.py
        for spec in ({"driver": "macvlan", "driver_opts": {"parent": "eth0"}},
                     {"driver": "bridge",
                      "driver_opts": {"com.docker.network.bridge.gateway_mode_ipv4": "routed"}},
                     {"driver": "bridge", "driver_opts": {}}, {"ipam": {}},
                     {"driver": "host"}, {"driver": "overlay"}, {"driver": "Bridge"},
                     {"internal": False}, {"internal": "true"}, {"attachable": True},
                     {"enable_ipv6": True}, {"labels": {}}, {"x-net": 1}):
            with self.subTest(spec=spec):
                self.assertNotEqual(self.with_net(spec), [])

    def test_broken_fixtures_are_refused(self):
        paths = sorted(glob.glob(os.path.join(FIXTURES, "beta_network_bad_*.json")))
        self.assertGreaterEqual(len(paths), 4)
        for path in paths:
            with self.subTest(fixture=os.path.basename(path)):
                with open(path) as fh:
                    errors = ca.check_beta_compose(json.load(fh))
                self.assertTrue(any("crm-beta-net" in e for e in errors), errors)

    def test_a_second_network_is_checked_too(self):
        d = self.base()
        d["networks"]["extra"] = {"driver": "macvlan"}
        self.assertNotEqual(ca.check_beta_compose(d), [])


if __name__ == "__main__":
    unittest.main()
