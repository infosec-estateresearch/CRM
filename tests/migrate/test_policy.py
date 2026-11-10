"""Compose policy and migrate.sh guards (AC10). Each rule fails against a broken fixture."""

import copy
import json
import re
import shutil
import subprocess
import unittest

from crm_migrate import hostcheck

from . import COMPOSE_PATH, ENV_EXAMPLE_PATH, REGISTER_PATH, SCRIPT_PATH
from .policy_checks import compose_violations, register_digest, script_violations


def load(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class ComposePolicyTest(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(load(COMPOSE_PATH))
        self.digest = register_digest(load(REGISTER_PATH))

    def test_register_digest_present(self):
        self.assertEqual(self.digest, "sha256:326df678c20c78d465db501563f3492d17c42a4afe33a1f2bf5406a1d56b0e86")

    def test_real_compose_passes(self):
        self.assertEqual(compose_violations(self.doc, self.digest), [])

    def test_broken_fixtures(self):
        live, st = "crm-migrate", "crm-migrate-selftest"

        def svc(d, name):
            return d["services"][name]

        cases = {
            "image_digest": lambda d: svc(d, live).update(image="python:3.13.9-slim-trixie"),
            "image_digest_other": lambda d: svc(d, st).update(
                image="python:3.13.9-slim-trixie@sha256:" + "0" * 64),
            "ports": lambda d: svc(d, live).update(ports=["127.0.0.1:8080:8080"]),
            "read_only": lambda d: svc(d, st).update(read_only=False),
            "cap_drop": lambda d: svc(d, live).update(cap_drop=["NET_RAW"]),
            "cap_add": lambda d: svc(d, live).update(cap_add=["NET_ADMIN"]),
            "no_new_privileges": lambda d: svc(d, live).update(security_opt=[]),
            "user": lambda d: svc(d, st).update(user="0:0"),
            "selftest_network_none": lambda d: svc(d, st).pop("network_mode"),
            "selftest_networks": lambda d: svc(d, st).update(networks=["crm-migrate-net"]),
            "selftest_no_env": lambda d: svc(d, st).update(env_file=["/srv/CRM/runtime/migrate/env"]),
            "container_name": lambda d: svc(d, live).update(container_name="crm-migrate"),
            "service_prefix": lambda d: d["services"].update(migrate=d["services"].pop(live)),
            "network_prefix": lambda d: d["networks"].update(default={"driver": "bridge"}),
            "external_network": lambda d: d["networks"]["crm-migrate-net"].update(external=True),
            "named_volume": lambda d: d.update(volumes={"crm-data": {}}),
            "extra_writable_bind": lambda d: svc(d, live)["volumes"].append(
                {"type": "bind", "source": "/srv/CRM/runtime/migrate", "target": "/data", "read_only": False,
                 "bind": {"create_host_path": False}}),
            "code_mount_writable": lambda d: svc(d, live)["volumes"][0].update(read_only=False),
            "out_not_per_run": lambda d: svc(d, live)["volumes"][1].update(source="/srv/CRM/runtime/migrate/snapshots"),
            "named_volume_mount": lambda d: svc(d, live)["volumes"].append(
                {"type": "volume", "source": "crm-cache", "target": "/cache"}),
            "create_host_path": lambda d: svc(d, live)["volumes"][1].pop("bind"),
            "tmpfs_exec": lambda d: svc(d, live).update(tmpfs=["/tmp:size=64m"]),
            "entrypoint_not_isolated": lambda d: svc(d, live).update(
                entrypoint=["python", "/opt/crm-migrate/bin/crm-migrate.py"]),
            "privileged": lambda d: svc(d, live).update(privileged=True),
            "host_network": lambda d: svc(d, live).update(network_mode="host"),
            "live_env_file": lambda d: svc(d, live).update(env_file=["./env"]),
            "live_environment": lambda d: svc(d, live).update(environment={"CRM_SF_CLIENT_SECRET": "x"}),
            "build": lambda d: svc(d, live).update(build="."),
            "pid_host": lambda d: svc(d, live).update(pid="host"),
            "extra_hosts": lambda d: svc(d, live).update(extra_hosts=["x:127.0.0.1"]),
        }
        for name, fn in cases.items():
            with self.subTest(name):
                doc = copy.deepcopy(self.doc)
                fn(doc)
                self.assertNotEqual(compose_violations(doc, self.digest), [], name)

    def test_wrong_register_digest_fails(self):
        self.assertIn("image_digest", compose_violations(self.doc, "sha256:" + "1" * 64))
        self.assertIn("image_digest", compose_violations(self.doc, None))


class ScriptPolicyTest(unittest.TestCase):
    def setUp(self):
        self.text = load(SCRIPT_PATH)

    def test_bash_syntax(self):
        bash = shutil.which("bash")
        self.assertIsNotNone(bash)
        proc = subprocess.run([bash, "-n", SCRIPT_PATH], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_bash_syntax_check_can_fail(self):
        proc = subprocess.run([shutil.which("bash"), "-n", "/dev/stdin"], input="if then fi\n",
                              capture_output=True, text=True, timeout=30)
        self.assertNotEqual(proc.returncode, 0)

    def test_real_script_passes(self):
        self.assertEqual(script_violations(self.text), [])

    def test_hostcheck_calls_exist(self):
        calls = set(re.findall(r"(?<![\w-])(?:require|check) ([a-z-]+)", self.text))
        known = {"target", "runtime-dirs", "env-names", "env-clean", "env-file", "uid-free", "run-id",
                 "run-dir-absent", "run-dir-prepared", "sealed", "verify-manifest"}
        self.assertTrue(calls)
        self.assertLessEqual(calls, known)
        self.assertIn("env-names", self.text)

    def test_broken_scripts(self):
        cases = {
            "root_only": (r'\[\[ \$\{EUID\} -eq 0 \]\] \|\| die "must be run as root"\n', ""),
            "target_guard": (r'require target "\$target"\n', ""),
            "runtime_guard": (r"require runtime-dirs\n", ""),
            "runtime_path": (r"readonly RUNTIME=/srv/CRM/runtime/migrate", "readonly RUNTIME=/tmp/migrate"),
            "exported_secret_guard": (r'require env-clean "\$ENV_EXAMPLE"\n', ""),
            "exported_secret_bash": (r'\[\[ -z "\$\{!name\+set\}" \]\] \|\| die', "true"),
            "uid_guard": (r"require uid-free [^\n]*\n", ""),
            "env_unset": (r'unset_args\+=\(-u "\$name"\)', "true"),
            "no_project_env_file": (r" --env-file /dev/null", ""),
            "run_dir_absent": (r'    require run-dir-absent "\$RUN_DIR"\n', ""),
            "run_dir_mkdir": (r"mkdir -m 0700 -- \"\$RUN_DIR\"", 'mkdir -p -- "$RUN_DIR"'),
            "seal_owner": (r"chown -R --no-dereference root:root", "chown -R root:crm"),
            "seal_files": (r"-type f -exec chmod 0400", "-type f -exec chmod 0644"),
            "seal_check": (r'check sealed "\$dir"', "true"),
            "manifest_reverify": (r'check verify-manifest "\$2"', "true"),
            "credentials_silent": (r'read -rs -p "Consumer secret: "', 'read -r -p "Consumer secret: "'),
            "credentials_atomic": (r'mv -T -f -- "\$CRED_TMP" "\$ENV_FILE"', 'cp "$CRED_TMP" "$ENV_FILE"'),
            "xtrace": (r"set -euo pipefail\n", "set -euo pipefail\nset -x\n"),
            "echo_values": (r"(printf 'migrate.sh: wrote)", 'echo "$client_secret"\n    \\1'),
            "docker_outside_wrapper": (r"(cmd_selftest\(\) \{\n)", "\\1    docker compose run crm-migrate\n"),
        }
        for name, (pattern, repl) in cases.items():
            with self.subTest(name):
                broken, n = re.subn(pattern, repl, self.text, count=1)
                self.assertEqual(n, 1, f"fixture pattern for {name} did not match")
                self.assertIn(name, script_violations(broken))


class EnvExampleTest(unittest.TestCase):
    def test_names_only(self):
        names, errors = hostcheck.parse_env_names(load(ENV_EXAMPLE_PATH))
        self.assertEqual(errors, [])
        self.assertEqual(names, ["CRM_SF_ORIGIN", "CRM_SF_CLIENT_ID", "CRM_SF_CLIENT_SECRET", "CRM_SF_API_VERSION"])

    def test_value_in_example_refused(self):
        _, errors = hostcheck.parse_env_names("CRM_SF_ORIGIN=\nCRM_SF_CLIENT_SECRET=abc\n")
        self.assertEqual(errors, ["env.example must hold names only"])

    def test_cli_names_match_env_example(self):
        from crm_migrate.cli import ENV_NAMES
        names, _ = hostcheck.parse_env_names(load(ENV_EXAMPLE_PATH))
        self.assertEqual(tuple(names), ENV_NAMES)


if __name__ == "__main__":
    unittest.main()
