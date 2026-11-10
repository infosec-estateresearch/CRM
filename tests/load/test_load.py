"""crm-load tests (CRM-006): in-process, synthetic, no network."""

import io
import json
import os
import shutil
import stat
import tempfile
import unittest

from tests.load import fixtures as fx
from tests.load.fixtures import FakeEspo, SENTINEL, write_snapshot

from crm_load import cli, snapshot as snap_mod  # noqa: E402  (path set by fixtures)
from crm_load.errors import GateError, LoadError, TransportError
from crm_load.mapping import EXCEPTION_CODES, Mapper, load_json
from crm_load.names import NameParser
from crm_load.transport import HttpsTransport
from crm_load.api import EspoClient

ROOT = fx.ROOT
ENTITY_DEFS = os.path.join(ROOT, "custom", "Espo", "Custom", "Resources", "metadata", "entityDefs")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir=os.environ.get("TMPDIR"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.snap = write_snapshot(os.path.join(self.tmp, "snap"))
        self.espo = FakeEspo()
        self._n = 0

    def run_load(self, *extra, snap=None, espo=None, fail_after=None, out=None, target="dev"):
        self._n += 1
        out = out or os.path.join(self.tmp, f"out{self._n}")
        err, std = io.StringIO(), io.StringIO()
        rc = cli.main(["load", snap or self.snap, "--target", target, "--out", out, *extra], transport=espo or self.espo,
                      stderr=err, stdout=std, sleep=lambda s: None, fail_after=fail_after)
        self.last_err, self.last_out, self.last_dir = err.getvalue(), std.getvalue(), out
        return rc

    def report(self, out=None):
        with open(os.path.join(out or self.last_dir, "load-report.json")) as fh:
            return json.load(fh)

    def exceptions(self, out=None):
        with open(os.path.join(out or self.last_dir, "exceptions.jsonl")) as fh:
            return [json.loads(line) for line in fh if line.strip()]


class TestGate(Base):
    def _refuse(self, root, code, *extra):
        with self.assertRaises(GateError) as cm:
            snap_mod.open_snapshot(root, *extra)
        self.assertEqual(cm.exception.code, code)
        rc = cli.main(["load", root, "--target", "dev", "--out", os.path.join(self.tmp, "never")] + (
            ["--accept-drift", extra[0]] if extra and extra[0] else []),
            transport=self.espo, stderr=io.StringIO(), stdout=io.StringIO())
        self.assertEqual(rc, 3)
        self.assertEqual(self.espo.requests, [])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "never")))

    def test_good_snapshot_passes(self):
        self.assertEqual(snap_mod.open_snapshot(self.snap).manifest["status"], "RECONCILED")

    def test_checksum_mismatch_refused(self):
        path = os.path.join(self.snap, "objects", "Account.jsonl.gz")
        with open(path, "ab") as fh:
            fh.write(b"x")
        self._refuse(self.snap, "checksum_mismatch")

    def test_unlisted_and_missing_file_refused(self):
        with open(os.path.join(self.snap, "objects", "Extra.jsonl.gz"), "wb") as fh:
            fh.write(b"")
        self._refuse(self.snap, "unlisted_file")
        os.remove(os.path.join(self.snap, "objects", "Extra.jsonl.gz"))
        os.remove(os.path.join(self.snap, "objects", "Note.jsonl.gz"))
        self._refuse(self.snap, "missing_file")

    def test_status_rules(self):
        for i, status in enumerate(("INCOMPLETE", "PASS", None)):
            root = write_snapshot(os.path.join(self.tmp, f"s{i}"), status=status)
            self._refuse(root, "status_not_loadable")
        drift = write_snapshot(os.path.join(self.tmp, "drift"), status="RECONCILED_WITH_DRIFT")
        self._refuse(drift, "drift_not_accepted")
        self._refuse(drift, "accept_drift_invalid", "https://example.test/issues/9#issuecomment-1")
        url = "https://github.com/infosec-estateresearch/CRM/issues/9#issuecomment-123"
        self.assertEqual(snap_mod.open_snapshot(drift, url).manifest["status"], "RECONCILED_WITH_DRIFT")
        self._refuse(self.snap, "accept_drift_not_applicable", url)

    def test_contract_version_exactly_int_4(self):
        self.assertEqual(snap_mod.open_snapshot(self.snap).manifest["contract"]["version"], 4)
        for i, v in enumerate((2, 3, 5, True, 4.0, "4", None)):
            root = write_snapshot(os.path.join(self.tmp, f"v{i}"), version=v)
            self._refuse(root, "contract_version_unknown")

    def test_mode_must_be_extract_or_selftest(self):
        for i, mode in enumerate(("reconcile", "count", "", None, "Selftest")):
            root = write_snapshot(os.path.join(self.tmp, f"m{i}"), extra={"mode": mode})
            self._refuse(root, "not_a_snapshot")
        real = write_snapshot(os.path.join(self.tmp, "real"), synthetic=False)
        self.assertFalse(snap_mod.open_snapshot(real).synthetic)
        self.assertTrue(snap_mod.open_snapshot(self.snap).synthetic)
        # Only the mode marks a snapshot synthetic; an invented key does not.
        fake = write_snapshot(os.path.join(self.tmp, "fake"), synthetic=False, extra={"synthetic": True})
        self.assertFalse(snap_mod.open_snapshot(fake).synthetic)

    def test_snapshot_not_modified(self):
        before = {p: os.stat(os.path.join(dp, p)).st_mtime_ns for dp, _, fs in os.walk(self.snap) for p in fs}
        self.assertEqual(self.run_load(), 0)
        after = {p: os.stat(os.path.join(dp, p)).st_mtime_ns for dp, _, fs in os.walk(self.snap) for p in fs}
        self.assertEqual(before, after)

    def test_target_dev_requires_selftest_and_beta_refuses_it(self):
        real = write_snapshot(os.path.join(self.tmp, "real"), synthetic=False)
        self.assertEqual(self.run_load(snap=real, target="dev"), 2)
        self.assertIn("code=target_dev_requires_synthetic", self.last_err)
        self.assertEqual(self.run_load(target="beta"), 2)
        self.assertIn("code=target_beta_refuses_synthetic", self.last_err)
        self.assertEqual(self.espo.requests, [])
        self.assertFalse(os.path.exists(self.last_dir))
        self.assertEqual(self.run_load(snap=real, target="beta"), 0)
        self.assertEqual(self.run_load(target="qa"), 2)
        self.assertIn("code=usage", self.last_err)


class TestLayout(Base):
    """CRM-002-W layout rule: exactly one of the two layouts, anything else refused."""

    def test_legacy_layout_loads_like_the_flat_one(self):
        legacy = write_snapshot(os.path.join(self.tmp, "legacy"), layout="legacy")
        s = snap_mod.open_snapshot(legacy)
        self.assertEqual(s.root, os.path.join(legacy, "run"))
        self.assertEqual(snap_mod.locate(self.snap), self.snap)
        self.assertEqual(self.run_load(snap=legacy), 0, self.last_err)
        rep_legacy = self.report()
        self.assertEqual(self.run_load(snap=self.snap, espo=FakeEspo()), 0)
        strip = lambda r: {k: v for k, v in r.items() if k != "snapshotManifestSha"}  # noqa: E731
        self.assertEqual(strip(rep_legacy), strip(self.report()))
        rc = cli.main(["verify", legacy], stdout=io.StringIO(), stderr=io.StringIO())
        self.assertEqual(rc, 0)

    def test_waiver_is_never_read(self):
        legacy = write_snapshot(os.path.join(self.tmp, "legacy"), layout="legacy")
        waiver = os.path.join(legacy, "input", "waiver.json")
        os.chmod(waiver, 0o000)                  # unreadable: any open would fail
        try:
            self.assertEqual(self.run_load(snap=legacy), 0, self.last_err)
        finally:
            os.chmod(waiver, 0o600)

    def _refuse_layout(self, root, code):
        with self.assertRaises(GateError) as cm:
            snap_mod.open_snapshot(root)
        self.assertEqual(cm.exception.code, code)
        n = len(self.espo.requests)
        self.assertEqual(self.run_load(snap=root), 3)
        self.assertIn(f"code={code}", self.last_err)
        self.assertEqual(len(self.espo.requests), n)
        self.assertFalse(os.path.exists(self.last_dir))

    def test_refusals(self):
        def legacy(name):
            return write_snapshot(os.path.join(self.tmp, name), layout="legacy")

        both = legacy("both")                                    # manifest at <id>/ and in run/
        shutil.copy(os.path.join(both, "run", "manifest.json"), os.path.join(both, "manifest.json"))
        self._refuse_layout(both, "snapshot_layout_ambiguous")
        flat_run = write_snapshot(os.path.join(self.tmp, "flatrun"))  # flat plus a run/ directory
        os.mkdir(os.path.join(flat_run, "run"))
        self._refuse_layout(flat_run, "snapshot_layout_ambiguous")
        flat_input = write_snapshot(os.path.join(self.tmp, "flatinput"))
        os.mkdir(os.path.join(flat_input, "input"))
        self._refuse_layout(flat_input, "snapshot_layout_ambiguous")
        extra = legacy("extra")                                  # a third top-level entry
        open(os.path.join(extra, "notes.txt"), "w").close()
        self._refuse_layout(extra, "snapshot_layout_unknown")
        no_input = legacy("noinput")
        shutil.rmtree(os.path.join(no_input, "input"))
        self._refuse_layout(no_input, "snapshot_layout_unknown")
        no_manifest = legacy("nomanifest")
        os.remove(os.path.join(no_manifest, "run", "manifest.json"))
        self._refuse_layout(no_manifest, "snapshot_layout_unknown")
        input_file = legacy("inputfile")                         # input must be a directory
        shutil.rmtree(os.path.join(input_file, "input"))
        open(os.path.join(input_file, "input"), "w").close()
        self._refuse_layout(input_file, "snapshot_layout_unknown")
        linked = legacy("linked")                                # run/ as a symlink
        os.rename(os.path.join(linked, "run"), os.path.join(self.tmp, "realrun"))
        os.symlink(os.path.join(self.tmp, "realrun"), os.path.join(linked, "run"))
        self._refuse_layout(linked, "snapshot_layout_unknown")
        empty = os.path.join(self.tmp, "empty")
        os.mkdir(empty)
        self._refuse_layout(empty, "snapshot_layout_unknown")
        nested = legacy("nested")                                # the run/ dir itself is not an <id>
        self._refuse_layout(os.path.join(nested, "run", "objects"), "snapshot_layout_unknown")

    def test_legacy_run_is_checksummed(self):
        legacy = write_snapshot(os.path.join(self.tmp, "legacy"), layout="legacy")
        open(os.path.join(legacy, "run", "objects", "planted.jsonl.gz"), "w").close()
        self._refuse_layout(legacy, "unlisted_file")


class TestReconciliation(Base):
    DOC = {"objects": {"Account": {"deletion_classes": {"absent_since_previous_unexplained": 3}}}}

    def rec(self, name="x-reconcile", snap=None, **kw):
        kw.setdefault("snapshot", fx.snapshot_ref(snap or self.snap))
        return fx.write_reconcile_run(os.path.join(self.tmp, name), self.DOC, **kw)

    def assertRefusedRec(self, path, code, snap=None):
        n = len(self.espo.requests)
        self.assertEqual(self.run_load("--reconciliation", path, snap=snap), 3, self.last_err)
        self.assertIn(f"code={code}", self.last_err)
        self.assertEqual(len(self.espo.requests), n)
        self.assertFalse(os.path.exists(self.last_dir))

    def test_real_reconcile_layout(self):
        rec = self.rec()
        self.assertEqual(sorted(os.listdir(rec)), ["report"])
        self.assertEqual(sorted(os.listdir(os.path.join(rec, "report"))),
                         ["manifest.json", "reconciliation.json", "reconciliation.md"])
        with open(os.path.join(rec, "report", "manifest.json")) as fh:
            manifest = json.load(fh)
        self.assertEqual(sorted(manifest["files"]), ["reconciliation.json", "reconciliation.md"])
        self.assertEqual(sorted(manifest), ["files", "mode", "previous", "snapshot_status", "tool"])
        self.assertEqual(sorted(fx.snapshot_ref(self.snap)),
                         ["contract_sha256", "contract_version", "overlap_seconds", "passes", "quiet", "status",
                          "t_start"])
        self.assertEqual(self.run_load("--reconciliation", rec), 0, self.last_err)
        rep = self.report()
        self.assertTrue(rep["reconciliation"])
        self.assertEqual(rep["objects"]["Account"]["skipped"]["absent_unexplained"], 3)
        self.assertEqual(rep["objects"]["Contact"]["skipped"]["absent_unexplained"], 0)

    def test_legacy_snapshot_binds_to_run_manifest(self):
        legacy = write_snapshot(os.path.join(self.tmp, "legacy"), layout="legacy")
        rec = self.rec("legacy-reconcile", snap=legacy)
        self.assertEqual(self.run_load("--reconciliation", rec, snap=legacy), 0, self.last_err)
        self.assertEqual(self.report()["objects"]["Account"]["skipped"]["absent_unexplained"], 3)

    def test_optional_and_unknown_without_it(self):
        self.assertEqual(self.run_load(), 0)
        rep = self.report()
        self.assertFalse(rep["reconciliation"])
        for obj in ("Account", "Contact", "Opportunity"):
            self.assertEqual(rep["objects"][obj]["skipped"]["absent_unexplained"], "unknown", obj)

    def test_a_report_inside_the_snapshot_is_not_used(self):
        snap = write_snapshot(os.path.join(self.tmp, "s2"))
        os.makedirs(os.path.join(snap, "report"))
        with open(os.path.join(snap, "report", "reconciliation.json"), "w") as fh:
            json.dump(self.DOC, fh)
        self.assertEqual(self.run_load(snap=snap), 3)             # an unlisted file: refused
        self.assertIn("code=unlisted_file", self.last_err)

    def test_snapshot_binding(self):
        ref = fx.snapshot_ref(self.snap)
        cases = {
            "t_start": "2026-10-31T23:59:59Z",
            "status": "RECONCILED_WITH_DRIFT",
            "contract_sha256": "1" * 64,
            "contract_version": 3,
        }
        for i, (key, value) in enumerate(cases.items()):
            with self.subTest(key=key):
                self.assertRefusedRec(self.rec(f"m{i}-reconcile", snapshot=dict(ref, **{key: value})),
                                      "reconciliation_snapshot_mismatch")
        for i, key in enumerate(("t_start", "status", "contract_sha256", "contract_version")):
            with self.subTest(missing=key):
                bad = {k: v for k, v in ref.items() if k != key}
                self.assertRefusedRec(self.rec(f"d{i}-reconcile", snapshot=bad), "reconciliation_snapshot_mismatch")
        with self.subTest(case="version as string"):
            self.assertRefusedRec(self.rec("s-reconcile", snapshot=dict(ref, contract_version="4")),
                                  "reconciliation_snapshot_mismatch")
        with self.subTest(case="no snapshot object"):
            self.assertRefusedRec(fx.write_reconcile_run(os.path.join(self.tmp, "n-reconcile"), self.DOC),
                                  "reconciliation_snapshot_mismatch")
        with self.subTest(case="another snapshot"):
            other = write_snapshot(os.path.join(self.tmp, "other"), extra={"t_start": "2026-11-02T00:00:00Z"})
            self.assertRefusedRec(self.rec("o-reconcile", snap=other), "reconciliation_snapshot_mismatch")

    def test_binding_is_strict(self):
        def check(ref, contract):
            manifest = {"t_start": "2026-11-01T00:00:00Z", "status": "RECONCILED", "contract": contract}
            snap_mod.bind_reconciliation({"snapshot": dict(ref, t_start="2026-11-01T00:00:00Z",
                                                           status="RECONCILED")}, manifest)

        check({"contract_sha256": "", "contract_version": 1}, {"sha256": "", "version": 1})
        for ref, contract in (
                ({"contract_version": 1}, {"version": 1}),                            # sha absent on both sides
                ({"contract_sha256": None, "contract_version": 1}, {"sha256": None, "version": 1}),
                ({"contract_sha256": "", "contract_version": True}, {"sha256": "", "version": 1})):  # bool is not int
            with self.subTest(ref=ref):
                with self.assertRaises(GateError) as cm:
                    check(ref, contract)
                self.assertEqual(cm.exception.code, "reconciliation_snapshot_mismatch")

    def test_layout_refusals(self):
        old = self.rec("old-reconcile", layout="snapshot-style")    # the round-2 layout: <id>/manifest.json
        self.assertRefusedRec(old, "reconciliation_layout_unknown")
        self.assertRefusedRec(self.rec("no-suffix"), "reconciliation_layout_unknown")
        extra = self.rec("extra-reconcile")
        os.mkdir(os.path.join(extra, "other"))
        self.assertRefusedRec(extra, "reconciliation_layout_unknown")
        linked = os.path.join(self.tmp, "linked-reconcile")
        os.mkdir(linked)
        os.symlink(os.path.join(self.rec("target-reconcile"), "report"), os.path.join(linked, "report"))
        self.assertRefusedRec(linked, "reconciliation_layout_unknown")
        no_manifest = self.rec("nom-reconcile")
        os.remove(os.path.join(no_manifest, "report", "manifest.json"))
        self.assertRefusedRec(no_manifest, "reconciliation_layout_unknown")
        self.assertRefusedRec(self.snap, "reconciliation_layout_unknown")

    def test_refusals(self):
        bad_sum = self.rec("a-reconcile")
        with open(os.path.join(bad_sum, "report", "reconciliation.json"), "a") as fh:
            fh.write(" ")
        planted = self.rec("p-reconcile")
        open(os.path.join(planted, "report", "planted.json"), "w").close()
        nested = self.rec("q-reconcile")              # keys must be relative to report/, not <id>/
        with open(os.path.join(nested, "report", "manifest.json")) as fh:
            m = json.load(fh)
        m["files"] = {"report/" + k: v for k, v in m["files"].items()}
        with open(os.path.join(nested, "report", "manifest.json"), "w") as fh:
            json.dump(m, fh)
        cases = [
            (bad_sum, "reconciliation_checksum_mismatch"),
            (planted, "reconciliation_unlisted_file"),
            (nested, "reconciliation_unlisted_file"),
            (self.rec("b-reconcile", mode="extract"), "reconciliation_not_a_reconcile_run"),
            (self.rec("c-reconcile", listed=False), "reconciliation_report_missing"),
            (os.path.join(self.tmp, "missing-reconcile"), "reconciliation_snapshot_missing"),
        ]
        for path, code in cases:
            with self.subTest(code=code):
                self.assertRefusedRec(path, code)


class TestMapping(Base):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.run_load(), 0)
        self.rep = self.report()
        self.exc = self.exceptions()
        self.acc = self.espo.by_sf("Account")
        self.opp = self.espo.by_sf("Opportunity")
        self.users = self.espo.by_sf("User")

    def test_exact_counts_per_object(self):
        o = self.rep["objects"]
        self.assertEqual(o["Account"]["targets"]["Account"]["created"], 5)
        self.assertEqual(o["Account"]["skipped"]["soft_deleted"], 1)
        self.assertEqual(o["User"]["skipped"]["user_not_human"], 1)
        self.assertEqual(o["Contact"]["targets"]["Contact"]["created"], 3)
        self.assertEqual(o["Opportunity"]["targets"]["Opportunity"]["created"], 6)
        self.assertEqual(o["Opportunity"]["targets"]["ServiceType"]["created"], 2)
        self.assertEqual(o["OpportunityContactRole"]["targets"]["Opportunity"]["updated"], 2)
        self.assertEqual(o["OpportunityContactRole"]["targets"]["Opportunity"]["failed"], 0)
        self.assertEqual(o["Task"]["targets"], {"Task": {"created": 2, "updated": 0, "unchanged": 0, "failed": 0},
                                                "Call": {"created": 2, "updated": 0, "unchanged": 0, "failed": 0}})
        self.assertEqual(o["Task"]["skipped"]["represented_by_email_message"], 2)
        self.assertEqual(o["Event"]["targets"]["Meeting"]["created"], 2)
        self.assertEqual(o["EmailMessage"]["targets"]["Email"]["created"], 2)
        self.assertEqual(o["EmailMessage"]["skipped"]["soft_deleted"], 1)
        self.assertEqual(o["EmailMessageRelation"]["skipped"]["parent_soft_deleted"], 2)
        self.assertEqual(o["Note"]["skipped"]["out_of_scope"], 1)
        self.assertEqual(o["Note"]["targets"], {})
        self.assertEqual(self.rep["deletes"], 0)

    def test_relationship_totals_match(self):
        rel = self.rep["relationships"]
        for name, r in rel.items():
            self.assertEqual(r["snapshot"], r["espocrm"], name)
        self.assertEqual(rel["account_parents"]["snapshot"], 2)
        self.assertEqual(rel["enquiry_contacts"]["snapshot"], 3)

    def test_account_fields_and_address_swap(self):
        a = self.acc[fx.A[0]]
        self.assertTrue(a["billingAddressStreet"].startswith("1 Ship St"))   # SF Shipping -> Espo billing (R4)
        self.assertTrue(a["shippingAddressStreet"].startswith("2 Bill St"))
        self.assertEqual(a["learningPlatformAccess"], "TLP")
        self.assertEqual(a["type"], "Tier 1")
        self.assertEqual(a["sfCreatedAt"], "2020-01-02 03:04:05")
        self.assertEqual(a["assignedUserId"], self.users[fx.U1]["id"])
        self.assertNotIn("type", self.acc[fx.A[1]])           # unmapped enum left empty
        self.assertIn({"object": "Account", "sfId": fx.A[1], "reason": "enum_unmapped"}, self.exc)

    def test_second_pass_parents(self):
        self.assertEqual(self.acc[fx.A[1]]["parentId"], self.acc[fx.A[0]]["id"])
        self.assertEqual(self.acc[fx.A[2]]["parentId"], self.acc[fx.A[1]]["id"])
        self.assertNotIn("parentId", self.acc[fx.A[3]])      # parent soft-deleted: never invented
        self.assertIn({"object": "Account", "sfId": fx.A[3], "reason": "parent_unresolved"}, self.exc)
        # pass 1 creates carry no parent; parents arrive by PUT after every Account exists
        posts = [b for m, e, b in self.espo.writes if m == "POST" and e == "Account"]
        self.assertTrue(all("parentId" not in b for b in posts))

    def test_soft_deleted_never_created(self):
        for entity, sf in (("Account", fx.A[4]), ("Contact", fx.C[3]), ("Opportunity", fx.O[6]),
                           ("Task", fx.T[4])):
            self.assertNotIn(sf, self.espo.by_sf(entity))

    def test_stage_stale_loss(self):
        o = self.opp
        self.assertEqual((o[fx.O[0]]["stage"], o[fx.O[0]]["sfStageName"]), ("Instructed", "Closed Won"))
        self.assertIs(o[fx.O[0]]["legacyStale"], False)
        self.assertEqual(o[fx.O[1]]["stage"], "Enquiry")
        self.assertIs(o[fx.O[1]]["legacyStale"], True)          # Enquiry, close date before T_start
        self.assertEqual(o[fx.O[2]]["stage"], "Quoted")
        self.assertIs(o[fx.O[2]]["legacyStale"], False)         # close date in the future
        self.assertEqual((o[fx.O[3]]["stage"], o[fx.O[3]]["lossReason"]), ("Lost", "Price"))
        self.assertIs(o[fx.O[3]]["lossReasonLegacyMissing"], False)
        self.assertNotIn("lossReason", o[fx.O[4]])
        self.assertIs(o[fx.O[4]]["lossReasonLegacyMissing"], True)
        self.assertNotIn("stage", o[fx.O[5]])
        self.assertIn({"object": "Opportunity", "sfId": fx.O[5], "reason": "stage_unmapped"}, self.exc)
        for rec in o.values():
            self.assertNotIn("postcode", rec)
            self.assertNotIn("keyInformation", rec)
            self.assertNotIn("introducedById", rec)             # D7 table is empty
            self.assertNotIn("channel", rec)

    def test_opportunity_links(self):
        o = self.opp[fx.O[0]]
        st = self.espo.by_sf("ServiceType", "sfValue")
        self.assertEqual(o["serviceTypeId"], st["Service X"]["id"])
        self.assertEqual(st["Service X"]["name"], "Service X")
        self.assertEqual(o["accountId"], self.acc[fx.A[0]]["id"])
        con = self.espo.by_sf("Contact")
        self.assertEqual(sorted(o["contactsIds"]), sorted([con[fx.C[0]]["id"], con[fx.C[1]]["id"]]))
        self.assertEqual(o["contactsColumns"][con[fx.C[0]]["id"]], {"role": "Decision Maker"})
        self.assertEqual(o["amount"], 100.5)
        self.assertEqual(o["sfLeadSource"], "AB" + SENTINEL)

    def test_owner_resolution(self):
        self.assertNotIn("assignedUserId", self.acc[fx.A[1]])   # queue
        self.assertEqual(self.acc[fx.A[1]]["sfOwnerId"], fx.QUEUE)
        self.assertNotIn("assignedUserId", self.acc[fx.A[2]])   # unresolved
        self.assertEqual(self.acc[fx.A[2]]["sfOwnerId"], fx.U_MISSING)
        self.assertEqual(self.acc[fx.A[3]]["assignedUserId"], self.users[fx.U_INACTIVE]["id"])
        self.assertEqual(self.opp[fx.O[1]]["assignedUserId"], self.users[fx.U_SHARED]["id"])  # D4 legacy user
        reasons = {(e["sfId"], e["reason"]) for e in self.exc}
        self.assertIn((fx.A[1], "owner_queue_or_group"), reasons)
        self.assertIn((fx.A[2], "owner_unresolved"), reasons)
        self.assertIn((fx.O[4], "owner_queue_or_group"), reasons)
        # AC5: every record without an assigned user has an owner exception
        owner_exc = {e["sfId"] for e in self.exc if e["reason"].startswith("owner_")}
        for entity in ("Account", "Contact", "Opportunity", "Task", "Call", "Meeting"):
            for sf, rec in self.espo.by_sf(entity).items():
                if not rec.get("assignedUserId"):
                    self.assertIn(sf, owner_exc)

    def test_activities(self):
        task = self.espo.by_sf("Task")[fx.T[0]]
        self.assertEqual((task["parentType"], task["parentId"]), ("Opportunity", self.opp[fx.O[0]]["id"]))
        self.assertEqual(task["status"], "Completed")
        call = self.espo.by_sf("Call")[fx.T[1]]
        self.assertEqual((call["parentType"], call["parentId"]), ("Account", self.acc[fx.A[0]]["id"]))  # fallback
        self.assertEqual((call["direction"], call["duration"], call["status"]), ("Outbound", 60, "Held"))
        call2 = self.espo.by_sf("Call")[fx.T[6]]                       # no CallType: Outbound, Held
        self.assertEqual((call2["direction"], call2["status"]), ("Outbound", "Held"))
        open_task = self.espo.by_sf("Task")[fx.T[5]]
        self.assertEqual((open_task["status"], open_task["priority"]), ("Not Started", "High"))
        meet = self.espo.by_sf("Meeting")
        self.assertEqual(meet[fx.E[0]]["meetingType"], "Unspecified (legacy)")      # D10
        self.assertEqual(meet[fx.E[0]]["dateStart"], "2025-06-01 08:00:00")          # +0100 -> UTC
        self.assertEqual(meet[fx.E[1]]["meetingType"], "Presentation")
        self.assertNotIn("parentId", meet[fx.E[1]])
        # EndDateTime before the manifest t_start (2026-11-01) -> Held; attendees: the owner only.
        self.assertEqual(meet[fx.E[0]]["status"], "Held")
        self.assertEqual(meet[fx.E[0]]["usersIds"], [self.users[fx.U2]["id"]])
        self.assertNotIn("contactsIds", meet[fx.E[0]])

    def test_email_archived(self):
        em = self.espo.by_sf("Email")
        e = em[fx.M[0]]
        self.assertEqual(e["status"], "Archived")
        self.assertIs(e["isHtml"], False)
        self.assertEqual(e["to"], f"a.{SENTINEL}@example.test;b@example.test")
        self.assertEqual(e["messageId"], f"<m1.{SENTINEL}@example.test>")
        self.assertEqual(e["sfActivityId"], fx.T[3])
        self.assertEqual((e["parentType"], e["parentId"]), ("Opportunity", self.opp[fx.O[0]]["id"]))
        self.assertEqual(e["usersIds"], [self.users[fx.U1]["id"]])
        self.assertEqual(e["bodyPlain"], e["body"])
        for rec in em.values():
            self.assertFalse({"bcc", "attachmentsIds", "hasAttachment"} & set(rec))
        self.assertNotIn("messageId", em[fx.M[1]])
        self.assertNotIn(fx.T[2], em)            # the Task-Email represented by its EmailMessage

    def test_contact_phones_currency_description(self):
        con = self.espo.by_sf("Contact")
        self.assertEqual([(p["type"], p["primary"]) for p in con[fx.C[0]]["phoneNumberData"]],
                         [("Office", True), ("Mobile", False)])
        self.assertEqual(con[fx.C[1]]["phoneNumberData"],
                         [{"phoneNumber": f"+44 7 {SENTINEL}", "type": "Mobile", "primary": True}])
        self.assertEqual([p["type"] for p in con[fx.C[2]]["phoneNumberData"]], ["Office"])
        self.assertNotIn("phoneNumber", con[fx.C[0]])
        self.assertEqual((self.opp[fx.O[0]]["amount"], self.opp[fx.O[0]]["amountCurrency"]), (100.5, "GBP"))
        self.assertNotIn("amountCurrency", self.opp[fx.O[5]])         # no amount, no currency
        self.assertTrue(self.opp[fx.O[0]]["description"].startswith("OppDesc"))
        self.assertTrue(self.acc[fx.A[0]]["description"].startswith("AccDesc"))

    def test_contact_roles_valid_options(self):
        cols = self.opp[fx.O[0]]["contactsColumns"]
        con = self.espo.by_sf("Contact")
        self.assertEqual(cols, {con[fx.C[0]]["id"]: {"role": "Decision Maker"}, con[fx.C[1]]["id"]: {"role": ""}})
        self.assertEqual(self.opp[fx.O[3]]["contactsColumns"], {con[fx.C[1]]["id"]: {"role": ""}})
        self.assertIn({"object": "OpportunityContactRole", "sfId": fx.sid("00K", 6), "reason": "role_unmapped"},
                      self.exc)

    def test_non_human_user_owner_is_unresolved(self):
        self.assertNotIn("assignedUserId", self.acc[fx.A[5]])
        self.assertEqual(self.acc[fx.A[5]]["sfOwnerId"], fx.U_AUTOMATED)
        self.assertIn({"object": "Account", "sfId": fx.A[5], "reason": "owner_unresolved"}, self.exc)

    def test_every_post_skips_duplicate_check(self):
        posts = [h for (m, _p), h in zip(self.espo.requests, self.espo.headers) if m == "POST"]
        self.assertTrue(posts)
        self.assertTrue(all(h == {"X-Skip-Duplicate-Check": "true"} for h in posts))
        others = [h for (m, _p), h in zip(self.espo.requests, self.espo.headers) if m != "POST"]
        self.assertTrue(all(h == {} for h in others))

    def test_never_deletes(self):
        self.assertFalse([r for r in self.espo.requests if r[0] not in ("GET", "POST", "PUT")])


class TestIdempotency(Base):
    def test_second_run_zero_writes(self):
        self.assertEqual(self.run_load(), 0)
        first = len(self.espo.writes)
        self.assertGreater(first, 0)
        self.assertEqual(self.run_load(), 0)
        self.assertEqual(len(self.espo.writes), first)
        rep = self.report()
        self.assertEqual(rep["requests"]["writes"], 0)
        totals = [t for o in rep["objects"].values() for t in o["targets"].values()]
        self.assertEqual(sum(t["created"] + t["updated"] for t in totals), 0)

    def test_update_only_changed_attributes(self):
        self.run_load()
        rec = self.espo.by_sf("Account")[fx.A[0]]
        rec["website"] = "changed"
        n = len(self.espo.writes)
        self.run_load()
        self.assertEqual(self.espo.writes[n:], [("PUT", "Account", {"website": "https://f.example.test/" + SENTINEL})])

    def test_existing_not_in_snapshot_flagged_not_deleted(self):
        self.espo._insert("Account", {"sfId": fx.A[4], "name": "kept"})
        self.espo._insert("Contact", {"sfId": fx.sid("003", 777), "lastName": "kept"})
        self.run_load()
        exc = self.exceptions()
        self.assertIn({"object": "Account", "sfId": fx.A[4], "reason": "exists_soft_deleted_in_sf"}, exc)
        self.assertIn({"object": "Contact", "sfId": fx.sid("003", 777), "reason": "exists_not_in_snapshot"}, exc)
        self.assertIn(fx.A[4], self.espo.by_sf("Account"))

    def _interrupted(self, out, limit=9):
        class Boom(Exception):
            pass

        def interrupt(client):
            orig = client.create

            def create(entity, attrs):
                if client.writes >= limit:
                    raise Boom()
                return orig(entity, attrs)
            client.create = create
            return client

        with self.assertRaises(Boom):
            self.run_load(out=out, fail_after=interrupt)
        self.assertFalse(os.path.exists(os.path.join(out, "load-report.json")))
        return out

    def test_resume_after_interruption(self):
        first = self._interrupted(os.path.join(self.tmp, "first"))
        before = {n: open(os.path.join(first, n), "rb").read() for n in os.listdir(first)}
        out = os.path.join(self.tmp, "resumed")
        self.assertEqual(self.run_load("--resume", first, out=out), 0, self.last_err)
        self.assertIn("event=run", self.last_err)
        self.assertIn("resumed=true", self.last_err)
        self.assertEqual({n: open(os.path.join(first, n), "rb").read() for n in os.listdir(first)}, before)
        resumed = self.report(out)
        ref_espo = FakeEspo()
        self.assertEqual(self.run_load(espo=ref_espo), 0)
        clean = self.report()
        strip = lambda r: {k: v for k, v in r.items() if k != "requests"}  # noqa: E731
        self.assertEqual(strip(resumed), strip(clean))
        norm = lambda e: sorted(json.dumps({k: v for k, v in r.items() if not k.endswith("Id") and  # noqa
                                            not k.endswith("Ids") and k not in ("id", "contactsColumns")},
                                           sort_keys=True) for r in e.db["Opportunity"].values())
        self.assertEqual(norm(self.espo), norm(ref_espo))
        self.assertEqual(sum(len(v) for v in self.espo.db.values()), sum(len(v) for v in ref_espo.db.values()))
        # the new progress carries the earlier entries too
        with open(os.path.join(first, "progress.jsonl")) as a, open(os.path.join(out, "progress.jsonl")) as b:
            self.assertTrue(b.read().startswith(a.read()))

    def test_resume_requires_same_snapshot_sha_and_target(self):
        first = self._interrupted(os.path.join(self.tmp, "first"))
        with open(os.path.join(first, "run.json")) as fh:
            run = json.load(fh)
        self.assertRegex(run["snapshotManifestSha"], r"\A[0-9a-f]{64}\Z")
        self.assertEqual(run["target"], "dev")
        other = write_snapshot(os.path.join(self.tmp, "other"), extra={"t_start": "2026-11-02T00:00:00Z"})
        n = len(self.espo.requests)
        self.assertEqual(self.run_load("--resume", first, snap=other), 2)
        self.assertIn("code=resume_snapshot_mismatch", self.last_err)
        self.assertFalse(os.path.exists(self.last_dir))
        self.assertEqual(len(self.espo.requests), n)
        real = write_snapshot(os.path.join(self.tmp, "real"), synthetic=False)
        real_first = os.path.join(self.tmp, "real-first")
        os.mkdir(real_first, 0o700)
        with open(os.path.join(real_first, "run.json"), "w") as fh:
            json.dump(dict(run, snapshotManifestSha=snap_mod.open_snapshot(real).manifest_sha256), fh)
        open(os.path.join(real_first, "progress.jsonl"), "w").close()
        for name in os.listdir(real_first):
            os.chmod(os.path.join(real_first, name), 0o600)
        self.assertEqual(self.run_load("--resume", real_first, snap=real, target="beta"), 2)
        self.assertIn("code=resume_target_mismatch", self.last_err)

    def test_resume_refuses_completed_or_unsealed_dir(self):
        self.run_load()
        done = self.last_dir
        self.assertEqual(self.run_load("--resume", done), 2)
        self.assertIn("code=resume_dir_complete", self.last_err)
        self.assertFalse(os.path.exists(self.last_dir))
        self.assertEqual(self.run_load("--resume", os.path.join(self.tmp, "missing")), 2)
        self.assertIn("code=resume_dir_missing", self.last_err)
        self.espo = FakeEspo()
        first = self._interrupted(os.path.join(self.tmp, "first"))
        os.chmod(first, 0o755)
        self.assertEqual(self.run_load("--resume", first), 2)
        self.assertIn("code=resume_dir_invalid", self.last_err)
        os.chmod(first, 0o700)
        open(os.path.join(first, "planted"), "w").close()
        self.assertEqual(self.run_load("--resume", first), 2)
        self.assertIn("code=resume_dir_invalid", self.last_err)
        os.remove(os.path.join(first, "planted"))
        os.chmod(os.path.join(first, "run.json"), 0o644)
        self.assertEqual(self.run_load("--resume", first), 2)
        self.assertIn("code=resume_dir_invalid", self.last_err)
        os.chmod(os.path.join(first, "run.json"), 0o600)
        self.assertEqual(self.run_load("--resume", first, out=first), 2)
        self.assertIn("code=output_dir_exists", self.last_err)

    def test_output_dir_must_not_exist(self):
        os.mkdir(os.path.join(self.tmp, "exists"))
        self.assertEqual(self.run_load(out=os.path.join(self.tmp, "exists")), 2)
        self.assertIn("code=output_dir_exists", self.last_err)


class TestTransportAndErrors(Base):
    def test_retry_on_429_and_5xx(self):
        self.espo.fail_next = [429, 503, 502]
        self.assertEqual(self.run_load(), 0)
        self.assertEqual(self.report()["objects"]["Account"]["targets"]["Account"]["created"], 5)

    def test_retries_bounded(self):
        client = EspoClient(self.espo, retries=2, sleep=lambda s: None)
        self.espo.fail_next = [503] * 10
        with self.assertRaises(TransportError):
            client.list_all("Account", ["sfId"])
        self.assertEqual(len(self.espo.requests), 3)

    def test_unique_sfid_violation_is_write_failed(self):
        # A soft-deleted EspoCRM row holding the sfId: 10.0.12 answers 500 (uncaught PDOException).
        espo = FakeEspo(hidden_sfids={fx.A[0]})
        self.assertEqual(self.run_load(espo=espo), 5)
        exc = self.exceptions()
        self.assertIn({"object": "Account", "sfId": fx.A[0], "reason": "write_failed"}, exc)
        posts = [b for m, e, b in espo.writes if m == "POST" and b.get("sfId") == fx.A[0]]
        self.assertEqual(len(posts), 6)                       # 1 + 5 bounded retries, then stop
        self.assertEqual(self.report()["objects"]["Account"]["targets"]["Account"]["failed"], 1)
        self.assertEqual(self.report()["objects"]["Account"]["targets"]["Account"]["created"], 4)

    def test_duplicate_conflict_409_recorded(self):
        class NoSkip:
            def __init__(self, inner):
                self.inner = inner

            def send(self, method, path, query=None, body=None, headers=None):
                return self.inner.send(method, path, query, body, None)
        espo = FakeEspo()
        espo._insert("Account", {"name": f"Firm 0 {SENTINEL}"})          # same name, no sfId
        self.assertEqual(self.run_load(espo=NoSkip(espo)), 5)
        self.assertIn({"object": "Account", "sfId": fx.A[0], "reason": "duplicate_conflict"}, self.exceptions())
        # With the header (the shipped client), branch firms sharing a name are created.
        espo2 = FakeEspo()
        espo2._insert("Account", {"name": f"Firm 0 {SENTINEL}"})
        self.assertEqual(self.run_load(espo=espo2), 0)
        self.assertIn(fx.A[0], espo2.by_sf("Account"))

    def test_https_transport_header_allowlist(self):
        t = HttpsTransport("127.0.0.1", 9, "k")
        for headers in ({"X-Skip-Duplicate-Check": "false"}, {"X-Api-Key": "other"}, {"Host": "example.test"}):
            with self.assertRaises(TransportError):
                t.send("POST", "Account", None, {}, headers)

    def test_https_transport_refuses_other_hosts(self):
        for host in ("localhost", "::1", "127.0.0.2", "example.test"):
            with self.assertRaises(TransportError):
                HttpsTransport(host, 8080, "k")
        with self.assertRaises(TransportError):
            HttpsTransport("127.0.0.1", 8080, "")
        t = HttpsTransport("127.0.0.1", 8080, "k")
        with self.assertRaises(TransportError):
            t.send("DELETE", "Account/abc")
        with self.assertRaises(TransportError):
            t.send("GET", "../admin")

    def test_missing_config_fails_loudly(self):
        rc = cli.main(["load", self.snap, "--out", os.path.join(self.tmp, "o")], environ={},
                      stderr=io.StringIO(), stdout=io.StringIO())
        self.assertEqual(rc, 2)


class TestNoContent(Base):
    def test_sentinel_absent_everywhere(self):
        self.espo.fail_next = [429]
        espo2 = FakeEspo(hidden_sfids={fx.O[0]})
        outputs = []
        for espo in (self.espo, espo2):
            self.run_load(espo=espo)
            outputs.append(self.last_err + self.last_out)
            for name in os.listdir(self.last_dir):
                with open(os.path.join(self.last_dir, name), encoding="utf-8") as fh:
                    outputs.append(fh.read())
        self.assertTrue(any(SENTINEL in json.dumps(b) for _, _, b in self.espo.writes))  # it was in the data
        for text in outputs:
            self.assertNotIn(SENTINEL, text)
            self.assertNotIn("7f3a", text)

    def test_exceptions_shape_and_mode(self):
        self.run_load()
        path = os.path.join(self.last_dir, "exceptions.jsonl")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.last_dir).st_mode), 0o700)
        for e in self.exceptions():
            self.assertEqual(set(e), {"object", "sfId", "reason"})
            self.assertIn(e["reason"], EXCEPTION_CODES)
            self.assertRegex(e["sfId"], r"\A[A-Za-z0-9]{18}\Z")

    def test_report_counts_only(self):
        self.run_load()

        def walk(v):
            if isinstance(v, dict):
                for k, x in v.items():
                    self.assertRegex(k, r"\A[A-Za-z_]+\Z")
                    walk(x)
            elif isinstance(v, str):
                self.assertRegex(v, r"\A[A-Za-z0-9_. -]+\Z")
            else:
                self.assertIsInstance(v, (int, bool, type(None)))
        walk(self.report())

    def test_log_redacts(self):
        from crm_load.log import Log
        log = Log(io.StringIO())
        log.event("x", value="a b " + SENTINEL, n=3, code="ok_code")
        self.assertEqual(log.lines[0], "crm-load event=x code=ok_code n=3 value=<redacted>")


class TestNames(unittest.TestCase):
    PATTERNS = [{"code": "ref_dash_name", "regex": r"(?P<clientReference>[A-Z]{2}\d{4}) - (?P<deceasedName>.+)"},
                {"code": "case_only", "regex": r"Case (?P<caseNumber>\d+)"}]

    def test_patterns(self):
        p = NameParser(self.PATTERNS)
        self.assertEqual(p.parse("AB1234 - Jane Example"),
                         ("ref_dash_name", {"clientReference": "AB1234", "deceasedName": "Jane Example"}))
        self.assertEqual(p.parse("Case 42"), ("case_only", {"caseNumber": "42"}))
        self.assertEqual(p.parse("AB1234 Jane"), (None, {}))      # no partial match
        self.assertEqual(p.parse(""), (None, {}))

    def test_bad_patterns_rejected(self):
        for bad in ({"code": "x", "regex": "("}, {"code": "X!", "regex": "(?P<caseNumber>a)"},
                    {"code": "x", "regex": "(?P<other>a)"}, {"code": "x", "regex": "abc"},
                    {"code": "x", "regex": "(?P<caseNumber>a)", "extra": 1}):
            with self.assertRaises(LoadError):
                NameParser([bad])

    def test_shipped_table_starts_empty(self):
        self.assertEqual(load_json("name_patterns.json")["patterns"], [])
        self.assertEqual(load_json("lead_source_map.json")["map"], {})

    def test_parsed_name_maps_and_unparsed_excepted(self):
        mapping = load_json("mapping.json")
        m = Mapper(mapping, {"map": {}}, NameParser(self.PATTERNS), "2026-11-01")

        class Ctx:
            user_id = record_id = service_type_id = staticmethod(lambda *a: None)
        row = dict(Id=fx.O[0], Name="AB1234 - Jane Example", StageName="Closed Won", OwnerId=fx.U1)
        attrs, exc = m.opportunity(row, Ctx())
        self.assertEqual((attrs["clientReference"], attrs["deceasedName"], attrs["caseNumber"]),
                         ("AB1234", "Jane Example", None))
        self.assertNotIn("name_unparsed", exc)
        attrs, exc = m.opportunity(dict(row, Name="free text"), Ctx())
        self.assertIn("name_unparsed", exc)
        self.assertIsNone(attrs["clientReference"])


class TestUsers(Base):
    def test_users_json(self):
        role_map = {"profiles": {"Profile A": {"teams": ["Enquiries"], "roles": ["ER Staff"]}},
                    "userRoles": {"Role C": {"teams": ["Ancillary intake"], "roles": ["ER Intake"]}},
                    "legacyShared": {"sfIds": [fx.U_SHARED], "firstName": "Ancillary Services",
                                     "lastName": "(shared, legacy)", "teams": ["Ancillary intake"], "roles": []}}
        rm = os.path.join(self.tmp, "rm.json")
        with open(rm, "w") as fh:
            json.dump(role_map, fh)
        out, err = os.path.join(self.tmp, "u"), io.StringIO()
        self.assertEqual(cli.main(["users", self.snap, "--role-map", rm, "--out", out], stderr=err,
                                  stdout=io.StringIO()), 0)
        self.assertNotIn(SENTINEL, err.getvalue())
        with open(os.path.join(out, "users.json")) as fh:
            users = {u["sfId"]: u for u in json.load(fh)}
        self.assertEqual(set(users[fx.U1]), {"sfId", "userName", "firstName", "lastName", "emailAddress",
                                             "isActive", "teams", "roles"})
        self.assertEqual((users[fx.U1]["teams"], users[fx.U1]["roles"]),
                         (["Ancillary intake", "Enquiries"], ["ER Intake", "ER Staff"]))
        self.assertEqual(users[fx.U2]["teams"], [])            # unmapped profile: nothing guessed
        self.assertIs(users[fx.U_INACTIVE]["isActive"], False)  # D5
        s = users[fx.U_SHARED]
        self.assertEqual((s["isActive"], s["lastName"], s["teams"]), (False, "(shared, legacy)", ["Ancillary intake"]))
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(out, "users.json")).st_mode), 0o600)
        # Standard users only: the AutomatedProcess user is skipped (user_not_human), not excepted.
        self.assertEqual(set(users), {fx.U1, fx.U2, fx.U_INACTIVE, fx.U_SHARED})
        self.assertIn("skipped_user_not_human=1", err.getvalue())
        with open(os.path.join(out, "exceptions.jsonl")) as fh:
            self.assertNotIn(fx.U_AUTOMATED, fh.read())

    def test_example_role_map_has_placeholders_only(self):
        with open(os.path.join(ROOT, "load", "examples", "role-map.example.json")) as fh:
            doc = json.load(fh)
        for section in ("profiles", "userRoles"):
            for name in doc[section]:
                self.assertRegex(name, r"\A<.*>\Z")


class TestStatic(unittest.TestCase):
    """Every attribute written by mapping.json exists in the target entityDefs or the 10.0.12 core."""

    # Core 10.0.12 attributes used here (Call/Meeting/Task/Email per tests/unit/activity_policy.py).
    CORE = {
        "Account": {"name", "description", "phoneNumber", "website", "assignedUser", "billingAddress", "shippingAddress",
                    "type", "industry"},
        "Contact": {"firstName", "lastName", "salutationName", "title", "emailAddress", "phoneNumber", "address",
                    "account", "assignedUser"},
        "Opportunity": {"name", "description", "amount", "closeDate", "account", "assignedUser", "contacts", "stage"},
        "ServiceType": set(),
        "Email": {"name", "status", "from", "to", "cc", "body", "bodyPlain", "isHtml", "dateSent", "parent",
                  "users", "messageId", "assignedUser"},
    }

    def _fields(self, entity):
        import importlib
        import sys
        unit = os.path.join(ROOT, "tests", "unit")
        if unit not in sys.path:
            sys.path.append(unit)
        ap = importlib.import_module("activity_policy")
        with open(os.path.join(ENTITY_DEFS, f"{entity}.json")) as fh:
            custom = set(json.load(fh).get("fields", {}))
        return custom | ap.CORE_FIELDS.get(entity, set()) | self.CORE.get(entity, set())

    @staticmethod
    def _field_of(attr):
        for suffix in ("Ids", "Columns", "Id", "Type", "Date", "Data", "Currency"):
            if attr.endswith(suffix) and len(attr) > len(suffix):
                return attr[:-len(suffix)]
        for part in ("Street", "City", "State", "PostalCode", "Country"):
            if attr.endswith(part):
                return attr[:-len(part)]
        return attr

    def test_every_mapped_attribute_exists(self):
        mapping = load_json("mapping.json")
        self.assertEqual(mapping["contractVersion"], 4)
        for entity, spec in mapping["entities"].items():
            fields = self._fields(entity)
            attrs = list(spec.get("copy", {})) + list(spec.get("enum", {})) + spec.get("attributes", []) + \
                spec.get("secondPass", [])
            for a in attrs:
                self.assertTrue(a in fields or self._field_of(a) in fields, f"{entity}.{a}")

    def test_enum_options_match_entity_defs(self):
        mapping = load_json("mapping.json")
        for key, options in mapping["enums"].items():
            entity, field = key.split(".")
            with open(os.path.join(ENTITY_DEFS, f"{entity}.json")) as fh:
                self.assertEqual(json.load(fh)["fields"][field]["options"], options, key)

    def test_source_fields_in_contract_v4(self):
        mapping = load_json("mapping.json")
        for entity, spec in mapping["entities"].items():
            src = spec["source"].split()[0]
            for f in list(spec.get("copy", {}).values()) + list(spec.get("enum", {}).values()):
                self.assertIn(f, fx.FIELDS_V4[src], f"{entity}.{f}")
            self.assertNotIn("Post_code__c", json.dumps(spec))
            self.assertNotIn("Key_Information__c", json.dumps(spec))


if __name__ == "__main__":
    unittest.main()
