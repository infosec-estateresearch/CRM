"""Command line: ``contract-check``, ``count``, ``extract``, ``reconcile``, ``selftest``, ``hostcheck``.

Live modes read ``CRM_SF_ORIGIN``, ``CRM_SF_CLIENT_ID``, ``CRM_SF_CLIENT_SECRET`` and
``CRM_SF_API_VERSION`` from the environment (the Compose ``env_file``) and fail loudly when
one is missing. Output is counts only. No exception text, response body or value is ever
printed: errors show a fixed code, the HTTP status and the Salesforce ``errorCode``.

CRM-002-S (temporary): ``--auth soap-legacy --credentials-stdin`` on ``contract-check``,
``count`` and ``extract`` reads one JSON object ``{"username": ..., "password": ...}`` (at most
4 KiB) from stdin, closes stdin, and authenticates through SOAP partner ``login`` only. The
environment then needs only ``CRM_SF_ORIGIN`` and optionally ``CRM_SF_API_VERSION``
(default ``59.0``, 31.0 to 64.0); a username or password is never read from the
environment. ``--waiver PATH`` (soap-legacy only) supplies the write-capable identity waiver.

Exit codes: 0 ok / RECONCILED; 2 usage or config; 3 metadata gate failed; 4 refused request
or HTTP error; 5 snapshot error; 10 RECONCILED_WITH_DRIFT; 11 INCOMPLETE; 12 selftest failed.
"""

import argparse
import datetime as _dt
import json
import logging
import os
import sys

from . import TOOL_VERSION, auth_soap, hostcheck
from .client import SalesforceClient
from .contract import load_contract, soql_count
from .errors import ConfigError, MigrateError
from .extract import DRIFT, INCOMPLETE, RECONCILED, ExtractOptions, run_extract
from .log import CountsLog, get_logger
from .manifest import OutputDir
from .metadata import run_gate
from .policy import RequestPolicy
from .reconcile import run_reconcile
from .selftest import run_selftest
from .transport import HttpsTransport
from .waiver import load_waiver

ENV_NAMES = ("CRM_SF_ORIGIN", "CRM_SF_CLIENT_ID", "CRM_SF_CLIENT_SECRET", "CRM_SF_API_VERSION")
LEGACY_ENV_NAMES = ("CRM_SF_ORIGIN", "CRM_SF_API_VERSION")
STATUS_EXIT = {RECONCILED: 0, DRIFT: 10, INCOMPLETE: 11}
AUTH_MODES = ("client-credentials", "soap-legacy")
MAX_STDIN_BYTES = 4096


def default_contract_path():
    migrate_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(migrate_dir, "contract", "salesforce-fields.json")


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # never echo argument values
        self.print_usage(sys.stderr)
        raise ConfigError("usage", detail="invalid arguments")


def _live_options(p):
    p.add_argument("--out", required=True)
    p.add_argument("--auth", choices=AUTH_MODES, default="client-credentials")
    p.add_argument("--credentials-stdin", action="store_true")
    p.add_argument("--sandbox", action="store_true")
    p.add_argument("--waiver")


def build_parser():
    p = _Parser(prog="crm-migrate", description="Read-only Salesforce extractor (CRM-002).")
    sub = p.add_subparsers(dest="mode", required=True, parser_class=_Parser)
    for mode in ("contract-check", "count"):
        _live_options(sub.add_parser(mode))
    e = sub.add_parser("extract")
    _live_options(e)
    e.add_argument("--passes", type=int, default=3)
    e.add_argument("--overlap-minutes", type=int, default=15)
    r = sub.add_parser("reconcile")
    r.add_argument("--snapshot", required=True)
    r.add_argument("--previous")
    r.add_argument("--out", required=True)
    s = sub.add_parser("selftest")
    s.add_argument("--quick", action="store_true")
    s.add_argument("--out", required=True)
    h = sub.add_parser("hostcheck")
    h.add_argument("args", nargs=argparse.REMAINDER)
    return p


def load_config(environ):
    missing = [n for n in ENV_NAMES if not environ.get(n)]
    if missing:
        raise ConfigError("config_missing", detail="missing " + ",".join(missing))
    return {n: environ[n] for n in ENV_NAMES}


class _DuplicateKey(Exception):
    """Internal marker; never escapes ``read_stdin_credentials``."""


def _no_duplicate_keys(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise _DuplicateKey()
    return dict(pairs)


def read_stdin_credentials(stream):
    """One JSON object ``{"username", "password"}`` from ``stream`` (<= 4 KiB), then close it.

    Values are never placed in the environment, arguments, files, logs or exception text."""
    if stream is None:
        raise ConfigError("credentials_stdin", detail="no stdin")
    try:
        raw = getattr(stream, "buffer", stream).read(MAX_STDIN_BYTES + 1)
    finally:
        try:
            stream.close()
        except Exception:  # closing is best effort; never report a value
            pass
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not raw:
        raise ConfigError("credentials_stdin", detail="no credentials on stdin")
    if len(raw) > MAX_STDIN_BYTES:
        raise ConfigError("credentials_stdin", detail="credentials on stdin exceed 4 KiB")
    doc, parsed, dup = None, False, False
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
        parsed = True
    except _DuplicateKey:
        dup = True
    except (UnicodeDecodeError, ValueError):
        pass
    finally:
        raw = None
    # Raised outside the except: no __context__ holding the raw stdin (password included).
    if dup:
        raise ConfigError("credentials_stdin", detail="credentials JSON repeats a key")
    if not parsed:
        raise ConfigError("credentials_stdin", detail="credentials on stdin are not a JSON object")
    if not isinstance(doc, dict) or sorted(doc) != ["password", "username"]:
        raise ConfigError("credentials_stdin", detail="credentials JSON must hold exactly username and password")
    for key in ("username", "password"):
        if not isinstance(doc[key], str) or not doc[key]:
            raise ConfigError("credentials_stdin", detail="username and password must be non-empty strings")
        try:
            doc[key].encode("utf-8", "strict")      # e.g. a lone surrogate from a JSON \ud800 escape
        except UnicodeError:
            valid = False
        else:
            valid = True
        if not valid:                               # raised outside the except: no chained value
            raise ConfigError("credentials_invalid", detail="username and password must be valid UTF-8")
    return doc["username"], doc["password"]


def load_legacy_config(environ):
    if not environ.get("CRM_SF_ORIGIN"):
        raise ConfigError("config_missing", detail="missing CRM_SF_ORIGIN")
    present = sorted(n for n in ("CRM_SF_CLIENT_ID", "CRM_SF_CLIENT_SECRET") if n in environ)
    if present:
        raise ConfigError("config_unexpected", detail="soap-legacy refuses " + ",".join(present))
    version = environ.get("CRM_SF_API_VERSION") or auth_soap.DEFAULT_SOAP_VERSION
    auth_soap.validate_soap_version(version)
    return {"CRM_SF_ORIGIN": environ["CRM_SF_ORIGIN"], "CRM_SF_API_VERSION": version}


def check_auth_args(args):
    legacy = args.auth == "soap-legacy"
    if legacy and not args.credentials_stdin:
        raise ConfigError("usage", detail="--auth soap-legacy requires --credentials-stdin")
    if not legacy and (args.credentials_stdin or args.sandbox or args.waiver):
        raise ConfigError("usage", detail="--credentials-stdin, --sandbox and --waiver need --auth soap-legacy")


def legacy_client(environ, contract, stdin, *, sandbox=False, waiver_path=None, transport=None, today=None):
    """SOAP-legacy client. The waiver is validated before any request is sent."""
    cfg = load_legacy_config(environ)
    origin, version = cfg["CRM_SF_ORIGIN"], cfg["CRM_SF_API_VERSION"]
    waiver = load_waiver(waiver_path, today) if waiver_path else None
    username, password = read_stdin_credentials(stdin)
    host = auth_soap.SANDBOX_LOGIN_HOST if sandbox else auth_soap.LOGIN_HOST
    if transport is None:
        transport = HttpsTransport(RequestPolicy(origin, version, contract.fields_by_object(),
                                                 soap_login_host=host))
    client = SalesforceClient(origin, version, transport, contract, soap_login_host=host)
    try:
        client.authenticate_soap(username, password)
    finally:
        username = password = None
    if waiver is not None:
        client.set_write_waiver(waiver)
    return client


def live_client(environ, contract, transport=None):
    cfg = load_config(environ)
    origin, version = cfg["CRM_SF_ORIGIN"], cfg["CRM_SF_API_VERSION"]
    if transport is None:
        transport = HttpsTransport(RequestPolicy(origin, version, contract.fields_by_object()))
    client = SalesforceClient(origin, version, transport, contract)
    client.authenticate(cfg["CRM_SF_CLIENT_ID"], cfg["CRM_SF_CLIENT_SECRET"])
    return client


def _contract_check(args, contract, client, log, stdout):
    out = OutputDir(args.out)
    gate = run_gate(client, contract, log)
    out.write_json("contract-check.json", gate.report)
    out.write_json("describe.json", gate.describe_summary)
    status = "PASS" if gate.ok else "FAIL"
    out.finalize({"tool": TOOL_VERSION, "mode": "contract-check", "status": status,
                  "contract_version": contract.version, "contract_sha256": contract.sha256,
                  "identity": gate.report["identity"], "writable_objects": gate.report["writable_objects"]})
    print(f"crm-migrate mode=contract-check status={status} objects={gate.report['objects_checked']} "
          f"failed={gate.report['objects_failed']} writable={gate.report['writable_objects']}", file=stdout)
    print(f"crm-migrate identity: {gate.report['identity']}", file=stdout)
    return 0 if gate.ok else 3


def _count(args, contract, client, log, stdout):
    out = OutputDir(args.out)
    gate = run_gate(client, contract, log)
    out.write_json("contract-check.json", gate.report)
    if not gate.ok:
        out.finalize({"tool": TOOL_VERSION, "mode": "count", "status": "FAIL", "gate": "failed",
                      "identity": gate.report["identity"], "writable_objects": gate.report["writable_objects"]})
        print("crm-migrate mode=count status=FAIL gate=failed", file=stdout)
        return 3
    counts = {}
    for spec in contract.objects:
        q = soql_count(spec)
        counts[spec.name] = {"query": client.count(q, all_rows=False), "queryAll": client.count(q, all_rows=True),
                             "soql": q}
        log.event("count_object", object=spec.name, query=counts[spec.name]["query"],
                  queryall=counts[spec.name]["queryAll"])
        print(f"crm-migrate count object={spec.name} query={counts[spec.name]['query']} "
              f"queryAll={counts[spec.name]['queryAll']}", file=stdout)
    out.write_json("counts.json", counts)
    out.finalize({"tool": TOOL_VERSION, "mode": "count", "status": "PASS", "gate": "passed",
                  "identity": gate.report["identity"], "writable_objects": gate.report["writable_objects"]})
    return 0


def _client_for(args, environ, contract, transport, stdin, today):
    check_auth_args(args)
    if args.auth == "soap-legacy":
        return legacy_client(environ, contract, stdin, sandbox=args.sandbox, waiver_path=args.waiver,
                             transport=transport, today=today)
    return live_client(environ, contract, transport)


def _logout(client, log):
    """Best effort; never changes the run's exit code and never lets an exception escape.
    A failure is logged as ``soap_logout ok=false code=<exception class name>`` only."""
    try:
        if client is None or client.auth_mode != "soap-legacy":
            return
        client.logout_soap()
    except Exception as exc:  # noqa: BLE001 - class name only, never the message
        try:
            name = type(exc).__name__
            log.allow(name)                       # an identifier only; never the message
            log.event("soap_logout", ok=False, code=name)
        except Exception:  # noqa: BLE001 - logging must not change the exit code either
            pass
        return
    try:
        log.event("soap_logout", ok=True)
    except Exception:  # noqa: BLE001
        pass


def main(argv=None, *, environ=None, transport=None, stdout=None, stderr=None, contract_path=None,
         stdin=None, today=None):
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    environ = os.environ if environ is None else environ
    os.umask(0o077)
    logger = get_logger()
    handler = logging.StreamHandler(stderr)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    log = CountsLog(logger)
    mode = None
    client = None
    try:
        old_stderr, sys.stderr = sys.stderr, stderr
        try:
            args = build_parser().parse_args(argv)
        finally:
            sys.stderr = old_stderr
        mode = args.mode
        if mode == "hostcheck":
            return hostcheck.main(args.args, environ, stdout)
        contract = load_contract(contract_path or default_contract_path())
        log.allow_contract(contract)
        log.event("start", mode=mode, contract_version=contract.version)
        if mode == "selftest":
            result = run_selftest(contract, OutputDir(args.out), log, quick=args.quick)
            print(f"crm-migrate mode=selftest status={result['status']} checks={len(result['checks'])}",
                  file=stdout)
            return 0 if result["status"] == RECONCILED else 12
        if mode == "reconcile":
            report = run_reconcile(args.snapshot, args.previous, OutputDir(args.out), log)
            print(f"crm-migrate mode=reconcile snapshot_status={report['snapshot']['status']} "
                  f"objects={len(report['objects'])}", file=stdout)
            return 0
        if mode == "extract":
            options = ExtractOptions(passes=args.passes, overlap=_dt.timedelta(minutes=args.overlap_minutes))
            options.validate()
            check_auth_args(args)
            out = OutputDir(args.out)
            client = _client_for(args, environ, contract, transport, stdin or sys.stdin, today)
            manifest = run_extract(client, contract, out, log, options)
            print(f"crm-migrate mode=extract status={manifest['status']} objects={len(manifest['objects'])} "
                  f"passes={len(manifest['passes'])} requests={client.request_count}", file=stdout)
            return STATUS_EXIT[manifest["status"]]
        client = _client_for(args, environ, contract, transport, stdin or sys.stdin, today)
        if mode == "contract-check":
            return _contract_check(args, contract, client, log, stdout)
        return _count(args, contract, client, log, stdout)
    except MigrateError as exc:
        log.event("error", mode=mode, code=exc.code, status=exc.status, sf_error=exc.sf_error)
        print(f"crm-migrate: error {exc.safe_message()}", file=stderr)
        return exc.exit_code
    except Exception as exc:  # never print the message: it might hold a value
        print(f"crm-migrate: internal error ({type(exc).__name__})", file=stderr)
        return 1
    finally:
        _logout(client, log)
        logger.removeHandler(handler)
