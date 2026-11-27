#!/usr/bin/env python3
"""Repeatable real-browser assurance (CRM-BROWSER-001).

  browser_assurance.py run --out DIR [--journey ID]... [--fault NAME]
  browser_assurance.py verify DIR --commit SHA

`run` builds a disposable Compose project (prefix crm-browser-) from this checkout, runs the
journeys inside a runner container on the project's own internal network, writes evidence to
DIR and removes everything it created. It accepts no target address. Host needs Docker with
Compose and the Python standard library only.

HOST SAFETY (WO 3.2 item 5): every Docker command goes through Policy.check() below; it only
admits resources named or labelled with this run's project. Nothing is pruned or removed by
pattern or image; no Docker socket, privileged container, host network, PID or IPC namespace;
the only host paths mounted are the repository (read-only), the run directory and DIR."""

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import browser_assurance_core as core  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PREFIX = "crm-browser-"
LABEL = "com.docker.compose.project"
MARKER = ".crm-browser-run"
RUNNER_IMAGE = ("mcr.microsoft.com/playwright/python:v1.65.1-noble@sha256:"
                "ce84a3d75a47e81657d2ec2c0a949e6e0ef790abdc32ce6819220a3df987ff9a")
FAULTS = ("broken-screen", "wrong-expectation", "killed-app")
APP_URL = "http://crm-app"
PROOF_PATH = "/var/www/html/client/custom/crm-browser-proof.txt"
PROOF_URL = "/client/custom/crm-browser-proof.txt"
RUN_TIMEOUT = 38 * 60
# Flags of `docker run` that are never allowed.
FORBIDDEN_RUN_FLAGS = ("--privileged", "--cap-add", "--pid", "--ipc", "--uts", "--userns", "--volumes-from",
                        "--device", "--mount", "--net", "--publish", "-p", "--add-host", "--env-file",
                        "--cgroupns", "--sysctl", "--security-opt=seccomp", "--security-opt=apparmor")


class RunError(RuntimeError):
    pass


# --- Docker policy -------------------------------------------------------------------

class Policy:
    """Admits only the Docker commands this runner may issue, for one project."""

    def __init__(self, project, repo, run_dir, out_dir, images):
        self.project, self.repo, self.run_dir, self.out_dir = project, repo, run_dir, out_dir
        self.images = set(images)
        self.mounts_ok = {os.path.realpath(p) for p in (repo, run_dir, out_dir)}

    def own(self, name, sep):
        return isinstance(name, str) and name.startswith(self.project + sep) and re.fullmatch(r"[A-Za-z0-9_.-]+", name)

    def check(self, args):
        args = list(args)
        if not args or any(not isinstance(a, str) for a in args):
            raise RunError("empty or non-text docker command")
        if any("docker.sock" in a for a in args):
            raise RunError("a Docker socket is never mounted")
        verb = args[0]
        label = f"label={LABEL}={self.project}"
        if verb == "compose":
            return self._compose(args)
        if verb == "run":
            return self._run(args)
        if verb == "network" and len(args) == 4 and args[1] == "create" and \
                args[2] == "--label" + "=" + f"{LABEL}={self.project}" and self.own(args[3], "_"):
            return
        if verb == "network" and len(args) == 3 and args[1] == "rm" and self.own(args[2], "_"):
            return
        if verb == "volume" and len(args) == 3 and args[1] == "rm" and self.own(args[2], "_"):
            return
        if verb == "rm" and len(args) == 3 and args[1] == "-f" and self.own(args[2], "-"):
            return
        if verb in ("ps", "network", "volume") and ("--filter", label) == tuple(args[-2:]) and \
                args[1:-2] in (["-a", "-q"], ["ls", "-q"]):
            return
        if verb == "image" and len(args) == 5 and args[1:3] == ["inspect", "--format"] and args[4] in self.images:
            return
        raise RunError(f"docker command refused by policy: {' '.join(args[:3])}")

    def _compose(self, args):
        if args[1:3] != ["-p", self.project] or args[3] != "-f" or \
                os.path.realpath(args[4]) != os.path.realpath(os.path.join(self.run_dir, "compose.json")):
            raise RunError("compose is only used with this run's project and file")
        sub, rest = args[5], args[6:]
        ok = {"up": ["-d", "--wait"], "down": ["-v", "--remove-orphans", "-t", "5"], "stop": []}
        if sub in ok and all(a in ok[sub] or a in ("crm-app", "crm-db", "5") for a in rest):
            return
        if sub == "exec" and rest[:1] == ["-T"] and "--privileged" not in rest:
            return
        raise RunError(f"compose {sub} not allowed")

    def _run(self, args):
        for a in args:
            if any(a == f or a.startswith(f + "=") for f in FORBIDDEN_RUN_FLAGS):
                raise RunError(f"docker run flag refused: {a}")
        if "--rm" not in args or f"--label={LABEL}={self.project}" not in args:
            raise RunError("docker run needs --rm and this run's project label")
        i = args.index("--name")
        if not self.own(args[i + 1], "-"):
            raise RunError("container name must carry the project prefix")
        if any(a.startswith("--network=") for a in args):
            raise RunError("--network is given as a separate argument")
        for i, a in enumerate(args):
            if a == "--network" and not self.own(args[i + 1], "_"):
                raise RunError("a helper container joins only this run's own networks")
        for j, a in enumerate(args):
            if a == "-v":
                src = os.path.realpath(args[j + 1].split(":")[0])
                if not any(src == ok or src.startswith(ok + os.sep) for ok in self.mounts_ok):
                    raise RunError(f"mount source refused: {src}")
                if src == os.path.realpath(self.repo) and not args[j + 1].endswith(":ro"):
                    raise RunError("the repository is mounted read-only")
        if not any(a in self.images for a in args):
            raise RunError("docker run image is not a pinned image")


class Docker:
    def __init__(self, policy):
        self.policy = policy

    def __call__(self, *args, timeout=900, check=True, capture=True):
        self.policy.check(args)
        proc = subprocess.run(["docker", *args], stdout=subprocess.PIPE if capture else None,
                              stderr=subprocess.STDOUT if capture else None, text=True, timeout=timeout)
        if check and proc.returncode != 0:
            raise RunError(f"docker {args[0]} failed ({proc.returncode}): {(proc.stdout or '')[-1500:]}")
        return proc


# --- compose document ----------------------------------------------------------------

def compose_document(repo, project, subnet, secrets_):
    """The run's Compose file, derived from deploy/compose.json (same pinned images)."""
    with open(os.path.join(repo, "deploy", "compose.json"), encoding="utf-8") as fh:
        base = json.load(fh)["services"]
    app_env = {
        "ESPOCRM_DATABASE_PLATFORM": "Mysql", "ESPOCRM_DATABASE_HOST": "crm-db",
        "ESPOCRM_DATABASE_NAME": "crm", "ESPOCRM_DATABASE_USER": "crm",
        "ESPOCRM_DATABASE_PASSWORD": secrets_["db"], "ESPOCRM_ADMIN_USERNAME": secrets_["admin_user"],
        "ESPOCRM_ADMIN_PASSWORD": secrets_["admin"], "ESPOCRM_SITE_URL": APP_URL,
        "CRM_ALLOWED_SOURCES": subnet,
    }
    return {
        "name": project,
        "services": {
            "crm-db": {
                "image": base["crm-db"]["image"],
                "environment": {"MARIADB_DATABASE": "crm", "MARIADB_USER": "crm",
                                "MARIADB_PASSWORD": secrets_["db"], "MARIADB_ROOT_PASSWORD": secrets_["db_root"]},
                "volumes": [{"type": "volume", "source": "db", "target": "/var/lib/mysql"}],
                "networks": ["crm-net"],
                "healthcheck": base["crm-db"]["healthcheck"],
            },
            "crm-app": {
                "image": base["crm-app"]["image"],
                "depends_on": {"crm-db": {"condition": "service_healthy"}},
                "environment": app_env,
                "volumes": [
                    {"type": "volume", "source": "data", "target": "/var/www/html/data"},
                    {"type": "volume", "source": "custom", "target": "/var/www/html/custom"},
                    {"type": "volume", "source": "clientcustom", "target": "/var/www/html/client/custom"},
                    {"type": "bind", "source": repo, "target": "/repo", "read_only": True},
                    {"type": "bind", "source": os.path.join(repo, "deploy", "apache", "crm-access.conf"),
                     "target": "/etc/apache2/conf-enabled/crm-access.conf", "read_only": True},
                ],
                "networks": {"crm-net": {"aliases": ["crm-app"]}},
                "healthcheck": base["crm-app"]["healthcheck"],
            },
        },
        "volumes": {"db": {}, "data": {}, "custom": {}, "clientcustom": {}},
        "networks": {"crm-net": {"driver": "bridge", "internal": True,
                                 "ipam": {"config": [{"subnet": subnet}]}}},
    }


def check_compose(doc, repo, project):
    """Refuse any Compose content outside WO 3.2: no ports, no host namespaces, no privilege,
    no socket, bind mounts only of the repository (read-only) and the Apache file."""
    for name, svc in doc["services"].items():
        for key in ("ports", "privileged", "network_mode", "pid", "ipc", "cap_add", "devices", "container_name",
                    "volumes_from", "extra_hosts", "env_file"):
            if key in svc:
                raise RunError(f"{name}: {key} is not allowed")
        for vol in svc.get("volumes", []):
            if vol["type"] == "bind":
                src = os.path.realpath(vol["source"])
                if not vol.get("read_only") or not (src == os.path.realpath(repo) or src.startswith(os.path.realpath(repo) + os.sep)):
                    raise RunError(f"{name}: bind mount refused: {src}")
            elif vol["type"] != "volume":
                raise RunError(f"{name}: volume type refused")
    if not doc["networks"]["crm-net"].get("internal"):
        raise RunError("the run network must have no external route")
    if doc["name"] != project or not project.startswith(PREFIX):
        raise RunError("project name must carry the crm-browser- prefix")


# --- run directory -------------------------------------------------------------------

def make_run_dir(project):
    path = tempfile.mkdtemp(prefix=project + "-")
    with open(os.path.join(path, MARKER), "w", encoding="utf-8") as fh:
        fh.write(project + "\n")
    return path


def remove_run_dir(path, project):
    """Remove only a directory this run created: its marker names this project."""
    marker = os.path.join(path, MARKER)
    if os.path.islink(path) or not os.path.isdir(path) or not os.path.basename(path).startswith(project + "-"):
        raise RunError(f"refusing to remove {path}: not this run's directory")
    if not os.path.isfile(marker):
        raise RunError(f"refusing to remove {path}: no marker")
    with open(marker, encoding="utf-8") as fh:
        named = fh.read().strip()
    if named != project:
        raise RunError(f"refusing to remove {path}: marker does not name this run")
    shutil.rmtree(path)


def check_out_dir(out):
    if os.path.lexists(out):
        if os.path.islink(out) or not os.path.isdir(out) or os.listdir(out):
            raise RunError(f"--out must be absent or an empty directory: {out}")
    else:
        os.makedirs(out)
    return os.path.realpath(out)


def git_commit(repo):
    """HEAD commit if the checkout is clean Git work, else None (recorded as uncommitted).
    Fallback: with no git program on the host the checkout is recorded as uncommitted, which
    only makes `verify --commit` refuse the evidence; it never changes a step verdict."""
    def git(*a):
        return subprocess.run(["git", "-c", f"safe.directory={repo}", "-C", repo, *a], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    try:
        head, status = git("rev-parse", "HEAD"), git("status", "--porcelain", "--untracked-files=all")
    except OSError:
        return None
    if head.returncode or status.returncode or status.stdout.strip():
        return None
    return head.stdout.strip() if re.fullmatch(r"[0-9a-f]{40}", head.stdout.strip()) else None


# --- the run -------------------------------------------------------------------------

def step(msg):
    print(f"[browser-assurance] {msg}", file=sys.stderr, flush=True)


def pick_subnet():
    return f"10.{secrets.randbelow(56) + 200}.{secrets.randbelow(256)}.0/24"


def pinned_images(repo):
    with open(os.path.join(repo, "deploy", "compose.json"), encoding="utf-8") as fh:
        base = json.load(fh)["services"]
    return [base["crm-db"]["image"], base["crm-app"]["image"], RUNNER_IMAGE]


def run_command(args):
    accounts = core.load_accounts()
    expectations = core.load_expectations([a["kind"] for a in accounts])
    journeys = args.journey or sorted(expectations["journeys"])
    unknown = [j for j in journeys if j not in expectations["journeys"]]
    if unknown:
        raise RunError(f"unknown journeys: {unknown}")
    out = check_out_dir(args.out)
    project = PREFIX + secrets.token_hex(4)
    run_dir = make_run_dir(project)
    images = pinned_images(REPO)
    docker = Docker(Policy(project, REPO, run_dir, out, images))
    uid = f"{os.getuid()}:{os.getgid()}"
    containers, networks = [], []
    compose = ["compose", "-p", project, "-f", os.path.join(run_dir, "compose.json")]
    failure = None
    started = False
    old = {s: signal.signal(s, _interrupt) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        sec = {k: secrets.token_urlsafe(24) for k in ("db", "db_root", "admin")}
        sec["admin_user"] = next(a["userName"] for a in accounts if a["kind"] == "administrator")
        nonce = secrets.token_hex(16)
        proof_sha = hashlib.sha256(nonce.encode()).hexdigest()
        # The run directory is private; it holds the Compose file with this run's own secrets.
        for attempt in range(5):
            subnet = pick_subnet()
            doc = compose_document(REPO, project, subnet, sec)
            check_compose(doc, REPO, project)
            with open(os.path.join(run_dir, "compose.json"), "w", encoding="utf-8") as fh:
                os.fchmod(fh.fileno(), 0o600)
                json.dump(doc, fh)
            started = True
            step(f"{project}: starting stack on {subnet}")
            proc = docker(*compose, "up", "-d", "--wait", timeout=1500, check=False)
            if proc.returncode == 0:
                break
            if "overlap" not in (proc.stdout or "") or attempt == 4:
                raise RunError(f"stack did not start: {(proc.stdout or '')[-1500:]}")
            docker(*compose, "down", "-v", "--remove-orphans", "-t", "5")
        step("deploying the repository's custom code and release settings")
        app_exec = [*compose, "exec", "-T", "crm-app"]
        docker(*app_exec, "sh", "-ec",
               "rm -rf /var/www/html/custom/Espo/Custom && mkdir -p /var/www/html/custom/Espo "
               "&& cp -R /repo/custom/Espo/Custom /var/www/html/custom/Espo/Custom "
               "&& rm -rf /var/www/html/client/custom/src && mkdir -p /var/www/html/client/custom "
               "&& if [ -d /repo/client/custom/src ]; then cp -R /repo/client/custom/src /var/www/html/client/custom/src; fi "
               f"&& printf '%s' '{nonce}' > {PROOF_PATH} "
               "&& chown -R www-data:www-data /var/www/html/custom /var/www/html/client/custom", timeout=300)
        if args.fault == "broken-screen":
            step("fault broken-screen: client code in this run's own stack only")
            docker(*app_exec, "sh", "-ec", BREAK_SCREEN, timeout=120)
        for cmd in ("clear-cache", "rebuild"):
            docker(*app_exec, "su", "-s", "/bin/sh", "www-data", "-c", f"cd /var/www/html && php bin/command {cmd}", timeout=900)
        for name, kind, value in _release_settings():
            docker(*app_exec, "su", "-s", "/bin/sh", "www-data", "-c",
                   f"cd /var/www/html && php bin/command config:set {name} {value} --type={kind}", timeout=300)
        # The administration page loads a frame from the vendor site; this run has no external route.
        # Disabled in this run's own stack only (views/admin/index, setting adminPanelIframeDisabled).
        docker(*app_exec, "su", "-s", "/bin/sh", "www-data", "-c",
               "cd /var/www/html && php bin/command config:set adminPanelIframeDisabled true --type=bool", timeout=300)
        # Runner packages: fetched hash-checked on a helper network, installed offline later.
        egress = f"{project}_egress"
        docker("network", "create", f"--label={LABEL}={project}", egress)
        networks.append(egress)
        os.mkdir(os.path.join(run_dir, "wheels"))
        os.chmod(os.path.join(run_dir, "wheels"), 0o777)
        helper = f"{project}-wheels"
        containers.append(helper)
        docker("run", "--rm", "--name", helper, f"--label={LABEL}={project}", "--network", egress,
               "--user", uid, "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only",
               "--tmpfs", "/tmp", "-e", "HOME=/tmp", "-v", f"{REPO}:/repo:ro",
               "-v", f"{run_dir}/wheels:/wheels", RUNNER_IMAGE,
               "python3", "-m", "pip", "download", "--no-cache-dir", "--require-hashes", "--only-binary=:all:",
               "--no-deps", "-r", "/repo/tests/browser/requirements.lock", "-d", "/wheels", timeout=600)
        docker("network", "rm", egress)
        networks.remove(egress)
        with open(os.path.join(run_dir, "run.json"), "w", encoding="utf-8") as fh:
            os.fchmod(fh.fileno(), 0o644)
            json.dump({"base_url": APP_URL, "admin_user": sec["admin_user"], "admin_password": sec["admin"],
                       "proof_url": PROOF_URL, "proof_sha256": proof_sha, "journeys": journeys,
                       "fault": args.fault}, fh)
        runner = f"{project}-runner"
        containers.append(runner)
        step(f"running journeys {journeys} in the runner container")
        stop_watch = threading.Event()
        if args.fault == "killed-app":
            threading.Thread(target=_kill_app_when_started, args=(docker, compose, out, stop_watch), daemon=True).start()
        proc = docker("run", "--rm", "--name", runner, f"--label={LABEL}={project}", "--network", f"{project}_crm-net",
                      "--user", uid, "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only",
                      "--tmpfs", "/tmp:exec,size=1g", "--shm-size", "1g", "-e", "HOME=/tmp",
                      "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONPATH=/tmp/pydeps",
                      "-v", f"{REPO}:/repo:ro", "-v", f"{run_dir}:/run-data:ro", "-v", f"{out}:/out",
                      RUNNER_IMAGE, "sh", "-ec",
                      "python3 -m pip install --no-cache-dir --no-index --find-links /run-data/wheels --require-hashes "
                      "--only-binary=:all: --no-deps --target /tmp/pydeps -r /repo/tests/browser/requirements.lock "
                      ">/dev/null && exec python3 -s -B /repo/scripts/browser_assurance_runner.py "
                      "--config /run-data/run.json --out /out",
                      timeout=RUN_TIMEOUT, check=False)
        stop_watch.set()
        containers.remove(runner)
        print(proc.stdout or "", file=sys.stderr)
        if proc.returncode != 0:
            failure = "runner reported a failed step or error (exit %d)" % proc.returncode
        _write_manifest(docker, out, accounts, expectations, images, args.fault)
    except (RunError, subprocess.TimeoutExpired, KeyboardInterrupt, OSError, KeyError, ValueError) as err:
        failure = failure or f"{type(err).__name__}: {err}"
    finally:
        for s in old:
            signal.signal(s, signal.SIG_IGN)  # teardown is not interrupted
        leftovers = _teardown(docker, compose, project, run_dir, containers, networks, started)
        for s, h in old.items():
            signal.signal(s, h)
    if leftovers:
        print(f"[browser-assurance] LEFTOVER after teardown: {leftovers}", file=sys.stderr)
        return 3
    if failure:
        print(f"[browser-assurance] FAILED: {failure}", file=sys.stderr)
        return 1
    print("[browser-assurance] PASSED; nothing of the run remains", file=sys.stderr)
    return 0


def _interrupt(signum, _frame):
    raise KeyboardInterrupt(f"signal {signum}")


BREAK_SCREEN = (
    "mkdir -p /var/www/html/client/custom/src/views "
    "&& printf '%s\\n' \"define('custom:views/broken-screen', ['views/record/edit'], function (Dep) { "
    "return Dep.extend({setup: function () { throw new Error('browser-assurance fault: broken screen'); }}); });\" "
    "> /var/www/html/client/custom/src/views/broken-screen.js "
    "&& php -r '$f=\"/var/www/html/custom/Espo/Custom/Resources/metadata/clientDefs/Account.json\"; "
    "$d=is_file($f)?json_decode(file_get_contents($f),true):[]; "
    "$d[\"recordViews\"][\"edit\"]=\"custom:views/broken-screen\"; "
    "file_put_contents($f,json_encode($d));' "
    "&& chown -R www-data:www-data /var/www/html/custom /var/www/html/client/custom")


def _kill_app_when_started(docker, compose, out, stop):
    """killed-app: once the first step has been recorded, stop the application of this run."""
    first = os.path.join(out, "J1", "administrator", "create-firm.json")
    while not stop.is_set():
        if os.path.exists(first):
            docker(*compose, "stop", "crm-app", check=False)
            return
        stop.wait(0.5)


def _release_settings():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import release_settings
    for name, kind, value in release_settings.load():
        yield name, kind, ("true" if value else "false") if kind == "bool" else "'%s'" % value


def _write_manifest(docker, out, accounts, expectations, images, fault=None):
    results_path = os.path.join(out, "results.json")
    if not os.path.isfile(results_path):
        raise RunError("the runner wrote no results.json")
    with open(results_path, encoding="utf-8") as fh:
        res = json.load(fh)
    ids = {}
    for ref in images:
        proc = docker("image", "inspect", "--format", "{{.Id}}", ref, check=False)
        ids[ref] = proc.stdout.strip() if proc.returncode == 0 else "unavailable"
    manifest = core.build_manifest(out, git_commit(REPO), ids,
                                   core.package_hashes(os.path.join(REPO, "tests", "browser", "requirements.lock")),
                                   res.get("browser"), res["results"], expectations, fault)
    core.write_manifest(out, manifest)


def _teardown(docker, compose, project, run_dir, containers, networks, started):
    """Remove what this run created; return what still carries the project label."""
    problems = []
    for name in containers:
        docker("rm", "-f", name, check=False)
    if started:
        docker(*compose, "down", "-v", "--remove-orphans", "-t", "5", check=False)
    for name in networks:
        docker("network", "rm", name, check=False)
    try:
        remove_run_dir(run_dir, project)
    except (RunError, OSError) as err:
        problems.append(str(err))
    label = f"label={LABEL}={project}"
    for args in (("ps", "-a", "-q"), ("network", "ls", "-q"), ("volume", "ls", "-q")):
        proc = docker(*args, "--filter", label, check=False)
        if proc.stdout.strip():
            problems.append(f"{args[0]}: {proc.stdout.split()}")
    return problems


def verify_command(args):
    accounts = core.load_accounts()
    kinds = [a["kind"] for a in accounts]
    expectations = core.load_expectations(kinds)
    if not os.path.isdir(args.dir):
        raise RunError(f"not a directory: {args.dir}")
    problems = core.verify_evidence(args.dir, args.commit, expectations, kinds)
    for p in problems:
        print(f"[browser-assurance] REJECTED: {p}", file=sys.stderr)
    if problems:
        return 1
    print("[browser-assurance] evidence accepted", file=sys.stderr)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="browser_assurance", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--out", required=True)
    run.add_argument("--journey", action="append")
    run.add_argument("--fault", choices=FAULTS)
    ver = sub.add_parser("verify")
    ver.add_argument("dir")
    ver.add_argument("--commit", required=True)
    args = parser.parse_args(argv)
    try:
        return run_command(args) if args.command == "run" else verify_command(args)
    except (RunError, core.DataError) as err:
        print(f"[browser-assurance] refused: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
