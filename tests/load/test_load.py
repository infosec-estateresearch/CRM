"""crm-load tests (CRM-006): in-process, synthetic, no network."""

import io
import json
import os
import shutil
import stat
import tempfile
import unittest

from tests.load import fixtures as fx
from tests.load.fixtures import SENTINEL, write_snapshot

from crm_load import cli, snapshot as snap_mod  # noqa: E402  (path set by fixtures)
from crm_load.errors import GateError, LoadError, TransportError
from crm_load.mapping import EXCEPTION_CODES, Mapper, load_json
from crm_load.names import NameParser
from crm_load.transport import LoopbackHttpTransport
from crm_load.api import EspoClient

ROOT = fx.ROOT
ENTITY_DEFS = os.path.join(ROOT, "custom", "Espo", "Custom", "Resources", "metadata", "entityDefs")
# Core 10.0.12 enum options, PL-verified on crm-dev (not in the custom entityDefs).
CORE_ENUM_OPTIONS = {"Contact.salutationName": ["", "Mr.", "Ms.", "Mrs.", "Dr."]}


class _NullCtx:
    def soft_deleted(self, sf_id):
        return False

    def user_id(self, sf_id):
        return None

    def record_id(self, obj, sf_id):
        return None

    def service_type_id(self, value):
        return value


class FakeEspo(fx.FakeEspo):
    """The fake as provisioned (config/settings.json): Settings currencyList GBP. The bare
    fixture (``fx.FakeEspo``) keeps the 10.0.12 install default, USD only (CRM-008)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.currency_list = ["GBP"]
        if isinstance(self.settings, dict):
            self.settings["currencyList"] = ["GBP"]


class Base(unittest.TestCase):
    def mapper(self):
        return Mapper(load_json("mapping.json"), {}, NameParser([]), "2026-11-01", "2026-11-01 00:00:00")

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
        fx.unseal(os.path.dirname(self.snap))
        path = os.path.join(self.snap, "objects", "Account.jsonl.gz")
        with open(path, "ab") as fh:
            fh.write(b"x")
        self._refuse(self.snap, "checksum_mismatch")

    def test_unlisted_and_missing_file_refused(self):
        fx.unseal(os.path.dirname(self.snap))
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
        self.assertIn("code=target_beta_requires_extract", self.last_err)
        self.assertEqual(self.espo.requests, [])
        self.assertFalse(os.path.exists(self.last_dir))
        self.assertEqual(self.run_load(snap=real, target="beta"), 0)
        self.assertEqual(self.run_load(target="qa"), 2)
        self.assertIn("code=usage", self.last_err)


class TestSyntheticRule(Base):
    """Synthetic: <name>-selftest/run-1|run-2 under a sealed, verified mode-selftest parent."""

    def _dev_refused(self, snap):
        n = len(self.espo.requests)
        self.assertEqual(self.run_load(snap=snap), 2, self.last_err)
        self.assertIn("code=target_dev_requires_synthetic", self.last_err)
        self.assertEqual(len(self.espo.requests), n)

    def _beta_refused(self, snap, code):
        n = len(self.espo.requests)
        self.assertEqual(self.run_load(snap=snap, target="beta"), 2, self.last_err)
        self.assertIn(f"code={code}", self.last_err)
        self.assertEqual(len(self.espo.requests), n)

    def _parent_manifest(self, parent, **change):
        path = os.path.join(parent, "manifest.json")
        fx.unseal(parent)
        with open(path) as fh:
            doc = json.load(fh)
        doc.update(change)
        with open(path, "w") as fh:
            json.dump(doc, fh)
        fx.seal(parent)

    def test_real_selftest_shape_is_synthetic(self):
        parent = os.path.dirname(self.snap)
        self.assertTrue(parent.endswith("-selftest"))
        with open(os.path.join(self.snap, "manifest.json")) as fh:
            run = json.load(fh)
        self.assertEqual((run["mode"], run["origin_kind"]), ("extract", "production"))
        with open(os.path.join(parent, "manifest.json")) as fh:
            self.assertNotIn("contract", json.load(fh))
        for name in ("run-1", "run-2"):
            self.assertTrue(snap_mod.open_snapshot(os.path.join(parent, name)).synthetic)
            self.assertEqual(self.run_load(snap=os.path.join(parent, name), espo=FakeEspo()), 0, self.last_err)
        rc = cli.main(["verify", self.snap], stdout=io.StringIO(), stderr=io.StringIO())
        self.assertEqual(rc, 0)

    def test_run_manifest_mode_selftest_is_not_a_snapshot(self):
        root = write_snapshot(os.path.join(self.tmp, "m"), extra={"mode": "selftest"})
        with self.assertRaises(GateError) as cm:
            snap_mod.open_snapshot(root)
        self.assertEqual(cm.exception.code, "not_a_snapshot")

    def test_parent_mode_must_be_selftest(self):
        parent = os.path.dirname(self.snap)
        self._parent_manifest(parent, mode="extract")
        self.assertFalse(snap_mod.synthetic_origin(self.snap))
        self._dev_refused(self.snap)

    def test_parent_must_verify(self):
        parent = os.path.dirname(self.snap)
        fx.unseal(parent)
        with open(os.path.join(parent, "planted.txt"), "w") as fh:
            fh.write("x")
        fx.seal(parent)
        self._dev_refused(self.snap)                         # unlisted file in the parent
        os.remove(os.path.join(parent, "planted.txt"))
        fx.unseal(parent)
        os.remove(os.path.join(parent, "manifest.json"))
        fx.seal(parent)
        self._dev_refused(self.snap)                         # no parent manifest

    def test_parent_must_be_sealed(self):
        parent = os.path.dirname(self.snap)
        for rel, mode in (("run-1/objects/Account.jsonl.gz", 0o600), ("manifest.json", 0o440),
                          ("run-2", 0o750), ("", 0o755)):
            path = os.path.join(parent, rel)
            os.chmod(path, mode)
            self.assertFalse(snap_mod.synthetic_origin(self.snap), rel)
            self._dev_refused(self.snap)
            fx.seal(parent)
        self.assertTrue(snap_mod.synthetic_origin(self.snap))

    def test_path_shape(self):
        unsealed = write_snapshot(os.path.join(self.tmp, "u"), sealed=False)
        self.assertFalse(snap_mod.synthetic_origin(unsealed))
        # a run-3, or a parent without the -selftest suffix, is not synthetic
        parent = os.path.dirname(self.snap)
        fx.unseal(parent)
        shutil.copytree(self.snap, os.path.join(parent, "run-3"))
        fx.write_selftest_manifest(parent)
        fx.seal(parent)
        self.assertTrue(snap_mod.synthetic_origin(self.snap))
        self._dev_refused(os.path.join(parent, "run-3"))
        other = os.path.join(self.tmp, "plain")
        shutil.copytree(parent, other)
        self._dev_refused(os.path.join(other, "run-1"))
        # an <id>-extract production snapshot is never synthetic
        self._dev_refused(write_snapshot(os.path.join(self.tmp, "p"), synthetic=False))

    def test_beta_takes_only_extract(self):
        self._beta_refused(self.snap, "target_beta_requires_extract")              # run-1 of a selftest
        parent = os.path.dirname(self.snap)
        nested = write_snapshot(os.path.join(parent + "-x", "inner-selftest", "z"), synthetic=False)
        self.assertTrue(nested.endswith("z-extract"))
        self._beta_refused(nested, "target_beta_requires_extract")                 # under a *-selftest dir
        odd = write_snapshot(os.path.join(self.tmp, "odd"), synthetic=False)
        renamed = os.path.join(self.tmp, "odd-snapshot")
        os.rename(odd, renamed)
        self._beta_refused(renamed, "target_beta_requires_extract")                # not <name>-extract
        marked = write_snapshot(os.path.join(self.tmp, "marked"), data=fx.org(), synthetic=False)
        self._beta_refused(marked, "synthetic_content_in_beta")                    # SENTINEL in Account Name
        self.assertFalse(os.path.exists(self.last_dir))
        good = write_snapshot(os.path.join(self.tmp, "good"), synthetic=False)
        self.assertEqual(self.run_load(snap=good, target="beta"), 0, self.last_err)


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
        import builtins
        from unittest import mock
        legacy = write_snapshot(os.path.join(self.tmp, "legacy"), layout="legacy")
        waiver = os.path.join(legacy, "input", "waiver.json")
        real_open, opened = builtins.open, []

        def spy(file, mode="r", *a, **kw):
            if isinstance(file, str):
                opened.append((os.path.abspath(file), mode))
            return real_open(file, mode, *a, **kw)
        with mock.patch("builtins.open", spy):
            self.assertEqual(self.run_load(snap=legacy), 0, self.last_err)
        self.assertTrue(any(f.startswith(legacy) for f, _m in opened))
        # dev: the selftest parent's checksums cover the waiver, so it is hashed (rb), never parsed
        self.assertEqual({m for f, m in opened if f == waiver}, {"rb"})
        # beta: a production <id>-extract waiver is never opened at all
        prod = write_snapshot(os.path.join(self.tmp, "prodlegacy"), layout="legacy", synthetic=False)
        opened.clear()
        with mock.patch("builtins.open", spy):
            self.assertEqual(self.run_load(snap=prod, target="beta", espo=FakeEspo()), 0, self.last_err)
        self.assertNotIn(os.path.join(prod, "input", "waiver.json"), {f for f, _m in opened})

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
        self.assertEqual(o["Opportunity"]["targets"]["Opportunity"]["created"], 5)   # O[5]: stage refused
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
        self.assertIsNone(self.acc[fx.A[1]]["type"])           # unmapped enum left empty (explicit null)
        self.assertIn({"object": "Account", "sfId": fx.A[1], "reason": "enum_unmapped"}, self.exc)

    def test_second_pass_parents(self):
        self.assertEqual(self.acc[fx.A[1]]["parentId"], self.acc[fx.A[0]]["id"])
        self.assertEqual(self.acc[fx.A[2]]["parentId"], self.acc[fx.A[1]]["id"])
        self.assertIsNone(self.acc[fx.A[3]].get("parentId"))      # parent soft-deleted: never linked
        self.assertIn({"object": "Account", "sfId": fx.A[3], "reason": "parent_soft_deleted_in_sf"}, self.exc)
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
        self.assertIsNone(o[fx.O[4]]["lossReason"])
        self.assertIs(o[fx.O[4]]["lossReasonLegacyMissing"], True)
        # An unmapped stage: Opportunity.stage has no "" option, so the record is refused, never defaulted.
        self.assertNotIn(fx.O[5], o)
        self.assertIn({"object": "Opportunity", "sfId": fx.O[5], "reason": "stage_unmapped"}, self.exc)
        self.assertIn({"object": "Opportunity", "sfId": fx.O[5], "reason": "enum_blank_unrepresentable"}, self.exc)
        self.assertEqual(self.rep["objects"]["Opportunity"]["skipped"]["enum_blank_unrepresentable"], 1)
        for rec in o.values():
            self.assertNotIn("postcode", rec)
            self.assertNotIn("keyInformation", rec)
            self.assertIsNone(rec["introducedById"])             # D7 table is empty
            self.assertIsNone(rec["channel"])

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
        self.assertIsNone(self.acc[fx.A[1]]["assignedUserId"])   # queue
        self.assertEqual(self.acc[fx.A[1]]["sfOwnerId"], fx.QUEUE)
        self.assertIsNone(self.acc[fx.A[2]]["assignedUserId"])   # unresolved
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
        self.assertIsNone(meet[fx.E[1]]["parentId"])
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
        self.assertEqual(e["from"], f"from.{SENTINEL}@example.test")          # bare address
        self.assertEqual(e["fromString"], f"N {SENTINEL} <from.{SENTINEL}@example.test>")
        self.assertEqual(em[fx.M[1]]["fromString"], "x@example.test")         # no name: the address
        self.assertTrue(e["messageId"].startswith("dummy:"))                 # server-set, never sent
        posts = [b for m, ent, b in self.espo.writes if ent == "Email"]
        self.assertTrue(posts and all("messageId" not in b for b in posts))
        self.assertEqual(e["sfActivityId"], fx.T[3])
        self.assertEqual((e["parentType"], e["parentId"]), ("Opportunity", self.opp[fx.O[0]]["id"]))
        self.assertEqual(e["usersIds"], [self.users[fx.U1]["id"]])
        self.assertEqual(e["bodyPlain"], e["body"])
        for rec in em.values():
            self.assertFalse({"bcc", "attachmentsIds", "hasAttachment"} & set(rec))
        self.assertNotIn(fx.T[2], em)            # the Task-Email represented by its EmailMessage

    def test_contact_phones_currency_description(self):
        con = self.espo.by_sf("Contact")
        self.assertEqual([(p["type"], p["primary"]) for p in con[fx.C[0]]["phoneNumberData"]],
                         [("Office", True), ("Mobile", False)])
        self.assertEqual(con[fx.C[1]]["phoneNumberData"],
                         [{"phoneNumber": "+44 7700 900001", "type": "Mobile", "primary": True,
                           "optOut": False, "invalid": False}])                 # read back with extra keys
        self.assertEqual([p["type"] for p in con[fx.C[2]]["phoneNumberData"]], ["Office"])
        # The importer never sends phoneNumber for a Contact; the server derives it from the primary.
        self.assertFalse([b for m, e, b in self.espo.writes if e == "Contact" and "phoneNumber" in b])
        self.assertEqual(con[fx.C[0]]["phoneNumber"], "01632 960100")
        self.assertEqual((self.opp[fx.O[0]]["amount"], self.opp[fx.O[0]]["amountCurrency"]), (100.5, "GBP"))
        attrs, _exc = self.mapper().opportunity(dict(Id=fx.O[0], StageName="Closed Won", Amount=None),
                                                 _NullCtx())
        self.assertIsNone(attrs["amountCurrency"])                     # no amount, no currency
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
        self.assertIsNone(self.acc[fx.A[5]]["assignedUserId"])
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


class TestServerBehaviour(Base):
    """The fake reproduces crm-dev: phone read-back keys and refusal, from, messageId, defaults."""

    def test_fake_reproduces_server(self):
        f = FakeEspo()
        _st, doc = f.send("POST", "Contact", body={"sfId": "x1", "phoneNumberData": [
            {"phoneNumber": "01632 960000", "type": "Office", "primary": True}]})
        self.assertEqual(f.db["Contact"][doc["id"]]["phoneNumberData"],
                         [{"phoneNumber": "01632 960000", "type": "Office", "primary": True, "optOut": False,
                           "invalid": False}])
        self.assertEqual(f.send("POST", "Contact", body={"sfId": "x2", "phoneNumber": "n/a"})[0], 400)
        intl = FakeEspo(phone_international=True)
        self.assertEqual(intl.send("POST", "Account", body={"sfId": "a", "name": "a", "phoneNumber": "01632 960000"}),
                         (400, {"field": "phoneNumber", "type": "valid"}))
        _st, doc = intl.send("POST", "Account", body={"sfId": "b", "name": "b", "phoneNumber": "+44 1632 960000"})
        self.assertEqual(intl.db["Account"][doc["id"]]["phoneNumber"], "+441632960000")
        _st, doc = f.send("POST", "Email", body={"sfId": "e", "from": "N <a@example.test>", "to": "b@example.test",
                                                 "messageId": "<m>"})
        self.assertIsNone(f.db["Email"][doc["id"]]["from"])
        self.assertEqual(f.db["Email"][doc["id"]]["messageId"], f"dummy:{doc['id']}")
        _st, doc = f.send("POST", "Call", body={"sfId": "c", "dateStart": "2025-01-01 00:00:00", "assignedUserId": "u"})
        self.assertEqual(f.db["Call"][doc["id"]]["direction"], "Outbound")
        self.assertEqual(f.send("POST", "Meeting", body={"sfId": "m"})[0], 400)

    def test_second_run_zero_writes_against_the_faithful_fake(self):
        self.assertEqual(self.run_load(), 0)
        con = self.espo.by_sf("Contact")[fx.C[0]]
        self.assertTrue(all({"optOut", "invalid"} <= set(p) for p in con["phoneNumberData"]))
        self.assertTrue(all(r["messageId"].startswith("dummy:") for r in self.espo.by_sf("Email").values()))
        # the phone order as read back differs from the order sent: still equal as a set
        con["phoneNumberData"].reverse()
        self.espo.by_sf("Opportunity")[fx.O[0]]["amount"] = 100.50    # numerically equal
        self.espo.by_sf("Opportunity")[fx.O[2]]["amount"] = "100.5"
        n = len(self.espo.writes)
        self.assertEqual(self.run_load(), 0)
        self.assertEqual(self.espo.writes[n:], [])
        self.assertEqual(self.report()["requests"]["writes"], 0)

    def test_phone_changes_are_still_written(self):
        self.run_load()
        con = self.espo.by_sf("Contact")[fx.C[0]]
        con["phoneNumberData"][0]["primary"] = False
        con["phoneNumberData"][1]["primary"] = True
        self.espo.by_sf("Opportunity")[fx.O[0]]["amount"] = 99
        n = len(self.espo.writes)
        self.run_load()
        ents = sorted(e for _m, e, _b in self.espo.writes[n:])
        self.assertEqual(ents, ["Contact", "Opportunity"])

    def test_junk_phone_never_sent(self):
        self.run_load()
        self.assertIsNone(self.espo.by_sf("Account")[fx.A[2]]["phoneNumber"])            # 'n/a'
        self.assertIn({"object": "Account", "sfId": fx.A[2], "reason": "phone_rejected"}, self.exceptions())
        self.assertFalse([b for _m, _e, b in self.espo.writes if b.get("phoneNumber") == "n/a"])

    def test_phone_refused_by_server_keeps_valid_siblings(self):
        class RefuseOffice(FakeEspo):
            """Refuses the national Office numbers 01632 9601xx; stores every other number verbatim."""
            def _phone(self, number):
                if isinstance(number, str) and number.startswith("01632 9601"):
                    return number, True
                return super()._phone(number)
        espo = RefuseOffice()
        self.assertEqual(self.run_load(espo=espo), 0, self.last_err)
        first_dir = self.last_dir
        exc = self.exceptions()
        con = espo.by_sf("Contact")
        # C[0]: national Office refused, international Mobile kept (now primary)
        self.assertEqual([(p["phoneNumber"], p["type"], p["primary"]) for p in con[fx.C[0]]["phoneNumberData"]],
                         [("+44 7700 900000", "Mobile", True)])
        self.assertFalse(con[fx.C[2]].get("phoneNumberData"))              # its only number refused
        for c in (fx.C[0], fx.C[2]):
            self.assertIn({"object": "Contact", "sfId": c, "reason": "phone_refused"}, exc)
        self.assertNotIn({"object": "Contact", "sfId": fx.C[1], "reason": "phone_refused"}, exc)
        self.assertEqual(self.report()["exceptions"]["byReason"]["phone_refused"], 2)   # once per number
        with open(os.path.join(first_dir, "phone-refusals.json")) as fh:
            hashes = json.load(fh)
        self.assertEqual(len(hashes), 2)
        self.assertNotIn("01632", json.dumps(hashes))                    # content-free
        self.assertTrue(all(len(h) == 64 for h in hashes))
        # second run with the remembered refusals: no retry, zero writes
        n, r = len(espo.writes), len(espo.requests)
        self.assertEqual(self.run_load("--phone-refusals", os.path.join(first_dir, "phone-refusals.json"),
                                       espo=espo), 0, self.last_err)
        self.assertEqual(espo.writes[n:], [])
        self.assertEqual(self.report()["requests"]["writes"], 0)
        self.assertIn({"object": "Contact", "sfId": fx.C[0], "reason": "phone_refused"}, self.exceptions())
        self.assertTrue(all(m == "GET" for m, _p in espo.requests[r:]))
        # an update refused on the phone keeps the other changes
        espo.by_sf("Contact")[fx.C[0]]["lastName"] = "changed"
        n = len(espo.writes)
        self.run_load(espo=espo)                                          # no memory given: re-probed
        puts = [b for m, e, b in espo.writes[n:] if e == "Contact" and m == "PUT"]
        self.assertIn({"lastName": "L" + SENTINEL}, puts)

    def test_other_400_not_retried(self):
        class Refuse(FakeEspo):
            def send(self, method, path, query=None, body=None, headers=None):
                if method == "POST" and path == "Contact":
                    self.requests.append((method, path))
                    self.headers.append(dict(headers or {}))
                    return 400, {"field": "lastName", "type": "required"}
                return super().send(method, path, query, body, headers)
        espo = Refuse()
        self.assertEqual(self.run_load(espo=espo), 5)
        self.assertEqual(sum(1 for r in espo.requests if r == ("POST", "Contact")), 3)   # one per contact
        self.assertIn({"object": "Contact", "sfId": fx.C[0], "reason": "write_rejected"}, self.exceptions())


class TestManufacturedValues(Base):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.run_load(), 0)
        self.exc = self.exceptions()

    def test_blank_call_type_sends_no_direction(self):
        self.assertNotIn("callDirectionDefault", load_json("mapping.json"))
        posts = {b["sfId"]: b for m, e, b in self.espo.writes if m == "POST" and e == "Call"}
        self.assertNotIn("direction", posts[fx.T[6]])
        self.assertEqual(posts[fx.T[1]]["direction"], "Outbound")
        self.assertIn({"object": "Task", "sfId": fx.T[6], "reason": "call_direction_unknown"}, self.exc)
        self.assertNotIn({"object": "Task", "sfId": fx.T[1], "reason": "call_direction_unknown"}, self.exc)
        self.assertEqual(self.report()["exceptions"]["byReason"]["call_direction_unknown"], 1)

    def test_call_type_maps_exactly(self):
        data = fx.org()
        for t in data["Task"]:
            if t["Id"] == fx.T[1]:
                t["CallType"] = "Internal"
            if t["Id"] == fx.T[6]:
                t["CallType"] = "Inbound"
        snap = write_snapshot(os.path.join(self.tmp, "ct"), data=data)
        espo = FakeEspo()
        self.run_load(snap=snap, espo=espo)
        posts = {b["sfId"]: b for m, e, b in espo.writes if m == "POST" and e == "Call"}
        self.assertEqual(posts[fx.T[6]]["direction"], "Inbound")
        self.assertNotIn("direction", posts[fx.T[1]])
        self.assertIn({"object": "Task", "sfId": fx.T[1], "reason": "enum_unmapped"}, self.exceptions())

    def test_required_date_start_fallbacks_are_coded(self):
        call = self.espo.by_sf("Call")[fx.T[6]]
        self.assertEqual(call["dateStart"], "2025-05-05 00:00:00")          # from ActivityDate
        self.assertIn({"object": "Task", "sfId": fx.T[6], "reason": "date_start_from_activity_date"}, self.exc)
        meet = self.espo.by_sf("Meeting")[fx.E[1]]
        self.assertEqual(meet["dateStart"], "2020-01-02 03:04:05")          # from CreatedDate
        self.assertIn({"object": "Event", "sfId": fx.E[1], "reason": "date_start_from_created"}, self.exc)
        coded = {e["sfId"] for e in self.exc if e["reason"].startswith("date_start_from_")}
        self.assertEqual(coded, {fx.T[6], fx.E[1]})                        # no others

    def test_email_date_sent_never_from_created(self):
        data = fx.org()
        row = dict(next(t for t in data["Task"] if t["Id"] == fx.T[0]), Id=fx.sid("00T", 50), TaskSubtype="Email",
                   CompletedDateTime=None)
        data["Task"].append(row)
        snap = write_snapshot(os.path.join(self.tmp, "em"), data=data)
        espo = FakeEspo()
        # CRM-008: a Task-Email no EmailMessage represents is a Task; give it one here.
        data["EmailMessage"].append(dict(data["EmailMessage"][0], Id=fx.sid("02s", 50),
                                         ActivityId=row["Id"], MessageDate=None))
        snap = write_snapshot(os.path.join(self.tmp, "em2"), data=data)
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        self.assertIsNone(espo.by_sf("Email")[fx.sid("02s", 50)]["dateSent"])


class TestAdvisories(Base):
    def test_value_shape_is_a_coded_exception(self):
        data = fx.org()
        data["Account"][0]["Name"] = {"nested": SENTINEL}
        data["Contact"][1]["Phone"] = ["x"]
        data["Opportunity"][2]["Opportunity_Service__c"] = {"v": 1}
        data["EmailMessageRelation"][0]["RelationId"] = [fx.U1]
        snap = write_snapshot(os.path.join(self.tmp, "shape"), data=data)
        espo = FakeEspo()
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        self.assertNotIn("Traceback", self.last_err)
        exc = self.exceptions()
        for obj, sf in (("Account", fx.A[0]), ("Contact", fx.C[1]), ("Opportunity", fx.O[2]),
                        ("EmailMessageRelation", fx.sid("0EM", 1))):
            self.assertIn({"object": obj, "sfId": sf, "reason": "value_shape"}, exc)
        self.assertNotIn(fx.A[0], espo.by_sf("Account"))
        self.assertIn(fx.A[1], espo.by_sf("Account"))
        self.assertEqual(self.report()["objects"]["Account"]["skipped"]["value_shape"], 1)

    def test_soft_deleted_parent_not_linked_even_if_in_espocrm(self):
        self.espo._insert("Account", {"sfId": fx.A[4], "name": "kept"})      # imported before its deletion
        self.espo._insert("Contact", {"sfId": fx.C[3], "lastName": "kept"})
        self.assertEqual(self.run_load(), 0)
        exc = self.exceptions()
        self.assertIsNone(self.espo.by_sf("Account")[fx.A[3]].get("parentId"))
        self.assertIsNone(self.espo.by_sf("Contact")[fx.C[2]].get("accountId"))
        self.assertIn({"object": "Account", "sfId": fx.A[3], "reason": "parent_soft_deleted_in_sf"}, exc)
        self.assertIn({"object": "Contact", "sfId": fx.C[2], "reason": "parent_soft_deleted_in_sf"}, exc)
        self.assertIn({"object": "OpportunityContactRole", "sfId": fx.sid("00K", 3),
                       "reason": "parent_soft_deleted_in_sf"}, exc)
        kept = self.espo.by_sf("Contact")[fx.C[3]]["id"]
        self.assertNotIn(kept, self.espo.by_sf("Opportunity")[fx.O[1]].get("contactsIds") or [])

    def test_loopback_transport_keeps_only_validation_field(self):
        from crm_load.transport import validation_failure
        body = json.dumps({"messageTranslation": {"label": "validationFailure", "scope": "Contact",
                                                  "data": {"field": "phoneNumber", "type": "valid"}},
                           "extra": SENTINEL}).encode()
        self.assertEqual(validation_failure(body), {"field": "phoneNumber", "type": "valid"})
        for bad in (b"", b"[]", b"{}", json.dumps({"messageTranslation": {"data": {"field": SENTINEL + " x",
                                                                                  "type": "valid"}}}).encode()):
            self.assertIsNone(validation_failure(bad))


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

    def test_loopback_transport_header_allowlist(self):
        t = LoopbackHttpTransport("127.0.0.1", 9, "k")
        for headers in ({"X-Skip-Duplicate-Check": "false"}, {"X-Api-Key": "other"}, {"Host": "example.test"}):
            with self.assertRaises(TransportError):
                t.send("POST", "Account", None, {}, headers)

    def test_loopback_transport_refuses_other_hosts(self):
        for host in ("localhost", "::1", "127.0.0.2", "example.test"):
            with self.assertRaises(TransportError):
                LoopbackHttpTransport(host, 8080, "k")
        with self.assertRaises(TransportError):
            LoopbackHttpTransport("127.0.0.1", 8080, "")
        t = LoopbackHttpTransport("127.0.0.1", 8080, "k")
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

    def test_user_name_collision_exports_neither(self):
        # The Username rule applies to a real snapshot (a selftest one derives names from sfIds).
        data = fx.org(account_marker=False)
        u1 = next(u for u in data["User"] if u["Id"] == fx.U1)
        u2 = next(u for u in data["User"] if u["Id"] == fx.U2)
        u2["Username"] = "U1@other.example.test"               # same local part, other domain/case
        snap = write_snapshot(os.path.join(self.tmp, "coll"), data=data, synthetic=False)
        rm = os.path.join(self.tmp, "rm.json")
        with open(rm, "w") as fh:
            json.dump({"profiles": {}, "userRoles": {}}, fh)
        out = os.path.join(self.tmp, "uc")
        self.assertEqual(cli.main(["users", snap, "--role-map", rm, "--out", out], stderr=io.StringIO(),
                                  stdout=io.StringIO()), 0)
        with open(os.path.join(out, "users.json")) as fh:
            ids = {u["sfId"] for u in json.load(fh)}
        self.assertFalse({u1["Id"], u2["Id"]} & ids)
        self.assertIn(fx.U_INACTIVE, ids)
        with open(os.path.join(out, "exceptions.jsonl")) as fh:
            exc = [json.loads(line) for line in fh]
        for sf in (fx.U1, fx.U2):
            self.assertIn({"object": "User", "sfId": sf, "reason": "user_not_exportable"}, exc)

    def test_example_role_map_has_placeholders_only(self):
        with open(os.path.join(ROOT, "load", "examples", "role-map.example.json")) as fh:
            doc = json.load(fh)
        for section in ("profiles", "userRoles"):
            for name in doc[section]:
                self.assertRegex(name, r"\A<.*>\Z")


class TestFidelity(Base):
    """CRM-006S: blanks are never server defaults, compared as stored, phone precondition, users."""

    def _blanks(self):
        data = fx.org()
        a0 = data["Account"][0]
        a0["TLP__c"] = None                                  # learningPlatformAccess default No
        a0["Name"] = "  " + a0["Name"] + "  "                # varchar: trimmed by the server
        a0["Description"] = "  padded text  "                # text: stored verbatim
        a0["Website"] = "   "                                # blank-ish varchar
        data["Opportunity"][1]["Opportunity_Service__c"] = "  Service Y  "   # same type as "Service Y"
        data["Opportunity"][0]["Description"] = None
        for t in data["Task"]:
            t["CallDurationInSeconds"] = None
        return data

    def test_run2_zero_writes_with_server_defaults_trim_and_refused_phone(self):
        class RefuseOffice(FakeEspo):
            def _phone(self, number):
                if isinstance(number, str) and number.startswith("01632 9601"):
                    return number, True
                return super()._phone(number)
        espo = RefuseOffice()
        snap = write_snapshot(os.path.join(self.tmp, "blank"), data=self._blanks())
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        first = self.last_dir
        acc = espo.by_sf("Account")[fx.A[0]]
        self.assertIsNone(acc["learningPlatformAccess"])            # never the default No
        self.assertEqual(acc["description"], "  padded text  ")
        self.assertFalse(acc["name"].startswith(" "))
        self.assertEqual(len(espo.db["ServiceType"]), 2)            # padded value: no duplicate type
        self.assertFalse(any(v.startswith(" ") for v in (r["sfValue"] for r in espo.db["ServiceType"].values())))
        for call in espo.by_sf("Call").values():
            self.assertEqual(call["duration"], 0)                    # sent null, stored 0, never 300
        self.assertTrue(all("duration" in b for m, e, b in espo.writes if m == "POST" and e == "Call"))
        exc = self.exceptions()
        self.assertTrue(any(e["reason"] == "call_duration_unknown" for e in exc))
        n = len(espo.writes)
        self.assertEqual(self.run_load("--phone-refusals", os.path.join(first, "phone-refusals.json"),
                                       snap=snap, espo=espo), 0, self.last_err)
        self.assertEqual(espo.writes[n:], [])
        self.assertEqual(self.report()["requests"]["writes"], 0)

    def test_omitted_blank_would_store_the_default(self):
        """The fake models the server: an omitted enum is the default, an explicit null refused."""
        f = FakeEspo()
        _st, doc = f.send("POST", "Account", body={"sfId": "a", "name": "a"})
        self.assertEqual(f.db["Account"][doc["id"]]["learningPlatformAccess"], "No")
        self.assertEqual(f.send("POST", "Opportunity", body={"sfId": "o", "stage": None})[0], 400)
        self.assertEqual(f.send("POST", "Opportunity", body={"sfId": "o", "stage": ""})[0], 400)
        _st, doc = f.send("POST", "Call", body={"sfId": "c", "dateStart": "2025-01-01 00:00:00", "assignedUserId": "u"})
        self.assertEqual(f.db["Call"][doc["id"]]["duration"], 300)
        _st, doc = f.send("POST", "Call", body={"sfId": "d", "dateStart": "2025-01-01 00:00:00", "duration": None,
                                                "assignedUserId": "u"})
        self.assertEqual(f.db["Call"][doc["id"]]["duration"], 0)
        _st, doc = f.send("POST", "Account", body={"sfId": "b", "name": " n ", "description": " d "})
        self.assertEqual((f.db["Account"][doc["id"]]["name"], f.db["Account"][doc["id"]]["description"]),
                         ("n", " d "))
        _st, doc = f.send("POST", "Meeting", body={"sfId": "m", "dateStart": "2025-01-01 00:00:00",
                                                   "meetingType": None, "assignedUserId": "u"})
        self.assertIsNone(f.db["Meeting"][doc["id"]]["meetingType"])

    def test_blank_enum_without_blank_option_is_refused(self):
        data = fx.org()
        data["Task"][0]["Status"] = None
        snap = write_snapshot(os.path.join(self.tmp, "eb"), data=data)
        self.assertEqual(self.run_load(snap=snap), 0, self.last_err)
        self.assertIn({"object": "Task", "sfId": fx.T[0], "reason": "enum_blank_unrepresentable"},
                      self.exceptions())
        self.assertNotIn(fx.T[0], self.espo.by_sf("Task"))
        self.assertFalse([b for _m, _e, b in self.espo.writes if b.get("sfId") == fx.T[0]])

    def test_every_blankable_enum_target_has_a_blank_option(self):
        """A2 guard: a mapped enum target that can receive a blank source value has "" in its
        options, or is listed in enumNoBlank (refused) or nullAccepted (PL-verified)."""
        mapping = load_json("mapping.json")
        refused = set(mapping["enumNoBlank"]["attributes"])
        null_ok = set(mapping["enumNoBlank"]["nullAccepted"])
        core = set(mapping["coreEnums"]["attributes"])
        blankable = {f"{e}.{a}" for e, spec in mapping["entities"].items() for a in spec.get("enum", {})}
        blankable |= {"Opportunity.lossReason", "Opportunity.channel", "Meeting.meetingType"}
        for key in sorted(blankable):
            entity, field = key.split(".")
            if key in core:
                options = CORE_ENUM_OPTIONS[key]
            else:
                with open(os.path.join(ENTITY_DEFS, f"{entity}.json")) as fh:
                    options = json.load(fh)["fields"][field]["options"]
            self.assertTrue("" in options or key in refused or key in null_ok, key)
            if key in mapping["enums"]:
                self.assertEqual(mapping["enums"][key], options, key)
        self.assertIn("Opportunity.stage", refused)

    def _beta(self, espo):
        real = write_snapshot(os.path.join(self.tmp, f"real{self._n}"), synthetic=False)
        return self.run_load(snap=real, target="beta", espo=espo)

    def test_beta_requires_phone_international_false(self):
        for settings in ({"phoneNumberInternational": True}, {}, {"phoneNumberInternational": None},
                         {"phoneNumberInternational": "false"}, FakeEspo.SETTINGS_REFUSED):
            espo = FakeEspo(settings=settings)
            self.assertEqual(self._beta(espo), 3, settings)
            self.assertIn("code=phone_international_enabled", self.last_err)
            self.assertEqual(espo.writes, [])
        espo = FakeEspo(settings={"phoneNumberInternational": False})
        self.assertEqual(self._beta(espo), 0, self.last_err)
        self.assertIn(("GET", "Settings"), espo.requests)
        self.assertEqual(espo.requests.index(("GET", "Settings")),
                         min(i for i, r in enumerate(espo.requests) if r[0] == "GET"))

    def test_dev_reports_the_setting_and_continues(self):
        espo = FakeEspo(settings={"phoneNumberInternational": True})
        self.assertEqual(self.run_load(espo=espo), 0, self.last_err)
        self.assertIn("event=settings phoneNumberInternational=true", self.last_err)
        espo = FakeEspo(settings=FakeEspo.SETTINGS_REFUSED)
        self.assertEqual(self.run_load(espo=espo), 0, self.last_err)
        self.assertIn("phoneNumberInternational=unknown", self.last_err)

    def test_phone_refusals_file_is_validated(self):
        bad = os.path.join(self.tmp, "bad.json")
        with open(bad, "w") as fh:
            json.dump(["01632 960100"], fh)
        self.assertEqual(self.run_load("--phone-refusals", bad), 2)
        self.assertIn("code=phone_refusals_invalid", self.last_err)

    def _users(self, snap):
        rm = os.path.join(self.tmp, f"rm{self._n}.json")
        with open(rm, "w") as fh:
            json.dump({"profiles": {}, "userRoles": {}}, fh)
        self._n += 1
        out = os.path.join(self.tmp, f"users{self._n}")
        self.assertEqual(cli.main(["users", snap, "--role-map", rm, "--out", out], stderr=io.StringIO(),
                                  stdout=io.StringIO()), 0)
        with open(os.path.join(out, "users.json")) as fh:
            return {u["sfId"] for u in json.load(fh)}

    def test_synthetic_user_types_only_in_selftest(self):
        def with_value_a(data):
            for u in data["User"]:
                if u["Id"] == fx.U1:
                    u["UserType"] = "Value A"
            return data
        syn = write_snapshot(os.path.join(self.tmp, "su"), data=with_value_a(fx.org(account_marker=True)))
        real = write_snapshot(os.path.join(self.tmp, "ru"), data=with_value_a(fx.org(account_marker=False)),
                              synthetic=False)
        self.assertIn(fx.U1, self._users(syn))
        self.assertNotIn(fx.U1, self._users(real))
        self.assertNotIn(fx.U_AUTOMATED, self._users(syn))          # AutomatedProcess never
        self.assertEqual(self.run_load(snap=syn), 0, self.last_err)
        self.assertEqual(self.report()["objects"]["User"]["skipped"]["user_not_human"], 1)
        espo = FakeEspo()
        self.assertEqual(self.run_load(snap=real, target="beta", espo=espo), 0, self.last_err)
        self.assertEqual(self.report()["objects"]["User"]["skipped"]["user_not_human"], 2)


class TestRound2(Base):
    """CRM-006S round 2: selftest users, trimmed phones, salutation, synthetic enums, refusal file."""

    @staticmethod
    def _selftest_users(data):
        """The real ``crm-migrate selftest`` User shape: "<marker> User Username <n>", Value A|B|C."""
        for i, u in enumerate(data["User"]):
            u["Username"] = f"{SENTINEL} User Username {i}"
            if u["UserType"] == "Standard":
                u["UserType"] = ("Value A", "Value B", "Value C")[i % 3]
        return data

    def _users_json(self, snap):
        rm = os.path.join(self.tmp, "rm.json")
        with open(rm, "w") as fh:
            json.dump({"profiles": {}, "userRoles": {}}, fh)
        self._n += 1
        out = os.path.join(self.tmp, f"users{self._n}")
        self.assertEqual(cli.main(["users", snap, "--role-map", rm, "--out", out], stderr=io.StringIO(),
                                  stdout=io.StringIO()), 0)
        with open(os.path.join(out, "users.json")) as fh:
            users = json.load(fh)
        with open(os.path.join(out, "exceptions.jsonl")) as fh:
            exc = [json.loads(line) for line in fh if line.strip()]
        return users, exc

    def test_selftest_usernames_resolve_owners(self):
        import hashlib
        from crm_load.users import USER_NAME
        snap = write_snapshot(os.path.join(self.tmp, "stu"), data=self._selftest_users(fx.org()))
        users, exc = self._users_json(snap)
        humans = {fx.U1, fx.U2, fx.U_INACTIVE, fx.U_SHARED}
        self.assertEqual({u["sfId"] for u in users}, humans)
        self.assertEqual(exc, [])                                       # no user_not_exportable
        for u in users:
            self.assertEqual(u["userName"], "syn-" + hashlib.sha256(u["sfId"].encode()).hexdigest()[:10])
            self.assertRegex(u["userName"], USER_NAME)
            self.assertNotIn(SENTINEL, u["userName"])
        # provisioned exactly as exported: owners who are synthetic users resolve
        espo = FakeEspo(users=sorted(u["sfId"] for u in users))
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        owners = {}
        for obj in ("Account", "Contact", "Opportunity", "Task", "Event"):
            for r in fx.org()[obj]:
                owners[r["Id"]] = r.get("OwnerId")
        unresolved = [e["sfId"] for e in self.exceptions() if e["reason"] == "owner_unresolved"]
        self.assertEqual([i for i in unresolved if owners.get(i) in humans], [])
        self.assertTrue(unresolved)                                     # U_MISSING / automated still coded
        self.assertEqual(espo.by_sf("Account")[fx.A[0]]["assignedUserId"],
                         next(r["id"] for r in espo.db["User"].values() if r["sfId"] == fx.U1))

    def test_real_snapshot_keeps_the_username_rule(self):
        data = self._selftest_users(fx.org(account_marker=False))
        for u in data["User"]:
            if u["UserType"].startswith("Value"):
                u["UserType"] = "Standard"
        real = write_snapshot(os.path.join(self.tmp, "rsu"), data=data, synthetic=False)
        users, exc = self._users_json(real)
        self.assertEqual(users, [])                                     # space, no "@": not exportable
        self.assertEqual({e["reason"] for e in exc}, {"user_not_exportable"})
        self.assertEqual(len(exc), 4)

    def test_padded_phones_compare_trimmed_and_hash_trimmed(self):
        class RefuseC2(FakeEspo):
            refuse = False

            def _phone(self, number):
                if self.refuse and isinstance(number, str) and number.strip() == "01632 960102":
                    return number, True
                return super()._phone(number)
        data = fx.org()
        for c in data["Contact"]:
            if isinstance(c.get("Phone"), str):
                c["Phone"] = "  " + c["Phone"] + "  "
        snap = write_snapshot(os.path.join(self.tmp, "pad"), data=data)
        espo = RefuseC2()
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        self.assertEqual(espo.by_sf("Contact")[fx.C[0]]["phoneNumberData"][0]["phoneNumber"], "01632 960100")
        n = len(espo.writes)
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        self.assertEqual(espo.writes[n:], [])                           # trimmed on save == padded source
        # refusal memory: refused while padded, remembered for the same number unpadded
        espo = RefuseC2()
        espo.refuse = True
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        memory = os.path.join(self.last_dir, "phone-refusals.json")
        unpadded = write_snapshot(os.path.join(self.tmp, "unpad"), data=fx.org())
        n = len(espo.writes)
        self.assertEqual(self.run_load("--phone-refusals", memory, snap=unpadded, espo=espo), 0, self.last_err)
        self.assertFalse([b for _m, e, b in espo.writes[n:] if e == "Contact" and "phoneNumberData" in b
                          and any(p["phoneNumber"].strip() == "01632 960102" for p in b["phoneNumberData"])])
        self.assertIn({"object": "Contact", "sfId": fx.C[2], "reason": "phone_refused"}, self.exceptions())

    def test_salutation_routed_through_enum(self):
        data = fx.org()
        data["Contact"][1]["Salutation"] = "Prof." + SENTINEL
        snap = write_snapshot(os.path.join(self.tmp, "sal"), data=data)
        self.assertEqual(self.run_load(snap=snap), 0, self.last_err)
        posts = {b["sfId"]: b for m, e, b in self.espo.writes if m == "POST" and e == "Contact"}
        self.assertIn("salutationName", posts[fx.C[1]])
        self.assertIsNone(posts[fx.C[1]]["salutationName"])             # null sent, not omitted
        self.assertEqual(posts[fx.C[0]]["salutationName"], "Mr.")
        exc = self.exceptions()
        self.assertIn({"object": "Contact", "sfId": fx.C[1], "reason": "enum_unmapped"}, exc)
        self.assertNotIn({"object": "Contact", "sfId": fx.C[0], "reason": "enum_unmapped"}, exc)
        self.assertNotIn("write_rejected", self.report()["exceptions"]["byReason"])
        # the fake refuses an unlisted salutation exactly as crm-dev does (400 valid)
        self.assertEqual(FakeEspo().send("POST", "Contact", body={"sfId": "x", "salutationName": "Prof."}),
                         (400, {"field": "salutationName", "type": "valid"}))

    @staticmethod
    def _synthetic_values(data):
        for o in data["Opportunity"]:
            o["StageName"] = "Value A"
        tasks = {t["Id"]: t for t in data["Task"]}
        tasks[fx.T[0]].update(Status="Value B", Priority="Value C")
        tasks[fx.T[5]].update(Status="Value A", Priority="Value A")
        tasks[fx.T[1]].update(TaskSubtype="Value B", CallType="Value A")      # -> Call, Inbound
        return data

    def test_synthetic_enum_map_on_selftest(self):
        snap = write_snapshot(os.path.join(self.tmp, "sem"), data=self._synthetic_values(fx.org()))
        self.assertEqual(self.run_load(snap=snap), 0, self.last_err)
        opp = self.espo.by_sf("Opportunity")
        self.assertEqual(opp[fx.O[0]]["stage"], "Enquiry")
        self.assertEqual(len(opp), 6)                                   # every current one created
        t0 = self.espo.by_sf("Task")[fx.T[0]]
        self.assertEqual((t0["status"], t0["priority"]), ("Started", "High"))
        self.assertEqual(self.espo.by_sf("Call")[fx.T[1]]["direction"], "Inbound")
        self.assertTrue(opp[fx.O[0]]["contactsIds"])                    # contact-role path reached
        rep = self.report()
        self.assertEqual(rep["exceptions"]["byReason"]["synthetic_enum_mapped"], 6 + 3)
        self.assertNotIn("enum_blank_unrepresentable", rep["exceptions"]["byReason"])
        n = len(self.espo.writes)
        self.assertEqual(self.run_load(snap=snap), 0, self.last_err)
        self.assertEqual(self.espo.writes[n:], [])

    def _beta_exceptions(self, contract_dir):
        data = self._synthetic_values(fx.org(account_marker=False))
        self._n += 1
        real = write_snapshot(os.path.join(self.tmp, f"semr{self._n}"), data=data, synthetic=False)
        espo, out = FakeEspo(), os.path.join(self.tmp, f"bout{self._n}")
        rc = cli.main(["load", real, "--target", "beta", "--out", out], transport=espo, stderr=io.StringIO(),
                      stdout=io.StringIO(), sleep=lambda s: None, contract_dir=contract_dir)
        self.assertEqual(rc, 0)
        return self.exceptions(out), espo

    def test_real_snapshot_never_consults_the_synthetic_map(self):
        self.assertIn("syntheticEnumMap", load_json("mapping.json"))
        with_map, espo = self._beta_exceptions(None)
        reasons = {e["reason"] for e in with_map}
        self.assertNotIn("synthetic_enum_mapped", reasons)
        self.assertIn({"object": "Opportunity", "sfId": fx.O[0], "reason": "enum_blank_unrepresentable"}, with_map)
        self.assertIn({"object": "Task", "sfId": fx.T[0], "reason": "enum_blank_unrepresentable"}, with_map)
        self.assertIn({"object": "Task", "sfId": fx.T[0], "reason": "enum_unmapped"}, with_map)
        self.assertEqual(espo.by_sf("Opportunity"), {})
        self.assertNotIn(fx.T[1], espo.by_sf("Call"))                   # TaskSubtype "Value B" stays a Task
        # exactly as before: identical exceptions with the map removed from the contract
        nomap = os.path.join(self.tmp, "contract-nomap")
        shutil.copytree(os.path.join(ROOT, "load", "contract"), nomap)
        doc = load_json("mapping.json", nomap)
        del doc["syntheticEnumMap"]
        with open(os.path.join(nomap, "mapping.json"), "w") as fh:
            json.dump(doc, fh)
        without_map, _ = self._beta_exceptions(nomap)
        self.assertEqual(with_map, without_map)

    def test_unmapped_call_type_is_direction_unknown(self):
        data = fx.org()
        for t in data["Task"]:
            if t["Id"] == fx.T[1]:
                t["CallType"] = "Internal"
        snap = write_snapshot(os.path.join(self.tmp, "uct"), data=data)
        self.assertEqual(self.run_load(snap=snap), 0, self.last_err)
        posts = {b["sfId"]: b for m, e, b in self.espo.writes if m == "POST" and e == "Call"}
        self.assertNotIn("direction", posts[fx.T[1]])
        exc = self.exceptions()
        for code in ("call_direction_unknown", "enum_unmapped"):
            self.assertIn({"object": "Task", "sfId": fx.T[1], "reason": code}, exc)

    def _memory(self, mode=0o600):
        path = os.path.join(self.tmp, f"mem{self._n}.json")
        with open(path, "w") as fh:
            fh.write("[]\n")
        os.chmod(path, mode)
        return path

    def test_phone_refusals_file_must_be_sealed(self):
        from unittest import mock
        good = self._memory()
        self.assertEqual(self.run_load("--phone-refusals", good), 0, self.last_err)
        self.assertEqual(self.report()["phoneRefusals"]["supplied"], True)
        self.assertIn("event=phone_refusals remembered=0 supplied=true", self.last_err)
        self.assertEqual(self.run_load(), 0, self.last_err)
        self.assertEqual(self.report()["phoneRefusals"]["supplied"], False)
        link = os.path.join(self.tmp, "link.json")
        os.symlink(good, link)
        cases = [(link, "phone_refusals_unreadable"), (self._memory(0o644), "phone_refusals_not_sealed"),
                 (self.tmp, "phone_refusals_not_sealed")]
        for path, code in cases:
            with self.subTest(path=path):
                self.assertEqual(self.run_load("--phone-refusals", path), 2)
                self.assertIn(f"code={code}", self.last_err)
        with mock.patch.object(cli, "_refusals_owner", return_value=os.geteuid() + 1):
            self.assertEqual(self.run_load("--phone-refusals", good), 2)
        self.assertIn("code=phone_refusals_not_sealed", self.last_err)

    def test_update_with_every_phone_probe_refused_is_unchanged(self):
        class Toggle(FakeEspo):
            refuse = False

            def _phone(self, number):
                if self.refuse and number == "01632 960102":
                    return number, True
                return super()._phone(number)
        espo = Toggle()
        self.assertEqual(self.run_load(espo=espo), 0, self.last_err)
        espo.refuse = True
        espo.by_sf("Contact")[fx.C[2]].update(phoneNumberData=[], phoneNumber=None)   # only its refused number differs
        n = len(espo.writes)
        self.assertEqual(self.run_load(espo=espo), 0, self.last_err)
        self.assertTrue(espo.writes[n:])                                # attempted (and refused)
        self.assertEqual(self.report()["objects"]["Contact"]["targets"]["Contact"],
                         {"created": 0, "updated": 0, "unchanged": 3, "failed": 0})
        self.assertIn({"object": "Contact", "sfId": fx.C[2], "reason": "phone_refused"}, self.exceptions())

    def test_text_attributes_are_not_trimmed_before_comparison(self):
        """M10: a text attribute is compared verbatim, so a trimmed copy in EspoCRM is restored."""
        from crm_load.engine import same_value
        self.assertFalse(same_value("description", "  x  ", "x", text=True))
        self.assertTrue(same_value("name", "  x  ", "x", text=False))
        data = fx.org()
        data["Account"][0]["Description"] = "  padded " + SENTINEL + "  "
        snap = write_snapshot(os.path.join(self.tmp, "txt"), data=data)
        self.assertEqual(self.run_load(snap=snap), 0, self.last_err)
        acc = self.espo.by_sf("Account")[fx.A[0]]
        acc["description"] = acc["description"].strip()
        n = len(self.espo.writes)
        self.assertEqual(self.run_load(snap=snap), 0, self.last_err)
        self.assertIn(("PUT", "Account", {"description": "  padded " + SENTINEL + "  "}), self.espo.writes[n:])


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
                  "users", "fromString", "assignedUser"},
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
        self.assertEqual({k: mapping["enums"][k] for k in mapping["coreEnums"]["attributes"]}, CORE_ENUM_OPTIONS)
        for key, options in mapping["enums"].items():
            entity, field = key.split(".")
            if key in CORE_ENUM_OPTIONS:
                continue
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


class TestCrm008(Base):
    """CRM-008 changes 3 to 7 (all data synthetic)."""

    def load(self, data, name):
        snap = write_snapshot(os.path.join(self.tmp, name), data=data)
        espo = FakeEspo()
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        # The fake refuses what 10.0.12 refuses: nothing the loader sends is refused.
        self.assertNotIn("write_rejected", self.report()["exceptions"]["byReason"])
        return snap, espo

    def codes(self, sf_id):
        return {e["reason"] for e in self.exceptions() if e["sfId"] == sf_id}

    def test_required_owner_refuses_task_call_and_meeting_only(self):
        data = fx.org()
        data["Task"][0]["OwnerId"] = fx.U_MISSING          # Task
        data["Task"][1]["OwnerId"] = fx.QUEUE              # Call, owned by a queue
        data["Event"][0]["OwnerId"] = None                 # Meeting
        data["Account"][0]["OwnerId"] = fx.U_MISSING       # Account: still created
        _, espo = self.load(data, "own")
        self.assertNotIn(fx.T[0], espo.by_sf("Task"))
        self.assertNotIn(fx.T[1], espo.by_sf("Call"))
        self.assertNotIn(fx.E[0], espo.by_sf("Meeting"))
        self.assertIn(fx.A[0], espo.by_sf("Account"))
        self.assertIsNone(espo.by_sf("Account")[fx.A[0]]["assignedUserId"])
        for sf_id in (fx.T[0], fx.T[1], fx.E[0]):
            self.assertIn("owner_required_unresolved", self.codes(sf_id), sf_id)
            self.assertNotIn("owner_unresolved", self.codes(sf_id), sf_id)
        self.assertIn("owner_queue_or_group", self.codes(fx.T[1]))
        self.assertEqual(self.codes(fx.A[0]) & {"owner_unresolved", "owner_required_unresolved"},
                         {"owner_unresolved"})
        rep = self.report()
        self.assertEqual(rep["objects"]["Task"]["skipped"]["owner_required_unresolved"], 2)
        self.assertEqual(rep["objects"]["Event"]["skipped"]["owner_required_unresolved"], 1)
        self.assertNotIn("write_rejected", rep["exceptions"]["byReason"])

    def test_task_email_without_email_message_is_a_task(self):
        data = fx.org()
        data["EmailMessage"][1]["ActivityId"] = None       # T[2] loses its EmailMessage
        _, espo = self.load(data, "te")
        task = espo.by_sf("Task")[fx.T[2]]
        src = data["Task"][2]
        self.assertEqual((task["name"], task["description"], task["status"], task["dateEndDate"]),
                         (src["Subject"], src["Description"], "Completed", src["ActivityDate"]))
        self.assertNotIn(fx.T[2], espo.by_sf("Email"))
        self.assertIn("task_email_imported_as_task", self.codes(fx.T[2]))
        # T[3] still has its EmailMessage: represented by it, not imported from the Task.
        self.assertNotIn(fx.T[3], espo.by_sf("Task"))
        self.assertNotIn(fx.T[3], espo.by_sf("Email"))
        self.assertEqual(self.report()["objects"]["Task"]["skipped"]["represented_by_email_message"], 1)

    def test_task_email_keeps_its_parent(self):
        data = fx.org()
        data["EmailMessage"][0]["ActivityId"] = None       # T[3] (parent O[0])
        _, espo = self.load(data, "tp")
        task = espo.by_sf("Task")[fx.T[3]]
        self.assertEqual(task["parentType"], "Opportunity")
        self.assertEqual(task["parentId"], espo.by_sf("Opportunity")[fx.O[0]]["id"])

    def test_over_length_values_are_null_with_the_attribute_name_never_truncated(self):
        data = fx.org()
        data["Contact"][0]["MailingPostalCode"] = "P" * 41
        data["Contact"][0]["Title"] = "T" * 255            # fits the raised limit
        data["Contact"][1]["Title"] = "T" * 256
        data["Contact"][0]["Phone"] = "0" * 37
        data["Account"][2]["ShippingCity"] = "B" * 101
        data["Account"][1]["Phone"] = "1" * 37
        _, espo = self.load(data, "len")
        c0 = espo.by_sf("Contact")[fx.C[0]]
        self.assertIsNone(c0["addressPostalCode"])
        self.assertEqual(c0["title"], "T" * 255)
        self.assertIsNone(espo.by_sf("Contact")[fx.C[1]]["title"])
        self.assertIsNone(espo.by_sf("Account")[fx.A[2]]["billingAddressCity"])
        self.assertIsNone(espo.by_sf("Account")[fx.A[1]]["phoneNumber"])
        self.assertFalse([p for p in c0.get("phoneNumberData") or [] if len(p["phoneNumber"]) > 36])
        lines = [e for e in self.exceptions() if e["reason"] == "value_too_long"]
        self.assertEqual({(e["sfId"], tuple(e["attributes"])) for e in lines},
                         {(fx.C[0], ("Contact.addressPostalCode",)), (fx.C[1], ("Contact.title",)),
                          (fx.A[2], ("Account.billingAddressCity",))})
        # Not required: the record is still written, so nothing is skipped.
        self.assertEqual({o: v["skipped"]["value_too_long"] for o, v in self.report()["objects"].items()
                          if v["skipped"]["value_too_long"]}, {})
        self.assertIn("phone_rejected", self.codes(fx.C[0]))
        self.assertIn("phone_rejected", self.codes(fx.A[1]))
        with open(os.path.join(self.last_dir, "exceptions.jsonl")) as fh:
            raw = fh.read()
        self.assertNotIn("P" * 41, raw)
        self.assertNotIn("B" * 101, raw)

    def test_over_length_required_name_refuses_the_record(self):
        data = fx.org()
        data["Account"][0]["Name"] = "N" * 250                       # Account.name 249, required
        for r in data["Opportunity"]:
            if r.get("Opportunity_Service__c") == "Service X":
                r["Opportunity_Service__c"] = "S" * 151              # ServiceType.name 150, required
        data["Opportunity"][0]["LeadSource"] = "L" * 101             # Opportunity.sfLeadSource: not required
        _, espo = self.load(data, "req")
        self.assertNotIn(fx.A[0], espo.by_sf("Account"))
        self.assertFalse([w for w in espo.writes if w[1] == "Account" and w[2].get("sfId") == fx.A[0]])
        self.assertEqual(sorted(r["name"] for r in espo.db["ServiceType"].values()), ["Service Y"])
        self.assertFalse([w for w in espo.writes if w[1] == "ServiceType" and w[2].get("name") is None])
        o0 = espo.by_sf("Opportunity")[fx.O[0]]                      # the Opportunity is still written
        self.assertIsNone(o0["serviceTypeId"])
        self.assertIsNone(o0["sfLeadSource"])
        self.assertEqual(o0["name"], data["Opportunity"][0]["Name"])
        lines = {(e["object"], e["sfId"]): e["attributes"] for e in self.exceptions()
                 if e["reason"] == "value_too_long"}
        # Qualified names: O[0] carries the ServiceType it first named, never a long Opportunity name.
        self.assertEqual(lines, {("Account", fx.A[0]): ["Account.name"],
                                 ("Opportunity", fx.O[0]): ["Opportunity.sfLeadSource", "ServiceType.name"]})
        rep = self.report()
        self.assertEqual(rep["objects"]["Account"]["skipped"]["value_too_long"], 1)
        self.assertEqual(rep["objects"]["Opportunity"]["skipped"]["value_too_long"], 1)   # the ServiceType
        self.assertNotIn("N" * 250, json.dumps(self.exceptions()))

    def test_over_length_required_name_refuses_an_update_and_keeps_the_stored_name(self):
        snap, espo = self.load(fx.org(), "u1")
        before = espo.by_sf("Account")[fx.A[0]]["name"]
        data = fx.org()
        data["Account"][0]["Name"] = "N" * 250
        data["Account"][0]["ShippingCity"] = "B" * 101
        snap2 = write_snapshot(os.path.join(self.tmp, "u2"), data=data)
        n = len(espo.writes)
        self.assertEqual(self.run_load(snap=snap2, espo=espo), 0, self.last_err)
        self.assertEqual(espo.by_sf("Account")[fx.A[0]]["name"], before)
        self.assertFalse([w for w in espo.writes[n:] if w[1] == "Account"
                          and w[2].get("name", before) != before])
        self.assertEqual(self.report()["objects"]["Account"]["skipped"]["value_too_long"], 1)

    def test_refused_existing_account_gets_no_write_in_any_pass(self):
        # Auditor probe (round 4): an existing Account re-loaded with Name of 250 characters,
        # a changed ParentId and a changed city.
        snap, espo = self.load(fx.org(), "p1")
        acc = espo.by_sf("Account")[fx.A[2]]
        before = dict(acc)
        data = fx.org()
        data["Account"][2]["Name"] = "N" * 250
        data["Account"][2]["ParentId"] = fx.A[0]                     # was A[1]
        data["Account"][2]["BillingCity"] = "Elsewhere"
        data["Account"][2]["ShippingCity"] = "Elsewhere"
        n_req = len(espo.requests)
        self.assertEqual(self.run_load(snap=write_snapshot(os.path.join(self.tmp, "p2"), data=data),
                                       espo=espo), 0, self.last_err)
        self.assertEqual([r for r in espo.requests[n_req:] if r[0] != "GET"], [])
        self.assertEqual(espo.by_sf("Account")[fx.A[2]], before)
        acc_rep = self.report()["objects"]["Account"]
        self.assertEqual(acc_rep["skipped"]["value_too_long"], 1)
        self.assertEqual(acc_rep["targets"]["Account"]["updated"], 0)
        self.assertEqual(acc_rep.get("second_pass", {}).get("updated", 0), 0)
        self.assertIn("value_too_long", self.codes(fx.A[2]))

    def test_refused_existing_opportunity_gets_no_contact_role_write(self):
        snap, espo = self.load(fx.org(), "r1")
        before = dict(espo.by_sf("Opportunity")[fx.O[0]])
        data = fx.org()
        data["Opportunity"][0]["StageName"] = None                   # Opportunity.stage: refused
        data["OpportunityContactRole"][1]["ContactId"] = fx.C[2]    # O[0] gains a role contact
        n_req = len(espo.requests)
        self.assertEqual(self.run_load(snap=write_snapshot(os.path.join(self.tmp, "r2"), data=data),
                                       espo=espo), 0, self.last_err)
        self.assertEqual([r for r in espo.requests[n_req:] if r[0] != "GET"], [])
        self.assertEqual(espo.by_sf("Opportunity")[fx.O[0]], before)
        rep = self.report()["objects"]
        self.assertEqual(rep["Opportunity"]["skipped"]["enum_blank_unrepresentable"], 2)   # O[0], O[5]
        self.assertEqual(rep["OpportunityContactRole"]["targets"].get("Opportunity", {}).get("updated", 0), 0)

    def test_refused_service_type_marks_every_opportunity_naming_it(self):
        data = fx.org()
        named = []
        for r in data["Opportunity"]:
            if r.get("Opportunity_Service__c") == "Service X":
                r["Opportunity_Service__c"] = "S" * 151
                if r.get("IsDeleted") is not True:
                    named.append(r["Id"])
        data["Opportunity"][5]["Opportunity_Service__c"] = " " + "S" * 151      # padded: same value
        named.append(data["Opportunity"][5]["Id"])
        self.assertGreater(len(named), 2)
        _, espo = self.load(data, "st")
        lines = [e for e in self.exceptions() if e["reason"] == "service_type_refused"]
        self.assertEqual(sorted(e["sfId"] for e in lines), sorted(named))
        self.assertEqual({e["object"] for e in lines}, {"Opportunity"})
        self.assertFalse([e for e in lines if set(e) - {"object", "sfId", "reason"}])     # id only
        opps = espo.by_sf("Opportunity")
        for sf_id in named:
            if sf_id in opps:
                self.assertIsNone(opps[sf_id]["serviceTypeId"], sf_id)
        # An Opportunity naming an accepted ServiceType gets no such code.
        y = [r["Id"] for r in data["Opportunity"] if r.get("Opportunity_Service__c") == "Service Y"]
        self.assertTrue(y)
        for sf_id in y:
            self.assertNotIn("service_type_refused", self.codes(sf_id))
            self.assertIsNotNone(opps[sf_id]["serviceTypeId"])
        self.assertEqual(self.report()["objects"]["Opportunity"]["exceptions"]["service_type_refused"], len(named))
        self.assertNotIn("S" * 151, json.dumps(self.exceptions()))

    def test_over_length_optional_value_clears_the_field_on_update(self):
        snap, espo = self.load(fx.org(), "c1")
        self.assertIsNotNone(espo.by_sf("Account")[fx.A[0]]["billingAddressCity"])
        data = fx.org()
        data["Account"][0]["ShippingCity"] = "B" * 101
        self.assertEqual(self.run_load(snap=write_snapshot(os.path.join(self.tmp, "c2"), data=data),
                                       espo=espo), 0, self.last_err)
        self.assertIsNone(espo.by_sf("Account")[fx.A[0]]["billingAddressCity"])
        self.assertIn("value_too_long", self.codes(fx.A[0]))

    def test_unresolved_owner_on_contact_opportunity_and_email_is_still_written(self):
        data = fx.org()
        data["Contact"][0]["OwnerId"] = fx.U_MISSING
        data["Opportunity"][0]["OwnerId"] = fx.U_MISSING
        # T[2] is a Task-Email an earlier run created as an Email; it is updated as an Email.
        data["Task"][2]["OwnerId"] = fx.U_MISSING
        data["EmailMessage"][1]["ActivityId"] = None
        snap = write_snapshot(os.path.join(self.tmp, "ow"), data=data)
        espo = FakeEspo()
        espo._insert("Email", {"sfId": fx.T[2], "from": "a@example.test", "name": "old", "status": "Archived",
                               "assignedUserId": None})
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        self.assertNotIn("write_rejected", self.report()["exceptions"]["byReason"])
        c0 = espo.by_sf("Contact")[fx.C[0]]
        o0 = espo.by_sf("Opportunity")[fx.O[0]]
        e2 = espo.by_sf("Email")[fx.T[2]]
        self.assertIsNone(c0["assignedUserId"])
        self.assertIsNone(o0["assignedUserId"])
        self.assertEqual(e2["name"], data["Task"][2]["Subject"])     # written, not refused
        self.assertNotIn(fx.T[2], espo.by_sf("Task"))
        for sf_id in (fx.C[0], fx.O[0], fx.T[2]):
            self.assertIn("owner_unresolved", self.codes(sf_id), sf_id)
            self.assertNotIn("owner_required_unresolved", self.codes(sf_id), sf_id)
        rep = self.report()
        for obj in ("Contact", "Opportunity", "Task"):
            self.assertEqual(rep["objects"][obj]["skipped"]["owner_required_unresolved"], 0, obj)

    def test_value_at_the_limit_is_sent(self):
        data = fx.org()
        data["Contact"][0]["MailingPostalCode"] = " " + "P" * 40 + " "   # trimmed: fits
        _, espo = self.load(data, "lim")
        self.assertEqual(espo.by_sf("Contact")[fx.C[0]]["addressPostalCode"].strip(), "P" * 40)
        self.assertNotIn("value_too_long", self.codes(fx.C[0]))

    def test_invalid_to_and_cc_are_dropped_and_invalid_from_refuses(self):
        data = fx.org()
        data["EmailMessage"][0]["ToAddress"] = "good@example.test; Value A"
        data["EmailMessage"][0]["CcAddress"] = "bad@@example.test"
        data["EmailMessage"][1]["FromAddress"] = "not an address"
        _, espo = self.load(data, "em")
        m0 = espo.by_sf("Email")[fx.M[0]]
        self.assertEqual(m0["to"], "good@example.test")
        self.assertIsNone(m0["cc"])
        self.assertIn("email_address_invalid", self.codes(fx.M[0]))
        self.assertNotIn(fx.M[1], espo.by_sf("Email"))
        self.assertIn("email_from_invalid", self.codes(fx.M[1]))
        self.assertEqual(self.report()["objects"]["EmailMessage"]["skipped"]["email_from_invalid"], 1)

    def test_blank_from_refuses(self):
        data = fx.org()
        data["EmailMessage"][1]["FromAddress"] = "  "
        _, espo = self.load(data, "bf")
        self.assertNotIn(fx.M[1], espo.by_sf("Email"))
        self.assertIn("email_from_invalid", self.codes(fx.M[1]))

    def test_rerun_after_refusals_makes_no_writes(self):
        data = fx.org()
        data["Task"][0]["OwnerId"] = fx.U_MISSING
        data["EmailMessage"][1]["ActivityId"] = None
        data["EmailMessage"][0]["CcAddress"] = "bad@@example.test"
        data["Contact"][1]["Title"] = "T" * 256
        data["Account"][0]["Name"] = "N" * 250
        data["Account"][1]["Phone"] = "1" * 37
        data["EmailMessage"][0]["ToAddress"] = "good@example.test; Value A"
        data["Event"][0]["OwnerId"] = fx.QUEUE
        snap, espo = self.load(data, "rr")
        self.assertEqual(self.report()["exceptions"]["byReason"].get("write_rejected", 0), 0)
        n = len(espo.writes)
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        self.assertEqual(espo.writes[n:], [])


class TestFaithfulFake(Base):
    """CRM-008: FakeEspo refuses what EspoCRM 10.0.12 refuses (PL-verified)."""

    def post(self, entity, body, espo=None):
        self._n += 1
        return (espo or FakeEspo()).send("POST", entity, body=dict(body, sfId=f"s{self._n}"))

    def test_owner_required_on_task_call_meeting(self):
        start = {"dateStart": "2025-01-01 00:00:00"}
        for entity in ("Task", "Call", "Meeting"):
            for body in ({}, {"assignedUserId": None}):
                with self.subTest(entity=entity, body=body):
                    self.assertEqual(self.post(entity, dict(start, **body)),
                                     (400, {"field": "assignedUser", "type": "required"}))
            self.assertEqual(self.post(entity, dict(start, assignedUserId="u"))[0], 200)
        self.assertEqual(self.post("Account", {"name": "a"})[0], 200)       # owner not required there
        f = FakeEspo()
        _st, doc = self.post("Task", {"assignedUserId": "u"}, f)
        self.assertEqual(f.send("PUT", f"Task/{doc['id']}", body={"assignedUserId": None})[0], 400)
        self.assertEqual(f.send("PUT", f"Task/{doc['id']}", body={"name": "n"})[0], 200)

    def test_name_required_on_account_and_service_type(self):
        for entity in ("Account", "ServiceType"):
            for body in ({}, {"name": None}, {"name": ""}, {"name": "  "}):
                with self.subTest(entity=entity, body=body):
                    self.assertEqual(self.post(entity, body), (400, {"field": "name", "type": "required"}))
            f = FakeEspo()
            _st, doc = self.post(entity, {"name": "n"}, f)
            self.assertEqual(f.send("PUT", f"{entity}/{doc['id']}", body={"name": None}),
                             (400, {"field": "name", "type": "required"}))
            self.assertEqual(f.send("PUT", f"{entity}/{doc['id']}", body={"description": "d"})[0], 200)
        self.assertEqual(self.post("Contact", {"lastName": "x"})[0], 200)   # name not checked there

    def test_max_length(self):
        self.assertEqual(self.post("Contact", {"title": "t" * 256}), (400, {"field": "title", "type": "maxLength"}))
        self.assertEqual(self.post("Contact", {"title": " " + "t" * 255 + " "})[0], 200)   # trimmed
        self.assertEqual(self.post("Account", {"name": "n" * 250})[0], 400)
        self.assertEqual(self.post("Account", {"name": "n" * 249})[0], 200)
        self.assertEqual(self.post("Account", {"name": "a", "phoneNumber": "1" * 37})[0], 400)
        self.assertEqual(self.post("Account", {"name": "a", "phoneNumber": "1" * 36})[0], 200)
        self.assertEqual(self.post("Contact", {"phoneNumberData": [{"phoneNumber": "1" * 37, "primary": True}]}),
                         (400, {"field": "phoneNumber", "type": "maxLength"}))

    def test_max_length_table_matches_mapping(self):
        mapping = {e: {a: n for a, n in v.items() if a != "phoneNumberData" and a != "phoneNumber"}
                   for e, v in load_json("mapping.json")["maxLength"].items() if e != "note"}
        self.assertEqual(mapping, fx.FakeEspo.MAX_LENGTH)
        phones = {n for v in load_json("mapping.json")["maxLength"].values() if isinstance(v, dict)
                  for a, n in v.items() if a in ("phoneNumber", "phoneNumberData")}
        self.assertEqual(phones, {fx.FakeEspo.PHONE_MAX_LENGTH})

    def test_amount_currency_against_settings(self):
        usd = fx.FakeEspo()                                  # 10.0.12 install default: USD only
        self.assertEqual(usd.send("GET", "Settings")[1]["currencyList"], ["USD"])
        body = {"name": "o", "stage": "Enquiry", "amount": 1.5, "amountCurrency": "GBP"}
        self.assertEqual(self.post("Opportunity", body, usd), (400, {"field": "amount", "type": "validCurrency"}))
        self.assertEqual(self.post("Opportunity", dict(body, amount=None, amountCurrency=None), usd)[0], 200)
        self.assertEqual(usd.provision_settings(), {"settings": {"created": 0, "updated": 1, "unchanged": 0}})
        self.assertEqual(usd.send("GET", "Settings")[1]["currencyList"], ["GBP"])
        self.assertEqual(self.post("Opportunity", dict(body, name="p"), usd)[0], 200)
        self.assertEqual(self.post("Opportunity", dict(body, name="q", amountCurrency="USD"), usd)[0], 400)
        self.assertEqual(usd.provision_settings(), {"settings": {"created": 0, "updated": 0, "unchanged": 1}})

    def test_email_addresses_and_from(self):
        ok = {"from": "a@example.test", "to": "b@example.test;c@example.test", "cc": None}
        self.assertEqual(self.post("Email", ok)[0], 200)
        for attr, bad in (("to", "b@example.test;Value A"), ("cc", "x@@example.test"), ("from", "nope")):
            with self.subTest(attr=attr):
                self.assertEqual(self.post("Email", dict(ok, **{attr: bad})), (400, {"field": attr, "type": "valid"}))
        for blank in (None, "", "  "):
            self.assertEqual(self.post("Email", dict(ok, **{"from": blank})),
                             (400, {"field": "from", "type": "required"}))
        self.assertEqual(self.post("Email", {k: v for k, v in ok.items() if k != "from"})[0], 400)


class TestCurrencySettings(Base):
    """The loader against USD-only Settings is refused every amount; against GBP it passes."""

    def test_usd_settings_refuse_every_amount_then_gbp_passes(self):
        espo = fx.FakeEspo()
        self.assertEqual(self.run_load(espo=espo), 5)
        with_amount = {r["Id"] for r in fx.org()["Opportunity"] if r["Amount"] is not None and not r["IsDeleted"]}
        rejected = {e["sfId"] for e in self.exceptions() if e["reason"] == "write_rejected"}
        self.assertEqual(rejected, with_amount)
        self.assertNotIn(fx.O[0], espo.by_sf("Opportunity"))
        self.assertEqual(len(rejected), self.report()["exceptions"]["byReason"]["write_rejected"])
        espo.provision_settings()
        self.assertEqual(self.run_load(espo=espo), 0, self.last_err)
        self.assertNotIn("write_rejected", self.report()["exceptions"]["byReason"])
        self.assertEqual(espo.by_sf("Opportunity")[fx.O[0]]["amountCurrency"], "GBP")
        n = len(espo.writes)
        self.assertEqual(self.run_load(espo=espo), 0, self.last_err)
        self.assertEqual(espo.writes[n:], [])


class TestEmailValidation(unittest.TestCase):
    def test_valid_and_invalid_addresses(self):
        from crm_load.mapping import email_valid
        for good in ("a@example.test", "first.last+tag@sub.example.co.uk", "o'neil@example.test",
                     "x_y-z@a-b.example.test", "a" * 64 + "@example.test"):
            self.assertTrue(email_valid(good), good)
        for bad in (None, "", " ", "Value A", "a@b", "a@@example.test", "a@example.test ",
                    ".a@example.test", "a.@example.test", "a..b@example.test", "a@-x.example.test",
                    "a@x-.example.test", "a@example.123", "a b@example.test", '"q"@example.test',
                    "a@[127.0.0.1]", "é@example.test", "a" * 65 + "@example.test",
                    "a@" + "b" * 64 + ".test", "a@" + ("b" * 60 + ".") * 5 + "test",
                    "a@example..test", "a@example.test;b@example.test"):
            self.assertFalse(email_valid(bad), bad)


class TestMaxLengthContract(unittest.TestCase):
    """CRM-008 change 5: mapping.json maxLength agrees with the custom entityDefs."""

    def test_entries_name_mapped_attributes_and_match_custom_entity_defs(self):
        mapping = load_json("mapping.json")
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        defs_dir = os.path.join(repo, "custom", "Espo", "Custom", "Resources", "metadata",
                                "entityDefs")
        for entity, limits in mapping["maxLength"].items():
            if entity == "note":
                continue
            spec = mapping["entities"][entity]
            mapped = set(spec.get("copy", {})) | set(spec.get("attributes", []))
            path = os.path.join(defs_dir, f"{entity}.json")
            fields = {}
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    fields = json.load(fh).get("fields", {})
            for attr, limit in limits.items():
                with self.subTest(attr=f"{entity}.{attr}"):
                    self.assertIn(attr, mapped)
                    self.assertIsInstance(limit, int)
                    if "maxLength" in fields.get(attr, {}):
                        self.assertEqual(limit, fields[attr]["maxLength"])

    def test_contact_title_is_255_in_both(self):
        self.assertEqual(load_json("mapping.json")["maxLength"]["Contact"]["title"], 255)

    def test_synthetic_event_type_maps_to_meeting_type_options(self):
        mapping = load_json("mapping.json")
        options = mapping["enums"]["Meeting.meetingType"]
        table = mapping["syntheticEnumMap"]["Event.Type"]
        self.assertEqual(set(table), {"Value A", "Value B", "Value C"})
        self.assertTrue(set(table.values()) <= set(options) - {""})


class TestSyntheticEventType(Base):
    def test_synthetic_type_is_mapped_only_for_a_synthetic_snapshot(self):
        row = dict(Id=fx.E[0], OwnerId=fx.U1, Subject="S", Type="Value B",
                   StartDateTime="2025-06-01T09:00:00Z", EndDateTime=None, IsAllDayEvent=False)

        class Ctx:
            def user_id(self, _):
                return "u1"

            def soft_deleted(self, _):
                return False

            def record_id(self, *_):
                return None
        real = self.mapper()
        attrs, exc = real.event(row, Ctx())
        self.assertIsNone(attrs["meetingType"])
        self.assertIn("enum_unmapped", exc)
        synth = Mapper(load_json("mapping.json"), {}, NameParser([]), "2026-11-01",
                       "2026-11-01 00:00:00", synthetic=True)
        attrs, exc = synth.event(row, Ctx())
        self.assertEqual(attrs["meetingType"], "Call")
        self.assertIn("synthetic_enum_mapped", exc)
        self.assertNotIn("enum_unmapped", exc)


class TestCrm008F(Base):
    """CRM-008-F: live-server fidelity from the second crm-dev load (all data synthetic)."""

    def load(self, data=None, name="f", espo=None):
        snap = write_snapshot(os.path.join(self.tmp, name), data=data or fx.org())
        espo = espo or FakeEspo()
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        self.assertNotIn("write_rejected", self.report()["exceptions"]["byReason"])
        return snap, espo

    def codes(self, sf_id):
        return {e["reason"] for e in self.exceptions() if e["sfId"] == sf_id}

    def rerun_writes(self, snap, espo):
        n = len(espo.writes)
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        return espo.writes[n:]

    # ------------------------------------------------------------ the fake (facts 1-4)
    def test_fake_list_omits_phone_data_single_read_returns_it(self):
        f = FakeEspo()
        data = [{"phoneNumber": " 01632 960000 ", "type": "Office", "primary": True},
                {"phoneNumber": "07700 900000", "type": "Mobile", "primary": False}]
        _st, doc = f.send("POST", "Contact", body={"sfId": "x", "phoneNumberData": data})
        _st, page = f.send("GET", "Contact", [("select", "id,sfId,phoneNumberData,phoneNumber"), ("maxSize", "200"),
                                              ("offset", "0"), ("where[0][type]", "isNotNull"),
                                              ("where[0][attribute]", "sfId")])
        self.assertNotIn("phoneNumberData", page["list"][0])
        self.assertEqual(page["list"][0]["phoneNumber"], "01632 960000")          # the primary, trimmed
        st, rec = f.send("GET", f"Contact/{doc['id']}")
        self.assertEqual(st, 200)
        self.assertEqual(rec["phoneNumberData"][1], {"phoneNumber": "07700 900000", "type": "Mobile",
                                                     "primary": False, "optOut": False, "invalid": False})
        self.assertEqual(f.send("GET", "Contact/nope"), (404, None))

    def test_fake_title_needs_account_and_date_completed_needs_completed(self):
        f = FakeEspo()
        _st, a = f.send("POST", "Contact", body={"sfId": "a", "title": "T", "accountId": None})
        _st, b = f.send("POST", "Contact", body={"sfId": "b", "title": "T", "accountId": "acc"})
        self.assertIsNone(f.db["Contact"][a["id"]]["title"])
        self.assertEqual(f.db["Contact"][b["id"]]["title"], "T")
        f.send("PUT", f"Contact/{a['id']}", body={"title": "T2"})
        self.assertIsNone(f.db["Contact"][a["id"]]["title"])
        # CRM-008-G: dateCompleted is readOnly; core stamps now on Completed, null otherwise.
        task = {"assignedUserId": "u", "priority": "Normal", "dateCompleted": "2025-01-01 00:00:00"}
        _st, t1 = f.send("POST", "Task", body=dict(task, sfId="t1", status="Not Started"))
        _st, t2 = f.send("POST", "Task", body=dict(task, sfId="t2", status="Completed"))
        self.assertIsNone(f.db["Task"][t1["id"]]["dateCompleted"])
        self.assertEqual(f.db["Task"][t2["id"]]["dateCompleted"], f.NOW)

    def test_fake_email_to_required(self):
        f = FakeEspo()
        for to in (None, "", "  "):
            self.assertEqual(f.send("POST", "Email", body={"sfId": f"e{to!r}", "from": "a@example.test", "to": to}),
                             (400, {"field": "to", "type": "required"}))
        self.assertEqual(f.send("POST", "Email", body={"sfId": "e0", "from": "a@example.test"})[0], 400)
        _st, doc = f.send("POST", "Email", body={"sfId": "e1", "from": "a@example.test", "to": "b@example.test"})
        self.assertEqual(f.send("PUT", f"Email/{doc['id']}", body={"to": None}),
                         (400, {"field": "to", "type": "required"}))
        self.assertEqual(f.send("PUT", f"Email/{doc['id']}", body={"name": "n"})[0], 200)   # to not sent

    # ------------------------------------------------------------ 1 phones
    def test_phones_second_run_zero_writes_with_bounded_single_reads(self):
        snap, espo = self.load()
        con = espo.by_sf("Contact")
        reads_before = len(espo.single_reads)
        self.assertEqual(self.rerun_writes(snap, espo), [])
        # Only C[0] has two numbers (with a matching primary): one GET; C[1] and C[2] have one.
        self.assertEqual(espo.single_reads[reads_before:], [("Contact", con[fx.C[0]]["id"])])
        self.assertEqual(self.report()["objects"]["Contact"]["targets"]["Contact"]["unchanged"], 3)

    def test_phones_primary_differs_writes_without_a_read(self):
        snap, espo = self.load()
        rec = espo.by_sf("Contact")[fx.C[0]]
        rec["phoneNumber"] = "01632 999999"
        reads_before = len(espo.single_reads)
        writes = self.rerun_writes(snap, espo)
        self.assertEqual([(m, e, sorted(b)) for m, e, b in writes], [("PUT", "Contact", ["phoneNumberData"])])
        self.assertEqual(espo.single_reads[reads_before:], [])
        self.assertEqual(rec["phoneNumber"], "01632 960100")

    def test_phones_secondary_differs_found_by_the_single_read(self):
        snap, espo = self.load()
        rec = espo.by_sf("Contact")[fx.C[0]]
        rec["phoneNumberData"] = rec["phoneNumberData"][:1]          # the Mobile was lost server-side
        reads_before, req_before = len(espo.single_reads), len(espo.requests)
        writes = self.rerun_writes(snap, espo)
        self.assertEqual([(m, e, sorted(b)) for m, e, b in writes], [("PUT", "Contact", ["phoneNumberData"])])
        self.assertEqual(espo.single_reads[reads_before:], [("Contact", rec["id"])])
        self.assertEqual(len(rec["phoneNumberData"]), 2)
        # requests.reads counts the single-record GET with the paged reads (the load's own client).
        gets = [p for m, p in espo.requests[req_before:] if m == "GET" and p != "Settings"]
        self.assertEqual(self.report()["requests"]["reads"], len(gets))
        self.assertEqual(sum(1 for p in gets if "/" in p), 1)

    def test_phones_single_number_and_none(self):
        data = fx.org()
        data["Contact"][1]["MobilePhone"] = None                    # C[1]: no phone at all
        snap, espo = self.load(data)
        self.assertIsNone(espo.by_sf("Contact")[fx.C[1]].get("phoneNumberData"))
        self.assertEqual(self.rerun_writes(snap, espo), [])
        espo.by_sf("Contact")[fx.C[1]]["phoneNumber"] = "01632 960555"     # a stored number, none in source
        writes = self.rerun_writes(snap, espo)
        self.assertEqual(writes, [("PUT", "Contact", {"phoneNumberData": None})])

    def test_single_read_failure_is_a_transport_error(self):
        snap, espo = self.load()

        class NoRead(FakeEspo):
            def send(self, method, path, query=None, body=None, headers=None):
                if method == "GET" and "/" in path:
                    return 403, None
                return super().send(method, path, query, body, headers)
        bad = NoRead()
        bad.db, bad._n = espo.db, espo._n
        self.assertEqual(self.run_load(snap=snap, espo=bad), 4)
        self.assertIn("code=read_failed", self.last_err)

    # ------------------------------------------------------------ 2 title
    def test_title_not_sent_without_account(self):
        data = fx.org()
        data["Contact"][1]["AccountId"] = None                       # C[1]: no account
        snap, espo = self.load(data)
        con = espo.by_sf("Contact")
        sent = [b for m, e, b in espo.writes if e == "Contact" and b.get("sfId") == fx.C[1]]
        self.assertNotIn("title", sent[0])
        self.assertIn("title_unstorable_without_account", self.codes(fx.C[1]))
        self.assertIn("title_unstorable_without_account", self.codes(fx.C[2]))   # account soft-deleted
        self.assertEqual(con[fx.C[0]]["title"], "T" + SENTINEL)                 # with an account: kept
        self.assertNotIn("title_unstorable_without_account", self.codes(fx.C[0]))
        self.assertEqual(self.rerun_writes(snap, espo), [])

    def test_title_blank_without_account_has_no_code(self):
        attrs, exc = self.mapper().contact(dict(Id=fx.C[0], Title=None, AccountId=None), _NullCtx())
        self.assertNotIn("title", attrs)
        self.assertNotIn("title_unstorable_without_account", exc)

    # ------------------------------------------------------------ 3 dateCompleted
    def test_date_completed_only_with_status_completed(self):
        data = fx.org()
        data["Task"][5]["CompletedDateTime"] = "2025-05-06T10:00:00.000+0000"     # Open, with a date
        snap, espo = self.load(data)
        tasks = espo.by_sf("Task")
        self.assertEqual(tasks[fx.T[0]]["dateCompleted"], "2025-05-05 10:00:00")
        self.assertIsNone(tasks[fx.T[5]].get("dateCompleted"))
        sent = [b for m, e, b in espo.writes if e == "Task" and b.get("sfId") == fx.T[5]]
        self.assertNotIn("dateCompleted", sent[0])
        self.assertNotIn("sfCompletedAt", sent[0])
        self.assertIn("date_completed_not_storable", self.codes(fx.T[5]))
        self.assertNotIn("date_completed_not_storable", self.codes(fx.T[0]))
        self.assertEqual(self.rerun_writes(snap, espo), [])

    def test_open_task_without_date_has_no_code(self):
        attrs, exc = self.mapper().task(dict(Id=fx.T[5], Status="Open", CompletedDateTime=None, OwnerId=fx.U1),
                                        _NullCtx())[1:]
        self.assertNotIn("dateCompleted", attrs)
        self.assertNotIn("sfCompletedAt", attrs)
        self.assertNotIn("date_completed_not_storable", exc)

    # ------------------------------------------------------------ 4 email without recipient
    def test_email_without_recipient_is_a_task(self):
        data = fx.org()
        data["EmailMessage"][1]["ToAddress"] = None                         # M[1]: linked to T[2]
        data["EmailMessage"][1]["TextBody"] = "Plain " + SENTINEL
        data["EmailMessage"][0]["ToAddress"] = "Value A; not-an-address"     # M[0]: none valid
        snap, espo = self.load(data)
        self.assertNotIn(fx.M[0], espo.by_sf("Email"))
        self.assertNotIn(fx.M[1], espo.by_sf("Email"))
        t = espo.by_sf("Task")[fx.M[1]]
        self.assertEqual((t["name"], t["description"], t["status"], t["dateCompleted"]),
                         ("Re2", "Plain " + SENTINEL, "Completed", "2025-07-02 12:00:00"))
        self.assertEqual(t["assignedUserId"], next(r["id"] for r in espo.db["User"].values() if r["sfId"] == fx.U1))
        t0 = espo.by_sf("Task")[fx.M[0]]
        self.assertEqual((t0["parentType"], t0["parentId"]), ("Opportunity", espo.by_sf("Opportunity")[fx.O[0]]["id"]))
        for m in (fx.M[0], fx.M[1]):
            self.assertIn("email_without_recipient_imported_as_task", self.codes(m))
        self.assertIn("email_address_invalid", self.codes(fx.M[0]))
        self.assertEqual((t["priority"], t0["priority"]), ("Normal", "Normal"))
        self.assertEqual(self.report()["exceptions"]["byReason"]["priority_server_default"], 2)
        self.assertEqual(self.report()["objects"]["EmailMessage"]["targets"]["Task"]["created"], 2)
        self.assertEqual(self.rerun_writes(snap, espo), [])
        self.assertNotIn("exists_not_in_snapshot", self.codes(fx.M[0]))

    def test_email_without_recipient_and_owner_is_refused_not_sent(self):
        data = fx.org()
        data["EmailMessage"][0].update(ToAddress=None, ActivityId=None)     # no linked Task, no owner
        snap, espo = self.load(data)
        self.assertNotIn(fx.M[0], espo.by_sf("Task"))
        self.assertNotIn(fx.M[0], espo.by_sf("Email"))
        self.assertIn("owner_required_unresolved", self.codes(fx.M[0]))
        self.assertNotIn("owner_from_created_by", self.codes(fx.M[0]))
        self.assertEqual(self.rerun_writes(snap, espo), [])

    # ------------------------------------------------------------ round 2: owner fallback, priority
    def _uid(self, espo, sf):
        return next(r["id"] for r in espo.db["User"].values() if r["sfId"] == sf)

    def test_email_task_owner_from_created_by_without_linked_task(self):
        data = fx.org()
        data["EmailMessage"][0].update(ToAddress=None, ActivityId=None, CreatedById=fx.U2)
        snap, espo = self.load(data)
        t = espo.by_sf("Task")[fx.M[0]]
        self.assertEqual((t["assignedUserId"], t["sfOwnerId"]), (self._uid(espo, fx.U2), fx.U2))
        self.assertEqual(t["priority"], "Normal")                     # server default, never sent
        sent = [b for m, e, b in espo.writes if e == "Task" and b.get("sfId") == fx.M[0]]
        self.assertNotIn("priority", sent[0])
        codes = self.codes(fx.M[0])
        self.assertTrue({"owner_from_created_by", "priority_server_default"} <= codes, codes)
        self.assertNotIn("owner_required_unresolved", codes)
        self.assertEqual(sum(1 for e in self.exceptions() if e["sfId"] == fx.M[0]
                             and e["reason"] == "priority_server_default"), 1)
        self.assertEqual(self.rerun_writes(snap, espo), [])

    def test_email_task_owner_from_created_by_when_linked_owner_unresolved(self):
        data = fx.org()
        data["EmailMessage"][1].update(ToAddress=None, CreatedById=fx.U2)    # linked to T[2]
        next(r for r in data["Task"] if r["Id"] == fx.T[2])["OwnerId"] = fx.QUEUE
        snap, espo = self.load(data)
        self.assertEqual(espo.by_sf("Task")[fx.M[1]]["assignedUserId"], self._uid(espo, fx.U2))
        codes = self.codes(fx.M[1])
        self.assertIn("owner_from_created_by", codes)
        self.assertFalse({"owner_queue_or_group", "owner_unresolved", "owner_required_unresolved"} & codes, codes)
        self.assertEqual(self.rerun_writes(snap, espo), [])

    def test_email_task_linked_owner_wins_over_created_by(self):
        data = fx.org()
        data["EmailMessage"][1].update(ToAddress=None, CreatedById=fx.U2)    # T[2] owned by U1
        snap, espo = self.load(data)
        self.assertEqual(espo.by_sf("Task")[fx.M[1]]["assignedUserId"], self._uid(espo, fx.U1))
        self.assertNotIn("owner_from_created_by", self.codes(fx.M[1]))
        self.assertIn("priority_server_default", self.codes(fx.M[1]))

    def test_email_task_created_by_not_provisioned_is_refused(self):
        for created_by in (fx.U_MISSING, fx.U_AUTOMATED, fx.QUEUE, None, {"Id": fx.U1}):
            data = fx.org()
            data["EmailMessage"][0].update(ToAddress=None, ActivityId=None, CreatedById=created_by)
            snap, espo = self.load(data, name=f"f{created_by!s:.3}{id(created_by)}")
            self.assertNotIn(fx.M[0], espo.by_sf("Task"), created_by)
            codes = self.codes(fx.M[0])
            self.assertIn("owner_required_unresolved", codes)
            self.assertNotIn("owner_from_created_by", codes)

    def test_plain_email_ignores_created_by(self):
        data = fx.org()
        data["EmailMessage"][0]["CreatedById"] = fx.U2
        snap, espo = self.load(data)
        e = espo.by_sf("Email")[fx.M[0]]
        self.assertIsNone(e.get("assignedUserId"))
        self.assertFalse({"owner_from_created_by", "priority_server_default"} & self.codes(fx.M[0]))

    def test_existing_email_stays_an_email(self):
        snap, espo = self.load()
        data = fx.org()
        data["EmailMessage"][1]["ToAddress"] = None
        snap2 = write_snapshot(os.path.join(self.tmp, "f2"), data=data)
        n = len(espo.writes)
        self.assertEqual(self.run_load(snap=snap2, espo=espo), 0, self.last_err)
        self.assertEqual(espo.writes[n:], [])                       # to is never sent as null
        self.assertNotIn(fx.M[1], espo.by_sf("Task"))
        self.assertEqual(espo.by_sf("Email")[fx.M[1]]["to"], "y@example.test")
        self.assertNotIn("email_without_recipient_imported_as_task", self.codes(fx.M[1]))


class TestCrm008G(Base):
    """CRM-008-G: the Salesforce completion date (sfCompletedAt and the Task hook), plus the
    CRM-008-F advisories (all data synthetic)."""

    load, codes, rerun_writes = TestCrm008F.load, TestCrm008F.codes, TestCrm008F.rerun_writes

    # ------------------------------------------------------------ the fake (facts 1-3)
    def test_fake_models_core_and_the_hook(self):
        f = FakeEspo()
        sf = "2025-01-01 00:00:00"
        base = {"assignedUserId": "u", "priority": "Normal"}
        _st, a = f.send("POST", "Task", body=dict(base, sfId="a", status="Completed", sfCompletedAt=sf))
        _st, b = f.send("POST", "Task", body=dict(base, sfId="b", status="Not Started", sfCompletedAt=sf))
        _st, c = f.send("POST", "Task", body=dict(base, sfId="c", status="Completed", sfCompletedAt=None))
        rec = f.db["Task"]
        self.assertEqual(rec[a["id"]]["dateCompleted"], sf)                    # the hook
        self.assertIsNone(rec[b["id"]]["dateCompleted"])                      # not Completed
        self.assertEqual(rec[c["id"]]["dateCompleted"], f.NOW)                # core, no sf date
        f.send("PUT", f"Task/{a['id']}", body={"name": "n", "dateCompleted": "2020-01-01 00:00:00"})
        self.assertEqual(rec[a["id"]]["dateCompleted"], sf)                    # unrelated, readOnly
        f.staff("PUT", f"Task/{a['id']}", body={"status": "Not Started"})
        self.assertIsNone(rec[a["id"]]["dateCompleted"])                      # reopen: core null
        f.staff("PUT", f"Task/{a['id']}", body={"status": "Completed"})
        self.assertEqual(rec[a["id"]]["dateCompleted"], f.NOW)                # staff re-completes
        f.send("PUT", f"Task/{a['id']}", body={"sfCompletedAt": "2025-02-02 00:00:00"})
        self.assertEqual(rec[a["id"]]["dateCompleted"], "2025-02-02 00:00:00")   # importer corrects
        # Round 2: the importer (an API user) re-completes a Task staff reopened.
        f.staff("PUT", f"Task/{a['id']}", body={"status": "Not Started"})
        f.send("PUT", f"Task/{a['id']}", body={"status": "Completed"})
        self.assertEqual(rec[a["id"]]["dateCompleted"], "2025-02-02 00:00:00")
        # An API save without a status change leaves dateCompleted alone.
        rec[a["id"]]["dateCompleted"] = f.NOW
        f.send("PUT", f"Task/{a['id']}", body={"name": "m"})
        self.assertEqual(rec[a["id"]]["dateCompleted"], f.NOW)
        self.assertEqual(f.writes[-1], ("PUT", "Task", {"name": "m"}))
        self.assertNotIn(("PUT", "Task", {"status": "Not Started"}), f.writes)   # staff(): not the importer's
        # Round 3: only ER Import (type api, userName er-import); another API user gets core's now.
        f.staff("PUT", f"Task/{a['id']}", body={"status": "Not Started"})
        f.as_user(("api", "sync-bot"), "PUT", f"Task/{a['id']}", body={"status": "Completed"})
        self.assertEqual(rec[a["id"]]["dateCompleted"], f.NOW)
        self.assertEqual(f.saving_user, ("api", "er-import"))                  # restored after as_user()

    def test_fake_another_api_user_recompletes_with_now(self):
        # The probe for the identity check: another API user re-completing a reopened Task.
        def probe(f):
            _st, a = f.send("POST", "Task", body={"sfId": "a", "assignedUserId": "u", "status": "Completed",
                                                 "sfCompletedAt": "2025-01-01 00:00:00"})
            f.staff("PUT", f"Task/{a['id']}", body={"status": "Not Started"})
            f.as_user(("api", "sync-bot"), "PUT", f"Task/{a['id']}", body={"status": "Completed"})
            return f.db["Task"][a["id"]]["dateCompleted"]
        f = FakeEspo()
        self.assertEqual(probe(f), f.NOW)
        loose = FakeEspo()
        loose.disabled_checks = {"import_user_identity"}                 # the round-2 hook: any API user
        self.assertEqual(probe(loose), "2025-01-01 00:00:00")

    def test_fake_without_the_hook_stamps_now(self):
        f = FakeEspo()
        f.disabled_checks = {"completed_hook"}
        _st, a = f.send("POST", "Task", body={"sfId": "a", "assignedUserId": "u", "status": "Completed",
                                             "sfCompletedAt": "2025-01-01 00:00:00"})
        self.assertEqual(f.db["Task"][a["id"]]["dateCompleted"], f.NOW)

    # ------------------------------------------------------------ 3 importer
    def completed_sources(self, data):
        """sfId -> the source completion time (EspoCRM format) of every Completed Task."""
        out = {}
        for r in data["Task"]:
            if r.get("IsDeleted") is not True and r.get("Status") == "Completed" and \
                    r.get("TaskSubtype") in (None, "Task") and r.get("CompletedDateTime"):
                out[r["Id"]] = r["CompletedDateTime"][:19].replace("T", " ")
        return out

    def test_completed_task_keeps_the_salesforce_date(self):
        data = fx.org()
        snap, espo = self.load(data)
        tasks = espo.by_sf("Task")
        expected = self.completed_sources(data)
        self.assertTrue(expected)
        for sf_id, when in expected.items():
            self.assertEqual((tasks[sf_id]["sfCompletedAt"], tasks[sf_id]["dateCompleted"]), (when, when))
        for m, e, body in espo.writes:
            if e == "Task":
                self.assertNotIn("dateCompleted", body)
        self.assertEqual(self.rerun_writes(snap, espo), [])

    def test_contract_reads_sf_completed_at_not_date_completed(self):
        with open(os.path.join(fx.ROOT, "load", "contract", "mapping.json"), encoding="utf-8") as fh:
            attrs = json.load(fh)["entities"]["Task"]["attributes"]
        self.assertIn("sfCompletedAt", attrs)
        self.assertNotIn("dateCompleted", attrs)

    def test_compares_sf_completed_at_never_date_completed(self):
        snap, espo = self.load()
        rec = espo.by_sf("Task")[fx.T[0]]
        rec["dateCompleted"] = espo.NOW              # e.g. a staff re-completion: not the importer's
        self.assertEqual(self.rerun_writes(snap, espo), [])
        rec["sfCompletedAt"] = "2020-01-01 00:00:00"     # the stored Salesforce value differs
        writes = self.rerun_writes(snap, espo)
        self.assertEqual(writes, [("PUT", "Task", {"sfCompletedAt": "2025-05-05 10:00:00"})])
        self.assertEqual(rec["dateCompleted"], "2025-05-05 10:00:00")

    # ------------------------------------------------------------ round 2: re-completion
    def reopen_and_rerun(self, snap, espo, sf_id):
        rec = espo.by_sf("Task")[sf_id]
        espo.staff("PUT", f"Task/{rec['id']}", body={"status": "Not Started"})     # staff reopens
        self.assertIsNone(rec["dateCompleted"])
        return rec, self.rerun_writes(snap, espo)

    def test_rerun_recompletes_a_reopened_task_with_the_source_date(self):
        # The reviewer's probe: reopen, then a rerun gives dateCompleted == source.
        snap, espo = self.load()
        rec, writes = self.reopen_and_rerun(snap, espo, fx.T[0])
        self.assertEqual(writes, [("PUT", "Task", {"status": "Completed"})])
        self.assertEqual((rec["status"], rec["dateCompleted"]), ("Completed", "2025-05-05 10:00:00"))
        self.assertEqual(self.rerun_writes(snap, espo), [])

    def test_rerun_recompletion_without_the_api_rule_stamps_now(self):
        # The round-1 hook (no API-user rule): the same probe ends with core's now.
        snap, espo = self.load()
        espo.disabled_checks = {"completed_hook_api_recompletion"}
        rec, writes = self.reopen_and_rerun(snap, espo, fx.T[0])
        self.assertEqual(writes, [("PUT", "Task", {"status": "Completed"})])
        self.assertEqual(rec["dateCompleted"], espo.NOW)

    def test_staff_recompletion_keeps_now_and_a_rerun_leaves_it(self):
        snap, espo = self.load()
        rec = espo.by_sf("Task")[fx.T[0]]
        espo.staff("PUT", f"Task/{rec['id']}", body={"status": "Not Started"})
        espo.staff("PUT", f"Task/{rec['id']}", body={"status": "Completed"})
        self.assertEqual(rec["dateCompleted"], espo.NOW)                      # core, a person
        self.assertEqual(self.rerun_writes(snap, espo), [])
        self.assertEqual(rec["dateCompleted"], espo.NOW)

    # ------------------------------------------------------------ round 2: no source date
    def test_completed_task_without_a_date_is_server_stamped(self):
        data = fx.org()
        data["Task"][0]["CompletedDateTime"] = None
        snap, espo = self.load(data)
        t = espo.by_sf("Task")[fx.T[0]]
        self.assertEqual((t["status"], t["sfCompletedAt"], t["dateCompleted"]), ("Completed", None, espo.NOW))
        self.assertIn("date_completed_server_stamped", self.codes(fx.T[0]))
        line = [e for e in self.exceptions() if e["reason"] == "date_completed_server_stamped"]
        self.assertEqual(line, [{"object": "Task", "sfId": fx.T[0], "reason": "date_completed_server_stamped"}])
        self.assertEqual(self.report()["exceptions"]["byReason"]["date_completed_server_stamped"], 1)
        # A Task with a source date gets no code. Round 3 (state-based): a plain re-run writes
        # nothing and records it again, so the latest report lists every such Task.
        self.assertTrue(any(r.get("Status") == "Completed" and r.get("CompletedDateTime") for r in data["Task"]))
        self.assertEqual(self.rerun_writes(snap, espo), [])
        self.assertEqual([e for e in self.exceptions() if e["reason"] == "date_completed_server_stamped"], line)
        self.assertEqual(self.report()["exceptions"]["byReason"]["date_completed_server_stamped"], 1)

    def test_completed_task_with_a_date_is_not_server_stamped(self):
        self.load()
        self.assertNotIn("date_completed_server_stamped", self.report()["exceptions"]["byReason"])

    # ------------------------------------------------------------ round 3: state-based stamp code
    def undated(self):
        data = fx.org()
        data["Task"][0]["CompletedDateTime"] = None
        return data

    def stamped(self, out=None):
        return [e for e in self.exceptions(out) if e["reason"] == "date_completed_server_stamped"]

    def test_rerun_after_staff_reopen_records_the_stamp_code(self):
        snap, espo = self.load(self.undated())
        rec, writes = self.reopen_and_rerun(snap, espo, fx.T[0])
        self.assertEqual(writes, [("PUT", "Task", {"status": "Completed"})])
        # No source date: core stamps the rerun time, and the code says so.
        self.assertEqual((rec["status"], rec["sfCompletedAt"], rec["dateCompleted"]), ("Completed", None, espo.NOW))
        self.assertEqual(self.stamped(), [{"object": "Task", "sfId": fx.T[0], "reason": "date_completed_server_stamped"}])
        self.assertEqual(self.report()["exceptions"]["byReason"]["date_completed_server_stamped"], 1)
        self.assertNotIn("write_rejected", self.report()["exceptions"]["byReason"])

    def test_reopened_task_left_open_gets_no_stamp_code(self):
        # State-based: a stored Task that is not Completed is not stamped (staff reopen, and the
        # rerun is refused, so it stays open).
        snap, espo = self.load(self.undated())
        rec = espo.by_sf("Task")[fx.T[0]]
        espo.staff("PUT", f"Task/{rec['id']}", body={"status": "Not Started"})
        orig = espo.send

        def send(method, path, query=None, body=None, headers=None):
            if method == "PUT" and path == f"Task/{rec['id']}":
                espo.writes.append((method, "Task", body))
                return 400, {"field": "status", "type": "valid"}
            return orig(method, path, query, body, headers)
        espo.send = send
        self.assertEqual(self.run_load(snap=snap, espo=espo), 5, self.last_err)    # finished, failures
        self.assertEqual(rec["status"], "Not Started")
        self.assertIn("write_rejected", self.codes(fx.T[0]))
        self.assertNotIn("date_completed_server_stamped", self.codes(fx.T[0]))

    def test_resume_past_the_post_records_the_stamp_code(self):
        data = self.undated()
        snap = write_snapshot(os.path.join(self.tmp, "undated"), data=data)

        class Boom(Exception):
            pass

        def interrupt(client):
            orig, posted = client.create, []

            def create(entity, attrs):
                if posted:
                    raise Boom()                       # the first POST after the stamped Task's
                rid = orig(entity, attrs)
                if entity == "Task" and attrs.get("sfId") == fx.T[0]:
                    posted.append(rid)
                return rid
            client.create = create
            return client

        first, espo = os.path.join(self.tmp, "first"), FakeEspo()
        with self.assertRaises(Boom):
            self.run_load(snap=snap, espo=espo, out=first, fail_after=interrupt)
        self.assertFalse(os.path.exists(os.path.join(first, "load-report.json")))
        self.assertIn(fx.T[0], espo.by_sf("Task"))                  # stored before the interruption
        out = os.path.join(self.tmp, "resumed")
        n = len(espo.writes)
        self.assertEqual(self.run_load("--resume", first, snap=snap, espo=espo, out=out), 0, self.last_err)
        self.assertNotIn(("POST", "Task"), [(m, e) for m, e, b in espo.writes[n:] if b.get("sfId") == fx.T[0]])
        resumed, resumed_exc = self.report(out), self.exceptions(out)
        self.assertEqual(self.stamped(out), [{"object": "Task", "sfId": fx.T[0],
                                              "reason": "date_completed_server_stamped"}])
        self.assertEqual(self.run_load(snap=snap, espo=FakeEspo()), 0, self.last_err)
        strip = lambda r: {k: v for k, v in r.items() if k != "requests"}  # noqa: E731
        self.assertEqual(strip(resumed), strip(self.report()))
        self.assertEqual(sorted(map(json.dumps, resumed_exc)), sorted(map(json.dumps, self.exceptions())))
        self.assertEqual(resumed["exceptions"]["byReason"]["date_completed_server_stamped"], 1)

    def test_rejected_post_records_no_stamp_code(self):
        snap, espo = self.load_rejected(self.undated(), fx.T[0])
        self.assertNotIn(fx.T[0], espo.by_sf("Task"))
        self.assertIn("write_rejected", self.codes(fx.T[0]))
        self.assertNotIn("date_completed_server_stamped", self.codes(fx.T[0]))
        self.assertNotIn("date_completed_server_stamped", self.report()["exceptions"]["byReason"])

    def test_rejected_email_task_post_records_no_stamp_code(self):
        data = fx.org()
        data["EmailMessage"][1].update(ToAddress=None, MessageDate=None)
        snap, espo = self.load_rejected(data, fx.M[1])
        self.assertIn("write_rejected", self.codes(fx.M[1]))
        self.assertNotIn("date_completed_server_stamped", self.codes(fx.M[1]))

    def test_refused_completed_task_without_a_date_gets_no_stamp_code(self):
        data = fx.org()
        data["Task"][0]["CompletedDateTime"] = None
        data["Task"][0]["OwnerId"] = fx.U_MISSING                # refused: never sent
        self.load(data)
        self.assertIn("owner_required_unresolved", self.codes(fx.T[0]))
        self.assertNotIn("date_completed_server_stamped", self.codes(fx.T[0]))

    def test_email_as_task_without_a_message_date_is_server_stamped(self):
        data = fx.org()
        data["EmailMessage"][1]["ToAddress"] = None
        data["EmailMessage"][1]["MessageDate"] = None
        snap, espo = self.load(data)
        t = espo.by_sf("Task")[fx.M[1]]
        self.assertEqual((t["status"], t["sfCompletedAt"], t["dateCompleted"]), ("Completed", None, espo.NOW))
        self.assertIn("date_completed_server_stamped", self.codes(fx.M[1]))
        self.assertEqual([e["object"] for e in self.exceptions() if e["reason"] == "date_completed_server_stamped"],
                         ["EmailMessage"])
        self.assertEqual(self.rerun_writes(snap, espo), [])
        self.assertIn("date_completed_server_stamped", self.codes(fx.M[1]))      # round 3: every run
        self.assertEqual(self.report()["exceptions"]["byReason"]["date_completed_server_stamped"], 1)

    def test_email_as_task_with_a_message_date_is_not_server_stamped(self):
        data = fx.org()
        data["EmailMessage"][1]["ToAddress"] = None
        self.load(data)
        self.assertIn("email_without_recipient_imported_as_task", self.codes(fx.M[1]))
        self.assertNotIn("date_completed_server_stamped", self.codes(fx.M[1]))

    def test_email_without_recipient_task_keeps_message_date(self):
        data = fx.org()
        data["EmailMessage"][1]["ToAddress"] = None
        snap, espo = self.load(data)
        t = espo.by_sf("Task")[fx.M[1]]
        self.assertEqual((t["sfCompletedAt"], t["dateCompleted"]), ("2025-07-02 12:00:00",) * 2)
        sent = [b for m, e, b in espo.writes if e == "Task" and b.get("sfId") == fx.M[1]]
        self.assertNotIn("dateCompleted", sent[0])
        self.assertEqual(self.rerun_writes(snap, espo), [])

    # ------------------------------------------------------------ 4 advisories
    def test_task_from_email_stays_a_task_once_it_has_a_recipient(self):
        data = fx.org()
        data["EmailMessage"][1]["ToAddress"] = None
        snap, espo = self.load(data)
        snap2 = write_snapshot(os.path.join(self.tmp, "g2"), data=fx.org())   # now has a recipient
        n = len(espo.writes)
        self.assertEqual(self.run_load(snap=snap2, espo=espo), 0, self.last_err)
        self.assertEqual(espo.writes[n:], [])                       # no Email POST, no Task write
        self.assertNotIn(fx.M[1], espo.by_sf("Email"))
        self.assertIn(fx.M[1], espo.by_sf("Task"))
        codes = self.codes(fx.M[1])
        self.assertIn("email_kept_as_task", codes)
        self.assertNotIn("email_without_recipient_imported_as_task", codes)
        self.assertEqual(self.report()["objects"]["EmailMessage"]["targets"]["Task"]["unchanged"], 1)

    def test_refused_email_task_records_no_sent_only_codes(self):
        data = fx.org()
        data["EmailMessage"][0].update(ToAddress=None, ActivityId=None)     # owner unresolved
        snap, espo = self.load(data)
        codes = self.codes(fx.M[0])
        self.assertIn("owner_required_unresolved", codes)
        self.assertFalse({"email_without_recipient_imported_as_task", "priority_server_default",
                          "email_kept_as_task"} & codes, codes)
        self.assertNotIn("priority_server_default", self.report()["exceptions"]["byReason"])

    def test_rejected_email_task_records_no_sent_only_codes(self):
        data = fx.org()
        data["EmailMessage"][1]["ToAddress"] = None
        snap, espo = self.load_rejected(data, fx.M[1])
        self.assertNotIn(fx.M[1], espo.by_sf("Task"))
        self.assertIn("write_rejected", self.codes(fx.M[1]))
        codes = self.codes(fx.M[1])
        self.assertFalse({"email_without_recipient_imported_as_task", "priority_server_default"} & codes,
                         codes)

    def load_rejected(self, data, sf_id):
        """A load whose server refuses the Task POST for ``sf_id`` (400): never stored."""
        class Refuses(FakeEspo):
            def send(self, method, path, query=None, body=None, headers=None):
                if method == "POST" and path == "Task" and (body or {}).get("sfId") == sf_id:
                    self.writes.append((method, path, body))
                    return 400, {"field": "name", "type": "valid"}
                return super().send(method, path, query, body, headers)
        snap = write_snapshot(os.path.join(self.tmp, "rej"), data=data)
        espo = Refuses()
        self.assertEqual(self.run_load(snap=snap, espo=espo), 5, self.last_err)    # finished, failures
        return snap, espo

    def test_html_only_body_gives_a_null_description(self):
        data = fx.org()
        data["EmailMessage"][1].update(ToAddress=None, TextBody=None)       # HtmlBody is not in v4
        snap, espo = self.load(data)
        t = espo.by_sf("Task")[fx.M[1]]
        self.assertIsNone(t["description"])
        sent = [b for m, e, b in espo.writes if e == "Task" and b.get("sfId") == fx.M[1]]
        self.assertIn("description", sent[0])
        self.assertIsNone(sent[0]["description"])
        self.assertEqual(self.rerun_writes(snap, espo), [])


class _Pages:
    """A scripted list endpoint: returns the given (total, rows) pages in order; records offsets."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.offsets = []

    def send(self, method, path, query=None, body=None, headers=None):
        assert method == "GET"
        self.offsets.append(int(dict(query)["offset"]))
        total, n = self.pages.pop(0)
        doc = {"list": [{"id": f"r{len(self.offsets)}-{i}", "sfId": f"s{len(self.offsets)}-{i}"} for i in range(n)]}
        if total is not _Pages.MISSING:
            doc["total"] = total
        return 200, doc

    MISSING = object()


class TestUnknownListTotal(Base):
    """CRM-009-H: 10.0.12 answers an Email list read with ``total: -1``; every page is read."""

    EXTRA = 250                     # more than one page (PAGE 200) of Emails

    def big_email_snapshot(self):
        data = fx.org()
        base = dict(data["EmailMessage"][1], ActivityId=None, RelatedToId=fx.O[0])
        for i in range(self.EXTRA):
            data["EmailMessage"].append(dict(base, Id=fx.sid("02s", 100 + i)))
        return write_snapshot(os.path.join(self.tmp, "many-emails"), data=data)

    def test_fake_reports_unknown_total_only_for_chosen_entities(self):
        espo = FakeEspo(uncounted={"Email"})
        espo._insert("Email", {"sfId": "e"})
        q = [("select", "id,sfId"), ("maxSize", "200"), ("offset", "0"),
             ("where[0][type]", "isNotNull"), ("where[0][attribute]", "sfId")]
        self.assertEqual(espo.send("GET", "Email", q)[1]["total"], -1)
        self.assertEqual(espo.send("GET", "User", q)[1]["total"], 4)
        counted = FakeEspo()                                                     # default unchanged
        counted._insert("Email", {"sfId": "e"})
        self.assertEqual(counted.send("GET", "Email", q)[1]["total"], 1)

    def test_every_email_indexed_rerun_zero_writes_parents_match(self):
        snap = self.big_email_snapshot()
        espo = FakeEspo(uncounted={"Email"})
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        emails = len(espo.by_sf("Email"))
        self.assertGreater(emails, 200)
        self.assertEqual(self.report()["objects"]["EmailMessage"]["targets"]["Email"]["created"], emails)
        rel = self.report()["relationships"]
        for name, r in rel.items():
            self.assertEqual(r["snapshot"], r["espocrm"], name)
        self.assertGreater(rel["activity_parents"]["snapshot"], self.EXTRA)
        first = len(espo.writes)
        self.assertEqual(self.run_load(snap=snap, espo=espo), 0, self.last_err)
        self.assertIn(f"event=index entity=Email records={emails}", self.last_err)
        self.assertEqual(len(espo.writes), first)
        rep = self.report()
        self.assertEqual(rep["requests"]["writes"], 0)
        self.assertEqual(rep["objects"]["EmailMessage"]["targets"]["Email"]["unchanged"], emails)
        for name, r in rep["relationships"].items():
            self.assertEqual(r["snapshot"], r["espocrm"], name)

    def test_unknown_total_pages_until_a_short_page(self):
        for total in (-1, None, _Pages.MISSING, "400", 1.5, True):
            with self.subTest(total=total):
                t = _Pages([(total, 200), (total, 200), (total, 7)])
                rows = EspoClient(t, sleep=lambda s: None).list_all("Email", ["sfId"])
                self.assertEqual(len(rows), 407)
                self.assertEqual(t.offsets, [0, 200, 400])
                self.assertEqual(t.pages, [])

    def test_unknown_total_stops_on_an_empty_page(self):
        t = _Pages([(-1, 200), (-1, 0)])
        client = EspoClient(t, sleep=lambda s: None)
        self.assertEqual(len(client.list_all("Email", ["sfId"])), 200)
        self.assertEqual(t.offsets, [0, 200])
        self.assertEqual(client.reads, 2)
        self.assertEqual(client.writes, 0)
        self.assertEqual(len(EspoClient(_Pages([(-1, 0)]), sleep=lambda s: None).list_all("Email", ["sfId"])), 0)

    def test_known_total_unchanged(self):
        t = _Pages([(250, 200), (250, 50)])
        self.assertEqual(len(EspoClient(t, sleep=lambda s: None).list_all("Meeting", ["sfId"])), 250)
        self.assertEqual(t.offsets, [0, 200])                    # stops at the total, no extra read
        t = _Pages([(0, 0)])
        self.assertEqual(EspoClient(t, sleep=lambda s: None).list_all("Meeting", ["sfId"]), [])

    def test_known_total_not_reached_is_list_incomplete(self):
        for pages in ([(300, 200), (300, 0)],                    # the server stops short
                      [(300, 200), (300, 50), (300, 0)],
                      [(150, 200)]):                             # more rows than the total
            with self.subTest(pages=pages):
                with self.assertRaises(TransportError) as cm:
                    EspoClient(_Pages(pages), sleep=lambda s: None).list_all("Meeting", ["sfId"])
                self.assertEqual(cm.exception.code, "list_incomplete")
                self.assertEqual(cm.exception.exit_code, 4)

    def test_incomplete_index_fails_the_load_with_no_writes(self):
        class ShortMeeting(FakeEspo):
            def send(self, method, path, query=None, body=None, headers=None):
                st, doc = super().send(method, path, query, body, headers)
                if method == "GET" and path == "Meeting" and isinstance(doc, dict) and "list" in doc:
                    doc["total"] = len(doc["list"]) + 1          # the count disagrees with the rows
                return st, doc
        espo = ShortMeeting()
        self.assertEqual(self.run_load(espo=espo), 4)
        self.assertIn("list_incomplete", self.last_err)
        self.assertEqual(espo.writes, [])
        self.assertFalse([r for r in espo.requests if r[0] != "GET"])


if __name__ == "__main__":
    unittest.main()
