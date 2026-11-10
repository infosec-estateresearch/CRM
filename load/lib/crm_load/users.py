"""``crm-load users``: users.json for scripts/provision_users.py (CRM-003). Never creates users.

Input format of provision_users.py: a JSON list of {sfId, userName, firstName, lastName,
emailAddress, isActive, teams[], roles[]}. Teams and roles come only from the
operator-supplied --role-map (Profile name and UserRole name -> teams/roles). Shared logins
listed in ``legacyShared.sfIds`` become the inactive legacy user (D4); inactive Salesforce
users stay inactive (D5).
"""

import json
import re

from .errors import LoadError

USER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,49}$")
SF_ID = re.compile(r"^[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?$")


def load_role_map(path):
    try:
        with open(path, "rb") as fh:
            doc = json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        raise LoadError("role_map_unreadable") from None
    if not isinstance(doc, dict):
        raise LoadError("role_map_invalid")
    for section in ("profiles", "userRoles"):
        table = doc.get(section, {})
        if not isinstance(table, dict):
            raise LoadError("role_map_invalid")
        for entry in table.values():
            if not isinstance(entry, dict) or not all(isinstance(entry.get(k, []), list) for k in ("teams", "roles")):
                raise LoadError("role_map_invalid")
    shared = doc.get("legacyShared", {})
    if not isinstance(shared, dict) or not isinstance(shared.get("sfIds", []), list):
        raise LoadError("role_map_invalid")
    return doc


def _user_name(row):
    """The Salesforce Username's local part, if it is a valid EspoCRM user name."""
    raw = row.get("Username")
    if not isinstance(raw, str):
        return None
    local = raw.split("@", 1)[0]
    return local if USER_NAME.fullmatch(local) else None


def build_users(snapshot, role_map):
    """Returns (users list, [(sfId, reason)] for the exceptions file, skipped count).

    Only UserType ``Standard`` is exported; the others (integration, automated, CsnOnly)
    are counted as skipped (``user_not_human``). Records they own resolve to an
    unresolved-owner exception at load time."""
    profiles = {r["Id"]: r.get("Name") for r in snapshot.rows("Profile")}
    roles = {r["Id"]: r.get("Name") for r in snapshot.rows("UserRole")}
    shared = role_map.get("legacyShared", {})
    shared_ids = set(shared.get("sfIds", []))
    users, problems, skipped = [], [], 0
    for row in snapshot.rows("User"):
        if row.get("UserType") != "Standard":
            skipped += 1
            continue
        sf_id = row.get("Id")
        if not isinstance(sf_id, str) or not SF_ID.fullmatch(sf_id):
            continue
        teams, eroles = [], []
        for table, key in ((role_map.get("profiles", {}), profiles.get(row.get("ProfileId"))),
                           (role_map.get("userRoles", {}), roles.get(row.get("UserRoleId")))):
            entry = table.get(key) if isinstance(key, str) else None
            if entry:
                teams += entry.get("teams", [])
                eroles += entry.get("roles", [])
        user = {"sfId": sf_id, "userName": _user_name(row), "firstName": row.get("FirstName"),
                "lastName": row.get("LastName"), "emailAddress": row.get("Email"),
                "isActive": row.get("IsActive") is True,
                "teams": sorted(set(teams)), "roles": sorted(set(eroles))}
        if sf_id in shared_ids:
            user.update(isActive=False, firstName=shared.get("firstName"), lastName=shared.get("lastName"),
                        teams=sorted(set(shared.get("teams", []))), roles=sorted(set(shared.get("roles", []))))
        if user["userName"] is None or not user["lastName"]:
            problems.append((sf_id, "user_not_exportable"))
            continue
        users.append(user)
    return users, problems, skipped
