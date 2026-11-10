"""Enquiry (Opportunity) policy for CRM-004, standard library only.

Each rule takes a "bundle" (see load_bundle) and returns a list of violation strings;
an empty list means the rule holds. test_enquiries.py breaks every rule with a
mutated copy of the repository bundle (the broken fixture) to show it can fail.

The loss-reason hook is checked statically (php is not available in the loop), and
its decision table is mirrored by loss_reason_allowed below.
"""

import json
import os
import re

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CUSTOM = os.path.join(REPO, "custom", "Espo", "Custom")
RES = os.path.join(CUSTOM, "Resources")
HOOK_PATH = os.path.join(CUSTOM, "Hooks", "Opportunity", "RequireLossReason.php")
FILTER_DIR = os.path.join(CUSTOM, "Classes", "Select", "Opportunity", "PrimaryFilters")

# Core Opportunity fields in EspoCRM 10.0.12 (verified by the operator, WO CRM-004).
CORE_FIELDS = {"name", "amount", "account", "contacts", "contact", "stage", "lastStage",
               "probability", "leadSource", "closeDate", "description", "contactRole",
               "assignedUser", "teams"}
STAGES = ["Enquiry", "Quoted", "Instructed", "Lost"]
PROBABILITY = {"Enquiry": 10, "Quoted": 50, "Instructed": 100, "Lost": 0}
LOSS_REASONS = ["", "No longer needed", "Unable to work in that country", "Other",
                "Lost to Competitor", "Price", "No Decision / Non-Responsive",
                "Solicitor carried out in house", "No Budget / Lost Funding",
                "Lost to Lay Client"]
ENUMS = {
    "lossReason": LOSS_REASONS,
    "channel": ["", "Unmapped (legacy)"],
    "businessType": ["", "New Business", "Existing Business"],
    "enquiryCategory": ["", "Yes", "No", "Ancillary", "Legal rights check", "Overseas Assets",
                        "Share Sale"],
}
CUSTOM_TYPES = dict(
    {"serviceType": "link", "introducedBy": "link", "clientReference": "varchar",
     "deceasedName": "varchar", "caseNumber": "varchar", "postcode": "varchar",
     "keyInformation": "text", "sfId": "varchar", "sfStageName": "varchar",
     "sfLeadSource": "varchar", "sfOwnerId": "varchar", "sfCreatedAt": "datetime",
     "legacyStale": "bool", "lossReasonLegacyMissing": "bool"},
    **{name: "enum" for name in ENUMS})
LEGACY_FIELDS = ["sfId", "sfStageName", "sfLeadSource", "sfOwnerId", "sfCreatedAt",
                 "legacyStale", "lossReasonLegacyMissing"]
AUDITED = ["stage", "amount", "assignedUser", "closeDate", "lossReason"]
LIST_LAYOUT = ["name", "account", "stage", "amount", "serviceType", "assignedUser", "closeDate"]
FILTERS_LAYOUT = ["stage", "assignedUser", "serviceType", "enquiryCategory", "legacyStale"]
QUICK_CREATE = ["account", "contact", "serviceType", "name", "description"]
CASE_DETAILS = ["clientReference", "deceasedName", "caseNumber", "postcode", "keyInformation"]
PRIMARY_FILTERS = {"openEnquiries": "OpenEnquiries", "myOpenEnquiries": "MyOpenEnquiries",
                   "legacyStale": "LegacyStale"}
FILTER_NS = "Espo\\Custom\\Classes\\Select\\Opportunity\\PrimaryFilters"


def _load(*parts):
    with open(os.path.join(RES, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def load_bundle():
    """Everything the rules look at, as plain data (so a test can mutate a copy)."""
    return {
        "defs": _load("metadata", "entityDefs", "Opportunity.json"),
        "serviceTypeDefs": _load("metadata", "entityDefs", "ServiceType.json"),
        "serviceTypeScope": _load("metadata", "scopes", "ServiceType.json"),
        "logic": _load("metadata", "logicDefs", "Opportunity.json"),
        "select": _load("metadata", "selectDefs", "Opportunity.json"),
        "client": _load("metadata", "clientDefs", "Opportunity.json"),
        "i18n": _load("i18n", "en_US", "Opportunity.json"),
        "global": _load("i18n", "en_US", "Global.json"),
        "layouts": {n[:-5]: _load("layouts", "Opportunity", n)
                    for n in os.listdir(os.path.join(RES, "layouts", "Opportunity"))},
        "filters": {name: _text(os.path.join(FILTER_DIR, f"{cls}.php"))
                    for name, cls in PRIMARY_FILTERS.items()
                    if os.path.isfile(os.path.join(FILTER_DIR, f"{cls}.php"))},
        "hook": _text(HOOK_PATH),
    }


def _fields(b):
    return (b.get("defs") or {}).get("fields") or {}


def layout_names(layout):
    names = []
    for item in layout:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and "rows" in item:
            names += [cell["name"] for row in item["rows"] for cell in row if cell]
        elif isinstance(item, dict):
            names.append(item.get("name"))
    return names


# --- the loss-reason rule, as a decision table (mirrors RequireLossReason.php) ------

def loss_reason_allowed(stage, loss_reason, legacy_missing, stage_changed, reason_changed,
                        is_api_user):
    """WO CRM-004 item 4: may an Opportunity be saved?"""
    if stage != "Lost":
        return True
    if loss_reason:
        return True
    if legacy_missing and is_api_user:
        return True
    return bool(legacy_missing and not stage_changed and not reason_changed)


# --- entityDefs rules --------------------------------------------------------------

def rule_stage(b):
    f = _fields(b).get("stage") or {}
    out = []
    if f.get("options") != STAGES:
        out.append(f"stage options {f.get('options')} != {STAGES}")
    if f.get("default") != "Enquiry":
        out.append(f"stage default {f.get('default')!r} != 'Enquiry'")
    if f.get("probabilityMap") != PROBABILITY:
        out.append(f"probabilityMap {f.get('probabilityMap')} != {PROBABILITY}")
    if set(f.get("style") or {}) != set(STAGES):
        out.append("stage style must cover every stage")
    last = (_fields(b).get("lastStage") or {}).get("options")
    if last != [s for s in STAGES if PROBABILITY[s] > 0]:
        out.append(f"lastStage options {last} must be the non-lost stages")
    return out


def rule_custom_fields(b):
    out = []
    fields = _fields(b)
    for name, kind in CUSTOM_TYPES.items():
        f = fields.get(name) or {}
        if f.get("type") != kind or f.get("isCustom") is not True:
            out.append(f"{name}: must be a custom {kind}")
    for name, options in ENUMS.items():
        f = fields.get(name) or {}
        if f.get("options") != options or f.get("default") != "":
            out.append(f"{name}: options {f.get('options')} != {options}, or default not ''")
    links = (b.get("defs") or {}).get("links") or {}
    for name, entity in (("serviceType", "ServiceType"), ("introducedBy", "User")):
        if (links.get(name) or {}).get("type") != "belongsTo" or links[name].get("entity") != entity:
            out.append(f"link {name} must be belongsTo {entity}")
    return out


def rule_audited(b):
    return [f"{n} is not audited" for n in AUDITED
            if (_fields(b).get(n) or {}).get("audited") is not True]


def rule_legacy_fields(b):
    """Amendment v1.1: no legacy field is readOnly; sfId is readOnlyAfterCreate,
    varchar 18 with a unique index; legacy fields are not audited."""
    out = []
    fields = _fields(b)
    for name in LEGACY_FIELDS:
        f = fields.get(name) or {}
        if "readOnly" in f:
            out.append(f"{name}: readOnly is set (global restriction would block ER Import)")
        if f.get("audited"):
            out.append(f"{name}: must not be audited")
        if f.get("readOnlyAfterCreate") and name != "sfId":
            out.append(f"{name}: only sfId is readOnlyAfterCreate")
    sf_id = fields.get("sfId") or {}
    if sf_id.get("readOnlyAfterCreate") is not True or sf_id.get("maxLength") != 18:
        out.append("sfId must be readOnlyAfterCreate with maxLength 18")
    if ((b.get("defs") or {}).get("indexes") or {}).get("sfId") != {"type": "unique",
                                                                    "columns": ["sfId"]}:
        out.append("sfId has no unique index named sfId")
    return out


def rule_service_type_entity(b):
    out = []
    defs = b.get("serviceTypeDefs") or {}
    fields = defs.get("fields") or {}
    for name, kind in (("name", "varchar"), ("isActive", "bool"), ("sfValue", "varchar")):
        if (fields.get(name) or {}).get("type") != kind:
            out.append(f"ServiceType.{name} must be a {kind}")
    if (defs.get("indexes") or {}).get("name") != {"type": "unique", "columns": ["name"]}:
        out.append("ServiceType.name has no unique index")
    link = (defs.get("links") or {}).get("opportunities") or {}
    if (link.get("type"), link.get("entity"), link.get("foreign")) != (
            "hasMany", "Opportunity", "serviceType"):
        out.append("ServiceType.opportunities must be hasMany Opportunity (foreign serviceType)")
    if ((b.get("defs") or {}).get("links") or {}).get("serviceType", {}).get("foreign") != \
            "opportunities":
        out.append("Opportunity.serviceType foreign must be 'opportunities'")
    scope = b.get("serviceTypeScope") or {}
    if not (scope.get("entity") is True and scope.get("acl") is True):
        out.append("ServiceType scope must be an ACL-controlled entity")
    return out


# --- dynamic logic ----------------------------------------------------------------

def _equals_lost(group):
    return any(c.get("type") == "equals" and c.get("attribute") == "stage"
               and c.get("value") == "Lost" for c in group or [])


def rule_dynamic_logic(b):
    fields = (b.get("logic") or {}).get("fields") or {}
    out = []
    last = ((fields.get("lastStage") or {}).get("visible") or {}).get("conditionGroup")
    if not _equals_lost(last) or "Closed Lost" in json.dumps(last):
        out.append("lastStage must be visible when stage equals 'Lost'")
    req = ((fields.get("lossReason") or {}).get("required") or {}).get("conditionGroup")
    if not _equals_lost(req):
        out.append("lossReason must be required when stage equals 'Lost'")
    return out


# --- layouts ----------------------------------------------------------------------

def rule_layout_fields_exist(b):
    known = CORE_FIELDS | set(_fields(b))
    return [f"{layout}: unknown field {n!r}"
            for layout, data in (b.get("layouts") or {}).items() if layout != "relationships"
            for n in layout_names(data) if n not in known]


def rule_layouts_as_specified(b):
    out = []
    layouts = b.get("layouts") or {}
    if layout_names(layouts.get("list") or []) != LIST_LAYOUT:
        out.append(f"list layout must be {LIST_LAYOUT}")
    if layout_names(layouts.get("filters") or []) != FILTERS_LAYOUT:
        out.append(f"filters layout must be {FILTERS_LAYOUT}")
    if sorted(layout_names(layouts.get("detailSmall") or [])) != sorted(QUICK_CREATE):
        out.append(f"quick create (detailSmall) must be exactly {QUICK_CREATE}")
    panels = {p.get("label"): p for p in layouts.get("detail") or []}
    if list(panels) != ["Enquiry", "Case details", "Legacy"]:
        out.append(f"detail panels are {list(panels)}")
    elif sorted(layout_names([panels["Case details"]])) != sorted(CASE_DETAILS):
        out.append("Case details panel fields are wrong")
    elif sorted(layout_names([panels["Legacy"]])) != sorted(LEGACY_FIELDS) or \
            panels["Legacy"].get("collapsed") is not True:
        out.append("Legacy panel must be collapsed and hold every legacy field")
    else:
        for label in ("Enquiry", "Case details"):
            if set(layout_names([panels[label]])) & set(LEGACY_FIELDS):
                out.append(f"{label} panel shows a legacy field")
    if "contacts" not in (layouts.get("relationships") or []):
        out.append("relationships must include the contacts panel")
    return out


def rule_legacy_not_in_edit_layouts(b):
    """Legacy fields stay out of every layout except the detail Legacy panel."""
    return [f"{layout}: shows legacy field {n}"
            for layout, data in (b.get("layouts") or {}).items()
            if layout not in ("detail", "filters")
            for n in layout_names(data) if n in LEGACY_FIELDS] + \
           [f"filters: shows legacy field {n}"
            for n in layout_names((b.get("layouts") or {}).get("filters") or [])
            if n in LEGACY_FIELDS and n != "legacyStale"]


# --- primary filters --------------------------------------------------------------

def _php(source):
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"(^|[^:])//.*$", r"\1", source, flags=re.M)


_OPEN = re.compile(r"Cond:{2}in\(\s*Cond:{2}column\('stage'\)\s*,\s*\['Enquiry'\s*,\s*'Quoted'\]\s*\)")
_NOT_STALE = re.compile(r"Cond:{2}equal\(\s*Cond:{2}column\('legacyStale'\)\s*,\s*false\s*\)")
_STALE = re.compile(r"Cond:{2}equal\(\s*Cond:{2}column\('legacyStale'\)\s*,\s*true\s*\)")
_MINE = re.compile(r"Cond:{2}equal\(\s*Cond:{2}column\('assignedUserId'\)\s*,\s*"
                   r"\$this->user->getId\(\)\s*\)")


def rule_primary_filters(b):
    out = []
    mapping = (b.get("select") or {}).get("primaryFilterClassNameMap") or {}
    for name, cls in PRIMARY_FILTERS.items():
        if mapping.get(name) != f"{FILTER_NS}\\{cls}":
            out.append(f"selectDefs does not map {name} to {FILTER_NS}\\{cls}")
        src = _php((b.get("filters") or {}).get(name, ""))
        if not re.search(rf"namespace\s+{re.escape(FILTER_NS)}\s*;", src) or \
                not re.search(rf"class\s+{cls}\s+implements\s+Filter\b", src) or \
                not re.search(r"use\s+Espo\\Core\\Select\\Primary\\Filter\s*;", src) or \
                not re.search(r"function\s+apply\(\s*SelectBuilder\s+\$queryBuilder\s*\)"
                              r"\s*:\s*void", src):
            out.append(f"{cls}.php is not a primary Filter class")
    src = {n: _php(s) for n, s in (b.get("filters") or {}).items()}
    if not (_OPEN.search(src.get("openEnquiries", "")) and
            _NOT_STALE.search(src.get("openEnquiries", ""))):
        out.append("openEnquiries must be stage in (Enquiry, Quoted) and legacyStale false")
    my = src.get("myOpenEnquiries", "")
    if not (_OPEN.search(my) and _NOT_STALE.search(my) and _MINE.search(my)):
        out.append("myOpenEnquiries must be the open filter plus assignedUserId = current user")
    if not _STALE.search(src.get("legacyStale", "")) or _OPEN.search(src.get("legacyStale", "")):
        out.append("legacyStale must select legacyStale = true")
    client = b.get("client") or {}
    listed = [f if isinstance(f, str) else f.get("name") for f in client.get("filterList") or []]
    for name in PRIMARY_FILTERS:
        if name not in listed:
            out.append(f"clientDefs filterList does not list {name}")
        if name not in ((b.get("i18n") or {}).get("presetFilters") or {}):
            out.append(f"no presetFilters label for {name}")
    if (client.get("defaultFilterData") or {}).get("primary") != "openEnquiries":
        out.append("the default primary filter must be openEnquiries")
    return out


# --- labels -----------------------------------------------------------------------

def rule_labels(b):
    out = []
    g = b.get("global") or {}
    if (g.get("scopeNames") or {}).get("Opportunity") != "Enquiry" or \
            (g.get("scopeNamesPlural") or {}).get("Opportunity") != "Enquiries":
        out.append("Global scope names must be Enquiry / Enquiries")
    i18n = b.get("i18n") or {}
    if (i18n.get("fields") or {}).get("amount") != "Quoted fee":
        out.append("amount must be labelled 'Quoted fee'")
    for name in CUSTOM_TYPES:
        if name not in (i18n.get("fields") or {}):
            out.append(f"no label for {name}")
    for name, f in _fields(b).items():
        if f.get("type") == "enum" and set((i18n.get("options") or {}).get(name) or {}) != \
                set(f.get("options") or []):
            out.append(f"option labels for {name} do not match its options")
    return out


# --- the loss-reason hook (static) ------------------------------------------------

# The whole of beforeSave, statement by statement, so a removed or weakened guard
# (a dropped condition, `||` for `&&`, an early return, a skipped throw) does not match.
_HOOK_BODY = re.compile(r"""
\s*if\s*\(\s*\$entity->get\('stage'\)\s*!==\s*'Lost'\s*\)\s*\{\s*return\s*;\s*\}
\s*if\s*\(\s*\(string\)\s*\$entity->get\('lossReason'\)\s*!==\s*''\s*\)\s*\{\s*return\s*;\s*\}
\s*\$legacyMissing\s*=\s*\$entity->get\('lossReasonLegacyMissing'\)\s*===\s*true\s*;
\s*if\s*\(\s*\$legacyMissing\s*&&\s*\$this->user->getType\(\)\s*===\s*User::TYPE_API\s*\)
\s*\{\s*return\s*;\s*\}
\s*\$unchanged\s*=\s*!\$entity->isAttributeChanged\('stage'\)\s*&&
\s*!\$entity->isAttributeChanged\('lossReason'\)\s*;
\s*if\s*\(\s*\$legacyMissing\s*&&\s*\$unchanged\s*\)\s*\{\s*return\s*;\s*\}
\s*throw\s+new\s+BadRequest\(\s*'[^'\\]*'\s*\)\s*;\s*
""", re.X)


def _method_body(code, name):
    m = re.search(r"function\s+" + name + r"\s*\([^)]*\)\s*(?::\s*\w+\s*)?\{", code)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(code) and depth:
        depth += {"{": 1, "}": -1}.get(code[i], 0)
        i += 1
    return code[m.end():i - 1] if depth == 0 else None


def rule_hook_shape(b):
    code = _php(b.get("hook") or "")
    out = []
    for pattern, msg in (
            (r"^\s*namespace\s+Espo\\Custom\\Hooks\\Opportunity\s*;", "namespace"),
            (r"^\s*use\s+Espo\\Core\\Hook\\Hook\\BeforeSave\s*;", "use BeforeSave"),
            (r"^\s*use\s+Espo\\Core\\Exceptions\\BadRequest\s*;", "use BadRequest"),
            (r"^\s*use\s+Espo\\Entities\\User\s*;", "use User"),
            (r"\bclass\s+RequireLossReason\s+implements\s+BeforeSave\b", "implements BeforeSave"),
            (r"__construct\(\s*private\s+User\s+\$user\s*\)", "injects the current User"),
            (r"public\s+function\s+beforeSave\s*\(\s*Entity\s+\$entity\s*,\s*SaveOptions\s+"
             r"\$options\s*\)\s*:\s*void", "beforeSave signature")):
        if not re.search(pattern, code, re.M):
            out.append(f"hook: {msg} missing")
    return out


def rule_hook_body(b):
    body = _method_body(_php(b.get("hook") or ""), "beforeSave")
    if body is None or not _HOOK_BODY.fullmatch(body):
        return ["beforeSave is not exactly the loss-reason rule (see loss_reason_allowed)"]
    return []


RULES = {
    "stage": rule_stage,
    "custom_fields": rule_custom_fields,
    "audited": rule_audited,
    "legacy_fields": rule_legacy_fields,
    "service_type_entity": rule_service_type_entity,
    "dynamic_logic": rule_dynamic_logic,
    "layout_fields_exist": rule_layout_fields_exist,
    "layouts_as_specified": rule_layouts_as_specified,
    "legacy_not_in_edit_layouts": rule_legacy_not_in_edit_layouts,
    "primary_filters": rule_primary_filters,
    "labels": rule_labels,
    "hook_shape": rule_hook_shape,
    "hook_body": rule_hook_body,
}


def check(bundle):
    return {name: fn(bundle) for name, fn in RULES.items()}
