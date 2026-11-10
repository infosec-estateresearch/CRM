"""Reconciled baseline (AC5, AC6) under every mutation hook."""

import datetime as dt
import os
import stat
import unittest

from crm_migrate.errors import HttpError, OutputError, ProtocolError
from crm_migrate.extract import ExtractOptions, assess_object, merge_rows, parse_sf_datetime
from crm_migrate.manifest import OutputDir, read_jsonl_gz, read_manifest, verify_tree

from .fake_salesforce import SENTINEL, TempDirMixin, contract, make_fake

EXPECTED_ROWS = {"User": 6, "Profile": 3, "UserRole": 3, "Account": 24, "Contact": 40, "Opportunity": 30,
                 "OpportunityContactRole": 15, "Task": 30, "Event": 12, "EmailMessage": 15,
                 "EmailMessageRelation": 30, "Note": 6}


def rows(snap, obj):
    return {r["Id"]: r for r in read_jsonl_gz(os.path.join(snap, "objects", f"{obj}.jsonl.gz"))}


class BaselineTest(TempDirMixin, unittest.TestCase):
    def test_no_mutation_exact_counts_reconciled(self):
        fake = make_fake(contract())
        snap, man = self.extract(fake)
        self.assertEqual(man["status"], "RECONCILED")
        self.assertTrue(man["quiet"])
        self.assertEqual(len(man["passes"]), 2)            # base + one quiet catch-up
        for obj, n in EXPECTED_ROWS.items():
            self.assertEqual(man["objects"][obj]["rows"], n, obj)
            self.assertEqual(man["objects"][obj]["status"], "RECONCILED", obj)
            self.assertEqual(len(rows(snap, obj)), n)
        self.assertEqual(man["passes"][0]["objects"]["Account"]["pages"], 4)
        self.assertEqual(man["passes"][0]["objects"]["Contact"]["pages"], 6)
        self.assertEqual(man["objects"]["Task"]["verification"]["count_query"], 26)      # 4 archived
        self.assertEqual(man["objects"]["Task"]["verification"]["count_queryAll"], 30)
        self.assertEqual(man["objects"]["Task"]["archived"], 4)
        self.assertEqual(man["objects"]["Account"]["verification"]["count_query"], 22)   # 2 soft-deleted
        self.assertEqual(fake.write_requests, 0)

    def test_watermarks_come_from_the_server_date_header(self):
        _, man = self.extract(make_fake(contract()))
        # token + 12 describes + limits = 14 requests on a fake clock that ticks once per request
        self.assertEqual(man["t_start"], "2026-11-10T09:00:14Z")
        self.assertEqual(man["passes"][1]["since"], "2026-11-10T08:45:14Z")
        self.assertEqual(man["overlap_seconds"], 900)
        self.assertIn("assumption", man["overlap_note"])

    def test_checksums_modes_and_manifest(self):
        old = os.umask(0o077)
        self.addCleanup(os.umask, old)
        snap, man = self.extract(make_fake(contract()))
        _, problems = verify_tree(snap)
        self.assertEqual(problems, [])
        for rel in ("manifest.json", "contract-check.json", "describe.json", "passlog.jsonl",
                    "objects/Account.jsonl.gz", "deleted/Account.jsonl.gz"):
            st = os.stat(os.path.join(snap, rel))
            self.assertEqual(stat.S_IMODE(st.st_mode), 0o600, rel)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(snap, "objects")).st_mode), 0o700)
        self.assertFalse(os.path.exists(os.path.join(snap, "deleted", "Note.jsonl.gz")))   # not replicateable
        self.assertEqual(man["deletion_log"]["Note"], "unavailable")
        for key in ("t_start", "passes", "overlap_seconds", "passes_max", "api_version", "contract", "objects",
                    "status", "files", "verification"):
            self.assertIn(key, man)
        self.assertEqual(man["contract"]["version"], 2)
        self.assertEqual(man["contract"]["sha256"], contract().sha256)
        self.assertEqual(read_manifest(snap)["files"], man["files"])

    def test_tampering_is_detected(self):
        snap, _ = self.extract(make_fake(contract()))
        with open(os.path.join(snap, "objects", "Note.jsonl.gz"), "ab") as fh:
            fh.write(b"x")
        self.assertEqual(verify_tree(snap)[1], ["checksum_mismatch"])
        with open(os.path.join(snap, "extra.txt"), "w") as fh:
            fh.write("x")
        self.assertIn("unlisted_file", verify_tree(snap)[1])

    def test_second_run_identical_content(self):
        a, man_a = self.extract(make_fake(contract()), name="a")
        b, man_b = self.extract(make_fake(contract()), name="b")
        for rel, entry in man_a["files"].items():
            if rel.startswith("objects/"):
                self.assertEqual(entry["sha256"], man_b["files"][rel]["sha256"], rel)

    def test_records_hold_only_effective_fields(self):
        snap, man = self.extract(make_fake(contract()))
        for obj, spec in man["contract"]["effective"].items():
            for row in rows(snap, obj).values():
                self.assertEqual(list(row), spec["fields"])
                break

    def test_output_dir_must_be_new_and_empty(self):
        d = self.tmp()
        with open(os.path.join(d, "existing"), "w") as fh:
            fh.write("x")
        with self.assertRaises(OutputError):
            OutputDir(d)
        out = OutputDir(os.path.join(self.tmp(), "new"))
        out.write_text("a.txt", "x")
        with self.assertRaises(OutputError):
            out.write_text("a.txt", "y")
        for bad in ("../x", "/abs", "a/../b", ""):
            with self.subTest(bad=bad), self.assertRaises(OutputError):
                out.write_text(bad, "y")

    def test_error_mid_run_is_incomplete_without_data_files(self):
        fake = make_fake(contract(), error_paths=(r"/query/01gS7000010-",))
        out = os.path.join(self.tmp(), "snap")
        from crm_migrate.client import SalesforceClient  # noqa: F401
        with self.assertRaises(HttpError):
            self.extract_to(fake, out)
        man = read_manifest(out)
        self.assertEqual(man["status"], "INCOMPLETE")
        self.assertEqual(man["error"]["code"], "http_error")
        self.assertFalse(os.path.exists(os.path.join(out, "objects")))

    def extract_to(self, fake, out):
        from crm_migrate.extract import run_extract
        from crm_migrate.log import CountsLog
        from .fake_salesforce import client_for
        return run_extract(client_for(fake), contract(), OutputDir(out), CountsLog(), ExtractOptions())

    def test_options_validated(self):
        for opts in (ExtractOptions(passes=0), ExtractOptions(passes=21),
                     ExtractOptions(overlap=dt.timedelta(minutes=-1)), ExtractOptions(deletion_log_days=30)):
            with self.subTest(opts=opts), self.assertRaises(ProtocolError):
                opts.validate()


class MutationHookTest(TempDirMixin, unittest.TestCase):
    def run_scenario(self, name, options=None):
        fake = make_fake(contract(), name)
        snap, man = self.extract(fake, options)
        self.assertEqual(fake.write_requests, 0)
        return fake, snap, man

    def assert_others_reconciled(self, man, changed):
        for obj, entry in man["objects"].items():
            if obj not in changed:
                self.assertEqual(entry["status"], "RECONCILED", obj)
                self.assertEqual(sum(entry["drift_per_pass"]), 0, obj)

    def test_update(self):
        fake, snap, man = self.run_scenario("update")
        self.assertEqual(man["status"], "RECONCILED")
        self.assertEqual(man["objects"]["Account"]["drift_per_pass"], [1, 0])
        self.assertEqual(man["passes"][1]["objects"]["Account"]["updated"], 1)
        got = rows(snap, "Account")
        for rid, row in fake.org.rows["Account"].items():
            self.assertEqual(got[rid]["Phone"], row["Phone"])
            self.assertEqual(got[rid]["SystemModstamp"], row["SystemModstamp"])
        self.assertIn("000 0000 0000", [r["Phone"] for r in got.values()])
        self.assert_others_reconciled(man, {"Account"})

    def test_insert(self):
        fake, snap, man = self.run_scenario("insert")
        self.assertEqual(man["status"], "RECONCILED")
        self.assertEqual(man["objects"]["Account"]["rows"], 25)
        self.assertEqual(man["passes"][1]["objects"]["Account"]["inserted"], 1)
        self.assertEqual(set(rows(snap, "Account")), set(fake.org.rows["Account"]))

    def test_soft_delete(self):
        fake, snap, man = self.run_scenario("soft_delete")
        self.assertEqual(man["status"], "RECONCILED")
        self.assertEqual(man["objects"]["Account"]["drift_per_pass"], [1, 0])
        self.assertEqual(man["objects"]["Account"]["soft_deleted"], 3)
        got = rows(snap, "Account")
        self.assertEqual(sum(1 for r in got.values() if r["IsDeleted"]), 3)
        self.assertEqual(man["objects"]["Account"]["verification"]["count_query"], 21)

    def test_permanent_delete_with_deletion_log(self):
        fake, snap, man = self.run_scenario("permanent_delete_logged")
        self.assertEqual(man["status"], "RECONCILED")
        self.assertEqual(man["objects"]["Account"]["deleted_during_run"], 1)
        self.assertEqual(man["objects"]["Account"]["rows"], 23)
        self.assertEqual(set(rows(snap, "Account")), set(fake.org.rows["Account"]))

    def test_permanent_delete_without_evidence_is_incomplete_and_kept(self):
        fake, snap, man = self.run_scenario("permanent_delete_unlogged")
        self.assertEqual(man["status"], "INCOMPLETE")
        acc = man["objects"]["Account"]
        self.assertEqual((acc["unexplained_missing"], acc["deleted_during_run"]), (1, 0))
        self.assertIn("unexplained_missing", acc["reasons"])
        self.assertEqual(acc["rows"], 24)                  # absence is never treated as deletion
        self.assertEqual(len(set(rows(snap, "Account")) - set(fake.org.rows["Account"])), 1)

    def test_merge(self):
        fake, snap, man = self.run_scenario("merge")
        self.assertEqual(man["status"], "RECONCILED")
        self.assertEqual(man["objects"]["Account"]["drift_per_pass"], [2, 0])
        got = rows(snap, "Account")
        merged = [r for r in got.values() if r["IsDeleted"] and r["MasterRecordId"]]
        self.assertEqual(len(merged), 2)                   # planted merge + hook merge
        hook_loser = [r for r in merged if r["Id"] != sorted(got)[19]]
        self.assertTrue(all(got[r["MasterRecordId"]]["IsDeleted"] is False for r in hook_loser))

    def test_late_visible_row_within_overlap(self):
        fake, snap, man = self.run_scenario("late_visible")
        self.assertEqual(man["status"], "RECONCILED")
        self.assertEqual(man["objects"]["Contact"]["drift_per_pass"], [1, 0])
        self.assertEqual(man["objects"]["Contact"]["rows"], 41)
        self.assertEqual(set(rows(snap, "Contact")), set(fake.org.rows["Contact"]))

    def test_late_visible_row_beyond_overlap_is_incomplete(self):
        _, _, man = self.run_scenario("late_visible_beyond_overlap")
        self.assertEqual(man["status"], "INCOMPLETE")
        self.assertEqual(man["objects"]["Contact"]["unexplained_new"], 1)

    def test_larger_overlap_catches_the_late_row(self):
        _, _, man = self.run_scenario("late_visible_beyond_overlap",
                                      ExtractOptions(overlap=dt.timedelta(minutes=120)))
        self.assertEqual(man["status"], "RECONCILED")
        self.assertEqual(man["objects"]["Contact"]["drift_per_pass"], [1, 0])
        self.assertEqual(man["overlap_seconds"], 7200)

    def test_continuous_change_is_drift(self):
        fake, snap, man = self.run_scenario("continuous")
        self.assertEqual(man["status"], "RECONCILED_WITH_DRIFT")
        self.assertFalse(man["quiet"])
        self.assertEqual(len(man["passes"]), 4)
        acc = man["objects"]["Account"]
        self.assertEqual(acc["status"], "RECONCILED_WITH_DRIFT")
        self.assertEqual(acc["drift_per_pass"], [1, 1, 1])
        self.assertEqual(acc["residual_drift"], {"new": 0, "changed": 1})
        self.assert_others_reconciled(man, {"Account"})

    def test_continuous_change_with_more_passes(self):
        _, _, man = self.run_scenario("continuous", ExtractOptions(passes=5))
        self.assertEqual(man["objects"]["Account"]["drift_per_pass"], [1, 1, 1, 1, 1])
        self.assertEqual(man["status"], "RECONCILED_WITH_DRIFT")

    def test_injected_id_set_mismatch_is_incomplete(self):
        _, _, man = self.run_scenario("injected_id_mismatch")
        self.assertEqual(man["status"], "INCOMPLETE")
        self.assertIn("unexplained_missing", man["objects"]["Account"]["reasons"])

    def test_injected_count_mismatch_is_incomplete(self):
        _, _, man = self.run_scenario("injected_count_mismatch")
        self.assertEqual(man["status"], "INCOMPLETE")
        self.assertIn("count_vs_id_set_mismatch", man["objects"]["Task"]["reasons"])
        self.assertEqual(man["objects"]["Account"]["status"], "RECONCILED")


class PureMergeTest(unittest.TestCase):
    def test_latest_change_key_wins(self):
        base = {}
        a = {"Id": "001S700000000001AA", "SystemModstamp": "2026-11-10T09:00:00.000+0000", "Name": "old"}
        b = dict(a, SystemModstamp="2026-11-10T09:00:01.000+0000", Name="new")
        self.assertEqual(merge_rows(base, [a], ("Id", "SystemModstamp", "Name"), "SystemModstamp"), (1, 0, 0))
        self.assertEqual(merge_rows(base, [b], ("Id", "SystemModstamp", "Name"), "SystemModstamp"), (0, 1, 0))
        self.assertEqual(merge_rows(base, [a], ("Id", "SystemModstamp", "Name"), "SystemModstamp"), (0, 0, 1))
        self.assertEqual(base["001S700000000001AA"][1]["Name"], "new")
        with self.assertRaises(ProtocolError):
            merge_rows(base, [{"Id": "bad id", "SystemModstamp": a["SystemModstamp"]}], ("Id",), "SystemModstamp")

    def test_datetime_parsing(self):
        utc = dt.timezone.utc
        self.assertEqual(parse_sf_datetime("2026-11-10T09:00:00.000+0000"), dt.datetime(2026, 11, 10, 9, tzinfo=utc))
        self.assertEqual(parse_sf_datetime("2026-11-10T10:00:00+01:00"), dt.datetime(2026, 11, 10, 9, tzinfo=utc))
        self.assertIsNone(parse_sf_datetime("2026-11-10 09:00"))
        self.assertIsNone(parse_sf_datetime(SENTINEL))

    def test_stamp_regression_is_incomplete(self):
        spec = contract().object("Account")
        t = dt.datetime(2026, 11, 10, 9, tzinfo=dt.timezone.utc)
        base = {"001S700000000001AA": (t, {"IsDeleted": False})}
        status, details, _ = assess_object(spec, spec.field_names, base,
                                           {"001S700000000001AA": (t - dt.timedelta(seconds=1), False)},
                                           1, 1, {}, t, dt.timedelta(minutes=15), 0)
        self.assertEqual(status, "INCOMPLETE")
        self.assertEqual(details["change_key_regressed"], 1)


if __name__ == "__main__":
    unittest.main()
