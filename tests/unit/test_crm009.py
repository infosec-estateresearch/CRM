"""CRM-009: crm-beta UAT mode (plain LAN HTTP), the per-mode crm-app scheme
policy, beta user provisioning with a common UAT password and service
identities, and scripts/uat_records.py. No private address is written here:
they are derived from the validator's RFC 1918 blocks (TestLiteralAddresses).
"""

import copy
import io
import json
import os
import stat
import sys
import tempfile
import unittest
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.dirname(__file__))

import check_access as ca  # noqa: E402
import provision_users  # noqa: E402
import uat_records  # noqa: E402
from test_check_access import host, private  # noqa: E402
import test_provision as tp  # noqa: E402

TEN, SEVENTEEN, ONE_NINE_TWO = ca.RFC1918
UAT_BIND = host(private(ONE_NINE_TWO, 33), 7)
LAN_A = private(ONE_NINE_TWO, 33)              # a /24 holding the bind address
LAN_B = private(TEN, 9, prefix=16)             # a /16
UAT = {"CRM_BETA_MODE": "uat", "CRM_BETA_BIND_IP": UAT_BIND, "CRM_BETA_PORT": "8443",
       "CRM_BETA_UPSTREAM_SOURCES": f"{LAN_A} {LAN_B}", "CRM_BETA_HOSTNAME": "",
       "CRM_BETA_APP_PORT": "8280", "CRM_SITE_URL": f"http://{UAT_BIND}:8443"}
PROD = {"CRM_BETA_BIND_IP": UAT_BIND, "CRM_BETA_PORT": "8443",
        "CRM_BETA_UPSTREAM_SOURCES": host(LAN_A, 2),
        "CRM_BETA_HOSTNAME": "crm-beta.example.invalid", "CRM_BETA_APP_PORT": "8280",
        "CRM_SITE_URL": "https://crm-beta.example.invalid"}


def env(base, **over):
    v = dict(base, **over)
    return "".join(f"{k}={x}\n" for k, x in v.items() if x is not None)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestMode(unittest.TestCase):
    def test_mode_values(self):
        self.assertEqual(ca.beta_mode(""), ("production", []))
        self.assertEqual(ca.beta_mode("CRM_BETA_MODE=\n"), ("production", []))
        self.assertEqual(ca.beta_mode("CRM_BETA_MODE=production\n"), ("production", []))
        self.assertEqual(ca.beta_mode("CRM_BETA_MODE=uat\n"), ("uat", []))
        for bad in ("CRM_BETA_MODE=UAT\n", "CRM_BETA_MODE=prod\n", "CRM_BETA_MODE=dev\n",
                    "CRM_BETA_MODE=uat\nCRM_BETA_MODE=uat\n", "export CRM_BETA_MODE=uat\n",
                    "CRM_BETA_MODE=uat # c\n"):
            with self.subTest(text=bad):
                mode, errors = ca.beta_mode(bad)
                self.assertIsNone(mode)
                self.assertNotEqual(errors, [])

    def test_production_unchanged_with_explicit_or_empty_mode(self):
        for mode in (None, "", "production"):
            with self.subTest(mode=mode):
                errors, cfg = ca.check_beta(env(PROD, CRM_BETA_MODE=mode), {})
                self.assertEqual(errors, [])
                self.assertIn(f"src {host(LAN_A, 2)}/32", cfg)
                # production still refuses networks and http
                self.assertNotEqual(ca.check_beta(env(PROD, CRM_BETA_MODE=mode,
                                                      CRM_BETA_UPSTREAM_SOURCES=LAN_A), {})[0], [])
                self.assertNotEqual(ca.check_beta(env(PROD, CRM_BETA_MODE=mode,
                                                      CRM_SITE_URL=f"http://{UAT_BIND}:8443"),
                                                  {})[0], [])

    def test_unknown_mode_and_mode_in_environment_refused(self):
        self.assertNotEqual(ca.check_beta(env(UAT, CRM_BETA_MODE="test"), {})[0], [])
        self.assertNotEqual(ca.check_beta(env(UAT), {"CRM_BETA_MODE": "uat"})[0], [])


class TestUatValues(unittest.TestCase):
    def test_good_uat_passes_and_renders_networks(self):
        for over in ({}, {"CRM_BETA_HOSTNAME": None}, {"CRM_SITE_URL": UAT["CRM_SITE_URL"] + "/"}):
            with self.subTest(over=over):
                errors, cfg = ca.check_beta(env(UAT, **over), {})
                self.assertEqual(errors, [])
                self.assertIn(f"acl trusted_upstream src {LAN_A} {LAN_B}", cfg)
                self.assertIn("http-request deny deny_status 403 if !trusted_upstream", cfg)
                self.assertIn(f"bind {UAT_BIND}:8443", cfg)
                self.assertEqual(ca.check_edge_config(cfg, "uat"), [])
                # the production edge policy would refuse networks
                self.assertNotEqual(ca.check_edge_config(cfg), [])

    def test_bad_uat_values_refused(self):
        dev_net = str(ca.compose_subnets()[0])
        cases = {
            "CRM_BETA_HOSTNAME": ["crm-beta.example.invalid"],
            "CRM_SITE_URL": [f"https://{UAT_BIND}:8443", f"http://{UAT_BIND}:8444",
                             f"http://{UAT_BIND}", f"http://{UAT_BIND}:8443/x",
                             "http://crm-beta.example.invalid:8443", ""],
            "CRM_BETA_UPSTREAM_SOURCES": [
                "", private(TEN, 0, prefix=15),                 # wider than /16
                host(LAN_A, 1) + "/24",                         # host bits set
                host(LAN_A, 1),                                 # no prefix
                private(SEVENTEEN, 1, prefix=16),               # a Docker default bridge
                private(SEVENTEEN, 4 * 256 + 3),                # inside 172.16.0.0/12
                dev_net,                                        # the crm-dev subnet
                "192.0.2.0/24", "198.51.100.0/24",              # documentation, not RFC 1918
                "0.0.0.0/0", " ".join([LAN_A] * 5), f"{LAN_A},{LAN_B}",
                str(TEN), "10.0.0.0/33"],
            "CRM_BETA_BIND_IP": ["0.0.0.0", "192.0.2.10", "127.0.0.1"],
        }
        for name, values in cases.items():
            for value in values:
                with self.subTest(name=name, value=value):
                    over = {name: value}
                    if name == "CRM_BETA_BIND_IP":
                        over["CRM_SITE_URL"] = f"http://{value}:8443"
                    errors, cfg = ca.check_beta(env(UAT, **over), {})
                    self.assertNotEqual(errors, [])
                    self.assertIsNone(cfg)


class TestProxyPerMode(unittest.TestCase):
    def test_each_mode_checks_its_own_file(self):
        prod, uat = read(ca.PROXY_CONF_PATH), read(ca.PROXY_UAT_CONF_PATH)
        self.assertEqual(ca.check_proxy_conf(prod, "production"), [])
        self.assertEqual(ca.check_proxy_conf(uat, "uat"), [])
        self.assertNotEqual(ca.check_proxy_conf(prod, "uat"), [])   # sets HTTPS
        self.assertNotEqual(ca.check_proxy_conf(uat, "production"), [])  # does not
        self.assertNotEqual(ca.check_proxy_conf(uat, "other"), [])
        self.assertEqual(read(ca.PROXY_PRODUCTION_COPY_PATH), prod)

    def test_broken_uat_confs_refused(self):
        good = read(ca.PROXY_UAT_CONF_PATH)
        unset = "RequestHeader unset X-Forwarded-Proto"
        for name, text in {
            "HTTPS on": good + "SetEnv HTTPS on\n",
            "HTTPS off": good + "SetEnv HTTPS off\n",
            "header kept": good.replace(unset + "\n", ""),
            "header set": good.replace(unset, "RequestHeader set X-Forwarded-Proto https"),
            "header-conditional": good + 'SetEnvIf X-Forwarded-Proto "^https$" HTTPS=on\n',
            "env module block": good + "<IfModule !env_module>\n    LoadModule env_module "
                                       "/usr/lib/apache2/modules/mod_env.so\n</IfModule>\n",
            "remoteip": good + "RemoteIPHeader X-Forwarded-For\n",
        }.items():
            with self.subTest(fixture=name):
                self.assertNotEqual(ca.check_proxy_conf(text, "uat"), [])

    def test_mode_resolves_to_the_file_compose_mounts(self):
        src = ca.PROXY_MOUNT_SOURCE
        apache = os.path.join(REPO, "deploy", "beta", "apache")
        for text, mode, suffix in (("", "production", ""), ("CRM_BETA_MODE=\n", "production", ""),
                                   ("CRM_BETA_MODE=production\n", "production", "-production"),
                                   ("CRM_BETA_MODE=uat\n", "uat", "-uat")):
            with self.subTest(text=text):
                got_mode, path = ca.proxy_conf_for(text)
                self.assertEqual(got_mode, mode)
                # what Compose's ${CRM_BETA_MODE:+-${CRM_BETA_MODE}} gives
                self.assertEqual(path, os.path.join(apache, src.replace(
                    "${CRM_BETA_MODE:+-${CRM_BETA_MODE}}", suffix).split("/", 2)[2]))
                self.assertEqual(ca.check_proxy_conf(read(path), mode), [])
        self.assertEqual(ca.proxy_conf_for("CRM_BETA_MODE=x\n"), (None, None))

    def test_beta_check_uses_the_mode_file_and_the_copy_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "crm-proxy-uat.conf")
            with open(bad, "w") as fh:
                fh.write(read(ca.PROXY_UAT_CONF_PATH) + "SetEnv HTTPS on\n")
            self.assertNotEqual(ca.check_beta(env(UAT), {}, proxy_conf_path=bad)[0], [])
            with mock.patch.object(ca, "PROXY_UAT_CONF_PATH", bad), \
                    mock.patch.dict(ca.PROXY_CONFS, {"uat": bad}):
                self.assertNotEqual(ca.check_beta(env(UAT), {})[0], [])
            copy_path = os.path.join(tmp, "copy.conf")
            with open(copy_path, "w") as fh:
                fh.write(read(ca.PROXY_CONF_PATH) + "\n")
            self.assertNotEqual(ca.proxy_copy_errors(copy=copy_path), [])
            self.assertEqual(ca.proxy_copy_errors(), [])


class TestComposeProxyMount(unittest.TestCase):
    def doc(self):
        with open(ca.BETA_COMPOSE_PATH) as fh:
            return json.load(fh)

    def mount(self, d):
        return next(v for v in d["services"]["crm-app"]["volumes"]
                    if v["target"] == ca.PROXY_TARGET)

    def test_repository_compose_mounts_the_mode_file(self):
        d = self.doc()
        self.assertEqual(ca.check_beta_compose(d), [])
        self.assertEqual(self.mount(d)["source"], ca.PROXY_MOUNT_SOURCE)

    def test_other_proxy_mounts_refused(self):
        extra = {"type": "bind", "source": "./apache/crm-proxy-uat.conf",
                 "target": "/etc/apache2/conf-enabled/x.conf", "read_only": True}
        cases = {
            "fixed production file": lambda d: self.mount(d).__setitem__(
                "source", "./apache/crm-proxy.conf"),
            "fixed uat file": lambda d: self.mount(d).__setitem__(
                "source", "./apache/crm-proxy-uat.conf"),
            "other variable": lambda d: self.mount(d).__setitem__(
                "source", "./apache/crm-proxy${CRM_X:+-${CRM_X}}.conf"),
            "writable": lambda d: self.mount(d).__setitem__("read_only", False),
            "other target": lambda d: self.mount(d).__setitem__(
                "target", "/etc/apache2/conf-enabled/other.conf"),
            "removed": lambda d: d["services"]["crm-app"]["volumes"].remove(self.mount(d)),
            "second apache mount": lambda d: d["services"]["crm-app"]["volumes"].append(extra),
            "on the daemon": lambda d: d["services"]["crm-daemon"]["volumes"].append(
                copy.deepcopy(self.mount(d))),
            "short syntax": lambda d: d["services"]["crm-app"]["volumes"].append(
                "./apache/crm-proxy-uat.conf:/etc/apache2/conf-enabled/y.conf:ro"),
        }
        for name, change in cases.items():
            with self.subTest(case=name):
                d = self.doc()
                change(d)
                self.assertNotEqual(ca.check_beta_compose(d), [])


class TestCheckAccessCli(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())  # under /tmp (TMPDIR)
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, True))
        self.runtime = os.path.join(self.tmp, "beta")
        os.makedirs(self.runtime)
        self.environ = {"CRM_TEST_ROOT": self.tmp}

    def main(self, text, *args):
        with open(os.path.join(self.runtime, "env"), "w") as fh:
            fh.write(text)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = ca.main(["beta", *args], self.environ)
        return code, out.getvalue(), err.getvalue()

    def test_mode_prints_only_the_mode(self):
        self.assertEqual(self.main(env(UAT), "--mode")[:2], (0, "uat\n"))
        self.assertEqual(self.main(env(PROD), "--mode")[:2], (0, "production\n"))
        code, out, err = self.main(env(UAT, CRM_BETA_MODE="Uat"), "--mode")
        self.assertEqual((code, out), (1, ""))
        self.assertNotIn(UAT_BIND, err)
        self.environ["CRM_BETA_MODE"] = "uat"
        self.assertEqual(self.main(env(UAT), "--mode")[0], 1)

    def test_uat_render_then_check(self):
        code, out, err = self.main(env(UAT), "--render")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.main(env(UAT))[0], 0)
        self.assertIn("uat mode", self.main(env(UAT))[1])
        self.assertEqual(self.main(env(UAT, CRM_BETA_UPSTREAM_SOURCES=LAN_A))[0], 1)  # stale edge


    def test_deploy_release_prints_the_mode_only(self):
        import subprocess
        script = ('. "$1/scripts/deploy_release.sh"; CRM_BETA_ENV_NAMES=(CRM_BETA_MODE); '
                  'deploy_mode "$1"')
        for text, want in ((env(UAT), "uat"), (env(PROD), "production")):
            with self.subTest(want=want):
                with open(os.path.join(self.runtime, "env"), "w") as fh:
                    fh.write(text)
                res = subprocess.run(["bash", "-c", script, "x", REPO], capture_output=True,
                                     text=True, env={"PATH": os.environ["PATH"],
                                                     "CRM_TEST_ROOT": self.tmp,
                                                     "CRM_RUNTIME_DIR": self.runtime})
                self.assertEqual((res.returncode, res.stdout), (0, want + "\n"), res.stderr)
        with open(os.path.join(self.runtime, "env"), "w") as fh:
            fh.write(env(UAT, CRM_BETA_MODE="staging"))
        res = subprocess.run(["bash", "-c", script, "x", REPO], capture_output=True, text=True,
                             env={"PATH": os.environ["PATH"], "CRM_TEST_ROOT": self.tmp,
                                  "CRM_RUNTIME_DIR": self.runtime})
        self.assertEqual(res.returncode, 1)
        self.assertIn("CRM_BETA_MODE", res.stderr)
        src = read(os.path.join(REPO, "scripts", "deploy_release.sh"))
        self.assertIn('echo "crm-beta mode: $DEPLOY_MODE"', src)
        self.assertIn("CRM_BETA_SAFE_MODE=${DEPLOY_MODE:-production}", src)


# --- provision_users: common password and service identities ---------------------

STRONG = "Uat-Common-Pass-2026"  # synthetic test value
SERVICE = "ZZZTEST00000002AAA"   # intake.one plays a service identity here


class TestCommonPassword(tp.UsersBase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(provision_users, "COMMON_PASSWORD_OWNER_UID", os.getuid())
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_pw(self, text=STRONG + "\n", mode=0o600, name="common"):
        path = self.path(name)
        with open(path, "w") as fh:
            fh.write(text)
        os.chmod(path, mode)
        return path

    def run_beta(self, *extra, users=None, fake=None):
        return tp.run(provision_users.main,
                      ["beta", "--input", self.write_users(users or tp.synthetic_users()),
                       "--legacy-shared", tp.LEGACY, *extra], fake or self.fake)

    def users(self):
        return {u["userName"]: u for u in self.fake.records["User"].values()
                if u.get("type") == "regular"}

    def test_new_active_users_get_the_common_password_and_nothing_is_recorded(self):
        code, out, err = self.run_beta("--common-password-file", self.write_pw(),
                                       "--service-identity", SERVICE)
        self.assertEqual(code, 0, err)
        users = self.users()
        self.assertEqual(self.fake.passwords[users["staff.one"]["id"]], STRONG)
        self.assertTrue(users["staff.one"]["isActive"])
        self.assertFalse(users["staff.one"]["sendAccessInfo"])
        for name in ("intake.one", "former.one", "shared.intake"):  # service, inactive, legacy
            with self.subTest(user=name):
                self.assertFalse(users[name]["isActive"])
                self.assertNotEqual(self.fake.passwords[users[name]["id"]], STRONG)
        self.assertEqual((users["intake.one"]["firstName"], users["intake.one"]["lastName"]),
                         ("Sam", "Sampleton"))  # names kept
        counts = json.loads(out)
        self.assertEqual((counts["passwordsIssued"], counts["commonPasswordUsers"]), (0, 1))
        self.assertNotIn(STRONG, out + err)
        self.assertEqual(os.listdir(self.tmp.name).count("pw.csv"), 0)
        admin = self.fake.records["User"]["admin1"]
        self.assertNotIn("admin1", self.fake.passwords)
        self.assertEqual(admin["type"], "admin")
        for call in self.fake.calls:  # the ER Import API user is never written
            if call["method"] in ("POST", "PUT") and call["data"]:
                self.assertNotEqual(call["data"].get("type"), "api")

    def test_password_file_when_given_records_nothing_and_rerun_touches_no_password(self):
        pw = self.write_pw()
        code, _, err = self.run_beta("--common-password-file", pw,
                                     "--password-file", self.path("gen.csv"))
        self.assertEqual(code, 0, err)
        self.assertFalse(os.path.lexists(self.path("gen.csv")))
        before = dict(self.fake.passwords)
        self.fake.calls.clear()
        code, _, err = self.run_beta("--common-password-file", pw)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.fake.writes(), [])
        self.assertEqual(self.fake.passwords, before)

    def test_bad_password_files_refused_before_any_request(self):
        target = self.write_pw(name="real")
        link = self.path("link")
        os.symlink(target, link)
        cases = {
            "symlink": link, "missing": self.path("nope"), "directory": self.tmp.name,
            "mode 0644": self.write_pw(mode=0o644, name="m644"),
            "mode 0400": self.write_pw(mode=0o400, name="m400"),
            "short": self.write_pw("Short-Pass-1\n", name="short"),
            "two classes": self.write_pw("onlylowercaseand12345\n", name="two"),
            "two lines": self.write_pw(STRONG + "\n" + STRONG + "\n", name="lines"),
            "empty": self.write_pw("", name="empty"),
        }
        for name, path in cases.items():
            with self.subTest(case=name):
                fake = tp.FakeEspo()
                code, out, err = self.run_beta("--common-password-file", path, fake=fake)
                self.assertNotEqual(code, 0)
                self.assertEqual(fake.calls, [])
                self.assertNotIn(STRONG, out + err)

    def test_not_root_owned_refused(self):
        with mock.patch.object(provision_users, "COMMON_PASSWORD_OWNER_UID", os.getuid() + 1):
            fake = tp.FakeEspo()
            code, _, err = self.run_beta("--common-password-file", self.write_pw(), fake=fake)
        self.assertEqual(code, 1)
        self.assertIn("owned by root", err)
        self.assertEqual(fake.calls, [])

    def test_dev_and_reset_refused(self):
        pw = self.write_pw()
        fake = tp.FakeEspo()
        code, _, err = tp.run(provision_users.main,
                              ["dev", "--input", self.write_users(tp.synthetic_users()),
                               "--common-password-file", pw], fake)
        self.assertEqual(code, 1)
        self.assertIn("only for target beta", err)
        code, _, err = tp.run(provision_users.main, ["beta", "--reset", SERVICE,
                                                     "--common-password-file", pw], fake)
        self.assertEqual(code, 1)
        self.assertEqual(fake.calls, [])


class TestServiceIdentity(tp.UsersBase):
    def test_inactive_unrecorded_names_kept_and_reset_refused(self):
        code, out, err = tp.run(provision_users.main,
                                ["dev", "--input", self.write_users(tp.synthetic_users()),
                                 "--password-file", self.path("pw.csv"),
                                 "--service-identity", SERVICE], self.fake)
        self.assertEqual(code, 0, err)
        svc = self.fake.by_user_name("intake.one")
        self.assertFalse(svc["isActive"])
        self.assertEqual((svc["firstName"], svc["lastName"]), ("Sam", "Sampleton"))
        rows = self.read_csv()
        self.assertNotIn("intake.one", {r[1] for r in rows[1:]})
        self.assertNotIn(self.fake.passwords[svc["id"]], {r[2] for r in rows[1:]})
        self.assertIn("service identity", err)
        code, _, err = tp.run(provision_users.main,
                              ["dev", "--reset", SERVICE, "--password-file", self.path("r.csv"),
                               "--service-identity", SERVICE], self.fake)
        self.assertEqual(code, 1)
        self.assertIn("service identity", err)
        self.assertFalse(os.path.lexists(self.path("r.csv")))

    def test_unknown_or_malformed_service_identity_refused(self):
        for sf in ("ZZZTEST00000099AAA", "bad id"):
            with self.subTest(sf=sf):
                fake = tp.FakeEspo()
                code, _, _ = tp.run(provision_users.main,
                                    ["dev", "--input", self.write_users(tp.synthetic_users()),
                                     "--password-file", self.path("x.csv"),
                                     "--service-identity", sf], fake)
                self.assertEqual(code, 1)
                self.assertEqual(fake.calls, [])


# --- beta-safe suite in UAT mode ---------------------------------------------------

import test_beta as tb  # noqa: E402  (module only: its classes are not collected here)


class TestBetaSafeUatSiteUrl(unittest.TestCase):
    def run_mode(self, mode, site):
        runner = tb.TestBetaSafeSuite("test_healthy_beta_passes_with_get_only")
        runner.setUp()
        try:
            env = {"CRM_BASE_URL": "http://127.0.0.1:8280", tb.bs.ENV_KEY_FILE: runner.key_file}
            if mode is not None:
                env[tb.bs.ENV_MODE] = mode
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop(tb.bs.ENV_MODE, None)
                result, _ = runner.run_suite(tb.FakeBetaEspo(site=site), env)
            return runner.failed(result)
        finally:
            runner.doCleanups()

    def test_site_url_scheme_follows_the_mode(self):
        lan = f"http://{UAT_BIND}:8443"
        self.assertEqual(self.run_mode("uat", lan), [])
        self.assertEqual(self.run_mode("uat", lan + "/"), [])
        self.assertEqual(self.run_mode(None, "https://crm-beta.example.invalid"), [])
        self.assertEqual(self.run_mode("production", "https://crm-beta.example.invalid"), [])
        for mode, site in (("uat", "https://crm-beta.example.invalid"), ("uat", f"http://{UAT_BIND}"),
                           ("uat", "http://192.0.2.10:8443"), ("uat", "http://127.0.0.1:8443"),
                           (None, lan), ("production", lan),
                           ("staging", "https://crm-beta.example.invalid")):
            with self.subTest(mode=mode, site=site):
                self.assertEqual(self.run_mode(mode, site), ["test_site_url_uses_https"])


# --- uat_records.py ----------------------------------------------------------------

class FakeRecords:
    def __init__(self):
        self.methods = []
        self.data = {e: [{"id": f"{e[:2].lower()}{i}", "sfId": sf}
                         for i, sf in enumerate(("ZZZTEST00000001AAA", None, "", None))]
                     for e in uat_records.ENTITIES}
        self.data["Email"] = [{"id": "em0", "sfId": "ZZZTEST00000001AAA"}]

    def request(self, method, url, headers, body):
        self.methods.append(method)
        parts = urllib.parse.urlsplit(url)
        entity = parts.path.split("/api/v1/", 1)[1]
        q = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
        rows = self.data[entity]
        if q["where[0][type]"] == ["isNull"]:
            rows = [r for r in rows if r["sfId"] is None]
        else:
            rows = [r for r in rows if r["sfId"] == q["where[0][value]"][0]]
        off, size = int(q["offset"][0]), int(q["maxSize"][0])
        return 200, json.dumps({"total": len(rows),
                                "list": [{"id": r["id"]} for r in rows[off:off + size]]}).encode()


class TestUatRecords(unittest.TestCase):
    def run_it(self, argv, environ=None):
        fake = FakeRecords()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = uat_records.main(argv, transport=fake, environ=environ or tp.BETA_ENV)
        return code, out.getvalue(), err.getvalue(), fake

    def test_counts_only_get_only(self):
        code, out, err, fake = self.run_it(["beta"])
        self.assertEqual(code, 0, err)
        counts = json.loads(out)
        self.assertEqual(list(counts), list(uat_records.ENTITIES))
        self.assertEqual(counts["Account"], 3)
        self.assertEqual(counts["Email"], 0)
        self.assertEqual(set(fake.methods), {"GET"})
        self.assertNotIn("ac1", out)

    def test_list_ids_writes_a_new_0600_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ids.csv")
            code, _, err, _ = self.run_it(["beta", "--list-ids", path])
            self.assertEqual(code, 0, err)
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
            lines = read(path).splitlines()
            self.assertIn("Account,ac1", lines)
            self.assertEqual(len(lines), 18)
            code, _, err, fake = self.run_it(["beta", "--list-ids", path])  # never overwritten
            self.assertEqual(code, 1)
            self.assertEqual(fake.methods, [])

    def test_guards(self):
        for argv in ([], ["dev"], ["prod"]):
            with self.subTest(argv=argv):
                code, _, _, fake = self.run_it(argv)
                self.assertEqual(code, 2)
                self.assertEqual(fake.methods, [])
        code, _, err, fake = self.run_it(["beta", "--base-url", tp.BASE])
        self.assertEqual(code, 2)
        self.assertEqual(fake.methods, [])

    def test_transport_refuses_writes(self):
        guard = uat_records.GetOnlyTransport(FakeRecords())
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.assertRaises(uat_records.ProvisionError):
                guard.request(method, "http://x/api/v1/Account", {}, b"{}")


if __name__ == "__main__":
    unittest.main()
