"""``selftest``: the synthetic suite end to end through the in-memory fake transport.

It needs no network and no credentials, so it runs in ``crm-migrate-selftest``
(``network_mode: none``). Requests still pass through ``SalesforceClient`` and its
allowlist. ``--quick`` runs two extractions and a reconciliation; the full run adds every
in-run mutation scenario and checks its expected completeness status.
"""

from . import TOOL_VERSION
from .client import SalesforceClient
from .extract import RECONCILED, run_extract
from .reconcile import run_reconcile
from .synthetic import (FAKE_API_VERSION, FAKE_CLIENT_ID, FAKE_CLIENT_SECRET, FAKE_ORIGIN, SCENARIO_EXPECTED,
                        make_fake)


def fake_client(contract, fake):
    client = SalesforceClient(FAKE_ORIGIN, FAKE_API_VERSION, fake, contract)
    client.authenticate(FAKE_CLIENT_ID, FAKE_CLIENT_SECRET)
    return client


def _between_runs(org):
    """Soft delete, logged permanent delete, unlogged permanent delete, and one merge."""
    ids = [rid for rid in sorted(org.rows["Contact"]) if org.rows["Contact"][rid].get("IsDeleted") is not True]
    org.tick()
    org.soft_delete("Contact", ids[10])
    org.hard_delete("Contact", ids[11], log=True)
    org.hard_delete("Contact", ids[12], log=False)
    org.merge("Contact", ids[14], ids[13])


def run_selftest(contract, out, log, quick=True):
    checks = {}
    fake = make_fake(contract, size="quick" if quick else "full")
    client = fake_client(contract, fake)
    m1 = run_extract(client, contract, out.subdir("run-1"), log)
    checks["run_1_reconciled"] = m1["status"] == RECONCILED
    # contract v4 visibleVia: the fixture's relations hidden by soft-deleted parents (L3-shaped)
    checks["visible_via_hidden"] = (m1["objects"]["EmailMessageRelation"].get("hidden_via")
                                    == {"EmailMessage.EmailMessageId": 4, "Contact.RelationId": 4})
    _between_runs(fake.org)
    m2 = run_extract(client, contract, out.subdir("run-2"), log)
    checks["run_2_reconciled"] = m2["status"] == RECONCILED
    report = run_reconcile(out.path + "/run-2", out.path + "/run-1", out.subdir("reconcile"), log)
    d = report["objects"]["Contact"]["deletion_classes"]
    checks["deletion_classes"] = (
        d["absent_since_previous_explained"] == 3
        and d["absent_since_previous_explained_by"] == {"soft_deleted_available": 1, "merged": 1,
                                                        "deletion_evidence": 1}
        and d["absent_since_previous_unexplained"] == 1
    )
    checks["no_write_requests"] = fake.write_requests == 0
    if not quick:
        for name, expected in SCENARIO_EXPECTED.items():
            sfake = make_fake(contract, name)
            sclient = fake_client(contract, sfake)
            man = run_extract(sclient, contract, out.subdir(f"scenario-{name}"), log)
            checks[f"scenario_{name}"] = man["status"] == expected
            checks[f"scenario_{name}_no_writes"] = sfake.write_requests == 0
    failed = sorted(k for k, v in checks.items() if not v)
    status = RECONCILED if not failed else "FAILED"
    result = {"tool": TOOL_VERSION, "mode": "selftest", "quick": quick, "status": status,
              "checks": {k: ("PASS" if v else "FAIL") for k, v in sorted(checks.items())}}
    out.write_json("selftest.json", result)
    out.finalize({"tool": TOOL_VERSION, "mode": "selftest", "status": status, "quick": quick})
    for name, value in sorted(checks.items()):
        log.event("selftest_check", passed=value, index=sorted(checks).index(name))
    log.event("selftest_result", status=status, checks=len(checks), failed=len(failed))
    return result
