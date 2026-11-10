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
        for i, mutate in enumerate(mutations):
            with self.subTest(mutation=i):
                d = self.doc()
                mutate(d)
                self.assertNotEqual(ca.check_beta_compose(d), [])

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
            "forwarded header from any source": good.replace(
                "X-Forwarded-Proto https if trusted_upstream", "X-Forwarded-Proto https"),
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
        }
        for name, text in fixtures.items():
            with self.subTest(fixture=name):
                self.assertNotEqual(text, good)
                self.assertNotEqual(ca.check_edge_config(text), [])

    def test_check_access_beta_cli_renders_only_when_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = os.path.join(tmp, "beta")
            os.mkdir(runtime)
            with open(os.path.join(runtime, "env"), "w") as fh:
                fh.write(env_text())
            env = {"PATH": os.environ["PATH"], "CRM_RUNTIME_DIR": runtime}
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
               "REAL_STAT": shutil.which("stat"), "REAL_ID": shutil.which("id"),
               "FAKE_DOCKER_LOG": self.log,
               "FAKE_ROOT_DIR": os.path.join(self.tmp, "runtime") if root else "/nonexistent",
               "CRM_DEPLOY_ROOT": os.path.join(self.tmp, "deploy")}
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
                self.assertIn("not a beta runtime", res.stderr)
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

    def test_unaccepted_commit_refused(self):
        with self.assertRaises(release.ReleaseError):
            self.build("c", self.git("rev-parse", "side"))

    def rewrite(self, path, change):
        """Rebuild the bundle with change(name, data) -> data|None applied."""
        with tarfile.open(path) as tar:
            members = [(m, tar.extractfile(m).read() if m.isfile() else None)
                       for m in tar.getmembers()]
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w:gz") as tar:
            for m, data in members:
                data = change(m.name, data) if data is not None else None
                if m.isfile() and data is None:
                    continue
                if data is not None:
                    m.size = len(data)
                tar.addfile(m, io.BytesIO(data) if data is not None else None)
        with open(path, "wb") as fh:
            fh.write(raw.getvalue())

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

    def test_wrong_bundle_digest_refused(self):
        path, _ = self.build("s")
        with self.assertRaisesRegex(release.ReleaseError, "sha256"):
            release.verify(path, "0" * 64)

    def test_release_sh_refuses_without_commit(self):
        res = subprocess.run(["bash", os.path.join(SCRIPTS, "release.sh")], capture_output=True,
                             text=True)
        self.assertEqual(res.returncode, 2)


class TestDeployRelease(ShellEnv):
    def setUp(self):
        super().setUp()
        repo = os.path.join(self.tmp, "repo")
        git = make_repo(repo)
        out = os.path.join(self.tmp, "out")
        os.mkdir(out)
        self.bundle, _ = release.build(repo, git("rev-parse", "main"), out)
        env = os.path.join(self.runtime, "env")
        with open(env, "w") as fh:
            fh.write(env_text())
        os.chmod(env, 0o600)

    def deploy(self, *extra, **kw):
        return self.run_sh("deploy_release.sh", "beta", self.bundle, *extra,
                           extra={"FAKE_UID": "0"}, **kw)

    def test_non_empty_runtime_refused_without_upgrade(self):
        os.mkdir(os.path.join(self.runtime, "data"))
        res = self.deploy()
        self.assertEqual(res.returncode, 1, res.stderr)
        self.assertIn("is not empty", res.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "deploy")))
        self.assertEqual(self.docker_calls(), [])

    def test_tampered_bundle_refused_before_anything(self):
        with open(self.bundle, "ab") as fh:
            fh.write(b"x")
        res = self.deploy()
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("failed verification", res.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "deploy")))

    def test_wrong_target_not_root_and_bad_runtime_refused(self):
        res = self.run_sh("deploy_release.sh", "dev", self.bundle, extra={"FAKE_UID": "0"})
        self.assertEqual(res.returncode, 2)
        res = self.run_sh("deploy_release.sh", "beta", self.bundle, extra={"FAKE_UID": "1000"})
        self.assertIn("must run as root", res.stderr)
        res = self.deploy(root=False)
        self.assertIn("owned by root with mode 0700", res.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "deploy")))

    def test_empty_runtime_passes_the_emptiness_check_and_unpacks(self):
        # The minimal test repo has no scripts beyond release.py, so the deploy
        # stops at the first bundled script; everything before it is checked.
        res = self.deploy()
        short = os.path.basename(self.bundle)[len("crm-release-"):-len(".tar.gz")]
        dest = os.path.join(self.tmp, "deploy", short)
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
    *"COUNT(*)"*) echo 7 ;;
    *"exec -T crm-db"*) cat > /dev/null; [ -z "${FAKE_FAIL_IMPORT:-}" ] || exit 1 ;;
esac
exit 0
"""


def make_backup(parent, name="crm-beta-20261110T000000Z"):
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
    subprocess.run(["sh", "-c", "sha256sum db.sql.gz data.tar.gz custom.tar.gz client-custom.tar.gz"
                    " > SHA256SUMS"], cwd=backup, check=True)
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
                2, "inside the crm-beta runtime"),
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
               "REAL_STAT": shutil.which("stat"), "FAKE_ROOT_DIR": os.path.join(self.tmp, "runtime"),
               "FAKE_DOCKER_LOG": self.log, "HOME": self.tmp}
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

    PY_STUB = ('python3() { printf "python3 %s\\n" "$*" | head -n1 >> "$FAKE_DOCKER_LOG"; '
               'case "$*" in *provision_access.py*) '
               '[ -z "${WRITE_KEY:-}" ] || printf "CRM_IMPORT_API_KEY=k\\n" > "$CRM_PROVISION_KEY_FILE"; '
               'return "${FAKE_PROV_RC:-0}";; '
               '*" -c "*) echo "safe-key=$CRM_BETA_SAFE_KEY_FILE" >> "$FAKE_DOCKER_LOG"; '
               'return "${FAKE_SAFE_RC:-0}";; esac; }')

    def creds(self, **over):
        env = {"CRM_ADMIN_USERNAME": "a", "CRM_ADMIN_PASSWORD": "p",
               "CRM_BASE_URL": "http://127.0.0.1:8280",
               "CRM_PROVISION_KEY_FILE": os.path.join(self.tmp, "new-key.env")}
        env.update(over)
        return {k: v for k, v in env.items() if v is not None}

    def accept(self, extra):
        return self.step(f'provision_and_accept {REPO}; echo "RESULT $PROVISIONED $ACCEPTANCE"',
                         extra=extra, stubs=self.PY_STUB)

    def test_provision_and_accept_skips_without_credentials(self):
        for missing in ("CRM_ADMIN_USERNAME", "CRM_ADMIN_PASSWORD", "CRM_BASE_URL",
                        "CRM_PROVISION_KEY_FILE"):
            with self.subTest(missing=missing):
                res = self.accept(self.creds(**{missing: None}))
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertIn("RESULT skipped skipped", res.stdout)
        self.assertEqual(self.docker_calls(), [])

    def test_provision_then_beta_safe_with_the_new_key(self):
        res = self.accept(dict(self.creds(), WRITE_KEY="1"))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("RESULT done passed", res.stdout)
        calls = self.docker_calls()
        self.assertIn(f"provision_access.py beta --key-file {self.tmp}/new-key.env", calls[0])
        self.assertIn(" -c ", calls[1])
        self.assertEqual(calls[2], f"safe-key={self.tmp}/new-key.env")

    def test_upgrade_without_a_new_key_needs_an_explicit_key_file(self):
        res = self.accept(self.creds())
        self.assertEqual(res.returncode, 1)
        self.assertIn("set CRM_BETA_SAFE_KEY_FILE", res.stderr)
        existing = os.path.join(self.tmp, "existing.env")
        open(existing, "w").close()
        res = self.accept(dict(self.creds(), CRM_BETA_SAFE_KEY_FILE=existing))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn(f"safe-key={existing}", self.docker_calls())

    def test_failures_stop_the_deploy(self):
        res = self.accept(dict(self.creds(), WRITE_KEY="1", FAKE_SAFE_RC="1"))
        self.assertEqual(res.returncode, 1)
        self.assertIn("beta-safe acceptance failed", res.stderr)
        res = self.accept(dict(self.creds(), FAKE_PROV_RC="1"))
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
        res = self.step("main beta x.tar.gz", stubs=stubs, extra={"CRM_DEPLOY_ROOT": "/x/deploy"})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.docker_calls(), [
            "verify_bundle", "check_runtime_empty", "unpack_release", "make_runtime", "render_edge",
            "start_stack", "configure_site", "provision_and_accept", "write_report"])
        os.unlink(self.log)
        res = self.step("main beta x.tar.gz", stubs=stubs,
                        extra={"CRM_DEPLOY_ROOT": "/x/deploy", "RENDER_RC": "1"})
        self.assertNotEqual(res.returncode, 0)
        self.assertEqual(self.docker_calls()[-1], "render_edge")


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
