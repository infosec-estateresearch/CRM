"""CRM-007 unit tests: target guards (dev|beta), beta bind policy, edge policy
with broken fixtures, the crm-app HTTPS policy, release bundle reproducibility
and verification refusals, deploy refusing a non-empty runtime and its
post-unpack steps, beta seeding refusal, the read-only beta-safe acceptance
suite (GET only), the restore test's isolation, and the backup timer
templates. In-process only: fake docker/stat/id/python3, temporary git
repositories, no network."""

import io
import ipaddress
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
import unittest.mock
import urllib.parse

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
sys.path.insert(0, SCRIPTS)

import check_access as ca  # noqa: E402
import release  # noqa: E402
import seed_synthetic  # noqa: E402
from test_check_access import host, private  # noqa: E402

TEN, _, ONE_NINE_TWO = ca.RFC1918
BIND = host(private(ONE_NINE_TWO, 33), 7)
UP1 = host(private(ONE_NINE_TWO, 33), 2)
UP2 = host(private(TEN, 9), 4)
GOOD = {"CRM_BETA_BIND_IP": BIND, "CRM_BETA_PORT": "8443",
        "CRM_BETA_UPSTREAM_SOURCES": f"{UP1} {UP2}/32",
        "CRM_BETA_HOSTNAME": "crm-beta.example.invalid", "CRM_BETA_APP_PORT": "8280",
        "CRM_SITE_URL": "https://crm-beta.example.invalid"}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def env_text(**over):
    v = dict(GOOD, **over)
    return "".join(f"{k}={x}\n" for k, x in v.items() if x is not None)


def rendered(**over):
    return ca.render_edge(dict(GOOD, **over))


class TestBetaValues(unittest.TestCase):
    def test_good_values_pass_and_render_a_valid_edge(self):
        errors, cfg = ca.check_beta(env_text(), {})
        self.assertEqual(errors, [])
        self.assertIn(f"bind {BIND}:8443", cfg)
        self.assertIn(f"src {UP1}/32 {UP2}/32", cfg)
        self.assertIn("server crm_app 127.0.0.1:8280", cfg)

    def test_bad_values_are_refused(self):
        cases = {
            "CRM_BETA_BIND_IP": ["0.0.0.0", "127.0.0.1", "192.0.2.10", "", "a.b.c.d"],
            "CRM_BETA_PORT": ["80", "1023", "65536", "8x", "", "8180"],
            "CRM_BETA_APP_PORT": ["443", "70000", "8180"],
            "CRM_BETA_UPSTREAM_SOURCES": ["", "0.0.0.0/0", f"{UP1}/24", "198.51.100.7",
                                          " ".join([UP1] * 5), f"{UP1},{UP2}"],
            "CRM_BETA_HOSTNAME": ["localhost", "Crm.Example.invalid", "-x.example.invalid",
                                  "crm_beta.example.invalid", "a..b"],
            "CRM_SITE_URL": ["http://crm-beta.example.invalid", "https://other.example.invalid/"],
        }
        for name, values in cases.items():
            for value in values:
                with self.subTest(name=name, value=value):
                    errors, cfg = ca.check_beta(env_text(**{name: value}), {})
                    self.assertNotEqual(errors, [])
                    self.assertIsNone(cfg)

    def test_missing_name_and_environment_override_refused(self):
        self.assertNotEqual(ca.check_beta(env_text(CRM_BETA_UPSTREAM_SOURCES=None), {})[0], [])
        self.assertNotEqual(ca.check_beta(env_text(), {"CRM_BETA_PORT": "8443"})[0], [])

    def test_same_edge_and_app_port_refused(self):
        self.assertNotEqual(ca.check_beta(env_text(CRM_BETA_APP_PORT="8443"), {})[0], [])


class TestBetaBindPolicy(unittest.TestCase):
    def doc(self):
        with open(ca.BETA_COMPOSE_PATH) as fh:
            return json.load(fh)

    def test_repository_compose_passes(self):
        self.assertEqual(ca.check_beta_compose(self.doc()), [])

    def test_broken_compose_is_refused(self):
        mutations = [
            lambda d: d["services"]["crm-app"].__setitem__(
                "ports", ["0.0.0.0:${CRM_BETA_APP_PORT:?x}:80"]),
            lambda d: d["services"]["crm-app"].__setitem__("ports", ["${CRM_BETA_APP_PORT:?x}:80"]),
            lambda d: d["services"]["crm-db"].__setitem__("ports", ["127.0.0.1:3306:3306"]),
            lambda d: d["services"]["crm-beta-edge"].__setitem__("network_mode", "bridge"),
            lambda d: d["services"]["crm-beta-edge"].__setitem__("read_only", False),
            lambda d: d["services"]["crm-beta-edge"].__setitem__("cap_add", ["NET_ADMIN"]),
            lambda d: d["services"]["crm-beta-edge"].__setitem__("cap_drop", []),
            lambda d: d["services"]["crm-beta-edge"].__setitem__("security_opt", []),
            lambda d: d["services"]["crm-beta-edge"].__setitem__("user", "root"),
            lambda d: d["services"]["crm-beta-edge"].__setitem__("ports", ["8443:8443"]),
            lambda d: d.__setitem__("name", "crm-dev"),
            lambda d: d["services"].pop("crm-beta-edge"),
        ]
        edge = lambda d: d["services"]["crm-beta-edge"]  # noqa: E731
        vol = {"type": "bind", "target": "/x"}
        named = {
            "external network": lambda d: d["networks"]["crm-beta-net"].__setitem__("external", True),
            "named network": lambda d: d["networks"]["crm-beta-net"].__setitem__("name", "crm-dev_crm-net"),
            "named volume": lambda d: d.__setitem__("volumes", {"v": {}}),
            "external volume": lambda d: d.__setitem__("volumes", {"v": {"external": True}}),
            "volume mount": lambda d: d["services"]["crm-db"]["volumes"].append(
                {"type": "volume", "source": "v", "target": "/y"}),
            "bind outside runtime": lambda d: d["services"]["crm-app"]["volumes"].append(
                dict(vol, source="/srv/CRM/runtime/dev/data")),
            "bind via ..": lambda d: d["services"]["crm-app"]["volumes"].append(
                dict(vol, source="/srv/CRM/runtime/beta/../dev")),
            "bind release escape": lambda d: d["services"]["crm-app"]["volumes"].append(
                dict(vol, source="./../../etc")),
            "bind other variable": lambda d: d["services"]["crm-app"]["volumes"].append(
                dict(vol, source="${HOME}")),
            "short-form bind": lambda d: d["services"]["crm-app"]["volumes"].append("/etc:/x"),
            "docker.sock": lambda d: edge(d)["volumes"].append(
                dict(vol, source="/var/run/docker.sock")),
            "docker.sock in runtime": lambda d: edge(d)["volumes"].append(
                dict(vol, source="/srv/CRM/runtime/beta/docker.sock")),
            "no edge user": lambda d: edge(d).pop("user"),
            "empty edge user": lambda d: edge(d).__setitem__("user", ""),
            "uid 0": lambda d: edge(d).__setitem__("user", "0"),
            "uid 00": lambda d: edge(d).__setitem__("user", "00"),
            "uid 0 with group": lambda d: edge(d).__setitem__("user", "0:99"),
            "root with group": lambda d: edge(d).__setitem__("user", "root:haproxy"),
            "uid 0 as int": lambda d: edge(d).__setitem__("user", 0),
            "uid 0 with spaces": lambda d: edge(d).__setitem__("user", " 0"),
        }
        for name, mutate in named.items():
            with self.subTest(mutation=name):
                d = self.doc()
                mutate(d)
                self.assertNotEqual(ca.check_beta_compose(d), [])
        for user in ("haproxy", "99", "99:99"):
            d = self.doc()
            edge(d)["user"] = user
            self.assertEqual(ca.check_beta_compose(d), [], user)
        for i, mutate in enumerate(mutations):
            with self.subTest(mutation=i):
                d = self.doc()
                mutate(d)
                self.assertNotEqual(ca.check_beta_compose(d), [])

    def test_allowlist_refuses_each_unlisted_key(self):
        """CRM-007 r4: one subtest per refused key, on a service and on the edge,
        each a single-key change to the shipped compose that alone must fail."""
        service_keys = {
            "volumes_from": ["crm-db"], "pid": "host", "ipc": "host",
            "env_file": ["/etc/passwd"], "extends": {"service": "crm-db"},
            "external_links": ["crm-dev-crm-db-1:db"], "secrets": ["s"], "configs": ["c"],
            "container_name": "crm-db", "devices": ["/dev/sda:/dev/sda"], "privileged": True,
            "cap_add": ["SYS_ADMIN"], "build": ".", "x-extra": 1, "labels": {"a": "b"},
            "network_mode": "container:crm-dev-crm-db-1",
        }
        for svc in ("crm-app", ca.EDGE_SERVICE):
            for key, value in service_keys.items():
                if svc == ca.EDGE_SERVICE and key == "network_mode":
                    value = "container:crm-dev-crm-db-1"
                with self.subTest(service=svc, key=key):
                    d = self.doc()
                    d["services"][svc][key] = value
                    errors = ca.check_beta_compose(d)
                    self.assertNotEqual(errors, [])
                    if key != "network_mode" or svc != ca.EDGE_SERVICE:
                        self.assertIn(f"{svc}: key {key!r} is not allowed", errors)
        for key in ("cap_drop", "read_only", "security_opt", "user", "network_mode"):
            with self.subTest(service="crm-db", edge_only_key=key):
                d = self.doc()
                d["services"]["crm-db"][key] = d["services"][ca.EDGE_SERVICE][key]
                self.assertIn(f"crm-db: key {key!r} is not allowed", ca.check_beta_compose(d))
        for key, value in {"include": ["other.yml"], "secrets": {"s": {"file": "/etc/shadow"}},
                           "configs": {"c": {"file": "/etc/shadow"}}, "x-anchor": {},
                           "version": "3.9"}.items():
            with self.subTest(top_level=key):
                d = self.doc()
                d[key] = value
                self.assertIn(f"beta compose top-level key {key!r} is not allowed",
                              ca.check_beta_compose(d))

    def test_image_must_be_pinned_by_digest(self):
        digest = "0" * 64
        bad = {"tag only": "mariadb:11.4.13", "latest": "haproxy:latest", "no image": None,
               "short digest": "haproxy@sha256:" + "0" * 63, "upper hex": "haproxy@sha256:" + "A" * 64,
               "other algorithm": "haproxy@sha512:" + digest, "digest then junk":
               "haproxy@sha256:" + digest + "x", "not a string": ["haproxy"]}
        for svc in ("crm-db", "crm-app", "crm-daemon", ca.EDGE_SERVICE):
            for label, image in bad.items():
                with self.subTest(service=svc, image=label):
                    d = self.doc()
                    if image is None:
                        d["services"][svc].pop("image")
                    else:
                        d["services"][svc]["image"] = image
                    self.assertIn(f"{svc}: image must be pinned as name@sha256:<64 hex>",
                                  ca.check_beta_compose(d))
        for image in ("haproxy@sha256:" + digest, "docker.io/library/mariadb:11.4@sha256:" + digest):
            d = self.doc()
            d["services"]["crm-db"]["image"] = image
            self.assertEqual(ca.check_beta_compose(d), [], image)

    def test_beta_shares_nothing_with_dev_and_pins_registered_images(self):
        doc = self.doc()
        self.assertEqual(set(doc["networks"]), {"crm-beta-net"})
        self.assertNotIn("volumes", doc)
        sys.path.insert(0, os.path.dirname(__file__))
        import compose_policy
        reg = compose_policy.load_register()
        self.assertEqual(reg["haproxy"]["digest"], "sha256:1c3568e520453cc8ba98c39501febcf"
                                                   "450429c80e6cc27ecad779961d76e597c")
        self.assertEqual(doc["services"]["crm-beta-edge"]["image"],
                         "haproxy@" + reg["haproxy"]["digest"])
        self.assertEqual(compose_policy.scan_literal_ips(), [])


class TestEdgePolicy(unittest.TestCase):
    def test_rendered_template_passes(self):
        self.assertEqual(ca.check_edge_config(rendered()), [])

    def test_broken_fixtures_are_refused(self):
        good = rendered()
        acl = f"acl trusted_upstream src {UP1}/32 {UP2}/32"
        fixtures = {
            "0.0.0.0/0 source": good.replace(acl, "acl trusted_upstream src 0.0.0.0/0"),
            "missing source list": good.replace(acl, "acl trusted_upstream src"),
            "no acl": good.replace(acl, ""),
            "no deny": good.replace("http-request deny deny_status 403 if !trusted_upstream\n", ""),
            "untrusted xff kept": good.replace(
                "http-request del-header X-Forwarded-For if !trusted_upstream\n", ""),
            "bind all interfaces": good.replace(f"bind {BIND}:8443", "bind *:8443"),
            "bind unspecified": good.replace(f"bind {BIND}:8443", "bind 0.0.0.0:8443"),
            "bind port only": good.replace(f"bind {BIND}:8443", "bind :8443"),
            "two binds": good.replace(f"bind {BIND}:8443", f"bind {BIND}:8443\n    bind {BIND}:9443"),
            "public bind": good.replace(f"bind {BIND}:8443", "bind 192.0.2.10:8443"),
            "wide source": good.replace(acl, f"acl trusted_upstream src {UP1}/24"),
            "allow rule": good.replace("default_backend", "http-request allow\n    default_backend"),
            "server elsewhere": good.replace("127.0.0.1:8280", f"{UP1}:8280"),
            "no timeouts": good.replace("timeout http-request 10s", ""),
            "mode tcp": good.replace("mode http", "mode tcp"),
            "mode tcp, tabs": good.replace("mode http", "mode\t \ttcp"),
            "allow rule, spaced": good.replace("default_backend", "http-request   allow\n    default_backend"),
            "allow rule, tab": good.replace("default_backend", "http-request\tallow if TRUE\n    default_backend"),
            "second server": good.replace("server crm_app 127.0.0.1:8280",
                                          "server crm_app 127.0.0.1:8280\n    server b 127.0.0.1:8281"),
            "use_backend": good.replace("default_backend crm_beta_app",
                                        "use_backend crm_beta_app if trusted_upstream\n    default_backend crm_beta_app"),
            "unknown directive": good.replace("maxconn 256", "maxconn 256\n    stats socket /tmp/s"),
            "unknown section": good + "\nlisten stats\n    bind 127.0.0.1:9000\n",
            "second frontend": good + "\nfrontend crm_beta_edge\n    bind 127.0.0.1:9000\n",
            "directive before a section": "maxconn 1\n" + good,
            "set-header": good.replace("default_backend", "http-request set-header X-A b\n    default_backend"),
            "trailing slash source": good.replace(acl, f"acl trusted_upstream src {UP1}/ {UP2}/32"),
        }
        for name, text in fixtures.items():
            with self.subTest(fixture=name):
                self.assertNotEqual(text, good)
                self.assertNotEqual(ca.check_edge_config(text), [])

    def test_whitespace_is_normalised_before_matching(self):
        good = rendered()
        spaced = good.replace("    http-request deny deny_status 403",
                              "\thttp-request  deny\tdeny_status   403")
        self.assertNotEqual(spaced, good)
        self.assertEqual(ca.check_edge_config(spaced), [])

    def test_each_rule_reports_its_own_error(self):
        """Message-specific: removing any one rule makes its case fail."""
        good = rendered()
        cases = {
            "a forwarded header is set without the trusted_upstream condition":
                good.replace("http-request deny deny_status 403 if !trusted_upstream",
                             "http-request deny deny_status 403 if !trusted_upstream\n"
                             f"    http-request set-header X-Forwarded-For {UP1}"),
            "exactly one server (found 2)": good.replace(
                "server crm_app 127.0.0.1:8280",
                "server crm_app 127.0.0.1:8280\n    server b 127.0.0.1:8281"),
            "must not use use_backend": good.replace(
                "default_backend crm_beta_app", "use_backend crm_beta_app\n    default_backend crm_beta_app"),
            "must run in mode http, not 'mode tcp'": good.replace("mode http", "mode  tcp"),
            "directive not allowed in 'global': stats": good.replace(
                "maxconn 256", "maxconn 256\n    stats socket /tmp/s"),
            "http-request action not allowed: allow": good.replace(
                "default_backend", "http-request\tallow\n    default_backend"),
            "must not use tcp-request or http-request allow": good.replace(
                "default_backend", "http-request  allow\n    default_backend"),
            "section not allowed: listen stats": good + "\nlisten stats\n",
            "section repeated": good + "\nglobal\n",
            "outside any section": "maxconn 1\n" + good,
        }
        for needle, text in cases.items():
            with self.subTest(rule=needle):
                self.assertTrue(any(needle in e for e in ca.check_edge_config(text)),
                                ca.check_edge_config(text))

    def test_no_x_forwarded_proto_and_xff_handling_kept(self):
        good = rendered()
        self.assertNotIn("X-Forwarded-Proto", "\n".join(ca._edge_lines(good)))
        self.assertIn("http-request del-header X-Forwarded-For if !trusted_upstream", good)
        self.assertIn("option forwardfor", good)

    def test_upstream_sources_are_exact_hosts(self):
        for value in (f"{UP1}/", f"{UP1}//32", f"{UP1}/32/", f"{UP1}/032", f"/{UP1}"):
            with self.subTest(value=value):
                self.assertNotEqual(ca.validate_upstream_sources(value), [])
        self.assertEqual(ca.validate_upstream_sources(f"{UP1} {UP2}/32"), [])

    def test_check_access_beta_cli_renders_only_when_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = os.path.join(tmp, "beta")
            os.mkdir(runtime)
            with open(os.path.join(runtime, "env"), "w") as fh:
                fh.write(env_text())
            env = {"PATH": os.environ["PATH"], "CRM_RUNTIME_DIR": runtime, "CRM_TEST_ROOT": tmp}
            res = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "check_access.py"),
                                  "beta", "--render"], capture_output=True, text=True, env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            for v in (BIND, UP1, UP2):
                self.assertNotIn(v, res.stdout + res.stderr)
            cfg = os.path.join(runtime, "edge", "haproxy.cfg")
            self.assertEqual(stat.S_IMODE(os.stat(cfg).st_mode), 0o644)
            os.unlink(cfg)
            with open(os.path.join(runtime, "env"), "w") as fh:
                fh.write(env_text(CRM_BETA_UPSTREAM_SOURCES="0.0.0.0/0"))
            res = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "check_access.py"),
                                  "beta", "--render"], capture_output=True, text=True, env=env)
            self.assertEqual(res.returncode, 1)
            self.assertFalse(os.path.exists(cfg))


FAKE_STAT = """#!/usr/bin/env bash
# Plays root ownership for paths under FAKE_ROOT_DIR (tests do not run as root).
if [ "$1" = -c ] && [ "$2" = '%u %a' ]; then
    real=$("$REAL_STAT" -c '%a' -- "$4")
    case "$4" in "$FAKE_ROOT_DIR"*) echo "0 $real"; exit 0 ;; esac
fi
exec "$REAL_STAT" "$@"
"""
FAKE_CHOWN = """#!/usr/bin/env bash
# Tests do not run as root: chown to 0:0 is recorded, not performed.
echo "chown $*" >> "$FAKE_DOCKER_LOG.chown"
"""
FAKE_ID = """#!/usr/bin/env bash
[ "$*" = "-u" ] && [ -n "${FAKE_UID:-}" ] && { echo "$FAKE_UID"; exit 0; }
exec "$REAL_ID" "$@"
"""


class ShellEnv(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())  # canonical: guards compare realpath
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = os.path.join(self.tmp, "bin")
        os.mkdir(self.bin)
        for name, text in (("stat", FAKE_STAT), ("id", FAKE_ID), ("chown", FAKE_CHOWN),
                           ("docker", "#!/usr/bin/env bash\necho \"$*\" >> \"$FAKE_DOCKER_LOG\"\n")):
            path = os.path.join(self.bin, name)
            with open(path, "w") as fh:
                fh.write(text)
            os.chmod(path, 0o700)
        self.runtime = os.path.join(self.tmp, "runtime", "beta")
        os.makedirs(self.runtime)
        os.chmod(self.runtime, 0o700)
        self.log = os.path.join(self.tmp, "docker.log")

    def run_sh(self, script, *args, root=True, runtime=None, extra=None):
        env = {"PATH": self.bin + os.pathsep + os.environ["PATH"],
               "CRM_RUNTIME_DIR": runtime or self.runtime, "HOME": self.tmp,
               "CRM_TEST_ROOT": os.path.join(self.tmp, "runtime"),
               "REAL_STAT": shutil.which("stat"), "REAL_ID": shutil.which("id"),
               "FAKE_DOCKER_LOG": self.log,
               "FAKE_ROOT_DIR": os.path.join(self.tmp, "runtime") if root else "/nonexistent"}
        env.update(extra or {})
        return subprocess.run(["bash", os.path.join(SCRIPTS, script), *args],
                              capture_output=True, text=True, env=env, timeout=60)

    def docker_calls(self):
        return read(self.log).splitlines() if os.path.exists(self.log) else []


class TestTargetGuards(ShellEnv):
    GUARDED = ["backup.sh", "restore.sh", "export.sh", "deploy_custom.sh", "up.sh"]

    def test_unknown_targets_refused(self):
        for script in self.GUARDED:
            for args in ([], ["prod"], ["BETA"], ["beta "], ["staging"], [""]):
                with self.subTest(script=script, args=args):
                    res = self.run_sh(script, *args)
                    self.assertEqual(res.returncode, 2, res.stderr)
                    self.assertIn("must be 'dev' or 'beta'", res.stderr)
        self.assertEqual(self.docker_calls(), [])

    def test_beta_refuses_a_dev_runtime_and_a_non_private_runtime(self):
        dev = os.path.join(self.tmp, "runtime", "dev")
        os.makedirs(dev)
        for script in self.GUARDED:
            with self.subTest(script=script, case="dev runtime"):
                res = self.run_sh(script, "beta", runtime=dev)
                self.assertEqual(res.returncode, 2)
                self.assertIn("the beta runtime is " + self.runtime, res.stderr)
            with self.subTest(script=script, case="not root"):
                res = self.run_sh(script, "beta", root=False)
                self.assertEqual(res.returncode, 2)
                self.assertIn("owned by root with mode 0700", res.stderr)
        os.chmod(self.runtime, 0o750)
        res = self.run_sh("up.sh", "beta")
        self.assertEqual(res.returncode, 2)
        self.assertIn("mode 0700", res.stderr)
        self.assertEqual(self.docker_calls(), [])

    def test_beta_passes_the_guard_with_a_private_runtime(self):
        # Gets past the target guard and stops at the env-file check.
        res = self.run_sh("up.sh", "beta")
        self.assertEqual(res.returncode, 1, res.stderr)
        self.assertIn("env file not readable", res.stderr)

    def test_beta_uses_its_own_project_and_compose_file(self):
        code = (f". {SCRIPTS}/lib/common.sh; require_target beta; "
                'echo "$CRM_PROJECT $CRM_COMPOSE_FILE ${CRM_ENV_NAMES[*]}"')
        env = {"PATH": self.bin + os.pathsep + os.environ["PATH"], "CRM_RUNTIME_DIR": self.runtime,
               "CRM_TEST_ROOT": os.path.join(self.tmp, "runtime"),
               "REAL_STAT": shutil.which("stat"), "FAKE_ROOT_DIR": os.path.join(self.tmp, "runtime")}
        res = subprocess.run(["bash", "-c", code], capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, res.stderr)
        project, compose, *names = res.stdout.split()
        self.assertEqual(project, "crm-beta")
        self.assertEqual(compose, os.path.join(REPO, "deploy", "beta", "compose.json"))
        self.assertIn("CRM_BETA_APP_PORT", names)
        self.assertNotIn("CRM_ALLOWED_SOURCES", names)

    def test_export_beta_needs_an_explicit_base_url(self):
        res = self.run_sh("export.sh", "beta")
        self.assertEqual(res.returncode, 1)
        self.assertIn("CRM_BASE_URL", res.stderr)


class TestDbDirPerTarget(ShellEnv):
    """CRM_DB_DIR must be exactly $CRM_RUNTIME_DIR/db, in the env file and in
    the crm-db /var/lib/mysql bind Compose resolves, for both targets."""

    def setUp(self):
        super().setUp()
        import test_scripts
        with open(os.path.join(self.bin, "docker"), "w") as fh:
            fh.write(test_scripts.FAKE_DOCKER)
        self.cfg = os.path.join(self.tmp, "fake_compose_config.py")
        with open(self.cfg, "w") as fh:
            fh.write(test_scripts.FAKE_COMPOSE_CONFIG)
        self.dev = os.path.join(self.tmp, "runtime", "dev")
        os.makedirs(self.dev)
        for rt in (self.runtime, self.dev):
            self.write_env(rt)

    def write_env(self, runtime, db=None):
        with open(os.path.join(runtime, "env"), "w") as fh:
            fh.write(f"CRM_DB_DIR={db or runtime + '/db'}\nCRM_DATA_DIR={runtime}/data\n"
                     f"CRM_CUSTOM_DIR={runtime}/custom\nCRM_CLIENT_CUSTOM_DIR={runtime}/client/custom\n")
        os.chmod(os.path.join(runtime, "env"), 0o600)

    def paths(self, target, fake_config=""):
        runtime = self.runtime if target == "beta" else self.dev
        code = (f"set -euo pipefail; . {SCRIPTS}/lib/common.sh; require_target {target}; "
                "require_runtime_paths; echo PATHS-OK")
        env = {"PATH": self.bin + os.pathsep + os.environ["PATH"], "CRM_RUNTIME_DIR": runtime,
               "CRM_TEST_ROOT": os.path.join(self.tmp, "runtime"),
               "REAL_STAT": shutil.which("stat"), "FAKE_ROOT_DIR": os.path.join(self.tmp, "runtime"),
               "FAKE_DOCKER_LOG": self.log, "FAKE_COMPOSE_CONFIG": self.cfg,
               "FAKE_CONFIG": fake_config}
        return subprocess.run(["bash", "-c", code], capture_output=True, text=True, env=env)

    def test_control_both_targets_pass(self):
        for target in ("beta", "dev"):
            with self.subTest(target=target):
                res = self.paths(target)
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertIn("PATHS-OK", res.stdout)

    def test_beta_with_the_dev_db_is_refused(self):
        self.write_env(self.runtime, db=self.dev + "/db")
        res = self.paths("beta")
        self.assertEqual(res.returncode, 1)
        self.assertIn(f"CRM_DB_DIR in {self.runtime}/env is '{self.dev}/db'", res.stderr)
        self.assertEqual(self.docker_calls(), [])

    def test_dev_with_the_beta_db_is_refused(self):
        self.write_env(self.dev, db=self.runtime + "/db")
        res = self.paths("dev")
        self.assertEqual(res.returncode, 1)
        self.assertIn(f"CRM_DB_DIR in {self.dev}/env is '{self.runtime}/db'", res.stderr)
        self.assertEqual(self.docker_calls(), [])

    def test_missing_db_dir_is_refused(self):
        with open(os.path.join(self.runtime, "env"), "w") as fh:
            fh.write(f"CRM_DATA_DIR={self.runtime}/data\nCRM_CUSTOM_DIR={self.runtime}/custom\n"
                     f"CRM_CLIENT_CUSTOM_DIR={self.runtime}/client/custom\n")
        res = self.paths("beta")
        self.assertEqual(res.returncode, 1)
        self.assertIn("must set CRM_DB_DIR exactly once (found 0)", res.stderr)

    def test_compose_resolved_db_bind_is_checked(self):
        cases = {
            "beta": f"source:crm-db:/var/lib/mysql:{self.dev}/db",
            "dev": f"source:crm-db:/var/lib/mysql:{self.runtime}/db",
        }
        for target, mode in cases.items():
            for fake in (mode, "drop:crm-db:/var/lib/mysql", "type:crm-db:/var/lib/mysql:volume"):
                with self.subTest(target=target, fake=fake):
                    res = self.paths(target, fake)
                    self.assertEqual(res.returncode, 1, res.stderr)
                    self.assertIn("crm-db /var/lib/mysql", res.stderr)
                    self.assertNotIn("PATHS-OK", res.stdout)


class TestBetaRuntimePinned(ShellEnv):
    """CRM-007 r4: beta's runtime is the constant /srv/CRM/runtime/beta; the only
    seam is CRM_TEST_ROOT under /tmp. Dev is unchanged."""

    def test_python_guard(self):
        root = os.path.join(self.tmp, "runtime")
        self.assertEqual(ca.beta_runtime({}), (ca.BETA_DEFAULT_RUNTIME, None))
        self.assertEqual(ca.beta_runtime({"CRM_RUNTIME_DIR": ca.BETA_DEFAULT_RUNTIME}),
                         (ca.BETA_DEFAULT_RUNTIME, None))
        self.assertEqual(ca.beta_runtime({"CRM_TEST_ROOT": root}), (self.runtime, None))
        self.assertEqual(ca.beta_runtime({"CRM_TEST_ROOT": root, "CRM_RUNTIME_DIR": self.runtime}),
                         (self.runtime, None))
        refused = {
            "other runtime": {"CRM_RUNTIME_DIR": "/srv/CRM/other/beta"},
            "tmp runtime without seam": {"CRM_RUNTIME_DIR": self.runtime},
            "seam outside /tmp": {"CRM_TEST_ROOT": "/srv/CRM/runtime"},
            "seam is /tmp itself": {"CRM_TEST_ROOT": "/tmp/"},
            "seam with ..": {"CRM_TEST_ROOT": root + "/../../../../srv/CRM/runtime"},
            "seam missing": {"CRM_TEST_ROOT": root + "/nope"},
            "seam and other runtime": {"CRM_TEST_ROOT": root,
                                       "CRM_RUNTIME_DIR": ca.BETA_DEFAULT_RUNTIME},
        }
        link = os.path.join(self.tmp, "link")
        os.symlink(root, link)
        refused["seam via symlink"] = {"CRM_TEST_ROOT": link}
        for label, environ in refused.items():
            with self.subTest(case=label):
                runtime, problem = ca.beta_runtime(environ)
                self.assertIsNone(runtime)
                self.assertTrue(problem)
                err = io.StringIO()
                with unittest.mock.patch("sys.stderr", err):
                    self.assertEqual(ca.main(["beta"], environ), 2)
                self.assertIn("refusing to run", err.getvalue())

    def shell(self, target, environ):
        code = (f"set -euo pipefail; . {SCRIPTS}/lib/common.sh; require_target {target}; "
                'echo "RUNTIME=$CRM_RUNTIME_DIR"')
        env = {"PATH": self.bin + os.pathsep + os.environ["PATH"], "REAL_STAT": shutil.which("stat"),
               "FAKE_ROOT_DIR": os.path.join(self.tmp, "runtime"), **environ}
        return subprocess.run(["bash", "-c", code], capture_output=True, text=True, env=env)

    def test_shell_guard(self):
        root = os.path.join(self.tmp, "runtime")
        res = self.shell("beta", {"CRM_TEST_ROOT": root})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn(f"RUNTIME={self.runtime}", res.stdout)
        # No seam: the constant (absent in the sandbox, so the private-runtime guard names it).
        res = self.shell("beta", {})
        self.assertEqual(res.returncode, 2)
        self.assertIn("/srv/CRM/runtime/beta", res.stderr)
        for label, environ in {
                "tmp runtime without seam": {"CRM_RUNTIME_DIR": self.runtime},
                "other runtime": {"CRM_RUNTIME_DIR": "/srv/CRM/other/beta"},
                "seam outside /tmp": {"CRM_TEST_ROOT": "/srv/CRM/runtime"},
                "seam with ..": {"CRM_TEST_ROOT": root + "/../../../../srv/CRM/runtime"},
                "seam missing": {"CRM_TEST_ROOT": root + "/nope"}}.items():
            with self.subTest(case=label):
                res = self.shell("beta", environ)
                self.assertEqual(res.returncode, 2, res.stdout)
                self.assertIn("refusing to run", res.stderr)
                self.assertNotIn("RUNTIME=", res.stdout)
        # dev is unchanged: CRM_RUNTIME_DIR is honoured without any seam.
        dev = os.path.join(self.tmp, "elsewhere", "dev")
        res = self.shell("dev", {"CRM_RUNTIME_DIR": dev})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn(f"RUNTIME={dev}", res.stdout)


class BetaStackEnv(ShellEnv):
    """A full beta runtime (env file with paths and edge values) and the fake
    docker from test_scripts, so up.sh beta runs to `compose up`."""

    def setUp(self):
        super().setUp()
        import test_scripts
        with open(os.path.join(self.bin, "docker"), "w") as fh:
            fh.write(test_scripts.FAKE_DOCKER)
        self.cfg_script = os.path.join(self.tmp, "fake_compose_config.py")
        with open(self.cfg_script, "w") as fh:
            fh.write(test_scripts.FAKE_COMPOSE_CONFIG)
        self.write_env()
        self.edge_cfg = os.path.join(self.runtime, "edge", "haproxy.cfg")

    def write_env(self, **over):
        rt = self.runtime
        with open(os.path.join(rt, "env"), "w") as fh:
            fh.write(f"CRM_DB_DIR={rt}/db\nCRM_DATA_DIR={rt}/data\nCRM_CUSTOM_DIR={rt}/custom\n"
                     f"CRM_CLIENT_CUSTOM_DIR={rt}/client/custom\n" + env_text(**over))
        os.chmod(os.path.join(rt, "env"), 0o600)

    def run_beta(self, script, *args, extra=None):
        return self.run_sh(script, "beta", *args,
                           extra={"FAKE_COMPOSE_CONFIG": self.cfg_script, **(extra or {})})

    def check(self):
        err = io.StringIO()
        environ = {"CRM_TEST_ROOT": os.path.join(self.tmp, "runtime"), "CRM_RUNTIME_DIR": self.runtime}
        with unittest.mock.patch("sys.stderr", err), unittest.mock.patch("sys.stdout", io.StringIO()):
            code = ca.main(["beta"], environ)
        return code, err.getvalue()


class TestEdgeRevalidation(BetaStackEnv):
    def recreates(self):
        return [c for c in self.docker_calls() if "--force-recreate" in c]

    def test_check_without_render_compares_byte_for_byte(self):
        code, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn("is not readable", err)  # missing: fail closed
        os.makedirs(os.path.dirname(self.edge_cfg))
        with open(self.edge_cfg, "w") as fh:
            fh.write(rendered())
        self.assertEqual(self.check(), (0, ""))
        good = read(self.edge_cfg)
        for label, text in {"one byte more": good + "\n", "one byte less": good[:-1],
                            "comment added": "# hi\n" + good, "empty": "",
                            "CRLF": good.replace("\n", "\r\n")}.items():
            with self.subTest(case=label):
                with open(self.edge_cfg, "w", newline="") as fh:
                    fh.write(text)
                code, err = self.check()
                self.assertEqual(code, 1)
                self.assertIn("differs from the one rendered", err)
        with open(self.edge_cfg, "w") as fh:
            fh.write(good)
        self.write_env(CRM_BETA_PORT="8444")  # env changed, edge not re-rendered
        code, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn("differs from the one rendered", err)
        os.unlink(self.edge_cfg)
        elsewhere = os.path.join(self.tmp, "copy.cfg")
        with open(elsewhere, "w") as fh:
            fh.write(rendered(CRM_BETA_PORT="8444"))
        os.symlink(elsewhere, self.edge_cfg)  # right bytes, but a symlink
        code, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn("is not readable", err)

    def test_other_scripts_refuse_a_stale_edge_config(self):
        os.makedirs(os.path.dirname(self.edge_cfg))
        with open(self.edge_cfg, "w") as fh:
            fh.write(rendered(CRM_BETA_PORT="9443"))
        res = self.run_beta("deploy_custom.sh")
        self.assertEqual(res.returncode, 1)
        self.assertIn("differs from the one rendered", res.stderr)
        self.assertFalse([c for c in self.docker_calls() if " up " in f" {c} "])

    def test_up_rerenders_and_recreates_the_edge_only_on_change(self):
        res = self.run_beta("up.sh")  # first run: rendered from nothing
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(read(self.edge_cfg), rendered())
        calls = self.docker_calls()
        ups = [i for i, c in enumerate(calls) if c.endswith(" up -d --wait")]
        recreate = [i for i, c in enumerate(calls)
                    if c.endswith(" up -d --wait --force-recreate --no-deps crm-beta-edge")]
        self.assertEqual(len(ups), 1, calls)
        self.assertEqual(len(recreate), 1, calls)
        self.assertLess(ups[0], recreate[0])
        self.assertIn("-p crm-beta", calls[recreate[0]])
        self.assertEqual(self.check(), (0, ""))

        os.unlink(self.log)  # unchanged: no recreate
        res = self.run_beta("up.sh")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.recreates(), [])

        os.unlink(self.log)  # env changed: re-rendered and recreated
        self.write_env(CRM_BETA_PORT="8444")
        res = self.run_beta("up.sh")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(read(self.edge_cfg), rendered(CRM_BETA_PORT="8444"))
        self.assertEqual(len(self.recreates()), 1)

        os.unlink(self.log)  # tampered on disk: re-rendered and recreated
        with open(self.edge_cfg, "a") as fh:
            fh.write("listen evil\n")
        res = self.run_beta("up.sh")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(read(self.edge_cfg), rendered(CRM_BETA_PORT="8444"))
        self.assertEqual(len(self.recreates()), 1)

    def test_up_with_invalid_edge_values_neither_renders_nor_starts(self):
        self.write_env(CRM_BETA_UPSTREAM_SOURCES="0.0.0.0/0")
        res = self.run_beta("up.sh")
        self.assertEqual(res.returncode, 1)
        self.assertFalse(os.path.exists(self.edge_cfg))
        self.assertFalse([c for c in self.docker_calls() if " up " in f" {c} "])


# Stands in for export_csv.py (records its arguments); check_access.py runs for real.
FAKE_EXPORT_PY = """#!/usr/bin/env bash
case "$1" in */export_csv.py) echo "EXPORT $*"; exit 0 ;; esac
exec "$REAL_PY" "$@"
"""


class TestExportBetaBaseUrl(BetaStackEnv):
    def export(self, url, *args):
        extra = {"CRM_ADMIN_USERNAME": "u", "CRM_ADMIN_PASSWORD": "p", "REAL_PY": sys.executable}
        if url is not None:
            extra["CRM_BASE_URL"] = url
        fake_py = os.path.join(self.bin, "python3")
        with open(fake_py, "w") as fh:
            fh.write(FAKE_EXPORT_PY)
        os.chmod(fake_py, 0o700)
        return self.run_beta("export.sh", *args, extra=extra)

    def test_base_url_must_be_the_env_files_app_port(self):
        res = self.export("http://127.0.0.1:8280")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("EXPORT", res.stdout)
        self.assertIn(" beta --base-url http://127.0.0.1:8280 --out ", res.stdout)
        for url in (None, "", "http://127.0.0.1:8180", "http://127.0.0.1:8280/",
                    "https://127.0.0.1:8280", "http://localhost:8280", f"http://{BIND}:8280",
                    "http://127.0.0.1:8443", "http://127.0.0.1:08280"):
            with self.subTest(url=url):
                res = self.export(url)
                self.assertEqual(res.returncode, 1, res.stdout)
                self.assertIn("CRM_BASE_URL", res.stderr)
                self.assertNotIn("EXPORT", res.stdout)

    def test_app_port_must_be_set_once(self):
        # CRM-007R: read through check_access.pinned_base_url, as provisioning
        # does (which, like Compose, unquotes a quoted value).
        env = os.path.join(self.runtime, "env")
        base = read(env)
        for label, text in {
                "missing": base.replace("CRM_BETA_APP_PORT=8280\n", ""),
                "twice": base + "CRM_BETA_APP_PORT=8280\n",
                "exported": base.replace("CRM_BETA_APP_PORT=8280", "export CRM_BETA_APP_PORT=8280"),
                "low port": base.replace("CRM_BETA_APP_PORT=8280", "CRM_BETA_APP_PORT=80")}.items():
            with self.subTest(case=label):
                with open(env, "w") as fh:
                    fh.write(text)
                port = "80" if label == "low port" else "8280"
                res = self.export(f"http://127.0.0.1:{port}")
                self.assertEqual(res.returncode, 1, res.stdout)
                self.assertIn("CRM_BETA_APP_PORT", res.stderr)
                self.assertNotIn("EXPORT", res.stdout)
        os.unlink(env)
        res = self.export("http://127.0.0.1:8280")
        self.assertEqual(res.returncode, 1)
        self.assertIn("env file not readable", res.stderr)


class TestSeedingRefusesBeta(unittest.TestCase):
    def test_beta_urls_and_target_refused(self):
        for url, env in (("https://crm-beta.example.invalid", {}),
                         ("http://127.0.0.1:8280", {}),
                         ("http://127.0.0.1:8180", {"CRM_TARGET": "beta"})):
            with self.subTest(url=url, env=env):
                out = io.StringIO()
                with unittest.mock.patch("sys.stderr", out):
                    code = seed_synthetic.main(["--base-url", url, "--dry-run"], environ=env)
                self.assertEqual(code, 2)
                self.assertIn("refusing to run", out.getvalue())

    def test_dev_url_still_allowed(self):
        with unittest.mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(seed_synthetic.main(["--base-url", "http://127.0.0.1:8180",
                                                  "--dry-run"], environ={}), 0)


def rewrite_bundle(path, change):
    """Rebuild the bundle with change(name, data) -> data|None applied
    (RELEASE.json last, so rehash() sees every other change first)."""
    with tarfile.open(path) as tar:
        members = [(m, tar.extractfile(m).read() if m.isfile() else None)
                   for m in tar.getmembers()]
    new = {}
    for m, data in sorted(members, key=lambda e: e[0].name.endswith("/RELEASE.json")):
        new[m.name] = change(m.name, data) if data is not None else None
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as tar:
        for m, _ in members:
            data = new[m.name]
            if m.isfile() and data is None:
                continue
            if data is not None:
                m.size = len(data)
            tar.addfile(m, io.BytesIO(data) if data is not None else None)
    with open(path, "wb") as fh:
        fh.write(raw.getvalue())


def rehash(change):
    """change(name, data) plus a consistently re-hashed RELEASE.json."""
    pending = {}
    def wrapped(name, data):
        if name.endswith("/RELEASE.json"):
            m = json.loads(data)
            for rel, new in pending.items():
                m["files"][rel] = release.sha256(new)
            return (json.dumps(m, indent=2, sort_keys=True) + "\n").encode()
        new = change(name, data)
        if new != data:
            pending[name.split("/", 1)[1]] = new
        return new
    return wrapped


def make_repo(root):
    def git(*args):
        subprocess.run(["git", "-C", root, *args], check=True, capture_output=True,
                       env={**os.environ, "GIT_AUTHOR_DATE": "2026-11-10T12:00:00Z",
                            "GIT_COMMITTER_DATE": "2026-11-10T12:00:00Z",
                            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    os.makedirs(root)
    git("init", "-q", "-b", "main")
    git("config", "user.name", "t")
    git("config", "user.email", "t@example.invalid")
    for rel in ("security/EXTERNAL_CODE_REGISTER.yaml", "deploy/compose.json",
                "deploy/beta/compose.json", "scripts/release.py"):
        dst = os.path.join(root, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(os.path.join(REPO, rel), dst)
    os.makedirs(os.path.join(root, ".forge", "CRM-003"))
    with open(os.path.join(root, ".forge", "CRM-003", "REPORT.md"), "w") as fh:
        fh.write("record\n")
    git("add", "-A")
    git("commit", "-q", "-m", "accepted")
    git("checkout", "-q", "-b", "side")
    with open(os.path.join(root, "x.txt"), "w") as fh:
        fh.write("unaccepted\n")
    git("add", "-A")
    git("commit", "-q", "-m", "side")
    return lambda *a: subprocess.run(["git", "-C", root, *a], capture_output=True,
                                     text=True).stdout.strip()


class TestReleaseBundle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        self.git = make_repo(self.repo)
        self.commit = self.git("rev-parse", "main")

    def build(self, sub, commit=None):
        out = os.path.join(self.tmp, sub)
        os.makedirs(out, exist_ok=True)
        return release.build(self.repo, commit or self.commit, out)

    def test_verify_tree_refuses_setuid_setgid_and_writable_modes(self):
        """CRM-007 r4: verify-tree refuses on disk what verify refuses in the tar."""
        path, _ = self.build("vt")
        with open(path, "rb") as fh:
            sha = release.sha256(fh.read())
        tree = os.path.join(self.tmp, "tree")
        os.mkdir(tree)
        with tarfile.open(path) as tar:
            tar.extractall(tree, filter="data")
        (top,) = os.listdir(tree)
        root = os.path.join(tree, top)
        release.verify_tree(root, path, sha)  # control: clean modes pass
        target = os.path.join(root, "scripts", "release.py")
        subdir = os.path.join(root, "scripts")
        for label, where, mode in (("setuid file", target, 0o4644), ("setgid file", target, 0o2644),
                                   ("world-writable file", target, 0o646),
                                   ("group-writable file", target, 0o664),
                                   ("sticky file", target, 0o1644),
                                   ("world-writable dir", subdir, 0o777),
                                   ("setgid dir", subdir, 0o2755)):
            with self.subTest(case=label):
                original = stat.S_IMODE(os.stat(where).st_mode)
                os.chmod(where, mode)
                try:
                    if stat.S_IMODE(os.stat(where).st_mode) != mode:
                        self.skipTest(f"the filesystem would not set {oct(mode)}")
                    with self.assertRaises(release.ReleaseError) as cm:
                        release.verify_tree(root, path, sha)
                    self.assertIn("setuid/setgid/sticky or writable-by-others", str(cm.exception))
                finally:
                    os.chmod(where, original)
        release.verify_tree(root, path, sha)

    def test_reproducible_byte_for_byte_and_verifies(self):
        a, manifest = self.build("a")
        b, _ = self.build("b")
        with open(a, "rb") as fa, open(b, "rb") as fb:
            self.assertEqual(fa.read(), fb.read())
        self.assertEqual(os.path.basename(a), f"crm-release-{self.commit[:12]}.tar.gz")
        got = release.verify(a)
        self.assertEqual(got["commit"], self.commit)
        self.assertEqual(set(got["images"]), {"espocrm", "mariadb", "haproxy"})
        self.assertIsNotNone(got["delivery_records"]["CRM-003"])
        self.assertIn("scripts/release.py", got["files"])

    def test_forge_records_excluded_but_listed_by_sha(self):
        path, manifest = self.build("f")
        self.assertEqual(manifest["excluded"], [".forge/"])
        self.assertFalse([n for n in manifest["files"] if n.startswith(".forge")])
        with tarfile.open(path) as tar:
            self.assertFalse([n for n in tar.getnames() if "/.forge" in n])
        self.assertRegex(manifest["delivery_records"]["CRM-003"], r"^[0-9a-f]{40}$")
        self.assertEqual(release.verify(path)["excluded"], [".forge/"])

    def test_gzip_header_has_no_timestamp_whatever_the_clock(self):
        with unittest.mock.patch("time.time", return_value=1_000_000_000.0):
            a, _ = self.build("clock1")
        with unittest.mock.patch("time.time", return_value=2_000_000_000.0):
            b, _ = self.build("clock2")
        with open(a, "rb") as fa, open(b, "rb") as fb:
            da, db = fa.read(), fb.read()
        self.assertEqual(da[4:8], b"\0\0\0\0")
        self.assertEqual(da, db)

    def test_unaccepted_commit_refused(self):
        with self.assertRaises(release.ReleaseError):
            self.build("c", self.git("rev-parse", "side"))

    def rewrite(self, path, change):
        rewrite_bundle(path, change)

    def test_tampered_file_refused(self):
        path, _ = self.build("t")
        self.rewrite(path, lambda n, d: d + b"\n" if n.endswith("deploy/compose.json") else d)
        with self.assertRaisesRegex(release.ReleaseError, "digest mismatch"):
            release.verify(path)

    def test_added_or_removed_file_refused(self):
        path, _ = self.build("r")
        self.rewrite(path, lambda n, d: None if n.endswith("scripts/release.py") else d)
        with self.assertRaisesRegex(release.ReleaseError, "member set"):
            release.verify(path)

    def test_wrong_image_digest_refused(self):
        path, _ = self.build("w")
        def change(name, data):
            if name.endswith("RELEASE.json"):
                m = json.loads(data)
                m["images"]["haproxy"] = "sha256:" + "0" * 64
                return json.dumps(m).encode()
            return data
        self.rewrite(path, change)
        with self.assertRaisesRegex(release.ReleaseError, "image digests"):
            release.verify(path)

    def test_compose_digest_must_be_in_the_register(self):
        # Consistent RELEASE.json (file digests re-hashed), but a compose image
        # digest the register does not list.
        path, _ = self.build("cd")
        bad = "sha256:" + "1" * 64
        self.rewrite(path, rehash(lambda n, d: d.replace(
            b"sha256:d1891ede5a559f1086f55053bb8cc1569b0298338c4d72d71725a7f74f6ba620",
            bad.encode()) if n.endswith("/deploy/beta/compose.json") else d))
        with self.assertRaisesRegex(release.ReleaseError, "compose image digest is not in the register"):
            release.verify(path)

    def test_excluded_must_be_recorded(self):
        path, _ = self.build("ex")
        def change(name, data):
            if name.endswith("RELEASE.json"):
                m = json.loads(data)
                m.pop("excluded")
                return json.dumps(m).encode()
            return data
        self.rewrite(path, change)
        with self.assertRaisesRegex(release.ReleaseError, "excluded"):
            release.verify(path)

    def test_verify_without_sha256_warns_not_anchored(self):
        path, _ = self.build("wa")
        err = io.StringIO()
        with unittest.mock.patch("sys.stderr", err), unittest.mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(release.main(["verify", path]), 0)
        self.assertIn("NOT ANCHORED", err.getvalue())
        with open(path, "rb") as fh:
            digest = release.sha256(fh.read())
        err = io.StringIO()
        with unittest.mock.patch("sys.stderr", err), unittest.mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(release.main(["verify", path, "--sha256", digest]), 0)
        self.assertNotIn("NOT ANCHORED", err.getvalue())
        for bad in (digest.upper(), digest[:-1], digest + "0", ""):
            with self.subTest(sha=bad), self.assertRaises(release.ReleaseError):
                release.verify(path, bad)

    def test_wrong_bundle_digest_refused(self):
        path, _ = self.build("s")
        with self.assertRaisesRegex(release.ReleaseError, "sha256"):
            release.verify(path, "0" * 64)

    def test_release_sh_refuses_without_commit(self):
        res = subprocess.run(["bash", os.path.join(SCRIPTS, "release.sh")], capture_output=True,
                             text=True)
        self.assertEqual(res.returncode, 2)


def DEPLOY_INPUTS(tmp):  # noqa: N802
    """CRM-007R: the inputs deploy_release.sh requires before it starts."""
    return {"CRM_ADMIN_USERNAME": "a", "CRM_ADMIN_PASSWORD": "p",
            "CRM_PROVISION_KEY_FILE": os.path.join(tmp, "new-key.env")}


class TestDeployRelease(ShellEnv):
    def setUp(self):
        super().setUp()
        repo = os.path.join(self.tmp, "repo")
        git = make_repo(repo)
        out = os.path.join(self.tmp, "out")
        os.mkdir(out)
        self.bundle, _ = release.build(repo, git("rev-parse", "main"), out)
        self.sha = self.digest(self.bundle)
        env = os.path.join(self.runtime, "env")
        with open(env, "w") as fh:
            fh.write(env_text())
        os.chmod(env, 0o600)

    @staticmethod
    def digest(path):
        with open(path, "rb") as fh:
            return release.sha256(fh.read())

    def deploy(self, *extra, sha=True, env=None, **kw):
        args = ["--sha256", self.sha] if sha is True else (["--sha256", sha] if sha else [])
        if "--upgrade" in extra:  # CRM-007R: an upgrade needs the existing API key file
            key = os.path.join(self.tmp, "existing-key.env")
            open(key, "a").close()
            env = {"CRM_BETA_SAFE_KEY_FILE": key, **(env or {})}
        return self.run_sh("deploy_release.sh", "beta", self.bundle, *args, *extra,
                           extra={"FAKE_UID": "0", "TMPDIR": self.tmp, **DEPLOY_INPUTS(self.tmp),
                                  **(env or {})}, **kw)

    def deploy_dir(self):
        short = os.path.basename(self.bundle)[len("crm-release-"):-len(".tar.gz")]
        return os.path.join(self.tmp, "runtime", "deploy", short)

    def assert_nothing_done(self, res):
        self.assertNotEqual(res.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "runtime", "deploy")))
        self.assertEqual(self.docker_calls(), [])
        self.assertEqual(sorted(os.listdir(self.runtime)), ["env"])
        self.assertFalse([n for n in os.listdir(self.tmp) if n.startswith("crm-deploy-")],
                         "private staging directory removed")

    def make_writable(self):
        for root, dirs, _ in os.walk(os.path.join(self.tmp, "runtime", "deploy")):
            os.chmod(root, 0o755)

    def test_sha256_is_mandatory_and_well_formed(self):
        for sha in (None, "", "0" * 63, "0" * 65, self.sha.upper(), "g" * 64, self.sha + " "):
            with self.subTest(sha=sha):
                res = self.deploy(sha=sha) if sha is not None else self.deploy(sha=False)
                self.assert_nothing_done(res)
                self.assertIn("--sha256 HEX", res.stderr)

    def test_rehashed_bundle_refused_without_or_with_a_wrong_sha256(self):
        # Change a file and re-hash RELEASE.json consistently: release.py verify
        # (unanchored) accepts it, so only the outside digest can catch it.
        rewrite_bundle(self.bundle, rehash(
            lambda n, d: d + b"\n# tampered\n" if n.endswith("/scripts/release.py") else d))
        release.verify(self.bundle)  # consistent: passes unanchored
        res = self.deploy(sha=False)
        self.assert_nothing_done(res)
        self.assertIn("--sha256 HEX", res.stderr)
        res = self.deploy()  # the release record's digest of the original bundle
        self.assert_nothing_done(res)
        self.assertIn("does not match --sha256", res.stderr)
        # With the tampered bundle's own digest, the operator vouches for it: it proceeds.
        res = self.deploy(sha=self.digest(self.bundle))
        self.assertTrue(os.path.isfile(os.path.join(self.deploy_dir(), "RELEASE.json")), res.stderr)
        self.make_writable()

    def test_right_sha256_proceeds(self):
        res = self.deploy()
        self.assertNotIn("does not match", res.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.deploy_dir(), "RELEASE.json")), res.stderr)
        self.make_writable()

    def test_unpacked_tree_is_rechecked(self):
        # A tar that adds a file while unpacking: the post-unpack check refuses.
        fake_tar = os.path.join(self.bin, "tar")
        with open(fake_tar, "w") as fh:
            fh.write('#!/usr/bin/env bash\n"$REAL_TAR" "$@" || exit\n'
                     'dir=; prev=; for a in "$@"; do [ "$prev" = -C ] && dir=$a; prev=$a; done\n'
                     'for d in "$dir"/crm-release-*; do echo x > "$d/${FAKE_TAR_FILE:-extra.txt}"; done\n')
        os.chmod(fake_tar, 0o700)
        for name in ("extra.txt", "README-unlisted", "RELEASE.json"):
            with self.subTest(planted=name):
                res = self.deploy(env={"REAL_TAR": shutil.which("tar"), "FAKE_TAR_FILE": name})
                self.assertEqual(res.returncode, 1, res.stderr)
                self.assertIn("unpacked files differ from the bundle", res.stderr)
                self.assertFalse(os.path.exists(self.deploy_dir()))
                self.assertEqual(os.listdir(os.path.join(self.tmp, "runtime", "deploy")), [])
                self.assertEqual(self.docker_calls(), [])

    def test_upgrade_rechecks_an_existing_release_dir(self):
        self.deploy()
        dest = self.deploy_dir()
        self.assertTrue(os.path.isdir(dest))
        self.make_writable()
        res = self.deploy("--upgrade")  # untouched: the check passes
        self.assertNotIn("differs from the bundle", res.stderr)
        self.assertNotIn("already exists", res.stderr)
        rel = os.path.join(dest, "scripts", "release.py")
        os.chmod(rel, 0o644)
        cases = {
            "extra file": lambda: open(os.path.join(dest, "extra"), "w").close(),
            "extra dir": lambda: os.mkdir(os.path.join(dest, "extra.d")),
            "changed file": lambda: open(rel, "a").write("# changed\n"),
            "missing file": lambda: os.unlink(rel),
            "symlink": lambda: os.symlink("/etc/passwd", os.path.join(dest, "link")),
        }
        for name, change in cases.items():
            with self.subTest(case=name):
                saved = read(rel) if os.path.exists(rel) else None
                change()
                res = self.deploy("--upgrade")
                self.assertEqual(res.returncode, 1, res.stderr)
                self.assertIn("differs from the bundle's RELEASE.json", res.stderr)
                for extra in ("extra", "link"):
                    if os.path.lexists(os.path.join(dest, extra)):
                        os.unlink(os.path.join(dest, extra))
                if os.path.isdir(os.path.join(dest, "extra.d")):
                    os.rmdir(os.path.join(dest, "extra.d"))
                if saved is not None:
                    with open(rel, "w") as fh:
                        fh.write(saved)
                else:
                    with open(rel, "w") as fh:
                        fh.write(read(os.path.join(REPO, "scripts", "release.py")))

    def test_non_empty_runtime_refused_without_upgrade(self):
        os.mkdir(os.path.join(self.runtime, "data"))
        res = self.deploy()
        self.assertEqual(res.returncode, 1, res.stderr)
        self.assertIn("is not empty", res.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "runtime", "deploy")))
        self.assertEqual(self.docker_calls(), [])

    def test_tampered_bundle_refused_before_anything(self):
        with open(self.bundle, "ab") as fh:
            fh.write(b"x")
        res = self.deploy()
        self.assert_nothing_done(res)
        self.assertIn("does not match --sha256", res.stderr)
        res = self.deploy(sha=self.digest(self.bundle))  # anchored to the tampered bytes
        self.assert_nothing_done(res)
        self.assertIn("failed verification", res.stderr)

    def test_wrong_target_not_root_and_bad_runtime_refused(self):
        res = self.run_sh("deploy_release.sh", "dev", self.bundle, extra={"FAKE_UID": "0"})
        self.assertEqual(res.returncode, 2)
        res = self.run_sh("deploy_release.sh", "beta", self.bundle, "--sha256", self.sha,
                          extra={"FAKE_UID": "1000"})
        self.assertIn("must run as root", res.stderr)
        res = self.deploy(root=False)
        self.assertIn("owned by root with mode 0700", res.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "runtime", "deploy")))

    def test_empty_runtime_passes_the_emptiness_check_and_unpacks(self):
        # The minimal test repo has no scripts beyond release.py, so the deploy
        # stops at the first bundled script; everything before it is checked.
        res = self.deploy()
        dest = self.deploy_dir()
        self.assertTrue(os.path.isfile(os.path.join(dest, "RELEASE.json")), res.stderr)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(dest, "RELEASE.json")).st_mode) & 0o222, 0)
        for d in ("db", "data", "custom", "client/custom", "backups"):
            self.assertTrue(os.path.isdir(os.path.join(self.runtime, d)), d)
        self.assertNotIn("is not empty", res.stderr)
        for root, dirs, _ in os.walk(dest):
            os.chmod(root, 0o755)  # let the cleanup remove the read-only tree


# --- CRM-007 r2: crm-app HTTPS policy -------------------------------------------------

class TestProxyHttpsPolicy(unittest.TestCase):
    def conf(self):
        with open(ca.PROXY_CONF_PATH) as fh:
            return fh.read()

    def test_repository_conf_passes_and_is_part_of_the_beta_check(self):
        self.assertEqual(ca.check_proxy_conf(self.conf()), [])
        self.assertEqual(ca.check_beta(env_text(), {})[0], [])

    def test_https_is_unconditional_and_the_header_is_dropped(self):
        lines = [l.strip() for l in self.conf().splitlines() if l.strip() and not l.startswith("#")]
        self.assertIn("SetEnv HTTPS on", lines)
        self.assertIn("RequestHeader unset X-Forwarded-Proto", lines)
        self.assertFalse(any(l.startswith("<If ") or l.startswith("SetEnvIf") for l in lines))

    def test_broken_confs_are_refused(self):
        good = self.conf()
        on, unset = "SetEnv HTTPS on", "RequestHeader unset X-Forwarded-Proto"
        fixtures = {
            "no SetEnv": good.replace(on + "\n", ""),
            "HTTPS off": good.replace(on, "SetEnv HTTPS off"),
            "SetEnv twice": good.replace(on, on + "\n" + on),
            "peer-conditional (round 1)": good.replace(
                on, "<If \"-R '127.0.0.0/8'\">\n    SetEnv HTTPS on\n</If>"),
            "header-conditional": good.replace(on, 'SetEnvIf X-Forwarded-Proto "^https$" HTTPS=on'),
            "header kept": good.replace(unset + "\n", ""),
            "header set": good.replace(unset, "RequestHeader set X-Forwarded-Proto http"),
            "silent IfModule": good.replace(unset, "<IfModule mod_headers.c>\n" + unset + "\n</IfModule>"),
            "other module loaded": good.replace("mod_env.so", "mod_remoteip.so"),
            "extra directive in block": good.replace(
                "<IfModule !env_module>", "<IfModule !env_module>\n    SetEnv HTTPS on"),
            "remoteip": good + "RemoteIPHeader X-Forwarded-For\n",
            "unclosed": good.replace("</IfModule>", "", 1),
        }
        for name, text in fixtures.items():
            with self.subTest(fixture=name):
                self.assertNotEqual(text, good)
                self.assertNotEqual(ca.check_proxy_conf(text), [])

    def test_beta_check_refuses_a_broken_conf(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "crm-proxy.conf")
            with open(bad, "w") as fh:
                fh.write(self.conf().replace("SetEnv HTTPS on\n", ""))
            errors, cfg = ca.check_beta(env_text(), {}, proxy_conf_path=bad)
            self.assertTrue(any("SetEnv HTTPS on" in e for e in errors), errors)
            self.assertIsNone(cfg)


# --- CRM-007 r2: beta-safe acceptance suite (GET only) -------------------------------

sys.path.insert(0, os.path.join(REPO, "tests", "acceptance"))
import test_beta_safe as bs  # noqa: E402

KEY = "NOT-A-REAL-BETA-KEY"
ROLE_NAMES = bs.role_names()


class FakeBetaEspo:
    """Answers only GETs a live crm-beta would; records every request."""

    def __init__(self, phone=False, site="https://crm-beta.example.invalid", markers=0,
                 roles=None, role_status=200, settings_extra=None):
        self.methods, self.paths = [], []
        self.phone, self.site, self.markers = phone, site, markers
        self.roles = ROLE_NAMES if roles is None else roles
        self.role_status = role_status
        self.settings_extra = settings_extra or {}

    def request(self, method, url, headers, body):
        parts = urllib.parse.urlsplit(url)
        path = parts.path.split("/api/v1/", 1)[1]
        self.methods.append(method)
        self.paths.append(path)
        if headers.get("X-Api-Key") != KEY:
            return 401, b""
        if method != "GET" or body is not None:
            return 405, b""
        q = urllib.parse.parse_qs(parts.query)
        if path == "App/user":
            return 200, json.dumps({"user": {"id": "u1", "type": "api"}}).encode()
        if path == "Settings":
            s = {"siteUrl": self.site}
            if self.phone is not None:
                s["phoneNumberInternational"] = self.phone
            s.update(self.settings_extra)
            return 200, json.dumps(s).encode()
        if path == "Role":
            if self.role_status != 200:
                return self.role_status, b'{"message":"forbidden"}'
            name = q["where[0][value]"][0]
            n = 1 if name in self.roles else 0
            return 200, json.dumps({"total": n, "list": [{"id": "r"}][:n]}).encode()
        if path == "Account":
            assert q["where[0][type]"] == ["contains"] and q["where[0][value]"] == [bs.SEED_MARKER]
            assert q["select"] == ["id"]
            return 200, json.dumps({"total": self.markers,
                                    "list": [{"id": "a"}][:self.markers]}).encode()
        return 404, b""


class TestBetaSafeSuite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.key_file = self.write_key(f"CRM_IMPORT_USERNAME=er-import\nCRM_IMPORT_API_KEY={KEY}\n")
        self.addCleanup(setattr, bs, "TRANSPORT", None)
        self.addCleanup(setattr, bs, "CLIENT", None)

    def write_key(self, text, name="key.env", mode=0o600):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as fh:
            fh.write(text)
        os.chmod(path, mode)
        return path

    def run_suite(self, fake, environ=None):
        env = {"CRM_BASE_URL": "http://127.0.0.1:8280", bs.ENV_KEY_FILE: self.key_file}
        env = env if environ is None else environ
        bs.TRANSPORT = fake
        out = io.StringIO()
        with unittest.mock.patch.dict(os.environ, env, clear=False):
            for k in ("CRM_BASE_URL", bs.ENV_KEY_FILE):
                if k not in env:
                    os.environ.pop(k, None)
            suite = unittest.defaultTestLoader.loadTestsFromModule(bs)
            result = unittest.TextTestRunner(stream=out, verbosity=2).run(suite)
        # The GET-only guarantee: whatever the outcome, nothing but GET was sent.
        self.assertEqual(set(fake.methods) - {"GET"}, set(), fake.methods)
        self.assertNotIn(KEY, out.getvalue())
        return result, out.getvalue()

    def failed(self, result):
        return sorted(t.id().rsplit(".", 1)[1] for t, _ in result.failures + result.errors)

    def test_healthy_beta_passes_with_get_only(self):
        fake = FakeBetaEspo()
        result, _ = self.run_suite(fake)
        self.assertTrue(result.wasSuccessful(), result.failures + result.errors)
        self.assertEqual((result.testsRun, len(result.skipped)), (5, 0))
        self.assertEqual(set(fake.methods), {"GET"})
        for p in ("App/user", "Settings", "Role", "Account"):
            self.assertIn(p, fake.paths)

    def test_each_check_fails_on_its_defect(self):
        cases = {
            "string false": (FakeBetaEspo(phone="false"), "test_phone_number_international_is_false"),
            "true": (FakeBetaEspo(phone=True), "test_phone_number_international_is_false"),
            "zero": (FakeBetaEspo(phone=0), "test_phone_number_international_is_false"),
            "missing": (FakeBetaEspo(phone=None), "test_phone_number_international_is_false"),
            "http site": (FakeBetaEspo(site="http://crm-beta.example.invalid"),
                          "test_site_url_uses_https"),
            "no site": (FakeBetaEspo(site=None), "test_site_url_uses_https"),
            "marker": (FakeBetaEspo(markers=3), "test_no_synthetic_seed_marker"),
            "role missing": (FakeBetaEspo(roles=ROLE_NAMES[1:]), "test_roles_from_config_exist"),
            "role forbidden": (FakeBetaEspo(role_status=403), "test_roles_from_config_exist"),
        }
        for name, (fake, test) in cases.items():
            with self.subTest(case=name):
                result, out = self.run_suite(fake)
                self.assertEqual(self.failed(result), [test], out)

    def test_marker_failure_reports_a_count_only(self):
        result, out = self.run_suite(FakeBetaEspo(markers=2))
        self.assertIn("2 Account record(s) carry the synthetic seed marker", out)

    def test_skipped_without_configuration_and_sends_nothing(self):
        fake = FakeBetaEspo()
        result, _ = self.run_suite(fake, environ={"CRM_BASE_URL": "http://127.0.0.1:8280"})
        self.assertEqual(result.testsRun, 0)
        self.assertEqual(fake.methods, [])

    def test_key_file_rules(self):
        self.assertEqual(bs.read_key(self.key_file), KEY)
        self.assertEqual(bs.read_key(self.write_key(f"CRM_LOAD_HOST=127.0.0.1\nCRM_LOAD_API_KEY={KEY}\n",
                                                    "load.env")), KEY)
        link = os.path.join(self.tmp, "link.env")
        os.symlink(self.key_file, link)
        bad = {
            "symlink": link,
            "world readable": self.write_key(f"CRM_IMPORT_API_KEY={KEY}\n", "a.env", 0o644),
            "group readable": self.write_key(f"CRM_IMPORT_API_KEY={KEY}\n", "b.env", 0o640),
            "two keys": self.write_key(f"CRM_IMPORT_API_KEY={KEY}\nCRM_LOAD_API_KEY={KEY}\n", "c.env"),
            "empty": self.write_key("CRM_IMPORT_API_KEY=\n", "d.env"),
            "other name": self.write_key(f"API_KEY={KEY}\n", "e.env"),
            "missing": os.path.join(self.tmp, "nope.env"),
        }
        for name, path in bad.items():
            with self.subTest(case=name):
                with self.assertRaises(bs.BetaSafeError) as cm:
                    bs.read_key(path)
                self.assertNotIn(KEY, str(cm.exception))

    def test_a_bad_key_file_errors_the_run_without_any_request(self):
        self.key_file = self.write_key(f"CRM_IMPORT_API_KEY={KEY}\n", "open.env", 0o644)
        fake = FakeBetaEspo()
        result, _ = self.run_suite(fake)
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(fake.methods, [])

    def test_the_client_can_only_send_get(self):
        public = sorted(n for n in dir(bs.ReadOnlyClient) if not n.startswith("_"))
        self.assertEqual(public, ["METHOD", "count", "get"])
        fake = FakeBetaEspo()
        client = bs.ReadOnlyClient("http://127.0.0.1:8280", KEY, fake)
        with unittest.mock.patch.object(bs.ReadOnlyClient, "METHOD", "POST"):
            with self.assertRaises(bs.BetaSafeError):
                client.get("Settings")
        self.assertEqual(fake.methods, [])

    def test_source_has_no_write_path_and_no_argv(self):
        with open(bs.__file__) as fh:
            src = fh.read()
        for token in ('"POST"', '"PUT"', '"PATCH"', '"DELETE"', "'POST'", "'PUT'", "'DELETE'",
                      ".call(", ".create(", ".delete(", "EspoClient", "sys.argv", "data="):
            with self.subTest(token=token):
                self.assertNotIn(token, src)
        # Exactly one place sends a request, and it hard-codes GET with no body.
        self.assertEqual(src.count("transport.request("), 1)
        self.assertIn('transport.request("GET", url, dict(self._headers), None)', src)


# --- CRM-007 r2: restore test isolation ------------------------------------------------

class TestRestoretestPolicy(unittest.TestCase):
    def doc(self):
        with open(ca.RESTORETEST_COMPOSE_PATH) as fh:
            return json.load(fh)

    def test_repository_compose_passes(self):
        self.assertEqual(ca.check_restoretest_compose(self.doc()), [])
        res = subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, "check_access.py"),
                              "restoretest"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_shares_nothing_with_beta_or_dev(self):
        doc = self.doc()
        beta = json.loads(read(ca.BETA_COMPOSE_PATH))
        self.assertNotEqual(doc["name"], beta["name"])
        self.assertFalse(set(doc["networks"]) & set(beta["networks"]))
        self.assertEqual(doc["services"]["crm-db"]["image"], beta["services"]["crm-db"]["image"])
        self.assertNotIn("/srv/CRM/runtime/beta/", json.dumps(doc))

    def test_broken_compose_is_refused(self):
        db = lambda d: d["services"]["crm-db"]  # noqa: E731
        mutations = {
            "beta name": lambda d: d.__setitem__("name", "crm-beta"),
            "dev name": lambda d: d.__setitem__("name", "crm-dev"),
            "port": lambda d: db(d).__setitem__("ports", ["127.0.0.1:3307:3306"]),
            "expose": lambda d: db(d).__setitem__("expose", ["3306"]),
            "host network": lambda d: db(d).__setitem__("network_mode", "host"),
            "bind mount": lambda d: db(d).__setitem__("volumes", [
                {"type": "bind", "source": "/srv/CRM/runtime/beta/db", "target": "/var/lib/mysql"}]),
            "aliased volume": lambda d: d["volumes"].__setitem__("db", {"name": "crm-beta_db"}),
            "external volume": lambda d: d["volumes"].__setitem__("db", {"external": True}),
            "beta network": lambda d: d.__setitem__("networks", {"crm-beta-net": {"external": True}}),
            "aliased network": lambda d: d["networks"]["restoretest-net"].__setitem__(
                "name", "crm-beta_crm-beta-net"),
            "not internal": lambda d: d["networks"]["restoretest-net"].__setitem__("internal", False),
            "extra service": lambda d: d["services"].__setitem__("crm-app", {"image": "x"}),
            "container name": lambda d: db(d).__setitem__("container_name", "crm-beta-crm-db-1"),
            "unpinned image": lambda d: db(d).__setitem__("image", "mariadb:11.4"),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                d = self.doc()
                mutate(d)
                self.assertNotEqual(ca.check_restoretest_compose(d), [])


FAKE_RT_DOCKER = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_DOCKER_LOG"
envf=
prev=
for a in "$@"; do [ "$prev" = --env-file ] && envf=$a; prev=$a; done
[ -n "$envf" ] && [ -f "$envf" ] && echo "envmode $("$REAL_STAT" -c %a -- "$envf")" >> "$FAKE_DOCKER_LOG.env"
case "$*" in
    *"COUNT(*)"*)
        [ -n "${FAKE_NO_COUNT:-}" ] && case "$*" in *"FROM "?"$FAKE_NO_COUNT"?" WHERE"*) exit 1 ;; esac
        echo 7 ;;
    *"exec -T crm-db"*) cat > /dev/null; [ -z "${FAKE_FAIL_IMPORT:-}" ] || exit 1 ;;
esac
exit 0
"""


def make_backup(parent, name="crm-beta-20261110T000000Z", marker="from-name"):
    """A synthetic backup as backup.sh writes it. marker: the TARGET file's
    text (default: the target in the name), or None for a legacy backup with
    no marker. TARGET is covered by SHA256SUMS."""
    if marker == "from-name":
        marker = name.split("-")[1] + "\n"
    backup = os.path.join(parent, name)
    os.makedirs(backup, mode=0o700)
    src = os.path.join(parent, ".src-" + name)
    for rel in ("data/upload", "custom/Espo/Custom", "client/custom/src"):
        os.makedirs(os.path.join(src, rel))
        with open(os.path.join(src, rel, "f.txt"), "w") as fh:
            fh.write("x\n")
    for rel, archive in (("data", "data.tar.gz"), ("custom", "custom.tar.gz"),
                         ("client/custom", "client-custom.tar.gz")):
        subprocess.run(["tar", "-C", src, "-czf", os.path.join(backup, archive), rel], check=True)
    subprocess.run(["sh", "-c", "printf 'CREATE TABLE t (x int);\\n' | gzip -c > db.sql.gz"],
                   cwd=backup, check=True)
    names = "db.sql.gz data.tar.gz custom.tar.gz client-custom.tar.gz"
    if marker is not None:
        with open(os.path.join(backup, "TARGET"), "w") as fh:
            fh.write(marker)
        names += " TARGET"
    subprocess.run(["sh", "-c", f"sha256sum {names} > SHA256SUMS"], cwd=backup, check=True)
    shutil.rmtree(src)
    return backup


class TestRestoretest(ShellEnv):
    def setUp(self):
        super().setUp()
        with open(os.path.join(self.bin, "docker"), "w") as fh:
            fh.write(FAKE_RT_DOCKER)
        self.backups = os.path.join(self.runtime, "backups")
        os.mkdir(self.backups, 0o700)
        self.backup = make_backup(self.backups)
        self.rt = os.path.join(self.tmp, "runtime", "beta-restoretest")
        os.mkdir(os.path.join(self.runtime, "data"))
        with open(os.path.join(self.runtime, "data", "live.txt"), "w") as fh:
            fh.write("beta data\n")

    def rt_run(self, *args, extra=None):
        env = {"CRM_RESTORETEST_DIR": self.rt}
        env.update(extra or {})
        return self.run_sh("restore.sh", "beta", "--restoretest", *args, extra=env)

    def beta_tree(self):
        return sorted(os.path.relpath(os.path.join(r, f), self.runtime)
                      for r, ds, fs in os.walk(self.runtime) for f in fs + ds)

    def test_restores_into_the_throwaway_project_prints_counts_and_tears_down(self):
        before = self.beta_tree()
        res = self.rt_run(os.path.basename(self.backup))
        self.assertEqual(res.returncode, 0, res.stderr)
        for table in ("account", "contact", "opportunity", "call", "email", "user"):
            self.assertIn(f"table {table}: 7", res.stdout)
        for d in ("data", "custom", "client/custom"):
            self.assertIn(f"files {d}: 1", res.stdout)
        calls = self.docker_calls()
        rt_compose = os.path.join(REPO, "deploy", "beta", "restoretest", "compose.json")
        prefix = f"compose -p crm-beta-restoretest -f {rt_compose} --env-file {self.rt}/env "
        self.assertTrue(calls)
        for c in calls:
            self.assertTrue(c.startswith(prefix), c)
            self.assertNotIn("crm-dev", c)
            self.assertNotIn("deploy/beta/compose.json", c)
        self.assertIn("up -d --wait crm-db", calls[0])
        self.assertEqual(calls[-1], prefix + "down -v --remove-orphans --timeout 10")
        self.assertFalse(any(" stop " in c or c.endswith(" stop") for c in calls))
        self.assertFalse(os.path.exists(self.rt))
        self.assertEqual(self.beta_tree(), before)
        self.assertEqual(set(read(self.log + ".env").split("\n")) - {""}, {"envmode 600"})
        self.assertNotIn("CRM_RESTORETEST_DB_ROOT_PASSWORD=", res.stdout + res.stderr)

    def test_a_missing_table_count_fails_the_run_after_teardown(self):
        res = self.rt_run(self.backup, extra={"FAKE_NO_COUNT": "opportunity"})
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("table opportunity: missing", res.stdout)
        self.assertIn("table account: 7", res.stdout)
        self.assertIn("1 table count(s) missing", res.stderr)
        self.assertTrue(self.docker_calls()[-1].endswith("down -v --remove-orphans --timeout 10"))
        self.assertFalse(os.path.exists(self.rt))

    def test_failure_still_tears_down_only_the_throwaway_project(self):
        res = self.rt_run(self.backup, extra={"FAKE_FAIL_IMPORT": "1"})
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("did not load", res.stderr)
        calls = self.docker_calls()
        self.assertTrue(calls[-1].endswith("down -v --remove-orphans --timeout 10"), calls)
        self.assertTrue(all("-p crm-beta-restoretest " in c for c in calls))
        self.assertFalse(os.path.exists(self.rt))
        self.assertTrue(os.path.exists(os.path.join(self.runtime, "data", "live.txt")))

    def test_guards_refuse_before_any_docker_call(self):
        cases = {
            "dev target": (lambda: self.run_sh("restore.sh", "dev", "--restoretest", self.backup,
                                               runtime=os.path.join(self.tmp, "runtime", "dev")),
                           2, "for beta only"),
            "wrong dir name": (lambda: self.rt_run(self.backup, extra={
                "CRM_RESTORETEST_DIR": os.path.join(self.tmp, "runtime", "beta")}),
                2, "not named beta-restoretest"),
            "inside beta runtime": (lambda: self.rt_run(self.backup, extra={
                "CRM_RESTORETEST_DIR": os.path.join(self.runtime, "beta-restoretest")}),
                2, "must sit next to"),
            "parent not /srv/CRM/runtime": (lambda: self.rt_run(self.backup, extra={
                "CRM_RESTORETEST_DIR": "/srv/CRM/other/beta-restoretest"}),
                2, "must be exactly /srv/CRM/runtime"),
            "parent /var/tmp": (lambda: self.rt_run(self.backup, extra={
                "CRM_RESTORETEST_DIR": "/var/tmp/beta-restoretest"}),
                2, "must be exactly /srv/CRM/runtime"),
            "relative": (lambda: self.rt_run(self.backup, extra={
                "CRM_RESTORETEST_DIR": "runtime/beta-restoretest"}), 2, "absolute"),
            "secret in env": (lambda: self.rt_run(self.backup, extra={
                "CRM_RESTORETEST_DB_ROOT_PASSWORD": "x"}), 2, "set in the environment"),
            "no backup": (lambda: self.rt_run(), 1, "usage"),
            "extra arg": (lambda: self.rt_run(self.backup, "more"), 1, "usage"),
        }
        os.makedirs(os.path.join(self.tmp, "runtime", "dev"), exist_ok=True)
        for name, (run, code, msg) in cases.items():
            with self.subTest(case=name):
                res = run()
                self.assertEqual(res.returncode, code, res.stderr)
                self.assertIn(msg, res.stderr)
        self.assertEqual(self.docker_calls(), [])

    def test_existing_restoretest_dir_is_refused_and_left_alone(self):
        os.mkdir(self.rt)
        with open(os.path.join(self.rt, "keep"), "w") as fh:
            fh.write("x")
        res = self.rt_run(self.backup)
        self.assertEqual(res.returncode, 2)
        self.assertIn("already exists", res.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.rt, "keep")))
        self.assertEqual(self.docker_calls(), [])

    def test_tampered_backup_refused_before_any_docker_call(self):
        with open(os.path.join(self.backup, "data.tar.gz"), "ab") as fh:
            fh.write(b"x")
        res = self.rt_run(self.backup)
        self.assertEqual(res.returncode, 1)
        self.assertIn("checksum mismatch", res.stderr)
        self.assertEqual(self.docker_calls(), [])
        self.assertFalse(os.path.exists(self.rt))

    def lib(self, code):
        script = (f"set -euo pipefail; . {SCRIPTS}/lib/common.sh; require_target beta; "
                  f". {SCRIPTS}/lib/restoretest.sh; {code}")
        env = {"PATH": self.bin + os.pathsep + os.environ["PATH"], "CRM_RUNTIME_DIR": self.runtime,
               "CRM_TEST_ROOT": os.path.join(self.tmp, "runtime"),
               "REAL_STAT": shutil.which("stat"), "FAKE_ROOT_DIR": os.path.join(self.tmp, "runtime"),
               "FAKE_DOCKER_LOG": self.log, "CRM_RESTORETEST_DIR": self.rt}
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)

    def test_project_and_teardown_guards(self):
        for code in ("CRM_RT_PROJECT=crm-beta; rt_guard",
                     "CRM_RT_PROJECT=crm-dev; rt_guard",
                     f"CRM_RT_COMPOSE_FILE={REPO}/deploy/beta/compose.json; rt_guard",
                     "CRM_RT_PROJECT=crm-beta; CRM_RT_DIR=$CRM_RESTORETEST_DIR; rt_teardown",
                     f"CRM_RT_DIR={self.runtime}; rt_teardown",
                     "CRM_RT_PROJECT=crm-beta; CRM_RT_DIR=$CRM_RESTORETEST_DIR; rt_compose ps"):
            with self.subTest(code=code):
                res = self.lib(code)
                self.assertEqual(res.returncode, 2, res.stderr)
                self.assertIn("refusing to run the restore test", res.stderr)
        self.assertEqual(self.docker_calls(), [])
        self.assertTrue(os.path.isdir(self.runtime))

    def test_teardown_removes_only_its_own_directory(self):
        os.mkdir(self.rt)
        with open(os.path.join(self.rt, "env"), "w") as fh:
            fh.write("CRM_RESTORETEST_DB_ROOT_PASSWORD=x\n")
        res = self.lib("CRM_RT_DIR=$CRM_RESTORETEST_DIR; rt_teardown")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertFalse(os.path.exists(self.rt))
        self.assertTrue(os.path.exists(os.path.join(self.runtime, "data", "live.txt")))
        self.assertEqual(len(self.docker_calls()), 1)
        self.assertIn("-p crm-beta-restoretest", self.docker_calls()[0])


# --- CRM-007 r2: backup timer templates ------------------------------------------------

def unit_entries(path):
    out, section = [], None
    with open(path) as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith(("#", ";")):
                continue
            if line.startswith("["):
                section = line.strip("[]")
                continue
            key, _, value = line.partition("=")
            out.append((section, key.strip(), value.strip()))
    return out


class TestBackupTimer(unittest.TestCase):
    DIR = os.path.join(REPO, "deploy", "beta", "systemd")

    def entries(self, name):
        return unit_entries(os.path.join(self.DIR, name))

    def test_service_runs_the_deployed_release_backup_for_beta_only(self):
        e = self.entries("crm-beta-backup@.service")
        d = {(s, k): v for s, k, v in e}
        self.assertEqual(d[("Service", "Type")], "oneshot")
        self.assertEqual(d[("Service", "ExecStart")],
                         "/usr/bin/bash /srv/CRM/deploy/%i/scripts/backup.sh beta")
        self.assertEqual(d[("Service", "UMask")], "0077")
        self.assertEqual(d[("Service", "User")], "root")
        self.assertEqual(d[("Service", "NoNewPrivileges")], "yes")
        self.assertEqual([k for s, k, v in e if k == "ExecStart"], ["ExecStart"])
        # No environment: backup.sh refuses if an env-file name is set.
        self.assertFalse([k for s, k, v in e if k.startswith("Environment")])
        text = read(os.path.join(self.DIR, "crm-beta-backup@.service"))
        self.assertNotIn("%I", text)
        self.assertNotIn(" dev", text)

    def test_timer_is_daily_and_persistent(self):
        d = {(s, k): v for s, k, v in self.entries("crm-beta-backup@.timer")}
        self.assertTrue(d[("Timer", "OnCalendar")])
        self.assertEqual(d[("Timer", "Persistent")], "true")
        self.assertEqual(d[("Install", "WantedBy")], "timers.target")
        self.assertNotIn(("Timer", "Unit"), d)  # triggers the same-instance service

    def test_nothing_in_the_repository_installs_it(self):
        for root, _, files in os.walk(SCRIPTS):
            for f in files:
                if f.endswith((".sh", ".py")):
                    with open(os.path.join(root, f), errors="replace") as fh:
                        src = fh.read()
                    self.assertNotIn("systemctl", src, f)
                    self.assertNotIn("/etc/systemd", src, f)


# --- CRM-007 r2: deploy_release.sh post-unpack steps -----------------------------------

FAKE_DEPLOY_DOCKER = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_DOCKER_LOG"
case "$*" in
    *"php -r"*) printf '%s' "${FAKE_PHP_OUT-false}" ;;
esac
exit 0
"""


class TestDeploySteps(ShellEnv):
    def setUp(self):
        super().setUp()
        with open(os.path.join(self.bin, "docker"), "w") as fh:
            fh.write(FAKE_DEPLOY_DOCKER)
        self.env_file = os.path.join(self.runtime, "env")
        with open(self.env_file, "w") as fh:
            fh.write(env_text())
        os.chmod(self.env_file, 0o600)

    def step(self, code, extra=None, stubs=""):
        script = (f"set -euo pipefail; . {SCRIPTS}/deploy_release.sh; "
                  f'load_env_names {REPO}/deploy/beta/env.example; '
                  'CRM_BETA_ENV_NAMES=("${CRM_ENV_NAMES[@]}"); export CRM_RUNTIME_DIR; '
                  f"{stubs}\n{code}")
        env = {"PATH": self.bin + os.pathsep + os.environ["PATH"], "CRM_RUNTIME_DIR": self.runtime,
               "CRM_TEST_ROOT": os.path.join(self.tmp, "runtime"),
               "REAL_STAT": shutil.which("stat"), "FAKE_ROOT_DIR": os.path.join(self.tmp, "runtime"),
               "FAKE_DOCKER_LOG": self.log, "HOME": self.tmp, "TMPDIR": self.tmp}
        env.update(extra or {})
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env,
                              timeout=60)

    def test_sourcing_runs_nothing(self):
        res = self.step("echo sourced")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "sourced")
        self.assertEqual(self.docker_calls(), [])

    def test_render_edge_writes_a_policy_clean_config(self):
        # An exported env-file name (as the operator does for step 7) is stripped.
        res = self.step(f"render_edge {REPO}", extra={"CRM_BETA_PORT": "9999",
                                                      "CRM_ADMIN_PASSWORD": "x"})
        self.assertEqual(res.returncode, 0, res.stderr)
        cfg = os.path.join(self.runtime, "edge", "haproxy.cfg")
        self.assertEqual(stat.S_IMODE(os.stat(cfg).st_mode), 0o644)
        text = read(cfg)
        self.assertEqual(ca.check_edge_config(text), [])
        self.assertIn(f"bind {BIND}:8443", text)
        for v in (BIND, UP1, UP2):
            self.assertNotIn(v, res.stdout + res.stderr)

    def test_render_edge_fails_closed(self):
        with open(self.env_file, "w") as fh:
            fh.write(env_text(CRM_BETA_UPSTREAM_SOURCES="0.0.0.0/0"))
        res = self.step(f"render_edge {REPO}; echo NOT-REACHED")
        self.assertEqual(res.returncode, 1)
        self.assertIn("edge settings failed", res.stderr)
        self.assertNotIn("NOT-REACHED", res.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.runtime, "edge", "haproxy.cfg")))

    def test_configure_site_sets_both_values_and_accepts_only_boolean_false(self):
        res = self.step(f"configure_site {REPO}")
        self.assertEqual(res.returncode, 0, res.stderr)
        calls = self.docker_calls()
        beta = f"compose -p crm-beta -f {REPO}/deploy/beta/compose.json --env-file {self.env_file} "
        self.assertTrue(all(c.startswith(beta) for c in calls), calls)
        self.assertTrue(calls[0].endswith("config:set siteUrl https://crm-beta.example.invalid"))
        self.assertTrue(calls[1].endswith("config:set phoneNumberInternational false"))
        self.assertIn("php -r", calls[2])
        for out in ("'false'", "true", "NULL", "", "0", "false\nfalse"):
            with self.subTest(read_back=out):
                res = self.step(f"configure_site {REPO}", extra={"FAKE_PHP_OUT": out})
                self.assertEqual(res.returncode, 1)
                self.assertIn("not exactly false", res.stderr)

    # check_access.py runs for real (the pinned beta URL from the env file).
    PY_STUB = ('python3() { case "$*" in *check_access.py*) command python3 "$@"; return;; esac; '
               'printf "python3 %s\\n" "$*" | head -n1 >> "$FAKE_DOCKER_LOG"; '
               'case "$*" in *provision_access.py*) echo "url=$CRM_BASE_URL" >> "$FAKE_DOCKER_LOG"; '
               '[ -z "${WRITE_KEY:-}" ] || printf "CRM_IMPORT_API_KEY=k\\n" > "$CRM_PROVISION_KEY_FILE"; '
               'return "${FAKE_PROV_RC:-0}";; '
               '*" -c "*) echo "safe-key=$CRM_BETA_SAFE_KEY_FILE" >> "$FAKE_DOCKER_LOG"; '
               'return "${FAKE_SAFE_RC:-0}";; esac; }')

    def creds(self, **over):
        env = {"CRM_ADMIN_USERNAME": "a", "CRM_ADMIN_PASSWORD": "p",
               "CRM_PROVISION_KEY_FILE": os.path.join(self.tmp, "new-key.env")}
        env.update(over)
        return {k: v for k, v in env.items() if v is not None}

    def accept(self, extra):
        return self.step(f'provision_and_accept {REPO}; echo "RESULT $PROVISIONED $ACCEPTANCE"',
                         extra=extra, stubs=self.PY_STUB)

    def test_provision_and_accept_never_skips(self):
        # CRM-007R (was: skipped without credentials): a missing input refuses.
        for missing in ("CRM_ADMIN_USERNAME", "CRM_ADMIN_PASSWORD", "CRM_PROVISION_KEY_FILE"):
            with self.subTest(missing=missing):
                res = self.accept(self.creds(**{missing: None}))
                self.assertEqual(res.returncode, 1, res.stdout)
                self.assertIn(f"{missing} is required", res.stderr)
                self.assertNotIn("RESULT", res.stdout)
        self.assertEqual(self.docker_calls(), [])

    def test_report_refuses_skipped_or_failed_steps(self):
        for prov, acc in (("skipped", "skipped"), ("done", "skipped"), ("skipped", "passed"),
                          ("done", "failed"), ("", "")):
            with self.subTest(provisioning=prov, acceptance=acc):
                res = self.step(f"PROVISIONED={prov} ACCEPTANCE={acc}; write_report {REPO} x 1")
                self.assertEqual(res.returncode, 1)
                self.assertIn("refusing to report success", res.stderr)
        self.assertFalse([n for n in os.listdir(self.runtime) if n.startswith("deploy-report")])

    def test_provision_then_beta_safe_with_the_new_key(self):
        # An operator CRM_BASE_URL (here dev-style) is never used: the URL is
        # beta's loopback URL from the env file.
        res = self.accept(dict(self.creds(), WRITE_KEY="1", CRM_BASE_URL=f"http://{BIND}:8180"))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("RESULT done passed", res.stdout)
        calls = self.docker_calls()
        self.assertIn(f"provision_access.py beta --key-file {self.tmp}/new-key.env", calls[0])
        self.assertEqual(calls[1], "url=http://127.0.0.1:8280")
        self.assertIn(" -c ", calls[2])
        self.assertEqual(calls[3], f"safe-key={self.tmp}/new-key.env")

    def test_existing_provision_key_without_safe_key_file_refused(self):
        key = os.path.join(self.tmp, "new-key.env")
        open(key, "w").close()
        res = self.accept(self.creds())
        self.assertEqual(res.returncode, 1)
        self.assertIn("CRM_PROVISION_KEY_FILE must not exist yet", res.stderr)
        self.assertEqual(self.docker_calls(), [])

    def test_upgrade_without_a_new_key_needs_an_explicit_key_file(self):
        res = self.accept(self.creds())  # provisioning wrote no key (API user existed)
        self.assertEqual(res.returncode, 1)
        self.assertIn("set CRM_BETA_SAFE_KEY_FILE", res.stderr)
        res = self.step(f'provision_and_accept {REPO} 1', extra=self.creds(), stubs=self.PY_STUB)
        self.assertEqual(res.returncode, 1)
        self.assertIn("required with --upgrade", res.stderr)
        existing = os.path.join(self.tmp, "existing.env")
        open(existing, "w").close()
        res = self.accept(dict(self.creds(), CRM_BETA_SAFE_KEY_FILE=existing))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn(f"safe-key={existing}", self.docker_calls())

    def test_failures_stop_the_deploy(self):
        res = self.accept(dict(self.creds(), WRITE_KEY="1", FAKE_SAFE_RC="1"))
        self.assertEqual(res.returncode, 1)
        self.assertIn("beta-safe acceptance failed", res.stderr)
        res = self.accept(dict(self.creds(CRM_PROVISION_KEY_FILE=os.path.join(self.tmp, "k2")),
                               FAKE_PROV_RC="1"))
        self.assertEqual(res.returncode, 1)
        self.assertIn("access provisioning failed", res.stderr)

    def test_run_beta_safe_fails_when_the_suite_is_skipped(self):
        # The real in-process runner, with no configuration: the suite skips, so it must fail.
        res = self.step(f"run_beta_safe {REPO}")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("skipped", res.stderr)

    def test_report_is_sanitised_and_private(self):
        dest = os.path.join(self.tmp, "rel")
        os.mkdir(dest)
        with open(os.path.join(dest, "RELEASE.json"), "w") as fh:
            json.dump({"commit": "c" * 40, "short": "c" * 12, "images": {"haproxy": "sha256:x"},
                       "delivery_records": {}, "files": {"a": "b"}, "extra": BIND}, fh)
        bundle = os.path.join(self.tmp, "b.tar.gz")
        with open(bundle, "wb") as fh:
            fh.write(b"bundle")
        res = self.step(f"PROVISIONED=done ACCEPTANCE=passed; write_report {dest} {bundle} 1")
        self.assertEqual(res.returncode, 0, res.stderr)
        path = res.stdout.strip()
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        report = json.loads(read(path))
        self.assertEqual(set(report), {"commit", "short", "images", "delivery_records", "target",
                                       "project", "stamp", "upgrade", "bundle_sha256",
                                       "phoneNumberInternational", "access", "acceptance"})
        self.assertIs(report["phoneNumberInternational"], False)
        self.assertNotIn(BIND, read(path))

    def test_main_stops_at_the_first_failing_step(self):
        stubs = "; ".join(f'{f}() {{ echo "{f}" >> "$FAKE_DOCKER_LOG"; }}' for f in (
            "verify_bundle", "check_runtime_empty", "make_runtime", "start_stack",
            "configure_site", "provision_and_accept")) + (
            '; unpack_release() { echo unpack_release >> "$FAKE_DOCKER_LOG"; echo ' + REPO + '; }'
            '; write_report() { echo write_report >> "$FAKE_DOCKER_LOG"; echo r; }'
            '; render_edge() { echo render_edge >> "$FAKE_DOCKER_LOG"; return ${RENDER_RC:-0}; }'
            '; id() { echo 0; }')
        sha = "a" * 64
        res = self.step(f"main beta x.tar.gz --sha256 {sha}", stubs=stubs,
                        extra=DEPLOY_INPUTS(self.tmp))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.docker_calls(), [
            "verify_bundle", "check_runtime_empty", "unpack_release", "make_runtime", "render_edge",
            "start_stack", "configure_site", "provision_and_accept", "write_report"])
        os.unlink(self.log)
        res = self.step(f"main beta x.tar.gz --sha256 {sha}", stubs=stubs,
                        extra={**DEPLOY_INPUTS(self.tmp), "RENDER_RC": "1"})
        self.assertNotEqual(res.returncode, 0)
        self.assertEqual(self.docker_calls()[-1], "render_edge")


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
