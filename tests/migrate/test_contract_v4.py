"""CRM-002-V: contract v4 ``visibleVia`` and verification of rows hidden by soft-deleted parents."""

import copy
import datetime as dt
import json
import os
import unittest

from crm_migrate.contract import CONTRACT_VERSION, ContractError
from crm_migrate.extract import assess_object
from crm_migrate.log import CountsLog
from crm_migrate.manifest import OutputDir
from crm_migrate.reconcile import load_snapshot, reconcile, render_markdown
from crm_migrate.selftest import run_selftest

from .fake_salesforce import (PLANTED, SCENARIO_EXPECTED, TempDirMixin, client_for, contract, contract_bytes,
                              contract_from_doc, make_fake)

EMR = "EmailMessageRelation"
VIA = [{"field": "EmailMessageId", "object": "EmailMessage"}, {"field": "RelationId", "object": "Contact"}]
L3_HIDDEN = {"EmailMessage.EmailMessageId": 4, "Contact.RelationId": 4}


def _obj(doc, name):
    return next(o for o in doc["objects"] if o["name"] == name)


class ContractV4LoadTest(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(contract_bytes())

    def mutate(self, fn):
        doc = copy.deepcopy(self.doc)
        fn(doc)
        return doc

    def test_version_and_visible_via(self):
        c = contract()
        self.assertEqual((CONTRACT_VERSION, c.version), (4, 4))
        self.assertEqual(_obj(self.doc, EMR)["visibleVia"], VIA)
        self.assertEqual(c.object(EMR).visible_via, (("EmailMessageId", "EmailMessage"), ("RelationId", "Contact")))
        for spec in c.objects:
            if spec.name != EMR:
                self.assertEqual(spec.visible_via, (), spec.name)
        names = c.object_names
        self.assertLess(names.index("EmailMessage"), names.index(EMR))
        self.assertLess(names.index("Contact"), names.index(EMR))

    def test_v3_is_refused(self):
        doc = self.mutate(lambda d: d.update(contractVersion=3))
        with self.assertRaises(ContractError) as ctx:
            contract_from_doc(doc)
        self.assertEqual(ctx.exception.code, "contract_version")

    def test_parent_after_child_is_refused(self):
        def move_email_message_after_relation(d):
            em = _obj(d, "EmailMessage")
            d["objects"].remove(em)
            d["objects"].append(em)
        with self.assertRaises(ContractError) as ctx:
            contract_from_doc(self.mutate(move_email_message_after_relation))
        self.assertEqual(ctx.exception.code, "visible_via")
        self.assertIn("not an earlier object", ctx.exception.detail)

    def test_parent_without_soft_delete_is_refused(self):
        doc = self.mutate(lambda d: _obj(d, EMR)["visibleVia"].append({"field": "RelationId", "object": "User"}))
        with self.assertRaises(ContractError) as ctx:
            contract_from_doc(doc)
        self.assertEqual(ctx.exception.code, "visible_via")
        self.assertIn("without softDelete", ctx.exception.detail)

    def test_other_invalid_visible_via_is_refused(self):
        cases = {
            "on_soft_delete_object": lambda d: _obj(d, "Note").update(
                visibleVia=[{"field": "ParentId", "object": "Account"}]),
            "unknown_field": lambda d: _obj(d, EMR)["visibleVia"].append(
                {"field": "NoSuchId", "object": "Contact"}),
            "not_a_reference": lambda d: _obj(d, EMR)["visibleVia"].append(
                {"field": "RelationType", "object": "Contact"}),
            "unknown_object": lambda d: _obj(d, EMR)["visibleVia"].append(
                {"field": "RelationId", "object": "Lead"}),
            "empty": lambda d: _obj(d, EMR).update(visibleVia=[]),
            "not_a_list": lambda d: _obj(d, EMR).update(visibleVia={"field": "RelationId"}),
            "extra_key": lambda d: _obj(d, EMR)["visibleVia"][0].update(note="x"),
            "duplicate": lambda d: _obj(d, EMR)["visibleVia"].append(dict(VIA[0])),
        }
        for name, fn in cases.items():
            with self.subTest(case=name), self.assertRaises(ContractError) as ctx:
                contract_from_doc(self.mutate(fn))
            self.assertEqual(ctx.exception.code, "visible_via", name)
        bad_name = self.mutate(lambda d: _obj(d, EMR)["visibleVia"].append({"field": "x;y", "object": "Contact"}))
        with self.assertRaises(ContractError) as ctx:
            contract_from_doc(bad_name)
        self.assertEqual(ctx.exception.code, "invalid_name")


class VisibleViaExtractTest(TempDirMixin, unittest.TestCase):
    def test_l3_shaped_fixture_reaches_reconciled_with_hidden_via_counts(self):
        fake = make_fake(contract())
        snap, man = self.extract(fake)
        self.assertEqual(man["status"], "RECONCILED")
        emr = man["objects"][EMR]
        self.assertEqual(emr["status"], "RECONCILED")
        self.assertEqual(emr["reasons"], [])
        self.assertEqual(emr["hidden_via"], L3_HIDDEN)
        self.assertEqual(emr["hidden_via"]["Contact.RelationId"], PLANTED["EmailMessageRelation.hidden_via."
                                                                         "Contact.RelationId"])
        self.assertEqual(emr["hidden_via_rows"], 8)
        self.assertEqual((emr["verification"]["count_query"], emr["verification"]["count_queryAll"]), (22, 30))
        self.assertTrue(emr["verification"]["count_query_matches_baseline"])
        self.assertEqual((emr["rows"], emr["current"]), (30, 22))
        for name in ("EmailMessage", "Contact"):
            self.assertEqual(man["objects"][name]["status"], "RECONCILED", name)
            self.assertEqual(man["objects"][name]["soft_deleted"], 1, name)
            self.assertNotIn("hidden_via", man["objects"][name])
        self.assertEqual(man["contract"]["effective"][EMR]["visibleVia"], VIA)
        self.assertEqual(man["contract"]["effective"]["Contact"]["visibleVia"], [])

    def test_one_unexplained_hidden_row_is_incomplete(self):
        fake = make_fake(contract(), "unexplained_hidden_relation")
        self.assertEqual(len(fake.hide_from_query), 1)
        _, man = self.extract(fake)
        self.assertEqual(man["status"], "INCOMPLETE")
        emr = man["objects"][EMR]
        self.assertEqual(emr["status"], "INCOMPLETE")
        self.assertEqual(emr["reasons"], ["query_count_mismatch"])
        self.assertEqual(emr["hidden_via"], L3_HIDDEN)          # the extra hidden row has no parent explanation
        self.assertEqual(emr["verification"]["count_query"], 21)
        self.assertEqual(SCENARIO_EXPECTED["unexplained_hidden_relation"], "INCOMPLETE")

    def test_parent_soft_deleted_during_run_uses_final_parent_baseline(self):
        fake = make_fake(contract(), "parent_soft_delete")
        _, man = self.extract(fake)
        self.assertEqual(man["status"], "RECONCILED")
        emr = man["objects"][EMR]
        self.assertEqual(emr["status"], "RECONCILED")
        self.assertEqual(emr["hidden_via"]["EmailMessage.EmailMessageId"], 5)   # 4 planted + 1 in-run child
        self.assertEqual(man["objects"]["EmailMessage"]["soft_deleted"], 2)

    def test_parent_soft_delete_the_run_never_saw_is_incomplete(self):
        """Query hides a child whose parent was soft-deleted after the parent was verified."""
        fake = make_fake(contract())
        rels = fake.org.rows[EMR]
        target = next(r["EmailMessageId"] for r in rels.values() if not fake.org.parent_hidden(EMR, r))
        from .fake_salesforce import Hook
        fired = []

        def late(o):
            if not fired:
                fired.append(1)
                o.rows["EmailMessage"][target]["IsDeleted"] = True   # no change-key bump: invisible to catch-up
        fake.hooks.append(Hook("page", late, obj="Note"))
        _, man = self.extract(fake)
        self.assertEqual(man["objects"][EMR]["status"], "INCOMPLETE")
        self.assertIn("query_count_mismatch", man["objects"][EMR]["reasons"])


class AssessObjectVisibleViaTest(unittest.TestCase):
    T = dt.datetime(2026, 11, 10, 9, tzinfo=dt.timezone.utc)

    def run_assess(self, count_query, parents):
        spec = contract().object(EMR)
        em_del, con_del = "02sS70000000000001AA", "003S70000000000001AA"
        base = {
            "0RsS70000000000001AA": (self.T, {"EmailMessageId": em_del, "RelationId": "003S70000000000009AA"}),
            "0RsS70000000000002AA": (self.T, {"EmailMessageId": "02sS70000000000009AA", "RelationId": con_del}),
            "0RsS70000000000003AA": (self.T, {"EmailMessageId": em_del, "RelationId": con_del}),
            "0RsS70000000000004AA": (self.T, {"EmailMessageId": "02sS70000000000009AA", "RelationId": None}),
        }
        verify = {rid: (self.T, None) for rid in base}
        return assess_object(spec, spec.field_names, base, verify, count_query, 4, {}, self.T,
                             dt.timedelta(minutes=15), 0, parents)

    def parents(self):
        return {"EmailMessage": frozenset({"02sS70000000000001AA"}), "Contact": frozenset({"003S70000000000001AA"})}

    def test_exact_count_reconciles_and_counts_per_entry(self):
        status, details, _ = self.run_assess(1, self.parents())
        self.assertEqual(status, "RECONCILED")
        self.assertEqual(details["hidden_via"], {"EmailMessage.EmailMessageId": 2, "Contact.RelationId": 2})
        self.assertEqual(details["hidden_via_rows"], 3)

    def test_count_off_by_one_either_way_is_incomplete(self):
        for count in (0, 2, 4):
            status, details, _ = self.run_assess(count, self.parents())
            self.assertEqual((status, details["reasons"]), ("INCOMPLETE", ["query_count_mismatch"]), count)

    def test_missing_parent_set_is_refused(self):
        from crm_migrate.errors import ProtocolError
        with self.assertRaises(ProtocolError):
            self.run_assess(1, {"EmailMessage": frozenset()})
        with self.assertRaises(ProtocolError):
            self.run_assess(1, None)


class ReconcileParentSoftDeletedTest(TempDirMixin, unittest.TestCase):
    def test_parent_soft_deleted_class_single_and_against_previous(self):
        fake = make_fake(contract())
        client = client_for(fake)
        from crm_migrate.extract import ExtractOptions, run_extract
        prev = os.path.join(self.tmp(), "prev")
        run_extract(client, contract(), OutputDir(prev), CountsLog(), ExtractOptions())
        fake.org.tick()
        visible = sorted(r for r, row in fake.org.rows["EmailMessage"].items()
                         if row.get("IsDeleted") is not True
                         and any(rel.get("EmailMessageId") == r for rel in fake.org.rows[EMR].values()))
        fake.org.soft_delete("EmailMessage", visible[0])
        cur = os.path.join(self.tmp(), "cur")
        man = run_extract(client, contract(), OutputDir(cur), CountsLog(), ExtractOptions())
        self.assertEqual(man["status"], "RECONCILED")
        single = reconcile(load_snapshot(prev))
        d = single["objects"][EMR]["deletion_classes"]
        self.assertEqual((d["current"], d["parent_soft_deleted"]), (22, 8))
        self.assertEqual(single["objects"][EMR]["verification"]["hidden_via"], L3_HIDDEN)
        self.assertEqual(single["objects"]["Contact"]["deletion_classes"]["parent_soft_deleted"], "not_applicable")
        rep = reconcile(load_snapshot(cur), load_snapshot(prev))
        d = rep["objects"][EMR]["deletion_classes"]
        newly = man["objects"][EMR]["hidden_via_rows"] - 8
        self.assertGreater(newly, 0)
        self.assertEqual(d["parent_soft_deleted"], 8 + newly)
        self.assertEqual(d["current"], 22 - newly)
        self.assertEqual(d["absent_since_previous_explained_by"]["parent_soft_deleted"], newly)
        self.assertEqual(d["absent_since_previous_unexplained"], 0)
        md = render_markdown(rep)
        self.assertIn("Parent soft-deleted", md)
        self.assertIn(f"| {EMR} | RECONCILED | 30 | {22 - newly} | 30 | 0 | {22 - newly} | not_applicable | "
                      f"not_applicable | {8 + newly} |", md)


class SelftestV4Test(TempDirMixin, unittest.TestCase):
    def test_full_selftest_reaches_reconciled_including_visible_via_scenarios(self):
        result = run_selftest(contract(), OutputDir(self.tmp() + "/selftest"), CountsLog(), quick=False)
        self.assertEqual(result["status"], "RECONCILED", result["checks"])
        for name in ("parent_soft_delete", "unexplained_hidden_relation"):
            self.assertEqual(result["checks"][f"scenario_{name}"], "PASS", name)


if __name__ == "__main__":
    unittest.main()
