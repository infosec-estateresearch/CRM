"""Script tests (WO CRM-001 items 4 and 5): bash -n, the dev guard, and the
backup/restore/export flows against a fake `docker` and a temporary runtime
directory. No stack, no network."""

import csv
import gzip
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
sys.path.insert(0, SCRIPTS)

import crm_api  # noqa: E402
import export_csv  # noqa: E402

GUARDED = ["backup.sh", "restore.sh", "export.sh"]

FAKE_DOCKER = """#!/usr/bin/env bash
# Records its arguments; plays mariadb-dump / mariadb inside "crm-db".
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
case "$*" in
    *mariadb-dump*) printf -- '-- fake dump\\nCREATE TABLE account (id int);\\n' ;;
    *"exec -T crm-db"*) cat > "$FAKE_DOCKER_STDIN" ;;
esac
exit 0
"""


def shell_scripts():
    out = []
    for root, _, files in os.walk(SCRIPTS):
        out += [os.path.join(root, f) for f in files if f.endswith(".sh")]
    return sorted(out)


class ScriptEnv(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = self.tmp.name
        self.bin = os.path.join(base, "bin")
        os.mkdir(self.bin)
        docker = os.path.join(self.bin, "docker")
        with open(docker, "w") as fh:
            fh.write(FAKE_DOCKER)
        os.chmod(docker, stat.S_IRWXU)
        self.log = os.path.join(base, "docker.log")
        self.stdin = os.path.join(base, "docker.stdin")
        self.runtime = os.path.join(base, "runtime", "dev")
        os.makedirs(os.path.join(self.runtime, "data", "upload"))
        with open(os.path.join(self.runtime, "data", "config.php"), "w") as fh:
            fh.write("<?php return [];\n")
        with open(os.path.join(self.runtime, "env"), "w") as fh:
            fh.write("CRM_DB_NAME=\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, name, *args, runtime=None, extra_env=None):
        env = {
            "PATH": self.bin + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
            "CRM_RUNTIME_DIR": runtime or self.runtime,
            "FAKE_DOCKER_LOG": self.log,
            "FAKE_DOCKER_STDIN": self.stdin,
            "HOME": self.tmp.name,
        }
        env.update(extra_env or {})
        return subprocess.run(["bash", os.path.join(SCRIPTS, name), *args],
                              capture_output=True, text=True, env=env, timeout=60)

    def docker_calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as fh:
            return fh.read().splitlines()


class TestBashSyntax(unittest.TestCase):
    def test_every_script_passes_bash_n(self):
        scripts = shell_scripts()
        self.assertGreaterEqual(len(scripts), 4)
        for path in scripts:
            with self.subTest(script=os.path.relpath(path, REPO)):
                res = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
                self.assertEqual(res.returncode, 0, res.stderr)

    def test_bash_n_detects_a_syntax_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".sh") as fh:
            fh.write("if true; then\n  echo broken\n")
            fh.flush()
            res = subprocess.run(["bash", "-n", fh.name], capture_output=True)
            self.assertNotEqual(res.returncode, 0)


class TestDevGuard(ScriptEnv):
    def test_refuses_any_target_but_dev(self):
        for script in GUARDED:
            for args in ([], ["prod"], ["beta"], ["DEV"], ["dev "], ["development"], [""]):
                with self.subTest(script=script, args=args):
                    res = self.run_script(script, *args)
                    self.assertEqual(res.returncode, 2, res.stderr)
                    self.assertIn("refusing to run", res.stderr)
                    self.assertEqual(self.docker_calls(), [])
        self.assertEqual(sorted(os.listdir(self.runtime)), ["data", "env"], "nothing written")

    def test_refuses_a_runtime_that_is_not_dev(self):
        prod = os.path.join(self.tmp.name, "runtime", "prod")
        os.makedirs(prod)
        for script in GUARDED:
            with self.subTest(script=script):
                res = self.run_script(script, "dev", runtime=prod)
                self.assertEqual(res.returncode, 2)
                self.assertIn("not a dev runtime", res.stderr)
        self.assertEqual(self.docker_calls(), [])
        self.assertEqual(os.listdir(prod), [])


class TestBackupRestore(ScriptEnv):
    def backup(self):
        res = self.run_script("backup.sh", "dev")
        self.assertEqual(res.returncode, 0, res.stderr)
        backups = os.listdir(os.path.join(self.runtime, "backups"))
        self.assertEqual(len(backups), 1)
        self.assertRegex(backups[0], r"^crm-dev-\d{8}T\d{6}Z$")
        return os.path.join(self.runtime, "backups", backups[0])

    def test_backup_writes_dump_data_and_checksums(self):
        dest = self.backup()
        self.assertEqual(sorted(os.listdir(dest)), ["SHA256SUMS", "data.tar.gz", "db.sql.gz"])
        with gzip.open(os.path.join(dest, "db.sql.gz"), "rt") as fh:
            self.assertIn("fake dump", fh.read())
        calls = self.docker_calls()
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].startswith(
            f"compose -p crm-dev -f {REPO}/deploy/compose.json --env-file {self.runtime}/env "
            "exec -T crm-db sh -c"))
        self.assertIn('"$MARIADB_ROOT_PASSWORD"', calls[0], "secret stays in the container")
        res = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=dest, capture_output=True)
        self.assertEqual(res.returncode, 0)

    def test_backup_requires_env_file(self):
        os.remove(os.path.join(self.runtime, "env"))
        res = self.run_script("backup.sh", "dev")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("env file not readable", res.stderr)
        self.assertEqual(self.docker_calls(), [])

    def test_restore_round_trip(self):
        dest = self.backup()
        marker = os.path.join(self.runtime, "data", "upload", "after-backup")
        open(marker, "w").close()
        open(self.log, "w").close()
        res = self.run_script("restore.sh", "dev", os.path.basename(dest))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertRegex(res.stdout, r"restore completed from .* in \d+s")
        self.assertTrue(os.path.isfile(os.path.join(self.runtime, "data", "config.php")))
        self.assertFalse(os.path.exists(marker), "data replaced by the backup copy")
        moved = [d for d in os.listdir(self.runtime) if d.startswith("data.replaced-")]
        self.assertEqual(len(moved), 1, "previous data kept, not deleted")
        with open(self.stdin) as fh:
            self.assertIn("fake dump", fh.read())
        verbs = [c.split(" --env-file ")[1].split(" ", 1)[1] for c in self.docker_calls()]
        self.assertEqual(verbs[0], "stop crm-daemon crm-app")
        self.assertEqual(verbs[1], "up -d --wait crm-db")
        self.assertTrue(verbs[2].startswith("exec -T crm-db sh -c"))
        self.assertEqual(verbs[3], "up -d --wait")

    def test_restore_rejects_tampered_or_missing_backup(self):
        dest = self.backup()
        open(self.log, "w").close()
        res = self.run_script("restore.sh", "dev")
        self.assertNotEqual(res.returncode, 0)
        res = self.run_script("restore.sh", "dev", "no-such-backup")
        self.assertIn("not a backup directory", res.stderr)
        with open(os.path.join(dest, "db.sql.gz"), "ab") as fh:
            fh.write(b"tampered")
        res = self.run_script("restore.sh", "dev", dest)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("checksum mismatch", res.stderr)
        self.assertEqual(self.docker_calls(), [])


class FakeListTransport:
    def __init__(self, records, total_override=None):
        self.records = records
        self.total_override = total_override
        self.calls = []

    def request(self, method, url, headers, body):
        self.calls.append(url)
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(url)
        entity = parsed.path.rsplit("/", 1)[-1]
        q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        rows = self.records[entity]
        off, size = int(q["offset"]), int(q["maxSize"])
        total = self.total_override if self.total_override is not None else len(rows)
        return 200, json.dumps({"total": total, "list": rows[off:off + size]}).encode()


class TestExport(unittest.TestCase):
    def records(self):
        accounts = [{"id": f"a{i:04d}", "name": f"Firm {i}", "phoneNumber": "+442079460001"}
                    for i in range(450)]
        contacts = [{"id": f"c{i:04d}", "firstName": "Sam", "lastName": f"L{i}",
                     "emailAddress": f"s{i}@example.test", "accountId": None}
                    for i in range(205)]
        return {"Account": accounts, "Contact": contacts}

    def test_export_pages_through_everything(self):
        transport = FakeListTransport(self.records())
        with tempfile.TemporaryDirectory() as out:
            client = crm_api.EspoClient("http://127.0.0.1:8180", "u", "p", transport)
            counts = export_csv.export(client, out)
            self.assertEqual(counts, {"Account": 450, "Contact": 205})
            with open(os.path.join(out, "accounts.csv"), newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 450)
            self.assertEqual(rows[0]["phoneNumber"], "+442079460001")
            with open(os.path.join(out, "contacts.csv"), newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["accountId"], "")
        self.assertEqual(len(transport.calls), 3 + 2)
        self.assertTrue(all("orderBy=id" in u for u in transport.calls))

    def test_incomplete_paging_is_an_error(self):
        transport = FakeListTransport(self.records(), total_override=9999)
        client = crm_api.EspoClient("http://127.0.0.1:8180", "u", "p", transport)
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaises(crm_api.ApiError):
                export_csv.export(client, out)

    def test_missing_credentials_fail_loudly(self):
        with tempfile.TemporaryDirectory() as out:
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                code = export_csv.main(["--base-url", "http://127.0.0.1:8180", "--out", out],
                                       transport=FakeListTransport({}), environ={})
            self.assertEqual(code, 2)
            self.assertIn("CRM_ADMIN_PASSWORD", err.getvalue())


if __name__ == "__main__":
    unittest.main()
