"""Reconciliation (AC7, AC8): deletion classes, relations, owners, fill rates, duplicates."""

import gzip
import json
import os
import shutil
import unittest

from crm_migrate.errors import SnapshotError
from crm_migrate.log import CountsLog
from crm_migrate.manifest import MANIFEST, OutputDir, collect_files, dumps, read_manifest
from crm_migrate.reconcile import load_snapshot, reconcile, render_markdown, run_reconcile

from .fake_salesforce import SENTINEL, TempDirMixin, contract, make_fake


def between_runs(org):
    ids = [r for r in sorted(org.rows["Contact"]) if org.rows["Contact"][r].get("IsDeleted") is not True]
    org.tick()
    org.soft_delete("Contact", ids[10])
    org.hard_delete("Contact", ids[11], log=True)
    org.hard_delete("Contact", ids[12], log=False)
    org.merge("Contact", ids[14], ids[13])
    org.hard_delete("Note", sorted(org.rows["Note"])[0], log=True)     # Note is not replicateable


def rewrite_manifest(snap):
    man = read_manifest(snap)
    man["files"] = collect_files(snap)
    os.chmod(os.path.join(snap, MANIFEST), 0o600)
    with open(os.path.join(snap, MANIFEST), "w") as fh:
        fh.write(dumps(man))


class ReconcileTest(TempDirMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._holder = TempDirMixin()
        cls._holder.addCleanup = lambda *a: None
        cls.base_dir = cls._holder.tmp()
        fake = make_fake(contract())
        from .fake_salesforce import client_for
        from crm_migrate.extract import ExtractOptions, run_extract
        client = client_for(fake)
        cls.prev = os.path.join(cls.base_dir, "prev")
        run_extract(client, contract(), OutputDir(cls.prev), CountsLog(), ExtractOptions())
        cls.fake = fake
        between_runs(fake.org)
        cls.cur = os.path.join(cls.base_dir, "cur")
        run_extract(client, contract(), OutputDir(cls.cur), CountsLog(), ExtractOptions())
        cls.report = reconcile(load_snapshot(cls.cur), load_snapshot(cls.prev))
        cls.single = reconcile(load_snapshot(cls.prev))

    @classmethod
    def tearDownClass(cls):
        for d in cls._holder._tmpdirs:
            d.cleanup()

    def test_relations_planted_orphans(self):
        rel = self.single["relations"]
        self.assertEqual((rel["Account.ParentId"]["ok"], rel["Account.ParentId"]["orphans"],
                          rel["Account.ParentId"]["null"]), (12, 2, 10))
        self.assertEqual((rel["Contact.AccountId"]["orphans"], rel["Contact.AccountId"]["null"],
                          rel["Contact.AccountId"]["ok"]), (3, 2, 35))
        self.assertEqual(rel["Opportunity.AccountId"]["orphans"], 1)
        self.assertEqual(rel["OpportunityContactRole.ContactId"]["orphans"], 1)
        self.assertEqual(rel["OpportunityContactRole.OpportunityId"]["orphans"], 0)
        self.assertEqual((rel["Task.WhatId"]["orphans"], rel["Task.WhatId"]["not_extracted"]), (2, 1))
        self.assertEqual(rel["Task.WhoId"]["orphans"], 0)
        self.assertEqual(rel["Task.AccountId"]["orphans"], 0)
        self.assertEqual(rel["Event.WhatId"]["orphans"], 0)
        self.assertEqual(rel["EmailMessage.ActivityId"]["orphans"], 1)
        self.assertEqual(rel["EmailMessageRelation.EmailMessageId"]["orphans"], 0)
        emr = rel["EmailMessageRelation.RelationId"]
        self.assertEqual((emr["unmatched_address"], emr["orphans"], emr["null"]), (4, 1, 0))
        self.assertEqual(emr["ok"], 25)

    def test_owner_classes_only_for_owner_check_objects(self):
        objs = self.single["objects"]
        self.assertEqual(objs["Account"]["owners"],
                         {"active_user": 20, "inactive_user": 2, "queue_or_group": 0, "unresolved": 2, "orphans": 2})
        self.assertEqual(objs["Task"]["owners"],
                         {"active_user": 27, "inactive_user": 0, "queue_or_group": 3, "unresolved": 0, "orphans": 0})
        self.assertEqual(objs["Event"]["owners"]["active_user"], 12)
        for name in ("User", "Profile", "UserRole", "OpportunityContactRole", "EmailMessage",
                     "EmailMessageRelation"):
            self.assertNotIn("owners", objs[name], name)
        for name in ("Account", "Contact", "Opportunity", "Task", "Event", "Note"):
            self.assertIn("owners", objs[name], name)

    def test_fill_rates(self):
        fr = self.single["objects"]["Account"]["fill_rates"]
        self.assertEqual(fr["ShippingPostalCode"], {"filled": 18, "rows": 24, "rate": 0.75})
        self.assertEqual(fr["Website"], {"filled": 8, "rows": 24, "rate": 0.3333})
        self.assertEqual(fr["Id"]["filled"], 24)
        self.assertEqual(self.single["objects"]["Task"]["fill_rates"]["IsArchived"]["filled"], 30)  # False is a value

    def test_unavailable_field_fill_rate_is_unavailable_not_zero(self):
        fake = make_fake(contract(), org_kwargs={"unavailable": ("Opportunity.Post_code__c",)})
        snap, _ = self.extract(fake)
        rep = reconcile(load_snapshot(snap))
        self.assertEqual(rep["objects"]["Opportunity"]["fill_rates"]["Post_code__c"], "unavailable")

    def test_deletion_classes_single_snapshot(self):
        acc = self.single["objects"]["Account"]["deletion_classes"]
        self.assertEqual((acc["current"], acc["soft_deleted_available"], acc["merged"], acc["deletion_evidence"]),
                         (22, 1, 1, 2))
        self.assertEqual(acc["absent_since_previous_unexplained"], "no_previous_snapshot")
        note = self.single["objects"]["Note"]["deletion_classes"]
        self.assertEqual(note["deletion_evidence"], "unavailable")
        emr = self.single["objects"]["EmailMessageRelation"]["deletion_classes"]
        self.assertEqual((emr["soft_deleted_available"], emr["merged"], emr["deletion_evidence"]),
                         ("not_applicable", "not_applicable", "unavailable"))
        self.assertEqual(self.single["objects"]["Opportunity"]["deletion_classes"]["merged"], "unavailable")

    def test_deletion_classes_against_previous(self):
        c = self.report["objects"]["Contact"]["deletion_classes"]
        self.assertEqual(c["absent_since_previous_explained"], 3)
        self.assertEqual(c["absent_since_previous_explained_by"],
                         {"soft_deleted_available": 1, "merged": 1, "deletion_evidence": 1})
        self.assertEqual(c["absent_since_previous_unexplained"], 1)
        self.assertEqual((c["current"], c["soft_deleted_available"], c["merged"], c["deletion_evidence"]),
                         (36, 1, 1, 3))
        # Note is not replicateable: its logged permanent delete has no evidence and stays unexplained.
        n = self.report["objects"]["Note"]["deletion_classes"]
        self.assertEqual((n["absent_since_previous_explained"], n["absent_since_previous_unexplained"]), (0, 1))
        self.assertEqual(n["deletion_evidence"], "unavailable")
        self.assertEqual(self.report["objects"]["Account"]["deletion_classes"]["absent_since_previous_unexplained"], 0)

    def test_unexplained_absence_never_counted_as_deleted(self):
        c = self.report["objects"]["Contact"]["deletion_classes"]
        explained_total = sum(c["absent_since_previous_explained_by"].values())
        self.assertEqual(explained_total, c["absent_since_previous_explained"])
        self.assertNotIn("deleted", c)
        self.assertIn("sfAbsentUnverified", " ".join(self.report["notes"]))
        self.assertIn("permanently deleted", " ".join(self.report["notes"]))

    def test_counts_against_verification(self):
        acc = self.single["objects"]["Account"]
        self.assertEqual((acc["extracted"], acc["verification"]["queryAll"], acc["verification"]["query"]),
                         (24, 24, 22))
        self.assertTrue(acc["extracted_matches_queryAll"])
        self.assertEqual(acc["duplicate_ids"], 0)

    def test_duplicates_are_counted(self):
        snap = os.path.join(self.tmp(), "dup")
        shutil.copytree(self.prev, snap)
        path = os.path.join(snap, "objects", "Account.jsonl.gz")
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            lines = fh.readlines()
        os.chmod(path, 0o600)
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            fh.writelines(lines + lines[:2])
        rewrite_manifest(snap)
        rep = reconcile(load_snapshot(snap))
        self.assertEqual(rep["objects"]["Account"]["duplicate_ids"], 2)
        self.assertEqual(rep["objects"]["Account"]["extracted"], 24)

    def test_tampered_snapshot_refused(self):
        snap = os.path.join(self.tmp(), "bad")
        shutil.copytree(self.prev, snap)
        with open(os.path.join(snap, "objects", "User.jsonl.gz"), "ab") as fh:
            fh.write(b"\0")
        with self.assertRaises(SnapshotError):
            load_snapshot(snap)

    def test_gate_failed_snapshot_refused(self):
        fake = make_fake(contract(), org_kwargs={"describe_overrides": {"Note": {"queryable": False}}})
        from crm_migrate.errors import GateFailed
        with self.assertRaises(GateFailed):
            self.extract(fake)
        snap = [os.path.join(d.name, "snap") for d in self._tmpdirs][-1]
        with self.assertRaises(SnapshotError):
            load_snapshot(snap)

    def test_outputs_are_counts_only(self):
        out = os.path.join(self.tmp(), "rep")
        run_reconcile(self.cur, self.prev, OutputDir(out), CountsLog())
        ids = set()
        for org_rows in self.fake.org.rows.values():
            ids |= set(org_rows)
        for name in ("reconciliation.json", "reconciliation.md", "manifest.json"):
            with open(os.path.join(out, name), encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn(SENTINEL.lower(), text.lower(), name)
            self.assertNotIn("example.test", text, name)
            for rid in ids:
                self.assertNotIn(rid[:15], text, name)
        with open(os.path.join(out, "reconciliation.json")) as fh:
            self.assertEqual(json.load(fh)["objects"]["Contact"]["deletion_classes"]
                             ["absent_since_previous_unexplained"], 1)

    def test_markdown_render(self):
        md = render_markdown(self.report)
        self.assertIn("| Contact | RECONCILED | 38 |", md)
        self.assertIn("Relationship integrity", md)


if __name__ == "__main__":
    unittest.main()
