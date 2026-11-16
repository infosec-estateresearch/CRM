"""Script tests (WO CRM-001 items 4 and 5): bash -n, the dev guard, and the
backup/restore/export/deploy_custom flows against a fake `docker` and a
temporary runtime directory. No stack, no network."""

import csv
import filecmp
import gzip
import io
import json
import hashlib
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
sys.path.insert(0, SCRIPTS)

import check_access  # noqa: E402
import crm_api  # noqa: E402
import export_csv  # noqa: E402
# Derived private addresses (no literal private address in the repository).
from test_check_access import BIND, SUBNET_A, SUBNET_B  # noqa: E402

GUARDED = ["backup.sh", "restore.sh", "export.sh", "deploy_custom.sh", "up.sh"]
# Valid LAN access settings for the synthetic env files.
ACCESS = {"CRM_BIND_IP": BIND, "CRM_ALLOWED_SOURCES": f"{SUBNET_A} {SUBNET_B}",
          "CRM_SITE_URL": f"http://{BIND}:8180"}
REPO_CUSTOM = os.path.join(REPO, "custom", "Espo", "Custom")

FAKE_DOCKER = """#!/usr/bin/env bash
# Records its arguments; plays mariadb-dump / mariadb inside "crm-db", and
# `compose config --format json` through FAKE_COMPOSE_CONFIG.
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
[ -z "${FAKE_DOCKER_ENV_LOG:-}" ] || env >> "$FAKE_DOCKER_ENV_LOG"
# FAKE_DOCKER_FAIL="<call suffix>@<n>;...": the n-th call ending with that suffix fails.
if [ -n "${FAKE_DOCKER_FAIL:-}" ]; then
    IFS=';' read -ra specs <<< "$FAKE_DOCKER_FAIL"
    for spec in "${specs[@]}"; do
        suffix=${spec%@*}; nth=${spec##*@}
        seen=$(grep -c -F -- "$suffix" "$FAKE_DOCKER_LOG" || true)
        case "$*" in *"$suffix") [ "$seen" != "$nth" ] || { echo "fake docker: injected failure: $suffix" >&2; exit 1; } ;; esac
    done
fi
# FAKE_DOCKER_SIGNAL="<call suffix>@<n>:<SIG>": on the n-th call ending with that suffix the
# script that called docker receives the real signal (its trap runs when this call returns).
if [ -n "${FAKE_DOCKER_SIGNAL:-}" ]; then
    spec=${FAKE_DOCKER_SIGNAL%:*}; sig=${FAKE_DOCKER_SIGNAL##*:}
    suffix=${spec%@*}; nth=${spec##*@}
    seen=$(grep -c -F -- "$suffix" "$FAKE_DOCKER_LOG" || true)
    case "$*" in *"$suffix") [ "$seen" != "$nth" ] || kill -s "$sig" "$PPID" ;; esac
fi
case "$*" in
    *"php bin/command update-app-timestamp")
        # Plays EspoCRM: appTimestamp in data/state.php advances by one (FAKE_APPTS=stuck: never,
        # late: only from the second call on).
        cur=$(sed -n "s/.*'appTimestamp' => \\([0-9]*\\).*/\\1/p" "$FAKE_STATE_FILE" 2>/dev/null | head -n 1)
        cur=${cur:-1000}; new=$((cur + 1))
        calls=$(grep -c -F -- "php bin/command update-app-timestamp" "$FAKE_DOCKER_LOG" || true)
        case "${FAKE_APPTS:-advance}" in
            stuck) new=$cur ;;
            late) [ "$calls" -ge 2 ] || new=$cur ;;
        esac
        printf "<?php\\nreturn array (\\n  'appTimestamp' => %s,\\n  'cacheTimestamp' => 5,\\n);\\n" "$new" > "$FAKE_STATE_FILE" ;;

    *" config --format json") exec python3 -I "$FAKE_COMPOSE_CONFIG" "$@" ;;
    *mariadb-dump*) printf -- '-- fake dump\\nCREATE TABLE account (id int);\\n' ;;
    *"exec -T crm-db"*) cat > "$FAKE_DOCKER_STDIN" ;;
    *" ps --status running -q crm-app"*) [ -z "${FAKE_DOCKER_RUNNING:-}" ] || echo 0123abcd ;;
    *" stop crm-daemon crm-app") [ -z "${FAKE_DOCKER_ON_STOP:-}" ] || bash -c "$FAKE_DOCKER_ON_STOP" ;;
esac
exit 0
"""

# Pins utc_stamp() so a test can plant the deploy's staging/old names in advance.
FAKE_DATE = """#!/usr/bin/env bash
if [ -n "${FAKE_DATE_STAMP:-}" ] && [ "$*" = "-u +%Y%m%dT%H%M%SZ" ]; then
    echo "$FAKE_DATE_STAMP"
    exit 0
fi
exec "$REAL_DATE" "$@"
"""
REAL_DATE = shutil.which("date")

# A secret value the fake resolved config carries; no script may ever print it.
FAKE_SECRET = "fake-secret-must-never-be-printed"

# Plays `docker compose ... --env-file F config --format json` the way Compose
# resolves it: the env file accepts NAME=value and NAME: value (optionally
# `export`, quotes), the last line wins, and the process environment beats the
# file. ${VAR:?msg} in deploy/compose.json is substituted; a missing bind-mount
# variable is an error, any other missing one is filled with FAKE_SECRET.
# FAKE_CONFIG alters the result: "fail", "garbage", "drop:<svc>:<target>",
# "source:<svc>:<target>:<path>" or "type:<svc>:<target>:<type>".
FAKE_COMPOSE_CONFIG = r"""
import json, os, re, sys
args = sys.argv[1:]
compose_file = args[args.index("-f") + 1]
env_file = args[args.index("--env-file") + 1]
mode = os.environ.get("FAKE_CONFIG", "")
if mode == "fail":
    sys.exit("fake compose: config failed")
if mode == "garbage":
    print("not json")
    sys.exit(0)
values = {}
with open(env_file) as fh:
    for raw in fh:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^export\s+", "", line)
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*[=:]\s*(.*)$", line)
        if m:
            value = m.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[m.group(1)] = value
for name in list(values) + ["CRM_DB_DIR", "CRM_DATA_DIR", "CRM_CUSTOM_DIR", "CRM_CLIENT_CUSTOM_DIR"]:
    if name in os.environ:
        values[name] = os.environ[name]
def sub(m):
    name = m.group(1)
    if values.get(name):
        return values[name]
    if name.endswith("_DIR"):
        sys.exit(f"fake compose: required variable {name} is missing a value")
    return FAKE_SECRET
with open(compose_file) as fh:
    text = re.sub(r"\$\{([A-Za-z0-9_]+):\?[^}]*\}", sub, fh.read())
doc = json.loads(text)
for spec in filter(None, mode.split(";")):
    kind, svc, target, *rest = spec.split(":")
    vols = doc["services"][svc]["volumes"]
    for v in list(vols):
        if v["target"] == target:
            if kind == "drop":
                vols.remove(v)
            elif kind == "source":
                v["source"] = rest[0]
            elif kind == "type":
                v["type"] = rest[0]
json.dump(doc, sys.stdout, indent=2)
""".replace("FAKE_SECRET", repr(FAKE_SECRET))


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
        fake_date = os.path.join(self.bin, "date")
        with open(fake_date, "w") as fh:
            fh.write(FAKE_DATE)
        os.chmod(fake_date, stat.S_IRWXU)
        self.compose_config = os.path.join(base, "fake_compose_config.py")
        with open(self.compose_config, "w") as fh:
            fh.write(FAKE_COMPOSE_CONFIG)
        self.log = os.path.join(base, "docker.log")
        self.stdin = os.path.join(base, "docker.stdin")
        self.runtime = os.path.join(base, "runtime", "dev")
        os.makedirs(os.path.join(self.runtime, "data", "upload"))
        with open(os.path.join(self.runtime, "data", "config.php"), "w") as fh:
            fh.write("<?php return [];\n")
        os.makedirs(os.path.join(self.runtime, "custom", "Espo", "Custom"))
        self.write("custom/Espo/Custom/Resources/metadata/entityDefs/Account.json", "{}\n")
        os.makedirs(os.path.join(self.runtime, "client", "custom"))
        self.write("client/custom/res.js", "// client customisation\n")
        self.write_env(self.runtime)

    def write_env(self, runtime, **override):
        values = {"CRM_DB_DIR": f"{runtime}/db",
                  "CRM_DATA_DIR": f"{runtime}/data",
                  "CRM_CUSTOM_DIR": f"{runtime}/custom",
                  "CRM_CLIENT_CUSTOM_DIR": f"{runtime}/client/custom",
                  **ACCESS}
        values.update(override)
        with open(os.path.join(runtime, "env"), "w") as fh:
            fh.write("# synthetic test env\nCRM_DB_NAME=\n")
            for name, value in values.items():
                if value is not None:
                    fh.write(f"{name}={value}\n")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = os.path.join(self.runtime, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
        return path

    def run_script(self, name, *args, runtime=None, extra_env=None, umask=None, scripts=None):
        env = {
            "PATH": self.bin + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
            "CRM_RUNTIME_DIR": runtime or self.runtime,
            "FAKE_DOCKER_LOG": self.log,
            "FAKE_DOCKER_STDIN": self.stdin,
            "HOME": self.tmp.name,
            "REAL_DATE": REAL_DATE,
            "FAKE_COMPOSE_CONFIG": self.compose_config,
            "FAKE_STATE_FILE": os.path.join(runtime or self.runtime, "data", "state.php"),
        }
        env.update(extra_env or {})
        preexec = (lambda: os.umask(umask)) if umask is not None else None
        res = subprocess.run(["bash", os.path.join(scripts or SCRIPTS, name), *args],
                             capture_output=True, text=True, env=env, timeout=60,
                             preexec_fn=preexec)
        self.assertNotIn(FAKE_SECRET, res.stdout + res.stderr, "resolved config printed")
        for value in (BIND, SUBNET_A, SUBNET_B):
            self.assertNotIn(value, res.stdout + res.stderr, "an access value was printed")
        return res

    def docker_calls(self, config=False):
        """docker invocations, without `compose config` unless config=True."""
        if not os.path.exists(self.log):
            return []
        with open(self.log) as fh:
            calls = fh.read().splitlines()
        return calls if config else [c for c in calls if not c.endswith(" config --format json")]

    def verbs(self, config=False):
        return [c.split(" --env-file ")[1].split(" ", 1)[1] for c in self.docker_calls(config)]


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
        self.assertEqual(sorted(os.listdir(self.runtime)), ["client", "custom", "data", "env"],
                         "nothing written")
        self.assertEqual(os.listdir(os.path.join(self.runtime, "custom", "Espo", "Custom")),
                         ["Resources"], "custom untouched")

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
        self.assertEqual(sorted(os.listdir(dest)),
                         ["SHA256SUMS", "TARGET", "client-custom.tar.gz", "custom.tar.gz",
                          "data.tar.gz", "db.sql.gz"])
        with open(os.path.join(dest, "TARGET")) as fh:
            self.assertEqual(fh.read(), "dev\n")  # CRM-007R: the target marker
        tops = {"data.tar.gz": "data/config.php",
                "custom.tar.gz": "custom/Espo/Custom/Resources/metadata/entityDefs/Account.json",
                "client-custom.tar.gz": "client/custom/res.js"}
        for archive, member in tops.items():
            with tarfile.open(os.path.join(dest, archive)) as tf:
                names = tf.getnames()
            self.assertIn(member, names, archive)
            root = member.split("/")[0] if archive != "client-custom.tar.gz" else "client/custom"
            self.assertTrue(all(n == root or n.startswith(root + "/") for n in names),
                            f"{archive} holds only {root}: {names}")
        with open(os.path.join(dest, "SHA256SUMS")) as fh:
            sums = fh.read().splitlines()
        self.assertEqual(len(sums), 5)
        self.assertRegex(sums[-1], r"^[0-9a-f]{64}  TARGET$")
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

    def test_backup_requires_every_persistent_dir(self):
        os.rename(os.path.join(self.runtime, "client", "custom"),
                  os.path.join(self.tmp.name, "moved"))
        res = self.run_script("backup.sh", "dev")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("client/custom directory missing", res.stderr)
        self.assertEqual(self.docker_calls(), [])
        self.assertFalse(os.path.exists(os.path.join(self.runtime, "backups")))

    def test_backup_requires_env_file(self):
        os.remove(os.path.join(self.runtime, "env"))
        res = self.run_script("backup.sh", "dev")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("env file not readable", res.stderr)
        self.assertEqual(self.docker_calls(), [])

    def test_restore_round_trip(self):
        dest = self.backup()
        markers = [self.write(rel, "x") for rel in
                   ("data/upload/after-backup", "custom/Espo/Custom/after-backup.json",
                    "client/custom/after-backup.js")]
        self.write("custom/Espo/Custom/Resources/metadata/entityDefs/Account.json", "changed")
        open(self.log, "w").close()
        res = self.run_script("restore.sh", "dev", os.path.basename(dest))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertRegex(res.stdout, r"restore completed from .* in \d+s")
        self.assertTrue(os.path.isfile(os.path.join(self.runtime, "data", "config.php")))
        for marker in markers:
            self.assertFalse(os.path.exists(marker), f"replaced by the backup copy: {marker}")
        with open(os.path.join(self.runtime, "custom/Espo/Custom/Resources/metadata/"
                               "entityDefs/Account.json")) as fh:
            self.assertEqual(fh.read(), "{}\n")
        with open(os.path.join(self.runtime, "client", "custom", "res.js")) as fh:
            self.assertEqual(fh.read(), "// client customisation\n")
        for parent, name in (("", "data"), ("", "custom"), ("client", "custom")):
            moved = [d for d in os.listdir(os.path.join(self.runtime, parent))
                     if d.startswith(name + ".replaced-")]
            self.assertEqual(len(moved), 1, f"previous {parent}/{name} kept, not deleted")
            kept = os.path.join(self.runtime, parent, moved[0])
            self.assertTrue(any("after-backup" in f for _, _, fs in os.walk(kept) for f in fs))
        with open(self.stdin) as fh:
            self.assertIn("fake dump", fh.read())
        verbs = self.verbs()
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

    def test_restore_rejects_backup_without_customisation(self):
        dest = self.backup()
        open(self.log, "w").close()
        os.remove(os.path.join(dest, "client-custom.tar.gz"))
        sums = os.path.join(dest, "SHA256SUMS")
        with open(sums) as fh:
            lines = [l for l in fh if "client-custom" not in l]
        with open(sums, "w") as fh:
            fh.writelines(lines)
        res = self.run_script("restore.sh", "dev", dest)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("backup is incomplete (no checksummed client-custom.tar.gz)", res.stderr)
        self.assertEqual(self.docker_calls(), [])
        self.assertFalse([d for d in os.listdir(self.runtime) if ".replaced-" in d])


def tree(root):
    """{relative path: file bytes, or None for a directory} under root."""
    out = {}
    for dirpath, dirs, files in os.walk(root):
        for d in dirs:
            out[os.path.relpath(os.path.join(dirpath, d), root)] = None
        for f in files:
            with open(os.path.join(dirpath, f), "rb") as fh:
                out[os.path.relpath(os.path.join(dirpath, f), root)] = fh.read()
    return out


class TestDeployCustom(ScriptEnv):
    def setUp(self):
        super().setUp()
        self.live = os.path.join(self.runtime, "custom", "Espo", "Custom")
        # Admin-UI style edits and a file since removed from Git
        self.write("custom/Espo/Custom/Resources/metadata/entityDefs/Account.json",
                   '{"edited": "in the Admin UI"}')
        self.write("custom/Espo/Custom/Resources/layouts/Account/removedFromGit.json", "[]")
        self.write("custom/Espo/Custom/.hidden-stale", "x")
        # outside Espo/Custom: not managed by the deploy
        self.write("custom/Espo/Modules/Other/keep.txt", "keep")

    def deploy(self, **kw):
        res = self.run_script("deploy_custom.sh", "dev", **kw)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res

    def test_runtime_tree_equals_git_tree(self):
        self.deploy()
        self.assertEqual(tree(self.live), tree(REPO_CUSTOM))
        cmp = filecmp.dircmp(REPO_CUSTOM, self.live)
        self.assertEqual((cmp.left_only, cmp.right_only, cmp.diff_files), ([], [], []))
        self.assertFalse(os.path.exists(os.path.join(
            self.live, "Resources/layouts/Account/removedFromGit.json")), "removed from Git")
        self.assertFalse(os.path.exists(os.path.join(self.live, ".hidden-stale")))
        with open(os.path.join(self.runtime, "custom/Espo/Modules/Other/keep.txt")) as fh:
            self.assertEqual(fh.read(), "keep")
        self.assertEqual(sorted(os.listdir(os.path.join(self.runtime, "custom", "Espo"))),
                         ["Custom", "Modules"], "no staging or old tree left behind")
        with open(os.path.join(self.runtime, "client", "custom", "res.js")) as fh:
            self.assertEqual(fh.read(), "// client customisation\n", "client/custom untouched")

    def test_deploy_is_repeatable_and_world_readable(self):
        self.deploy()
        first = tree(self.live)
        self.deploy(umask=0o077)  # the operator's restrictive umask must not leak in
        self.assertEqual(tree(self.live), first)
        for dirpath, dirs, files in os.walk(self.live):
            for name in dirs + files:
                mode = os.stat(os.path.join(dirpath, name)).st_mode
                self.assertTrue(mode & stat.S_IROTH, f"{name} not readable by www-data")

    def test_first_deploy_into_empty_runtime_custom(self):
        import shutil
        shutil.rmtree(os.path.join(self.runtime, "custom"))
        os.mkdir(os.path.join(self.runtime, "custom"))
        self.deploy()
        self.assertEqual(tree(self.live), tree(REPO_CUSTOM))

    def test_not_running_skips_rebuild(self):
        res = self.deploy()
        self.assertIn("clear-cache/rebuild skipped", res.stdout)
        verbs = self.verbs()
        self.assertEqual(verbs, ["ps --status running -q crm-app", "stop crm-daemon crm-app"])

    def test_running_app_gets_clear_cache_then_rebuild(self):
        res = self.deploy(extra_env={"FAKE_DOCKER_RUNNING": "1"})
        self.assertIn("clear-cache and rebuild completed", res.stdout)
        verbs = self.verbs()
        self.assertEqual(verbs, [
            "ps --status running -q crm-app",
            "stop crm-daemon crm-app",
            "up -d --wait crm-app crm-daemon",
            "exec -T -u www-data -w /var/www/html crm-app php bin/command clear-cache",
            "exec -T -u www-data -w /var/www/html crm-app php bin/command rebuild",
            "exec -T -u www-data -w /var/www/html crm-app php bin/command update-app-timestamp",
        ])

    def test_missing_runtime_custom_dir_fails_and_writes_nothing(self):
        import shutil
        shutil.rmtree(os.path.join(self.runtime, "custom"))
        res = self.run_script("deploy_custom.sh", "dev")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("runtime custom directory missing", res.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.runtime, "custom")))
        self.assertEqual(self.docker_calls(), [])

    def test_requires_env_file(self):
        os.remove(os.path.join(self.runtime, "env"))
        res = self.run_script("deploy_custom.sh", "dev")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("env file not readable", res.stderr)
        self.assertNotEqual(tree(self.live), tree(REPO_CUSTOM), "nothing deployed")



def tree_hash(root):
    """sha256 over every entry under root (type, mode, bytes, link target); never follows links."""
    h = hashlib.sha256()
    for dirpath, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(dirs + files):
            path = os.path.join(dirpath, name)
            st = os.lstat(path)
            h.update(f"{os.path.relpath(path, root)}\0{st.st_mode:o}\0".encode())
            if stat.S_ISLNK(st.st_mode):
                h.update(os.readlink(path).encode())
            elif stat.S_ISREG(st.st_mode):
                with open(path, "rb") as fh:
                    h.update(fh.read())
    return h.hexdigest()


class TestDeployPathSafety(ScriptEnv):
    """CRM-001-C2: a symlink at any component the deploy works on must stop it
    before anything is written through the link, whether the link is there
    before the run or appears while crm-app/crm-daemon are being stopped."""

    STAMP = "20261110T120000Z"
    COMPONENTS = ["", "custom", "custom/Espo", "custom/Espo/Custom"]
    NEW_NAMES = [".Custom.deploy-" + STAMP, ".Custom.old-" + STAMP]

    def setUp(self):
        super().setUp()
        self.write("custom/Espo/Custom/marker.txt", "live tree before the deploy")
        self.sentinel = os.path.join(self.tmp.name, "sentinel")

    def deploy(self, on_stop=None):
        env = {"FAKE_DOCKER_RUNNING": "1", "FAKE_DATE_STAMP": self.STAMP}
        if on_stop:
            env["FAKE_DOCKER_ON_STOP"] = on_stop
        return self.run_script("deploy_custom.sh", "dev", extra_env=env)

    def redirect_cmd(self, rel):
        """Shell command: move the real directory at rel aside to the sentinel
        and leave a symlink to it, so writes through the link land in the sentinel."""
        path = os.path.join(self.runtime, rel) if rel else self.runtime
        return f"mv -T -- {shlex.quote(path)} {shlex.quote(self.sentinel)} && " \
               f"ln -s -- {shlex.quote(self.sentinel)} {shlex.quote(path)}"

    def plant_cmd(self, name):
        """Shell command: an unrelated sentinel directory, and a symlink to it at a staging/old name."""
        link = os.path.join(self.runtime, "custom", "Espo", name)
        return f"mkdir -p {shlex.quote(self.sentinel)} && echo keep > {shlex.quote(self.sentinel)}/keep.txt && " \
               f"ln -s -- {shlex.quote(self.sentinel)} {shlex.quote(link)}"

    def assert_refused(self, res, before, at_stop):
        self.assertNotEqual(res.returncode, 0, res.stdout + res.stderr)
        # Refused by the deploy's own path checks, or earlier by the shared
        # runtime/env-file check in lib/common.sh (runtime dir and custom/).
        self.assertRegex(res.stderr, r"refusing to deploy|not canonical|resolves to")
        self.assertEqual(tree_hash(self.sentinel), before, "symlink target changed")
        verbs = self.verbs()
        self.assertFalse([v for v in verbs if v.startswith(("up", "exec"))], verbs)
        if at_stop:
            self.assertEqual(verbs, ["ps --status running -q crm-app", "stop crm-daemon crm-app"])
            self.assertIn("left stopped", res.stderr)
        else:
            self.assertEqual(verbs, [], "a bad layout is refused before the stack is touched")

    def fresh(self):
        """A new temporary runtime for each subtest."""
        self.tearDown()
        self.setUp()

    def test_symlinked_component_planted_before_the_run(self):
        for rel in self.COMPONENTS:
            with self.subTest(component=rel or "$CRM_RUNTIME_DIR"):
                self.fresh()
                subprocess.run(["bash", "-c", self.redirect_cmd(rel)], check=True)
                before = tree_hash(self.sentinel)
                res = self.deploy()
                self.assert_refused(res, before, at_stop=False)

    def test_symlinked_component_planted_while_the_stack_stops(self):
        for rel in self.COMPONENTS:
            with self.subTest(component=rel or "$CRM_RUNTIME_DIR"):
                self.fresh()
                path = os.path.join(self.runtime, rel) if rel else self.runtime
                before = tree_hash(path)
                res = self.deploy(on_stop=self.redirect_cmd(rel))
                self.assertTrue(os.path.islink(path), "the plant happened")
                self.assert_refused(res, before, at_stop=True)

    def test_preexisting_staging_or_old_name(self):
        reference = os.path.join(self.tmp.name, "reference")
        os.mkdir(reference)
        with open(os.path.join(reference, "keep.txt"), "w") as fh:
            fh.write("keep\n")
        expected = tree_hash(reference)  # what plant_cmd's sentinel holds
        for name in self.NEW_NAMES:
            for at_stop in (False, True):
                with self.subTest(name=name, at_stop=at_stop):
                    self.fresh()
                    live = os.path.join(self.runtime, "custom/Espo/Custom")
                    live_before = tree_hash(live)
                    if at_stop:
                        res = self.deploy(on_stop=self.plant_cmd(name))
                    else:
                        subprocess.run(["bash", "-c", self.plant_cmd(name)], check=True)
                        self.assertEqual(tree_hash(self.sentinel), expected)
                        res = self.deploy()
                    self.assert_refused(res, expected, at_stop=at_stop)
                    self.assertEqual(tree_hash(live), live_before, "live tree untouched")

    def test_dangling_symlink_at_staging_name(self):
        link = os.path.join(self.runtime, "custom", "Espo", self.NEW_NAMES[0])
        os.symlink(os.path.join(self.tmp.name, "does-not-exist"), link)
        res = self.deploy()
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("already exists", res.stderr)
        self.assertFalse(os.path.lexists(os.path.join(self.tmp.name, "does-not-exist")))
        self.assertTrue(os.path.islink(link), "the planted link is reported, not removed")

    def test_group_or_world_writable_runtime_is_refused(self):
        live = os.path.join(self.runtime, "custom/Espo/Custom")
        before = tree_hash(live)
        for mode in (0o775, 0o757, 0o722, 0o1777):
            with self.subTest(mode=oct(mode)):
                os.chmod(self.runtime, mode)
                res = self.deploy()
                self.assertNotEqual(res.returncode, 0)
                self.assertIn("group- or world-writable", res.stderr)
                self.assertEqual(self.docker_calls(), [])
                self.assertEqual(tree_hash(live), before)
        os.chmod(self.runtime, 0o700)
        res = self.deploy()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(tree(live), tree(REPO_CUSTOM), "a private runtime deploys")

    def test_missing_managed_parent_is_created_as_a_real_directory(self):
        shutil.rmtree(os.path.join(self.runtime, "custom", "Espo"))
        res = self.deploy()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertFalse(os.path.islink(os.path.join(self.runtime, "custom", "Espo")))
        self.assertEqual(tree(os.path.join(self.runtime, "custom/Espo/Custom")), tree(REPO_CUSTOM))


class TestEnvPathDivergence(ScriptEnv):
    """CRM-001-C2: deploy, backup and restore refuse unless the env file's
    bind-mount sources are exactly $CRM_RUNTIME_DIR/{data,custom,client/custom}."""

    SCRIPTS = [("deploy_custom.sh",), ("backup.sh",), ("restore.sh", "crm-dev-20261110T120000Z"),
               ("up.sh",)]
    VARS = {"CRM_DATA_DIR": "data", "CRM_CUSTOM_DIR": "custom", "CRM_CLIENT_CUSTOM_DIR": "client/custom"}

    def setUp(self):
        super().setUp()
        # CRM-007R: restore.sh checks the backup (its own, marked) before the
        # env file, so these cases use a valid dev backup.
        from test_beta import make_backup
        os.makedirs(os.path.join(self.runtime, "backups"))
        make_backup(os.path.join(self.runtime, "backups"), "crm-dev-20261110T120000Z")

    def assert_all_refuse(self, needle, extra_env=None, config_ran=False):
        listing = sorted(os.listdir(self.runtime))
        live = tree_hash(os.path.join(self.runtime, "custom"))
        for args in self.SCRIPTS:
            with self.subTest(script=args[0]):
                open(self.log, "w").close()
                res = self.run_script(args[0], "dev", *args[1:], extra_env=extra_env)
                self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                self.assertIn(needle, res.stderr)
                if config_ran:
                    self.assertEqual(self.verbs(config=True), ["config --format json"],
                                     "refused after compose config, before any other docker call")
                else:
                    self.assertEqual(self.docker_calls(config=True), [])
                self.assertEqual(sorted(os.listdir(self.runtime)), listing, "nothing written")
                self.assertEqual(tree_hash(os.path.join(self.runtime, "custom")), live)

    def test_each_divergent_variable_is_refused(self):
        for name, rel in self.VARS.items():
            with self.subTest(var=name):
                elsewhere = os.path.join(self.tmp.name, "elsewhere", rel)
                os.makedirs(elsewhere, exist_ok=True)
                self.write_env(self.runtime, **{name: elsewhere})
                self.assert_all_refuse(f"{name} in {self.runtime}/env is '{elsewhere}'")

    def test_each_missing_variable_is_refused(self):
        for name in self.VARS:
            with self.subTest(var=name):
                self.write_env(self.runtime, **{name: None})
                self.assert_all_refuse(f"must set {name} exactly once (found 0)")

    def test_ambiguous_relative_or_aliased_values_are_refused(self):
        cases = {
            "duplicate": ("CRM_DATA_DIR", f"{self.runtime}/data\nexport CRM_DATA_DIR=/elsewhere",
                          "exactly once (found 2)"),
            "relative": ("CRM_CUSTOM_DIR", "./custom", "must be an absolute path"),
            "sibling prefix": ("CRM_DATA_DIR", f"{self.runtime}/data-old", "resolves to"),
        }
        for label, (name, value, needle) in cases.items():
            with self.subTest(case=label):
                self.write_env(self.runtime, **{name: value})
                self.assert_all_refuse(needle)
        # a symlinked data/ resolves outside the runtime even with the right spelling
        self.write_env(self.runtime)
        os.rename(os.path.join(self.runtime, "data"), os.path.join(self.tmp.name, "data-real"))
        os.symlink(os.path.join(self.tmp.name, "data-real"), os.path.join(self.runtime, "data"))
        self.assert_all_refuse("CRM_DATA_DIR")

    def test_equivalent_spellings_are_accepted(self):
        self.write_env(self.runtime, CRM_DATA_DIR=f'"{self.runtime}/data/"',
                       CRM_CUSTOM_DIR=f"'{self.runtime}/./custom'")
        res = self.run_script("backup.sh", "dev")
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_non_canonical_runtime_dir_is_refused(self):
        res = self.run_script("backup.sh", "dev", runtime=self.runtime + "/../dev")
        self.assertEqual(res.returncode, 1)
        self.assertIn("not canonical", res.stderr)
        self.assertEqual(self.docker_calls(), [])


class TestEnvOverrideAndResolvedMounts(TestEnvPathDivergence):
    """CRM-001-C2 round 2: Compose takes the bind-mount variables from the
    process environment before the env file, and its env-file parser also
    accepts NAME: value with the last line winning. Both must be refused, and
    what Compose itself resolves must match the runtime."""

    ALL_VARS = ["CRM_DB_DIR", "CRM_DATA_DIR", "CRM_CUSTOM_DIR", "CRM_CLIENT_CUSTOM_DIR"]

    def write_raw_env(self, *lines):
        with open(os.path.join(self.runtime, "env"), "w") as fh:
            fh.write("".join(line + "\n" for line in lines))

    def plain_lines(self, **skip):
        values = {"CRM_DB_DIR": f"{self.runtime}/db", "CRM_DATA_DIR": f"{self.runtime}/data",
                  "CRM_CUSTOM_DIR": f"{self.runtime}/custom",
                  "CRM_CLIENT_CUSTOM_DIR": f"{self.runtime}/client/custom", **ACCESS}
        return [f"{k}={v}" for k, v in values.items() if k not in skip]

    def test_shell_override_is_refused(self):
        # The reported case: CRM_CUSTOM_DIR=/etc exported, env file correct.
        self.assert_all_refuse("CRM_CUSTOM_DIR is set in the environment",
                               extra_env={"CRM_CUSTOM_DIR": "/etc"})
        for name in self.ALL_VARS:
            for value in ("/etc", "", f"{self.runtime}/x"):
                with self.subTest(var=name, value=value):
                    self.assert_all_refuse(f"{name} is set in the environment",
                                           extra_env={name: value})

    def test_colon_form_and_other_second_assignments_are_refused(self):
        custom = f"{self.runtime}/custom"
        for extra in ("CRM_CUSTOM_DIR: /etc", "CRM_CUSTOM_DIR:/etc", "  CRM_CUSTOM_DIR : /etc",
                      "export CRM_CUSTOM_DIR: /etc", "\tCRM_CUSTOM_DIR=/etc",
                      "CRM_CUSTOM_DIR", f"CRM_CUSTOM_DIR: {custom}"):
            with self.subTest(extra=extra):
                self.write_raw_env(*self.plain_lines(), extra)
                self.assert_all_refuse("must set CRM_CUSTOM_DIR exactly once (found 2)")

    def test_single_non_plain_assignment_is_refused(self):
        custom = f"{self.runtime}/custom"
        for only in (f"CRM_CUSTOM_DIR: {custom}", f"export CRM_CUSTOM_DIR={custom}",
                     f" CRM_CUSTOM_DIR={custom}", f"CRM_CUSTOM_DIR ={custom}"):
            with self.subTest(line=only):
                self.write_raw_env(*self.plain_lines(CRM_CUSTOM_DIR=1), only)
                self.assert_all_refuse("in the plain form CRM_CUSTOM_DIR=<path>")

    def test_longer_names_are_not_counted(self):
        self.write_raw_env(*self.plain_lines(), "CRM_CUSTOM_DIR_OLD: /etc", "CRM_CUSTOM_DIRS=/etc")
        res = self.run_script("backup.sh", "dev")
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_compose_resolved_mounts_must_match(self):
        cases = {
            "fail": "compose config failed",
            "garbage": "compose config failed",
            "drop:crm-daemon:/var/www/html/custom": "crm-daemon /var/www/html/custom: 0 mounts",
            "source:crm-app:/var/www/html/custom:/etc": "crm-app /var/www/html/custom: Compose resolves the source to '/etc'",
            "source:crm-daemon:/var/www/html/data:/etc": "crm-daemon /var/www/html/data: Compose resolves",
            f"source:crm-app:/var/www/html/client/custom:{self.runtime}/client/custom-old":
                "crm-app /var/www/html/client/custom: Compose resolves",
            f"source:crm-app:/var/www/html/data:{self.runtime}/data/../../dev/data/x/..": None,
            "type:crm-daemon:/var/www/html/data:volume": "crm-daemon /var/www/html/data: Compose resolves",
        }
        for mode, needle in cases.items():
            with self.subTest(fake_config=mode):
                if needle is None:  # normalises to the right path, still refused: no '..' 
                    needle = "crm-app /var/www/html/data: Compose resolves"
                self.assert_all_refuse(needle, extra_env={"FAKE_CONFIG": mode}, config_ran=True)

    def test_resolved_mounts_check_passes_on_a_good_config_and_runs_first(self):
        res = self.run_script("deploy_custom.sh", "dev")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.verbs(config=True)[:2], ["config --format json",
                                                       "ps --status running -q crm-app"])

    def test_compose_wrapper_removes_every_env_file_variable(self):
        envlog = os.path.join(self.tmp.name, "docker.env")
        names = check_access.env_example_names()
        self.assertTrue(set(self.ALL_VARS) | set(check_access.NAMES) <= set(names))
        env = {"PATH": self.bin + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
               "FAKE_DOCKER_LOG": self.log, "FAKE_DOCKER_ENV_LOG": envlog,
               "FAKE_COMPOSE_CONFIG": self.compose_config, "KEEP_ME": "1",
               **{name: "/etc" for name in names}}
        script = f". {shlex.quote(os.path.join(SCRIPTS, 'lib', 'common.sh'))}; " \
                 f"CRM_ENV_FILE={shlex.quote(os.path.join(self.runtime, 'env'))}; compose ps"
        subprocess.run(["bash", "-c", script], env=env, check=True)
        with open(envlog) as fh:
            seen = {line.split("=", 1)[0] for line in fh.read().splitlines() if "=" in line}
        self.assertIn("KEEP_ME", seen)
        self.assertEqual(seen & set(names), set(), "env-file variables reached docker")


def run_common(script, env=None, repo_lib=None):
    """Run bash code after sourcing scripts/lib/common.sh (or another copy)."""
    lib = repo_lib or os.path.join(SCRIPTS, "lib", "common.sh")
    return subprocess.run(["bash", "-c", f". {shlex.quote(lib)}; {script}"], capture_output=True,
                          text=True, env=env or {"PATH": os.environ.get("PATH", "/usr/bin:/bin")})


class TestSharedEnvNames(unittest.TestCase):
    """CRM-001-LAN round 2: one list of env-file names, read from deploy/env.example."""

    def test_shell_list_equals_env_example(self):
        res = run_common('printf "%s\\n" "${CRM_ENV_NAMES[@]}"')
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(REPO, "deploy", "env.example")) as fh:
            independent = [l.split("=", 1)[0] for l in fh
                           if l[:1].isupper() and "=" in l and not l.startswith("#")]
        self.assertEqual(res.stdout.split(), independent)
        self.assertEqual(res.stdout.split(), check_access.env_example_names())
        self.assertEqual(len(independent), 13)

    def test_missing_env_example_fails_closed(self):
        with tempfile.TemporaryDirectory() as repo:
            os.makedirs(os.path.join(repo, "scripts", "lib"))
            lib = os.path.join(repo, "scripts", "lib", "common.sh")
            shutil.copy(os.path.join(SCRIPTS, "lib", "common.sh"), lib)
            bin_dir = os.path.join(repo, "bin")
            os.mkdir(bin_dir)
            log = os.path.join(repo, "docker.log")
            with open(os.path.join(bin_dir, "docker"), "w") as fh:
                fh.write(f"#!/bin/sh\necho \"$*\" >> {shlex.quote(log)}\n")
            os.chmod(os.path.join(bin_dir, "docker"), stat.S_IRWXU)
            env = {"PATH": bin_dir + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")}
            for call in ("CRM_ENV_FILE=/x; compose up -d", "require_runtime_paths"):
                with self.subTest(call=call):
                    res = run_common(call, env=env, repo_lib=lib)
                    self.assertEqual(res.returncode, 1)
                    self.assertIn("no variable names could be read", res.stderr)
            self.assertFalse(os.path.exists(log), "docker never ran")


class TestAccessEnforced(ScriptEnv):
    """CRM-001-LAN round 2 (script-env-override): every script that can start or
    recreate a service refuses, before any docker call, when the LAN access
    settings would be bypassed or are invalid. Against the round-1 candidate
    (49bbbe0) deploy_custom.sh and restore.sh exit 0 and run `up` in each case."""

    STARTERS = ["deploy_custom.sh", "restore.sh", "up.sh"]

    def make_backup(self):
        res = self.run_script("backup.sh", "dev")
        self.assertEqual(res.returncode, 0, res.stderr)
        return os.listdir(os.path.join(self.runtime, "backups"))[0]

    def run_starter(self, script, backup, extra_env=None):
        open(self.log, "w").close()
        args = [backup] if script == "restore.sh" else []
        env = {"FAKE_DOCKER_RUNNING": "1", **(extra_env or {})}
        return self.run_script(script, "dev", *args, extra_env=env)

    def assert_refused_before_docker(self, needle, extra_env=None):
        backup = self.make_backup()
        live = tree_hash(os.path.join(self.runtime, "custom"))
        for script in self.STARTERS:
            with self.subTest(script=script):
                res = self.run_starter(script, backup, extra_env)
                self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                self.assertIn(needle, res.stderr)
                self.assertEqual(self.verbs(), [], "refused before the stack is touched")
                self.assertEqual(tree_hash(os.path.join(self.runtime, "custom")), live)
                self.assertFalse([d for d in os.listdir(self.runtime) if ".replaced-" in d])

    def test_good_settings_start_the_stack(self):
        backup = self.make_backup()
        for script in self.STARTERS:
            with self.subTest(script=script):
                res = self.run_starter(script, backup)
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertIn("access settings OK", res.stdout)
                self.assertTrue([v for v in self.verbs() if v.startswith("up -d --wait")])

    def test_exported_bind_ip_is_refused(self):
        self.assert_refused_before_docker("CRM_BIND_IP is set in the environment",
                                          {"CRM_BIND_IP": "0.0.0.0"})

    def test_exported_allowed_sources_is_refused(self):
        self.assert_refused_before_docker("CRM_ALLOWED_SOURCES is set in the environment",
                                          {"CRM_ALLOWED_SOURCES": "0.0.0.0/0"})

    def test_exported_site_url_is_refused(self):
        self.assert_refused_before_docker("CRM_SITE_URL is set in the environment",
                                          {"CRM_SITE_URL": "http://127.0.0.1:8180"})

    def test_invalid_env_file_sources_are_refused(self):
        self.write_env(self.runtime, CRM_ALLOWED_SOURCES="0.0.0.0/0")
        self.assert_refused_before_docker("failed scripts/check_access.py")

    def test_bind_ip_outside_the_sources_is_refused(self):
        self.write_env(self.runtime, CRM_ALLOWED_SOURCES=SUBNET_B)
        self.assert_refused_before_docker("failed scripts/check_access.py")

    def test_every_env_example_name_is_refused_when_exported(self):
        names = check_access.env_example_names()
        backup = self.make_backup()
        for name in names:
            for script in self.STARTERS + ["backup.sh"]:
                with self.subTest(name=name, script=script):
                    res = self.run_starter(script, backup, {name: "x"})
                    self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                    self.assertIn(f"{name} is set in the environment", res.stderr)
                    self.assertEqual(self.docker_calls(config=True), [])

    def test_env_file_other_than_the_runtime_env_is_refused(self):
        other = os.path.join(self.tmp.name, "other.env")
        shutil.copy(os.path.join(self.runtime, "env"), other)
        backup = self.make_backup()
        for value in (other, self.runtime + "/env.bak"):
            for script in self.STARTERS + ["backup.sh"]:
                with self.subTest(env_file=value, script=script):
                    res = self.run_starter(script, backup, {"CRM_ENV_FILE": value})
                    self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                    self.assertIn(f"the env file must be {self.runtime}/env", res.stderr)
                    self.assertEqual(self.docker_calls(config=True), [])
        res = self.run_starter("up.sh", backup, {"CRM_ENV_FILE": os.path.join(self.runtime, "env")})
        self.assertEqual(res.returncode, 0, res.stderr)


class TestUp(ScriptEnv):
    """scripts/up.sh dev: guard, path checks and access check, then up -d --wait."""

    def test_runs_the_checks_then_up(self):
        res = self.run_script("up.sh", "dev")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("access settings OK", res.stdout)
        self.assertEqual(self.verbs(config=True), ["config --format json", "up -d --wait"])

    def test_extra_arguments_are_appended(self):
        res = self.run_script("up.sh", "dev", "--force-recreate", "crm-app")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.verbs(), ["up -d --wait --force-recreate crm-app"])

    def test_missing_access_setting_is_refused(self):
        for name in check_access.NAMES:
            with self.subTest(name=name):
                open(self.log, "w").close()
                self.write_env(self.runtime, **{name: None})
                res = self.run_script("up.sh", "dev")
                self.assertEqual(res.returncode, 1)
                self.assertIn(f"must set {name} exactly once (found 0)", res.stderr)
                self.assertEqual(self.verbs(), [])


class TestRemoveTree(unittest.TestCase):
    """remove_tree() from deploy_custom.sh, run on its own: it refuses a
    symlink and passes --one-file-system to rm."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name
        self.sentinel = os.path.join(self.base, "sentinel")
        os.makedirs(os.path.join(self.sentinel, "sub"))
        with open(os.path.join(self.sentinel, "sub", "keep.txt"), "w") as fh:
            fh.write("keep\n")
        self.bin = os.path.join(self.base, "bin")
        os.mkdir(self.bin)
        self.rm_log = os.path.join(self.base, "rm.log")
        rm = os.path.join(self.bin, "rm")
        with open(rm, "w") as fh:
            fh.write(f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$RM_LOG"\nexec {shutil.which("rm")} "$@"\n')
        os.chmod(rm, stat.S_IRWXU)

    def tearDown(self):
        self.tmp.cleanup()

    def remove_tree(self, path):
        script = "eval \"$(sed -n '/^remove_tree() {/,/^}/p' \"$1\")\"; " \
                 "declare -F remove_tree >/dev/null || exit 99; remove_tree \"$2\""
        return subprocess.run(["bash", "-c", script, "deploy_custom.sh",
                               os.path.join(SCRIPTS, "deploy_custom.sh"), path],
                              capture_output=True, text=True,
                              env={"PATH": self.bin + os.pathsep + os.environ.get("PATH", ""),
                                   "RM_LOG": self.rm_log})

    def rm_calls(self):
        if not os.path.exists(self.rm_log):
            return []
        with open(self.rm_log) as fh:
            return fh.read().splitlines()

    def test_refuses_a_symlink(self):
        before = tree_hash(self.sentinel)
        for target in (self.sentinel, os.path.join(self.base, "missing")):
            with self.subTest(target=target):
                link = os.path.join(self.base, ".Custom.old-x")
                os.symlink(target, link)
                res = self.remove_tree(link)
                self.assertEqual(res.returncode, 1, res.stderr)
                self.assertIn("not removing a symlink", res.stderr)
                self.assertTrue(os.path.islink(link), "the link is left for inspection")
                self.assertEqual(self.rm_calls(), [], "rm never ran")
                self.assertEqual(tree_hash(self.sentinel), before)
                os.remove(link)

    def test_removes_a_real_tree_on_one_filesystem_only(self):
        tree_dir = os.path.join(self.base, ".Custom.old-x")
        os.makedirs(os.path.join(tree_dir, "a"))
        os.symlink(self.sentinel, os.path.join(tree_dir, "a", "link"))
        before = tree_hash(self.sentinel)
        res = self.remove_tree(tree_dir)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertFalse(os.path.lexists(tree_dir))
        self.assertEqual(tree_hash(self.sentinel), before, "links inside are not followed")
        # A mount point cannot be created without privileges here, so the flag
        # is checked on the rm invocation itself.
        self.assertEqual(self.rm_calls(), [f"-rf --one-file-system -- {tree_dir}"])

    def test_missing_path_is_a_no_op(self):
        res = self.remove_tree(os.path.join(self.base, "absent"))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.rm_calls(), [])


class TestDeploySecuresCustomDirs(ScriptEnv):
    """After the stop, custom/ and custom/Espo are owned by the invoking uid and
    not group- or world-writable, so a host process with the container's uid
    cannot swap entries in them. The tests run unprivileged: they cannot create
    a directory owned by another uid, so the owner part is checked through the
    chown invocation and the resulting (own) uid; the mode part is checked fully."""

    def setUp(self):
        super().setUp()
        self.custom = os.path.join(self.runtime, "custom")
        self.espo = os.path.join(self.custom, "Espo")
        self.chown_log = os.path.join(self.tmp.name, "chown.log")
        chown = os.path.join(self.bin, "chown")
        with open(chown, "w") as fh:
            fh.write(f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$CHOWN_LOG"\n'
                     f'exec {shutil.which("chown")} "$@"\n')
        os.chmod(chown, stat.S_IRWXU)

    def deploy(self, **env):
        return self.run_script("deploy_custom.sh", "dev",
                               extra_env={"FAKE_DOCKER_RUNNING": "1", "CHOWN_LOG": self.chown_log, **env})

    def chown_calls(self):
        if not os.path.exists(self.chown_log):
            return []
        with open(self.chown_log) as fh:
            return fh.read().splitlines()

    def assert_private(self, path):
        st = os.lstat(path)
        self.assertTrue(stat.S_ISDIR(st.st_mode))
        self.assertEqual(st.st_uid, os.getuid())
        self.assertEqual(st.st_mode & 0o022, 0, f"{path} mode {st.st_mode & 0o7777:o}")

    def test_writable_dirs_are_made_private_after_the_stop(self):
        os.chmod(self.custom, 0o777)
        # the "container" re-opens both while the stack stops
        on_stop = f"chmod 0777 {shlex.quote(self.custom)} {shlex.quote(self.espo)}"
        res = self.deploy(FAKE_DOCKER_ON_STOP=on_stop)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assert_private(self.custom)
        self.assert_private(self.espo)
        uid = os.getuid()
        client_custom = os.path.join(self.runtime, "client", "custom")
        self.assertEqual(self.chown_calls(), [f"-h -- {uid} {self.custom}", f"-h -- {uid} {self.espo}",
                                              f"-h -- {uid} {client_custom}"],
                         "non-recursive, no-dereference chown of exactly the three directories "
                         "(CRM-CLIENT-001R2 adds client/custom)")
        self.assertEqual(tree(os.path.join(self.espo, "Custom")), tree(REPO_CUSTOM))

    def test_created_parent_is_private(self):
        shutil.rmtree(self.espo)
        res = self.deploy(FAKE_DOCKER_ON_STOP=f"chmod 0777 {shlex.quote(self.custom)}")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assert_private(self.custom)
        self.assert_private(self.espo)

    def test_check_paths_refuses_if_the_mode_did_not_change(self):
        # chmod that silently does nothing: the authoritative check must catch it
        noop = os.path.join(self.bin, "chmod")
        with open(noop, "w") as fh:
            fh.write("#!/usr/bin/env bash\nexit 0\n")
        os.chmod(noop, stat.S_IRWXU)
        live = os.path.join(self.espo, "Custom")
        before = tree_hash(live)
        for path in (self.custom, self.espo):
            with self.subTest(path=path):
                os.chmod(self.custom, 0o755)
                os.chmod(self.espo, 0o755)
                open(self.log, "w").close()
                res = self.deploy(FAKE_DOCKER_ON_STOP=f"{shutil.which('chmod')} 0757 {shlex.quote(path)}")
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(f"refusing to deploy: group- or world-writable (mode 757): {path}", res.stderr)
                self.assertIn("left stopped", res.stderr)
                self.assertEqual(self.verbs(), ["ps --status running -q crm-app", "stop crm-daemon crm-app"])
                self.assertEqual(tree_hash(live), before)

    def test_check_paths_owned_verifies_custom_and_parent(self):
        # check_paths from deploy_custom.sh on its own: the first pass accepts a
        # container-owned (here: writable) custom/, the "owned" pass does not.
        script = "for f in real_dir absent owned_private check_paths; do " \
                 "eval \"$(sed -n \"/^$f() {/,/^}/p\" \"$1\")\"; declare -F $f >/dev/null || exit 99; done; " \
                 "die() { echo \"$*\" >&2; exit 1; }; CRM_RUNTIME_DIR=$2; runtime_custom=$2/custom; " \
                 "parent=$2/custom/Espo; live=$parent/Custom; staging=$parent/.s; old=$parent/.o; check_paths $3"
        def check(arg):
            return subprocess.run(["bash", "-c", script, "check", os.path.join(SCRIPTS, "deploy_custom.sh"),
                                   self.runtime, arg], capture_output=True, text=True)
        self.assertEqual(check("owned").returncode, 0, check("owned").stderr)
        for path in (self.custom, self.espo):
            with self.subTest(path=path):
                os.chmod(path, 0o757)
                self.assertEqual(check("").returncode, 0, "first pass does not require ownership")
                res = check("owned")
                self.assertEqual(res.returncode, 1)
                self.assertIn(f"group- or world-writable (mode 757): {path}", res.stderr)
                os.chmod(path, 0o755)


# ---------------------------------------------------------------- CRM-CLIENT-001R2
REPO_SRC = os.path.join(REPO, "client", "custom", "src")
APPTS = "php bin/command update-app-timestamp"
UP = "up -d --wait crm-app crm-daemon"
STOP = "stop crm-daemon crm-app"
CLEAR = "php bin/command clear-cache"
REBUILD = "php bin/command rebuild"
CMD_PREFIX = "exec -T -u www-data -w /var/www/html crm-app "


class ClientDeployBase(ScriptEnv):
    """deploy_custom.sh with the client tree: runtime client/custom holds a stale src/,
    EspoCRM's reserved modules/ and another entry that the deploy must never touch."""

    STAMP = "20261116T120000Z"

    def setUp(self):
        super().setUp()
        self.custom_live = os.path.join(self.runtime, "custom", "Espo", "Custom")
        self.cc = os.path.join(self.runtime, "client", "custom")
        self.live_src = os.path.join(self.cc, "src")
        self.write("custom/Espo/Custom/marker.txt", "previous custom tree")
        self.write("client/custom/src/crm/previous-only.js", "define([], function () { return {}; });\n")
        self.write("client/custom/src/stale/old.txt", "stale\n")
        self.write("client/custom/modules/Ext/ext.js", "// extension, not ours\n")
        self.write("client/custom/other.txt", "not under src\n")
        self.write("data/state.php", "<?php\nreturn array (\n  'appTimestamp' => 1000,\n);\n")
        self.mvlog = os.path.join(self.tmp.name, "mv.log")
        mv = os.path.join(self.bin, "mv")
        # FAKE_MV_FAIL: every mv whose arguments contain it fails. FAKE_MV_FAIL_ONCE: only the
        # first one does. FAKE_MV_SIGNAL="<pattern>:<SIG>": the first matching mv sends the real
        # signal to the deploy script, then runs (the trap fires when mv returns).
        with open(mv, "w") as fh:
            fh.write('#!/usr/bin/env bash\nprintf "MV %s\\n" "$*" >> "$MV_LOG"\n'
                     'if [ -n "${FAKE_MV_FAIL:-}" ]; then case "$*" in *"$FAKE_MV_FAIL"*) exit 1 ;; esac; fi\n'
                     'if [ -n "${FAKE_MV_FAIL_ONCE:-}" ]; then case "$*" in *"$FAKE_MV_FAIL_ONCE"*)\n'
                     '  [ -e "$MV_LOG.once" ] || { : > "$MV_LOG.once"; exit 1; } ;; esac; fi\n'
                     'if [ -n "${FAKE_MV_SIGNAL:-}" ]; then pat=${FAKE_MV_SIGNAL%:*}; sig=${FAKE_MV_SIGNAL##*:}\n'
                     '  case "$*" in *"$pat"*) [ -e "$MV_LOG.sig" ] || { : > "$MV_LOG.sig"; kill -s "$sig" "$PPID"; } ;; esac; fi\n'
                     f'exec {shutil.which("mv")} "$@"\n')
        os.chmod(mv, stat.S_IRWXU)
        # FAKE_CP_SIGNAL="<pattern>:<SIG>": the first matching cp signals the deploy script, then copies.
        cp = os.path.join(self.bin, "cp")
        with open(cp, "w") as fh:
            fh.write('#!/usr/bin/env bash\nif [ -n "${FAKE_CP_SIGNAL:-}" ]; then pat=${FAKE_CP_SIGNAL%:*}; '
                     'sig=${FAKE_CP_SIGNAL##*:}\n  case "$*" in *"$pat"*) [ -e "$MV_LOG.cpsig" ] || '
                     '{ : > "$MV_LOG.cpsig"; kill -s "$sig" "$PPID"; } ;; esac; fi\n'
                     f'exec {shutil.which("cp")} "$@"\n')
        os.chmod(cp, stat.S_IRWXU)
        sleep = os.path.join(self.bin, "sleep")
        with open(sleep, "w") as fh:
            fh.write('#!/usr/bin/env bash\nprintf "SLEEP %s\\n" "$*" >> "$MV_LOG"\nexit 0\n')
        os.chmod(sleep, stat.S_IRWXU)

    def repo_copy(self, name="repo-b"):
        dst = os.path.join(self.tmp.name, name)
        for d in ("scripts", "deploy", "custom", "client"):
            shutil.copytree(os.path.join(REPO, d), os.path.join(dst, d), symlinks=True,
                            ignore=shutil.ignore_patterns("__pycache__"))
        return dst

    def deploy(self, repo=None, running=True, on_stop=None, umask=None, **env):
        e = {"FAKE_DATE_STAMP": self.STAMP, "MV_LOG": self.mvlog}
        if running:
            e["FAKE_DOCKER_RUNNING"] = "1"
        if on_stop:
            e["FAKE_DOCKER_ON_STOP"] = on_stop
        e.update(env)
        return self.run_script("deploy_custom.sh", "dev", extra_env=e, umask=umask,
                               scripts=os.path.join(repo, "scripts") if repo else None)

    def non_src(self):
        """Everything under client/custom except src/ and the deploy's own .src.* names."""
        return {k: v for k, v in tree(self.cc).items()
                if k.split("/")[0] != "src" and not k.split("/")[0].startswith(".src.")}

    def appts(self):
        with open(os.path.join(self.runtime, "data", "state.php")) as fh:
            import re
            return int(re.search(r"'appTimestamp' => (\d+)", fh.read()).group(1))

    def mv_lines(self):
        if not os.path.exists(self.mvlog):
            return []
        with open(self.mvlog) as fh:
            return fh.read().splitlines()


class TestDeployClientTree(ClientDeployBase):
    """AC2 and AC3: client/custom/src is replaced as a whole, staged and renamed on the
    same filesystem after the stop; modules/ and every other entry stay byte-identical."""

    def test_src_replaced_as_a_whole_and_removed_files_disappear(self):
        before_other = self.non_src()
        self.deploy()
        self.assertEqual(tree(self.live_src), tree(REPO_SRC))
        self.assertFalse(os.path.exists(os.path.join(self.live_src, "crm", "previous-only.js")))
        self.assertFalse(os.path.exists(os.path.join(self.live_src, "stale")))
        self.assertEqual(self.non_src(), before_other, "modules/ and other entries untouched")
        self.assertEqual(sorted(os.listdir(self.cc)), ["modules", "other.txt", "res.js", "src"],
                         "no staging, old or failed tree left behind")
        self.assertEqual(sorted(os.listdir(os.path.join(self.runtime, "custom", "Espo"))), ["Custom"])
        self.assertEqual(tree(self.custom_live), tree(REPO_CUSTOM))
        for dirpath, dirs, files in os.walk(self.live_src):
            for name in dirs + files:
                self.assertTrue(os.stat(os.path.join(dirpath, name)).st_mode & stat.S_IROTH, name)

    def test_modules_and_other_entries_are_byte_identical_across_a_deploy(self):
        modules = os.path.join(self.cc, "modules")
        before = (tree_hash(modules), self.non_src())
        self.deploy(umask=0o077)
        self.assertEqual((tree_hash(modules), self.non_src()), before)

    def test_first_deploy_creates_src_when_the_runtime_has_none(self):
        shutil.rmtree(self.live_src)
        self.deploy()
        self.assertEqual(tree(self.live_src), tree(REPO_SRC))

    def test_deploy_is_repeatable(self):
        self.deploy()
        first = tree(self.live_src)
        self.deploy()
        self.assertEqual(tree(self.live_src), first)

    def test_staged_and_renamed_beside_the_live_tree_after_the_stop(self):
        res = self.deploy(on_stop=f"echo STOP >> {shlex.quote(self.mvlog)}")
        self.assertEqual(res.returncode, 0, res.stderr)
        lines = self.mv_lines()
        self.assertEqual(lines[0], "STOP", "the stack is stopped before anything is swapped")
        staging = os.path.join(self.cc, f".src.deploy-{self.STAMP}")
        old = os.path.join(self.cc, f".src.old-{self.STAMP}")
        self.assertIn(f"MV -T -- {self.live_src} {old}", lines)
        self.assertIn(f"MV -T -- {staging} {self.live_src}", lines)
        self.assertLess(lines.index(f"MV -T -- {self.live_src} {old}"),
                        lines.index(f"MV -T -- {staging} {self.live_src}"))
        self.assertEqual(os.path.dirname(staging), os.path.dirname(self.live_src), "same filesystem")
        # the custom/Espo/Custom tree is swapped first
        self.assertLess([i for i, l in enumerate(lines) if ".Custom.deploy-" in l][0],
                        lines.index(f"MV -T -- {staging} {self.live_src}"))

    def test_repository_without_client_source_is_refused_before_any_docker_call(self):
        repo = self.repo_copy()
        shutil.rmtree(os.path.join(repo, "client", "custom", "src"))
        before = (tree_hash(self.live_src), tree_hash(self.custom_live))
        res = self.deploy(repo)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("repository client customisation missing", res.stderr)
        self.assertEqual(self.docker_calls(), [])
        self.assertEqual((tree_hash(self.live_src), tree_hash(self.custom_live)), before)

    def test_symlink_in_the_repository_source_is_refused(self):
        repo = self.repo_copy()
        os.symlink("/etc", os.path.join(repo, "client", "custom", "src", "crm", "link.js"))
        before = (tree_hash(self.live_src), tree_hash(self.custom_live))
        res = self.deploy(repo)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("symlink in", res.stderr)
        self.assertEqual(self.docker_calls(), [])
        self.assertEqual((tree_hash(self.live_src), tree_hash(self.custom_live)), before)

    def test_missing_runtime_client_custom_is_refused_and_writes_nothing(self):
        shutil.rmtree(os.path.join(self.runtime, "client"))
        res = self.deploy()
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("runtime client/custom directory missing", res.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.runtime, "client")))
        self.assertEqual(self.docker_calls(), [])


class TestDeployClientPathSafety(ClientDeployBase):
    """AC2: a symlinked or redirected client, client/custom or src, or a planted working
    name, stops the deploy before any swap, whether planted before or while the stack stops."""

    COMPONENTS = ["client", "client/custom", "client/custom/src"]
    NAMES = [(".src.deploy-", "client/custom"), (".src.old-", "client/custom"),
             (".src.failed-", "client/custom"), (".Custom.failed-", "custom/Espo")]

    def setUp(self):
        super().setUp()
        self.sentinel = os.path.join(self.tmp.name, "sentinel")

    def redirect_cmd(self, rel):
        path = os.path.join(self.runtime, rel)
        return f"mv -T -- {shlex.quote(path)} {shlex.quote(self.sentinel)} && " \
               f"ln -s -- {shlex.quote(self.sentinel)} {shlex.quote(path)}"

    def plant_cmd(self, prefix, where):
        link = os.path.join(self.runtime, where, prefix + self.STAMP)
        return f"mkdir -p {shlex.quote(self.sentinel)} && echo keep > {shlex.quote(self.sentinel)}/keep.txt && " \
               f"ln -s -- {shlex.quote(self.sentinel)} {shlex.quote(link)}"

    def fresh(self):
        self.tearDown()
        self.setUp()

    def assert_refused_before_swap(self, res, at_stop):
        self.assertNotEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertRegex(res.stderr, r"refusing to deploy|not canonical|resolves to|already exists")
        self.assertNotIn("customisation deployed", res.stdout)
        verbs = self.verbs()
        self.assertFalse([v for v in verbs if v.startswith(("up", "exec"))], verbs)
        self.assertFalse([l for l in self.mv_lines() if "deploy-" in l or "old-" in l],
                         "no swap was attempted")
        if at_stop:
            self.assertEqual(verbs, ["ps --status running -q crm-app", STOP])
        else:
            self.assertEqual(verbs, [])

    def test_symlinked_component_planted_before_the_run(self):
        for rel in self.COMPONENTS:
            with self.subTest(component=rel):
                self.fresh()
                subprocess.run(["bash", "-c", self.redirect_cmd(rel)], check=True)
                before = tree_hash(self.sentinel)
                custom_before = tree_hash(self.custom_live)
                res = self.deploy()
                self.assert_refused_before_swap(res, at_stop=False)
                self.assertEqual(tree_hash(self.sentinel), before, "nothing written through the link")
                self.assertEqual(tree_hash(self.custom_live), custom_before)

    def test_symlinked_component_planted_while_the_stack_stops(self):
        for rel in self.COMPONENTS:
            with self.subTest(component=rel):
                self.fresh()
                path = os.path.join(self.runtime, rel)
                before = tree_hash(path)
                custom_before = tree_hash(self.custom_live)
                res = self.deploy(on_stop=self.redirect_cmd(rel))
                self.assertTrue(os.path.islink(path), "the plant happened")
                self.assert_refused_before_swap(res, at_stop=True)
                self.assertEqual(tree_hash(self.sentinel), before, "nothing written through the link")
                self.assertEqual(tree_hash(self.custom_live), custom_before, "custom tree not swapped")

    def test_planted_working_names_are_refused_before_and_while_stopping(self):
        reference = os.path.join(self.tmp.name, "reference")
        os.mkdir(reference)
        with open(os.path.join(reference, "keep.txt"), "w") as fh:
            fh.write("keep\n")
        expected = tree_hash(reference)
        for prefix, where in self.NAMES:
            for at_stop in (False, True):
                with self.subTest(name=prefix, at_stop=at_stop):
                    self.fresh()
                    src_before = tree_hash(self.live_src)
                    custom_before = tree_hash(self.custom_live)
                    if at_stop:
                        res = self.deploy(on_stop=self.plant_cmd(prefix, where))
                    else:
                        subprocess.run(["bash", "-c", self.plant_cmd(prefix, where)], check=True)
                        res = self.deploy()
                    self.assert_refused_before_swap(res, at_stop=at_stop)
                    self.assertEqual(tree_hash(self.sentinel), expected)
                    self.assertEqual((tree_hash(self.live_src), tree_hash(self.custom_live)),
                                     (src_before, custom_before), "live trees untouched")

    def test_group_or_world_writable_client_custom_is_made_private_but_client_must_be_private(self):
        os.chmod(os.path.join(self.runtime, "client"), 0o775)
        before = tree_hash(self.live_src)
        res = self.deploy()
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("group- or world-writable", res.stderr)
        self.assertEqual(tree_hash(self.live_src), before)
        self.assertEqual(tree(self.custom_live)["marker.txt"], b"previous custom tree")
        self.assertFalse([l for l in self.mv_lines() if "deploy-" in l])
        os.chmod(os.path.join(self.runtime, "client"), 0o755)
        # the container re-opens client/custom while the stack stops: the deploy secures it
        res = self.deploy(on_stop=f"chmod 0777 {shlex.quote(self.cc)}")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(os.stat(self.cc).st_mode & 0o022, 0)


class TestDeployClientCacheBust(ClientDeployBase):
    """AC4: up --wait, clear-cache, rebuild, update-app-timestamp, in that order, in crm-app
    as www-data; the appTimestamp must advance strictly."""

    def test_success_path_order_and_strict_advance(self):
        res = self.deploy()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.verbs(), [
            "ps --status running -q crm-app", STOP, UP,
            CMD_PREFIX + CLEAR, CMD_PREFIX + REBUILD, CMD_PREFIX + APPTS])
        self.assertEqual(self.appts(), 1001)
        self.assertIn("appTimestamp advanced: 1000 -> 1001", res.stdout)
        self.assertIn("client cache-bust done", res.stdout)
        self.assertEqual([l for l in self.mv_lines() if l.startswith("SLEEP")], [], "no retry needed")

    def test_value_that_does_not_advance_is_retried_once_after_one_second(self):
        res = self.deploy(FAKE_APPTS="late")
        self.assertEqual(res.returncode, 0, res.stderr)
        calls = [v for v in self.verbs() if v.endswith(APPTS)]
        self.assertEqual(len(calls), 2)
        self.assertEqual([l for l in self.mv_lines() if l.startswith("SLEEP")], ["SLEEP 1"])
        self.assertEqual(self.appts(), 1001)

    def test_value_that_never_advances_fails_the_step(self):
        before = tree(self.live_src)
        res = self.deploy(FAKE_APPTS="stuck")
        self.assertEqual(res.returncode, 46, "recovery also cannot advance it")
        self.assertIn("FAILED STEP: update-app-timestamp (not advanced)", res.stderr)
        self.assertIn("RECOVERY FAILED", res.stderr)
        self.assertNotIn("customisation deployed", res.stdout)
        self.assertEqual(len([v for v in self.verbs() if v.endswith(APPTS)]), 4, "one retry each pass")
        self.assertEqual(before, tree(os.path.join(self.cc, "src")), "previous src restored")

    def test_an_unreadable_timestamp_is_not_success(self):
        res = self.deploy(FAKE_STATE_FILE=os.path.join(self.tmp.name, "elsewhere.php"))
        self.assertEqual(res.returncode, 46, res.stdout + res.stderr)
        self.assertIn("FAILED STEP: update-app-timestamp (not advanced)", res.stderr)

    def test_stopped_stack_prints_that_the_cache_bust_was_skipped(self):
        res = self.deploy(running=False)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("clear-cache/rebuild skipped", res.stdout)
        self.assertIn("client cache-bust (update-app-timestamp) was skipped", res.stdout)
        self.assertIn("re-run this script", res.stdout)
        self.assertEqual(self.verbs(), ["ps --status running -q crm-app", STOP])
        self.assertEqual(tree(self.live_src), tree(REPO_SRC))
        self.assertEqual(self.appts(), 1000)
        self.assertEqual(sorted(os.listdir(self.cc)), ["modules", "other.txt", "res.js", "src"])


class TestDeployClientFailureAndRecovery(ClientDeployBase):
    """AC4b / annex B7: a failure after the swap names the step, restores the previous
    trees byte for byte, keeps the new ones as .failed-<stamp>, and either recovers the
    cache-bust or stops the stack."""

    STEPS = [("up", UP, 21), ("clear-cache", CMD_PREFIX + CLEAR, 22),
             ("rebuild", CMD_PREFIX + REBUILD, 23), ("update-app-timestamp", CMD_PREFIX + APPTS, 24)]
    RECOVERY = [("stop", STOP, 41), ("up", UP, 43), ("clear-cache", CMD_PREFIX + CLEAR, 44),
                ("rebuild", CMD_PREFIX + REBUILD, 45), ("update-app-timestamp", CMD_PREFIX + APPTS, 46)]
    PASS = [UP, CMD_PREFIX + CLEAR, CMD_PREFIX + REBUILD, CMD_PREFIX + APPTS]

    def snapshot(self):
        return {"src": tree(self.live_src), "custom": tree(self.custom_live), "other": self.non_src(),
                "modules": tree_hash(os.path.join(self.cc, "modules"))}

    def assert_no_success(self, res):
        self.assertNotIn("customisation deployed", res.stdout)
        self.assertNotIn("cache-bust done", res.stdout)

    def failed_dirs(self):
        return (os.path.join(self.cc, f".src.failed-{self.STAMP}"),
                os.path.join(self.runtime, "custom", "Espo", f".Custom.failed-{self.STAMP}"))

    def test_failure_at_each_post_swap_step_recovers(self):
        for step, suffix, code in self.STEPS:
            with self.subTest(step=step):
                self.tearDown()
                self.setUp()
                before = self.snapshot()
                res = self.deploy(FAKE_DOCKER_FAIL=f"{suffix}@1")
                self.assertEqual(res.returncode, code, res.stdout + res.stderr)
                self.assertIn(f"FAILED STEP: {step}", res.stderr)
                self.assertIn("RECOVERED: previous customisation restored", res.stderr)
                self.assertNotIn("RECOVERY FAILED", res.stderr)
                self.assert_no_success(res)
                self.assertEqual(self.snapshot(), before, "previous trees restored byte for byte")
                src_failed, custom_failed = self.failed_dirs()
                self.assertEqual(tree(src_failed), tree(REPO_SRC), "the failed new tree is retained")
                self.assertEqual(tree(custom_failed), tree(REPO_CUSTOM))
                self.assertEqual(sorted(os.listdir(self.cc)),
                                 sorted(["modules", "other.txt", "res.js", "src", f".src.failed-{self.STAMP}"]))
                index = [s for s, _, _ in self.STEPS].index(step)
                done = self.PASS[:index + 1]
                self.assertEqual(self.verbs(), ["ps --status running -q crm-app", STOP, *done,
                                                STOP, *self.PASS], "recovery re-runs the cache-bust")
                self.assertEqual(self.appts(), 1001 if step != "update-app-timestamp" else 1001)

    def test_failure_at_each_recovery_step_stops_the_stack(self):
        for step, suffix, code in self.RECOVERY:
            with self.subTest(step=step):
                self.tearDown()
                self.setUp()
                before = self.snapshot()
                nth = 2  # the recovery's call is the second one (the deploy's failed first)
                res = self.deploy(FAKE_DOCKER_FAIL=f"{CMD_PREFIX + APPTS}@1;{suffix}@{nth}")
                self.assertEqual(res.returncode, code, res.stdout + res.stderr)
                self.assertIn("FAILED STEP: update-app-timestamp", res.stderr)
                self.assertIn(f"RECOVERY FAILED: stack left stopped (step: {step})", res.stderr)
                self.assertNotIn("RECOVERED", res.stderr)
                self.assert_no_success(res)
                self.assertEqual(self.verbs()[-1], STOP, "controlled stop of crm-app and crm-daemon")
                src_failed, custom_failed = self.failed_dirs()
                if step == "stop":  # nothing restored yet: new trees live, previous ones retained
                    old_src = os.path.join(self.cc, f".src.old-{self.STAMP}")
                    self.assertEqual(tree(old_src), before["src"])
                    self.assertEqual(tree(self.live_src), tree(REPO_SRC))
                else:
                    self.assertEqual(self.snapshot(), before)
                    self.assertEqual(tree(src_failed), tree(REPO_SRC))

    def test_failure_to_restore_the_trees_retains_both(self):
        before = self.snapshot()
        res = self.deploy(FAKE_DOCKER_FAIL=f"{CMD_PREFIX + REBUILD}@1", FAKE_MV_FAIL=".failed-")
        self.assertEqual(res.returncode, 42, res.stdout + res.stderr)
        self.assertIn("FAILED STEP: rebuild", res.stderr)
        self.assertIn("RECOVERY FAILED: stack left stopped (step: restore-trees)", res.stderr)
        self.assertEqual(tree(self.live_src), tree(REPO_SRC), "the new tree is still live, not lost")
        self.assertEqual(tree(os.path.join(self.cc, f".src.old-{self.STAMP}")), before["src"])
        self.assertEqual(tree(os.path.join(self.runtime, "custom", "Espo", f".Custom.old-{self.STAMP}")),
                         before["custom"])
        self.assertEqual(self.verbs()[-1], STOP)
        self.assertEqual(self.non_src(), before["other"])

    def test_second_swap_failure_swaps_the_first_back(self):
        before = self.snapshot()
        res = self.deploy(FAKE_MV_FAIL=f".src.deploy-{self.STAMP}")
        self.assertEqual(res.returncode, 20, res.stdout + res.stderr)
        self.assertIn("FAILED STEP: swap", res.stderr)
        self.assert_no_success(res)
        self.assertEqual(self.snapshot(), before, "previous trees in place")
        self.assertEqual(tree(self.failed_dirs()[1]), tree(REPO_CUSTOM))
        self.assertEqual(self.verbs(), ["ps --status running -q crm-app", STOP], "stack left stopped")
        self.assertFalse(os.path.exists(os.path.join(self.cc, f".src.deploy-{self.STAMP}")),
                         "the staging tree is removed")

    def test_modules_are_identical_through_success_failure_and_failed_recovery(self):
        modules = tree_hash(os.path.join(self.cc, "modules"))
        other = self.non_src()
        cases = [{}, {"FAKE_DOCKER_FAIL": f"{CMD_PREFIX + REBUILD}@1"},
                 {"FAKE_DOCKER_FAIL": f"{CMD_PREFIX + REBUILD}@1;{UP}@2"},
                 {"FAKE_DOCKER_FAIL": f"{CMD_PREFIX + REBUILD}@1", "FAKE_MV_FAIL": ".failed-"}]
        for env in cases:
            with self.subTest(env=env):
                self.tearDown()
                self.setUp()
                self.deploy(**env)
                self.assertEqual(tree_hash(os.path.join(self.cc, "modules")), modules)
                self.assertEqual(self.non_src(), other)


class TestClientBackupRestoreRollback(ClientDeployBase):
    """AC5: backup of A, deploy of B, restore gives A back byte for byte; redeploying A
    over B removes B-only files; the deploy ends with a cache-bust."""

    def test_backup_deploy_restore_and_rollback(self):
        a = self.deploy()
        self.assertEqual(a.returncode, 0, a.stderr)
        tree_a = tree(self.live_src)
        res = self.run_script("backup.sh", "dev")
        self.assertEqual(res.returncode, 0, res.stderr)
        (name,) = os.listdir(os.path.join(self.runtime, "backups"))
        repo_b = self.repo_copy()
        only_b = os.path.join(repo_b, "client", "custom", "src", "crm", "only-in-b.js")
        with open(only_b, "w") as fh:
            fh.write("define([], function () { return 'b'; });\n")
        b = self.deploy(repo_b, MV_LOG=self.mvlog)
        self.assertEqual(b.returncode, 0, b.stderr)
        self.assertIn("crm/only-in-b.js", tree(self.live_src))
        self.assertNotEqual(tree(self.live_src), tree_a)
        res = self.run_script("restore.sh", "dev", name)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(tree(self.live_src), tree_a, "restore gives A back byte for byte")
        self.assertNotIn("crm/only-in-b.js", tree(self.live_src))
        # rollback: B again, then A over B through the deploy
        self.deploy(repo_b)
        self.assertIn("crm/only-in-b.js", tree(self.live_src))
        ts_before = self.appts()
        open(self.log, "w").close()
        res = self.deploy()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(tree(self.live_src), tree_a, "redeploying A removes the files only B had")
        self.assertEqual(self.verbs()[-1], CMD_PREFIX + APPTS, "followed by a cache-bust")
        self.assertGreater(self.appts(), ts_before)

    def test_restore_is_followed_by_the_documented_cache_bust(self):
        with open(os.path.join(REPO, "docs", "RELEASE.md")) as fh:
            doc = fh.read()
        self.assertRegex(doc, r"```sh\n[^`]*restore\.sh dev [^`]*bin/command update-app-timestamp[^`]*```")



class TestDeploySwapFailureLeftoversAndSignals(ClientDeployBase):
    """AC4c (R5): a swap failure puts both trees back and leaves no staging; leftovers of
    earlier runs are listed and never used; INT, TERM and HUP are handled with the real
    signal, before and after the first swap."""

    SIGNALS = ("INT", "TERM", "HUP")
    LEFTOVER_NAMES = (".Custom.deploy-", ".Custom.old-", ".Custom.failed-",
                      ".src.deploy-", ".src.old-", ".src.failed-")

    def snapshot(self):
        return {"src": tree(self.live_src), "custom": tree(self.custom_live), "other": self.non_src(),
                "modules": tree_hash(os.path.join(self.cc, "modules"))}

    def working_names(self):
        espo = os.path.join(self.runtime, "custom", "Espo")
        return sorted(n for d in (espo, self.cc) for n in os.listdir(d) if n.startswith((".Custom.", ".src.")))

    def reset(self):
        self.tearDown()
        self.setUp()

    def test_swap_failure_at_each_point_restores_both_trees_and_removes_staging(self):
        points = [("custom: moving the live tree aside", f".Custom.old-{self.STAMP}"),
                  ("custom: installing staging", f".Custom.deploy-{self.STAMP}"),
                  ("src: moving the live tree aside", f".src.old-{self.STAMP}"),
                  ("src: installing staging", f".src.deploy-{self.STAMP}")]
        for label, pattern in points:
            with self.subTest(point=label):
                self.reset()
                before = self.snapshot()
                res = self.deploy(FAKE_MV_FAIL_ONCE=pattern)
                self.assertEqual(res.returncode, 20, res.stdout + res.stderr)
                self.assertIn("FAILED STEP: swap", res.stderr)
                self.assertNotIn("customisation deployed", res.stdout)
                self.assertEqual(self.snapshot(), before, "previous trees live and byte-identical")
                self.assertFalse([n for n in self.working_names() if ".deploy-" in n],
                                 "no staging directory remains for either tree")
                self.assertEqual(self.verbs(), ["ps --status running -q crm-app", STOP], "stack left stopped")

    def test_swap_failure_keeps_going_when_the_restore_also_fails_but_removes_staging(self):
        res = self.deploy(FAKE_MV_FAIL=f".src.deploy-{self.STAMP}")
        self.assertEqual(res.returncode, 20)
        self.assertFalse([n for n in self.working_names() if ".deploy-" in n])

    def test_leftovers_are_listed_never_used_and_never_touched(self):
        old = "20250101T000000Z"
        planted = {}
        for name in self.LEFTOVER_NAMES:
            base = os.path.join(self.runtime, "custom", "Espo") if name.startswith(".Custom") else self.cc
            self.write(os.path.relpath(os.path.join(base, name + old, "marker.txt"), self.runtime),
                       f"leftover {name}\n")
            planted[name + old] = tree_hash(os.path.join(base, name + old))
        before_other = self.non_src()
        res = self.deploy()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(tree(self.live_src), tree(REPO_SRC), "exactly the repository tree is live")
        self.assertEqual(tree(self.custom_live), tree(REPO_CUSTOM))
        for name, digest in planted.items():
            self.assertIn(f"LEFTOVER: {name}\n", res.stderr)
            base = os.path.join(self.runtime, "custom", "Espo") if name.startswith(".Custom") else self.cc
            self.assertEqual(tree_hash(os.path.join(base, name)), digest, f"{name} neither moved nor changed")
        self.assertEqual(res.stderr.count("LEFTOVER:"), len(planted), "every leftover, and only those")
        self.assertEqual({k: v for k, v in self.non_src().items() if not k.startswith(".src.")},
                         {k: v for k, v in before_other.items() if not k.startswith(".src.")})

    def test_a_clean_runtime_lists_no_leftover(self):
        res = self.deploy()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("LEFTOVER", res.stderr)

    def test_signal_during_a_post_swap_step_recovers(self):
        for sig in self.SIGNALS:
            for step, suffix in (("up", UP), ("clear-cache", CMD_PREFIX + CLEAR),
                                 ("rebuild", CMD_PREFIX + REBUILD), ("update-app-timestamp", CMD_PREFIX + APPTS)):
                with self.subTest(signal=sig, step=step):
                    self.reset()
                    before = self.snapshot()
                    res = self.deploy(FAKE_DOCKER_SIGNAL=f"{suffix}@1:{sig}")
                    self.assertEqual(res.returncode, 47, res.stdout + res.stderr)
                    self.assertIn(f"INTERRUPTED: {sig}", res.stderr)
                    self.assertIn("RECOVERED: previous customisation restored", res.stderr)
                    self.assertNotIn("RECOVERY FAILED", res.stderr)
                    self.assertNotIn("customisation deployed", res.stdout)
                    self.assertEqual(self.snapshot(), before, "previous trees restored byte for byte")
                    self.assertEqual(tree(os.path.join(self.cc, f".src.failed-{self.STAMP}")), tree(REPO_SRC))
                    self.assertFalse([n for n in self.working_names() if ".deploy-" in n])
                    self.assertEqual(self.verbs()[-5:], [STOP, *TestDeployClientFailureAndRecovery.PASS],
                                     "recovery stops, then re-runs the cache-bust")
                    self.assertGreater(self.appts(), 1000)

    def test_signal_during_each_swap_move_recovers(self):
        moves = [f".Custom.old-{self.STAMP}", f".Custom.deploy-{self.STAMP}",
                 f".src.old-{self.STAMP}", f".src.deploy-{self.STAMP}"]
        for sig in self.SIGNALS:
            for pattern in moves:
                with self.subTest(signal=sig, move=pattern):
                    self.reset()
                    before = self.snapshot()
                    res = self.deploy(FAKE_MV_SIGNAL=f"{pattern}:{sig}")
                    self.assertEqual(res.returncode, 47, res.stdout + res.stderr)
                    self.assertIn(f"INTERRUPTED: {sig}", res.stderr)
                    self.assertIn("RECOVERED", res.stderr)
                    self.assertEqual(self.snapshot(), before, "previous trees restored byte for byte")
                    self.assertFalse([n for n in self.working_names() if ".deploy-" in n])
                    self.assertEqual(self.verbs()[-5:], [STOP, *TestDeployClientFailureAndRecovery.PASS])

    def test_signal_before_the_first_swap_removes_staging_and_leaves_the_stack_stopped(self):
        for sig in self.SIGNALS:
            with self.subTest(signal=sig, where="after staging"):
                self.reset()
                before = self.snapshot()
                res = self.deploy(FAKE_CP_SIGNAL=f".src.deploy-{self.STAMP}:{sig}")
                self.assertEqual(res.returncode, 48, res.stdout + res.stderr)
                self.assertIn(f"INTERRUPTED: {sig}", res.stderr)
                self.assertNotIn("customisation deployed", res.stdout)
                self.assertEqual(self.snapshot(), before, "previous trees untouched")
                self.assertEqual(self.working_names(), [], "staging removed for both trees")
                self.assertEqual(self.verbs(), ["ps --status running -q crm-app", STOP])
            with self.subTest(signal=sig, where="during the stop"):
                self.reset()
                before = self.snapshot()
                res = self.deploy(FAKE_DOCKER_SIGNAL=f"{STOP}@1:{sig}")
                self.assertEqual(res.returncode, 48, res.stdout + res.stderr)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.working_names(), [])
                self.assertEqual(self.verbs(), ["ps --status running -q crm-app", STOP])

    def test_signal_with_the_stack_stopped_restores_and_leaves_it_stopped(self):
        before = self.snapshot()
        res = self.deploy(running=False, FAKE_MV_SIGNAL=f".src.deploy-{self.STAMP}:TERM")
        self.assertEqual(res.returncode, 47, res.stdout + res.stderr)
        self.assertIn("INTERRUPTED: TERM", res.stderr)
        self.assertIn("RECOVERED", res.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.verbs(), ["ps --status running -q crm-app", STOP, STOP], "never started")

    def test_signal_then_failed_recovery_stops_the_stack_and_retains_the_trees(self):
        before = self.snapshot()
        res = self.deploy(FAKE_DOCKER_SIGNAL=f"{CMD_PREFIX + REBUILD}@1:INT",
                          FAKE_DOCKER_FAIL=f"{UP}@2")
        self.assertEqual(res.returncode, 43, res.stdout + res.stderr)
        self.assertIn("INTERRUPTED: INT", res.stderr)
        self.assertIn("RECOVERY FAILED: stack left stopped (step: up)", res.stderr)
        self.assertNotIn("customisation deployed", res.stdout)
        self.assertEqual(self.verbs()[-1], STOP)
        self.assertEqual(self.snapshot(), before, "the previous trees are back even though the start failed")
        self.assertEqual(tree(os.path.join(self.cc, f".src.failed-{self.STAMP}")), tree(REPO_SRC))

    def test_a_successful_deploy_leaves_no_working_tree_and_no_interruption(self):
        res = self.deploy()
        self.assertEqual(res.returncode, 0)
        self.assertNotIn("INTERRUPTED", res.stderr)
        self.assertEqual(self.working_names(), [])


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
        with tempfile.TemporaryDirectory() as base:
            runtime = os.path.join(base, "dev")
            os.makedirs(os.path.join(runtime, "backups"))
            with open(os.path.join(runtime, "env"), "w") as fh:
                fh.write(f"CRM_BIND_IP={ACCESS['CRM_BIND_IP']}\n")
            out = os.path.join(runtime, "backups", "export-x")
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                code = export_csv.main(
                    ["dev", "--base-url", f"http://{ACCESS['CRM_BIND_IP']}:8180", "--out", out],
                    transport=FakeListTransport({}), environ={"CRM_RUNTIME_DIR": runtime})
            self.assertEqual(code, 2)
            self.assertIn("CRM_ADMIN_PASSWORD", err.getvalue())



class TestExecutableModes(unittest.TestCase):
    """CRM-008 change 9: the documented direct invocations need the executable bit,
    which Git records (mode 100755) from the working tree."""

    FILES = ("scripts/load.sh", "scripts/provision_access.py", "scripts/provision_users.py",
             "scripts/check_access.py", "scripts/crm_api.py", "load/bin/crm-load.py")

    def test_files_are_executable(self):
        for rel in self.FILES:
            with self.subTest(file=rel):
                mode = os.stat(os.path.join(REPO, rel)).st_mode
                self.assertEqual(mode & 0o111, 0o111, f"{rel} is not executable")

    def test_git_index_mode_when_committed(self):
        """In a checkout whose index is in sync, Git must also say 100755."""
        if not shutil.which("git"):
            self.skipTest("git not installed")
        res = subprocess.run(["git", "-C", REPO, "ls-files", "-s", "--", *self.FILES],
                             capture_output=True, text=True)
        dirty = subprocess.run(["git", "-C", REPO, "diff", "--quiet", "--", *self.FILES])
        if res.returncode != 0 or dirty.returncode != 0:
            self.skipTest("no Git metadata, or the mode change is not yet committed")
        modes = {line.split("\t")[1]: line.split()[0] for line in res.stdout.splitlines()}
        self.assertEqual(modes, {f: "100755" for f in self.FILES})


if __name__ == "__main__":
    unittest.main()
