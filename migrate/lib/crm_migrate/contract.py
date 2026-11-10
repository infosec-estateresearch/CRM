"""Source-field contract: load, validate, and build SOQL from it.

SOQL is generated only here, only from contract names, and only in four shapes:

* ``SELECT <fields> FROM <Object> ORDER BY Id``
* ``SELECT <fields> FROM <Object> WHERE SystemModstamp >= <datetime> ORDER BY Id``
* ``SELECT COUNT() FROM <Object>``
* the id-only verification select (``Id, IsDeleted, SystemModstamp``).

The only literal is a datetime, formatted from a typed ``datetime`` value. Names must
match ``^[A-Za-z][A-Za-z0-9_]*$``; wildcards, ``FIELDS(...)``, compound address fields
and names outside the contract are refused.
"""

import datetime as _dt
import hashlib
import json
import re
from dataclasses import dataclass

from .errors import ContractError

CONTRACT_VERSION = 3
NAME_RE = re.compile(r"\A[A-Za-z][A-Za-z0-9_]*\Z")
PURPOSE_RE = re.compile(r"\A[RM]\d+\b")
FIELD_TYPES = frozenset({
    "id", "string", "textarea", "email", "phone", "url", "picklist", "multipicklist",
    "combobox", "reference", "boolean", "int", "double", "currency", "percent", "date",
    "datetime", "time",
})
COMPOUND_TYPES = frozenset({"address", "location"})
COMPOUND_FIELDS = frozenset({"BillingAddress", "ShippingAddress", "MailingAddress", "OtherAddress", "Address"})
EXCLUDED_FIELDS = frozenset({"HtmlBody", "BccAddress"})  # D5
WAIVABLE_FLAGS = ("createable", "updateable", "deletable")
_DT_LITERAL_RE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    purpose: str
    required: bool
    reference_to: tuple = ()
    reference_match: str = "exact"


@dataclass(frozen=True)
class ObjectSpec:
    name: str
    owner_check: bool
    soft_delete: bool
    change_key: str
    fields: tuple

    def field(self, name):
        for fld in self.fields:
            if fld.name == name:
                return fld
        return None

    @property
    def field_names(self):
        return tuple(f.name for f in self.fields)


@dataclass(frozen=True)
class Contract:
    version: int
    objects: tuple
    waivers: tuple
    sha256: str

    def object(self, name):
        for obj in self.objects:
            if obj.name == name:
                return obj
        return None

    @property
    def object_names(self):
        return tuple(o.name for o in self.objects)

    def fields_by_object(self):
        return {o.name: frozenset(o.field_names) for o in self.objects}


def check_name(name, what="name"):
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise ContractError("invalid_name", detail=what)
    return name


def _need(cond, code, detail):
    if not cond:
        raise ContractError(code, detail=detail)


def parse_contract(raw_bytes):
    """Parse and validate contract bytes. Raises ContractError on any violation."""
    try:
        doc = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ContractError("contract_not_json") from None
    _need(isinstance(doc, dict), "contract_shape", "top-level object")
    _need(doc.get("contractVersion") == CONTRACT_VERSION, "contract_version",
          f"expected {CONTRACT_VERSION}")
    raw_objects = doc.get("objects")
    _need(isinstance(raw_objects, list) and raw_objects, "contract_shape", "objects")
    objects = []
    seen = set()
    for raw in raw_objects:
        _need(isinstance(raw, dict), "contract_shape", "object entry")
        name = raw.get("name")
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            raise ContractError("invalid_name", detail="object name")
        _need(name not in seen, "duplicate_object", name)
        seen.add(name)
        objects.append(_parse_object(name, raw))
    waivers = []
    raw_waivers = doc.get("waivers", [])
    _need(isinstance(raw_waivers, list), "contract_shape", "waivers")
    for w in raw_waivers:
        _need(isinstance(w, dict), "contract_shape", "waiver")
        _need(w.get("object") in seen, "waiver_object", "unknown object")
        _need(w.get("flag") in WAIVABLE_FLAGS, "waiver_flag", "unknown flag")
        _need(isinstance(w.get("approvedBy"), str) and w.get("approvedBy") == "Architect", "waiver_approval",
              "approvedBy must be Architect")
        _need(isinstance(w.get("record"), str) and w["record"].strip() != "", "waiver_approval", "record")
        waivers.append((w["object"], w["flag"]))
    return Contract(
        version=CONTRACT_VERSION,
        objects=tuple(objects),
        waivers=tuple(waivers),
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
    )


def _parse_object(name, raw):
    for key in ("ownerCheck", "softDelete"):
        _need(isinstance(raw.get(key), bool), "contract_shape", f"{name}.{key}")
    change_key = raw.get("changeKey")
    _need(change_key == "SystemModstamp", "change_key", f"{name}.changeKey")
    raw_fields = raw.get("fields")
    _need(isinstance(raw_fields, list) and raw_fields, "contract_shape", f"{name}.fields")
    fields = []
    seen = set()
    for rf in raw_fields:
        _need(isinstance(rf, dict), "contract_shape", f"{name} field entry")
        fname = rf.get("name")
        if not isinstance(fname, str) or not NAME_RE.fullmatch(fname):
            raise ContractError("invalid_name", detail=f"{name} field name")
        _need(fname not in seen, "duplicate_field", f"{name}.{fname}")
        seen.add(fname)
        _need(fname not in COMPOUND_FIELDS, "compound_field", f"{name}.{fname}")
        _need(fname not in EXCLUDED_FIELDS, "excluded_field", f"{name}.{fname}")
        ftype = rf.get("type")
        _need(ftype not in COMPOUND_TYPES, "compound_field", f"{name}.{fname}")
        _need(ftype in FIELD_TYPES, "field_type", f"{name}.{fname}")
        purpose = rf.get("purpose")
        _need(isinstance(purpose, str) and PURPOSE_RE.match(purpose), "field_purpose", f"{name}.{fname}")
        _need(isinstance(rf.get("required"), bool), "field_required", f"{name}.{fname}")
        ref = rf.get("referenceTo")
        match = rf.get("referenceMatch", "exact")
        if ftype == "reference":
            _need(isinstance(ref, list) and ref, "reference_to", f"{name}.{fname}")
            for target in ref:
                if not isinstance(target, str) or not NAME_RE.fullmatch(target):
                    raise ContractError("invalid_name", detail=f"{name}.{fname} referenceTo")
            _need(match in ("exact", "superset"), "reference_match", f"{name}.{fname}")
            ref_t = tuple(ref)
        else:
            _need(ref is None and "referenceMatch" not in rf, "reference_to", f"{name}.{fname}")
            ref_t = ()
        fields.append(FieldSpec(fname, ftype, purpose, rf["required"], ref_t, match))
    spec = ObjectSpec(name, raw["ownerCheck"], raw["softDelete"], change_key, tuple(fields))
    idf = spec.field("Id")
    _need(idf is not None and idf.type == "id" and idf.required, "structural_field", f"{name}.Id")
    ck = spec.field(change_key)
    _need(ck is not None and ck.type == "datetime" and ck.required, "structural_field", f"{name}.{change_key}")
    isdel = spec.field("IsDeleted")
    if spec.soft_delete:
        _need(isdel is not None and isdel.type == "boolean" and isdel.required, "structural_field",
              f"{name}.IsDeleted")
    else:
        _need(isdel is None, "structural_field", f"{name}.IsDeleted without softDelete")
    if spec.owner_check:
        owner = spec.field("OwnerId")
        _need(owner is not None and owner.type == "reference" and owner.required, "structural_field",
              f"{name}.OwnerId")
    return spec


def load_contract(path):
    with open(path, "rb") as fh:
        return parse_contract(fh.read())


# ---------------------------------------------------------------- effective contract

@dataclass(frozen=True)
class EffectiveObject:
    spec: ObjectSpec
    fields: tuple          # available contract field names, in contract order
    unavailable: tuple     # optional contract fields absent from describe

    @property
    def name(self):
        return self.spec.name


def effective_object(spec, available_names):
    available = set(available_names)
    fields = tuple(f.name for f in spec.fields if f.name in available)
    unavailable = tuple(f.name for f in spec.fields if f.name not in available)
    for name in unavailable:
        if spec.field(name).required:
            raise ContractError("required_field_unavailable", detail=f"{spec.name}.{name}")
    return EffectiveObject(spec, fields, unavailable)


def effective_to_json(effective):
    return {
        e.name: {
            "ownerCheck": e.spec.owner_check,
            "softDelete": e.spec.soft_delete,
            "changeKey": e.spec.change_key,
            "fields": list(e.fields),
            "unavailable": list(e.unavailable),
        }
        for e in effective
    }


# ---------------------------------------------------------------- SOQL

def soql_datetime(value):
    """Format a timezone-aware datetime as a SOQL UTC literal ``YYYY-MM-DDThh:mm:ssZ``."""
    if not isinstance(value, _dt.datetime) or value.tzinfo is None:
        raise ContractError("soql_literal", detail="aware datetime required")
    utc = value.astimezone(_dt.timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _check_select_fields(spec, fields):
    if not fields:
        raise ContractError("soql_fields", detail=f"{spec.name} no fields")
    seen = set()
    for name in fields:
        if not isinstance(name, str) or "*" in name or "(" in name or not NAME_RE.fullmatch(name):
            raise ContractError("soql_fields", detail="invalid field name")
        if name in COMPOUND_FIELDS or name in EXCLUDED_FIELDS:
            raise ContractError("soql_fields", detail=f"{spec.name}.{name} refused")
        if spec.field(name) is None:
            raise ContractError("soql_fields", detail=f"{spec.name}.{name} not in contract")
        if name in seen:
            raise ContractError("soql_fields", detail=f"{spec.name}.{name} duplicate")
        seen.add(name)


def soql_select(spec, fields, since=None):
    check_name(spec.name, "object")
    _check_select_fields(spec, fields)
    q = f"SELECT {', '.join(fields)} FROM {spec.name}"
    if since is not None:
        q += f" WHERE {spec.change_key} >= {soql_datetime(since)}"
    return q + " ORDER BY Id"


def soql_count(spec):
    check_name(spec.name, "object")
    return f"SELECT COUNT() FROM {spec.name}"


def id_only_fields(spec):
    return ("Id", "IsDeleted", spec.change_key) if spec.soft_delete else ("Id", spec.change_key)


def soql_id_only(spec):
    return soql_select(spec, id_only_fields(spec))


_SOQL_RE = re.compile(
    r"SELECT (?P<fields>COUNT\(\)|[A-Za-z][A-Za-z0-9_]*(?:, [A-Za-z][A-Za-z0-9_]*)*)"
    r" FROM (?P<object>[A-Za-z][A-Za-z0-9_]*)"
    r"(?: WHERE SystemModstamp >= (?P<since>" + _DT_LITERAL_RE + r"))?"
    r"(?P<order> ORDER BY Id)?"
)


@dataclass(frozen=True)
class ParsedSoql:
    object: str
    fields: tuple  # empty for COUNT()
    since: object  # datetime or None
    is_count: bool


def parse_soql(q):
    """Parse a SOQL string of one of the generated shapes; return None if it is not one."""
    if not isinstance(q, str):
        return None
    m = _SOQL_RE.fullmatch(q)   # fullmatch: "$" would accept a trailing newline
    if not m:
        return None
    is_count = m.group("fields") == "COUNT()"
    if is_count and (m.group("since") or m.group("order")):
        return None
    if not is_count and not m.group("order"):
        return None
    since = None
    if m.group("since"):
        try:
            since = _dt.datetime.strptime(m.group("since"), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
        except ValueError:
            return None
    fields = () if is_count else tuple(m.group("fields").split(", "))
    return ParsedSoql(m.group("object"), fields, since, is_count)
