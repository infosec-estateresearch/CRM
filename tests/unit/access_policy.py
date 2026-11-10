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
OTHER_SCOPES = ["Case", "Document", "User", "Team"]
ACTIONS = ["create", "read", "edit", "delete", "stream"]
LEVELS = {"create": {"yes", "no"}, "read": {"all", "team", "own", "no"},
          "edit": {"all", "team", "own", "no"}, "delete": {"all", "team", "own", "no"},
          "stream": {"all", "team", "own", "no"}}
SF_KEY_ENTITIES = ["User", "Account", "Contact"]
SF_EXTRA = {"sfOwnerId": "varchar", "sfCreatedAt": "datetime"}
# Every Salesforce key field, by entity. None of them may be readOnly (the global
# restriction would stop the importer too); people are kept off them by fieldData.
SF_FIELDS = {"User": ["sfId"], "Account": ["sfId"] + list(SF_EXTRA),
             "Contact": ["sfId"] + list(SF_EXTRA)}
AUDITED = {"Account": ["name", "type", "industry", "assignedUser", "parent",
                       "learningPlatformAccess"],
           "Contact": ["account", "emailAddress"]}


def _row(create, edit, delete):
    return {"create": create, "read": "all", "edit": edit, "delete": delete, "stream": "all"}


# The WO CRM-003 item 2 table, transcribed independently of config/access/roles.json.
_OTHERS = {s: _row("no", "no", "no") for s in OTHER_SCOPES}
EXPECTED_DATA = {
    STAFF: dict({"Account": _row("yes", "all", "no"), "Contact": _row("yes", "all", "no"),
                 "Opportunity": _row("yes", "own", "no"), "Email": _row("yes", "own", "no")},
                **{a: _row("yes", "own", "own") for a in ACTIVITIES}, **_OTHERS),
    INTAKE: dict({"Account": _row("yes", "all", "no"), "Contact": _row("yes", "all", "no"),
                  "Opportunity": _row("yes", "all", "no"), "Email": _row("yes", "own", "no")},
                 **{a: _row("yes", "own", "own") for a in ACTIVITIES}, **_OTHERS),
    MANAGER: dict({"Account": _row("yes", "all", "no"), "Contact": _row("yes", "all", "all"),
                   "Opportunity": _row("yes", "all", "all"), "Email": _row("yes", "all", "no")},
                  **{a: _row("yes", "all", "all") for a in ACTIVITIES}, **_OTHERS),
    IMPORT: dict({s: _row("yes", "all", "no") for s in MAIN_SCOPES}, **_OTHERS),
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


def rule_known_levels(doc):
    """Every role covers every scope with exactly the five actions, at valid levels."""
    out = []
    for name, role in _roles(doc).items():
        data = role.get("data") or {}
        for scope in MAIN_SCOPES + OTHER_SCOPES:
            if scope not in data:
                out.append(f"{name}: no access defined for {scope}")
        for scope, actions in data.items():
            if not isinstance(actions, dict) or sorted(actions) != sorted(ACTIONS):
                out.append(f"{name}.{scope}: actions must be exactly {ACTIONS}")
                continue
            for action, level in actions.items():
                if level not in LEVELS[action]:
                    out.append(f"{name}.{scope}.{action}: invalid level {level!r}")
    return out


def rule_stream_as_read(doc):
    out = []
    for name, role in _roles(doc).items():
        for scope, actions in (role.get("data") or {}).items():
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
    return [f"{IMPORT}.{scope}: delete is {actions.get('delete')!r}"
            for scope, actions in _data(doc, IMPORT).items()
            if not isinstance(actions, dict) or actions.get("delete") != "no"]


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


def rule_matches_work_order_table(doc):
    out = []
    for name, expected in EXPECTED_DATA.items():
        actual = _data(doc, name)
        for scope in sorted(set(expected) | set(actual)):
            if actual.get(scope) != expected.get(scope):
                out.append(f"{name}.{scope}: {actual.get(scope)} != WO table {expected.get(scope)}")
    return out


def rule_sf_id_admin_only(doc):
    """Human roles cannot read or edit sfId on User, Account or Contact."""
    out = []
    for name in NON_ADMIN_HUMAN_ROLES:
        field_data = (_roles(doc).get(name) or {}).get("fieldData") or {}
        for entity in SF_KEY_ENTITIES:
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
    "known_levels": rule_known_levels,
    "stream_as_read": rule_stream_as_read,
    "no_account_delete": rule_no_account_delete,
    "staff_edits_own_opportunity": rule_staff_edits_own_opportunity,
    "intake_edits_all_opportunity": rule_intake_edits_all_opportunity,
    "import_never_deletes": rule_import_never_deletes,
    "import_api_only": rule_import_api_only,
    "matches_work_order_table": rule_matches_work_order_table,
    "sf_id_admin_only": rule_sf_id_admin_only,
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


HOOK_RULES = {
    "hook_shape": rule_hook_shape,
    "hook_counts_opportunities": rule_hook_counts_opportunities,
    "hook_throws_forbidden": rule_hook_throws_forbidden,
    "hook_no_admin_bypass": rule_hook_no_admin_bypass,
}


def check_hook(source):
    return {name: fn(source) for name, fn in HOOK_RULES.items()}
