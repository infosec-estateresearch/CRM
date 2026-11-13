"""Metadata gate (AC4): contract-check, and extract through it."""

import os
import unittest

from crm_migrate.errors import GateFailed
from crm_migrate.extract import ExtractOptions, run_extract
from crm_migrate.log import CountsLog
from crm_migrate.manifest import OutputDir
from crm_migrate.metadata import evaluate_gate, run_gate

from .fake_salesforce import (TempDirMixin, client_for, contract, contract_bytes, contract_from_doc, data_queries,
                              make_fake)


class GateTest(TempDirMixin, unittest.TestCase):
    def gate(self, **org_kwargs):
        fake = make_fake(contract(), org_kwargs=org_kwargs)
        return run_gate(client_for(fake), contract()), fake

    def assert_extract_refused(self, **org_kwargs):
        fake = make_fake(contract(), org_kwargs=org_kwargs)
        out = os.path.join(self.tmp(), "snap")
        with self.assertRaises(GateFailed):
            run_extract(client_for(fake), contract(), OutputDir(out), CountsLog(), ExtractOptions())
        self.assertEqual(data_queries(fake), [], "a data query was issued after a failed gate")
        self.assertFalse(os.path.exists(os.path.join(out, "objects")))
        with open(os.path.join(out, "manifest.json")) as fh:
            self.assertIn('"status": "INCOMPLETE"', fh.read())
        return fake

    def test_clean_org_passes_and_reads_describe_only(self):
        result, fake = self.gate()
        self.assertTrue(result.ok)
        self.assertEqual(result.report["objects_failed"], 0)
        self.assertEqual(data_queries(fake), [])
        self.assertTrue(all(p.endswith("/describe/") or p.endswith("/token") for _, p in fake.requests))

    def test_not_queryable(self):
        result, _ = self.gate(describe_overrides={"Note": {"queryable": False}})
        self.assertFalse(result.ok)
        self.assertFalse(result.report["objects"]["Note"]["ok"])
        self.assert_extract_refused(describe_overrides={"Note": {"queryable": False}})

    def test_not_retrieveable(self):
        result, _ = self.gate(describe_overrides={"Task": {"retrieveable": False}})
        self.assertFalse(result.ok)

    def test_required_field_missing(self):
        kw = {"field_overrides": {"Account.ParentId": None}}
        result, _ = self.gate(**kw)
        self.assertEqual(result.report["objects"]["Account"]["missing_required"], ["ParentId"])
        self.assert_extract_refused(**kw)

    def test_required_field_wrong_type(self):
        kw = {"field_overrides": {"Opportunity.Amount": {"type": "double"}}}
        result, _ = self.gate(**kw)
        self.assertEqual(result.report["objects"]["Opportunity"]["type_mismatch"], ["Amount"])
        self.assert_extract_refused(**kw)

    def test_reference_target_differs(self):
        kw = {"field_overrides": {"Contact.AccountId": {"referenceTo": ["Lead"]}}}
        result, _ = self.gate(**kw)
        self.assertEqual(result.report["objects"]["Contact"]["reference_mismatch"], ["AccountId"])
        self.assert_extract_refused(**kw)

    def test_exact_reference_with_extra_target_fails(self):
        result, _ = self.gate(field_overrides={"Account.ParentId": {"referenceTo": ["Account", "User"]}})
        self.assertEqual(result.report["objects"]["Account"]["reference_mismatch"], ["ParentId"])

    def test_superset_reference_missing_listed_target_fails(self):
        result, _ = self.gate(field_overrides={"Task.WhatId": {"referenceTo": ["Account", "Case"]}})
        self.assertEqual(result.report["objects"]["Task"]["reference_mismatch"], ["WhatId"])

    def test_any_write_flag_fails(self):
        for flag in ("createable", "updateable", "deletable"):
            with self.subTest(flag=flag):
                kw = {"describe_overrides": {"Account": {flag: True}}}
                result, _ = self.gate(**kw)
                self.assertFalse(result.ok)
                self.assertTrue(result.report["objects"]["Account"][flag])
                self.assert_extract_refused(**kw)

    def test_missing_write_flag_fails_safe(self):
        result, _ = self.gate(describe_overrides={"Account": {"deletable": None}})
        self.assertFalse(result.ok)

    def test_user_updateable_is_a_finding_not_a_waiver(self):
        result, _ = self.gate(describe_overrides={"User": {"updateable": True}})
        self.assertFalse(result.ok)
        self.assertEqual(len(result.report["findings"]), 1)
        self.assertIn("L1 finding", result.report["findings"][0])

    def test_architect_waiver_applies_only_to_its_flag(self):
        import json
        doc = json.loads(contract_bytes())
        doc["waivers"] = [{"object": "User", "flag": "updateable", "approvedBy": "Architect", "record": "Issue 9"}]
        waived = contract_from_doc(doc)
        fake = make_fake(waived, org_kwargs={"describe_overrides": {"User": {"updateable": True}}})
        result = run_gate(client_for(fake, waived), waived)
        self.assertTrue(result.ok)
        self.assertEqual(result.report["objects"]["User"]["waived"], ["updateable"])
        fake = make_fake(waived, org_kwargs={"describe_overrides": {"User": {"updateable": True,
                                                                              "createable": True}}})
        self.assertFalse(run_gate(client_for(fake, waived), waived).ok)

    def test_missing_optional_field_is_excluded_and_reported(self):
        result, _ = self.gate(unavailable=("Task.IsArchived", "EmailMessage.ThreadIdentifier"))
        self.assertTrue(result.ok)
        self.assertEqual(result.report["objects"]["Task"]["unavailable_optional"], ["IsArchived"])
        eff = {e.name: e for e in result.effective}
        self.assertNotIn("IsArchived", eff["Task"].fields)
        self.assertEqual(eff["EmailMessage"].unavailable, ("ThreadIdentifier",))

    def test_optional_field_with_wrong_type_fails(self):
        result, _ = self.gate(field_overrides={"Opportunity.Post_code__c": {"type": "int"}})
        self.assertFalse(result.ok)

    def test_describe_error_fails(self):
        fake = make_fake(contract(), error_paths=(r"/sobjects/Note/describe",))
        result = run_gate(client_for(fake), contract())
        self.assertFalse(result.ok)
        self.assertEqual(result.report["objects"]["Note"]["describe"], "failed")

    def test_pure_gate_with_no_describes_fails_everything(self):
        result = evaluate_gate(contract(), {})
        self.assertFalse(result.ok)
        self.assertEqual(result.report["objects_failed"], len(contract().objects))

    def test_describe_summary_stores_picklists_and_prefixes(self):
        result, _ = self.gate()
        self.assertEqual(result.describe_summary["Account"]["keyPrefix"], "001")
        self.assertTrue(result.describe_summary["Opportunity"]["fields"]["StageName"]["picklistValues"])
        self.assertNotIn("ShippingAddress", result.describe_summary["Account"]["fields"])


if __name__ == "__main__":
    unittest.main()
