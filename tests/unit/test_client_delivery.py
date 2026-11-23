"""CRM-WIP-LINK-001: the browser-asset delivery of scripts/deploy_custom.sh
(runtime client/custom/src). A fake `docker`, a copy of the repository's scripts
in a temporary directory and a temporary runtime: no Docker, no network. Each
rule is proved non-vacuous by removing it from a copy of the script (the
`TestEveryRuleIsNonVacuous` class)."""

import contextlib
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
import test_scripts as ts  # noqa: E402  (its test classes stay in that module)

STAMP = "20261118T120000Z"
CLIENT_SRC_REL = os.path.join("client", "custom", "src")
MARKER = ".src-managed-by-git"

FAKE_DOCKER = ts.FAKE_DOCKER.replace(
    'case "$*" in\n',
    '''once() { [ -n "${FAKE_FAIL_ALWAYS:-}" ] || [ ! -e "$FAKE_DOCKER_LOG.$1" ]; }
if [ -n "${FAKE_FAIL:-}" ] && [[ "$*" == *"$FAKE_FAIL"* ]] && once failed; then
    touch "$FAKE_DOCKER_LOG.failed"; echo "fake docker: failing $FAKE_FAIL" >&2; exit 1
fi
if [ -n "${FAKE_HOOK_MATCH:-}" ] && [[ "$*" == *"$FAKE_HOOK_MATCH"* ]]; then bash -c "$FAKE_HOOK_CMD"; fi
if [ -n "${FAKE_KILL:-}" ] && [[ "$*" == *"$FAKE_KILL"* ]] && [ ! -e "$FAKE_DOCKER_LOG.killed" ]; then
    touch "$FAKE_DOCKER_LOG.killed"; kill -TERM "$PPID"; exit 0
fi
case "$*" in
''', 1)
assert "FAKE_KILL" in FAKE_DOCKER

# A shim that fails when its arguments contain $<VAR>, otherwise runs the real tool.
SHIM = """#!/usr/bin/env bash
if [ -n "${%(var)s:-}" ] && [[ "$*" == *"$%(var)s"* ]]; then echo "fake %(tool)s failure" >&2; exit 1; fi
exec %(real)s "$@"
"""


def snapshot(path):
    """Bytes and modes of everything under path (a file, a link, a directory or absent)."""
    if not os.path.lexists(path):
        return None
    if os.path.islink(path):
        return ("link", os.readlink(path))
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            return ("file", fh.read())
    return ("dir", ts.tree_hash(path))


class Delivery(ts.ScriptEnv):
    mutator = None

    def fresh(self):
        """A new temporary runtime and repository (a mutation, if any, is kept)."""
        self.tearDown()
        self.setUp()

    def setUp(self):
        super().setUp()
        base = self.tmp.name
        self.repo = os.path.join(base, "repo")
        os.mkdir(self.repo)
        for name in ("scripts", "deploy", "custom", "config", "security", "client"):
            if os.path.isdir(os.path.join(ts.REPO, name)):
                shutil.copytree(os.path.join(ts.REPO, name), os.path.join(self.repo, name),
                                ignore=shutil.ignore_patterns("__pycache__"))
        self.script = os.path.join(self.repo, "scripts", "deploy_custom.sh")
        self.rsrc = os.path.join(self.repo, CLIENT_SRC_REL)
        self.client = os.path.join(self.runtime, "client")
        self.cc = os.path.join(self.client, "custom")
        self.src = os.path.join(self.cc, "src")
        self.live = os.path.join(self.runtime, "custom", "Espo", "Custom")
        self.repo_custom = os.path.join(self.repo, "custom", "Espo", "Custom")
        with open(os.path.join(self.bin, "docker"), "w") as fh:
            fh.write(FAKE_DOCKER)
        if self.mutator is not None:  # the mutation sweep: a copy of the script without one rule
            with open(self.script) as fh:
                mutated = self.mutator(fh.read())
            with open(self.script, "w") as fh:
                fh.write(mutated)
        self.shim("cp", "FAKE_CP_FAIL")
        self.shim("mv", "FAKE_MV_FAIL")
        self.shim("rm", "FAKE_RM_FAIL")
        # entries of client/custom the delivery must never touch
        self.write("client/custom/modules/Canary/canary.js", "// canary\n")
        self.write("client/custom/unmanaged.txt", "keep\n")
        self.sentinel = os.path.join(base, "sentinel")

    def sub(self, **labels):
        """A labelled case inside a scenario. Failures raise (not recorded), so the
        mutation sweep can see them."""
        return contextlib.nullcontext()

    def shim(self, tool, var):
        path = os.path.join(self.bin, tool)
        with open(path, "w") as fh:
            fh.write(SHIM % {"var": var, "tool": tool, "real": shutil.which(tool)})
        os.chmod(path, stat.S_IRWXU)

    # ---- running ----
    def deploy(self, running=True, **env):
        e = {"FAKE_DATE_STAMP": STAMP, **env}
        if running:
            e["FAKE_DOCKER_RUNNING"] = "1"
        full = {
            "PATH": self.bin + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
            "CRM_RUNTIME_DIR": self.runtime, "FAKE_DOCKER_LOG": self.log,
            "FAKE_DOCKER_STDIN": self.stdin, "HOME": self.tmp.name, "REAL_DATE": ts.REAL_DATE,
            "FAKE_COMPOSE_CONFIG": self.compose_config, **e,
        }
        open(self.log, "w").close()
        for suffix in (".failed", ".killed"):
            if os.path.exists(self.log + suffix):
                os.remove(self.log + suffix)
        return subprocess.run(["bash", self.script, "dev"], capture_output=True, text=True,
                              env=full, timeout=120)

    def ok(self, **kw):
        res = self.deploy(**kw)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        return res

    # ---- state ----
    def others(self):
        """Every entry of client/custom except src and the marker."""
        return {n: snapshot(os.path.join(self.cc, n)) for n in os.listdir(self.cc)
                if n not in ("src", MARKER) and not n.startswith(".src.failed-")}

    def state(self):
        return {"custom": snapshot(self.live), "src": snapshot(self.src),
                "marker": os.path.lexists(os.path.join(self.cc, MARKER)), "others": self.others()}

    def names(self):
        return sorted(os.listdir(self.cc))

    def write_repo(self, rel, text):
        path = os.path.join(self.rsrc, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)

    def tree_equal(self, a, b):
        self.assertEqual(ts.tree(a), ts.tree(b))

    def stderr_has(self, res, *needles):
        for n in needles:
            self.assertIn(n, res.stderr, res.stdout + res.stderr)

    # ================= scenarios (used by the tests and by the mutation sweep) =================
    def sc_first_install(self):
        before = self.others()
        res = self.ok()
        self.tree_equal(self.src, self.rsrc)
        self.assertTrue(os.path.isfile(os.path.join(self.cc, MARKER)))
        self.assertEqual(self.others(), before, "modules/ and the other entries are untouched")
        self.assertEqual(self.names(), sorted([MARKER, "modules", "res.js", "src", "unmanaged.txt"]))
        verbs = self.verbs()
        update = "exec -T -u www-data -w /var/www/html crm-app php bin/command update-app-timestamp"
        self.assertIn(update, verbs)
        self.assertLess(verbs.index("exec -T -u www-data -w /var/www/html crm-app php bin/command rebuild"),
                        verbs.index(update))
        self.assertIn("application timestamp advanced", res.stdout)

    def sc_not_running(self):
        res = self.ok(running=False)
        self.tree_equal(self.src, self.rsrc)
        self.assertEqual(self.verbs(), ["ps --status running -q crm-app", "stop crm-daemon crm-app"])
        self.assertIn("timestamp was not advanced", res.stdout)

    def sc_update(self):
        self.ok()
        self.write_repo("handlers/account-open-wip.js", "// changed\n")
        self.write_repo("handlers/new.js", "// new\n")
        os.remove(os.path.join(self.rsrc, "handlers", "new.js"))
        self.write_repo("extra/added.js", "// added\n")
        self.write_repo("extra/kept.js", "// kept\n")
        self.ok()
        self.tree_equal(self.src, self.rsrc)
        os.remove(os.path.join(self.rsrc, "extra", "kept.js"))
        hook = f"ls -A {shlex.quote(self.cc)} {shlex.quote(os.path.dirname(self.live))} > {shlex.quote(self.sentinel)}"
        self.ok(FAKE_HOOK_MATCH="update-app-timestamp", FAKE_HOOK_CMD=hook)
        self.tree_equal(self.src, self.rsrc)
        self.assertFalse(os.path.exists(os.path.join(self.src, "extra", "kept.js")), "removed file is gone")
        with open(self.sentinel) as fh:
            during = fh.read().split()
        self.assertIn(f".src.old-{STAMP}", during, "previous src kept until the last step")
        self.assertIn(f".Custom.old-{STAMP}", during, "previous custom tree kept until the last step")
        self.assertNotIn(f".src.old-{STAMP}", self.names())
        self.assertFalse(os.path.exists(os.path.join(self.live, "..", f".Custom.old-{STAMP}")))

    def sc_timestamp_not_advancing(self):
        self.ok()
        self.write_repo("handlers/account-open-wip.js", "// v2\n")
        before = self.state()
        res = self.deploy(FAKE_TS_STATIC="1")
        self.assertEqual(res.returncode, 27, res.stdout + res.stderr)
        self.stderr_has(res, "FAILED STEP: update-app-timestamp", "did not advance", "RECOVERED")
        self.assertEqual(self.state(), before)

    def failure_case(self, code, step, env, running=True, failed_names=("client", "custom"), recovered=True,
                     pre=None):
        self.ok()
        self.write_repo("handlers/account-open-wip.js", "// v2 (to be rolled back)\n")
        with open(os.path.join(self.repo_custom, "Resources", "marker-v2.json"), "w") as fh:
            fh.write("{}\n")
        if pre:
            pre()
        before = self.state()
        res = self.deploy(running=running, **env)
        self.assertEqual(res.returncode, code, res.stdout + res.stderr)
        self.stderr_has(res, f"FAILED STEP: {step}")
        self.assertEqual(self.state(), before, "both trees are back as they were")
        left = [n for n in os.listdir(self.cc) if ".deploy-" in n or ".old-" in n]
        self.assertEqual(left, [], "no staging or old tree left")
        parent = os.path.dirname(self.live)
        self.assertEqual([n for n in os.listdir(parent) if ".deploy-" in n or ".old-" in n], [])
        if "client" in failed_names:
            self.assertTrue(os.path.isfile(os.path.join(self.cc, f".src.failed-{STAMP}", "handlers",
                                                        "account-open-wip.js")), "new client tree kept")
        else:
            self.assertFalse(os.path.lexists(os.path.join(self.cc, f".src.failed-{STAMP}")))
        if "custom" in failed_names:
            self.assertTrue(os.path.isfile(os.path.join(parent, f".Custom.failed-{STAMP}", "Resources",
                                                        "marker-v2.json")), "new custom tree kept")
        else:
            self.assertFalse(os.path.lexists(os.path.join(parent, f".Custom.failed-{STAMP}")))
        self.stderr_has(res, "RECOVERED" if recovered else "RECOVERY FAILED")
        return res

    def sc_post_swap_failures(self):
        for code, step, pattern in ((24, "up", "up -d --wait"), (25, "clear-cache", "clear-cache"),
                                    (26, "rebuild", "bin/command rebuild"),
                                    (27, "update-app-timestamp", "bin/command update-app-timestamp")):
            with self.sub(step=step):
                self.fresh()
                res = self.failure_case(code, step, {"FAKE_FAIL": pattern})
                # the stack was started again and the cache steps re-ran
                self.assertGreaterEqual(self.verbs().count("up -d --wait crm-app crm-daemon"), 2, res.stderr)

    def sc_recovery_failed(self):
        res = self.failure_case(26, "rebuild", {"FAKE_FAIL": "bin/command rebuild", "FAKE_FAIL_ALWAYS": "1"},
                                recovered=False)
        self.assertNotIn("RECOVERED", res.stderr)

    def sc_swap_failures(self):
        with self.sub(step="swap-custom"):
            self.failure_case(22, "swap-custom", {"FAKE_MV_FAIL": ".Custom.deploy-"}, failed_names=())
        with self.sub(step="swap-client"):
            self.fresh()
            self.failure_case(23, "swap-client", {"FAKE_MV_FAIL": ".src.deploy-"}, failed_names=("custom",))

    def sc_swap_failure_stack_stopped(self):
        self.failure_case(22, "swap-custom", {"FAKE_MV_FAIL": ".Custom.deploy-"}, running=False, failed_names=())
        self.assertNotIn("up -d --wait crm-app crm-daemon", self.verbs())

    def sc_stage_failures(self):
        with self.sub(step="stage-custom"):
            self.failure_case(20, "stage-custom", {"FAKE_CP_FAIL": ".Custom.deploy-"}, failed_names=())
        with self.sub(step="stage-client"):
            self.fresh()
            self.failure_case(21, "stage-client", {"FAKE_CP_FAIL": ".src.deploy-"}, failed_names=())

    def sc_interrupted(self):
        self.failure_case(29, "interrupted", {"FAKE_KILL": "bin/command clear-cache"})

    def sc_marker_failure(self):
        self.failure_case(28, "marker", {"FAKE_RM_FAIL": MARKER}, pre=lambda: shutil.rmtree(self.rsrc),
                          failed_names=("custom",))

    def sc_managed_removal(self):
        self.ok()
        shutil.rmtree(self.rsrc)
        before = self.others()
        res = self.ok()
        self.assertFalse(os.path.lexists(self.src))
        self.assertFalse(os.path.lexists(os.path.join(self.cc, MARKER)))
        self.assertEqual(self.others(), before)
        self.assertEqual(self.names(), ["modules", "res.js", "unmanaged.txt"])
        self.assertIn("update-app-timestamp", " ".join(self.verbs()))
        self.assertIn("client assets removed", res.stdout)

    def sc_removal_failure_restores(self):
        self.ok()
        shutil.rmtree(self.rsrc)
        before = self.state()
        res = self.deploy(FAKE_FAIL="bin/command rebuild")
        self.assertEqual(res.returncode, 26, res.stdout + res.stderr)
        self.assertEqual(self.state(), before)
        self.assertTrue(os.path.isfile(os.path.join(self.src, "handlers", "account-open-wip.js")))

    def sc_unmanaged_untouched(self):
        shutil.rmtree(self.rsrc)
        os.makedirs(os.path.join(self.src, "mine"))
        self.write("client/custom/src/mine/hand-made.js", "// hand made\n")
        before = self.state()
        res = self.ok()
        self.assertEqual(self.state()["src"], before["src"], "unmanaged src is left untouched")
        self.assertEqual(self.state()["others"], before["others"])
        self.assertFalse(os.path.lexists(os.path.join(self.cc, MARKER)))
        self.assertIn("left untouched", res.stdout)
        self.tree_equal(self.live, self.repo_custom)  # custom/Espo/Custom is still deployed

    def sc_leftovers(self):
        parent = os.path.dirname(self.live)
        planted = [os.path.join(self.cc, n) for n in (".src.old-20250101T000000Z", ".src.deploy-20250101T000000Z",
                                                      ".src.failed-20250101T000000Z")]
        planted += [os.path.join(parent, n) for n in (".Custom.old-20250101T000000Z", ".Custom.failed-20250101T000000Z")]
        for p in planted:
            os.makedirs(p)
            with open(os.path.join(p, "x.js"), "w") as fh:
                fh.write(p)
        before = {p: snapshot(p) for p in planted}
        res = self.ok()
        for p in planted:
            self.assertIn(f"LEFTOVER: {os.path.basename(p)}", res.stderr)
            self.assertEqual(snapshot(p), before[p], "never touched")
        self.assertNotIn("LEFTOVER: modules", res.stderr)
        self.assertNotIn("LEFTOVER: unmanaged.txt", res.stderr)

    def sc_modules_never_touched(self):
        os.chmod(self.cc, 0o777)  # as the container leaves it
        before = self.others()
        self.ok(FAKE_DOCKER_ON_STOP=f"chmod 0777 {shlex.quote(self.cc)}")
        self.assertEqual(self.others(), before)
        self.assertEqual(os.stat(self.cc).st_mode & 0o022, 0, "client/custom secured")
        self.assertEqual(os.stat(self.cc).st_uid, os.getuid())

    # ---- path safety scenarios ----
    def refused(self, res, before=None, verbs=None):
        self.assertNotEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertRegex(res.stderr, r"refusing to deploy|refusing to run|resolves to|not canonical")
        self.assertEqual(snapshot(self.live), self.live_before, "live custom tree untouched")
        self.assertEqual([n for n in os.listdir(os.path.dirname(self.live)) if ".deploy-" in n or ".old-" in n], [])
        if verbs is not None:
            self.assertEqual(self.verbs(), verbs)

    def redirect(self, rel):
        path = os.path.join(self.runtime, rel)
        os.makedirs(self.sentinel, exist_ok=True)
        with open(os.path.join(self.sentinel, "keep.txt"), "w") as fh:
            fh.write("keep\n")
        shutil.move(path, os.path.join(self.tmp.name, "moved-" + rel.replace("/", "-")))
        os.symlink(self.sentinel, path)
        return ts.tree_hash(self.sentinel)

    def sc_symlinks_refused(self):
        self.ok()
        self.write_repo("handlers/account-open-wip.js", "// v2\n")
        for rel in ("client/custom/src", "client", "client/custom"):
            with self.sub(component=rel):
                self.fresh()
                self.ok()
                self.write_repo("handlers/account-open-wip.js", "// v2\n")
                self.live_before = snapshot(self.live)
                keep = self.redirect(rel)
                res = self.deploy()
                self.refused(res, verbs=[])
                self.assertEqual(ts.tree_hash(self.sentinel), keep)

    def sc_symlink_planted_while_stopping(self):
        for rel in ("client/custom/src", "client/custom", "client"):
            with self.sub(component=rel):
                self.fresh()
                self.ok()
                self.write_repo("handlers/account-open-wip.js", "// v2\n")
                self.live_before = snapshot(self.live)
                os.makedirs(self.sentinel)
                keep = ts.tree_hash(self.sentinel)
                path = os.path.join(self.runtime, rel)
                cmd = f"mv -T -- {shlex.quote(path)} {shlex.quote(path)}.moved && ln -s -- {shlex.quote(self.sentinel)} {shlex.quote(path)}"
                res = self.deploy(FAKE_DOCKER_ON_STOP=cmd)
                self.assertTrue(os.path.islink(path), "the plant happened")
                self.refused(res, verbs=["ps --status running -q crm-app", "stop crm-daemon crm-app"])
                self.assertIn("left stopped", res.stderr)
                self.assertEqual(ts.tree_hash(self.sentinel), keep)

    def sc_symlink_in_repository(self):
        os.makedirs(self.sentinel)
        os.symlink(self.sentinel, os.path.join(self.rsrc, "handlers", "link"))
        self.live_before = snapshot(self.live)
        res = self.deploy()
        self.refused(res, verbs=[])
        self.assertIn("symlink inside the client source", res.stderr)
        self.assertFalse(os.path.lexists(self.src))

    def sc_symlinked_source_root(self):
        shutil.move(self.rsrc, os.path.join(self.tmp.name, "real-src"))
        os.symlink(os.path.join(self.tmp.name, "real-src"), self.rsrc)
        self.live_before = snapshot(self.live)
        res = self.deploy()
        self.refused(res, verbs=[])
        self.assertIn("not a real directory", res.stderr)

    def sc_writable_client_refused(self):
        self.ok()
        self.write_repo("handlers/account-open-wip.js", "// v2\n")
        self.live_before = snapshot(self.live)
        src_before = snapshot(self.src)
        for mode in (0o775, 0o757, 0o777, 0o722):
            with self.sub(mode=oct(mode)):
                os.chmod(self.client, mode)
                res = self.deploy()
                self.refused(res, verbs=[])
                self.assertIn("group- or world-writable", res.stderr)
                self.assertEqual(snapshot(self.src), src_before)
        os.chmod(self.client, 0o755)
        self.ok()

    def sc_preexisting_names(self):
        self.ok()
        self.write_repo("handlers/account-open-wip.js", "// v2\n")
        parent = os.path.dirname(self.live)
        for base, name in ((self.cc, f".src.deploy-{STAMP}"), (self.cc, f".src.old-{STAMP}"),
                           (self.cc, f".src.failed-{STAMP}"), (parent, f".Custom.failed-{STAMP}")):
            with self.sub(name=name):
                self.live_before = snapshot(self.live)
                path = os.path.join(base, name)
                os.symlink(os.path.join(self.tmp.name, "nowhere"), path)  # even a dangling link
                src_before = snapshot(self.src)
                res = self.deploy()
                self.refused(res, verbs=[])
                self.assertIn("already exists", res.stderr)
                self.assertTrue(os.path.islink(path), "reported, not removed")
                self.assertEqual(snapshot(self.src), src_before)
                os.remove(path)

    def sc_none_equals_base(self):
        shutil.rmtree(os.path.join(self.repo, "client"))
        res = self.ok(running=True)
        self.assertEqual(res.stderr, "")
        self.assertEqual(res.stdout.split("\n", 1)[1], (
            f"customisation deployed: {self.repo}/custom/Espo/Custom -> {self.live}\n"
            "crm-app and crm-daemon restarted; clear-cache and rebuild completed in crm-app\n"))
        self.assertEqual(self.verbs(), [
            "ps --status running -q crm-app", "stop crm-daemon crm-app", "up -d --wait crm-app crm-daemon",
            "exec -T -u www-data -w /var/www/html crm-app php bin/command clear-cache",
            "exec -T -u www-data -w /var/www/html crm-app php bin/command rebuild"])
        self.assertEqual(self.names(), ["modules", "res.js", "unmanaged.txt"])
        # a leftover is not even listed when there is no browser asset on either side
        os.makedirs(os.path.join(self.cc, ".src.old-20250101T000000Z"))
        res = self.ok(running=False)
        self.assertEqual(res.stderr, "")
        self.assertEqual(res.stdout.split("\n", 1)[1], (
            f"customisation deployed: {self.repo}/custom/Espo/Custom -> {self.live}\n"
            "crm-app was not running: left stopped, clear-cache/rebuild skipped. A first installation "
            "rebuilds by itself; otherwise re-run this script once the stack is up.\n"))
        self.assertEqual(self.verbs(), ["ps --status running -q crm-app", "stop crm-daemon crm-app"])

    # ---- marker guard (CRM-WIP-LINK-001R2): the marker must be a regular file, not a link ----
    MARKER_RUNS = ("install", "update", "removal")
    MARKER_KINDS = ("link-inside", "dangling-link", "link-to-canary", "directory", "fifo")
    MARKER_LINE = "client/custom/src is managed by scripts/deploy_custom.sh\n"

    @property
    def marker(self):
        return os.path.join(self.cc, MARKER)

    @property
    def canary(self):
        return os.path.join(self.tmp.name, "canary.txt")

    @property
    def dangling_target(self):
        return os.path.join(self.tmp.name, "dangling-target")

    def deploy_bounded(self, **env):
        """deploy(), but a script blocked on a marker (a write into a FIFO) fails as a
        test assertion after a short time instead of hanging for the full timeout."""
        real = subprocess.run

        def bounded(*args, **kwargs):
            kwargs["timeout"] = 20
            try:
                return real(*args, **kwargs)
            except subprocess.TimeoutExpired as exc:
                raise AssertionError("the script hung on the marker (a write into it blocked)") from exc
        with mock.patch.object(subprocess, "run", bounded):
            return self.deploy(**env)

    def marker_prepare(self, run):
        """The runtime and repository of one run kind, with a regular marker where the run has one."""
        if run == "install":
            return
        self.ok()  # an earlier good install: managed src and a regular marker
        if run == "update":
            self.write_repo("handlers/account-open-wip.js", "// v2 (the update)\n")
        else:
            shutil.rmtree(self.rsrc)  # removal: the repository has no client/custom/src

    def marker_plant(self, kind, path=None):
        """Put a marker of this kind in place (replacing a regular marker); returns the canary bytes."""
        path = path or self.marker
        with open(self.canary, "w") as fh:
            fh.write("canary: nothing may write here or remove it\n")
        if os.path.lexists(path):
            os.remove(path)
        if kind == "link-inside":
            self.write("client/custom/marker-target.txt", "a regular file inside client/custom\n")
            os.symlink(os.path.join(self.cc, "marker-target.txt"), path)
        elif kind == "dangling-link":
            os.symlink(self.dangling_target, path)
        elif kind == "link-to-canary":
            os.symlink(self.canary, path)
        elif kind == "directory":
            os.mkdir(path)
            with open(os.path.join(path, "inner.txt"), "w") as fh:
                fh.write("inner\n")
        elif kind == "fifo":
            os.mkfifo(path)
        else:
            raise AssertionError(kind)

    def marker_world(self):
        """Everything a refused run must leave exactly as it was (types, modes, link targets, bytes)."""
        return {"client": ts.tree_hash(self.client),
                "custom": ts.tree_hash(os.path.join(self.runtime, "custom")),
                "marker": snapshot(self.marker) if not stat.S_ISFIFO(os.lstat(self.marker).st_mode) else "fifo",
                "marker-mode": os.lstat(self.marker).st_mode,
                "canary": snapshot(self.canary),
                "dangling-target-created": os.path.lexists(self.dangling_target)}

    def marker_no_working_names(self):
        parent = os.path.dirname(self.live)
        for d in (self.cc, parent):
            self.assertEqual([n for n in os.listdir(d) if ".deploy-" in n or ".old-" in n or ".failed-" in n], [],
                             "no working name was created")

    def marker_refusal(self, run, kind):
        self.fresh()
        self.marker_prepare(run)
        self.marker_plant(kind)
        before = self.marker_world()
        res = self.deploy_bounded()
        self.assertNotEqual(res.returncode, 0, f"{run}/{kind}: {res.stdout}{res.stderr}")
        self.stderr_has(res, f"refusing to deploy: the marker is not a regular file: {self.marker}")
        self.assertEqual(self.verbs(), [], f"{run}/{kind}: no docker call, so nothing was stopped, removed or rebuilt")
        self.assertEqual(self.marker_world(), before, f"{run}/{kind}: the runtime and the canary are untouched")
        self.assertFalse(os.path.lexists(self.dangling_target), "nothing was written through the link")
        self.marker_no_working_names()

    def sc_marker_refused_install(self):
        for kind in self.MARKER_KINDS:
            with self.sub(run="install", kind=kind):
                self.marker_refusal("install", kind)

    def sc_marker_refused_update(self):
        for kind in self.MARKER_KINDS:
            with self.sub(run="update", kind=kind):
                self.marker_refusal("update", kind)

    def sc_marker_refused_removal(self):
        for kind in self.MARKER_KINDS:
            with self.sub(run="removal", kind=kind):
                self.marker_refusal("removal", kind)

    def sc_marker_second_pass(self):
        """The marker becomes a link while the stack stops: refused after the stop, stack left stopped."""
        for run in ("install", "update"):
            with self.sub(run=run):
                self.fresh()
                self.marker_prepare(run)
                with open(self.canary, "w") as fh:
                    fh.write("canary: nothing may write here or remove it\n")
                canary = snapshot(self.canary)
                cmd = f"rm -f -- {shlex.quote(self.marker)} && ln -s -- {shlex.quote(self.canary)} {shlex.quote(self.marker)}"
                client_before = ts.tree_hash(self.src) if os.path.isdir(self.src) else None
                custom_before = ts.tree_hash(os.path.join(self.runtime, "custom"))
                res = self.deploy_bounded(FAKE_DOCKER_ON_STOP=cmd)
                self.assertTrue(os.path.islink(self.marker), f"{run}: the plant happened")
                self.assertNotEqual(res.returncode, 0, f"{run}: {res.stdout}{res.stderr}")
                self.stderr_has(res, f"refusing to deploy: the marker is not a regular file: {self.marker}", "left stopped")
                self.assertEqual(self.verbs(), ["ps --status running -q crm-app", "stop crm-daemon crm-app"])
                self.assertEqual(os.readlink(self.marker), self.canary)
                self.assertEqual(snapshot(self.canary), canary, "nothing was written through the link")
                self.assertEqual(ts.tree_hash(self.src) if os.path.isdir(self.src) else None, client_before)
                self.assertEqual(ts.tree_hash(os.path.join(self.runtime, "custom")), custom_before)
                self.marker_no_working_names()

    def sc_marker_positive_controls(self):
        """The same harness with the guard intact accepts a regular marker (so the refusals are not vacuous)."""
        with self.sub(run="install"):
            self.fresh()
            self.assertFalse(os.path.lexists(self.marker))
            self.ok()
            self.assertTrue(os.path.isfile(self.marker) and not os.path.islink(self.marker))
            with open(self.marker) as fh:
                self.assertEqual(fh.read(), self.MARKER_LINE)
            self.tree_equal(self.src, self.rsrc)
        with self.sub(run="update"):
            self.fresh()
            self.marker_prepare("update")
            self.assertTrue(os.path.isfile(self.marker) and not os.path.islink(self.marker))
            self.ok()
            self.tree_equal(self.src, self.rsrc)
            self.assertTrue(os.path.isfile(self.marker) and not os.path.islink(self.marker))
            with open(self.marker) as fh:
                self.assertEqual(fh.read(), self.MARKER_LINE)
        with self.sub(run="removal"):
            self.fresh()
            self.marker_prepare("removal")
            self.assertTrue(os.path.isfile(self.marker) and not os.path.islink(self.marker))
            self.ok()
            self.assertFalse(os.path.lexists(self.src))
            self.assertFalse(os.path.lexists(self.marker))


class TestClientDelivery(Delivery):
    def test_first_install(self): self.sc_first_install()
    def test_first_install_stack_not_running(self): self.sc_not_running()
    def test_update_reflects_changes_and_keeps_previous_until_last_step(self): self.sc_update()
    def test_timestamp_that_does_not_advance_fails_with_the_step(self): self.sc_timestamp_not_advancing()
    def test_each_post_swap_failure_restores_both_trees(self): self.sc_post_swap_failures()
    def test_recovery_failure_is_reported(self): self.sc_recovery_failed()
    def test_swap_failures_restore_both_trees(self): self.sc_swap_failures()
    def test_failure_with_the_stack_stopped_leaves_it_stopped(self): self.sc_swap_failure_stack_stopped()
    def test_stage_failures(self): self.sc_stage_failures()
    def test_interruption_after_the_stop_restores_both_trees(self): self.sc_interrupted()
    def test_marker_step_failure_restores(self): self.sc_marker_failure()
    def test_managed_removal(self): self.sc_managed_removal()
    def test_managed_removal_failure_restores(self): self.sc_removal_failure_restores()
    def test_unmanaged_src_is_left_untouched_with_a_notice(self): self.sc_unmanaged_untouched()
    def test_leftovers_are_listed_and_never_touched(self): self.sc_leftovers()
    def test_other_client_custom_entries_are_never_touched(self): self.sc_modules_never_touched()
    def test_symlinked_components_are_refused(self): self.sc_symlinks_refused()
    def test_symlink_planted_while_the_stack_stops_is_refused(self): self.sc_symlink_planted_while_stopping()
    def test_symlink_inside_the_repository_tree_is_refused(self): self.sc_symlink_in_repository()
    def test_symlinked_repository_source_is_refused(self): self.sc_symlinked_source_root()
    def test_group_or_world_writable_client_is_refused(self): self.sc_writable_client_refused()
    def test_preexisting_working_names_are_refused(self): self.sc_preexisting_names()
    def test_no_asset_on_either_side_equals_the_base_behaviour(self): self.sc_none_equals_base()

    def test_marker_that_is_not_a_regular_file_is_refused_on_install(self): self.sc_marker_refused_install()
    def test_marker_that_is_not_a_regular_file_is_refused_on_update(self): self.sc_marker_refused_update()
    def test_marker_that_is_not_a_regular_file_is_refused_on_removal(self): self.sc_marker_refused_removal()
    def test_marker_replaced_by_a_link_while_the_stack_stops_is_refused(self): self.sc_marker_second_pass()
    def test_a_regular_marker_is_accepted_on_install_update_and_removal(self): self.sc_marker_positive_controls()

    def test_exit_codes_are_documented_in_the_script_header(self):
        with open(self.script) as fh:
            header = fh.read().split("set -euo pipefail")[0]
        for code, step in ((20, "stage-custom"), (21, "stage-client"), (22, "swap-custom"), (23, "swap-client"),
                           (24, "up"), (25, "clear-cache"), (26, "rebuild"), (27, "update-app-timestamp"),
                           (28, "marker"), (29, "interrupted"), (30, "cleanup")):
            self.assertRegex(header, rf"#\s+{code} +{step}\b")
        self.assertEqual(len({20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30}), 11)

    def test_backup_still_archives_the_handler(self):
        self.ok()
        res = self.run_script("backup.sh", "dev")
        self.assertEqual(res.returncode, 0, res.stderr)


def replace_once(text, old, new):
    assert old in text, f"mutation target not found: {old!r}"
    return text.replace(old, new)


# (name, script mutation, scenario that must then fail)
MUTATIONS = [
    ("marker not required for removal",
     lambda s: replace_once(s, 'if [ -f "$marker" ] && [ ! -L "$marker" ]; then cmode=remove', 'if true; then cmode=remove'),
     "sc_unmanaged_untouched"),
    ("client/ privacy not checked", lambda s: replace_once(s, '    owned_private "$client_dir"\n', ''), "sc_writable_client_refused"),
    ("symlinks in the repository tree allowed",
     lambda s: replace_once(s, '[ -z "$(find "$csrc" -type l -print -quit)" ] \\\n        || die "refusing to deploy: symlink inside', 'true \\\n        || die "refusing to deploy: symlink inside'),
     "sc_symlink_in_repository"),
    ("source root symlink allowed", lambda s: replace_once(s, '[ ! -L "$csrc" ] && [ -d "$csrc" ]', '[ -d "$csrc" ]'), "sc_symlinked_source_root"),
    ("src may be a symlink", lambda s: replace_once(s, 'if [ -e "$csrc_live" ] || [ -L "$csrc_live" ]; then real_dir "$csrc_live"; fi\n    if [ -e "$marker"', 'if [ -e "$marker"'), "sc_symlinks_refused"),
    ("client/custom not secured", lambda s: replace_once(s, '    secure_dir "$client_custom"\n    check_client_paths owned', '    check_client_paths owned'), "sc_modules_never_touched"),
    ("working name .src.deploy not checked", lambda s: replace_once(s, '    absent "$cstaging"\n', ''), "sc_preexisting_names"),
    ("working name .src.failed not checked", lambda s: replace_once(s, '    absent "$cfailed"\n', ''), "sc_preexisting_names"),
    ("working name .Custom.failed not checked", lambda s: replace_once(s, '    absent "$failed"\n', ''), "sc_preexisting_names"),
    ("no restore of the trees", lambda s: replace_once(s, "restore_trees() {\n    local rc=0\n", "restore_trees() {\n    return 0\n    local rc=0\n"), "sc_post_swap_failures"),
    ("failed trees not kept", lambda s: replace_once(s, 'mv -T -- "$csrc_live" "$cfailed" || rc=1', 'rm -rf -- "$csrc_live" || rc=1'), "sc_post_swap_failures"),
    ("one exit code for every step", lambda s: replace_once(s, '    exit "$code"\n}\nrun_step', '    exit 1\n}\nrun_step'), "sc_post_swap_failures"),
    ("step not named", lambda s: replace_once(s, 'FAILED STEP: $step"', 'FAILED: $step"'), "sc_swap_failures"),
    ("timestamp step skipped", lambda s: replace_once(s, '    run_step update-app-timestamp 27 advance_app_timestamp\n', ''), "sc_first_install"),
    ("timestamp need not advance", lambda s: s.replace('-le "$before"', '-lt "$before"'), "sc_timestamp_not_advancing"),
    ("old trees removed too early", lambda s: replace_once(s, 'if [ -n "$was_running" ]; then\n    run_step up 24', 'remove_tree "$old"; remove_tree "$cold"\nif [ -n "$was_running" ]; then\n    run_step up 24'), "sc_update"),
    ("leftovers not listed", lambda s: replace_once(s, '    list_leftovers\n', ''), "sc_leftovers"),
    ("marker not written", lambda s: replace_once(s, 'scripts/deploy_custom.sh" > "$marker"', 'scripts/deploy_custom.sh" > /dev/null'), "sc_first_install"),
    ("marker not removed", lambda s: replace_once(s, "        rm -f -- \"$marker\"\n", "        true\n"), "sc_managed_removal"),
    ("removal not restored on failure", lambda s: replace_once(s, '    if [ -n "$client_aside" ]; then mv -T -- "$cold" "$csrc_live" || rc=1; fi', ''), "sc_removal_failure_restores"),
    ("interruption not handled", lambda s: replace_once(s, "trap 'fail_step interrupted 29' INT TERM HUP\n", ""), "sc_interrupted"),
    ("base behaviour changed when nothing is managed", lambda s: replace_once(s, 'if [ "$cmode" = none ]; then\n    # Neither', 'if false; then\n    # Neither'), "sc_none_equals_base"),
    ("leftovers listed when nothing is managed", lambda s: replace_once(s, "if [ \"$cmode\" != none ]; then\n    [ \"$cmode\" != install ] || check_client_source\n    check_client_paths\n    secure_dir", "list_leftovers\nif [ \"$cmode\" != none ]; then\n    [ \"$cmode\" != install ] || check_client_source\n    check_client_paths\n    secure_dir"), "sc_none_equals_base"),
    ("staging copy failure not stepped", lambda s: replace_once(s, "run_step stage-client 21 stage_client", "stage_client || true"), "sc_stage_failures"),
    ("recovery does not restart the stack", lambda s: replace_once(s, "{ compose up -d --wait crm-app crm-daemon \\\n            && app_exec", "{ true \\\n            && app_exec"), "sc_post_swap_failures"),
    ("RECOVERY FAILED never printed", lambda s: replace_once(s, "RECOVERY FAILED:", "RECOVERED?:"), "sc_recovery_failed"),
    ("the other client/custom entries are listed as leftovers", lambda s: replace_once(s, '$d"/.src.deploy-* "$d"/.src.old-*', '$d"/* "$d"/.src.old-*'), "sc_leftovers"),
    # marker guard (CRM-WIP-LINK-001R2): M05 and its variants
    ("M05 marker guard body removed",
     lambda s: replace_once(s, '        [ ! -L "$marker" ] && [ -f "$marker" ] \\\n            || die "refusing to deploy: the marker is not a regular file: $marker"\n', '        true\n'),
     "sc_marker_refused_install"),
    ("M05a marker symlink test dropped (only -f stays)",
     lambda s: replace_once(s, '[ ! -L "$marker" ] && [ -f "$marker" ] \\\n            || die', '[ -f "$marker" ] \\\n            || die'),
     "sc_marker_refused_update"),
    ("M05b marker regular-file test dropped (only ! -L stays)",
     lambda s: replace_once(s, '[ ! -L "$marker" ] && [ -f "$marker" ] \\\n            || die', '[ ! -L "$marker" ] \\\n            || die'),
     "sc_marker_refused_removal"),
    ("M05c marker guard entered only when -e is true (a dangling link escapes)",
     lambda s: replace_once(s, 'if [ -e "$marker" ] || [ -L "$marker" ]; then\n        [ ! -L', 'if [ -e "$marker" ]; then\n        [ ! -L'),
     "sc_marker_refused_install"),
    ("M05d marker refusal downgraded to a warning",
     lambda s: replace_once(s, '|| die "refusing to deploy: the marker is not a regular file: $marker"', '|| echo "warning: the marker is not a regular file: $marker" >&2'),
     "sc_marker_second_pass"),
]


class TestEveryRuleIsNonVacuous(Delivery):
    """Each rule removed from a copy of the script makes its scenario fail."""

    def test_mutations_are_caught(self):
        for name, mutate, scenario in MUTATIONS:
            with self.subTest(mutation=name):
                self.mutator = mutate
                self.fresh()
                syntax = subprocess.run(["bash", "-n", self.script], capture_output=True, text=True)
                self.assertEqual(syntax.returncode, 0, syntax.stderr)
                with self.assertRaises(AssertionError, msg=f"not caught: {name}"):
                    getattr(self, scenario)()
        self.mutator = None

    def test_the_unmutated_script_passes_every_scenario(self):
        for name in sorted({m[2] for m in MUTATIONS}):
            with self.sub(scenario=name):
                self.fresh()
                getattr(self, name)()


if __name__ == "__main__":
    unittest.main()
