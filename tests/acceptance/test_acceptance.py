"""Live acceptance tests for CRM-001 (operator stage only; AC3-AC9).

Run against a freshly deployed and seeded crm-dev stack, from the repository root:

    export CRM_EXPECTED_BIND_IP=<CRM_BIND_IP from the runtime env file>   # AC9 (CRM-D019)
    export CRM_BASE_URL=http://$CRM_EXPECTED_BIND_IP:8180
    export CRM_ADMIN_USERNAME=...  CRM_ADMIN_PASSWORD=...   # never stored
    export CRM_SEED=1                 # the --seed used by seed_synthetic.py (default 1)
    export CRM_EXPORT_DIR=...         # output of scripts/export.sh dev (AC8)
    python3 -m unittest discover -s tests/acceptance -v

Expected values are recomputed from the deterministic seeder, so nothing about
the dataset is stored. The counts assume the stack holds only the seeded data.
AC7 tries to create each held-back near-duplicate; if one is wrongly accepted it
is deleted again and the test fails.

AC9's expected host IP comes from CRM_EXPECTED_BIND_IP, never from Git. It is a
different name from the env file's CRM_BIND_IP on purpose: Compose prefers the
process environment to the env file, so CRM_BIND_IP must not be exported.
"""

import collections
import csv
import json
import os
import socket
import subprocess
import sys
import unittest

ENV_EXPECTED_BIND_IP = "CRM_EXPECTED_BIND_IP"
APP_PORT = 8180

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import crm_api  # noqa: E402
import seed_synthetic as seeder  # noqa: E402

CLIENT = None
DATA = None
IDS = {}


def norm(text):
    return " ".join(str(text or "").split()).lower()


def setUpModule():
    global CLIENT, DATA
    username, password = crm_api.credentials_from_env()  # raises ConfigError if unset
    CLIENT = crm_api.EspoClient(os.environ.get(crm_api.ENV_BASE_URL, ""), username, password)
    DATA = seeder.build_dataset(int(os.environ.get("CRM_SEED", seeder.DEFAULT_SEED)))
    accounts = CLIENT.list_all("Account", {
        "select": "id,name,billingAddressPostalCode,parentId,parentName"})
    by_key = {(norm(a["name"]), norm(a["billingAddressPostalCode"])): a for a in accounts}
    for f in DATA["firms"]:
        rec = by_key.get((norm(f["name"]), norm(f["billingAddressPostalCode"])))
        if rec:
            IDS[f["key"]] = rec["id"]
    contacts = CLIENT.list_all("Contact", {"select": "id,emailAddress,accountId"})
    by_email = {norm(c["emailAddress"]): c for c in contacts}
    for c in DATA["contacts"]:
        rec = by_email.get(norm(c["emailAddress"]))
        if rec:
            IDS[c["key"]] = rec["id"]
    setUpModule.accounts = accounts
    setUpModule.contacts = contacts


def total(entity, conditions):
    page = CLIENT.list_page(entity, crm_api.where_params(conditions), max_size=1)
    return page["total"]


class TestAcceptance(unittest.TestCase):
    def test_ac3_firms_exist_branches_show_parent_big_parent_lists_34(self):
        accounts = {a["id"]: a for a in setUpModule.accounts}
        firms = {f["key"]: f for f in DATA["firms"]}
        missing = [f["name"] for f in DATA["firms"] if f["key"] not in IDS]
        self.assertEqual(missing, [], "seeded firms not found")
        for f in DATA["firms"]:
            rec = accounts[IDS[f["key"]]]
            if f["parentKey"]:
                self.assertEqual(rec["parentId"], IDS[f["parentKey"]], f["name"])
                self.assertEqual(rec["parentName"], firms[f["parentKey"]]["name"])
            else:
                self.assertFalse(rec.get("parentId"), f["name"])
        children = collections.Counter(f["parentKey"] for f in DATA["firms"] if f["parentKey"])
        big_key, count = children.most_common(1)[0]
        self.assertEqual(count, 34)
        panel = CLIENT.list_all(f"Account/{IDS[big_key]}/branches", {"select": "id"})
        self.assertEqual({r["id"] for r in panel},
                         {IDS[f["key"]] for f in DATA["firms"] if f["parentKey"] == big_key})

    def test_ac4_same_name_branches_are_distinct_records(self):
        names = collections.Counter(f["name"] for f in DATA["firms"])
        name = next(n for n, c in names.items() if c == 2)
        found = [a for a in setUpModule.accounts if a["name"] == name]
        self.assertEqual(len(found), 2, "both saved, neither merged nor renamed")
        self.assertNotEqual(found[0]["id"], found[1]["id"])
        self.assertNotEqual(norm(found[0]["billingAddressPostalCode"]),
                            norm(found[1]["billingAddressPostalCode"]))

    def test_ac5_contacts_on_their_firm_and_filter_counts(self):
        contacts = {c["id"]: c for c in setUpModule.contacts}
        for c in DATA["contacts"]:
            self.assertIn(c["key"], IDS, c["emailAddress"])
            self.assertEqual(contacts[IDS[c["key"]]]["accountId"], IDS[c["firmKey"]],
                             c["emailAddress"])
        for field in ("type", "industry", "learningPlatformAccess"):
            expected = collections.Counter(f[field] for f in DATA["firms"])
            for value, count in expected.items():
                with self.subTest(field=field, value=value):
                    self.assertEqual(total("Account", [("equals", field, value)]), count)

    def test_ac6_search_probes_in_top_5(self):
        for p in DATA["probes"]:
            with self.subTest(kind=p["kind"], entity=p["entityType"]):
                page = CLIENT.list_page(p["entityType"], {"textFilter": p["query"]},
                                        max_size=5)
                self.assertIn(IDS[p["expectKey"]], [r["id"] for r in page["list"]])

    def test_ac7_held_back_near_duplicates_raise_duplicate_warning(self):
        for h in DATA["heldBack"]:
            with self.subTest(entity=h["entityType"], original=h["originalKey"]):
                try:
                    created = CLIENT.create(h["entityType"], h["record"])
                except crm_api.ApiError as err:
                    self.assertEqual(err.status, 409, err.body)
                    continue
                CLIENT.delete(h["entityType"], created["id"])
                self.fail("near-duplicate was accepted without a duplicate warning")

    def test_ac8_records_after_restore_and_csv_export_complete(self):
        self.assertEqual(len(setUpModule.accounts), len(DATA["firms"]))
        self.assertEqual(len(setUpModule.contacts), len(DATA["contacts"]))
        export_dir = os.environ.get("CRM_EXPORT_DIR")
        self.assertTrue(export_dir, "set CRM_EXPORT_DIR to the scripts/export.sh output")
        with open(os.path.join(export_dir, "accounts.csv"), newline="", encoding="utf-8") as fh:
            accounts = list(csv.DictReader(fh))
        with open(os.path.join(export_dir, "contacts.csv"), newline="", encoding="utf-8") as fh:
            contacts = list(csv.DictReader(fh))
        self.assertEqual(len(accounts), len(DATA["firms"]))
        self.assertEqual(len(contacts), len(DATA["contacts"]))
        self.assertEqual({norm(c["emailAddress"]) for c in contacts},
                         {norm(c["emailAddress"]) for c in DATA["contacts"]})
        self.assertEqual({r["id"] for r in accounts}, {a["id"] for a in setUpModule.accounts})

    def expected_bind_ip(self):
        ip = os.environ.get(ENV_EXPECTED_BIND_IP, "")
        self.assertTrue(ip, f"set {ENV_EXPECTED_BIND_IP} to the env file's CRM_BIND_IP")
        self.assertNotIn(ip, ("127.0.0.1", "0.0.0.0", ""), "LAN bind expected")
        return ip

    def test_ac9_project_isolation_own_resources_only(self):
        expected_ip = self.expected_bind_ip()

        def docker_json(*args):
            res = subprocess.run(["docker", *args], capture_output=True, text=True, check=True)
            return json.loads(res.stdout)

        net = docker_json("network", "inspect", "crm-dev_crm-net")[0]
        self.assertEqual(net["Labels"].get("com.docker.compose.project"), "crm-dev",
                         "network created by the project, not external")
        names = sorted(c["Name"] for c in net["Containers"].values())
        self.assertTrue(names)
        for name in names:
            self.assertRegex(name, r"^crm-dev-crm-[a-z]+-\d+$")
        for c in docker_json("inspect", *names):
            service = c["Config"]["Labels"]["com.docker.compose.service"]
            bindings = c["HostConfig"].get("PortBindings") or {}
            if service == "crm-app":
                ips = {b.get("HostIp") for v in bindings.values() for b in v or []}
                self.assertEqual(ips, {expected_ip})  # was {"127.0.0.1"} before CRM-D019
                self.assertEqual(set(bindings), {"80/tcp"})
                self.assertEqual({b.get("HostPort") for b in bindings["80/tcp"]}, {str(APP_PORT)})
            else:
                self.assertEqual(bindings, {}, f"{service} publishes a port")
            self.assertEqual({m["Type"] for m in c["Mounts"]}, {"bind"},
                             f"{service} uses a volume")

    def test_ac9_app_not_published_on_loopback(self):
        """Live: nothing answers on the host's 127.0.0.1:8180 any more, while the
        LAN address does (CRM-D019). Run on the host itself."""
        expected_ip = self.expected_bind_ip()
        with self.assertRaises(OSError, msg="127.0.0.1:8180 still accepts connections"):
            socket.create_connection(("127.0.0.1", APP_PORT), timeout=5).close()
        socket.create_connection((expected_ip, APP_PORT), timeout=5).close()

    def test_ac9_unlisted_source_refused_loopback_allowed(self):
        """Live, inside the project's own containers only: crm-daemon's crm-net
        address is never in CRM_ALLOWED_SOURCES (check_access.py refuses any
        overlap), so Apache must answer it 403; the loopback healthcheck must
        still pass."""
        def docker(*args):
            return subprocess.run(["docker", *args], capture_output=True, text=True,
                                  check=True).stdout.strip()

        status = docker("exec", "crm-dev-crm-daemon-1", "curl", "-s", "-o", "/dev/null",
                        "-w", "%{http_code}", "http://crm-app/")
        self.assertEqual(status, "403", "a source outside CRM_ALLOWED_SOURCES was not refused")
        health = docker("inspect", "-f", "{{.State.Health.Status}}", "crm-dev-crm-app-1")
        self.assertEqual(health, "healthy", "loopback healthcheck refused")


if __name__ == "__main__":
    unittest.main()
