"""Metadata gate (``contract-check``): describe only, no records.

Per contract object it requires ``queryable`` and ``retrieveable``; every required
contract field present with the expected type and ``referenceTo``; and ``createable``,
``updateable`` and ``deletable`` all false (unless the contract lists an Architect
waiver). Optional fields that are missing are excluded and reported ``unavailable``.
The result is a counts-and-flags report plus the effective contract.
"""

from dataclasses import dataclass

from .contract import WAIVABLE_FLAGS, EffectiveObject
from .errors import MigrateError

REQUIRED_TRUE = ("queryable", "retrieveable")


@dataclass
class GateResult:
    ok: bool
    report: dict
    effective: tuple       # EffectiveObject per contract object (only meaningful if ok)
    describe_summary: dict


def _field_map(describe):
    out = {}
    for fld in describe.get("fields") or []:
        if isinstance(fld, dict) and isinstance(fld.get("name"), str):
            out[fld["name"]] = fld
    return out


def _reference_ok(spec_field, described):
    actual = described.get("referenceTo") or []
    if not isinstance(actual, list):
        return False
    expected = set(spec_field.reference_to)
    if spec_field.reference_match == "superset":
        return expected.issubset(set(actual))
    return expected == set(actual)


def evaluate_gate(contract, describes):
    """Pure gate decision. ``describes`` maps object name to describe JSON (or None on error)."""
    objects_report = {}
    effective = []
    summary = {}
    findings = []
    ok = True
    waivers = set(contract.waivers)
    for spec in contract.objects:
        rep = {
            "describe": "ok", "queryable": None, "retrieveable": None, "replicateable": None,
            "createable": None, "updateable": None, "deletable": None, "waived": [],
            "missing_required": [], "type_mismatch": [], "reference_mismatch": [],
            "unavailable_optional": [], "fields_available": 0, "fields_in_contract": len(spec.fields),
            "ok": True,
        }
        objects_report[spec.name] = rep
        doc = describes.get(spec.name)
        if not isinstance(doc, dict) or doc.get("name") != spec.name:
            rep["describe"] = "failed"
            rep["ok"] = False
            ok = False
            continue
        for flag in REQUIRED_TRUE + ("replicateable",) + WAIVABLE_FLAGS:
            value = doc.get(flag)
            rep[flag] = value if isinstance(value, bool) else None
        for flag in REQUIRED_TRUE:
            if rep[flag] is not True:
                rep["ok"] = False
        for flag in WAIVABLE_FLAGS:
            if rep[flag] is not False:
                if rep[flag] is True and (spec.name, flag) in waivers:
                    rep["waived"].append(flag)
                    continue
                rep["ok"] = False
                if spec.name == "User" and flag == "updateable" and rep[flag] is True:
                    findings.append("User updateable: L1 finding for Architect decision, not waived")
        fields = _field_map(doc)
        available = []
        for fspec in spec.fields:
            described = fields.get(fspec.name)
            if described is None:
                if fspec.required:
                    rep["missing_required"].append(fspec.name)
                else:
                    rep["unavailable_optional"].append(fspec.name)
                continue
            if described.get("type") != fspec.type:
                rep["type_mismatch"].append(fspec.name)
                continue
            if fspec.type == "reference" and not _reference_ok(fspec, described):
                rep["reference_mismatch"].append(fspec.name)
                continue
            available.append(fspec.name)
        if rep["missing_required"] or rep["type_mismatch"] or rep["reference_mismatch"]:
            rep["ok"] = False
        rep["fields_available"] = len(available)
        ok = ok and rep["ok"]
        effective.append(EffectiveObject(
            spec, tuple(available), tuple(f.name for f in spec.fields if f.name not in available)))
        summary[spec.name] = {
            "keyPrefix": doc.get("keyPrefix") if isinstance(doc.get("keyPrefix"), str) else None,
            "flags": {k: rep[k] for k in REQUIRED_TRUE + ("replicateable",) + WAIVABLE_FLAGS},
            "fields": {
                name: {
                    "type": fields[name].get("type"),
                    "referenceTo": list(fields[name].get("referenceTo") or []),
                    "picklistValues": [
                        {"value": p.get("value"), "active": p.get("active")}
                        for p in (fields[name].get("picklistValues") or []) if isinstance(p, dict)
                    ],
                }
                for name in available
            },
        }
    report = {
        "ok": ok,
        "objects_checked": len(contract.objects),
        "objects_failed": sum(1 for r in objects_report.values() if not r["ok"]),
        "contract_version": contract.version,
        "contract_sha256": contract.sha256,
        "findings": findings,
        "objects": objects_report,
    }
    return GateResult(ok, report, tuple(effective), summary)


def run_gate(client, contract, log=None):
    describes = {}
    for spec in contract.objects:
        try:
            describes[spec.name] = client.describe(spec.name)
        except MigrateError as exc:
            describes[spec.name] = None
            if log:
                log.event("describe_failed", object=spec.name, code=exc.code, status=exc.status,
                          sf_error=exc.sf_error)
    result = evaluate_gate(contract, describes)
    if log:
        for name, rep in result.report["objects"].items():
            log.event("gate_object", object=name, ok=rep["ok"], missing_required=len(rep["missing_required"]),
                      type_mismatch=len(rep["type_mismatch"]), reference_mismatch=len(rep["reference_mismatch"]),
                      unavailable_optional=len(rep["unavailable_optional"]), createable=rep["createable"],
                      updateable=rep["updateable"], deletable=rep["deletable"])
        log.event("gate_result", ok=result.ok, objects_failed=result.report["objects_failed"])
    return result
