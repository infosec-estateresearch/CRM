"""Provisioning tests (WO CRM-003 items 3, 4 and 7): teams, roles, the API user
and named users against an in-memory fake EspoCRM, with no network.

Covers idempotency (a second run writes nothing and issues no password),
password strength, the password and API-key sentinels never reaching stdout,
stderr or logs, and the 0600 never-overwritten output files. All data is
synthetic (example.test; sfIds start with ZZZ)."""

import copy
import csv
import io
import json
import logging
import os
import stat
import string
import sys
import tempfile
import unittest
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import provision_access  # noqa: E402
import provision_users  # noqa: E402

BASE = "http://127.0.0.1:8180"
ENV = {"CRM_ADMIN_USERNAME": "unit-admin", "CRM_ADMIN_PASSWORD": "unit-admin-pass",
       "CRM_BASE_URL": BASE}
API_KEY_SENTINEL = "NOT-A-REAL-KEY-SENTINEL"


def synthetic_users():
    return [
        {"sfId": "ZZZTEST00000001AAA", "userName": "staff.one", "firstName": "Alex",
         "lastName": "Testperson", "emailAddress": "staff.one@example.test", "isActive": True,
         "teams": ["Enquiries"], "roles": ["ER Staff"]},
        {"sfId": "ZZZTEST00000002AAA", "userName": "intake.one", "firstName": "Sam",
         "lastName": "Sampleton", "emailAddress": "intake.one@example.test", "isActive": True,
         "teams": ["Ancillary intake"], "roles": ["ER Intake"]},
        {"sfId": "ZZZTEST00000003AAA", "userName": "former.one", "firstName": "Jo",
         "lastName": "Formerly", "emailAddress": "former.one@example.test", "isActive": False,
         "teams": [], "roles": ["ER Staff"]},
        {"sfId": "ZZZTEST00000004AAA", "userName": "shared.intake", "firstName": "",
         "lastName": "Shared Intake", "emailAddress": "", "isActive": True,
         "teams": ["Enquiries"], "roles": ["ER Intake"]},
    ]


LEGACY = "ZZZTEST00000004AAA"


class FakeEspo:
    """Just enough of the EspoCRM REST API: list with equals filters, read,
    create and update for Team, Role and User. Passwords are kept apart from
    the records, as EspoCRM keeps only a hash."""

    def __init__(self, drop_sf_id=False, fail=None):
        self.records = {"Team": {}, "Role": {}, "User": {}}
        self.passwords = {}
        self.calls = []
        self.drop_sf_id = drop_sf_id
        self.fail = fail  # (method, entity, nth) -> answer HTTP 500 on that call
        self.next_id = 1
        self.records["User"]["admin1"] = {"id": "admin1", "userName": "unit-admin",
                                          "type": "admin", "isActive": True,
                                          "lastAccess": "2026-11-01 09:00:00"}

    def writes(self):
        return [c for c in self.calls if c["method"] != "GET"]

    def _new_id(self):
        self.next_id += 1
        return f"rec{self.next_id:04d}"

    def _public(self, entity, rec):
        out = copy.deepcopy(rec)
        if entity == "User" and rec.get("type") == "api":
            out["apiKey"] = rec["_apiKey"]
        out.pop("_apiKey", None)
        return out

    def request(self, method, url, headers, body):
        parts = urllib.parse.urlsplit(url)
        path = parts.path.split("/api/v1/", 1)[1].split("/")
        data = json.loads(body) if body else None
        self.calls.append({"method": method, "path": "/".join(path), "data": data,
                           "body": body or b""})
        entity = path[0]
        if self.fail:
            f_method, f_entity, nth = self.fail
            if method == f_method and entity == f_entity:
                seen = sum(1 for c in self.calls
                           if c["method"] == method and c["path"].split("/")[0] == entity)
                if seen == nth:
                    return 500, b'{"message":"fake failure"}'
        store = self.records[entity]
        if method == "GET" and len(path) == 1:
            query = urllib.parse.parse_qs(parts.query)
            rows = list(store.values())
            i = 0
            while f"where[{i}][type]" in query:
                attr = query[f"where[{i}][attribute]"][0]
                value = query[f"where[{i}][value]"][0]
                rows = [r for r in rows if r.get(attr) == value]
                i += 1
            rows.sort(key=lambda r: r["id"])
            offset = int(query.get("offset", ["0"])[0])
            size = int(query.get("maxSize", ["200"])[0])
            page = [{k: v for k, v in r.items() if not k.startswith("_")}
                    for r in rows[offset:offset + size]]
            return 200, json.dumps({"total": len(rows), "list": page}).encode()
        if method == "GET":
            rec = store.get(path[1])
            return (200, json.dumps(self._public(entity, rec)).encode()) if rec else (404, b"")
        if method == "POST":
            if entity == "User" and any(u.get("userName") == data.get("userName")
                                        for u in store.values()):
                return 409, b'{"reason":"userNameExists"}'
            rec = dict(data, id=self._new_id())
            self._take_password(rec)
            if self.drop_sf_id:
                rec.pop("sfId", None)
            if entity == "User" and rec.get("type") == "api":
                rec["_apiKey"] = API_KEY_SENTINEL
            store[rec["id"]] = rec
            return 200, json.dumps(self._public(entity, rec)).encode()
        if method == "PUT":
            rec = store[path[1]]
            rec.update(data)
            self._take_password(rec)
            return 200, json.dumps(self._public(entity, rec)).encode()
        return 405, b""

    def _take_password(self, rec):
        if "password" in rec:
            self.passwords[rec["id"]] = rec.pop("password")
            rec.pop("passwordConfirm", None)

    def by_user_name(self, name):
        return next(u for u in self.records["User"].values() if u.get("userName") == name)


def run(main, argv, fake, environ=None):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv, transport=fake, environ=ENV if environ is None else environ)
    return code, out.getvalue(), err.getvalue()


class TmpDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def write_users(self, users, name="users.json"):
        with open(self.path(name), "w", encoding="utf-8") as fh:
            json.dump(users, fh)
        return self.path(name)

    def provision_access(self, fake, key_name="key.env", *extra):
        return run(provision_access.main, ["dev", "--key-file", self.path(key_name), *extra], fake)

    def provision_users(self, fake, users, csv_name="pw.csv", *extra):
        return run(provision_users.main, ["dev", "--input", self.write_users(users),
                                          "--password-file", self.path(csv_name), *extra], fake)

    def read_csv(self, name="pw.csv"):
        with open(self.path(name), newline="", encoding="utf-8") as fh:
            return list(csv.reader(fh))

    def mode(self, name):
        return stat.S_IMODE(os.stat(self.path(name)).st_mode)


class TestEnvironmentGuard(TmpDir):
    def test_both_scripts_refuse_any_target_but_dev(self):
        for main in (provision_access.main, provision_users.main):
            x = self.path("x")
            for argv in ([], ["prod"], ["beta", "--key-file", x], ["DEV"], ["--input", x],
                         ["prod", "--input", x, "--password-file", x]):
                with self.subTest(script=main.__module__, argv=argv):
                    fake = FakeEspo()
                    code, _, err = run(main, argv, fake)
                    self.assertEqual(code, 2)
                    self.assertIn("refusing to run", err)
                    self.assertEqual(fake.calls, [])
                    self.assertFalse(os.path.lexists(x))

    def test_missing_credentials_fail_loudly_without_http(self):
        fake = FakeEspo()
        code, _, err = run(provision_access.main, ["dev", "--key-file", self.path("k")], fake,
                           environ={"CRM_BASE_URL": BASE})
        self.assertEqual(code, 2)
        self.assertIn("CRM_ADMIN_USERNAME", err)
        self.assertEqual(fake.calls, [])
        self.assertFalse(os.path.exists(self.path("k")))


class TestProvisionAccess(TmpDir):
    def test_first_run_creates_teams_roles_and_api_user(self):
        fake = FakeEspo()
        code, out, err = self.provision_access(fake)
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(t["name"] for t in fake.records["Team"].values()),
                         ["Ancillary intake", "Enquiries", "Firm management"])
        roles = {r["name"]: r for r in fake.records["Role"].values()}
        self.assertEqual(sorted(roles), ["ER Import", "ER Intake", "ER Manager", "ER Staff"])
        self.assertEqual(roles["ER Staff"]["data"]["Opportunity"]["edit"], "own")
        api = fake.by_user_name("er-import")
        self.assertEqual((api["type"], api["authMethod"], api["isActive"]), ("api", "ApiKey", True))
        self.assertEqual(api["rolesIds"], [roles["ER Import"]["id"]])
        self.assertNotIn("password", fake.writes()[-1]["data"])
        self.assertEqual(json.loads(out)["role"]["created"], 4)

    def test_api_key_goes_only_to_a_new_0600_file(self):
        fake = FakeEspo()
        old = os.umask(0)
        try:
            code, out, err = self.provision_access(fake)
        finally:
            os.umask(old)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.mode("key.env"), 0o600)
        with open(self.path("key.env"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "CRM_IMPORT_USERNAME=er-import\n"
                                        f"CRM_IMPORT_API_KEY={API_KEY_SENTINEL}\n")
        self.assertNotIn(API_KEY_SENTINEL, out + err)

    def test_second_run_changes_nothing_and_writes_no_key(self):
        fake = FakeEspo()
        self.assertEqual(self.provision_access(fake)[0], 0)
        before = copy.deepcopy(fake.records)
        fake.calls.clear()
        code, out, err = self.provision_access(fake, "key2.env")
        self.assertEqual(code, 0, err)
        self.assertEqual(fake.writes(), [])
        self.assertEqual(fake.records, before)
        self.assertFalse(os.path.lexists(self.path("key2.env")))
        counts = json.loads(out)
        self.assertEqual(counts["team"], {"created": 0, "updated": 0, "unchanged": 3})
        self.assertEqual(counts["role"], {"created": 0, "updated": 0, "unchanged": 4})
        self.assertEqual(counts["apiUser"], {"created": 0, "updated": 0, "unchanged": 1})
        self.assertNotIn(API_KEY_SENTINEL, out + err)

    def test_drift_is_corrected_by_name_with_only_the_changed_attributes(self):
        fake = FakeEspo()
        self.provision_access(fake)
        staff = next(r for r in fake.records["Role"].values() if r["name"] == "ER Staff")
        staff["data"]["Account"]["delete"] = "all"
        staff["exportPermission"] = "yes"
        fake.calls.clear()
        code, _, err = self.provision_access(fake, "key2.env")
        self.assertEqual(code, 0, err)
        self.assertEqual([(c["method"], c["path"]) for c in fake.writes()],
                         [("PUT", f"Role/{staff['id']}")])
        self.assertEqual(set(fake.writes()[0]["data"]), {"data", "exportPermission"})
        self.assertEqual(staff["data"]["Account"]["delete"], "no")

    def test_existing_key_file_is_refused_before_any_http(self):
        with open(self.path("key.env"), "w") as fh:
            fh.write("keep me\n")
        fake = FakeEspo()
        code, _, err = self.provision_access(fake)
        self.assertEqual(code, 1)
        self.assertIn("refusing to overwrite", err)
        self.assertEqual(fake.calls, [])
        with open(self.path("key.env")) as fh:
            self.assertEqual(fh.read(), "keep me\n")

    def test_create_private_file_itself_never_replaces_a_file(self):
        # independent of the up-front check: O_EXCL also covers a file that appears later
        with open(self.path("late.env"), "w") as fh:
            fh.write("keep me\n")
        with self.assertRaises(provision_access.ProvisionError):
            provision_access.create_private_file(self.path("late.env"))
        with open(self.path("late.env")) as fh:
            self.assertEqual(fh.read(), "keep me\n")

    def test_symlinked_key_file_is_refused(self):
        os.symlink(self.path("elsewhere"), self.path("key.env"))
        fake = FakeEspo()
        self.assertEqual(self.provision_access(fake)[0], 1)
        self.assertFalse(os.path.exists(self.path("elsewhere")))

    def test_import_user_can_be_deactivated_and_stays_so(self):
        fake = FakeEspo()
        self.provision_access(fake)
        code, _, err = self.provision_access(fake, "k2", "--import-user-active", "no")
        self.assertEqual(code, 0, err)
        self.assertFalse(fake.by_user_name("er-import")["isActive"])
        fake.calls.clear()
        self.assertEqual(self.provision_access(fake, "k3")[0], 0)
        self.assertEqual(fake.writes(), [])
        self.assertFalse(fake.by_user_name("er-import")["isActive"])

    def test_a_regular_user_with_the_api_user_name_is_not_converted(self):
        fake = FakeEspo()
        fake.records["User"]["u9"] = {"id": "u9", "userName": "er-import", "type": "regular"}
        code, _, err = self.provision_access(fake)
        self.assertEqual(code, 1)
        self.assertIn("not an API user", err)
        self.assertEqual(fake.records["User"]["u9"]["type"], "regular")


class UsersBase(TmpDir):
    def setUp(self):
        super().setUp()
        self.fake = FakeEspo()
        code, _, err = self.provision_access(self.fake)
        self.assertEqual(code, 0, err)
        self.fake.calls.clear()


class TestProvisionUsers(UsersBase):
    def first_run(self, users=None):
        code, out, err = self.provision_users(self.fake, users or synthetic_users(),
                                              "pw.csv", "--legacy-shared", LEGACY)
        self.assertEqual(code, 0, err)
        return out, err

    def test_first_run_creates_users_with_temporary_passwords_for_active_only(self):
        out, _ = self.first_run()
        users = {u["userName"]: u for u in self.fake.records["User"].values()
                 if u.get("type") == "regular"}
        self.assertEqual(sorted(users), ["former.one", "intake.one", "shared.intake", "staff.one"])
        for u in users.values():
            self.assertFalse(u["sendAccessInfo"])
            self.assertEqual(u["type"], "regular")
        self.assertTrue(users["staff.one"]["isActive"])
        self.assertFalse(users["former.one"]["isActive"])
        self.assertFalse(users["shared.intake"]["isActive"], "legacy shared identity is inactive")
        rows = self.read_csv()
        self.assertEqual(rows[0], ["sfId", "userName", "temporaryPassword"])
        self.assertEqual({r[1] for r in rows[1:]}, {"staff.one", "intake.one"})
        for sf_id, name, pw in rows[1:]:
            self.assertEqual(self.fake.passwords[users[name]["id"]], pw)
            self.assertEqual(users[name]["sfId"], sf_id)
        for name in ("former.one", "shared.intake"):  # random, never recorded
            self.assertNotIn(self.fake.passwords[users[name]["id"]],
                             {r[2] for r in rows[1:]})
        self.assertEqual(json.loads(out)["passwordsIssued"], 2)
        staff_role = next(r for r in self.fake.records["Role"].values() if r["name"] == "ER Staff")
        self.assertEqual(users["staff.one"]["rolesIds"], [staff_role["id"]])

    def test_csv_is_0600_even_with_a_permissive_umask(self):
        old = os.umask(0)
        try:
            self.first_run()
        finally:
            os.umask(old)
        self.assertEqual(self.mode("pw.csv"), 0o600)

    def test_second_run_writes_nothing_and_issues_no_password(self):
        self.first_run()
        before = (copy.deepcopy(self.fake.records), dict(self.fake.passwords))
        self.fake.calls.clear()
        code, out, err = self.provision_users(self.fake, synthetic_users(), "pw2.csv",
                                              "--legacy-shared", LEGACY)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.fake.writes(), [])
        self.assertEqual((self.fake.records, self.fake.passwords), before)
        self.assertFalse(os.path.lexists(self.path("pw2.csv")))
        counts = json.loads(out)
        self.assertEqual(counts["passwordsIssued"], 0)
        self.assertEqual(counts["user"], {"created": 0, "updated": 0, "unchanged": 4})

    def test_rerun_updates_names_state_teams_roles_but_never_passwords(self):
        self.first_run()
        passwords = dict(self.fake.passwords)
        users = synthetic_users()
        users[0].update(lastName="Renamed", isActive=False, teams=["Firm management"],
                        roles=["ER Manager"], emailAddress="STAFF.ONE@example.test")
        self.fake.calls.clear()
        code, _, err = self.provision_users(self.fake, users, "pw2.csv", "--legacy-shared", LEGACY)
        self.assertEqual(code, 0, err)
        writes = self.fake.writes()
        self.assertEqual(len(writes), 1)
        self.assertEqual(set(writes[0]["data"]), {"lastName", "isActive", "teamsIds", "rolesIds"})
        self.assertEqual(self.fake.passwords, passwords)
        self.assertFalse(self.fake.by_user_name("staff.one")["isActive"])
        self.assertFalse(os.path.lexists(self.path("pw2.csv")))

    def test_reactivated_user_gets_no_password_until_reset(self):
        self.first_run()
        users = synthetic_users()
        users[2]["isActive"] = True
        self.fake.calls.clear()
        code, _, err = self.provision_users(self.fake, users, "pw2.csv", "--legacy-shared", LEGACY)
        self.assertEqual(code, 0, err)
        self.assertNotIn("password", self.fake.writes()[0]["data"])
        self.assertIn("--reset ZZZTEST00000003AAA", err)

    def test_legacy_shared_identity_stays_inactive_on_reruns(self):
        self.first_run()
        self.fake.calls.clear()
        self.provision_users(self.fake, synthetic_users(), "pw2.csv", "--legacy-shared", LEGACY)
        self.assertEqual(self.fake.writes(), [])
        self.assertFalse(self.fake.by_user_name("shared.intake")["isActive"])

    def test_existing_password_file_is_never_overwritten(self):
        with open(self.path("pw.csv"), "w") as fh:
            fh.write("earlier passwords\n")
        code, _, err = self.provision_users(self.fake, synthetic_users())
        self.assertEqual(code, 1)
        self.assertIn("refusing to overwrite", err)
        self.assertEqual(self.fake.calls, [])
        with open(self.path("pw.csv")) as fh:
            self.assertEqual(fh.read(), "earlier passwords\n")

    def test_password_file_is_required(self):
        code, _, err = run(provision_users.main,
                           ["dev", "--input", self.write_users(synthetic_users())], self.fake)
        self.assertEqual(code, 1)
        self.assertIn("--password-file is required", err)
        self.assertEqual(self.fake.calls, [])

    def test_user_name_taken_without_the_sf_id_is_not_adopted(self):
        self.fake.records["User"]["u7"] = {"id": "u7", "userName": "staff.one", "type": "regular"}
        code, _, err = self.provision_users(self.fake, synthetic_users()[:1])
        self.assertEqual(code, 1)
        self.assertIn("refusing to adopt", err)
        self.assertFalse([c for c in self.fake.writes() if c["method"] == "POST"])
        self.assertNotIn("sfId", self.fake.records["User"]["u7"])

    def test_sf_id_on_an_admin_or_api_user_is_refused(self):
        self.fake.records["User"]["admin1"]["sfId"] = "ZZZTEST00000001AAA"
        code, _, err = self.provision_users(self.fake, synthetic_users()[:1])
        self.assertEqual(code, 1)
        self.assertIn("only regular users", err)
        self.assertEqual(self.fake.writes(), [])

    def test_dropped_sf_id_fails_loudly_and_keeps_the_password(self):
        self.fake.drop_sf_id = True  # what EspoCRM would do if it ignored read-only input
        code, _, err = self.provision_users(self.fake, synthetic_users()[:1])
        self.assertEqual(code, 1)
        self.assertIn("did not store its sfId", err)
        self.assertEqual([r[1] for r in self.read_csv()[1:]], ["staff.one"])

    def test_api_failure_reports_status_only(self):
        self.fake.fail = ("POST", "User", 2)
        code, _, err = self.provision_users(self.fake, synthetic_users())
        self.assertEqual(code, 1)
        self.assertIn("POST User -> HTTP 500", err)
        self.assertEqual([r[1] for r in self.read_csv()[1:]], ["staff.one"],
                         "only the user that was created has a recorded password")
        self.assertIn("1 temporary password(s) written", err)

    def test_invalid_input_is_refused_before_any_http(self):
        cases = {
            "bad sfId": lambda u: u[0].update(sfId="not-an-id"),
            "unknown team": lambda u: u[0].update(teams=["Nope"]),
            "unknown role": lambda u: u[0].update(roles=["Administrator"]),
            "API-only role": lambda u: u[0].update(roles=["ER Import"]),
            "duplicate sfId": lambda u: u[1].update(sfId=u[0]["sfId"]),
            "duplicate userName": lambda u: u[1].update(userName="STAFF.ONE"),
            "extra key": lambda u: u[0].update(type="admin"),
            "missing key": lambda u: u[0].pop("roles"),
            "isActive not bool": lambda u: u[0].update(isActive="yes"),
            "no lastName": lambda u: u[0].update(lastName=" "),
            "bad email": lambda u: u[0].update(emailAddress="nobody"),
        }
        for label, mutate in cases.items():
            with self.subTest(case=label):
                users = synthetic_users()
                mutate(users)
                self.fake.calls.clear()
                code, _, _ = self.provision_users(self.fake, users, f"pw-{len(label)}.csv")
                self.assertEqual(code, 1)
                self.assertEqual(self.fake.calls, [])
        for doc in ([], {}, "x"):
            with self.subTest(doc=doc):
                self.assertEqual(self.provision_users(self.fake, doc)[0], 1)

    def test_legacy_shared_must_be_in_the_input(self):
        code, _, err = self.provision_users(self.fake, synthetic_users(), "pw.csv",
                                            "--legacy-shared", "ZZZTEST00000099AAA")
        self.assertEqual(code, 1)
        self.assertEqual(self.fake.calls, [])

    def test_missing_team_in_espocrm_points_to_provision_access(self):
        self.fake.records["Team"].clear()
        code, _, err = self.provision_users(self.fake, synthetic_users())
        self.assertEqual(code, 1)
        self.assertIn("run provision_access.py first", err)
        self.assertEqual(self.fake.writes(), [])


class TestReset(UsersBase):
    def setUp(self):
        super().setUp()
        code, _, err = self.provision_users(self.fake, synthetic_users(), "pw.csv",
                                            "--legacy-shared", LEGACY)
        self.assertEqual(code, 0, err)
        self.fake.calls.clear()

    def reset(self, sf_id, name="reset.csv"):
        return run(provision_users.main, ["dev", "--reset", sf_id, "--password-file",
                                          self.path(name)], self.fake)

    def test_reset_issues_one_new_password(self):
        staff = self.fake.by_user_name("staff.one")
        old = self.fake.passwords[staff["id"]]
        code, out, err = self.reset("ZZZTEST00000001AAA")
        self.assertEqual(code, 0, err)
        self.assertEqual([(c["method"], set(c["data"])) for c in self.fake.writes()],
                         [("PUT", {"password", "passwordConfirm"})])
        rows = self.read_csv("reset.csv")
        self.assertEqual(rows[1][:2], ["ZZZTEST00000001AAA", "staff.one"])
        self.assertEqual(self.fake.passwords[staff["id"]], rows[1][2])
        self.assertNotEqual(rows[1][2], old)
        self.assertEqual(self.mode("reset.csv"), 0o600)
        self.assertNotIn(rows[1][2], out + err)

    def test_reset_refuses_inactive_and_unknown_users(self):
        for sf_id in ("ZZZTEST00000003AAA", LEGACY, "ZZZTEST00000099AAA"):
            with self.subTest(sfId=sf_id):
                self.fake.calls.clear()
                code, _, _ = self.reset(sf_id, f"r-{sf_id}.csv")
                self.assertEqual(code, 1)
                self.assertEqual(self.fake.writes(), [])
                self.assertFalse(os.path.lexists(self.path(f"r-{sf_id}.csv")))

    def test_reset_refuses_an_existing_file(self):
        code, _, _ = run(provision_users.main, ["dev", "--reset", "ZZZTEST00000001AAA",
                                                "--password-file", self.path("pw.csv")], self.fake)
        self.assertEqual(code, 1)
        self.assertEqual(self.fake.calls, [])


class TestNeverLoggedInReport(UsersBase):
    def test_lists_active_regular_users_without_last_access(self):
        self.provision_users(self.fake, synthetic_users(), "pw.csv", "--legacy-shared", LEGACY)
        self.fake.by_user_name("intake.one")["lastAccess"] = "2026-11-09 10:00:00"
        code, out, err = run(provision_users.main, ["dev", "--report-never-logged-in"], self.fake)
        self.assertEqual(code, 0, err)
        self.assertEqual(out.split(), ["staff.one"])


class TestPasswordGeneration(unittest.TestCase):
    def test_length_and_character_classes(self):
        for _ in range(500):
            pw = provision_users.generate_password()
            self.assertGreaterEqual(len(pw), 20)
            self.assertEqual(len(pw), provision_users.PASSWORD_LENGTH)
            self.assertTrue(any(c in string.ascii_lowercase for c in pw))
            self.assertTrue(any(c in string.ascii_uppercase for c in pw))
            self.assertTrue(any(c in string.digits for c in pw))
            self.assertTrue(any(c in provision_users.PASSWORD_SYMBOLS for c in pw))
            self.assertTrue(set(pw) <= set(provision_users.PASSWORD_ALPHABET))

    def test_alphabet_is_large_and_csv_and_shell_safe(self):
        alphabet = provision_users.PASSWORD_ALPHABET
        self.assertGreaterEqual(len(set(alphabet)), 70)
        self.assertEqual(len(set(alphabet)), len(alphabet))
        self.assertFalse(set(alphabet) & set("\"',\\ $&`\t\n"))

    def test_unique_and_well_spread(self):
        sample = [provision_users.generate_password() for _ in range(2000)]
        self.assertEqual(len(set(sample)), len(sample))
        self.assertEqual(set("".join(sample)), set(provision_users.PASSWORD_ALPHABET))

    def test_shorter_than_20_is_refused(self):
        with self.assertRaises(ValueError):
            provision_users.generate_password(19)
        self.assertEqual(len(provision_users.generate_password(20)), 20)

    def test_uses_the_secrets_module(self):
        # every character is drawn by secrets.choice from the full alphabet; a draw
        # missing a class is discarded whole (rejection keeps the distribution uniform)
        draws = iter("a" * 24 + "aA1!" * 6)
        with mock.patch.object(provision_users.secrets, "choice",
                               side_effect=lambda seq: next(draws)) as choice:
            pw = provision_users.generate_password()
        self.assertEqual(pw, "aA1!" * 6)
        self.assertEqual(choice.call_count, 48)
        for call in choice.call_args_list:
            self.assertEqual(call.args[0], provision_users.PASSWORD_ALPHABET)
        with open(provision_users.__file__, encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotRegex(source, r"\bimport random\b|\bfrom random\b")

    def test_unusable_password_is_long_and_random(self):
        a, b = provision_users.unusable_password(), provision_users.unusable_password()
        self.assertGreaterEqual(len(a), 60)
        self.assertNotEqual(a, b)


class TestNoSecretInOutput(UsersBase):
    """The temporary passwords, the discarded passwords and the API key never
    reach stdout, stderr or logging; they do reach the CSV / key file and the
    API request bodies, which proves the check is not vacuous."""

    SENTINEL = "Pw-SENTINEL-{n:02d}-aZ9#xQ7!"
    DISCARDED = "Discarded-SENTINEL-{n:02d}"

    def setUp(self):
        super().setUp()
        self.log = io.StringIO()
        handler = logging.StreamHandler(self.log)
        root = logging.getLogger()
        old_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        self.addCleanup(root.removeHandler, handler)
        self.addCleanup(root.setLevel, old_level)
        self.issued = []
        self.discarded = []

        def fake_generate(length=provision_users.PASSWORD_LENGTH):
            self.issued.append(self.SENTINEL.format(n=len(self.issued)))
            return self.issued[-1]

        def fake_unusable():
            self.discarded.append(self.DISCARDED.format(n=len(self.discarded)))
            return self.discarded[-1]

        for name, fn in (("generate_password", fake_generate), ("unusable_password", fake_unusable)):
            patcher = mock.patch.object(provision_users, name, side_effect=fn)
            patcher.start()
            self.addCleanup(patcher.stop)

    def assertNoSecret(self, text):
        for secret in self.issued + self.discarded + [API_KEY_SENTINEL]:
            self.assertNotIn(secret, text)
        self.assertNotIn("SENTINEL", text)

    def bodies(self):
        return b"".join(c["body"] for c in self.fake.calls).decode()

    def test_provision_and_rerun(self):
        out1 = "".join(self.provision_users(self.fake, synthetic_users(), "pw.csv",
                                            "--legacy-shared", LEGACY)[1:])
        out2 = "".join(self.provision_users(self.fake, synthetic_users(), "pw2.csv")[1:])
        self.assertEqual(len(self.issued), 2)
        self.assertEqual(len(self.discarded), 2)
        self.assertNoSecret(out1 + out2 + self.log.getvalue())
        with open(self.path("pw.csv"), encoding="utf-8") as fh:
            recorded = fh.read()
        for secret in self.issued:
            self.assertIn(secret, recorded)
            self.assertIn(secret, self.bodies())
        for secret in self.discarded:
            self.assertNotIn(secret, recorded)
            self.assertIn(secret, self.bodies())

    def test_failure_paths(self):
        self.fake.fail = ("POST", "User", 2)
        out = "".join(self.provision_users(self.fake, synthetic_users())[1:])
        self.fake.fail = ("PUT", "User", 1)
        self.fake.calls.clear()
        out += "".join(run(provision_users.main, ["dev", "--reset", "ZZZTEST00000001AAA",
                                                  "--password-file", self.path("r.csv")],
                           self.fake)[1:])
        self.fake.drop_sf_id = True
        self.fake.fail = None
        users = synthetic_users()[1:2]
        users[0].update(sfId="ZZZTEST00000005AAA", userName="dropped.one")
        out += "".join(self.provision_users(self.fake, users, "pw3.csv")[1:])
        self.assertGreaterEqual(len(self.issued), 3)
        self.assertNoSecret(out + self.log.getvalue())

    def test_reset(self):
        self.provision_users(self.fake, synthetic_users(), "pw.csv", "--legacy-shared", LEGACY)
        out = "".join(run(provision_users.main, ["dev", "--reset", "ZZZTEST00000002AAA",
                                                 "--password-file", self.path("r.csv")],
                          self.fake)[1:])
        self.assertEqual(len(self.issued), 3)
        self.assertNoSecret(out + self.log.getvalue())

    def test_api_key(self):
        fake = FakeEspo()
        out = "".join(self.provision_access(fake, "fresh.env")[1:])
        self.assertNoSecret(out + self.log.getvalue())
        with open(self.path("fresh.env"), encoding="utf-8") as fh:
            self.assertIn(API_KEY_SENTINEL, fh.read())


if __name__ == "__main__":
    unittest.main()
