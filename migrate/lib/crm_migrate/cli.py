"""Command line: ``contract-check``, ``count``, ``extract``, ``reconcile``, ``selftest``, ``hostcheck``.

Live modes read ``CRM_SF_ORIGIN``, ``CRM_SF_CLIENT_ID``, ``CRM_SF_CLIENT_SECRET`` and
``CRM_SF_API_VERSION`` from the environment (the Compose ``env_file``) and fail loudly when
one is missing. Output is counts only. No exception text, response body or value is ever
printed: errors show a fixed code, the HTTP status and the Salesforce ``errorCode``.

Exit codes: 0 ok / RECONCILED; 2 usage or config; 3 metadata gate failed; 4 refused request
or HTTP error; 5 snapshot error; 10 RECONCILED_WITH_DRIFT; 11 INCOMPLETE; 12 selftest failed.
"""

import argparse
import datetime as _dt
import logging
import os
import sys

from . import TOOL_VERSION, hostcheck
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

ENV_NAMES = ("CRM_SF_ORIGIN", "CRM_SF_CLIENT_ID", "CRM_SF_CLIENT_SECRET", "CRM_SF_API_VERSION")
STATUS_EXIT = {RECONCILED: 0, DRIFT: 10, INCOMPLETE: 11}


def default_contract_path():
    migrate_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(migrate_dir, "contract", "salesforce-fields.json")


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # never echo argument values
        self.print_usage(sys.stderr)
        raise ConfigError("usage", detail="invalid arguments")


def build_parser():
    p = _Parser(prog="crm-migrate", description="Read-only Salesforce extractor (CRM-002).")
    sub = p.add_subparsers(dest="mode", required=True, parser_class=_Parser)
    for mode in ("contract-check", "count"):
        sub.add_parser(mode).add_argument("--out", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--out", required=True)
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
                  "contract_version": contract.version, "contract_sha256": contract.sha256})
    print(f"crm-migrate mode=contract-check status={status} objects={gate.report['objects_checked']} "
          f"failed={gate.report['objects_failed']}", file=stdout)
    return 0 if gate.ok else 3


def _count(args, contract, client, log, stdout):
    out = OutputDir(args.out)
    gate = run_gate(client, contract, log)
    out.write_json("contract-check.json", gate.report)
    if not gate.ok:
        out.finalize({"tool": TOOL_VERSION, "mode": "count", "status": "FAIL", "gate": "failed"})
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
    out.finalize({"tool": TOOL_VERSION, "mode": "count", "status": "PASS", "gate": "passed"})
    return 0


def main(argv=None, *, environ=None, transport=None, stdout=None, stderr=None, contract_path=None):
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
            out = OutputDir(args.out)
            client = live_client(environ, contract, transport)
            manifest = run_extract(client, contract, out, log, options)
            print(f"crm-migrate mode=extract status={manifest['status']} objects={len(manifest['objects'])} "
                  f"passes={len(manifest['passes'])} requests={client.request_count}", file=stdout)
            return STATUS_EXIT[manifest["status"]]
        client = live_client(environ, contract, transport)
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
        logger.removeHandler(handler)
