"""Reconciled baseline (``extract``).

1. The metadata gate runs first; SOQL is built only from the effective contract.
2. Pass 0: ``T_start`` from the server ``Date`` header, then a full ``queryAll`` per object,
   ordered by Id, paging only through ``nextRecordsUrl``.
3. Catch-up passes 1..N: ``SystemModstamp >= W - overlap`` (W = start of the previous pass),
   merged by Id so the latest ``SystemModstamp`` wins. Stop early on a quiet pass.
4. Verification: ``COUNT()`` through ``query`` and ``queryAll``, an id-only ``queryAll``, and
   (for ``replicateable`` objects) the deleted-records log.
5. Status per object and overall: RECONCILED, RECONCILED_WITH_DRIFT or INCOMPLETE.

Watermarks never come from the local clock. The overlap is an assumption, not a guarantee.
"""

import datetime as _dt
import json
import re
import time
from dataclasses import dataclass

from . import TOOL_VERSION
from .contract import effective_to_json, id_only_fields, soql_count, soql_datetime, soql_id_only, soql_select
from .errors import GateFailed, MigrateError, ProtocolError
from .metadata import run_gate

RECONCILED = "RECONCILED"
DRIFT = "RECONCILED_WITH_DRIFT"
INCOMPLETE = "INCOMPLETE"
_ID_RE = re.compile(r"^[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?$")
_SF_DT_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:?\d{2})$")


@dataclass
class ExtractOptions:
    passes: int = 3
    overlap: _dt.timedelta = _dt.timedelta(minutes=15)
    deletion_log_days: int = 29

    def validate(self):
        if not isinstance(self.passes, int) or not 1 <= self.passes <= 20:
            raise ProtocolError("options", detail="passes must be 1..20")
        if not _dt.timedelta(0) <= self.overlap <= _dt.timedelta(hours=24):
            raise ProtocolError("options", detail="overlap must be 0..24h")
        if not isinstance(self.deletion_log_days, int) or not 1 <= self.deletion_log_days <= 29:
            raise ProtocolError("options", detail="deletion log days must be 1..29")


def parse_sf_datetime(value):
    if not isinstance(value, str):
        return None
    m = _SF_DT_RE.match(value)
    if not m:
        return None
    y, mo, d, h, mi, s, frac, tz = m.groups()
    micro = int((frac or "0").ljust(6, "0"))
    if tz == "Z":
        offset = _dt.timedelta(0)
    else:
        sign = 1 if tz[0] == "+" else -1
        digits = tz[1:].replace(":", "")
        offset = sign * _dt.timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
    try:
        return _dt.datetime(int(y), int(mo), int(d), int(h), int(mi), int(s), micro,
                            tzinfo=_dt.timezone(offset)).astimezone(_dt.timezone.utc)
    except ValueError:
        return None


def iso(value):
    return soql_datetime(value) if value is not None else None


def _row_key(row, change_key):
    rid = row.get("Id")
    if not isinstance(rid, str) or not _ID_RE.match(rid):
        raise ProtocolError("record_shape", detail="invalid Id")
    stamp = parse_sf_datetime(row.get(change_key))
    if stamp is None:
        raise ProtocolError("record_shape", detail="invalid change key")
    return rid, stamp


def _clean(row, fields):
    return {name: row.get(name) for name in fields}


def merge_rows(baseline, rows, fields, change_key):
    """Merge rows into ``baseline`` (id -> (stamp, row)); latest change key wins."""
    inserted = updated = unchanged = 0
    for raw in rows:
        if not isinstance(raw, dict):
            raise ProtocolError("record_shape", detail="record is not an object")
        rid, stamp = _row_key(raw, change_key)
        current = baseline.get(rid)
        if current is None:
            baseline[rid] = (stamp, _clean(raw, fields))
            inserted += 1
        elif stamp > current[0]:
            baseline[rid] = (stamp, _clean(raw, fields))
            updated += 1
        else:
            unchanged += 1
    return inserted, updated, unchanged


def _query_visible(row, spec, effective_fields):
    if spec.soft_delete and row.get("IsDeleted") is True:
        return False
    if "IsArchived" in effective_fields and row.get("IsArchived") is True:
        return False
    return True


def assess_object(spec, effective_fields, baseline, verify_ids, count_query, count_all,
                  deleted_ids, last_pass_start, overlap, last_pass_changed):
    """Pure verification of one object. Returns (status, details, explained_deleted_ids)."""
    b_ids = set(baseline)
    v_ids = set(verify_ids)
    missing = b_ids - v_ids
    explained = missing & set(deleted_ids)
    unexplained_missing = len(missing - explained)
    threshold = last_pass_start - overlap
    residual_new = unexplained_new = 0
    for rid in v_ids - b_ids:
        stamp, _ = verify_ids[rid]
        if stamp >= threshold:
            residual_new += 1
        else:
            unexplained_new += 1
    residual_changed = regressed = inconsistent = 0
    for rid in b_ids & v_ids:
        v_stamp, v_del = verify_ids[rid]
        b_stamp, b_row = baseline[rid]
        if v_stamp > b_stamp:
            residual_changed += 1
        elif v_stamp < b_stamp:
            regressed += 1
        elif spec.soft_delete and v_del != b_row.get("IsDeleted"):
            inconsistent += 1
    final_ids = b_ids - explained
    residual = residual_new + residual_changed
    count_all_matches_ids = count_all == len(v_ids)
    count_all_matches = None
    count_query_matches = None
    archive_known = not (spec.field("IsArchived") is not None and "IsArchived" not in effective_fields)
    if residual == 0:
        count_all_matches = count_all == len(final_ids)
        if archive_known:
            visible = sum(1 for rid in final_ids if _query_visible(baseline[rid][1], spec, effective_fields))
            count_query_matches = count_query == visible
    reasons = []
    if unexplained_missing:
        reasons.append("unexplained_missing")
    if unexplained_new:
        reasons.append("unexplained_new")
    if regressed:
        reasons.append("change_key_regressed")
    if inconsistent:
        reasons.append("state_mismatch")
    if not count_all_matches_ids:
        reasons.append("count_vs_id_set_mismatch")
    if count_all_matches is False:
        reasons.append("queryAll_count_mismatch")
    if count_query_matches is False:
        reasons.append("query_count_mismatch")
    if reasons:
        status = INCOMPLETE
    elif residual or last_pass_changed:
        status = DRIFT
    else:
        status = RECONCILED
    details = {
        "status": status,
        "reasons": reasons,
        "verification": {
            "count_query": count_query,
            "count_queryAll": count_all,
            "id_set": len(v_ids),
            "count_queryAll_matches_id_set": count_all_matches_ids,
            "count_queryAll_matches_baseline": count_all_matches,
            "count_query_matches_baseline": count_query_matches if archive_known else "unavailable",
        },
        "deleted_during_run": len(explained),
        "unexplained_missing": unexplained_missing,
        "unexplained_new": unexplained_new,
        "residual_drift": {"new": residual_new, "changed": residual_changed},
        "change_key_regressed": regressed,
        "state_mismatch": inconsistent,
    }
    return status, details, explained


def overall_status(statuses, quiet):
    if any(s == INCOMPLETE for s in statuses):
        return INCOMPLETE
    if not quiet or any(s == DRIFT for s in statuses):
        return DRIFT
    return RECONCILED


def run_extract(client, contract, out, log, options=None):
    options = options or ExtractOptions()
    options.validate()
    t0 = time.monotonic()
    manifest = {
        "tool": TOOL_VERSION,
        "mode": "extract",
        "api_version": client.api_version,
        "origin_kind": "sandbox" if ".sandbox." in client.origin else "production",
        "contract": {"version": contract.version, "sha256": contract.sha256, "effective": None},
        "passes_max": options.passes,
        "overlap_seconds": int(options.overlap.total_seconds()),
        "overlap_note": "The overlap is an assumption, not a guarantee.",
        "status": INCOMPLETE,
        "error": None,
    }
    try:
        _extract(client, contract, out, log, options, manifest)
    except MigrateError as exc:
        manifest["status"] = INCOMPLETE
        manifest["error"] = {"code": exc.code, "status": exc.status, "sf_error": exc.sf_error}
        manifest["api_requests"] = client.request_count
        manifest["duration_seconds"] = round(time.monotonic() - t0, 3)
        out.finalize(manifest)
        log.event("extract_result", status=INCOMPLETE, code=exc.code)
        raise
    except Exception as exc:  # never print a value; record the class only
        manifest["status"] = INCOMPLETE
        manifest["error"] = {"code": "internal_error", "class": type(exc).__name__}
        out.finalize(manifest)
        log.event("extract_result", status=INCOMPLETE, code="internal_error")
        raise MigrateError("internal_error", detail=type(exc).__name__) from None
    manifest["api_requests"] = client.request_count
    manifest["duration_seconds"] = round(time.monotonic() - t0, 3)
    manifest = out.finalize(manifest)
    log.event("extract_result", status=manifest["status"], api_requests=client.request_count)
    return manifest


def _extract(client, contract, out, log, options, manifest):
    gate = run_gate(client, contract, log)
    out.write_json("contract-check.json", gate.report)
    out.write_json("describe.json", gate.describe_summary)
    if not gate.ok:
        manifest["gate"] = "failed"
        raise GateFailed(detail="no data query issued")
    manifest["gate"] = "passed"
    effective = {e.name: e for e in gate.effective}
    manifest["contract"]["effective"] = effective_to_json(gate.effective)
    specs = [contract.object(name) for name in contract.object_names]

    t_start, remaining = client.server_time()
    manifest["t_start"] = iso(t_start)
    manifest["api_remaining_at_start"] = remaining
    baselines = {spec.name: {} for spec in specs}
    passes = []

    # Pass 0
    p0 = {"pass": 0, "kind": "base", "start": iso(t_start), "since": None, "objects": {}}
    for spec in specs:
        fields = effective[spec.name].fields
        q = soql_select(spec, fields)
        started = time.monotonic()
        rows = pages = 0
        for page in client.iter_pages(q, all_rows=True):
            pages += 1
            rows += len(page)
            merge_rows(baselines[spec.name], page, fields, spec.change_key)
        p0["objects"][spec.name] = {"soql": q, "rows": rows, "pages": pages,
                                    "seconds": round(time.monotonic() - started, 3)}
        log.event("pass_object", pass_index=0, object=spec.name, rows=rows, pages=pages)
    passes.append(p0)

    prev_start = t_start
    quiet = False
    for k in range(1, options.passes + 1):
        pk, _ = client.server_time()
        since = prev_start - options.overlap
        rec = {"pass": k, "kind": "catch-up", "start": iso(pk), "since": iso(since), "objects": {}, "changed": 0}
        for spec in specs:
            fields = effective[spec.name].fields
            q = soql_select(spec, fields, since=since)
            started = time.monotonic()
            ins = upd = same = pages = 0
            for page in client.iter_pages(q, all_rows=True):
                pages += 1
                i, u, s = merge_rows(baselines[spec.name], page, fields, spec.change_key)
                ins, upd, same = ins + i, upd + u, same + s
            rec["objects"][spec.name] = {"soql": q, "rows": ins + upd + same, "pages": pages,
                                         "inserted": ins, "updated": upd, "unchanged": same,
                                         "changed": ins + upd,
                                         "seconds": round(time.monotonic() - started, 3)}
            rec["changed"] += ins + upd
            log.event("pass_object", pass_index=k, object=spec.name, inserted=ins, updated=upd, unchanged=same)
        passes.append(rec)
        prev_start = pk
        if rec["changed"] == 0:
            quiet = True
            break
    manifest["passes"] = passes
    manifest["quiet"] = quiet
    last = passes[-1]
    last_start = parse_sf_datetime(last["start"])

    # Verification
    pv, remaining = client.server_time()
    verification = {"start": iso(pv), "objects": {}}
    describe = gate.describe_summary
    deletion_log = {}
    objects = {}
    statuses = []
    for spec in specs:
        fields = effective[spec.name].fields
        q_count = soql_count(spec)
        count_query = client.count(q_count, all_rows=False)
        count_all = client.count(q_count, all_rows=True)
        q_ids = soql_id_only(spec)
        verify_ids = {}
        for page in client.iter_pages(q_ids, all_rows=True):
            for raw in page:
                if not isinstance(raw, dict):
                    raise ProtocolError("record_shape")
                rid, stamp = _row_key(raw, spec.change_key)
                verify_ids[rid] = (stamp, raw.get("IsDeleted") if spec.soft_delete else None)
        verification["objects"][spec.name] = {"soql_count": q_count, "soql_ids": q_ids,
                                              "id_fields": list(id_only_fields(spec))}
        deleted_ids = {}
        if describe[spec.name]["flags"].get("replicateable") is True:
            start = (pv - _dt.timedelta(days=options.deletion_log_days)).replace(second=0, microsecond=0)
            doc = client.deleted(spec.name, soql_datetime(start), soql_datetime(pv))
            for item in doc["deletedRecords"]:
                rid = item.get("id") if isinstance(item, dict) else None
                if not isinstance(rid, str) or not _ID_RE.match(rid):
                    raise ProtocolError("deleted_shape", detail=spec.name)
                deleted_ids[rid] = item.get("deletedDate") if isinstance(item.get("deletedDate"), str) else None
            deletion_log[spec.name] = {
                "start": soql_datetime(start), "end": soql_datetime(pv), "records": len(deleted_ids),
                "earliestDateAvailable": doc.get("earliestDateAvailable"),
                "latestDateCovered": doc.get("latestDateCovered"),
            }
        else:
            deletion_log[spec.name] = "unavailable"
        last_changed = last["objects"][spec.name].get("changed", 0) if last["kind"] == "catch-up" else 0
        status, details, explained = assess_object(
            spec, fields, baselines[spec.name], verify_ids, count_query, count_all, deleted_ids,
            last_start, options.overlap, last_changed)
        statuses.append(status)
        final = {rid: v for rid, v in baselines[spec.name].items() if rid not in explained}
        rows = [final[rid][1] for rid in sorted(final)]
        out.write_jsonl_gz(f"objects/{spec.name}.jsonl.gz", rows)
        if deletion_log[spec.name] != "unavailable":
            out.write_jsonl_gz(f"deleted/{spec.name}.jsonl.gz",
                               ({"Id": rid, "deletedDate": deleted_ids[rid]} for rid in sorted(deleted_ids)))
        drift = [p["objects"][spec.name]["changed"] for p in passes if p["kind"] == "catch-up"]
        details.update({
            "rows": len(rows),
            "current": sum(1 for r in rows if not (spec.soft_delete and r.get("IsDeleted") is True)),
            "soft_deleted": sum(1 for r in rows if spec.soft_delete and r.get("IsDeleted") is True),
            "archived": (sum(1 for r in rows if r.get("IsArchived") is True) if "IsArchived" in fields
                         else ("unavailable" if spec.field("IsArchived") else "not_applicable")),
            "drift_per_pass": drift,
        })
        objects[spec.name] = details
        log.event("verify_object", object=spec.name, status=status, rows=len(rows), count_query=count_query,
                  count_queryall=count_all, deleted_during_run=details["deleted_during_run"],
                  unexplained_missing=details["unexplained_missing"], unexplained_new=details["unexplained_new"],
                  residual_new=details["residual_drift"]["new"],
                  residual_changed=details["residual_drift"]["changed"])
    manifest["verification"] = verification
    manifest["deletion_log"] = deletion_log
    manifest["objects"] = objects
    manifest["api_remaining_at_end"] = remaining
    manifest["status"] = overall_status(statuses, quiet)
    out.write_text("passlog.jsonl", "".join(
        json.dumps({"pass": p["pass"], "kind": p["kind"], "start": p["start"], "since": p["since"],
                                  "objects": {n: {k: v for k, v in o.items() if k != "soql"}
                                              for n, o in p["objects"].items()}},
                                 sort_keys=True) + "\n"
        for p in passes))
