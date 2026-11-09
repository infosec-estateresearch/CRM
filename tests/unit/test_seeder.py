"""Seeder tests (WO CRM-001 items 3 and 5): determinism, dataset shape and the
API writes, through a fake transport with no network."""

import collections
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import crm_api  # noqa: E402
import seed_synthetic as seeder  # noqa: E402

BASE = "http://127.0.0.1:8180"
ENV = {"CRM_ADMIN_USERNAME": "unit-user", "CRM_ADMIN_PASSWORD": "unit-pass"}


class FakeTransport:
    """Records every request; answers POSTs with a generated id."""

    def __init__(self, fail_on=None, status=409):
        self.calls = []
        self.fail_on = fail_on
        self.status = status

    def request(self, method, url, headers, body):
        data = json.loads(body) if body else None
        self.calls.append({"method": method, "url": url, "headers": headers, "data": data})
        if self.fail_on is not None and len(self.calls) == self.fail_on:
            return self.status, b'{"reason":"Duplicate"}'
        return 200, json.dumps({"id": f"id{len(self.calls):04d}"}).encode()


def norm(text):
    return " ".join(str(text).split()).lower()


class TestDeterminism(unittest.TestCase):
    def test_same_seed_same_dataset(self):
        a = json.dumps(seeder.build_dataset(7), sort_keys=True)
        b = json.dumps(seeder.build_dataset(7), sort_keys=True)
        self.assertEqual(a, b)

    def test_default_seed_is_stable_across_calls(self):
        self.assertEqual(seeder.build_dataset(), seeder.build_dataset(seeder.DEFAULT_SEED))

    def test_different_seed_different_dataset(self):
        self.assertNotEqual(seeder.build_dataset(1)["firms"], seeder.build_dataset(2)["firms"])


class TestShape(unittest.TestCase):
    SEEDS = (1, 2, 3, 42, 2026)

    def check_shape(self, ds):
        firms = {f["key"]: f for f in ds["firms"]}
        children = collections.defaultdict(list)
        for f in ds["firms"]:
            if f["parentKey"]:
                children[f["parentKey"]].append(f)
        parents = [f for f in ds["firms"] if f["role"] == "parent"]
        branches = [f for f in ds["firms"] if f["role"] == "branch"]
        standalone = [f for f in ds["firms"] if f["role"] == "standalone"]

        # 1 parent with 34 branches; 24 parents with 1-8 branches; 40 stand-alone
        sizes = sorted(len(children[p["key"]]) for p in parents)
        self.assertEqual(len(parents), 25)
        self.assertEqual(sizes.count(34), 1)
        self.assertEqual(len([s for s in sizes if 1 <= s <= 8]), 24)
        self.assertEqual(len(standalone), 40)
        for f in standalone:
            self.assertIsNone(f["parentKey"])
            self.assertNotIn(f["key"], children)
        for b in branches:
            self.assertEqual(firms[b["parentKey"]]["role"], "parent")
            self.assertNotIn(b["key"], children, "branches have no branches")

        # exactly one pair of records sharing a name: two branches, distinct postcodes
        by_name = collections.Counter(norm(f["name"]) for f in ds["firms"])
        shared = [n for n, c in by_name.items() if c > 1]
        self.assertEqual(len(shared), 1)
        pair = [f for f in ds["firms"] if norm(f["name"]) == shared[0]]
        self.assertEqual(len(pair), 2)
        self.assertEqual({f["role"] for f in pair}, {"branch"})
        self.assertNotEqual(norm(pair[0]["billingAddressPostalCode"]),
                            norm(pair[1]["billingAddressPostalCode"]))

        # no seeded record trips the duplicate rules (name+postcode, email)
        dup_keys = [(norm(f["name"]), norm(f["billingAddressPostalCode"])) for f in ds["firms"]]
        self.assertEqual(len(dup_keys), len(set(dup_keys)))
        emails = [c["emailAddress"].lower() for c in ds["contacts"]]
        self.assertEqual(len(emails), len(set(emails)))

        # every option value used at least once
        self.assertEqual({f["type"] for f in ds["firms"]}, set(seeder.TIERS))
        self.assertEqual({f["industry"] for f in ds["firms"]}, set(seeder.INDUSTRIES))
        self.assertEqual({f["learningPlatformAccess"] for f in ds["firms"]},
                         set(seeder.LEARNING_PLATFORM_ACCESS))

        # about 600 contacts at @example.test, each on a seeded firm
        self.assertEqual(len(ds["contacts"]), 600)
        for c in ds["contacts"]:
            self.assertTrue(c["emailAddress"].endswith("@example.test"), c)
            self.assertIn(c["firmKey"], firms)
        self.assertEqual({c["firmKey"] for c in ds["contacts"]}, set(firms))

        # synthetic contact details only
        for f in ds["firms"]:
            self.assertTrue(f["billingAddressPostalCode"].startswith("ZZ"))
            self.assertTrue(f["phoneNumber"].startswith(seeder.FIRM_PHONE_PREFIX))
        for c in ds["contacts"]:
            self.assertTrue(c["phoneNumber"].startswith(seeder.CONTACT_PHONE_PREFIX))
        phones = [x["phoneNumber"] for x in ds["firms"] + ds["contacts"]]
        self.assertEqual(len(phones), len(set(phones)))

    def test_shape_for_several_seeds(self):
        for s in self.SEEDS:
            with self.subTest(seed=s):
                self.check_shape(seeder.build_dataset(s))

    def test_held_back_near_duplicates(self):
        for s in self.SEEDS:
            with self.subTest(seed=s):
                ds = seeder.build_dataset(s)
                held = ds["heldBack"]
                self.assertEqual(len(held), 5)
                index = {x["key"]: x for x in ds["firms"] + ds["contacts"]}
                for h in held:
                    orig = index[h["originalKey"]]
                    rec = h["record"]
                    if h["entityType"] == "Account":
                        self.assertNotEqual(rec["name"], orig["name"], "near, not exact")
                        self.assertEqual(norm(rec["name"]), norm(orig["name"]))
                        self.assertEqual(norm(rec["billingAddressPostalCode"]),
                                         norm(orig["billingAddressPostalCode"]))
                    else:
                        self.assertEqual(h["entityType"], "Contact")
                        self.assertNotEqual(rec["emailAddress"], orig["emailAddress"])
                        self.assertEqual(rec["emailAddress"].lower(), orig["emailAddress"])

    def test_probes(self):
        for s in self.SEEDS:
            with self.subTest(seed=s):
                ds = seeder.build_dataset(s)
                probes = ds["probes"]
                self.assertEqual(len(probes), 10)
                kinds = collections.Counter(p["kind"] for p in probes)
                self.assertEqual(kinds, {"partial firm name": 2, "postcode": 2, "phone": 2,
                                         "contact email": 2, "surname": 2})
                index = {x["key"]: x for x in ds["firms"] + ds["contacts"]}
                names = [f["name"] for f in ds["firms"]]
                for p in probes:
                    target = index[p["expectKey"]]
                    if p["kind"] == "partial firm name":
                        self.assertTrue(target["name"].startswith(p["query"]))
                        self.assertNotEqual(target["name"], p["query"])
                        self.assertLessEqual(seeder._prefix_matches(names, p["query"]), 5)
                    elif p["kind"] == "surname":
                        self.assertEqual(target["lastName"], p["query"])
                    elif p["kind"] == "postcode":
                        self.assertEqual(target["billingAddressPostalCode"], p["query"])
                    elif p["kind"] == "phone":
                        self.assertEqual(target["phoneNumber"], p["query"])
                    else:
                        self.assertEqual(target["emailAddress"], p["query"])


class TestApiWrites(unittest.TestCase):
    def setUp(self):
        self.ds = seeder.build_dataset(1)
        self.transport = FakeTransport()
        client = crm_api.EspoClient(BASE, "unit-user", "unit-pass", self.transport)
        self.ids = seeder.seed(client, self.ds)

    def test_one_post_per_record_and_nothing_else(self):
        calls = self.transport.calls
        self.assertEqual(len(calls), len(self.ds["firms"]) + len(self.ds["contacts"]))
        self.assertEqual({c["method"] for c in calls}, {"POST"})
        urls = collections.Counter(c["url"] for c in calls)
        self.assertEqual(urls, {f"{BASE}/api/v1/Account": len(self.ds["firms"]),
                                f"{BASE}/api/v1/Contact": len(self.ds["contacts"])})
        for c in calls:
            self.assertIn("Espo-Authorization", c["headers"])
            self.assertNotIn("X-Skip-Duplicate-Check", c["headers"])

    def test_parents_before_branches_and_links_resolved(self):
        created = set()
        for n, call in enumerate(self.transport.calls, start=1):
            data = call["data"]
            if call["url"].endswith("/Account"):
                if "parentId" in data:
                    self.assertIn(data["parentId"], created, "parent created first")
                created.add(f"id{n:04d}")  # the id FakeTransport returned for this call
        id_by_key = self.ids
        firms = {f["key"]: f for f in self.ds["firms"]}
        account_posts = [c["data"] for c in self.transport.calls if c["url"].endswith("/Account")]
        for f in self.ds["firms"]:
            post = next(p for p in account_posts if p["name"] == f["name"]
                        and p["billingAddressPostalCode"] == f["billingAddressPostalCode"])
            if f["parentKey"]:
                self.assertEqual(post["parentId"], id_by_key[f["parentKey"]])
            else:
                self.assertNotIn("parentId", post)
            self.assertEqual(post["learningPlatformAccess"], f["learningPlatformAccess"])
        contact_posts = [c["data"] for c in self.transport.calls if c["url"].endswith("/Contact")]
        for c, post in zip(self.ds["contacts"], contact_posts):
            self.assertEqual(post["emailAddress"], c["emailAddress"])
            self.assertEqual(post["accountId"], id_by_key[c["firmKey"]])
            self.assertIn(c["firmKey"], firms)

    def test_held_back_records_are_not_created(self):
        posted = {json.dumps(c["data"], sort_keys=True) for c in self.transport.calls}
        emails = {c["data"].get("emailAddress") for c in self.transport.calls}
        names = {c["data"].get("name") for c in self.transport.calls}
        for h in self.ds["heldBack"]:
            self.assertNotIn(json.dumps(h["record"], sort_keys=True), posted)
            if h["entityType"] == "Contact":
                self.assertNotIn(h["record"]["emailAddress"], emails)
            else:
                self.assertNotIn(h["record"]["name"], names)


class TestCli(unittest.TestCase):
    def run_main(self, argv, environ, transport=None):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = seeder.main(argv, transport=transport, environ=environ)
        return code, out.getvalue(), err.getvalue()

    def test_missing_credentials_fail_loudly_without_http(self):
        transport = FakeTransport()
        code, _, err = self.run_main(["--base-url", BASE], {}, transport)
        self.assertEqual(code, 2)
        self.assertIn("CRM_ADMIN_USERNAME", err)
        self.assertEqual(transport.calls, [])

    def test_missing_or_bad_base_url_fails(self):
        for url in ("", "file:///etc/passwd", "127.0.0.1:8180"):
            with self.subTest(url=url):
                transport = FakeTransport()
                code, _, _ = self.run_main(["--base-url", url], dict(ENV), transport)
                self.assertEqual(code, 2)
                self.assertEqual(transport.calls, [])

    def test_api_error_stops_with_status_1(self):
        transport = FakeTransport(fail_on=3)
        code, _, err = self.run_main(["--base-url", BASE], dict(ENV), transport)
        self.assertEqual(code, 1)
        self.assertIn("HTTP 409", err)
        self.assertEqual(len(transport.calls), 3)

    def test_dry_run_makes_no_calls(self):
        transport = FakeTransport()
        code, out, _ = self.run_main(["--dry-run", "--seed", "5"], {}, transport)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["contacts"], 600)
        self.assertEqual(transport.calls, [])

    def test_success_does_not_print_credentials(self):
        transport = FakeTransport()
        code, out, err = self.run_main(["--base-url", BASE], dict(ENV), transport)
        self.assertEqual(code, 0)
        self.assertNotIn("unit-pass", out + err)
        self.assertEqual(json.loads(out)["firms"], 219)


if __name__ == "__main__":
    unittest.main()
