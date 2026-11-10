"""Counts-only reconciliation of one snapshot, optionally against the previous one.

The output (``reconciliation.json`` and ``reconciliation.md``) holds counts, rates,
statuses, and contract object and field names. It never holds an id or a record value.
An unexplained absence is never counted as deleted. Rows of a ``visibleVia`` object (contract
v4) whose listed parent is soft-deleted in the same snapshot are ``parent_soft_deleted``, not
``current``.
"""

import json
import os

from . import TOOL_VERSION
from .errors import SnapshotError
from .manifest import read_jsonl_gz, verify_tree

GROUP_PREFIX = "00G"

# (object, field, fixed targets or None = resolve by key prefix against describe referenceTo)
RELATIONS = (
    ("Account", "ParentId", ("Account",)),
    ("Contact", "AccountId", ("Account",)),
    ("Opportunity", "AccountId", ("Account",)),
    ("OpportunityContactRole", "OpportunityId", ("Opportunity",)),
    ("OpportunityContactRole", "ContactId", ("Contact",)),
    ("Task", "WhatId", None),
    ("Task", "WhoId", None),
    ("Task", "AccountId", None),
    ("Event", "WhatId", None),
    ("Event", "WhoId", None),
    ("Event", "AccountId", None),
    ("EmailMessage", "ActivityId", ("Task",)),
    ("EmailMessageRelation", "EmailMessageId", ("EmailMessage",)),
    ("EmailMessageRelation", "RelationId", ("Contact", "User")),
)


class Snapshot:
    def __init__(self, path, manifest, describe, rows, deleted):
        self.path = path
        self.manifest = manifest
        self.describe = describe
        self.rows = rows          # object -> list of rows (duplicates kept)
        self.deleted = deleted    # object -> set of ids, or None when unavailable

    @property
    def effective(self):
        return self.manifest["contract"]["effective"]

    def by_id(self, obj):
        return {r.get("Id"): r for r in self.rows.get(obj, [])}

    def prefix_map(self):
        return {d.get("keyPrefix"): name for name, d in self.describe.items() if d.get("keyPrefix")}


def load_snapshot(path):
    manifest, problems = verify_tree(path)
    if problems:
        raise SnapshotError("checksum_mismatch", detail=",".join(sorted(set(problems))))
    if manifest.get("mode") != "extract":
        raise SnapshotError("not_a_snapshot")
    effective = (manifest.get("contract") or {}).get("effective")
    if not isinstance(effective, dict):
        raise SnapshotError("snapshot_without_data", detail="gate failed or run aborted")
    try:
        with open(os.path.join(path, "describe.json"), "rb") as fh:
            describe = json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        raise SnapshotError("describe_unreadable") from None
    rows, deleted = {}, {}
    files = manifest.get("files", {})
    for obj in effective:
        rel = f"objects/{obj}.jsonl.gz"
        if rel not in files:
            raise SnapshotError("object_file_missing", detail=obj)
        try:
            rows[obj] = list(read_jsonl_gz(os.path.join(path, "objects", f"{obj}.jsonl.gz")))
            drel = f"deleted/{obj}.jsonl.gz"
            deleted[obj] = ({r.get("Id") for r in read_jsonl_gz(os.path.join(path, "deleted", f"{obj}.jsonl.gz"))}
                            if drel in files else None)
        except (OSError, ValueError, EOFError):
            raise SnapshotError("object_file_unreadable", detail=obj) from None
    return Snapshot(path, manifest, describe, rows, deleted)


def _filled(value):
    return value is not None and value != ""


def _relation(snapshot, obj, field, targets, prefixes):
    eff = snapshot.effective.get(obj)
    if eff is None or field not in eff["fields"]:
        return "unavailable"
    if targets is None:
        targets = tuple(snapshot.describe.get(obj, {}).get("fields", {}).get(field, {}).get("referenceTo") or ())
    target_ids = {name: set(snapshot.by_id(name)) for name in targets if name in snapshot.rows}
    res = {"checked": 0, "null": 0, "ok": 0, "orphans": 0, "not_extracted": 0, "type_not_allowed": 0}
    if obj == "EmailMessageRelation" and field == "RelationId":
        res["unmatched_address"] = 0
    for row in snapshot.by_id(obj).values():
        value = row.get(field)
        res["checked"] += 1
        if not _filled(value):
            if "unmatched_address" in res and _filled(row.get("RelationAddress")):
                res["unmatched_address"] += 1
            else:
                res["null"] += 1
            continue
        target = prefixes.get(str(value)[:3])
        if target is None:
            res["not_extracted"] += 1
        elif target not in targets:
            res["type_not_allowed"] += 1
        elif target not in target_ids:
            res["not_extracted"] += 1
        elif value in target_ids[target]:
            res["ok"] += 1
        else:
            res["orphans"] += 1
    return res


def _owners(snapshot, obj, users, user_prefix):
    refs = snapshot.describe.get(obj, {}).get("fields", {}).get("OwnerId", {}).get("referenceTo") or []
    group_allowed = "Group" in refs
    out = {"active_user": 0, "inactive_user": 0, "queue_or_group": 0, "unresolved": 0}
    for row in snapshot.by_id(obj).values():
        owner = row.get("OwnerId")
        if isinstance(owner, str) and user_prefix and owner.startswith(user_prefix) and owner in users:
            out["active_user" if users[owner].get("IsActive") is True else "inactive_user"] += 1
        elif isinstance(owner, str) and owner.startswith(GROUP_PREFIX) and group_allowed:
            out["queue_or_group"] += 1
        else:
            out["unresolved"] += 1
    out["orphans"] = out["unresolved"]
    return out


def _parent_hidden(snapshot, obj, spec):
    """Ids of ``obj`` rows hidden from ``query`` through a soft-deleted parent (``visibleVia``)."""
    via = spec.get("visibleVia") or []
    parents = {}
    for entry in via:
        name = entry["object"]
        if name not in parents:
            parents[name] = {i for i, r in snapshot.by_id(name).items() if r.get("IsDeleted") is True}
    return {i for i, r in snapshot.by_id(obj).items()
            if any(r.get(e["field"]) in parents[e["object"]] for e in via)}


def _deletion_classes(current, previous, obj, spec):
    rows = current.by_id(obj)
    soft = spec["softDelete"]
    has_via = bool(spec.get("visibleVia"))
    hidden = _parent_hidden(current, obj, spec) if has_via else set()
    master_available = "MasterRecordId" in spec["fields"]
    evidence = current.deleted.get(obj)
    res = {}
    if soft:
        cur = {i for i, r in rows.items() if r.get("IsDeleted") is not True}
        deleted_rows = {i: r for i, r in rows.items() if r.get("IsDeleted") is True}
        merged = {i for i, r in deleted_rows.items() if master_available and _filled(r.get("MasterRecordId"))}
        soft_only = set(deleted_rows) - merged
        res["current"] = len(cur)
        res["soft_deleted_available"] = len(soft_only)
        res["merged"] = len(merged) if master_available else "unavailable"
    else:
        cur, soft_only, merged = set(rows) - hidden, set(), set()
        res["current"] = len(cur)
        res["soft_deleted_available"] = "not_applicable"
        res["merged"] = "not_applicable"
    res["parent_soft_deleted"] = len(hidden) if has_via else "not_applicable"
    res["deletion_evidence"] = len(evidence) if evidence is not None else "unavailable"
    if previous is None:
        res["absent_since_previous_explained"] = "no_previous_snapshot"
        res["absent_since_previous_unexplained"] = "no_previous_snapshot"
        return res
    prev_rows = previous.by_id(obj)
    if soft:
        prev_current = {i for i, r in prev_rows.items() if r.get("IsDeleted") is not True}
    else:
        prev_spec = previous.effective.get(obj) or {}
        prev_hidden = _parent_hidden(previous, obj, prev_spec) if prev_spec.get("visibleVia") else set()
        prev_current = set(prev_rows) - prev_hidden
    absent = prev_current - cur
    by = {"soft_deleted_available": 0, "merged": 0, "deletion_evidence": 0}
    if has_via:
        by["parent_soft_deleted"] = 0
    unexplained = 0
    for rid in absent:
        if rid in hidden:
            by["parent_soft_deleted"] += 1
        elif rid in merged:
            by["merged"] += 1
        elif rid in soft_only:
            by["soft_deleted_available"] += 1
        elif evidence is not None and rid in evidence:
            by["deletion_evidence"] += 1
        else:
            unexplained += 1
    res["absent_since_previous_explained"] = sum(by.values())
    res["absent_since_previous_explained_by"] = by
    res["absent_since_previous_unexplained"] = unexplained
    return res


def reconcile(current, previous=None):
    man = current.manifest
    report = {
        "tool": TOOL_VERSION,
        "report": "crm-migrate reconciliation (counts only)",
        "snapshot": {
            "status": man.get("status"),
            "t_start": man.get("t_start"),
            "contract_version": man["contract"].get("version"),
            "contract_sha256": man["contract"].get("sha256"),
            "passes": len(man.get("passes", [])),
            "quiet": man.get("quiet"),
            "overlap_seconds": man.get("overlap_seconds"),
        },
        "previous": None if previous is None else {
            "status": previous.manifest.get("status"), "t_start": previous.manifest.get("t_start")},
        "objects": {},
        "relations": {},
        "notes": [
            "queryAll cannot return permanently deleted records (emptied from the Recycle Bin, past retention, "
            "or hard-deleted).",
            "absent_since_previous_unexplained is NOT deleted: downstream keeps such records, flagged "
            "sfAbsentUnverified.",
        ],
    }
    prefixes = current.prefix_map()
    users = current.by_id("User") if "User" in current.rows else {}
    user_prefix = current.describe.get("User", {}).get("keyPrefix")
    for obj, spec in current.effective.items():
        all_rows = current.rows[obj]
        unique = current.by_id(obj)
        mobj = man.get("objects", {}).get(obj, {})
        ver = mobj.get("verification", {})
        entry = {
            "status": mobj.get("status"),
            "extracted": len(unique),
            "verification": {"query": ver.get("count_query"), "queryAll": ver.get("count_queryAll")},
            "extracted_matches_queryAll": ver.get("count_queryAll") == len(unique),
            "duplicate_ids": len(all_rows) - len(unique),
            "deletion_classes": _deletion_classes(current, previous, obj, spec),
            "fill_rates": {},
            "drift": {"per_pass": mobj.get("drift_per_pass"), "residual": mobj.get("residual_drift"),
                      "deleted_during_run": mobj.get("deleted_during_run")},
        }
        if "hidden_via" in mobj:
            entry["verification"]["hidden_via"] = mobj["hidden_via"]
        n = len(unique)
        for fname in spec["fields"]:
            filled = sum(1 for r in unique.values() if _filled(r.get(fname)))
            entry["fill_rates"][fname] = {"filled": filled, "rows": n, "rate": round(filled / n, 4) if n else None}
        for fname in spec["unavailable"]:
            entry["fill_rates"][fname] = "unavailable"
        if spec["ownerCheck"]:
            entry["owners"] = _owners(current, obj, users, user_prefix)
        report["objects"][obj] = entry
    for obj, field, targets in RELATIONS:
        if obj in current.rows:
            report["relations"][f"{obj}.{field}"] = _relation(current, obj, field, targets, prefixes)
    return report


def render_markdown(report):
    lines = ["# crm-migrate reconciliation (counts only)", ""]
    snap = report["snapshot"]
    lines += [f"- Snapshot status: **{snap['status']}**", f"- T_start: {snap['t_start']}",
              f"- Contract version {snap['contract_version']}, sha256 `{snap['contract_sha256']}`",
              f"- Passes: {snap['passes']}, quiet: {snap['quiet']}, overlap: {snap['overlap_seconds']} s"]
    if report["previous"]:
        lines.append(f"- Previous snapshot: {report['previous']['status']} at {report['previous']['t_start']}")
    lines += ["", "## Objects", "",
              "| Object | Status | Extracted | query | queryAll | Duplicates | Current | Soft-deleted | Merged | "
              "Parent soft-deleted | Deletion evidence | Absent explained | Absent unexplained |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for obj, e in report["objects"].items():
        d = e["deletion_classes"]
        lines.append(f"| {obj} | {e['status']} | {e['extracted']} | {e['verification']['query']} | "
                     f"{e['verification']['queryAll']} | {e['duplicate_ids']} | {d['current']} | "
                     f"{d['soft_deleted_available']} | {d['merged']} | {d['parent_soft_deleted']} | "
                     f"{d['deletion_evidence']} | "
                     f"{d['absent_since_previous_explained']} | {d['absent_since_previous_unexplained']} |")
    lines += ["", "## Owners (ownerCheck objects only)", "",
              "| Object | Active user | Inactive user | Queue or group | Unresolved (orphans) |",
              "|---|---:|---:|---:|---:|"]
    for obj, e in report["objects"].items():
        if "owners" in e:
            o = e["owners"]
            lines.append(f"| {obj} | {o['active_user']} | {o['inactive_user']} | {o['queue_or_group']} | "
                         f"{o['unresolved']} |")
    lines += ["", "## Relationship integrity", "",
              "| Relation | Checked | Null | OK | Orphans | Not extracted | Type not allowed |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for rel, r in report["relations"].items():
        if r == "unavailable":
            lines.append(f"| {rel} | unavailable | | | | | |")
            continue
        extra = f" (unmatched addresses: {r['unmatched_address']})" if "unmatched_address" in r else ""
        lines.append(f"| {rel}{extra} | {r['checked']} | {r['null']} | {r['ok']} | {r['orphans']} | "
                     f"{r['not_extracted']} | {r['type_not_allowed']} |")
    lines += ["", "## Notes", ""] + [f"- {n}" for n in report["notes"]] + [""]
    return "\n".join(lines)


def run_reconcile(snapshot_path, previous_path, out, log):
    current = load_snapshot(snapshot_path)
    previous = load_snapshot(previous_path) if previous_path else None
    report = reconcile(current, previous)
    out.write_json("reconciliation.json", report)
    out.write_text("reconciliation.md", render_markdown(report))
    out.finalize({"tool": TOOL_VERSION, "mode": "reconcile", "snapshot_status": report["snapshot"]["status"],
                  "previous": previous is not None})
    for obj, e in report["objects"].items():
        d = e["deletion_classes"]
        log.event("reconcile_object", object=obj, extracted=e["extracted"], duplicates=e["duplicate_ids"],
                  current=d["current"],
                  absent_unexplained=d["absent_since_previous_unexplained"]
                  if isinstance(d["absent_since_previous_unexplained"], int) else None)
    log.event("reconcile_result", status=report["snapshot"]["status"], previous=previous is not None)
    return report
