#!/usr/bin/env python3
"""Provision named EspoCRM users from a JSON list, idempotently by sfId (CRM-003).

Standard library only; HTTP goes through scripts/crm_api.py.

Usage (operator stage; credentials only in the environment):

    python3 scripts/provision_users.py dev --input users.json --password-file /root/new-passwords.csv \
        [--legacy-shared <sfId>]...
    python3 scripts/provision_users.py dev --reset <sfId> --password-file /root/reset.csv
    python3 scripts/provision_users.py dev --report-never-logged-in

Input: a JSON list of {sfId, userName, firstName, lastName, emailAddress,
isActive, teams[], roles[]}. Team and role names must exist in config/access.

- A user is matched by sfId only. A new sfId whose userName already exists is
  refused, never adopted.
- Re-runs update names, email address, active state, teams and roles, and
  never touch passwords.
- A new active user gets a strong random temporary password (secrets module,
  24 characters, lower, upper, digit and symbol). A new inactive user, and every
  --legacy-shared identity (always inactive), gets a random password that is
  never recorded, so it has no usable password.
- Temporary passwords are written only to --password-file: a new file, mode
  0600, created only when a password is issued. They are never printed or
  logged, and sendAccessInfo is always false, so no email is sent.
- The sfIds in config/access/legacy_shared.json are legacy shared identities on
  every run, whatever the flags or input say: always inactive, never a recorded
  password, and --reset is refused for them.
- --reset issues a new temporary password for one active user.
- --report-never-logged-in lists active regular users whose lastAccess is empty.

The first argument names the target environment and must be exactly "dev"
(exit 2 otherwise). Credentials come from CRM_ADMIN_USERNAME /
CRM_ADMIN_PASSWORD; the base URL from --base-url or CRM_BASE_URL.
"""

import argparse
import csv
import json
import os
import re
import secrets
import string
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_access  # noqa: E402
import crm_api  # noqa: E402
import provision_access as access  # noqa: E402
from provision_access import ProvisionError, log  # noqa: E402

INPUT_KEYS = ("sfId", "userName", "firstName", "lastName", "emailAddress",
              "isActive", "teams", "roles")
SF_ID = re.compile(r"^[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?$")
USER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,49}$")

PASSWORD_LENGTH = 24
MIN_PASSWORD_LENGTH = 20
# Symbols that need no quoting in CSV, shells or URLs: no quotes, comma,
# backslash, space, '$', '&' or backtick.
PASSWORD_SYMBOLS = "!#%+-.:=?@^_~"
PASSWORD_CLASSES = (string.ascii_lowercase, string.ascii_uppercase, string.digits,
                    PASSWORD_SYMBOLS)
PASSWORD_ALPHABET = "".join(PASSWORD_CLASSES)
CSV_HEADER = ("sfId", "userName", "temporaryPassword")


def generate_password(length=PASSWORD_LENGTH):
    """Uniformly random over PASSWORD_ALPHABET, with every character class present."""
    if length < MIN_PASSWORD_LENGTH:
        raise ValueError(f"temporary passwords must be at least {MIN_PASSWORD_LENGTH} characters")
    while True:
        candidate = "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))
        if all(any(c in cls for c in candidate) for cls in PASSWORD_CLASSES):
            return candidate


def unusable_password():
    """A random password that is generated, sent once and never recorded anywhere."""
    return secrets.token_urlsafe(48)


class PasswordFile:
    """The 0600 CSV of temporary passwords: created on first use, never overwritten."""

    def __init__(self, path):
        self.path = path
        self._fh = None
        self._writer = None
        self.issued = 0

    def open(self):
        if self._fh is None:
            self._fh = access.create_private_file(self.path)
            self._writer = csv.writer(self._fh)
            self._writer.writerow(CSV_HEADER)
            self._sync()

    def record(self, sf_id, user_name, password):
        self.open()
        self._writer.writerow((sf_id, user_name, password))
        self._sync()
        self.issued += 1

    def _sync(self):
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None


# --- input -------------------------------------------------------------------

def validate_users(users, config):
    """Raise ProvisionError on the first problem; messages name sfId/userName only."""
    if not isinstance(users, list) or not users:
        raise ProvisionError("input must be a non-empty JSON list of users")
    teams = {t["name"] for t in config["teams"]}
    roles = {r["name"] for r in config["roles"]}
    api_only = access.api_only_roles(config)
    seen_sf, seen_names = set(), set()
    for i, u in enumerate(users):
        where = f"input user #{i + 1}"
        if not isinstance(u, dict) or set(u) != set(INPUT_KEYS):
            raise ProvisionError(f"{where}: keys must be exactly {', '.join(INPUT_KEYS)}")
        if not isinstance(u["sfId"], str) or not SF_ID.match(u["sfId"]):
            raise ProvisionError(f"{where}: sfId must be 15 or 18 letters and digits")
        where = f"input user {u['sfId']}"
        if not isinstance(u["userName"], str) or not USER_NAME.match(u["userName"]):
            raise ProvisionError(f"{where}: invalid userName")
        for key in ("firstName", "lastName", "emailAddress"):
            if not isinstance(u[key], str):
                raise ProvisionError(f"{where}: {key} must be a string")
        if not u["lastName"].strip():
            raise ProvisionError(f"{where}: lastName is required")
        if u["emailAddress"] and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", u["emailAddress"]):
            raise ProvisionError(f"{where}: invalid emailAddress")
        if not isinstance(u["isActive"], bool):
            raise ProvisionError(f"{where}: isActive must be true or false")
        for key, known in (("teams", teams), ("roles", roles)):
            if not isinstance(u[key], list) or not all(isinstance(n, str) for n in u[key]):
                raise ProvisionError(f"{where}: {key} must be a list of names")
            unknown = set(u[key]) - known
            if unknown:
                raise ProvisionError(f"{where}: unknown {key} {sorted(unknown)}")
        if set(u["roles"]) & api_only:
            raise ProvisionError(f"{where}: roles {sorted(set(u['roles']) & api_only)} "
                                 "are for API users only")
        if u["sfId"] in seen_sf:
            raise ProvisionError(f"{where}: duplicate sfId")
        if u["userName"].lower() in seen_names:
            raise ProvisionError(f"{where}: duplicate userName {u['userName']}")
        seen_sf.add(u["sfId"])
        seen_names.add(u["userName"].lower())


def load_legacy_shared(config_dir):
    """The sticky legacy shared identities from config/access/legacy_shared.json."""
    path = os.path.join(config_dir, "legacy_shared.json")
    doc = access._load_json(path)
    ids = doc.get("legacyShared") if isinstance(doc, dict) else None
    if not isinstance(ids, list) or not all(isinstance(i, str) and SF_ID.match(i) for i in ids):
        raise ProvisionError(f"{path}: legacyShared must be a list of sfIds")
    return set(ids)


def load_users(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as err:
        raise ProvisionError(f"cannot read {path}: {err}") from None


# --- provisioning ----------------------------------------------------------------

def _find_by_sf_id(client, sf_id):
    return access.find_one(client, "User", [("equals", "sfId", sf_id)], f"sfId {sf_id}")


def _user_changes(current, desired):
    changes = access.diff(current, desired)
    for key in ("firstName", "lastName"):  # EspoCRM may store an empty name as null
        if key in changes and (current.get(key) or "") == (desired[key] or ""):
            del changes[key]
    if "emailAddress" in changes and \
            (current.get("emailAddress") or "").lower() == desired["emailAddress"].lower():
        del changes["emailAddress"]
    return changes


def provision_users(client, users, config, passwords, legacy_shared=()):
    names_used = sorted({n for u in users for n in u["teams"]})
    roles_used = sorted({n for u in users for n in u["roles"]})
    team_ids = access.name_ids(client, "Team", names_used)
    role_ids = access.name_ids(client, "Role", roles_used)
    counter = access.Counter()
    for u in users:
        sf_id, user_name = u["sfId"], u["userName"]
        active = u["isActive"] and sf_id not in legacy_shared
        desired = {
            "firstName": u["firstName"],
            "lastName": u["lastName"],
            "emailAddress": u["emailAddress"],
            "isActive": active,
            "teamsIds": [team_ids[n] for n in u["teams"]],
            "rolesIds": [role_ids[n] for n in u["roles"]],
        }
        found = _find_by_sf_id(client, sf_id)
        if found is None:
            clash = access.find_one(client, "User", [("equals", "userName", user_name)],
                                    f"userName {user_name}")
            if clash is not None:
                raise ProvisionError(f"user {user_name} already exists without sfId {sf_id}; "
                                     "refusing to adopt it")
            if active:
                passwords.open()  # fail before the user exists if the file cannot be made
                password = generate_password()
            else:
                password = unusable_password()
            data = dict(desired, userName=user_name, type="regular", sfId=sf_id,
                        sendAccessInfo=False, password=password, passwordConfirm=password)
            record = client.create("User", data)
            if active:
                passwords.record(sf_id, user_name, password)
            password = data = None
            stored = record.get("sfId")
            if stored is None:
                stored = (access.get(client, "User", record["id"]) or {}).get("sfId")
            if stored != sf_id:
                raise ProvisionError(
                    f"user {user_name} was created but EspoCRM did not store its sfId; "
                    "re-runs could not find it. See docs/ACCESS.md, section 5.")
            counter.add("user", "created")
            log(f"user {user_name}: created ({'active, temporary password issued' if active else 'inactive, no usable password'})")
            continue
        current = access.get(client, "User", found["id"])
        if current.get("type") != "regular":
            raise ProvisionError(f"sfId {sf_id} belongs to a {current.get('type')!r} user; "
                                 "only regular users are provisioned")
        if current.get("userName") != user_name:
            log(f"user {current.get('userName')}: input userName differs ({user_name}); "
                "userName is not changed")
        changes = _user_changes(current, desired)
        if changes:
            access.update(client, "User", found["id"], changes)
            counter.add("user", "updated")
            log(f"user {current.get('userName')}: updated ({', '.join(sorted(changes))})")
            if changes.get("isActive") is True:
                log(f"user {current.get('userName')}: now active without a known password; "
                    f"issue one with --reset {sf_id}")
        else:
            counter.add("user", "unchanged")
            log(f"user {current.get('userName')}: unchanged")
    counts = counter.counts
    counts["passwordsIssued"] = passwords.issued
    return counts


def reset_password(client, sf_id, passwords, legacy_shared=()):
    if sf_id in legacy_shared:
        raise ProvisionError(f"sfId {sf_id} is a legacy shared identity; it never gets a password")
    found = _find_by_sf_id(client, sf_id)
    if found is None:
        raise ProvisionError(f"no user has sfId {sf_id}")
    current = access.get(client, "User", found["id"])
    if current.get("type") != "regular":
        raise ProvisionError(f"sfId {sf_id} is not a regular user")
    if not current.get("isActive"):
        raise ProvisionError(f"user {current.get('userName')} is inactive; "
                             "activate it through the input file first")
    passwords.open()
    password = generate_password()
    access.update(client, "User", found["id"], {"password": password, "passwordConfirm": password})
    passwords.record(sf_id, current.get("userName"), password)
    password = None
    log(f"user {current.get('userName')}: temporary password reset")
    return {"passwordsIssued": passwords.issued}


def never_logged_in(client):
    rows = client.list_all("User", {"select": "id,userName,type,isActive,lastAccess"})
    out = []
    for row in rows:
        if "lastAccess" not in row:
            row = access.get(client, "User", row["id"])
        if row.get("type") == "regular" and row.get("isActive") and not row.get("lastAccess"):
            out.append(row.get("userName"))
    return sorted(out)


def main(argv=None, transport=None, environ=None):
    argv = sys.argv[1:] if argv is None else argv
    environ = os.environ if environ is None else environ
    prog = "provision_users"
    refused = access.require_target(argv[0] if argv else "", prog)
    if refused is not None:
        return refused
    parser = argparse.ArgumentParser(prog=prog, description=__doc__.splitlines()[0])
    parser.add_argument("target")
    parser.add_argument("--base-url", default=environ.get(crm_api.ENV_BASE_URL, ""))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", help="JSON list of users")
    mode.add_argument("--reset", metavar="SFID", help="issue a new temporary password")
    mode.add_argument("--report-never-logged-in", action="store_true")
    parser.add_argument("--password-file", help="new file (mode 0600) for temporary passwords")
    parser.add_argument("--legacy-shared", action="append", default=[], metavar="SFID",
                        help="a legacy shared identity: always provisioned inactive")
    parser.add_argument("--config-dir", default=access.CONFIG_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    # CRM-007R: the base URL is pinned to the target (check_access.pinned_base_url).
    problem = check_access.base_url_problem(args.target, args.base_url, environ)
    if problem:
        print(f"{prog}: refusing to run: {problem}", file=sys.stderr)
        return 2
    passwords = None
    try:
        if args.report_never_logged_in:
            client = access.client_from_env(args.base_url, environ, transport)
            for name in never_logged_in(client):
                print(name)
            return 0
        if not args.password_file:
            raise ProvisionError("--password-file is required with --input and --reset")
        access.check_new_private_path(args.password_file)
        config = access.load_config(args.config_dir)
        sticky = load_legacy_shared(args.config_dir)
        passwords = PasswordFile(args.password_file)
        if args.reset:
            if not SF_ID.match(args.reset):
                raise ProvisionError("--reset needs an sfId (15 or 18 letters and digits)")
            client = access.client_from_env(args.base_url, environ, transport)
            counts = reset_password(client, args.reset, passwords,
                                    sticky | set(args.legacy_shared))
        else:
            users = load_users(args.input)
            validate_users(users, config)
            unknown = set(args.legacy_shared) - {u["sfId"] for u in users}
            if unknown:
                raise ProvisionError("--legacy-shared names an sfId that is not in the input")
            client = access.client_from_env(args.base_url, environ, transport)
            counts = provision_users(client, users, config, passwords,
                                     sticky | set(args.legacy_shared))
    except crm_api.ConfigError as err:
        print(f"{prog}: {err}", file=sys.stderr)
        return 2
    except (ProvisionError, crm_api.ApiError) as err:
        print(f"{prog}: {err}", file=sys.stderr)
        return 1
    finally:
        if passwords is not None:
            passwords.close()
            if passwords.issued:
                log(f"{passwords.issued} temporary password(s) written to {passwords.path}")
    print(json.dumps(counts, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
