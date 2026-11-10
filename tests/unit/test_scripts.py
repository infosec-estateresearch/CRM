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

import crm_api  # noqa: E402
import export_csv  # noqa: E402

GUARDED = ["backup.sh", "restore.sh", "export.sh", "deploy_custom.sh"]
REPO_CUSTOM = os.path.join(REPO, "custom", "Espo", "Custom")

FAKE_DOCKER = """#!/usr/bin/env bash
# Records its arguments; plays mariadb-dump / mariadb inside "crm-db".
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
case "$*" in
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
        values = {"CRM_DATA_DIR": f"{runtime}/data",
                  "CRM_CUSTOM_DIR": f"{runtime}/custom",
                  "CRM_CLIENT_CUSTOM_DIR": f"{runtime}/client/custom"}
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

    def run_script(self, name, *args, runtime=None, extra_env=None, umask=None):
        env = {
            "PATH": self.bin + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
            "CRM_RUNTIME_DIR": runtime or self.runtime,
            "FAKE_DOCKER_LOG": self.log,
            "FAKE_DOCKER_STDIN": self.stdin,
            "HOME": self.tmp.name,
            "REAL_DATE": REAL_DATE,
        }
        env.update(extra_env or {})
        preexec = (lambda: os.umask(umask)) if umask is not None else None
        return subprocess.run(["bash", os.path.join(SCRIPTS, name), *args],
                              capture_output=True, text=True, env=env, timeout=60,
                              preexec_fn=preexec)

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
                         ["SHA256SUMS", "client-custom.tar.gz", "custom.tar.gz",
                          "data.tar.gz", "db.sql.gz"])
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
            self.assertEqual(len(fh.read().splitlines()), 4)
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
        verbs = [c.split(" --env-file ")[1].split(" ", 1)[1] for c in self.docker_calls()]
        self.assertEqual(verbs, ["ps --status running -q crm-app", "stop crm-daemon crm-app"])

    def test_running_app_gets_clear_cache_then_rebuild(self):
        res = self.deploy(extra_env={"FAKE_DOCKER_RUNNING": "1"})
        self.assertIn("clear-cache and rebuild completed", res.stdout)
        verbs = [c.split(" --env-file ")[1].split(" ", 1)[1] for c in self.docker_calls()]
        self.assertEqual(verbs, [
            "ps --status running -q crm-app",
            "stop crm-daemon crm-app",
            "up -d --wait crm-app crm-daemon",
            "exec -T -u www-data -w /var/www/html crm-app php bin/command clear-cache",
            "exec -T -u www-data -w /var/www/html crm-app php bin/command rebuild",
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
        verbs = [c.split(" --env-file ")[1].split(" ", 1)[1] for c in self.docker_calls()]
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

    SCRIPTS = [("deploy_custom.sh",), ("backup.sh",), ("restore.sh", "crm-dev-20261110T120000Z")]
    VARS = {"CRM_DATA_DIR": "data", "CRM_CUSTOM_DIR": "custom", "CRM_CLIENT_CUSTOM_DIR": "client/custom"}

    def assert_all_refuse(self, needle):
        listing = sorted(os.listdir(self.runtime))
        live = tree_hash(os.path.join(self.runtime, "custom"))
        for args in self.SCRIPTS:
            with self.subTest(script=args[0]):
                res = self.run_script(args[0], "dev", *args[1:])
                self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                self.assertIn(needle, res.stderr)
                self.assertEqual(self.docker_calls(), [])
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
