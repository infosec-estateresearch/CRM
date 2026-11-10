#!/usr/bin/env python3
"""Provision EspoCRM teams, roles and the ER Import API user from config/access (CRM-003).

Standard library only; HTTP goes through scripts/crm_api.py.

Usage (operator stage; credentials only in the environment):

    python3 scripts/provision_access.py dev --key-file /root/crm-import-key.env
    python3 scripts/provision_access.py dev --key-file ... --import-user-active no   # after the load

- The first argument names the target environment and must be exactly "dev"
  (exit 2 otherwise), as for the shell scripts' dev guard.
- Teams and roles are created or updated by name, so a second run changes
  nothing. Roles are compared field by field and only differences are sent.
- The ER Import API user (config/access/api_users.json) is created with the
  API-key auth method. EspoCRM generates the key; it is written only to
  --key-file, which must not exist and is created mode 0600. An existing API
  user keeps its key: nothing is written and the file is not created.
- Nothing secret is printed: progress goes to stderr by name, a summary to stdout.

Credentials come from CRM_ADMIN_USERNAME / CRM_ADMIN_PASSWORD; the base URL from
--base-url or CRM_BASE_URL.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import crm_api  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_DIR = os.path.join(REPO, "config", "access")
TARGET_ENV = "dev"

# Role attributes managed from config/access/roles.json (EspoCRM 10.0.12 Role fields).
ROLE_PERMISSIONS = (
    "assignmentPermission", "userPermission", "messagePermission", "portalPermission",
    "groupEmailAccountPermission", "exportPermission", "massUpdatePermission",
    "dataPrivacyPermission", "followerManagementPermission", "auditPermission",
    "mentionPermission", "userCalendarPermission", "lockPermission",
)
ROLE_ATTRIBUTES = ("info", "data", "fieldData") + ROLE_PERMISSIONS


class ProvisionError(RuntimeError):
    """A refusal or inconsistency; the message never contains a secret."""


def log(msg):
    print(msg, file=sys.stderr)


def require_target(argv_target, prog):
    """The environment guard: exactly 'dev'. Returns an exit code or None."""
    if argv_target != TARGET_ENV:
        print(f"{prog}: refusing to run: target environment must be '{TARGET_ENV}' "
              f"(got '{argv_target or '<none>'}')", file=sys.stderr)
        return 2
    return None


# --- private output files ----------------------------------------------------

def check_new_private_path(path):
    """Fail before any API call unless path does not exist and its directory does."""
    if not path:
        raise ProvisionError("an output file path is required")
    if os.path.lexists(path):
        raise ProvisionError(f"refusing to overwrite an existing file: {path}")
    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        raise ProvisionError(f"output directory does not exist: {parent}")


def create_private_file(path):
    """Open a new file for writing, mode 0600, never following or replacing anything."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        raise ProvisionError(f"refusing to overwrite an existing file: {path}") from None
    except OSError as err:
        raise ProvisionError(f"cannot create {path}: {err.strerror}") from None
    os.fchmod(fd, 0o600)  # independent of the umask
    return os.fdopen(fd, "w", encoding="utf-8", newline="")


# --- configuration -------------------------------------------------------------

def _load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as err:
        raise ProvisionError(f"cannot read {path}: {err}") from None


def load_config(config_dir=CONFIG_DIR):
    teams = _load_json(os.path.join(config_dir, "teams.json")).get("teams")
    roles = _load_json(os.path.join(config_dir, "roles.json")).get("roles")
    api_users = _load_json(os.path.join(config_dir, "api_users.json")).get("apiUsers")
    if not isinstance(teams, list) or not isinstance(roles, list) or not isinstance(api_users, list):
        raise ProvisionError(f"{config_dir}: teams, roles and apiUsers must be lists")
    for kind, items in (("team", teams), ("role", roles), ("API user", api_users)):
        key = "userName" if kind == "API user" else "name"
        names = [i.get(key) for i in items]
        if not all(isinstance(n, str) and n.strip() for n in names):
            raise ProvisionError(f"every {kind} needs a non-empty {key}")
        if len(set(names)) != len(names):
            raise ProvisionError(f"duplicate {kind} {key} in {config_dir}")
    role_names = {r["name"] for r in roles}
    team_names = {t["name"] for t in teams}
    for role in roles:
        unknown = set(role) - {"name"} - set(ROLE_ATTRIBUTES)
        if unknown:
            raise ProvisionError(f"role {role['name']}: unknown attributes {sorted(unknown)}")
    for user in api_users:
        if not set(user.get("roles", [])) <= role_names:
            raise ProvisionError(f"API user {user['userName']}: unknown role")
        if not set(user.get("teams", [])) <= team_names:
            raise ProvisionError(f"API user {user['userName']}: unknown team")
    return {"teams": teams, "roles": roles, "apiUsers": api_users}


def api_only_roles(config):
    """Roles assigned to API users in config; regular users may never hold them."""
    return {r for u in config["apiUsers"] for r in u.get("roles", [])}


# --- API helpers ---------------------------------------------------------------

def find(client, entity, conditions, select="id"):
    params = crm_api.where_params(conditions)
    params["select"] = select
    return client.list_all(entity, params)


def find_one(client, entity, conditions, what):
    rows = find(client, entity, conditions)
    if len(rows) > 1:
        raise ProvisionError(f"{len(rows)} {entity} records match {what}; expected at most one")
    return rows[0] if rows else None


def get(client, entity, record_id):
    return client.call("GET", f"{entity}/{record_id}")


def update(client, entity, record_id, data):
    return client.call("PUT", f"{entity}/{record_id}", data=data)


def _same(a, b):
    """Order-insensitive for id lists; exact otherwise (JSON documents compare as values)."""
    if isinstance(a, list) and isinstance(b, list) and all(isinstance(x, str) for x in a + b):
        return sorted(a) == sorted(b)
    if isinstance(a, dict) and isinstance(b, dict):
        return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    return a == b


def diff(current, desired):
    """Attributes of desired whose value differs from current."""
    return {k: v for k, v in desired.items() if not _same(current.get(k), v)}


class Counter:
    def __init__(self):
        self.counts = {}

    def add(self, kind, outcome):
        self.counts.setdefault(kind, {"created": 0, "updated": 0, "unchanged": 0})
        self.counts[kind][outcome] += 1


def ensure_by_name(client, entity, desired, counter, kind):
    """Create or update one Team/Role by name. Returns its id."""
    name = desired["name"]
    found = find_one(client, entity, [("equals", "name", name)], f"name {name!r}")
    if found is None:
        record = client.create(entity, desired)
        counter.add(kind, "created")
        log(f"{kind} {name}: created")
        return record["id"]
    changes = diff(get(client, entity, found["id"]), desired)
    if changes:
        update(client, entity, found["id"], changes)
        counter.add(kind, "updated")
        log(f"{kind} {name}: updated ({', '.join(sorted(changes))})")
    else:
        counter.add(kind, "unchanged")
        log(f"{kind} {name}: unchanged")
    return found["id"]


def name_ids(client, entity, names):
    """{name: id} for every name; fails if one is missing in EspoCRM."""
    out = {}
    for name in names:
        found = find_one(client, entity, [("equals", "name", name)], f"name {name!r}")
        if found is None:
            raise ProvisionError(f"{entity} {name!r} does not exist; run provision_access.py first")
        out[name] = found["id"]
    return out


def ensure_api_user(client, spec, role_ids, team_ids, key_file, active, counter):
    """Create or update an API user. A new user's key goes to key_file only."""
    user_name = spec["userName"]
    desired = {
        "rolesIds": [role_ids[r] for r in spec.get("roles", [])],
        "teamsIds": [team_ids[t] for t in spec.get("teams", [])],
        "authMethod": "ApiKey",
    }
    found = find_one(client, "User", [("equals", "userName", user_name)],
                     f"userName {user_name!r}")
    if found is None:
        data = dict(desired, userName=user_name, type="api", lastName=spec.get("lastName", user_name),
                    isActive=True if active is None else active)
        # Open the key file (O_EXCL, 0600) before the user exists, so a key EspoCRM
        # returns always has somewhere to go (as PasswordFile.open() does).
        with create_private_file(key_file) as fh:
            record = client.create("User", data)
            api_key = record.get("apiKey") or (get(client, "User", record["id"]) or {}).get("apiKey")
            if not api_key:
                raise ProvisionError(f"API user {user_name} was created but EspoCRM returned no API "
                                     "key; generate one in Administration > API Users")
            fh.write(f"CRM_IMPORT_USERNAME={user_name}\nCRM_IMPORT_API_KEY={api_key}\n")
            fh.flush()
            os.fsync(fh.fileno())
        counter.add("apiUser", "created")
        log(f"API user {user_name}: created; key written to {key_file}")
        return
    current = get(client, "User", found["id"])
    if current.get("type") != "api":
        raise ProvisionError(f"user {user_name} exists but is not an API user; refusing to change it")
    if active is not None:
        desired["isActive"] = active
    changes = diff(current, desired)
    if changes:
        update(client, "User", found["id"], changes)
        counter.add("apiUser", "updated")
        log(f"API user {user_name}: updated ({', '.join(sorted(changes))}); key unchanged")
    else:
        counter.add("apiUser", "unchanged")
        log(f"API user {user_name}: unchanged; key unchanged")


def provision(client, config, key_file, import_active=None):
    counter = Counter()
    team_ids = {t["name"]: ensure_by_name(client, "Team", t, counter, "team")
                for t in config["teams"]}
    role_ids = {r["name"]: ensure_by_name(client, "Role", r, counter, "role")
                for r in config["roles"]}
    for spec in config["apiUsers"]:
        ensure_api_user(client, spec, role_ids, team_ids, key_file, import_active, counter)
    return counter.counts


def client_from_env(base_url, environ, transport):
    username, password = crm_api.credentials_from_env(environ)
    return crm_api.EspoClient(base_url, username, password, transport)


def main(argv=None, transport=None, environ=None):
    argv = sys.argv[1:] if argv is None else argv
    environ = os.environ if environ is None else environ
    prog = "provision_access"
    refused = require_target(argv[0] if argv else "", prog)
    if refused is not None:
        return refused
    parser = argparse.ArgumentParser(prog=prog, description=__doc__.splitlines()[0])
    parser.add_argument("target")
    parser.add_argument("--base-url", default=environ.get(crm_api.ENV_BASE_URL, ""))
    parser.add_argument("--key-file", required=True,
                        help="new file (mode 0600) for a newly created API user's key")
    parser.add_argument("--import-user-active", choices=("yes", "no"),
                        help="set the API user's active state (default: leave it as it is)")
    parser.add_argument("--config-dir", default=CONFIG_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    active = None if args.import_user_active is None else args.import_user_active == "yes"
    try:
        check_new_private_path(args.key_file)
        config = load_config(args.config_dir)
        client = client_from_env(args.base_url, environ, transport)
        counts = provision(client, config, args.key_file, active)
    except crm_api.ConfigError as err:
        print(f"{prog}: {err}", file=sys.stderr)
        return 2
    except (ProvisionError, crm_api.ApiError) as err:
        print(f"{prog}: {err}", file=sys.stderr)
        return 1
    print(json.dumps(counts, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
