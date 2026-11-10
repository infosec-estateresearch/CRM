"""Counts-only ``load-report.json`` and ids-and-codes-only ``exceptions.jsonl``."""

import json
import os

from . import TOOL_VERSION
from .engine import SnapshotContext
from .errors import LoadError
from .mapping import check_shape


def _shaped(loader, obj):
    """Current rows the load could map (``value_shape`` rows are exceptions, not counted)."""
    out = []
    for r in loader.s.current(obj):
        try:
            check_shape(obj, r, loader.mapping)
        except LoadError:
            continue
        out.append(r)
    return out


def _open_new(path):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.fchmod(fd, 0o600)
    return os.fdopen(fd, "w", encoding="utf-8")


def relationships(loader):
    """Relationship totals: the snapshot's own resolvable references against EspoCRM now."""
    s, m = loader.s, loader.mapper
    snap = SnapshotContext(s, set(loader.index["User"]))
    cur = {o: _shaped(loader, o) for o in ("Account", "Contact", "OpportunityContactRole", "Task",
                                                 "Event", "EmailMessage")}
    acc_ids = {r["Id"] for r in cur["Account"]}
    expected = {
        "account_parents": sum(1 for r in cur["Account"] if r.get("ParentId") in acc_ids),
        "contact_accounts": sum(1 for r in cur["Contact"] if r.get("AccountId") in acc_ids),
        "enquiry_contacts": len({(r.get("OpportunityId"), r.get("ContactId")) for r in cur["OpportunityContactRole"]
                                 if snap.record_id("Opportunity", r.get("OpportunityId"))
                                 and snap.record_id("Contact", r.get("ContactId"))}),
    }
    emailed = {r.get("ActivityId") for r in cur["EmailMessage"] if r.get("ActivityId")}
    task_by_id = {r["Id"]: r for r in cur["Task"]}
    parents = 0
    for r in cur["Task"]:
        if m.task_entity(r) == "Email" and r["Id"] in emailed:
            continue
        parents += m._parent(r, snap, [])[1] is not None
    for r in cur["Event"]:
        parents += m._parent(r, snap, [])[1] is not None
    for r in cur["EmailMessage"]:
        parents += m.email_message(r, [], task_by_id, snap)[0]["parentId"] is not None
    expected["activity_parents"] = parents

    # EspoCRM side: a fresh paged read (reads only), restricted to snapshot-current sfIds.
    loader.build_index()
    idx = loader.index
    keys = lambda o: {r["Id"] for r in cur[o]}  # noqa: E731
    acc, con = keys("Account"), {r["Id"] for r in s.current("Contact")}
    opp = {r["Id"] for r in s.current("Opportunity")}
    actual = {
        "account_parents": sum(1 for k, r in idx["Account"].items() if k in acc and r.get("parentId")),
        "contact_accounts": sum(1 for k, r in idx["Contact"].items() if k in con and r.get("accountId")),
        "enquiry_contacts": sum(len(r.get("contactsIds") or []) for k, r in idx["Opportunity"].items() if k in opp),
    }
    act_keys = keys("Task") | keys("Event") | keys("EmailMessage")
    actual["activity_parents"] = sum(1 for e in ("Task", "Call", "Meeting", "Email")
                                     for k, r in idx[e].items() if k in act_keys and r.get("parentId"))
    return {name: {"snapshot": expected[name], "espocrm": actual[name]} for name in expected}


def build_report(loader, status, accept_drift_used):
    exc_by_reason = {}
    for (_obj, _sf, reason) in loader.exceptions:
        exc_by_reason[reason] = exc_by_reason.get(reason, 0) + 1
    return {
        "tool": TOOL_VERSION,
        "mappingVersion": loader.mapping["mappingVersion"],
        "contractVersion": loader.mapping["contractVersion"],
        "snapshotStatus": status,
        "acceptedDrift": bool(accept_drift_used),
        "synthetic": loader.s.synthetic,
        "snapshotManifestSha": loader.s.manifest_sha256,
        "reconciliation": loader.s.has_reconciliation,
        "objects": loader.objects,
        "existingNotCurrentInSnapshot": loader.flagged,
        "exceptions": {"total": len(loader.exceptions), "byReason": dict(sorted(exc_by_reason.items()))},
        "relationships": relationships(loader),
        "requests": {"writes": loader.client.writes, "reads": loader.client.reads},
        "deletes": 0,
        # Whether the previous run's phone-refusals.json was given (--phone-refusals); without it
        # every server-refused phone is probed again and the re-run is not write-free.
        "phoneRefusals": {"supplied": bool(getattr(loader, "refusals_supplied", False)),
                          "remembered": len(loader.refused_before), "refusedThisRun": len(loader.refused)},
    }


def write_outputs(outdir, report, exceptions):
    with _open_new(os.path.join(outdir, "load-report.json")) as fh:
        fh.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    with _open_new(os.path.join(outdir, "exceptions.jsonl")) as fh:
        for (obj, sf_id, reason) in exceptions:
            fh.write(json.dumps({"object": obj, "sfId": sf_id, "reason": reason}, sort_keys=True) + "\n")
