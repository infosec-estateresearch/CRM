"""Access policy for CRM-003, standard library only.

Three groups of rules, each a function returning a list of violation strings
(an empty list means the rule holds):
- ROLE_RULES take the parsed config/access documents {"roles", "teams", "apiUsers"};
- KEY_RULES take {entity: parsed custom entityDefs} for User, Account and Contact;
- HOOK_RULES take the source text of the Account deletion-guard hook.
"""

import json
import os
import re

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ACCESS_DIR = os.path.join(REPO, "config", "access")
RES = os.path.join(REPO, "custom", "Espo", "Custom", "Resources")
ENTITY_DEFS_DIR = os.path.join(RES, "metadata", "entityDefs")
HOOK_PATH = os.path.join(REPO, "custom", "Espo", "Custom", "Hooks", "Account",
                         "RestrictDeleteWithEnquiries.php")

TEAMS = ["Enquiries", "Ancillary intake", "Firm management"]
STAFF, INTAKE, MANAGER, IMPORT = "ER Staff", "ER Intake", "ER Manager", "ER Import"
ROLES = [STAFF, INTAKE, MANAGER, IMPORT]
NON_ADMIN_HUMAN_ROLES = [STAFF, INTAKE, MANAGER]
ACTIVITIES = ["Call", "Meeting", "Task"]
MAIN_SCOPES = ["Account", "Contact", "Opportunity"] + ACTIVITIES + ["Email"]

# The authoritative set of ACL-enabled scopes, verified by PL in espocrm 10.0.12
# (scope metadata of the running image). That instance has no aclStrictMode, so a
# scope a role leaves unset is ALLOWED: every role must list every scope here.
# To add a scope (CRM-004: ServiceType), add it to ACL_ENTITY_SCOPES or
# ACL_BOOLEAN_SCOPES and give it a row in EXPECTED_DATA; the rules below follow.
ACL_ENTITY_SCOPES = [
    "Account", "Call", "Campaign", "Case", "Contact", "Currency", "Document", "DocumentFolder",
    "Email", "EmailTemplate", "EmailTemplateCategory", "KnowledgeBaseArticle",
    "KnowledgeBaseCategory", "Lead", "Meeting", "Opportunity", "TargetList",
    "TargetListCategory", "Task", "Team", "Template", "User",
    "ServiceType",  # added by CRM-004 (custom reference entity)
]
ACL_BOOLEAN_SCOPES = [
    "Activities", "Calendar", "EmailAccountScope", "ExternalAccount", "GlobalStream", "Import",
    "OpenApi", "Webhook", "WorkingTimeCalendar",
]
ACL_SCOPES = ACL_ENTITY_SCOPES + ACL_BOOLEAN_SCOPES
# Generic CRM entity scopes Estate Research does not use: no access (false) for every role.
UNUSED_SCOPES = ["Lead", "Campaign", "TargetList", "TargetListCategory", "KnowledgeBaseArticle",
                 "KnowledgeBaseCategory", "Template", "EmailTemplate", "EmailTemplateCategory",
                 "Case"]
# Reference scopes: read all, never create, edit or delete.
READ_ONLY_SCOPES = ["Currency", "Document", "DocumentFolder", "User", "Team"]
# CRM-003-F: entity scopes whose ACL is level-based, not the five-action table. Verified
# by the PL live in espocrm 10.0.12 (scopes.<scope>.aclActionList / aclLevelList): the
# server refuses (HTTP 400) any other action or level, e.g. Currency read "all".
LEVEL_SCOPES = {"Currency": {"actions": ["read", "edit"], "levels": {"yes", "no"}}}
# Read-only, per scope kind: entity scopes read all and nothing else; level-based scopes
# read yes, edit no.
READ_ONLY_LEVEL_ROW = {"read": "yes", "edit": "no"}
# Added by CRM-004: reference data that admins maintain. Human roles read all and
# change nothing (admins bypass role ACL); ER Import creates and edits, never deletes.
ADMIN_MANAGED_SCOPES = ["ServiceType"]
# Boolean scopes for the human roles; ER Import has every boolean scope false except
# Import (CRM-006): EspoCRM 10.0.12 CheckFromAddress refuses a non-admin creating an
# Email whose from is not their own unless the Import scope is granted.
HUMAN_BOOLEAN = {"Activities": True, "Calendar": True, "GlobalStream": True,
                 "WorkingTimeCalendar": True, "Import": False, "Webhook": False,
                 "OpenApi": False, "ExternalAccount": False, "EmailAccountScope": False}
IMPORT_BOOLEAN = dict({s: False for s in ACL_BOOLEAN_SCOPES}, Import=True)
ACTIONS = ["create", "read", "edit", "delete", "stream"]
LEVELS = {"create": {"yes", "no"}, "read": {"all", "team", "own", "no"},
          "edit": {"all", "team", "own", "no"}, "delete": {"all", "team", "own", "no"},
          "stream": {"all", "team", "own", "no"}}
SF_KEY_ENTITIES = ["User", "Account", "Contact"]
SF_EXTRA = {"sfOwnerId": "varchar", "sfCreatedAt": "datetime"}
# Every Salesforce key field, by entity. None of them may be readOnly (the global
# restriction would stop the importer too); people are kept off them by fieldData.
# Added by CRM-004 (Amendment v1.1): the Opportunity legacy fields, read-only for
# people through fieldData, writable by ER Import.
OPPORTUNITY_LEGACY_FIELDS = ["sfId", "sfStageName", "sfLeadSource", "sfOwnerId", "sfCreatedAt",
                             "legacyStale", "lossReasonLegacyMissing"]
# Added by CRM-005: the activity and email legacy fields, the same pattern.
ACTIVITY_LEGACY_FIELDS = ["sfId", "sfOwnerId", "sfCreatedAt"]
# CRM-008-G: Task also keeps the Salesforce completion date (read-only for people).
TASK_LEGACY_FIELDS = ACTIVITY_LEGACY_FIELDS + ["sfCompletedAt"]
EMAIL_LEGACY_FIELDS = ACTIVITY_LEGACY_FIELDS + ["sfEmailMessageId", "sfThreadIdentifier",
                                                "sfActivityId"]
SF_FIELDS = dict({"User": ["sfId"], "Account": ["sfId"] + list(SF_EXTRA),
                  "Contact": ["sfId"] + list(SF_EXTRA), "Opportunity": OPPORTUNITY_LEGACY_FIELDS},
                 **{a: TASK_LEGACY_FIELDS if a == "Task" else ACTIVITY_LEGACY_FIELDS
                    for a in ACTIVITIES}, Email=EMAIL_LEGACY_FIELDS)
AUDITED = {"Account": ["name", "type", "industry", "assignedUser", "parent",
                       "learningPlatformAccess"],
           "Contact": ["account", "emailAddress"]}


def _row(create, edit, delete):
    return {"create": create, "read": "all", "edit": edit, "delete": delete, "stream": "all"}


def read_only_row(scope):
    """The read-only access for `scope`, expressed in that scope's kind of ACL."""
    return dict(READ_ONLY_LEVEL_ROW) if scope in LEVEL_SCOPES else _row("no", "no", "no")


# The WO CRM-003 item 2 table (plus the round-4 scope ruling), transcribed
# independently of config/access/roles.json. CRM-005: Email edit is "no" for
# ER Staff and ER Intake (archived email is read-only history). CRM-003-F: Currency
# is level-based (read yes, edit no).
_FIXED = dict({s: read_only_row(s) for s in READ_ONLY_SCOPES},
              **{s: False for s in UNUSED_SCOPES})
_HUMAN_ADMIN_MANAGED = {s: _row("no", "no", "no") for s in ADMIN_MANAGED_SCOPES}  # CRM-004
_IMPORT_ADMIN_MANAGED = {s: _row("yes", "all", "no") for s in ADMIN_MANAGED_SCOPES}  # CRM-004
_HUMAN = dict(_FIXED, **HUMAN_BOOLEAN, **_HUMAN_ADMIN_MANAGED)
EXPECTED_DATA = {
    STAFF: dict({"Account": _row("yes", "all", "no"), "Contact": _row("yes", "all", "no"),
                 "Opportunity": _row("yes", "own", "no"), "Email": _row("yes", "no", "no")},
                **{a: _row("yes", "own", "own") for a in ACTIVITIES}, **_HUMAN),
    INTAKE: dict({"Account": _row("yes", "all", "no"), "Contact": _row("yes", "all", "no"),
                  "Opportunity": _row("yes", "all", "no"), "Email": _row("yes", "no", "no")},
                 **{a: _row("yes", "own", "own") for a in ACTIVITIES}, **_HUMAN),
    MANAGER: dict({"Account": _row("yes", "all", "no"), "Contact": _row("yes", "all", "all"),
                   "Opportunity": _row("yes", "all", "all"), "Email": _row("yes", "all", "no")},
                  **{a: _row("yes", "all", "all") for a in ACTIVITIES}, **_HUMAN),
    IMPORT: dict({s: _row("yes", "all", "no") for s in MAIN_SCOPES}, **_FIXED, **IMPORT_BOOLEAN,
                  **_IMPORT_ADMIN_MANAGED),
}


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_access(roles_path=None, teams_path=None, api_users_path=None):
    return {
        "roles": _load(roles_path or os.path.join(ACCESS_DIR, "roles.json")).get("roles"),
        "teams": _load(teams_path or os.path.join(ACCESS_DIR, "teams.json")).get("teams"),
        "apiUsers": _load(api_users_path or os.path.join(ACCESS_DIR, "api_users.json")).get("apiUsers"),
    }


def load_entity_defs(directory=ENTITY_DEFS_DIR, overrides=None):
    """{entity: defs} for User, Account and Contact; overrides maps entity -> path."""
    overrides = overrides or {}
    return {e: _load(overrides.get(e) or os.path.join(directory, f"{e}.json"))
            for e in SF_KEY_ENTITIES}


def load_hook(path=HOOK_PATH):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _roles(doc):
    return {r.get("name"): r for r in doc.get("roles") or [] if isinstance(r, dict)}


def _data(doc, role):
    return (_roles(doc).get(role) or {}).get("data") or {}


# --- role rules -------------------------------------------------------------------

def rule_teams_and_roles_present(doc):
    out = []
    teams = [t.get("name") for t in doc.get("teams") or []]
    if teams != TEAMS:
        out.append(f"teams are {teams}, expected {TEAMS}")
    roles = [r.get("name") for r in doc.get("roles") or []]
    if roles != ROLES:
        out.append(f"roles are {roles}, expected {ROLES}")
    return out


def rule_every_acl_scope_explicit(doc):
    """Non-strict ACL allows any unset scope: every role lists exactly ACL_SCOPES, and
    every boolean scope is an explicit true or false."""
    out = []
    for name, role in _roles(doc).items():
        data = role.get("data") or {}
        for scope in ACL_SCOPES:
            if scope not in data:
                out.append(f"{name}: no explicit access for {scope} (unset means allowed)")
        for scope in sorted(set(data) - set(ACL_SCOPES)):
            out.append(f"{name}: {scope} is not a verified ACL scope (add it to ACL_SCOPES)")
        for scope in ACL_BOOLEAN_SCOPES:
            if scope in data and not isinstance(data[scope], bool):
                out.append(f"{name}.{scope}: boolean scope must be true or false, "
                           f"not {data[scope]!r}")
    return out


def rule_known_levels(doc):
    """Every entity scope is false or exactly the five actions, at valid levels.
    Level-based scopes are checked by rule_level_scopes instead."""
    out = []
    for name, role in _roles(doc).items():
        for scope, actions in (role.get("data") or {}).items():
            if scope in ACL_BOOLEAN_SCOPES or scope in LEVEL_SCOPES or actions is False:
                continue
            if not isinstance(actions, dict) or sorted(actions) != sorted(ACTIONS):
                out.append(f"{name}.{scope}: must be false or exactly the actions {ACTIONS}")
                continue
            for action, level in actions.items():
                if level not in LEVELS[action]:
                    out.append(f"{name}.{scope}.{action}: invalid level {level!r}")
    return out


def rule_level_scopes(doc):
    """CRM-003-F: a level-based scope (Currency) is false or uses exactly its own actions,
    each at one of its own levels; EspoCRM 10.0.12 refuses anything else with HTTP 400."""
    out = []
    for name, role in _roles(doc).items():
        data = role.get("data") or {}
        for scope, spec in LEVEL_SCOPES.items():
            if scope not in data or data[scope] is False:
                continue  # a missing scope is every_acl_scope_explicit's to report
            actions = data[scope]
            if not isinstance(actions, dict) or sorted(actions) != sorted(spec["actions"]):
                out.append(f"{name}.{scope}: level-based scope must be false or exactly "
                           f"the actions {spec['actions']}, not {actions!r}")
                continue
            for action, level in actions.items():
                if level not in spec["levels"]:
                    out.append(f"{name}.{scope}.{action}: level {level!r} is not one of "
                               f"{sorted(spec['levels'])}")
    return out


def rule_unused_scopes_disabled(doc):
    """Generic CRM scopes Estate Research does not use are false for every role."""
    return [f"{name}.{scope}: is {(role.get('data') or {}).get(scope)!r}, expected false"
            for name, role in _roles(doc).items() for scope in UNUSED_SCOPES
            if (role.get("data") or {}).get(scope) is not False]


def rule_read_only_reference_scopes(doc):
    """Document, DocumentFolder, User and Team: read all, nothing else. Currency
    (level-based): read yes, edit no."""
    return [f"{name}.{scope}: {(role.get('data') or {}).get(scope)} "
            f"!= read-only {read_only_row(scope)}"
            for name, role in _roles(doc).items() for scope in READ_ONLY_SCOPES
            if (role.get("data") or {}).get(scope) != read_only_row(scope)]


def rule_boolean_scopes(doc):
    """Human roles: Activities, Calendar, GlobalStream and WorkingTimeCalendar true, the
    rest false. ER Import: every boolean scope false (it uses REST, not Espo's Import)."""
    out = []
    for name, role in _roles(doc).items():
        data = role.get("data") or {}
        want = IMPORT_BOOLEAN if name == IMPORT else HUMAN_BOOLEAN
        for scope, value in want.items():
            if data.get(scope) is not value:
                out.append(f"{name}.{scope}: is {data.get(scope)!r}, expected {value!r}")
    return out


def rule_stream_as_read(doc):
    """Every entity scope with the five-action table; level-based scopes have no stream."""
    out = []
    for name, role in _roles(doc).items():
        for scope, actions in (role.get("data") or {}).items():
            if scope in LEVEL_SCOPES:
                continue
            if isinstance(actions, dict) and actions.get("stream") != actions.get("read"):
                out.append(f"{name}.{scope}: stream {actions.get('stream')!r} "
                           f"differs from read {actions.get('read')!r}")
    return out


def rule_no_account_delete(doc):
    """No role (none of them is an admin) may delete an Account."""
    return [f"{name}: Account delete is {(role.get('data') or {}).get('Account', {}).get('delete')!r}"
            for name, role in _roles(doc).items()
            if (role.get("data") or {}).get("Account", {}).get("delete") != "no"]


def rule_staff_edits_own_opportunity(doc):
    level = _data(doc, STAFF).get("Opportunity", {}).get("edit")
    return [] if level == "own" else [f"{STAFF}: Opportunity edit is {level!r}, expected 'own'"]


def rule_intake_edits_all_opportunity(doc):
    level = _data(doc, INTAKE).get("Opportunity", {}).get("edit")
    return [] if level == "all" else [f"{INTAKE}: Opportunity edit is {level!r}, expected 'all'"]


def rule_import_never_deletes(doc):
    """ER Import deletes nothing: every scope is false, a boolean, or has delete 'no'.
    A level-based scope has no delete action (rule_level_scopes refuses one), so it
    passes here unless it carries a delete other than 'no'."""
    return [f"{IMPORT}.{scope}: delete is "
            f"{actions.get('delete') if isinstance(actions, dict) else actions!r}"
            for scope, actions in _data(doc, IMPORT).items()
            if not (actions is False or isinstance(actions, bool) and scope in ACL_BOOLEAN_SCOPES
                    or isinstance(actions, dict) and actions.get("delete") == "no"
                    or scope in LEVEL_SCOPES and isinstance(actions, dict)
                    and actions.get("delete", "no") == "no")]


def rule_import_api_only(doc):
    """ER Import is held only by API users, and every API user holds only it."""
    out = []
    users = doc.get("apiUsers") or []
    if not any(IMPORT in (u.get("roles") or []) for u in users):
        out.append(f"no API user holds {IMPORT}")
    for u in users:
        if (u.get("roles") or []) != [IMPORT]:
            out.append(f"API user {u.get('userName')}: roles {u.get('roles')}, expected [{IMPORT!r}]")
    return out


def rule_service_type_admin_managed(doc):
    """CRM-004: human roles read ServiceType and change nothing; ER Import creates and
    edits it and never deletes."""
    out = []
    for name in ROLES:
        want = _row("yes", "all", "no") if name == IMPORT else _row("no", "no", "no")
        for scope in ADMIN_MANAGED_SCOPES:
            if _data(doc, name).get(scope) != want:
                out.append(f"{name}.{scope}: {_data(doc, name).get(scope)} != {want}")
    return out


def rule_matches_work_order_table(doc):
    out = []
    for name, expected in EXPECTED_DATA.items():
        actual = _data(doc, name)
        for scope in sorted(set(expected) | set(actual)):
            if actual.get(scope) != expected.get(scope):
                out.append(f"{name}.{scope}: {actual.get(scope)} != WO table {expected.get(scope)}")
    return out


# CRM-004 (round 2): Opportunity.sfId is hidden from people as well.
# CRM-005: so is sfId on Call, Meeting, Task and Email.
SF_ID_HIDDEN_ENTITIES = SF_KEY_ENTITIES + ["Opportunity"] + ACTIVITIES + ["Email"]


def rule_staff_and_intake_cannot_edit_email(doc):
    """CRM-005: ER Staff and ER Intake have Email edit 'no' (archived email is history)."""
    return [f"{name}: Email edit is {_data(doc, name).get('Email', {}).get('edit')!r}, "
            "expected 'no'"
            for name in (STAFF, INTAKE)
            if _data(doc, name).get("Email", {}).get("edit") != "no"]


def rule_sf_id_admin_only(doc):
    """Human roles cannot read or edit sfId on User, Account, Contact, Opportunity, Call,
    Meeting, Task or Email."""
    out = []
    for name in NON_ADMIN_HUMAN_ROLES:
        field_data = (_roles(doc).get(name) or {}).get("fieldData") or {}
        for entity in SF_ID_HIDDEN_ENTITIES:
            if (field_data.get(entity) or {}).get("sfId") != {"read": "no", "edit": "no"}:
                out.append(f"{name}: {entity}.sfId is not hidden (read no, edit no)")
    return out


def _field_data(doc, role):
    return (_roles(doc).get(role) or {}).get("fieldData") or {}


def rule_sf_fields_read_only_for_people(doc):
    """Every human role has edit 'no' on every sf* field; the provenance fields
    (sfOwnerId, sfCreatedAt) are readable, sfId stays hidden (sf_id_admin_only)."""
    out = []
    for name in NON_ADMIN_HUMAN_ROLES:
        field_data = _field_data(doc, name)
        for entity, fields in SF_FIELDS.items():
            for field in fields:
                acl = (field_data.get(entity) or {}).get(field) or {}
                if acl.get("edit") != "no":
                    out.append(f"{name}: {entity}.{field} edit is {acl.get('edit')!r}, expected 'no'")
                if field != "sfId" and acl.get("read") != "yes":
                    out.append(f"{name}: {entity}.{field} read is {acl.get('read')!r}, expected 'yes'")
    return out


def rule_import_edits_sf_fields(doc):
    """The importer can read and write every sf* field."""
    field_data = _field_data(doc, IMPORT)
    return [f"{IMPORT}: {entity}.{field} is {(field_data.get(entity) or {}).get(field)}, "
            "expected read yes, edit yes"
            for entity, fields in SF_FIELDS.items() for field in fields
            if (field_data.get(entity) or {}).get(field) != {"read": "yes", "edit": "yes"}]


ROLE_RULES = {
    "teams_and_roles_present": rule_teams_and_roles_present,
    "every_acl_scope_explicit": rule_every_acl_scope_explicit,
    "known_levels": rule_known_levels,
    "level_scopes": rule_level_scopes,
    "unused_scopes_disabled": rule_unused_scopes_disabled,
    "read_only_reference_scopes": rule_read_only_reference_scopes,
    "boolean_scopes": rule_boolean_scopes,
    "stream_as_read": rule_stream_as_read,
    "no_account_delete": rule_no_account_delete,
    "staff_edits_own_opportunity": rule_staff_edits_own_opportunity,
    "intake_edits_all_opportunity": rule_intake_edits_all_opportunity,
    "import_never_deletes": rule_import_never_deletes,
    "import_api_only": rule_import_api_only,
    "service_type_admin_managed": rule_service_type_admin_managed,
    "matches_work_order_table": rule_matches_work_order_table,
    "sf_id_admin_only": rule_sf_id_admin_only,
    "staff_and_intake_cannot_edit_email": rule_staff_and_intake_cannot_edit_email,
    "sf_fields_read_only_for_people": rule_sf_fields_read_only_for_people,
    "import_edits_sf_fields": rule_import_edits_sf_fields,
}


def check_roles(doc):
    return {name: fn(doc) for name, fn in ROLE_RULES.items()}


# --- Salesforce key and audit rules --------------------------------------------------

def _fields(defs, entity):
    return (defs.get(entity) or {}).get("fields") or {}


def rule_sf_id_field(defs):
    out = []
    for entity in SF_KEY_ENTITIES:
        f = _fields(defs, entity).get("sfId")
        if not isinstance(f, dict):
            out.append(f"{entity}: no sfId field")
            continue
        for key, want in (("type", "varchar"), ("maxLength", 18), ("readOnlyAfterCreate", True),
                          ("isCustom", True)):
            if f.get(key) != want:
                out.append(f"{entity}.sfId: {key} is {f.get(key)!r}, expected {want!r}")
        if f.get("audited"):
            out.append(f"{entity}.sfId must not be audited")
    return out


def rule_sf_id_unique_index(defs):
    out = []
    for entity in SF_KEY_ENTITIES:
        indexes = (defs.get(entity) or {}).get("indexes") or {}
        if indexes.get("sfId") != {"type": "unique", "columns": ["sfId"]}:
            out.append(f"{entity}: index 'sfId' is not unique on [sfId]: {indexes.get('sfId')}")
    return out


def rule_sf_provenance_fields(defs):
    out = []
    for entity in ("Account", "Contact"):
        for name, kind in SF_EXTRA.items():
            f = _fields(defs, entity).get(name) or {}
            if f.get("type") != kind or f.get("isCustom") is not True:
                out.append(f"{entity}.{name}: must be a custom {kind}")
            elif kind == "varchar" and f.get("maxLength") != 18:
                out.append(f"{entity}.{name}: maxLength must be 18")
            if f.get("audited"):
                out.append(f"{entity}.{name} must not be audited")
    return out


def rule_sf_fields_not_read_only(defs):
    """No sf* field carries readOnly: EspoCRM turns it into a global restriction that
    also blocks the importer's API user. sfId uses readOnlyAfterCreate instead."""
    out = []
    for entity in SF_KEY_ENTITIES:
        for name, f in _fields(defs, entity).items():
            if name.startswith("sf") and isinstance(f, dict) and f.get("readOnly"):
                out.append(f"{entity}.{name}: readOnly is {f['readOnly']!r}; "
                           "use readOnlyAfterCreate or role fieldData")
    return out


def rule_audited_fields(defs):
    out = []
    for entity, names in AUDITED.items():
        for name in names:
            if (_fields(defs, entity).get(name) or {}).get("audited") is not True:
                out.append(f"{entity}.{name} is not audited")
    return out


KEY_RULES = {
    "sf_id_field": rule_sf_id_field,
    "sf_id_unique_index": rule_sf_id_unique_index,
    "sf_provenance_fields": rule_sf_provenance_fields,
    "sf_fields_not_read_only": rule_sf_fields_not_read_only,
    "audited_fields": rule_audited_fields,
}


def check_keys(defs):
    return {name: fn(defs) for name, fn in KEY_RULES.items()}


# --- the deletion-guard hook (static: php is not available in the loop) -----------------

def _code(source):
    """PHP source with comments removed, so a commented-out guard does not count."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    source = re.sub(r"(^|[^:])//.*$", r"\1", source, flags=re.M)
    return re.sub(r"^\s*#.*$", "", source, flags=re.M)


def rule_hook_shape(source):
    code = _code(source)
    out = []
    if not re.search(r"^\s*namespace\s+Espo\\Custom\\Hooks\\Account\s*;", code, re.M):
        out.append("namespace is not Espo\\Custom\\Hooks\\Account")
    if not re.search(r"^\s*use\s+Espo\\Core\\Hook\\Hook\\BeforeRemove\s*;", code, re.M):
        out.append("does not import Espo\\Core\\Hook\\Hook\\BeforeRemove")
    if not re.search(r"\bclass\s+RestrictDeleteWithEnquiries\s+implements\s+BeforeRemove\b", code):
        out.append("class RestrictDeleteWithEnquiries does not implement BeforeRemove")
    if not re.search(r"public\s+function\s+beforeRemove\s*\(\s*Entity\s+\$entity\s*,\s*"
                     r"RemoveOptions\s+\$options\s*\)\s*:\s*void", code):
        out.append("beforeRemove(Entity $entity, RemoveOptions $options): void is missing")
    return out


def rule_hook_counts_opportunities(source):
    code = _code(source)
    if re.search(r"getRelation\(\s*\$entity\s*,\s*'opportunities'\s*\)\s*->\s*count\(\)", code):
        return []
    return ["the hook does not count the Account's 'opportunities' relation"]


def rule_hook_throws_forbidden(source):
    code = _code(source)
    out = []
    if not re.search(r"^\s*use\s+Espo\\Core\\Exceptions\\Forbidden\s*;", code, re.M):
        out.append("does not import Espo\\Core\\Exceptions\\Forbidden")
    if not re.search(r"if\s*\(\s*\$\w+\s*>\s*0\s*\)\s*\{\s*throw\s+new\s+Forbidden\s*\(", code):
        out.append("does not throw Forbidden when the count is above zero")
    return out


def rule_hook_no_admin_bypass(source):
    """The guard applies to admins too: no user, admin or ACL condition, no early return."""
    code = _code(source)
    out = []
    if re.search(r"isAdmin|\bUser\b|\bAcl\b|skipHooks|SKIP_HOOKS|\$options\s*->", code):
        out.append("the hook consults the user, ACL or options (admins must not bypass it)")
    if re.search(r"\breturn\s*;", code):
        out.append("the hook has an early return")
    return out


def _method_body(code, name):
    """The body of method `name` (between its braces), or None."""
    m = re.search(r"function\s+" + name + r"\s*\([^)]*\)\s*(?::\s*\w+\s*)?\{", code)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(code) and depth:
        depth += {"{": 1, "}": -1}.get(code[i], 0)
        i += 1
    return code[m.end():i - 1] if depth == 0 else None


# The whole of beforeRemove: count Account.opportunities into a variable, and throw
# Forbidden (with a literal message) if it is above zero. Nothing else, so arithmetic
# on the count (`->count() * 0`), a short-circuited condition (`if (false && ...)`), an
# early return or any other statement before the throw does not match.
_GUARD_BODY = re.compile(
    r"\s*\$(?P<v>\w+)\s*=\s*\$this\s*->\s*entityManager\s*"
    r"->\s*getRDBRepository\(\s*'Account'\s*\)\s*"
    r"->\s*getRelation\(\s*\$entity\s*,\s*'opportunities'\s*\)\s*"
    r"->\s*count\(\s*\)\s*;"
    r"\s*if\s*\(\s*\$(?P=v)\s*>\s*0\s*\)\s*\{"
    r"\s*throw\s+new\s+Forbidden\(\s*'[^'\\]*'(?:\s*\.\s*'[^'\\]*')*\s*\)\s*;"
    r"\s*\}\s*")


def rule_hook_body_is_the_guard(source):
    body = _method_body(_code(source), "beforeRemove")
    if body is None:
        return ["no beforeRemove body found"]
    if not _GUARD_BODY.fullmatch(body):
        return ["beforeRemove is not exactly: count Account.opportunities; "
                "if (count > 0) { throw new Forbidden('...'); }"]
    return []


HOOK_RULES = {
    "hook_shape": rule_hook_shape,
    "hook_counts_opportunities": rule_hook_counts_opportunities,
    "hook_throws_forbidden": rule_hook_throws_forbidden,
    "hook_no_admin_bypass": rule_hook_no_admin_bypass,
    "hook_body_is_the_guard": rule_hook_body_is_the_guard,
}


def check_hook(source):
    return {name: fn(source) for name, fn in HOOK_RULES.items()}
