"""crm-load command line.

    crm-load verify <snapshot> [--accept-drift URL]
    crm-load users  <snapshot> --role-map FILE --out NEWDIR
    crm-load load   <snapshot> --target dev|beta --out NEWDIR [--accept-drift URL]
                    [--reconciliation RECONCILE-RUN-DIR] [--resume PREVIOUS-OUT-DIR]
                    [--phone-refusals PREVIOUS-OUT-DIR/phone-refusals.json]

``<snapshot>`` is the ``<id>`` directory in either layout (see ``snapshot.locate``).
``--out`` is always a new directory. It gets ``run.json`` (the snapshot manifest sha256 and
the target) before any request, then ``progress.jsonl``, ``load-report.json`` and
``exceptions.jsonl``. ``--resume`` names an earlier, interrupted output directory of the
same snapshot sha and target: its progress is copied into the new ``progress.jsonl`` and
the earlier directory is only read.

``load`` reads CRM_LOAD_HOST (must be 127.0.0.1), CRM_LOAD_PORT and CRM_LOAD_API_KEY from
the environment (root-only runtime env); it fails loudly when any is missing.
``--target dev`` accepts only a synthetic snapshot: ``<name>-selftest/run-1`` or ``run-2``
under a sealed, verified ``mode`` ``selftest`` parent (``snapshot.synthetic_origin``).
``--target beta`` accepts only a ``<name>-extract`` directory outside any ``*-selftest``
directory, and refuses (``synthetic_content_in_beta``) a snapshot in which any Account
``Name`` contains the synthetic marker ``SENTINEL-7f3a``. Output is
counts and codes only; record content never reaches stdout, stderr or the report.

Before any write, ``load`` reads ``GET Settings``: ``--target beta`` refuses
(``phone_international_enabled``, exit 3) unless ``phoneNumberInternational`` is exactly
``false`` (a refused read counts as not confirmed); dev reports the value and continues.
``phone-refusals.json`` in the output holds the sha256 of (sfId, field, number) of every
phone the server refused (number trimmed, as stored); given back with ``--phone-refusals``,
those numbers are not retried. That file is opened with O_NOFOLLOW and must be a regular file
owned by the running user (root under load.sh), mode 0600; the report's ``phoneRefusals``
says whether one was supplied.

Exit codes: 0 ok, 2 usage/config, 3 gate refused, 4 transport, 5 load finished with
write failures.
"""

import argparse
import json
import os
import stat
import sys
import time

from . import TOOL_VERSION
from .api import EspoClient
from .engine import Loader, Progress
from .errors import LoadError
from .log import Log
from .mapping import Mapper, load_json
from .names import NameParser
from .report import build_report, write_outputs
from .snapshot import SUPPORTED_CONTRACT_VERSION, open_snapshot
from .transport import LoopbackHttpTransport
from .users import build_users, load_role_map


TARGETS = ("dev", "beta")
SYNTHETIC_MARKER = "SENTINEL-7f3a"


def _check_target(snapshot, target):
    if target == "dev":
        if not snapshot.synthetic:
            raise LoadError("target_dev_requires_synthetic")
        return
    if snapshot.synthetic or not snapshot.production:
        raise LoadError("target_beta_requires_extract")
    for row in snapshot.rows("Account"):
        name = row.get("Name")
        if isinstance(name, str) and SYNTHETIC_MARKER in name:
            raise LoadError("synthetic_content_in_beta")


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise LoadError("usage")


def _parser():
    p = _Parser(prog="crm-load", add_help=False)
    sub = p.add_subparsers(dest="mode", required=True, parser_class=_Parser)
    v = sub.add_parser("verify", add_help=False)
    v.add_argument("snapshot")
    v.add_argument("--accept-drift")
    u = sub.add_parser("users", add_help=False)
    u.add_argument("snapshot")
    u.add_argument("--role-map", required=True)
    u.add_argument("--out", required=True)
    u.add_argument("--accept-drift")
    ld = sub.add_parser("load", add_help=False)
    ld.add_argument("snapshot")
    ld.add_argument("--out", required=True)
    ld.add_argument("--accept-drift")
    ld.add_argument("--resume")
    ld.add_argument("--reconciliation")
    ld.add_argument("--phone-refusals")
    ld.add_argument("--target", required=True, choices=TARGETS)
    return p


def _new_dir(path):
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        raise LoadError("output_dir_exists") from None
    except OSError:
        raise LoadError("output_dir_unwritable") from None
    return path


RUN_FILE = "run.json"
PROGRESS_FILE = "progress.jsonl"
COMPLETE_FILES = ("load-report.json", "exceptions.jsonl")


def _write_run(out, snapshot, target):
    doc = {"tool": TOOL_VERSION, "snapshotManifestSha": snapshot.manifest_sha256, "target": target}
    fd = os.open(os.path.join(out, RUN_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, sort_keys=True) + "\n")


def _resume_dir(path, snapshot, target):
    """A sealed, interrupted earlier output of the same snapshot sha and target."""
    try:
        st = os.lstat(path)
    except OSError:
        raise LoadError("resume_dir_missing") from None
    if not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o700:
        raise LoadError("resume_dir_invalid")
    names = set(os.listdir(path))
    if names & set(COMPLETE_FILES):
        raise LoadError("resume_dir_complete")
    if names != {RUN_FILE, PROGRESS_FILE}:
        raise LoadError("resume_dir_invalid")
    for name in names:
        fst = os.lstat(os.path.join(path, name))
        if not stat.S_ISREG(fst.st_mode) or stat.S_IMODE(fst.st_mode) != 0o600:
            raise LoadError("resume_dir_invalid")
    try:
        with open(os.path.join(path, RUN_FILE), "rb") as fh:
            run = json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        raise LoadError("resume_dir_invalid") from None
    if not isinstance(run, dict) or run.get("snapshotManifestSha") != snapshot.manifest_sha256:
        raise LoadError("resume_snapshot_mismatch")
    if run.get("target") != target:
        raise LoadError("resume_target_mismatch")
    return os.path.join(path, PROGRESS_FILE)


REFUSALS_FILE = "phone-refusals.json"
_HEX64 = frozenset("0123456789abcdef")


def _refusals_owner():
    """The uid a phone-refusals file must be owned by: the running user (root under load.sh)."""
    return os.geteuid()


def _read_refusals(path):
    """A list of sha256 hex digests (content-free); anything else is refused.

    Opened without following a symlink, then checked on the open descriptor (no race): a
    regular file, owned by the running user (root under load.sh), mode exactly 0600."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        raise LoadError("phone_refusals_unreadable") from None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != _refusals_owner() or stat.S_IMODE(st.st_mode) != 0o600:
            raise LoadError("phone_refusals_not_sealed")
        with os.fdopen(fd, "rb") as fh:
            fd = None
            doc = json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        raise LoadError("phone_refusals_unreadable") from None
    finally:
        if fd is not None:
            os.close(fd)
    if not isinstance(doc, list) or not all(isinstance(h, str) and len(h) == 64 and set(h) <= _HEX64
                                            for h in doc):
        raise LoadError("phone_refusals_invalid")
    return frozenset(doc)


def _write_refusals(out, hashes):
    fd = os.open(os.path.join(out, REFUSALS_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(sorted(hashes)) + "\n")


def check_phone_setting(client, target, log):
    """beta: phoneNumberInternational must be exactly false. dev: reported, never refused."""
    value = client.setting("phoneNumberInternational")
    log.event("settings", phoneNumberInternational=("unknown" if value is _UNKNOWN else value))
    if target == "beta" and value is not False:
        raise LoadError("phone_international_enabled", exit_code=3)


_UNKNOWN = object()


def _env_transport(environ):
    host = environ.get("CRM_LOAD_HOST")
    port = environ.get("CRM_LOAD_PORT")
    key = environ.get("CRM_LOAD_API_KEY")
    if not host or not port or not key:
        raise LoadError("config_missing")
    if not port.isdigit():
        raise LoadError("config_invalid")
    return LoopbackHttpTransport(host, int(port), key)


def run_load(args, transport, log, contract_dir=None, sleep=time.sleep, fail_after=None):
    snapshot = open_snapshot(args.snapshot, args.accept_drift, args.reconciliation)
    _check_target(snapshot, args.target)
    log.event("gate", status=snapshot.manifest["status"], synthetic=snapshot.synthetic)
    mapping = load_json("mapping.json", contract_dir)
    if mapping.get("contractVersion") != SUPPORTED_CONTRACT_VERSION:
        raise LoadError("mapping_contract_mismatch")
    mapper = Mapper(mapping, load_json("lead_source_map.json", contract_dir),
                    NameParser(load_json("name_patterns.json", contract_dir)["patterns"]), snapshot.as_of,
                    snapshot.t_start, synthetic=snapshot.synthetic is True)
    previous = _resume_dir(args.resume, snapshot, args.target) if args.resume is not None else None
    refused = _read_refusals(args.phone_refusals) if args.phone_refusals is not None else frozenset()
    out = _new_dir(args.out)
    _write_run(out, snapshot, args.target)
    log.event("run", resumed=previous is not None, reconciliation=args.reconciliation is not None)
    client = EspoClient(transport, sleep=sleep)
    if fail_after is not None:
        client = fail_after(client)
    progress = Progress(os.path.join(out, PROGRESS_FILE), previous)
    try:
        # Before any write: the phone rule beta depends on (refused unless exactly false).
        check_phone_setting(EspoClient(transport, sleep=sleep, unknown=_UNKNOWN), args.target, log)
    except LoadError:
        progress.close()
        raise
    loader = Loader(snapshot, mapper, client, log, progress, mapping, refused)
    loader.refusals_supplied = args.phone_refusals is not None
    log.event("phone_refusals", supplied=loader.refusals_supplied, remembered=len(refused))
    try:
        loader.run()
    finally:
        progress.close()
    # Only a completed run writes it: an interrupted output stays resumable (run.json + progress).
    _write_refusals(out, loader.refused)
    report = build_report(loader, snapshot.manifest["status"], args.accept_drift)
    write_outputs(out, report, loader.exceptions)
    failed = sum(t.get("failed", 0) for o in loader.objects.values() for t in o["targets"].values())
    for obj, o in loader.objects.items():
        for entity, t in o["targets"].items():
            log.event("object", object=obj, entity=entity, created=t["created"], updated=t["updated"],
                      unchanged=t["unchanged"], failed=t["failed"])
    log.event("load_result", writes=client.writes, exceptions=len(loader.exceptions), failed=failed)
    return report, (5 if failed else 0)


def run_users(args, log):
    snapshot = open_snapshot(args.snapshot, args.accept_drift)
    role_map = load_role_map(args.role_map)
    users, problems, skipped = build_users(snapshot, role_map)
    out = _new_dir(args.out)
    fd = os.open(os.path.join(out, "users.json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(users, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    fd = os.open(os.path.join(out, "exceptions.jsonl"), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for sf_id, reason in problems:
            fh.write(json.dumps({"object": "User", "sfId": sf_id, "reason": reason}, sort_keys=True) + "\n")
    log.event("users_result", users=len(users), inactive=sum(1 for u in users if not u["isActive"]),
              exceptions=len(problems), skipped_user_not_human=skipped)
    return 0


def main(argv, transport=None, environ=None, stdout=None, stderr=None, contract_dir=None, sleep=time.sleep,
         fail_after=None):
    os.umask(0o077)
    stdout = stdout or sys.stdout
    log = Log(stderr or sys.stderr)
    try:
        args = _parser().parse_args(argv)
        if args.mode == "verify":
            snap = open_snapshot(args.snapshot, args.accept_drift)
            stdout.write(f"crm-load mode=verify status={snap.manifest['status']} "
                         f"synthetic={str(snap.synthetic).lower()}\n")
            return 0
        if args.mode == "users":
            return run_users(args, log)
        if transport is None:
            transport = _env_transport(environ if environ is not None else os.environ)
        report, code = run_load(args, transport, log, contract_dir, sleep, fail_after)
        stdout.write(f"crm-load mode=load writes={report['requests']['writes']} "
                     f"exceptions={report['exceptions']['total']} exit={code}\n")
        return code
    except LoadError as exc:
        log.event("refused", code=exc.code, tool=TOOL_VERSION.replace(" ", "-"))
        return exc.exit_code
