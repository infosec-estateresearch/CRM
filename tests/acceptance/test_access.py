"""Live acceptance tests for CRM-003 (operator stage only; AC3-AC8). Synthetic users only.

Run against the crm-dev stack with the CRM-003 customisation deployed, from the
repository root:

    export CRM_BASE_URL=http://<CRM_BIND_IP>:8180
    export CRM_ADMIN_USERNAME=...  CRM_ADMIN_PASSWORD=...     # never stored
    export CRM_ACCESS_OUTPUT_DIR=/root/crm-003-acceptance     # existing directory, mode 0700
    python3 -m unittest discover -s tests/acceptance -p test_access.py -v

The module is skipped unless all four are set. It provisions the real
config/access teams and roles and four synthetic users (acc.*, @example.test,
sfIds starting ZZZACC) with scripts/provision_access.py and
scripts/provision_users.py. Every key and password file it makes is a new 0600
file in CRM_ACCESS_OUTPUT_DIR. That includes the ER Import API key, if this run
is the one that creates the API user. Nothing secret is printed. The firms and
enquiries the tests create are deleted again; the synthetic users stay
(re-runs reuse them and reset their passwords).
"""

import contextlib
import csv
import datetime
import io
import json
import os
import secrets
import stat
import string
import sys
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import crm_api  # noqa: E402
import provision_access  # noqa: E402
import provision_users  # noqa: E402

ENV_OUTPUT_DIR = "CRM_ACCESS_OUTPUT_DIR"
REQUIRED_ENV = (crm_api.ENV_BASE_URL, crm_api.ENV_USERNAME, crm_api.ENV_PASSWORD, ENV_OUTPUT_DIR)

STAFF, INTAKE, FORMER, LEAVER = "acc.staff", "acc.intake", "acc.former", "acc.leaver"
USERS = [
    {"sfId": "ZZZACC000000001AAA", "userName": STAFF, "firstName": "Acceptance",
     "lastName": "Staff", "emailAddress": "acc.staff@example.test", "isActive": True,
     "teams": ["Enquiries"], "roles": ["ER Staff"]},
    {"sfId": "ZZZACC000000002AAA", "userName": INTAKE, "firstName": "Acceptance",
     "lastName": "Intake", "emailAddress": "acc.intake@example.test", "isActive": True,
     "teams": ["Ancillary intake"], "roles": ["ER Intake"]},
    {"sfId": "ZZZACC000000003AAA", "userName": FORMER, "firstName": "Acceptance",
     "lastName": "Former", "emailAddress": "acc.former@example.test", "isActive": False,
     "teams": [], "roles": ["ER Staff"]},
    {"sfId": "ZZZACC000000004AAA", "userName": LEAVER, "firstName": "Acceptance",
     "lastName": "Leaver", "emailAddress": "acc.leaver@example.test", "isActive": True,
     "teams": ["Enquiries"], "roles": ["ER Staff"]},
]
SF_IDS = {u["userName"]: u["sfId"] for u in USERS}

ADMIN = None
OUT = None
PASSWORDS = {}


class CountingTransport(crm_api.UrllibTransport):
    """The real transport, recording each request's method."""

    def __init__(self):
        super().__init__()
        self.methods = []

    def request(self, method, url, headers, body):
        self.methods.append(method)
        return super().request(method, url, headers, body)


def out_path(name):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return os.path.join(OUT, f"{stamp}-{name}")


def run_script(main, argv, transport=None):
    """Run a provisioning main() in-process; output is captured, never shown."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv, transport=transport or CountingTransport(), environ=os.environ)
    return code, out.getvalue(), err.getvalue()


def write_users(users):
    path = out_path("users.json")
    with provision_access.create_private_file(path) as fh:
        json.dump(users, fh)
    return path


def read_passwords(path):
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {row["userName"]: row["temporaryPassword"] for row in csv.DictReader(fh)}


def provision_users_run(users, transport=None):
    csv_path = out_path("passwords.csv")
    code, out, err = run_script(provision_users.main, [
        "dev", "--input", write_users(users), "--password-file", csv_path], transport)
    return code, err, csv_path


def reset(user_name):
    csv_path = out_path(f"reset-{user_name}.csv")
    code, _, err = run_script(provision_users.main, [
        "dev", "--reset", SF_IDS[user_name], "--password-file", csv_path])
    if code != 0:
        raise AssertionError(f"--reset {user_name} failed: {err}")
    PASSWORDS[user_name] = read_passwords(csv_path)[user_name]


def setUpModule():
    global ADMIN, OUT
    missing = [n for n in REQUIRED_ENV if not os.environ.get(n)]
    if missing:
        raise unittest.SkipTest(f"live CRM-003 acceptance needs {', '.join(missing)}")
    OUT = os.environ[ENV_OUTPUT_DIR]
    if not os.path.isdir(OUT) or stat.S_IMODE(os.stat(OUT).st_mode) & 0o077:
        raise AssertionError(f"{ENV_OUTPUT_DIR} must be an existing directory with mode 0700")
    username, password = crm_api.credentials_from_env()
    ADMIN = crm_api.EspoClient(os.environ[crm_api.ENV_BASE_URL], username, password)
    # Round 1 (creates whatever does not exist yet).
    code, _, err = run_script(provision_access.main,
                              ["dev", "--key-file", out_path("import-key.env")])
    if code != 0:
        raise AssertionError(f"provision_access failed: {err}")
    code, err, csv_path = provision_users_run(USERS)
    if code != 0:
        raise AssertionError(f"provision_users failed: {err}")
    PASSWORDS.update(read_passwords(csv_path))
    for name in (STAFF, LEAVER):  # users kept from an earlier acceptance run
        if name not in PASSWORDS:
            reset(name)


def client_for(user_name, password=None):
    return crm_api.EspoClient(os.environ[crm_api.ENV_BASE_URL], user_name,
                              PASSWORDS[user_name] if password is None else password)


def sign_in_status(user_name, password=None):
    try:
        client_for(user_name, password).call("GET", "App/user")
        return 200
    except crm_api.ApiError as err:
        return err.status


def user_record(user_name):
    rows = ADMIN.list_all("User", crm_api.where_params([("equals", "userName", user_name)]))
    if len(rows) != 1:
        raise AssertionError(f"{len(rows)} users named {user_name}")
    return ADMIN.call("GET", f"User/{rows[0]['id']}")


def snapshot():
    """The provisioned teams, roles and users as EspoCRM holds them."""
    config = provision_access.load_config()
    state = {}
    for entity, items in (("Team", config["teams"]), ("Role", config["roles"])):
        for item in items:
            rows = ADMIN.list_all(entity, crm_api.where_params([("equals", "name", item["name"])]))
            state[(entity, item["name"])] = [ADMIN.call("GET", f"{entity}/{r['id']}") for r in rows]
    for u in USERS:
        rec = user_record(u["userName"])
        state[("User", u["userName"])] = {k: rec.get(k) for k in (
            "id", "sfId", "firstName", "lastName", "emailAddress", "isActive", "type",
            "teamsIds", "rolesIds", "modifiedAt")}
    return state


def synthetic_name(label):
    return f"CRM-003 acceptance {label} {secrets.token_hex(4)}"


def synthetic_sf_id():
    return "ZZZACC" + "".join(secrets.choice(string.ascii_uppercase + string.digits)
                              for _ in range(12))


class TestAccessAcceptance(unittest.TestCase):
    def setUp(self):
        self.cleanup = []  # (entity, id), deleted in reverse order as admin

    def tearDown(self):
        for entity, record_id in reversed(self.cleanup):
            try:
                ADMIN.delete(entity, record_id)
            except crm_api.ApiError:
                pass

    def create(self, entity, data):
        record = ADMIN.create(entity, data)
        self.cleanup.append((entity, record["id"]))
        return record

    def test_ac3_second_provisioning_changes_nothing_and_issues_no_password(self):
        before = snapshot()
        transport = CountingTransport()
        key_file = out_path("import-key-second.env")
        code, _, err = run_script(provision_access.main, ["dev", "--key-file", key_file], transport)
        self.assertEqual(code, 0, err)
        code, err, csv_path = provision_users_run(USERS, transport)
        self.assertEqual(code, 0, err)
        self.assertEqual([m for m in transport.methods if m != "GET"], [],
                         "the second run must not write anything")
        self.assertFalse(os.path.exists(key_file), "no new API key on the second run")
        self.assertFalse(os.path.exists(csv_path), "no new password on the second run")
        self.assertEqual(snapshot(), before)
        self.assertFalse(user_record(FORMER)["isActive"])

    def test_ac4_staff_signs_in_reads_all_firms_and_contacts_and_cannot_delete_a_firm(self):
        self.assertEqual(sign_in_status(STAFF), 200)
        staff = client_for(STAFF)
        for entity in ("Account", "Contact"):
            with self.subTest(entity=entity):
                admin_total = ADMIN.list_page(entity, max_size=1)["total"]
                self.assertGreater(admin_total, 0, f"seed the stack first ({entity})")
                self.assertEqual(staff.list_page(entity, max_size=1)["total"], admin_total)
        firm = self.create("Account", {"name": synthetic_name("firm"),
                                       "billingAddressPostalCode": "ZZ99 9ZZ"})
        with self.assertRaises(crm_api.ApiError) as ctx:
            staff.delete("Account", firm["id"])
        self.assertEqual(ctx.exception.status, 403)
        self.assertEqual(ADMIN.call("GET", f"Account/{firm['id']}")["id"], firm["id"])

    def test_ac5_inactive_users_cannot_sign_in(self):
        self.assertFalse(user_record(FORMER)["isActive"])
        self.assertEqual(sign_in_status(FORMER, secrets.token_urlsafe(24)), 401)
        # A user who could sign in is deactivated by re-provisioning, then cannot.
        self.assertEqual(sign_in_status(LEAVER), 200)
        leaving = [dict(u, isActive=False) if u["userName"] == LEAVER else u for u in USERS]
        code, err, csv_path = provision_users_run(leaving)
        self.assertEqual(code, 0, err)
        self.assertFalse(os.path.exists(csv_path))
        self.assertFalse(user_record(LEAVER)["isActive"])
        self.assertEqual(sign_in_status(LEAVER), 401)

    def test_ac6_firm_with_an_enquiry_cannot_be_deleted_even_by_an_admin(self):
        firm = self.create("Account", {"name": synthetic_name("guarded firm"),
                                       "billingAddressPostalCode": "ZZ99 9ZY"})
        close = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        enquiry = self.create("Opportunity", {"name": synthetic_name("enquiry"),
                                              "accountId": firm["id"], "closeDate": close,
                                              "amount": 1})
        with self.assertRaises(crm_api.ApiError) as ctx:
            ADMIN.delete("Account", firm["id"])
        self.assertEqual(ctx.exception.status, 403)
        self.assertEqual(ADMIN.call("GET", f"Account/{firm['id']}")["id"], firm["id"])
        # Deliberate clean-up: remove the enquiry first, then the firm can go.
        ADMIN.delete("Opportunity", enquiry["id"])
        ADMIN.delete("Account", firm["id"])
        self.cleanup.clear()

    def test_ac7_audited_field_edit_appears_in_the_stream_with_user_and_time(self):
        me = ADMIN.call("GET", "App/user")["user"]
        firm = self.create("Account", {"name": synthetic_name("audited firm"),
                                       "billingAddressPostalCode": "ZZ99 9ZX", "type": "Tier 3"})
        ADMIN.call("PUT", f"Account/{firm['id']}", data={"type": "Tier 2"})
        notes = ADMIN.call("GET", f"Account/{firm['id']}/stream",
                           params={"maxSize": 50}).get("list", [])
        updates = [n for n in notes if n.get("type") == "Update"
                   and "type" in ((n.get("data") or {}).get("fields") or [])]
        self.assertTrue(updates, "no Update note for the audited 'type' field")
        note = updates[0]
        self.assertEqual(note.get("createdById"), me["id"])
        self.assertTrue(note.get("createdAt"))

    def test_ac8_sf_id_unique_index_rejects_a_duplicate(self):
        sf_id, owner_id = synthetic_sf_id(), synthetic_sf_id()
        keys = {"sfId": sf_id, "sfOwnerId": owner_id, "sfCreatedAt": "2015-06-01 09:30:00"}
        first = self.create("Account", dict({"name": synthetic_name("keyed firm"),
                                             "billingAddressPostalCode": "ZZ99 9ZW"}, **keys))
        stored = ADMIN.call("GET", f"Account/{first['id']}")
        self.assertEqual({k: stored.get(k) for k in keys}, keys,
                         "the Salesforce keys were not stored through the API on create")
        # sfId is readOnlyAfterCreate: an update cannot change it, even by an admin.
        with contextlib.suppress(crm_api.ApiError):
            ADMIN.call("PUT", f"Account/{first['id']}", data={"sfId": synthetic_sf_id()})
        self.assertEqual(ADMIN.call("GET", f"Account/{first['id']}").get("sfId"), sf_id)
        # The other keys are edit "no" for people (role fieldData): Staff cannot change them.
        with contextlib.suppress(crm_api.ApiError):
            client_for(STAFF).call("PUT", f"Account/{first['id']}",
                                   data={"sfOwnerId": synthetic_sf_id()})
        self.assertEqual(ADMIN.call("GET", f"Account/{first['id']}").get("sfOwnerId"), owner_id)
        try:
            second = ADMIN.create("Account", {"name": synthetic_name("duplicate keyed firm"),
                                              "billingAddressPostalCode": "ZZ99 9ZV",
                                              "sfId": sf_id})
        except crm_api.ApiError as err:
            self.assertGreaterEqual(err.status, 400)
        else:
            self.cleanup.append(("Account", second["id"]))
            self.fail("a second Account with the same sfId was accepted")
        rows = ADMIN.list_all("Account", crm_api.where_params([("equals", "sfId", sf_id)]))
        self.assertEqual([r["id"] for r in rows], [first["id"]])
        # The same index on User: the provisioned staff user's sfId cannot be reused.
        with self.assertRaises(crm_api.ApiError):
            dup = ADMIN.create("User", {"userName": f"acc.dup.{secrets.token_hex(3)}",
                                        "lastName": "Duplicate", "type": "regular",
                                        "isActive": False, "sendAccessInfo": False,
                                        "sfId": SF_IDS[STAFF]})
            self.cleanup.append(("User", dup["id"]))


if __name__ == "__main__":
    unittest.main()
