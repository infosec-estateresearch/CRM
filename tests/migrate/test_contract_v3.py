"""CRM-002-U: source-field contract v3 (L1 corrections) and type reporting in the gate."""

import datetime as _dt
import io
import json
import logging
import unittest

from crm_migrate import waiver as wv
from crm_migrate.contract import CONTRACT_VERSION, ContractError
from crm_migrate.log import LOGGER_NAME, CountsLog
from crm_migrate.manifest import OutputDir
from crm_migrate.metadata import evaluate_gate, run_gate
from crm_migrate.selftest import run_selftest

from .fake_salesforce import (SCENARIO_EXPECTED, TempDirMixin, client_for, contract, contract_bytes,
                              contract_from_doc, make_fake)

TODAY = _dt.date(2026, 11, 10)
WAIVER = wv.parse_waiver(json.dumps({"authorisation": wv.ISSUE_COMMENT_PREFIX + "1234567",
                                     "identity": "legacy-eric", "expires": "2026-11-30"}).encode(), TODAY)
WRITE_CAPABLE = {"createable": True, "updateable": True, "deletable": True}


def _fld(doc, obj, name):
    o = next(o for o in doc["objects"] if o["name"] == obj)
    return next(f for f in o["fields"] if f["name"] == name)


def l1_describes():
    """Describes in the shape of the L1 result (2026-11-10): schema only, synthetic."""
    fake = make_fake(contract())
    describes = {}
    for spec in contract().objects:
        doc = fake.org.describe(spec.name)
        doc.update(WRITE_CAPABLE)                          # all 12 objects writable for the legacy identity
        fields = {f["name"]: f for f in doc["fields"]}
        if spec.name == "Account":
            fields["Interested_in_integration__c"].update(type="picklist")
        if spec.name == "EmailMessageRelation":
            fields["RelationAddress"].update(type="string")
        if spec.name == "Opportunity":
            # a self-lookup named Post_code__c exists; Key_Information__c does not
            doc["fields"].append({"name": "Post_code__c", "type": "reference", "referenceTo": ["Opportunity"],
                                  "relationshipName": "Post_code__r", "picklistValues": []})
        describes[spec.name] = doc
    return describes


def v2_typed_contract():
    """The v3 file with the v2 field types and fields restored (version left at 3 so it parses)."""
    doc = json.loads(contract_bytes())
    _fld(doc, "Account", "Interested_in_integration__c")["type"] = "boolean"
    _fld(doc, "EmailMessageRelation", "RelationAddress")["type"] = "email"
    opp = next(o for o in doc["objects"] if o["name"] == "Opportunity")
    at = [f["name"] for f in opp["fields"]].index("IsDeleted")
    opp["fields"][at:at] = [
        {"name": "Post_code__c", "type": "string", "purpose": "R7 postcode", "required": False},
        {"name": "Key_Information__c", "type": "textarea", "purpose": "R7 key information", "required": False},
    ]
    return doc


class ContractV3Test(unittest.TestCase):
    def test_version_and_l1_fields(self):
        c = contract()
        self.assertEqual(CONTRACT_VERSION, 3)
        self.assertEqual(c.version, 3)
        acc = c.object("Account").field("Interested_in_integration__c")
        self.assertEqual((acc.type, acc.required), ("picklist", True))
        rel = c.object("EmailMessageRelation").field("RelationAddress")
        self.assertEqual((rel.type, rel.required), ("string", True))
        opp = c.object("Opportunity")
        self.assertIsNone(opp.field("Post_code__c"))
        self.assertIsNone(opp.field("Key_Information__c"))

    def test_v2_shaped_contract_is_refused_with_contract_version(self):
        for doc in (v2_typed_contract(), json.loads(contract_bytes())):
            doc["contractVersion"] = 2
            with self.assertRaises(ContractError) as ctx:
                contract_from_doc(doc)
            self.assertEqual(ctx.exception.code, "contract_version")
        for bad in (None, "3", 3.5, 4, True):
            doc = json.loads(contract_bytes())
            doc["contractVersion"] = bad
            with self.subTest(version=bad), self.assertRaises(ContractError) as ctx:
                contract_from_doc(doc)
            self.assertEqual(ctx.exception.code, "contract_version")


class L1GateTest(unittest.TestCase):
    def test_l1_shaped_describe_passes_the_v3_gate(self):
        result = evaluate_gate(contract(), l1_describes(), WAIVER)
        self.assertTrue(result.ok, json.dumps(result.report["objects"], indent=1))
        self.assertEqual(result.report["objects_failed"], 0)
        self.assertEqual(result.report["contract_version"], 3)
        self.assertEqual(result.report["writable_objects"], 12)
        self.assertTrue(result.report["identity"].startswith("write-capable (waived: "))
        self.assertEqual(result.report["findings"],
                         ["User updateable: L1 finding for Architect decision, not waived"])
        for name, rep in result.report["objects"].items():
            self.assertEqual(sorted(rep["waived"]),
                             ["createable:identity", "deletable:identity", "updateable:identity"], name)
            self.assertEqual((rep["missing_required"], rep["type_mismatch"], rep["reference_mismatch"]),
                             ([], [], []), name)
        eff = {e.name: e for e in result.effective}
        self.assertNotIn("Post_code__c", eff["Opportunity"].fields)
        self.assertIn("Interested_in_integration__c", eff["Account"].fields)
        self.assertIn("RelationAddress", eff["EmailMessageRelation"].fields)

    def test_l1_describe_against_v2_types_fails_three_objects_with_described_types(self):
        result = evaluate_gate(contract_from_doc(v2_typed_contract()), l1_describes(), WAIVER)
        self.assertFalse(result.ok)
        objs = result.report["objects"]
        self.assertEqual(sorted(n for n, r in objs.items() if not r["ok"]),
                         ["Account", "EmailMessageRelation", "Opportunity"])
        self.assertEqual(objs["Account"]["type_mismatch"],
                         [{"field": "Interested_in_integration__c", "expected": "boolean", "described": "picklist"}])
        self.assertEqual(objs["EmailMessageRelation"]["type_mismatch"],
                         [{"field": "RelationAddress", "expected": "email", "described": "string"}])
        self.assertEqual(objs["Opportunity"]["type_mismatch"],
                         [{"field": "Post_code__c", "expected": "string", "described": "reference",
                           "referenceTo": ["Opportunity"]}])
        self.assertEqual(objs["Opportunity"]["unavailable_optional"], ["Key_Information__c"])


class MismatchReportTest(TempDirMixin, unittest.TestCase):
    def gate(self, overrides):
        fake = make_fake(contract(), org_kwargs={"field_overrides": overrides})
        return run_gate(client_for(fake), contract())

    def test_type_mismatch_records_described_type(self):
        rep = self.gate({"Account.Name": {"type": "textarea"}}).report["objects"]["Account"]
        self.assertEqual(rep["type_mismatch"], [{"field": "Name", "expected": "string", "described": "textarea"}])

    def test_type_mismatch_to_reference_records_targets(self):
        rep = self.gate({"Account.Name": {"type": "reference", "referenceTo": ["Opportunity", "User"]}}).report
        self.assertEqual(rep["objects"]["Account"]["type_mismatch"],
                         [{"field": "Name", "expected": "string", "described": "reference",
                           "referenceTo": ["Opportunity", "User"]}])

    def test_reference_mismatch_records_described_targets(self):
        rep = self.gate({"Account.ParentId": {"referenceTo": ["Account", "User"]}}).report["objects"]["Account"]
        self.assertEqual(rep["reference_mismatch"],
                         [{"field": "ParentId", "expected": "reference", "described": "reference",
                           "expectedReferenceTo": ["Account"], "referenceTo": ["Account", "User"]}])

    def test_non_identifier_type_values_are_unrecognised(self):
        for bad in ("pick list", "picklist\n", "1picklist", "_x", "a" * 81, "x<script>", "pïcklist", "", 7, None,
                    ["picklist"], {"t": "picklist"}, True):
            with self.subTest(described=repr(bad)[:40]):
                result = self.gate({"Account.Name": {"type": bad}})
                self.assertFalse(result.ok)
                self.assertEqual(result.report["objects"]["Account"]["type_mismatch"],
                                 [{"field": "Name", "expected": "string", "described": "unrecognised"}])
                self.assertNotIn("script", json.dumps(result.report))

    def test_identifier_length_boundary(self):
        ok80 = "a" * 80
        rep = self.gate({"Account.Name": {"type": ok80}}).report["objects"]["Account"]
        self.assertEqual(rep["type_mismatch"][0]["described"], ok80)

    def test_non_identifier_reference_targets_are_unrecognised(self):
        rep = self.gate({"Account.ParentId": {"referenceTo": ["Account", "Bad Name", 5, "x" * 81, "Lead"]}}).report
        self.assertEqual(rep["objects"]["Account"]["reference_mismatch"][0]["referenceTo"],
                         ["Account", "unrecognised", "unrecognised", "unrecognised", "Lead"])
        rep = self.gate({"Account.ParentId": {"referenceTo": "Account; DROP"}}).report
        entry = rep["objects"]["Account"]["reference_mismatch"][0]
        self.assertEqual(entry["referenceTo"], "unrecognised")
        self.assertNotIn("DROP", json.dumps(rep))

    def test_logs_keep_counts_only(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger(LOGGER_NAME + ".v3test")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        self.addCleanup(logger.removeHandler, handler)
        log = CountsLog(logger)
        log.allow_contract(contract())
        fake = make_fake(contract(), org_kwargs={"field_overrides": {
            "Account.Name": {"type": "textarea"},
            "Account.ParentId": {"referenceTo": ["Opportunity"]}}})
        run_gate(client_for(fake), contract(), log)
        text = stream.getvalue()
        self.assertIn("event=gate_object", text)
        line = next(ln for ln in text.splitlines() if "event=gate_object" in ln and "object=Account" in ln)
        self.assertIn("type_mismatch=1", line)
        self.assertIn("reference_mismatch=1", line)
        for leaked in ("textarea", "Opportunity", "expected", "described"):
            self.assertNotIn(leaked, line)


class SelftestV3Test(TempDirMixin, unittest.TestCase):
    def test_full_selftest_reaches_reconciled_with_every_scenario(self):
        result = run_selftest(contract(), OutputDir(self.tmp() + "/selftest"), CountsLog(), quick=False)
        self.assertEqual(result["status"], "RECONCILED", result["checks"])
        self.assertEqual({k for k, v in result["checks"].items() if v != "PASS"}, set())
        for name in SCENARIO_EXPECTED:
            self.assertEqual(result["checks"][f"scenario_{name}"], "PASS", name)


if __name__ == "__main__":
    unittest.main()
