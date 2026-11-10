"""Activity and archived-email policy for CRM-005, standard library only.

Each rule takes a "bundle" (see load_bundle) and returns a list of violation strings;
an empty list means the rule holds. test_activities.py breaks every rule with a
mutated copy of the repository bundle to show it can fail.

The archived-email hook is checked statically (php is not available in the loop),
and its decision table is mirrored by archived_save_allowed below.
"""

import json
import os
import re

import enquiry_policy

REPO = enquiry_policy.REPO
CUSTOM = enquiry_policy.CUSTOM
RES = enquiry_policy.RES
HOOK_PATH = os.path.join(CUSTOM, "Hooks", "Email", "ProtectArchivedEmail.php")
DASHBOARDS_PATH = os.path.join(REPO, "config", "access", "dashboards.json")
TEAMS_PATH = os.path.join(REPO, "config", "access", "teams.json")

ENTITIES = ["Call", "Meeting", "Task", "Email"]
LEGACY_TYPES = {"sfId": "varchar", "sfOwnerId": "varchar", "sfCreatedAt": "datetime"}
EMAIL_LEGACY_TYPES = dict(LEGACY_TYPES, sfEmailMessageId="varchar",
                          sfThreadIdentifier="varchar", sfActivityId="varchar")
LEGACY = {e: EMAIL_LEGACY_TYPES if e == "Email" else LEGACY_TYPES for e in ENTITIES}
# Salesforce ids are 18 characters; the thread identifier is free text.
MAX_LENGTH = {"sfId": 18, "sfOwnerId": 18, "sfEmailMessageId": 18, "sfActivityId": 18,
              "sfThreadIdentifier": 255}
MEETING_TYPES = ["Meeting", "Presentation", "Bag Drop", "Call", "Other", "Email",
                 "Unspecified (legacy)"]
# Core fields of 10.0.12 (verified by the PL) that the custom layouts may name.
CORE_FIELDS = {
    "Call": {"name", "status", "direction", "dateStart", "dateEnd", "duration", "reminders",
             "description", "parent", "account", "users", "contacts", "leads", "assignedUser",
             "teams"},
    "Meeting": {"name", "status", "dateStart", "dateEnd", "isAllDay", "duration", "reminders",
                "description", "parent", "account", "users", "contacts", "leads",
                "assignedUser", "teams"},
    "Task": {"name", "status", "priority", "dateStart", "dateEnd", "reminders", "description",
             "parent", "account", "contact", "attachments", "assignedUser", "teams"},
}
# The archived-email guard: the attributes it protects and the one API user it exempts.
PROTECTED_ATTRIBUTES = ["name", "body", "bodyPlain", "isHtml", "from", "to", "cc", "bcc",
                        "fromString", "dateSent", "messageId", "status"]
IMPORT_ROLE = enquiry_policy.IMPORT_ROLE


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _layouts(entity):
    d = os.path.join(RES, "layouts", entity)
    return {n[:-5]: _json(os.path.join(d, n)) for n in os.listdir(d)} if os.path.isdir(d) else {}


def load_bundle():
    """Everything the rules look at, as plain data (so a test can mutate a copy)."""
    return {
        "defs": {e: _json(os.path.join(RES, "metadata", "entityDefs", f"{e}.json"))
                 for e in ENTITIES},
        "i18n": {e: _json(os.path.join(RES, "i18n", "en_US", f"{e}.json")) for e in ENTITIES},
        "layouts": {e: _layouts(e) for e in ENTITIES},
        "hook": _text(HOOK_PATH),
        "apiUsers": _json(enquiry_policy.API_USERS_PATH).get("apiUsers") or [],
        "dashboards": _json(DASHBOARDS_PATH).get("dashboardTemplates") or [],
        "teams": [t.get("name") for t in _json(TEAMS_PATH).get("teams") or []],
    }


def _fields(b, entity):
    return ((b.get("defs") or {}).get(entity) or {}).get("fields") or {}


layout_names = enquiry_policy.layout_names


# --- the archived-email rule, as a decision table (mirrors ProtectArchivedEmail.php) ---

def archived_save_allowed(is_new, fetched_status, is_admin, is_import_user, changed):
    """WO CRM-005 item 2: may this Email save go ahead? changed is the set of changed
    attributes; is_import_user means type api and userName 'er-import'."""
    if is_new or fetched_status != "Archived":
        return True
    if is_admin or is_import_user:
        return True
    return not set(changed) & set(PROTECTED_ATTRIBUTES)


# --- entityDefs rules ---------------------------------------------------------------

def rule_legacy_fields(b):
    """Amendment v1.1: no legacy field is readOnly; sfId alone is readOnlyAfterCreate;
    all are custom, typed, unaudited and kept out of list and mass update."""
    out = []
    for entity, types in LEGACY.items():
        fields = _fields(b, entity)
        for name, kind in types.items():
            f = fields.get(name) or {}
            where = f"{entity}.{name}"
            if f.get("type") != kind or f.get("isCustom") is not True:
                out.append(f"{where}: must be a custom {kind}")
            if kind == "varchar" and f.get("maxLength") != MAX_LENGTH[name]:
                out.append(f"{where}: maxLength must be {MAX_LENGTH[name]}")
            if "readOnly" in f:
                out.append(f"{where}: readOnly is set (global restriction would block ER Import)")
            if f.get("readOnlyAfterCreate") is not (True if name == "sfId" else None):
                out.append(f"{where}: only sfId is (and must be) readOnlyAfterCreate")
            if f.get("audited"):
                out.append(f"{where}: must not be audited")
            if f.get("layoutListDisabled") is not True or \
                    f.get("layoutMassUpdateDisabled") is not True:
                out.append(f"{where}: must be list- and mass-update-disabled")
        for name in fields:
            if name.startswith("sf") and name not in types:
                out.append(f"{entity}.{name}: not a legacy field of this WO")
        if "messageId" in fields:
            out.append(f"{entity}: redefines the core messageId")
    return out


def rule_unique_indexes(b):
    return [f"{e}: index 'sfId' is not unique on [sfId]"
            for e in ENTITIES
            if (((b.get("defs") or {}).get(e) or {}).get("indexes") or {}).get("sfId") !=
            {"type": "unique", "columns": ["sfId"]}]


def rule_meeting_type(b):
    f = _fields(b, "Meeting").get("meetingType") or {}
    out = []
    if f.get("type") != "enum" or f.get("isCustom") is not True:
        out.append("Meeting.meetingType must be a custom enum")
    if f.get("options") != MEETING_TYPES:
        out.append(f"meetingType options {f.get('options')} != {MEETING_TYPES}")
    if f.get("default") not in MEETING_TYPES:
        out.append("meetingType default must be one of its options")
    if f.get("readOnly") or f.get("readOnlyAfterCreate"):
        out.append("meetingType must stay editable")
    for e in ("Call", "Task", "Email"):
        if "meetingType" in _fields(b, e):
            out.append(f"{e} must not define meetingType")
    return out


# --- layouts ------------------------------------------------------------------------

def rule_layouts(b):
    """Meeting list and detail show meetingType; every custom detail layout ends with a
    collapsed Legacy panel holding exactly the legacy fields, which appear nowhere else;
    every named field exists."""
    out = []
    layouts = b.get("layouts") or {}
    meeting = layouts.get("Meeting") or {}
    for name in ("list", "detail"):
        if "meetingType" not in layout_names(meeting.get(name) or []):
            out.append(f"Meeting {name} layout does not show meetingType")
    for entity, by_name in layouts.items():
        legacy = set(LEGACY[entity])
        known = CORE_FIELDS.get(entity, set()) | set(_fields(b, entity))
        for lname, data in by_name.items():
            for n in layout_names(data):
                if n not in known:
                    out.append(f"{entity}/{lname}: unknown field {n!r}")
            if lname != "detail":
                shown = set(layout_names(data)) & legacy
                if shown:
                    out.append(f"{entity}/{lname}: shows legacy fields {sorted(shown)}")
                continue
            panels = [p for p in data if isinstance(p, dict)]
            last = panels[-1] if panels else {}
            if last.get("label") != "Legacy" or last.get("collapsed") is not True or \
                    sorted(layout_names([last])) != sorted(legacy):
                out.append(f"{entity}/detail: must end with a collapsed Legacy panel of "
                           f"{sorted(legacy)}")
            for p in panels[:-1]:
                if set(layout_names([p])) & legacy:
                    out.append(f"{entity}/detail: legacy field outside the Legacy panel")
    if "Email" in layouts and layouts["Email"]:
        out.append("Email layouts are core (archived body shown via isHtml false, see "
                   "docs/ACTIVITIES.md)")
    return out


# --- labels -------------------------------------------------------------------------

def rule_labels(b):
    out = []
    for entity in ENTITIES:
        i18n = (b.get("i18n") or {}).get(entity) or {}
        for name, f in _fields(b, entity).items():
            if f.get("isCustom") and name not in (i18n.get("fields") or {}):
                out.append(f"{entity}: no label for {name}")
            if f.get("type") == "enum" and set((i18n.get("options") or {}).get(name) or {}) != \
                    set(f.get("options") or []):
                out.append(f"{entity}: option labels for {name} do not match its options")
    return out


# --- dashboard template -------------------------------------------------------------

def rule_dashboard_template(b):
    """An "ER Staff" template with a "My open tasks" Tasks dashlet and a Calendar dashlet,
    deployed (only on request) to a team that exists."""
    found = [t for t in b.get("dashboards") or [] if t.get("name") == "ER Staff"]
    if len(found) != 1:
        return ["exactly one dashboard template must be named 'ER Staff'"]
    t = found[0]
    out = []
    dashlets = [d for tab in t.get("layout") or [] for d in tab.get("layout") or []]
    options = t.get("dashletsOptions") or {}
    tasks = [d for d in dashlets if d.get("name") == "Tasks"]
    if len(tasks) != 1 or (options.get(tasks[0].get("id")) or {}).get("title") != "My open tasks":
        out.append("ER Staff needs one Tasks dashlet titled 'My open tasks'")
    if [d.get("name") for d in dashlets].count("Calendar") != 1:
        out.append("ER Staff needs one Calendar dashlet")
    ids = [d.get("id") for d in dashlets]
    if len(set(ids)) != len(ids) or not set(options) <= set(ids):
        out.append("dashlet ids must be unique and dashletsOptions keyed by them")
    teams = t.get("deployToTeams") or []
    if not teams or not set(teams) <= set(b.get("teams") or []):
        out.append(f"deployToTeams {teams} must name existing teams")
    return out


# --- the archived-email hook (static) -----------------------------------------------

_php = enquiry_policy._php
_method_body = enquiry_policy._method_body

# The whole of beforeSave, statement by statement (see archived_save_allowed).
_HOOK_BODY = re.compile(r"""
\s*if\s*\(\s*\$entity->isNew\(\)\s*\)\s*\{\s*return\s*;\s*\}
\s*if\s*\(\s*\$entity->getFetched\('status'\)\s*!==\s*'Archived'\s*\)\s*\{\s*return\s*;\s*\}
\s*if\s*\(\s*\$this->user->isAdmin\(\)\s*\)\s*\{\s*return\s*;\s*\}
\s*\$isImportUser\s*=\s*\$this->user->getType\(\)\s*===\s*User::TYPE_API\s*&&
\s*\$this->user->getUserName\(\)\s*===\s*'(?P<user>[^'\\]+)'\s*;
\s*if\s*\(\s*\$isImportUser\s*\)\s*\{\s*return\s*;\s*\}
\s*foreach\s*\(\s*self:{2}PROTECTED_ATTRIBUTES\s+as\s+\$attribute\s*\)\s*\{
\s*if\s*\(\s*\$entity->isAttributeChanged\(\$attribute\)\s*\)\s*\{
\s*throw\s+new\s+Forbidden\(\s*'[^'\\]*'\s*\)\s*;
\s*\}\s*\}\s*
""", re.X)
_PROTECTED = re.compile(r"private\s+const\s+PROTECTED_ATTRIBUTES\s*=\s*\[(?P<list>[^\]]*)\]\s*;")


def rule_hook_shape(b):
    code = _php(b.get("hook") or "")
    out = []
    for pattern, msg in (
            (r"^\s*namespace\s+Espo\\Custom\\Hooks\\Email\s*;", "namespace"),
            (r"^\s*use\s+Espo\\Core\\Hook\\Hook\\BeforeSave\s*;", "use BeforeSave"),
            (r"^\s*use\s+Espo\\Core\\Exceptions\\Forbidden\s*;", "use Forbidden"),
            (r"^\s*use\s+Espo\\Entities\\User\s*;", "use User"),
            (r"\bclass\s+ProtectArchivedEmail\s+implements\s+BeforeSave\b",
             "implements BeforeSave"),
            (r"__construct\(\s*private\s+User\s+\$user\s*\)", "injects the current User"),
            (r"public\s+function\s+beforeSave\s*\(\s*Entity\s+\$entity\s*,\s*SaveOptions\s+"
             r"\$options\s*\)\s*:\s*void", "beforeSave signature")):
        if not re.search(pattern, code, re.M):
            out.append(f"hook: {msg} missing")
    return out


def import_user_names(b):
    return [u.get("userName") for u in b.get("apiUsers") or []
            if isinstance(u, dict) and IMPORT_ROLE in (u.get("roles") or [])]


def rule_hook_body(b):
    code = _php(b.get("hook") or "")
    body = _method_body(code, "beforeSave")
    match = _HOOK_BODY.fullmatch(body) if body is not None else None
    if not match:
        return ["beforeSave is not exactly the archived-email rule (see archived_save_allowed)"]
    out = []
    names = import_user_names(b)
    if names != [match.group("user")]:
        out.append(f"hook exempts API user {match.group('user')!r}, but the ER Import API "
                   f"users in api_users.json are {names}")
    const = _PROTECTED.search(code)
    listed = re.findall(r"'([^'\\]*)'", const.group("list")) if const else None
    if listed != PROTECTED_ATTRIBUTES:
        out.append(f"PROTECTED_ATTRIBUTES {listed} != {PROTECTED_ATTRIBUTES}")
    return out


RULES = {
    "legacy_fields": rule_legacy_fields,
    "unique_indexes": rule_unique_indexes,
    "meeting_type": rule_meeting_type,
    "layouts": rule_layouts,
    "labels": rule_labels,
    "dashboard_template": rule_dashboard_template,
    "hook_shape": rule_hook_shape,
    "hook_body": rule_hook_body,
}


def check(bundle):
    return {name: fn(bundle) for name, fn in RULES.items()}
