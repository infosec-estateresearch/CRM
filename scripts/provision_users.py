#!/usr/bin/env python3
"""Provision named EspoCRM users from a JSON list, idempotently by sfId (CRM-003).

Standard library only; HTTP goes through scripts/crm_api.py.

Usage (operator stage; credentials only in the environment):

    python3 scripts/provision_users.py dev --input users.json --password-file /root/new-passwords.csv \
        [--legacy-shared <sfId>]...
    python3 scripts/provision_users.py dev --reset <sfId> --password-file /root/reset.csv
    python3 scripts/provision_users.py dev --report-never-logged-in
    python3 scripts/provision_users.py beta --input users.json \
        --common-password-file /root/uat-password [--password-file FILE] \
        [--service-identity <sfId>]... [--legacy-shared <sfId>]...

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
- --service-identity SFID (CRM-009, repeatable, must be in the input): a
  non-person Salesforce login (an integration user, a shared mailbox) kept so
  that its records have an owner. Always inactive, with a random password
  that is never recorded; its names are kept; --reset is refused for it.
  Service identities are sticky (CRM-009 r2): every --service-identity sfId
  (on --input and --reset runs) is added to <target runtime>/service_identities.json
  (outside Git; the runtime found as for the pinned base URL), and every
  --input and --reset run uses the union of that file and the flags, whatever
  the flags say. The file must be a regular file (opened with O_NOFOLLOW),
  owned by root, mode 0600; it is created on first use, and only in a deployed
  runtime (one holding the db directory deploy_release.sh makes), so it never
  makes a runtime unclean before a first deploy. A user that is active when it
  becomes a service identity is deactivated and given a new random password
  that is never recorded. There is no flag to remove one: that is a manual
  root edit of the file.
- --common-password-file FILE (CRM-009, target beta only, with --input): every
  NEW ACTIVE user that is neither legacy shared nor a service identity gets the
  one common UAT password in FILE instead of a generated one, and nothing is
  written for it to --password-file (optional in this mode; when given it holds
  only generated passwords, so none). FILE must be a regular file (opened with
  O_NOFOLLOW), owned by root, mode 0600, holding one line: at least 16
  characters from at least three of lower case, upper case, digits and other.
  The password is never printed or logged. Re-runs never touch passwords, and
  the admin and ER Import API users (not regular users) are never touched.

The first argument names the target environment and must be exactly "dev" or
"beta" (exit 2 otherwise); the base URL is pinned to it
(check_access.base_url_problem). Credentials come from CRM_ADMIN_USERNAME /
CRM_ADMIN_PASSWORD; the base URL from --base-url or CRM_BASE_URL.
"""

import argparse
import csv
import json
import os
import re
import secrets
import stat
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

# CRM-009: the common UAT password file.
COMMON_PASSWORD_OWNER_UID = 0  # root; tests patch it to their own uid
COMMON_PASSWORD_MIN_LENGTH = 16
COMMON_PASSWORD_MIN_CLASSES = 3
COMMON_PASSWORD_MAX_BYTES = 1024


def read_common_password(path):
    """The common UAT password from path. Raise ProvisionError (never quoting
    the content) unless path is a regular file, not a symlink, owned by
    COMMON_PASSWORD_OWNER_UID, mode 0600, holding exactly one line with a
    password of at least 16 characters and three character classes."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0))
    except OSError as err:
        raise ProvisionError(f"--common-password-file cannot be opened without following a "
                             f"symlink ({type(err).__name__})") from None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ProvisionError("--common-password-file must be a regular file")
        if st.st_uid != COMMON_PASSWORD_OWNER_UID:
            raise ProvisionError("--common-password-file must be owned by root")
        if stat.S_IMODE(st.st_mode) != 0o600:
            raise ProvisionError("--common-password-file must have mode 0600")
        raw = os.read(fd, COMMON_PASSWORD_MAX_BYTES + 1)
    finally:
        os.close(fd)
    if len(raw) > COMMON_PASSWORD_MAX_BYTES:
        raise ProvisionError("--common-password-file is too long")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ProvisionError("--common-password-file is not UTF-8 text") from None
    if text.endswith("\n"):
        text = text[:-1]
    if any(c in text for c in "\r\n") or any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise ProvisionError("--common-password-file must hold exactly one line, with no "
                             "control characters")
    if len(text) < COMMON_PASSWORD_MIN_LENGTH:
        raise ProvisionError(f"the common password must be at least "
                             f"{COMMON_PASSWORD_MIN_LENGTH} characters")
    classes = sum((any(c.islower() for c in text), any(c.isupper() for c in text),
                   any(c.isdigit() for c in text), any(not c.isalnum() for c in text)))
    if classes < COMMON_PASSWORD_MIN_CLASSES:
        raise ProvisionError("the common password must use at least three of lower case, "
                             "upper case, digits and other characters")
    return text


class NoPasswordFile:
    """Stands in for --password-file when it is not given with
    --common-password-file: any attempt to record a password fails."""

    path = None
    issued = 0

    def open(self):
        raise ProvisionError("a generated password would be issued, but no --password-file "
                             "was given")

    def record(self, *_):
        self.open()

    def close(self):
        pass


# CRM-009 r2: the sticky service identities, kept outside Git (sfIds must never
# be in the repository) in <target runtime>/service_identities.json.
SERVICE_IDENTITIES_FILE = "service_identities.json"
SERVICE_IDENTITIES_KEY = "serviceIdentities"
SERVICE_IDENTITIES_OWNER_UID = 0  # root; tests patch it to their own uid
SERVICE_IDENTITIES_MAX_BYTES = 1024 * 1024
# The file is created only in a deployed runtime: deploy_release.sh's
# make_runtime creates <runtime>/db, and the clean-runtime check runs before it.
DEPLOYED_MARKER = "db"


def service_identities_path(target, environ):
    """<target runtime>/service_identities.json, the runtime found as for the
    pinned base URL (check_access.target_runtime). Raise ProvisionError if the
    runtime cannot be determined or is not a real directory."""
    runtime, problem = check_access.target_runtime(target, environ)
    if problem:
        raise ProvisionError(f"cannot determine the {target} runtime: {problem}")
    if os.path.islink(runtime) or not os.path.isdir(runtime):
        raise ProvisionError(f"the {target} runtime is not a real directory: {runtime}")
    return os.path.join(runtime, SERVICE_IDENTITIES_FILE)


def _check_store_fd(fd, path):
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        raise ProvisionError(f"{path} must be a regular file")
    if st.st_uid != SERVICE_IDENTITIES_OWNER_UID:
        raise ProvisionError(f"{path} must be owned by root")
    if stat.S_IMODE(st.st_mode) != 0o600:
        raise ProvisionError(f"{path} must have mode 0600")


def load_service_identities(path):
    """The stored service identities (a set; empty if the file does not exist
    yet). Raise ProvisionError unless the file, when present, is a regular
    file (opened with O_NOFOLLOW) owned by root, mode 0600, holding
    {"serviceIdentities": [sfId, ...]}."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0))
    except FileNotFoundError:
        if os.path.lexists(path):  # a dangling symlink
            raise ProvisionError(f"{path} cannot be opened without following a symlink") from None
        return set()
    except OSError as err:
        raise ProvisionError(f"{path} cannot be opened without following a symlink "
                             f"({type(err).__name__})") from None
    try:
        _check_store_fd(fd, path)
        raw = os.read(fd, SERVICE_IDENTITIES_MAX_BYTES + 1)
    finally:
        os.close(fd)
    if len(raw) > SERVICE_IDENTITIES_MAX_BYTES:
        raise ProvisionError(f"{path} is too large")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ProvisionError(f"{path} is not valid JSON") from None
    ids = doc.get(SERVICE_IDENTITIES_KEY) if isinstance(doc, dict) and \
        set(doc) == {SERVICE_IDENTITIES_KEY} else None
    if not isinstance(ids, list) or not all(isinstance(i, str) and SF_ID.match(i) for i in ids):
        raise ProvisionError(f"{path}: must be exactly {{\"{SERVICE_IDENTITIES_KEY}\": "
                             "[sfId, ...]}")
    return set(ids)


def store_service_identities(path, ids):
    """Atomically write ids (sorted) to path: a new 0600 file opened with
    O_CREAT|O_EXCL|O_NOFOLLOW, then renamed over path. Refused in a runtime
    that has not been deployed (no <runtime>/DEPLOYED_MARKER directory)."""
    runtime = os.path.dirname(path)
    marker = os.path.join(runtime, DEPLOYED_MARKER)
    if os.path.islink(marker) or not os.path.isdir(marker):
        raise ProvisionError(f"refusing to create {path}: {runtime} has not been deployed "
                             f"(no {DEPLOYED_MARKER} directory)")
    tmp = path + ".tmp"
    if os.path.lexists(tmp):
        raise ProvisionError(f"{tmp} exists (an interrupted run?); inspect and remove it")
    body = json.dumps({SERVICE_IDENTITIES_KEY: sorted(ids)}, indent=2) + "\n"
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except OSError as err:
        raise ProvisionError(f"cannot create {tmp} ({type(err).__name__})") from None
    try:
        os.fchmod(fd, 0o600)
        _check_store_fd(fd, tmp)
        os.write(fd, body.encode("utf-8"))
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        os.unlink(tmp)
        raise
    os.close(fd)
    os.replace(tmp, path)


def sticky_service_identities(target, environ, flagged):
    """The union of the stored service identities and flagged (the
    --service-identity sfIds). New flagged sfIds are added to the store, which
    is created on first use. There is no way to remove one here: that is a
    manual root edit of the file (docs/ACCESS.md)."""
    path = service_identities_path(target, environ)
    stored = load_service_identities(path)
    union = stored | set(flagged)
    if union != stored:
        store_service_identities(path, union)
        log(f"{len(union - stored)} service identit(y/ies) added to {path}")
    return union


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


def provision_users(client, users, config, passwords, legacy_shared=(), service_ids=(),
                    common_password=None):
    names_used = sorted({n for u in users for n in u["teams"]})
    roles_used = sorted({n for u in users for n in u["roles"]})
    team_ids = access.name_ids(client, "Team", names_used)
    role_ids = access.name_ids(client, "Role", roles_used)
    counter = access.Counter()
    common_users = 0
    for u in users:
        sf_id, user_name = u["sfId"], u["userName"]
        active = u["isActive"] and sf_id not in legacy_shared and sf_id not in service_ids
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
            common = active and common_password is not None
            if common:
                password = common_password  # CRM-009: never recorded
            elif active:
                passwords.open()  # fail before the user exists if the file cannot be made
                password = generate_password()
            else:
                password = unusable_password()
            data = dict(desired, userName=user_name, type="regular", sfId=sf_id,
                        sendAccessInfo=False, password=password, passwordConfirm=password)
            record = client.create("User", data)
            if active and not common:
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
            if common:
                common_users += 1
                state = "active, common UAT password"
            elif active:
                state = "active, temporary password issued"
            elif sf_id in service_ids:
                state = "service identity, inactive, no usable password"
            else:
                state = "inactive, no usable password"
            log(f"user {user_name}: created ({state})")
            continue
        current = access.get(client, "User", found["id"])
        if current.get("type") != "regular":
            raise ProvisionError(f"sfId {sf_id} belongs to a {current.get('type')!r} user; "
                                 "only regular users are provisioned")
        if current.get("userName") != user_name:
            log(f"user {current.get('userName')}: input userName differs ({user_name}); "
                "userName is not changed")
        changes = _user_changes(current, desired)
        if sf_id in service_ids and current.get("isActive"):
            # CRM-009 r2: a user that becomes a service identity loses any
            # password it was given while active; the new one is never recorded.
            password = unusable_password()
            changes = dict(changes, password=password, passwordConfirm=password)
            password = None
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
    if common_password is not None:
        counts["commonPasswordUsers"] = common_users
    return counts


def reset_password(client, sf_id, passwords, legacy_shared=(), service_ids=()):
    if sf_id in legacy_shared:
        raise ProvisionError(f"sfId {sf_id} is a legacy shared identity; it never gets a password")
    if sf_id in service_ids:
        raise ProvisionError(f"sfId {sf_id} is a service identity; it never gets a password")
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
    parser.add_argument("--service-identity", action="append", default=[], metavar="SFID",
                        help="a non-person login: always inactive, no usable password")
    parser.add_argument("--common-password-file", metavar="FILE",
                        help="beta only: the common UAT password for new active users")
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
        common_password = None
        if args.common_password_file is not None:
            if args.target != "beta":
                raise ProvisionError("--common-password-file is allowed only for target beta")
            if not args.input:
                raise ProvisionError("--common-password-file is allowed only with --input")
            common_password = read_common_password(args.common_password_file)
        elif not args.password_file:
            raise ProvisionError("--password-file is required with --input and --reset")
        if not all(SF_ID.match(i) for i in args.service_identity):
            raise ProvisionError("--service-identity needs an sfId (15 or 18 letters and digits)")
        flagged = set(args.service_identity)
        if args.password_file:
            access.check_new_private_path(args.password_file)
        config = access.load_config(args.config_dir)
        sticky = load_legacy_shared(args.config_dir)
        passwords = PasswordFile(args.password_file) if args.password_file else NoPasswordFile()
        if args.reset:
            if not SF_ID.match(args.reset):
                raise ProvisionError("--reset needs an sfId (15 or 18 letters and digits)")
            services = sticky_service_identities(args.target, environ, flagged)
            client = access.client_from_env(args.base_url, environ, transport)
            counts = reset_password(client, args.reset, passwords,
                                    sticky | set(args.legacy_shared), services)
        else:
            users = load_users(args.input)
            validate_users(users, config)
            unknown = set(args.legacy_shared) - {u["sfId"] for u in users}
            if unknown:
                raise ProvisionError("--legacy-shared names an sfId that is not in the input")
            if flagged - {u["sfId"] for u in users}:
                raise ProvisionError("--service-identity names an sfId that is not in the input")
            services = sticky_service_identities(args.target, environ, flagged)
            client = access.client_from_env(args.base_url, environ, transport)
            counts = provision_users(client, users, config, passwords,
                                     sticky | set(args.legacy_shared), services, common_password)
            common_password = None
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
