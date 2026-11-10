"""CRM-007R unit tests: crm-beta / crm-dev isolation follow-up.

1. Backups are bound to their environment (TARGET marker, constant backup dir,
   crm-<target>-<stamp> directly under it); cross-environment restores are
   refused in both directions before any docker call. Dev only: a legacy
   unmarked backup needs --legacy-unmarked.
2. Provisioning is pinned to its target's own base URL.
3. The deploy root is constant and must be root-owned, not group/other-writable.
4. A deploy refuses to start without the provisioning and acceptance inputs.
5. Beta Compose networks: only {}, driver bridge, internal true; the
   restore-test compose gets the same network allowlist, a local volume only
   and no top-level secrets/configs.
6. export.sh / export_csv.py are bound to their target: output only a new
   export-<name> directly under the target's backup directory, base URL only
   the target's own.
7. --legacy-unmarked accepts only stamps before the cut-over 20261111T000000Z.
8. write_report refuses unless provisioning and acceptance both ran.

The reviewers' probes (probe_cross.py, probe_deployroot.py,
r5/allow_probe.py, probe_export.py, probe_r.py) are cases here. In-process only: fake docker, no network."""

import copy
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
import unittest.mock

import test_beta as tb
import test_scripts as ts
from test_beta import BIND, REPO, SCRIPTS, ca, make_backup, read

import export_csv  # noqa: E402  (scripts/ is on sys.path via test_beta)
import provision_access  # noqa: E402
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

    def test_legacy_flag_refused_from_the_cutover_on(self):  # PL decision, CRM-007R r2
        for stamp in ("20261111T000000Z", "20261111T000001Z", "20261231T120000Z", "20990101T000000Z"):
            with self.subTest(stamp=stamp):
                backup = make_backup(self.backups, f"crm-dev-{stamp}", marker=None)
                self.assert_refused(self.restore("--legacy-unmarked", os.path.basename(backup)),
                                    "stamped before 20261111T000000Z")

    def test_legacy_flag_accepts_the_last_second_before_the_cutover(self):
        backup = make_backup(self.backups, "crm-dev-20261110T235959Z", marker=None)
        res = self.restore("--legacy-unmarked", os.path.basename(backup))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("restore completed", res.stdout)

    def test_marked_backup_after_the_cutover_restores(self):
        backup = make_backup(self.backups, "crm-dev-20270101T000000Z")
        res = self.restore(os.path.basename(backup))
        self.assertEqual(res.returncode, 0, res.stderr)

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


class TestRestoretestNetworkAndVolumeSpecs(unittest.TestCase):
    """The restore-test compose: beta's network allowlist (plus internal: true,
    required there), a local volume only, no top-level secrets or configs."""

    def doc(self):
        with open(ca.RESTORETEST_COMPOSE_PATH) as fh:
            return json.load(fh)

    def test_allowed_specs(self):
        for net in ({"internal": True}, {"driver": "bridge", "internal": True}):
            for vol in (None, {}, {"driver": "local"}):
                with self.subTest(net=net, vol=vol):
                    d = self.doc()
                    d["networks"]["restoretest-net"] = net
                    d["volumes"]["db"] = vol
                    self.assertEqual(ca.check_restoretest_compose(d), [])

    def test_refused_network_specs(self):
        for spec in ({"driver": "macvlan", "internal": True},
                     {"driver": "bridge", "internal": True, "driver_opts": {}},
                     {"internal": True, "ipam": {}}, {"internal": True, "attachable": True},
                     {"internal": True, "enable_ipv6": True}, {"internal": True, "labels": {}},
                     {"driver": "Bridge", "internal": True}, {"driver": "bridge"}, {}):
            with self.subTest(spec=spec):
                d = self.doc()
                d["networks"]["restoretest-net"] = spec
                self.assertNotEqual(ca.check_restoretest_compose(d), [])

    def test_refused_volume_and_top_level(self):
        for vol in ({"driver": "local-persist"}, {"driver": "nfs"}, {"driver": "Local"},
                    {"driver": "local", "labels": {}}, {"labels": {"a": "b"}}):
            with self.subTest(vol=vol):
                d = self.doc()
                d["volumes"]["db"] = vol
                self.assertNotEqual(ca.check_restoretest_compose(d), [])
        for key in ("secrets", "configs"):
            with self.subTest(top=key):
                for value in ({"s": {"file": "/srv/CRM/runtime/beta/env"}}, {}):
                    d = self.doc()
                    d[key] = value
                    self.assertTrue(any(f"'{key}'" in e for e in ca.check_restoretest_compose(d)))

    def test_broken_fixtures_are_refused(self):
        paths = sorted(glob.glob(os.path.join(FIXTURES, "restoretest_bad_*.json")))
        self.assertGreaterEqual(len(paths), 20)
        for path in paths:
            with self.subTest(fixture=os.path.basename(path)):
                with open(path) as fh:
                    self.assertNotEqual(ca.check_restoretest_compose(json.load(fh)), [])


# CRM-007R r3: each allowlist fixture is refused for its own key.
RESTORETEST_KEY_FIXTURES = {
    "top_include": "top-level 'include'", "top_x_extension": "top-level 'x-crm'",
    "top_version": "top-level 'version'", "top_secrets": "top-level 'secrets'",
    "top_configs": "top-level 'configs'",
    "service_depends_on": "key 'depends_on'", "service_security_opt": "key 'security_opt'",
    "service_userns_mode": "key 'userns_mode'", "service_labels": "key 'labels'",
    "service_tmpfs": "key 'tmpfs'", "service_extra_hosts": "key 'extra_hosts'",
    "service_restart": "key 'restart'",
    "mount_bind_option": "refused: 'bind'", "mount_volume_subpath": "refused: 'volume'",
}

# Every crm-db key the brief names, plus a few more; none is in the shipped file.
RESTORETEST_REFUSED_DB_KEYS = (
    "depends_on", "ports", "expose", "network_mode", "security_opt", "userns_mode", "uts",
    "cgroup", "cgroup_parent", "pid", "ipc", "privileged", "cap_add", "devices", "tmpfs",
    "extra_hosts", "external_links", "links", "labels", "sysctls", "runtime", "secrets",
    "configs", "restart", "command", "entrypoint", "extends", "env_file", "volumes_from",
    "container_name", "user", "build", "dns", "x-crm", "volume_driver", "storage_opt")


class TestRestoretestAllowlist(unittest.TestCase):
    """CRM-007R r3: the restore-test compose is an allowlist, mirroring beta's."""

    def doc(self):
        with open(ca.RESTORETEST_COMPOSE_PATH) as fh:
            return json.load(fh)

    def test_shipped_file_uses_only_allowlisted_keys(self):
        d = self.doc()
        self.assertEqual(ca.check_restoretest_compose(d), [])
        self.assertLessEqual(set(d), ca.RESTORETEST_TOP_KEYS)
        self.assertEqual(set(d["services"]["crm-db"]), ca.RESTORETEST_DB_KEYS)
        self.assertEqual(set(d["services"]["crm-db"]["volumes"][0]), ca.RESTORETEST_MOUNT_KEYS)

    def test_key_fixtures_refused_for_their_key(self):
        for name, needle in RESTORETEST_KEY_FIXTURES.items():
            with self.subTest(fixture=name):
                with open(os.path.join(FIXTURES, f"restoretest_bad_{name}.json")) as fh:
                    errors = ca.check_restoretest_compose(json.load(fh))
                self.assertTrue(any(needle in e for e in errors), errors)

    def test_top_level_keys(self):
        for key, value in (("include", ["../compose.json"]), ("include", []), ("x-anything", {}),
                           ("x-", None), ("version", "3"), ("secrets", {}), ("configs", {}),
                           ("services2", {}), ("Networks", {})):
            with self.subTest(key=key, value=value):
                d = self.doc()
                d[key] = value
                errors = ca.check_restoretest_compose(d)
                self.assertTrue(any(f"top-level {key!r}" in e for e in errors), errors)
        d = self.doc()
        del d["name"]  # name is required (the project name), not merely allowed
        self.assertNotEqual(ca.check_restoretest_compose(d), [])

    def test_refused_service_keys(self):
        for key in RESTORETEST_REFUSED_DB_KEYS:
            for value in ("x", [], {}, None, True):
                with self.subTest(key=key, value=value):
                    d = self.doc()
                    d["services"]["crm-db"][key] = value
                    errors = ca.check_restoretest_compose(d)
                    self.assertTrue(any(f"crm-db: key {key!r}" in e for e in errors), errors)

    def test_image_must_be_a_pinned_mariadb(self):
        good = self.doc()["services"]["crm-db"]["image"]
        for image in (good + "\n", good[:-1], good + "0", good.replace("mariadb:", "mysql:"),
                      "mariadb@sha256:" + "0" * 64, "x/mariadb:11@sha256:" + "0" * 64,
                      good.replace("@sha256:", "@sha512:"), good.upper(), None, ["x"], 1):
            with self.subTest(image=image):
                d = self.doc()
                d["services"]["crm-db"]["image"] = image
                self.assertNotEqual(ca.check_restoretest_compose(d), [])

    def test_mounts_are_plain_named_volumes(self):
        refused = (
            {"bind": {"propagation": "rshared"}}, {"bind": {}}, {"volume": {"subpath": "x"}},
            {"volume": {"nocopy": True}}, {"volume": {}}, {"tmpfs": {"size": 1}},
            {"propagation": "rshared"}, {"subpath": "x"}, {"read_only": True},
            {"consistency": "cached"}, {"type": "bind"}, {"type": "tmpfs"},
            {"type": "npipe"}, {"type": "image"}, {"source": "/srv/CRM/runtime/beta/db"},
            {"source": ["db"]}, {"source": None}, {"target": "/var/lib/mysql/"})
        for over in refused:
            with self.subTest(over=over):
                d = self.doc()
                d["services"]["crm-db"]["volumes"][0].update(over)
                self.assertNotEqual(ca.check_restoretest_compose(d), [])
        for vols in ("db:/var/lib/mysql", ["db:/var/lib/mysql"], [], None,
                     [self.doc()["services"]["crm-db"]["volumes"][0]] * 2):
            with self.subTest(vols=vols):
                d = self.doc()
                d["services"]["crm-db"]["volumes"] = vols
                self.assertNotEqual(ca.check_restoretest_compose(d), [])

    def test_cli_refuses_an_include(self):  # check_access.py restoretest, on a copy of scripts/
        import tempfile
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        shutil.copytree(os.path.join(REPO, "scripts"), os.path.join(root, "scripts"))
        os.makedirs(os.path.join(root, "deploy", "beta", "restoretest"))
        shutil.copy(os.path.join(FIXTURES, "restoretest_bad_top_include.json"),
                    os.path.join(root, "deploy", "beta", "restoretest", "compose.json"))
        res = subprocess.run([sys.executable, "-I", os.path.join(root, "scripts", "check_access.py"),
                              "restoretest"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 1, res.stderr)
        self.assertIn("top-level 'include' is not allowed", res.stderr)


# --- 6. export bound to its target -----------------------------------------------

# Stands in for export_csv.py (records its argv); check_access.py runs for real.
EXPORT_SHIM = """#!/usr/bin/env bash
case "$1" in */export_csv.py) printf '%s\\n' "$*" >> "$EXPORT_LOG"; exit 0 ;; esac
exec "$REAL_PY" "$@"
"""

BAD_NAMES = ("/tmp/export-x", "../export-x", "export-x/../../dev/backups/export-x", "a/export-x",
             "..", "export-..", "export-a..b", "export-", "export", "backup-x", "export-x y",
             "export-x\n", "-export-x", "export-x/", "export-é")


class ExportMixin:
    def install_shim(self, bindir, tmp):
        self.export_log = os.path.join(tmp, "export.log")
        path = os.path.join(bindir, "python3")
        with open(path, "w") as fh:
            fh.write(EXPORT_SHIM)
        os.chmod(path, 0o700)
        return {"EXPORT_LOG": self.export_log, "REAL_PY": sys.executable,
                "CRM_ADMIN_USERNAME": "a", "CRM_ADMIN_PASSWORD": "b"}

    def exports(self):
        if not os.path.exists(self.export_log):
            return []
        with open(self.export_log) as fh:
            return fh.read().splitlines()

    def assert_export_refused(self, res, needle=None):
        self.assertNotEqual(res.returncode, 0, res.stdout)
        if needle:
            self.assertIn(needle, res.stderr)
        self.assertEqual(self.exports(), [], "export_csv.py never ran (no request)")


class TestBetaExportBound(ExportMixin, tb.BetaStackEnv):
    """probe_export.py / probe_r.py, beta side."""

    def setUp(self):
        super().setUp()
        self.env = self.install_shim(self.bin, self.tmp)
        self.env["CRM_BASE_URL"] = "http://127.0.0.1:8280"
        self.backups = os.path.join(self.runtime, "backups")
        self.dev_backups = os.path.join(self.tmp, "runtime", "dev", "backups")
        os.makedirs(self.dev_backups)

    def export(self, *args, **over):
        open(self.export_log, "w").close()
        return self.run_beta("export.sh", *args, extra={**self.env, **over})

    def test_default_output_is_a_new_dir_under_beta_backups(self):  # probe_r.py
        res = self.export()
        self.assertEqual(res.returncode, 0, res.stderr)
        [call] = self.exports()
        self.assertRegex(call, r" beta --base-url http://127\.0\.0\.1:8280 --out "
                         + self.backups.replace(".", r"\.") + r"/export-\d{8}T\d{6}Z$")
        self.assertEqual(os.listdir(self.dev_backups), [])

    def test_bare_name_accepted(self):
        res = self.export("export-before-upgrade_1.2")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(self.exports()[0].endswith(f"--out {self.backups}/export-before-upgrade_1.2"))

    def test_into_dev_backups_refused(self):  # probe_export.py, probe_r.py
        for arg in (os.path.join(self.dev_backups, "export-x"), os.path.join(self.dev_backups, "stolen"),
                    self.dev_backups, os.path.join(self.backups, "export-x")):
            with self.subTest(arg=arg):
                self.assert_export_refused(self.export(arg), "bare name")
        self.assertEqual(os.listdir(self.dev_backups), [])

    def test_bad_names_refused(self):
        for name in BAD_NAMES:
            with self.subTest(name=name):
                self.assert_export_refused(self.export(name), "bare name")

    def test_existing_dir_or_symlink_refused(self):
        os.makedirs(self.backups, 0o700, exist_ok=True)
        os.mkdir(os.path.join(self.backups, "export-old"))
        os.symlink(self.dev_backups, os.path.join(self.backups, "export-link"))
        os.symlink(os.path.join(self.dev_backups, "nope"), os.path.join(self.backups, "export-dangling"))
        for name in ("export-old", "export-link", "export-dangling"):
            with self.subTest(name=name):
                self.assert_export_refused(self.export(name), "already exists")
        self.assertEqual(os.listdir(self.dev_backups), [])

    def test_backup_dir_override_refused(self):  # probe_r.py (incl. empty)
        for value in ("/tmp/elsewhere", self.dev_backups, ""):
            with self.subTest(value=value):
                res = self.export(CRM_BACKUP_DIR=value)
                self.assertEqual(res.returncode, 2)
                self.assertIn("unset CRM_BACKUP_DIR", res.stderr)
                self.assertEqual(self.exports(), [])

    def test_too_many_arguments_refused(self):
        self.assert_export_refused(self.export("export-a", "export-b"), "usage")

    def test_forwarded_url_is_the_derived_pinned_url(self):  # CRM-007R r3
        # export.sh passes export_csv.py the URL check_access.py derives from the
        # env file. With beta CRM_BASE_URL must equal it, so forwarding
        # "$CRM_BASE_URL" instead is an equivalent mutant on beta; this pins the
        # contract (the dev test below is where that mutant differs).
        self.write_env(CRM_BETA_APP_PORT="8391")
        environ = {"CRM_TEST_ROOT": os.path.join(self.tmp, "runtime"), "CRM_RUNTIME_DIR": self.runtime}
        derived, problem = ca.pinned_base_url("beta", environ)
        self.assertIsNone(problem)
        self.assertEqual(derived, "http://127.0.0.1:8391")
        res = self.export("export-u", CRM_BASE_URL=derived)
        self.assertEqual(res.returncode, 0, res.stderr)
        [call] = self.exports()
        argv = call.split(" ")
        self.assertEqual(argv[1:3], ["beta", "--base-url"])
        self.assertEqual(argv[3], derived)
        self.assertEqual(argv[4:], ["--out", os.path.join(self.backups, "export-u")])

    def test_other_urls_refused(self):  # routed through check_access.py beta --base-url
        for url in (f"http://{BIND}:8180", "http://127.0.0.1:8180", "http://127.0.0.1:8280/",
                    "http://localhost:8280", "https://127.0.0.1:8280", "http://127.0.0.1:18080", ""):
            with self.subTest(url=url):
                self.assert_export_refused(self.export(CRM_BASE_URL=url), "CRM_BASE_URL")
        with open(os.path.join(self.runtime, "env"), "a") as fh:  # port set twice
            fh.write("CRM_BETA_APP_PORT=8281\n")
        self.assert_export_refused(self.export(), "CRM_BETA_APP_PORT exactly once")


DEV_BIND = ts.ACCESS["CRM_BIND_IP"]


class TestDevExportBound(ExportMixin, ts.ScriptEnv):
    """probe_export.py / probe_r.py, dev side."""

    def setUp(self):
        super().setUp()
        self.env = self.install_shim(self.bin, self.tmp.name)
        self.backups = os.path.join(self.runtime, "backups")
        self.dev_url = f"http://{DEV_BIND}:8180"

    def export(self, *args, **over):
        open(self.export_log, "w").close()
        env = {**self.env, **over}
        return self.run_script("export.sh", "dev", *args,
                               extra_env={k: v for k, v in env.items() if v is not None})

    def test_own_url_or_unset_accepted(self):
        for url in (self.dev_url, None):
            with self.subTest(url=url):
                res = self.export(CRM_BASE_URL=url)
                self.assertEqual(res.returncode, 0, res.stderr)
                [call] = self.exports()
                self.assertIn(f" dev --base-url {self.dev_url} --out {self.backups}/export-", call)
                shutil.rmtree(self.backups)

    def test_other_urls_refused(self):  # probe_export.py, probe_r.py (beta loopback)
        for url in ("http://127.0.0.1:8280", "http://127.0.0.1:18080", "http://127.0.0.1:8180",
                    f"http://{DEV_BIND}:8280", f"http://{DEV_BIND}:8181", f"{self.dev_url}/",
                    f"https://{DEV_BIND}:8180", "http://localhost:8180", ""):
            with self.subTest(url=url):
                res = self.export(CRM_BASE_URL=url)
                if url == "":  # empty = unset, as everywhere else in the scripts
                    self.assertEqual(res.returncode, 0, res.stderr)
                    shutil.rmtree(self.backups)
                    continue
                self.assert_export_refused(res, "CRM_BASE_URL must be exactly")
                self.assertNotIn(DEV_BIND, res.stderr, "the bind address is not printed")

    def test_forwarded_url_is_the_derived_pinned_url(self):  # CRM-007R r3
        environ = {"CRM_RUNTIME_DIR": self.runtime}
        derived, problem = ca.pinned_base_url("dev", environ)
        self.assertIsNone(problem)
        self.assertEqual(derived, self.dev_url)
        for url in (None, "", derived):  # unset/empty: only the derived URL can be forwarded
            with self.subTest(url=url):
                res = self.export("export-u", CRM_BASE_URL=url)
                self.assertEqual(res.returncode, 0, res.stderr)
                [call] = self.exports()
                self.assertEqual(call.split(" ")[1:],
                                 ["dev", "--base-url", derived, "--out",
                                  os.path.join(self.backups, "export-u")])
                shutil.rmtree(self.backups)

    def test_dev_env_without_a_valid_bind_ip_refused(self):
        self.write_env(self.runtime, CRM_BIND_IP="127.0.0.1")
        self.assert_export_refused(self.export(CRM_BASE_URL="http://127.0.0.1:8180"),
                                   "cannot determine the dev base URL")

    def test_paths_and_bad_names_refused(self):
        beta_backups = os.path.join(self.tmp.name, "runtime", "beta", "backups")
        os.makedirs(beta_backups)
        for name in BAD_NAMES + (os.path.join(beta_backups, "export-x"),):
            with self.subTest(name=name):
                self.assert_export_refused(self.export(name), "bare name")
        self.assertEqual(os.listdir(beta_backups), [])

    def test_existing_dir_or_symlink_refused(self):
        os.mkdir(self.backups)
        os.mkdir(os.path.join(self.backups, "export-old"))
        os.symlink("/tmp", os.path.join(self.backups, "export-link"))
        for name in ("export-old", "export-link"):
            with self.subTest(name=name):
                self.assert_export_refused(self.export(name), "already exists")

    def test_backup_dir_symlink_refused(self):
        beta_backups = os.path.join(self.tmp.name, "runtime", "beta", "backups")
        os.makedirs(beta_backups)
        os.symlink(beta_backups, self.backups)
        self.assert_export_refused(self.export(), "not a real canonical directory")
        self.assertEqual(os.listdir(beta_backups), [])


class TestExportCsvBound(unittest.TestCase):
    """export_csv.py checks the target, URL and output again, before any request."""

    def setUp(self):
        import tempfile
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        for target, text in (("dev", f"CRM_BIND_IP={BIND}\n"), ("beta", "CRM_BETA_APP_PORT=8280\n")):
            os.makedirs(os.path.join(self.root, target, "backups"))
            with open(os.path.join(self.root, target, "env"), "w") as fh:
                fh.write(text)
        self.url = {"dev": f"http://{BIND}:8180", "beta": "http://127.0.0.1:8280"}
        self.seam = {"dev": {"CRM_RUNTIME_DIR": os.path.join(self.root, "dev")},
                     "beta": {"CRM_TEST_ROOT": self.root}}

    def out(self, target, name="export-x"):
        return os.path.join(self.root, target, "backups", name)

    def run_main(self, target, url, out):
        t, err = CountingTransport(), io.StringIO()
        env = {"CRM_ADMIN_USERNAME": "a", "CRM_ADMIN_PASSWORD": "b", **self.seam[target]}
        with unittest.mock.patch("sys.stderr", err), unittest.mock.patch("sys.stdout", io.StringIO()):
            rc = export_csv.main([target, "--base-url", url, "--out", out], transport=t, environ=env)
        return rc, err.getvalue(), t.calls

    def assert_refused(self, result):
        rc, err, calls = result
        self.assertEqual(rc, 2, err)
        self.assertIn("refusing to run", err)
        self.assertEqual(calls, [], "no HTTP request")

    def test_own_target_writes_a_new_dir(self):
        for target in ("dev", "beta"):
            with self.subTest(target=target):
                rc, err, calls = self.run_main(target, self.url[target], self.out(target))
                self.assertEqual(rc, 0, err)
                self.assertTrue(calls)
                self.assertEqual(sorted(os.listdir(self.out(target))), ["accounts.csv", "contacts.csv"])
                self.assertEqual(os.stat(self.out(target)).st_mode & 0o777, 0o700)

    def test_cross_target_out_or_url_refused(self):
        for target, other in (("dev", "beta"), ("beta", "dev")):
            with self.subTest(target=target):
                self.assert_refused(self.run_main(target, self.url[target], self.out(other)))
                self.assert_refused(self.run_main(target, self.url[other], self.out(target)))
                self.assertEqual(os.listdir(os.path.join(self.root, other, "backups")), [])

    def test_bad_out_refused(self):
        for target in ("dev", "beta"):
            backups = os.path.join(self.root, target, "backups")
            os.mkdir(self.out(target, "export-old"))
            os.symlink("/tmp", self.out(target, "export-link"))
            for out in (self.out(target, "export-old"), self.out(target, "export-link"),
                        self.out(target, "x"), self.out(target, "export-.."),
                        os.path.join(backups, "export-old", "export-y"),
                        os.path.join(backups, "..", "export-y"), backups + "//export-y",
                        os.path.join(self.root, "export-y"), "export-y"):
                with self.subTest(target=target, out=out):
                    self.assert_refused(self.run_main(target, self.url[target], out))
            self.assertEqual(sorted(os.listdir(backups)), ["export-link", "export-old"])
            self.assertEqual(os.listdir(self.out(target, "export-old")), [])

    def test_trailing_newline_in_the_name_refused(self):  # CRM-007R r3: fullmatch, not `$`
        for target in ("dev", "beta"):
            for name in ("export-n\n", "export-n\r", "export-n\n\n", "\nexport-n"):
                with self.subTest(target=target, name=name):
                    out = self.out(target, name)
                    problem = ca.export_out_problem(target, out, self.seam[target])
                    self.assertIn("must be named export-", problem or "")
                    self.assert_refused(self.run_main(target, self.url[target], out))
                    self.assertFalse(os.path.lexists(out))
            self.assertIsNone(ca.export_out_problem(target, self.out(target, "export-n"),
                                                    self.seam[target]))

    def test_symlinked_backup_dir_refused(self):
        dev_backups = os.path.join(self.root, "dev", "backups")
        os.rmdir(dev_backups)
        os.symlink(os.path.join(self.root, "beta", "backups"), dev_backups)
        self.assert_refused(self.run_main("dev", self.url["dev"], self.out("dev")))
        self.assertEqual(os.listdir(os.path.join(self.root, "beta", "backups")), [])


# --- 8. the report gate ------------------------------------------------------------

class TestReportGate(tb.TestDeploySteps):
    """write_report refuses unless PROVISIONED=done and ACCEPTANCE=passed, with
    otherwise valid inputs, so the gate alone decides."""

    def inputs(self):
        dest = os.path.join(self.tmp, "rel")
        os.makedirs(dest, exist_ok=True)
        with open(os.path.join(dest, "RELEASE.json"), "w") as fh:
            json.dump({"commit": "c" * 40, "short": "c" * 12, "images": {}, "delivery_records": {}}, fh)
        bundle = os.path.join(self.tmp, "b.tar.gz")
        with open(bundle, "wb") as fh:
            fh.write(b"bundle")
        return dest, bundle

    def reports(self):
        return [n for n in os.listdir(self.runtime) if n.startswith("deploy-report")]

    def test_report_gate(self):
        dest, bundle = self.inputs()
        for prov, acc in (("skipped", "passed"), ("done", "skipped"), ("done", "failed"),
                          ("", "passed"), ("done", ""), ("", ""), ("Done", "passed"),
                          ("done", "passed "), ("unset", "unset")):
            with self.subTest(provisioning=prov, acceptance=acc):
                res = self.step(f"PROVISIONED='{prov}' ACCEPTANCE='{acc}'; "
                                f"write_report {dest} {bundle} 1; echo REPORTED")
                self.assertEqual(res.returncode, 1, res.stdout)
                self.assertIn("refusing to report success", res.stderr)
                self.assertNotIn("REPORTED", res.stdout)
                self.assertEqual(self.reports(), [])
        # Control: the same inputs with both steps done do produce a report.
        res = self.step(f"PROVISIONED=done ACCEPTANCE=passed; write_report {dest} {bundle} 1")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(len(self.reports()), 1)


for _name in [n for n in dir(tb.TestDeploySteps) if n.startswith("test_")]:
    setattr(TestReportGate, _name, None)


if __name__ == "__main__":
    unittest.main()
