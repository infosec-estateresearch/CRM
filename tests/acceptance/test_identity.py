"""Live acceptance suite for CRM-IDINT-001, identity integrity (A1 to A10).

NOT run by the unit loop, and NOT run in the build sandbox (no EspoCRM, Docker or
browser there). It is the operator stage's proof, against a disposable synthetic
stack with the candidate deployed:

    export CRM_BASE_URL=http://<host>:<port>
    export CRM_ADMIN_USERNAME=...  CRM_ADMIN_PASSWORD=...      # never stored
    export CRM_ACCESS_OUTPUT_DIR=<existing 0700 directory>       # new 0600 password files go here
    export CRM_IDENTITY_IMPORT_KEY_FILE=<file with CRM_IMPORT_API_KEY=...>   # the ER Import key
    # Operator-supplied commands, run without a shell (argv split like a shell would), no secrets in them:
    export CRM_AUDIT_FAULT_ON_CMD=...   # makes identity audit storage unwritable (A3)
    export CRM_AUDIT_FAULT_OFF_CMD=...  # restores it
    export CRM_CLEANUP_AGE_CMD=...      # ages data past every retention period (A7)
    export CRM_CLEANUP_RUN_CMD=...      # runs the scheduled cleanup job once (A7)
    export CRM_DB_COUNT_CMD=...         # prints "<accounts> <contacts> <audit records>", deleted rows included (A7)
    export CRM_SEEDED_EXCEPTION_IDS=id1,id2   # optional: the contacts seeded as 3.3 exceptions (A5)
    python3 -m unittest discover -s tests/acceptance -p test_identity.py -v

Every record the suite creates is synthetic, uniquely named and never deleted (the
product refuses deleting firms and contacts): run it on a stack that is torn down
afterwards. The whole matrix of tests/acceptance/identity_matrix.py is driven:
every (relationship, route, kind) cell must be refused-and-unchanged, or
performed-and-audited, as the matrix says. Missing configuration fails loudly.
"""

import base64
import datetime
import json
import os
import secrets
import shlex
import stat
import subprocess
import sys
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import crm_api  # noqa: E402
import identity_matrix as matrix  # noqa: E402
import identity_report  # noqa: E402
import provision_access  # noqa: E402
import provision_users  # noqa: E402

ENV_OUTPUT_DIR = "CRM_ACCESS_OUTPUT_DIR"
ENV_IMPORT_KEY_FILE = "CRM_IDENTITY_IMPORT_KEY_FILE"
ENV_FAULT_ON, ENV_FAULT_OFF = "CRM_AUDIT_FAULT_ON_CMD", "CRM_AUDIT_FAULT_OFF_CMD"
ENV_AGE, ENV_RUN, ENV_COUNT = "CRM_CLEANUP_AGE_CMD", "CRM_CLEANUP_RUN_CMD", "CRM_DB_COUNT_CMD"
ENV_SEEDED = "CRM_SEEDED_EXCEPTION_IDS"
REQUIRED_ENV = (crm_api.ENV_BASE_URL, crm_api.ENV_USERNAME, crm_api.ENV_PASSWORD, ENV_OUTPUT_DIR,
                ENV_IMPORT_KEY_FILE, ENV_FAULT_ON, ENV_FAULT_OFF, ENV_AGE, ENV_RUN, ENV_COUNT)

USERS = [
    {"sfId": "ZZZIDI000000001AAA", "userName": "idi.staff", "firstName": "Identity", "lastName": "Staff",
     "emailAddress": "idi.staff@example.test", "isActive": True, "teams": ["Enquiries"], "roles": ["ER Staff"]},
    {"sfId": "ZZZIDI000000002AAA", "userName": "idi.intake", "firstName": "Identity", "lastName": "Intake",
     "emailAddress": "idi.intake@example.test", "isActive": True, "teams": ["Ancillary intake"],
     "roles": ["ER Intake"]},
    {"sfId": "ZZZIDI000000003AAA", "userName": "idi.manager", "firstName": "Identity", "lastName": "Manager",
     "emailAddress": "idi.manager@example.test", "isActive": True, "teams": ["Firm management"],
     "roles": ["ER Manager"]},
]
USER_OF_KIND = {"staff": "idi.staff", "intake": "idi.intake", "manager": "idi.manager"}
SF_IDS = {u["userName"]: u["sfId"] for u in USERS}

ADMIN = None
CLIENTS = {}
USER_IDS = {}
CREATED = []          # (entity, id) of every record the run created, for A10
RESULTS = {}          # cell -> {"ok": bool, "outcome": str, "audited": bool, "detail": str}
CLEANUP = {}          # the one cleanup-job observation


class ApiKeyClient(crm_api.EspoClient):
    """EspoClient that authenticates with an API key (the ER Import service account)."""

    def __init__(self, base_url, key):
        super().__init__(base_url, "api", "key")
        self._headers = {"X-Api-Key": key, "Accept": "application/json", "Content-Type": "application/json"}


def uniq(label):
    return f"IDI {label} {secrets.token_hex(4)}"


def read_key(path):
    mode = os.stat(path).st_mode
    if not stat.S_ISREG(mode) or mode & 0o077:
        raise AssertionError(f"{ENV_IMPORT_KEY_FILE} must name a regular file with no group or other access")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            name, _, value = line.strip().partition("=")
            if name == "CRM_IMPORT_API_KEY" and value:
                return value
    raise AssertionError(f"{ENV_IMPORT_KEY_FILE} holds no CRM_IMPORT_API_KEY")


def run_operator_command(env_name):
    """Run an operator-supplied command (no shell). Returns stdout; failure is a test failure."""
    res = subprocess.run(shlex.split(os.environ[env_name]), capture_output=True, text=True, timeout=1800)
    if res.returncode != 0:
        raise AssertionError(f"{env_name} failed with exit code {res.returncode}")
    return res.stdout


def out_path(name):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return os.path.join(os.environ[ENV_OUTPUT_DIR], f"{stamp}-{name}")


def provision():
    """Teams, roles, the ER Import user and the three human synthetic users (idempotent)."""
    import contextlib
    import csv
    import io

    def run(main, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv, transport=crm_api.UrllibTransport(), environ=os.environ)
        if code != 0:
            raise AssertionError(f"{main.__module__} failed: {err.getvalue()[:200]}")

    run(provision_access.main, ["dev", "--key-file", out_path("import-key.env")])
    users_file = out_path("users.json")
    with provision_access.create_private_file(users_file) as fh:
        json.dump(USERS, fh)
    passwords = {}
    csv_path = out_path("passwords.csv")
    run(provision_users.main, ["dev", "--input", users_file, "--password-file", csv_path])
    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as fh:
            passwords.update({r["userName"]: r["temporaryPassword"] for r in csv.DictReader(fh)})
    for name in USER_OF_KIND.values():
        if name not in passwords:  # users kept from an earlier run: reset their password
            reset_csv = out_path(f"reset-{name}.csv")
            run(provision_users.main, ["dev", "--reset", SF_IDS[name], "--password-file", reset_csv])
            with open(reset_csv, newline="", encoding="utf-8") as fh:
                passwords[name] = {r["userName"]: r["temporaryPassword"] for r in csv.DictReader(fh)}[name]
    return passwords


def setUpModule():
    global ADMIN
    missing = [n for n in REQUIRED_ENV if not os.environ.get(n)]
    if missing:
        raise AssertionError(f"the identity acceptance suite needs {', '.join(missing)}")
    out = os.environ[ENV_OUTPUT_DIR]
    if not os.path.isdir(out) or stat.S_IMODE(os.stat(out).st_mode) & 0o077:
        raise AssertionError(f"{ENV_OUTPUT_DIR} must be an existing directory with mode 0700")
    base = os.environ[crm_api.ENV_BASE_URL]
    user, password = crm_api.credentials_from_env()
    ADMIN = crm_api.EspoClient(base, user, password)
    passwords = provision()
    CLIENTS["admin"] = ADMIN
    for kind, name in USER_OF_KIND.items():
        CLIENTS[kind] = crm_api.EspoClient(base, name, passwords[name])
        rows = ADMIN.list_all("User", crm_api.where_params([("equals", "userName", name)]))
        USER_IDS[kind] = rows[0]["id"]
    CLIENTS["import"] = ApiKeyClient(base, read_key(os.environ[ENV_IMPORT_KEY_FILE]))
    me = CLIENTS["import"].call("GET", "App/user")["user"]
    USER_IDS["import"] = me["id"]
    USER_IDS["admin"] = ADMIN.call("GET", "App/user")["user"]["id"]


# ---- records -------------------------------------------------------------------------------------

def register(entity, record):
    CREATED.append((entity, record["id"]))
    return record["id"]


def mk_firm(parent=None):
    data = {"name": uniq("firm"), "billingAddressPostalCode": "ZZ99 9ZZ"}
    if parent:
        data["parentId"] = parent
    return register("Account", ADMIN.create("Account", data))


def mk_contact(primary=None, linked=()):
    data = {"firstName": "Identity", "lastName": uniq("contact"),
            "emailAddress": f"idi.{secrets.token_hex(5)}@example.test"}
    if primary:
        data["accountId"] = primary
    if linked:
        data["accountsIds"] = list(linked)
    return register("Contact", ADMIN.create("Contact", data))


def mk_enquiry(firm, assignee):
    close = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    return register("Opportunity", ADMIN.create("Opportunity", {
        "name": uniq("enquiry"), "accountId": firm, "closeDate": close, "amount": 1,
        "assignedUserId": assignee}))


def get(entity, record_id):
    return ADMIN.call("GET", f"{entity}/{record_id}")


def exists(entity, record_id):
    try:
        return bool(get(entity, record_id).get("id"))
    except crm_api.ApiError as err:
        if err.status in (403, 404):
            return False
        raise


def linked_firms(contact_id):
    return sorted(r["id"] for r in ADMIN.list_all(f"Contact/{contact_id}/accounts", {"select": "id"}))


def audits(record_id):
    return ADMIN.list_all("IdentityAudit", crm_api.where_params([("equals", "recordId", record_id)]))


def by_name(entity, field, name):
    return sorted(r["id"] for r in ADMIN.list_all(entity, crm_api.where_params([("equals", field, name)])))


def attempt(fn):
    """Run an action as some account; an API refusal is an outcome, not an error."""
    try:
        fn()
        return None
    except crm_api.ApiError as err:
        return err.status


def mass(client, action, entity, ids, data=None):
    body = {"action": action, "entityType": entity, "params": {"ids": list(ids)}}
    if data is not None:
        body["data"] = data
    return client.call("POST", "MassAction", data=body)


# ---- one world per cell ------------------------------------------------------------------------------

class World:
    """The synthetic records one matrix cell acts on, and how to read their identity state."""

    def __init__(self, relationship, kind):
        self.rel, self.kind = relationship, kind
        self.actor = USER_IDS[kind]
        self.p1, self.p2, self.p3 = mk_firm(), mk_firm(), mk_firm()
        self.name = uniq("new")
        if relationship == "parentFirm":
            self.record = mk_firm(self.p1)
            self.targets = [self.record, self.p1]
        elif relationship == "primaryFirm":
            self.record = mk_contact(self.p1, [self.p1, self.p2, self.p3])
            self.targets = [self.record, self.p1]
        elif relationship == "contactFirmLink":
            self.record = mk_contact(self.p1, [self.p1, self.p3])
            self.targets = [self.record, self.p1]
        elif relationship == "enquiryFirm":
            self.record = mk_enquiry(self.p1, self.actor)
            self.targets = [self.p1]
        else:  # successor
            self.record = mk_firm()
            self.succ = mk_firm()
            self.targets = [self.record, self.succ]
        self.entity = matrix.RECORD_OF[relationship]

    def state(self):
        """What a refused action must leave untouched."""
        s = {"exists": {t: exists(self.entity if t == self.record else "Account", t) for t in self.targets}}
        rec = get(self.entity, self.record)
        if self.rel == "parentFirm":
            s["v"] = rec.get("parentId")
        elif self.rel in ("primaryFirm", "enquiryFirm"):
            s["v"] = rec.get("accountId")
        elif self.rel == "contactFirmLink":
            s["v"] = (rec.get("accountId"), linked_firms(self.record))
        else:
            s["v"] = (rec.get("identityStatus"), rec.get("successorId"))
        return s

    def created_ids(self):
        field = "lastName" if self.entity == "Contact" else "name"
        return by_name(self.entity, field, self.name)

    def audit_count(self):
        n = len([a for a in audits(self.record) if a.get("relationship") == self.rel
                 or (self.rel == "successor" and a.get("relationship") == "status")])
        for new_id in self.created_ids():
            n += len(audits(new_id))
        return n


def payload_for_create(w):
    """The create payload of a world's relationship, with a name unique to this cell."""
    if w.rel == "parentFirm":
        return "Account", {"name": w.name, "billingAddressPostalCode": "ZZ99 9ZZ", "parentId": w.p2}
    if w.rel == "primaryFirm":
        return "Contact", {"firstName": "Identity", "lastName": w.name, "accountId": w.p1,
                           "emailAddress": f"idi.{secrets.token_hex(5)}@example.test"}
    if w.rel == "contactFirmLink":
        return "Contact", {"firstName": "Identity", "lastName": w.name, "accountId": w.p1,
                           "accountsIds": [w.p1, w.p2], "emailAddress": f"idi.{secrets.token_hex(5)}@example.test"}
    if w.rel == "enquiryFirm":
        close = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        return "Opportunity", {"name": w.name, "accountId": w.p2, "closeDate": close, "amount": 1,
                               "assignedUserId": w.actor}
    return "Account", {"name": w.name, "billingAddressPostalCode": "ZZ99 9ZZ",
                       "identityStatus": "superseded", "successorId": w.p1}


def import_csv(client, w, include_id=False):
    """Upload a one-row CSV and ask for it to be imported as the world's record kind."""
    entity, data = payload_for_create(w)
    columns = [k for k in data if not isinstance(data[k], list)]
    if include_id:
        data = dict(data, id=secrets.token_hex(8))
        columns.append("id")
    csv_text = ",".join(columns) + "\n" + ",".join(f'"{data[c]}"' for c in columns) + "\n"
    att = client.create("Attachment", {
        "name": "identity.csv", "type": "text/csv", "role": "Import File", "relatedType": "Import",
        "field": "file", "file": "data:text/csv;base64," + base64.b64encode(csv_text.encode()).decode()})
    client.create("Import", {
        "entityType": entity, "attachmentId": att["id"], "action": "create", "headerRow": True,
        "fieldDelimiter": ",", "textQualifier": "\"", "attributeList": columns, "idleMode": False,
        "silentMode": True, "dateFormat": "YYYY-MM-DD", "timeFormat": "HH:mm", "personNameFormat": "f l",
        "decimalMark": ".", "currency": "GBP", "defaultValues": {}, "skipDuplicateChecking": False,
        "manualMode": False, "timezone": "UTC", "updateBy": []})


def link_routes(w):
    """route -> (method, path, body) of the link and unlink calls for one relationship."""
    rel = w.rel
    succ = getattr(w, "succ", "")  # only the successor world has one
    return {
        "parentFirm": {"link_owner_side": ("POST", f"Account/{w.p2}/branches", {"id": w.record}),
                       "unlink_owner_side": ("DELETE", f"Account/{w.p1}/branches", {"id": w.record}),
                       "bulk_link": ("POST", f"Account/{w.p2}/branches", None)},
        "primaryFirm": {"link_owner_side": ("POST", f"Account/{w.p2}/contactsPrimary", {"id": w.record}),
                        "unlink_owner_side": ("DELETE", f"Account/{w.p1}/contactsPrimary", {"id": w.record}),
                        "bulk_link": ("POST", f"Account/{w.p2}/contactsPrimary", None)},
        "contactFirmLink": {"link_owner_side": ("POST", f"Contact/{w.record}/accounts", {"id": w.p2}),
                            "link_other_side": ("POST", f"Account/{w.p2}/contacts", {"id": w.record}),
                            "unlink_owner_side": ("DELETE", f"Contact/{w.record}/accounts", {"id": w.p3}),
                            "unlink_other_side": ("DELETE", f"Account/{w.p3}/contacts", {"id": w.record}),
                            "bulk_link": ("POST", f"Account/{w.p2}/contacts", None)},
        "enquiryFirm": {"link_owner_side": ("POST", f"Account/{w.p2}/opportunities", {"id": w.record}),
                        "unlink_owner_side": ("DELETE", f"Account/{w.p1}/opportunities", {"id": w.record}),
                        "bulk_link": ("POST", f"Account/{w.p2}/opportunities", None)},
        "successor": {"link_owner_side": ("POST", f"Account/{succ}/predecessors", {"id": w.record}),
                      "link_other_side": ("POST", f"Account/{w.record}/successor", {"id": succ}),
                      "unlink_owner_side": ("DELETE", f"Account/{succ}/predecessors", {"id": w.record}),
                      "unlink_other_side": ("DELETE", f"Account/{w.record}/successor", {"id": succ}),
                      "bulk_link": ("POST", f"Account/{succ}/predecessors", None)},
    }[rel]


def act(w, route, client):
    """Perform one route as one account. Returns nothing: the outcome is read from the stack."""
    rel, E = w.rel, w.entity
    if route == "record_create":
        entity, data = payload_for_create(w)
        return client.create(entity, data)
    if route == "supplied_id":
        entity, data = payload_for_create(w)
        return client.create(entity, dict(data, id=secrets.token_hex(8)))
    if route == "csv_import":
        return import_csv(client, w, include_id=True)
    if route == "record_edit":
        body = {"parentFirm": {"parentId": w.p2}, "primaryFirm": {"accountId": w.p2},
                "contactFirmLink": {"accountsIds": [w.p1, w.p2, w.p3]}, "enquiryFirm": {"accountId": w.p2},
                "successor": {"identityStatus": "superseded", "successorId": w.succ if rel == "successor" else None,
                              "description": "edited"}}[rel]
        return client.call("PUT", f"{E}/{w.record}", data=body)
    if route == "retire":
        return client.call("PUT", f"{E}/{w.record}", data={"identityStatus": "retired"})
    if route == "supersede":
        return client.call("PUT", f"{E}/{w.record}", data={"identityStatus": "superseded", "successorId": w.succ})
    links = link_routes(w)
    if route in links:
        method, path, body = links[route]
        if route == "bulk_link":
            body = {"massRelate": True, "where": [{"type": "equals", "attribute": "id", "value": w.record}]}
        return client.call(method, path, data=body)
    if route == "mass_update":
        data = {"parentFirm": {"parentId": w.p2}, "primaryFirm": {"accountId": w.p2},
                "enquiryFirm": {"accountId": w.p2}, "successor": {"identityStatus": "retired"}}[rel]
        return mass(client, "update", E, [w.record], data)
    if route == "delete":
        for target in w.targets:
            attempt(lambda t=target: client.delete(E if t == w.record else "Account", t))
        return None
    if route == "mass_delete":
        for target in w.targets:
            attempt(lambda t=target: mass(client, "delete", E if t == w.record else "Account", [t]))
        return None
    if route == "merge":
        if E == "Contact":
            other = mk_contact(w.p1, [w.p1])
            return client.call("POST", "Contact/action/merge",
                               data={"targetId": w.record, "sourceIdList": [other], "attributes": {}})
        other = w.p2
        target = w.p1 if rel in ("parentFirm", "enquiryFirm") else w.record
        if rel == "successor":
            other = w.succ
        return client.call("POST", "Account/action/merge",
                           data={"targetId": target, "sourceIdList": [other], "attributes": {}})
    raise AssertionError(f"no action for route {route}")


def evaluate(expect, before, after, audit_before, audit_after, created_before, created_after):
    """(ok, outcome, audited, detail) for one attempted cell."""
    changed = before != after or created_after != created_before
    audited = audit_after > audit_before
    if changed:
        outcome = "performed"
    else:
        outcome = "refused"
    if expect == "refused":
        return (not changed), outcome, audited, "a change got through" if changed else ""
    if expect == "performed":
        return (changed and audited), outcome, audited, \
            "" if changed and audited else ("not performed" if not changed else "performed without an audit record")
    if expect == "either":
        return (not changed or audited), outcome, audited, "" if not changed or audited else \
            "performed without an audit record"
    raise AssertionError(expect)


def run_cell(relationship, route, kind):
    expect, _ = matrix.expectation(relationship, route, kind)
    if expect == "na":
        return {"ok": True, "outcome": "na", "audited": False, "detail": ""}
    if route == "cleanup_job":
        ok = CLEANUP.get("removed") == 0
        return {"ok": ok, "outcome": "refused" if ok else "performed", "audited": False,
                "detail": "" if ok else "the cleanup job removed records"}
    w = World(relationship, kind)
    before, audit_before, created_before = w.state(), w.audit_count(), w.created_ids()
    attempt(lambda: act(w, route, CLIENTS[kind]))
    after, audit_after, created_after = w.state(), w.audit_count(), w.created_ids()
    ok, outcome, audited, detail = evaluate(expect, before, after, audit_before, audit_after,
                                            created_before, created_after)
    return {"ok": ok, "outcome": outcome, "audited": audited, "detail": detail}


def cleanup_observation():
    """A7: age every retention period, run the cleanup job, count rows before and after."""
    def counts():
        parts = run_operator_command(ENV_COUNT).split()
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise AssertionError(f"{ENV_COUNT} must print three integers")
        return [int(p) for p in parts]

    before = counts()
    run_operator_command(ENV_AGE)
    run_operator_command(ENV_RUN)
    after = counts()
    return {"before": before, "after": after,
            "removed": sum(max(b - a, 0) for b, a in zip(before, after))}


class TestIdentityAcceptance(unittest.TestCase):
    """Methods run in name order; later ones read what earlier ones recorded."""

    def test_a01_matrix_every_cell(self):
        CLEANUP.update(cleanup_observation())
        for cell in matrix.cells():
            with self.subTest(cell="/".join(cell)):
                RESULTS[cell] = run_cell(*cell)
                self.assertTrue(RESULTS[cell]["ok"], RESULTS[cell]["detail"])
        self.assertEqual(set(RESULTS), set(matrix.cells()), "a matrix cell was not driven")
        failed = [c for c, r in RESULTS.items() if not r["ok"]]
        print(f"identity matrix: {len(RESULTS) - len(failed)} of {len(RESULTS)} cells pass")
        self.assertEqual(failed, [])

    def test_a02_every_editing_role_can_still_change_each_relationship(self):
        self.assertTrue(RESULTS, "run test_a01 first")
        for rel in matrix.RELATIONSHIPS:
            for kind in matrix.HUMAN_KINDS + ["import"]:
                with self.subTest(relationship=rel, kind=kind):
                    done = [r for r in matrix.ROUTES
                            if RESULTS[(rel, r, kind)]["outcome"] == "performed" and RESULTS[(rel, r, kind)]["audited"]
                            and r not in matrix.REFUSED_ROUTES]
                    self.assertTrue(done, "no supported route changed it with an audit record")

    def test_a03_audit_storage_unwritable_nothing_changes(self):
        # Records are made first: with storage unwritable even a plain set-up could not link them.
        cases = []
        for rel in matrix.RELATIONSHIPS:
            for kind in matrix.KINDS:
                for route in matrix.ROUTES:
                    expect, _ = matrix.expectation(rel, route, kind)
                    if expect == "na" or route == "cleanup_job":
                        continue
                    w = World(rel, kind)
                    cases.append((f"{rel}/{route}/{kind}", route, kind, w, w.state(), w.created_ids()))
        run_operator_command(ENV_FAULT_ON)
        observed = []
        try:
            for label, route, kind, w, state, created in cases:
                attempt(lambda: act(w, route, CLIENTS[kind]))
                observed.append((label, w.state() == state and w.created_ids() == created))
        finally:
            run_operator_command(ENV_FAULT_OFF)
        self.assertEqual(len(observed), len(cases))
        for label, unchanged in observed:
            with self.subTest(cell=label):
                self.assertTrue(unchanged, "a change succeeded while audit storage was unwritable")

    def test_a04_audit_records_are_protected_for_every_account(self):
        firm = mk_firm()
        parent = mk_firm()
        ADMIN.call("PUT", f"Account/{firm}", data={"parentId": parent})
        record = audits(firm)[0]
        for kind, client in CLIENTS.items():
            with self.subTest(kind=kind):
                for fn in (lambda: client.call("PUT", f"IdentityAudit/{record['id']}", data={"newValue": "x"}),
                           lambda: client.delete("IdentityAudit", record["id"]),
                           lambda: mass(client, "delete", "IdentityAudit", [record["id"]]),
                           lambda: mass(client, "update", "IdentityAudit", [record["id"]], {"newValue": "x"}),
                           lambda: client.create("IdentityAudit", {"name": "forged", "recordId": firm,
                                                                  "relationship": "parentFirm",
                                                                  "recordType": "Account"})):
                    attempt(fn)
                self.assertEqual(ADMIN.call("GET", f"IdentityAudit/{record['id']}")["newValue"], record["newValue"])
                self.assertEqual(len(audits(firm)), 1)

    def test_a05_primary_firm_rule_and_exceptions_report(self):
        before_ids = set(identity_report.find_exceptions(ADMIN))
        seeded = {s for s in os.environ.get(ENV_SEEDED, "").split(",") if s}
        if seeded:
            self.assertEqual(before_ids, seeded, "the report must list exactly the seeded exceptions")
        # 3.3: removing the primary link is refused unless the same change sets or clears the primary.
        a, b = mk_firm(), mk_firm()
        c = mk_contact(a, [a, b])
        for kind, client in CLIENTS.items():
            with self.subTest(kind=kind):
                attempt(lambda: client.call("DELETE", f"Contact/{c}/accounts", data={"id": a}))
                attempt(lambda: client.call("DELETE", f"Account/{a}/contacts", data={"id": c}))
                attempt(lambda: client.call("PUT", f"Contact/{c}", data={"accountsIds": [b]}))
                self.assertEqual(get("Contact", c)["accountId"], a)
                self.assertIn(a, linked_firms(c))
        ADMIN.call("PUT", f"Contact/{c}", data={"accountId": b, "accountsIds": [b]})
        self.assertEqual((get("Contact", c)["accountId"], linked_firms(c)), (b, [b]))
        ADMIN.call("PUT", f"Contact/{c}", data={"accountId": None, "accountsIds": []})
        self.assertFalse(get("Contact", c).get("accountId"))
        # The matrix run created nothing that breaks the rule, and the report is read-only.
        digest = json.dumps(sorted((r["id"], r.get("modifiedAt"), r.get("accountId"))
                                   for r in ADMIN.list_all("Contact", {"select": "id,modifiedAt,accountId"})))
        after_ids = set(identity_report.find_exceptions(ADMIN))
        self.assertEqual(after_ids - before_ids, set(), "a contact now breaks the primary-firm rule")
        self.assertEqual(digest, json.dumps(sorted(
            (r["id"], r.get("modifiedAt"), r.get("accountId"))
            for r in ADMIN.list_all("Contact", {"select": "id,modifiedAt,accountId"}))))

    def test_a06_delete_mass_delete_and_merge_refused_for_every_account(self):
        self.assertTrue(RESULTS, "run test_a01 first")
        for rel in matrix.RELATIONSHIPS:
            for route in ("delete", "mass_delete", "merge"):
                for kind in matrix.KINDS:
                    with self.subTest(cell=f"{rel}/{route}/{kind}"):
                        self.assertEqual(RESULTS[(rel, route, kind)]["outcome"], "refused")

    def test_a07_cleanup_job_removes_nothing(self):
        self.assertTrue(CLEANUP, "run test_a01 first")
        self.assertEqual(CLEANUP["removed"], 0, "the cleanup job removed firm, contact or audit rows")
        self.assertGreaterEqual(CLEANUP["after"][2], CLEANUP["before"][2])

    def test_a08_supplied_identifiers_are_never_used_and_import_is_refused(self):
        for kind, client in CLIENTS.items():
            for entity, make in (("Account", lambda: {"name": uniq("supplied"), "billingAddressPostalCode": "ZZ99 9ZZ"}),
                                 ("Contact", lambda: {"lastName": uniq("supplied"),
                                                      "emailAddress": f"idi.{secrets.token_hex(5)}@example.test"})):
                with self.subTest(kind=kind, entity=entity):
                    chosen = "chosen" + secrets.token_hex(6)
                    attempt(lambda: client.create(entity, dict(make(), id=chosen)))
                    self.assertFalse(exists(entity, chosen), "a supplied identifier was used")
        for rel in ("parentFirm", "primaryFirm", "enquiryFirm"):
            for kind in matrix.KINDS:
                with self.subTest(import_for=rel, kind=kind):
                    w = World(rel, kind)
                    created_before = w.created_ids()
                    attempt(lambda: import_csv(CLIENTS[kind], w))
                    self.assertEqual(w.created_ids(), created_before, "CSV import created a record")

    def test_a09_over_length_input_is_a_validation_error_and_changes_nothing(self):
        firm = mk_firm()
        for kind, client in CLIENTS.items():
            with self.subTest(kind=kind):
                name = uniq("long")
                before = len(ADMIN.list_all("Contact", {"select": "id"}))
                try:
                    client.create("Contact", {"lastName": name, "title": "t" * 300, "accountId": firm,
                                              "emailAddress": f"idi.{secrets.token_hex(5)}@example.test"})
                except crm_api.ApiError as err:
                    self.assertEqual(err.status, 400, "over-length input must be a validation error")
                else:
                    self.fail("over-length input was accepted")
                self.assertEqual(len(ADMIN.list_all("Contact", {"select": "id"})), before)
        c = mk_contact(firm, [firm])
        with self.assertRaises(crm_api.ApiError) as ctx:
            ADMIN.call("PUT", f"Contact/{c}", data={"title": "t" * 300})
        self.assertEqual(ctx.exception.status, 400)
        self.assertNotEqual(get("Contact", c).get("title"), "t" * 300)

    def test_a10_every_identifier_resolves_and_bad_successors_are_refused(self):
        for entity in ("Account", "Contact"):
            first = mk_firm() if entity == "Account" else mk_contact()
            second = mk_firm() if entity == "Account" else mk_contact()
            third = mk_firm() if entity == "Account" else mk_contact()
            for bad in ({"identityStatus": "superseded", "successorId": first},      # self
                        {"identityStatus": "superseded", "successorId": "missing" + secrets.token_hex(4)},
                        {"identityStatus": "superseded", "successorId": USER_IDS["admin"]},   # wrong kind
                        {"identityStatus": "superseded"},
                        {"identityStatus": "retired", "successorId": second}):
                with self.subTest(entity=entity, bad=bad):
                    with self.assertRaises(crm_api.ApiError) as ctx:
                        ADMIN.call("PUT", f"{entity}/{first}", data=bad)
                    self.assertIn(ctx.exception.status, (400, 403))
                    self.assertEqual(get(entity, first)["identityStatus"], "active")
            ADMIN.call("PUT", f"{entity}/{first}", data={"identityStatus": "superseded", "successorId": second})
            ADMIN.call("PUT", f"{entity}/{second}", data={"identityStatus": "superseded", "successorId": third})
            with self.subTest(entity=entity, case="cycle"):
                with self.assertRaises(crm_api.ApiError):
                    ADMIN.call("PUT", f"{entity}/{third}", data={"identityStatus": "superseded", "successorId": first})
                self.assertEqual(get(entity, third)["identityStatus"], "active")
            ADMIN.call("PUT", f"{entity}/{third}", data={"identityStatus": "retired"})
            self.assertEqual(self.resolve(entity, first), (third, "retired"))
            self.assertTrue([a for a in audits(first) if a["relationship"] == "successor"])
        for entity, record_id in CREATED:
            if entity in ("Account", "Contact"):
                with self.subTest(identifier=record_id):
                    end, status = self.resolve(entity, record_id)
                    self.assertIn(status, ("active", "retired"))

    @staticmethod
    def resolve(entity, record_id):
        """Follow successors to the end: (identifier, status of the end). Refuses a loop."""
        seen = set()
        current = record_id
        while True:
            assert current not in seen, "successor loop"
            seen.add(current)
            rec = get(entity, current)
            assert rec["identityStatus"] in ("active", "retired", "superseded")
            if rec["identityStatus"] != "superseded":
                assert not rec.get("successorId")
                return current, rec["identityStatus"]
            current = rec["successorId"]


if __name__ == "__main__":
    unittest.main()
