"""No record content, secret or token in any stdout, stderr or log line, in every mode (AC9)."""

import io
import logging
import os
import unittest

from crm_migrate import cli
from crm_migrate.log import LOGGER_NAME, CountsLog

from .fake_salesforce import (FAKE_API_VERSION, FAKE_CLIENT_ID, FAKE_CLIENT_SECRET, FAKE_ORIGIN, SENTINEL,
                              TempDirMixin, contract, make_fake)

ENV = {"CRM_SF_ORIGIN": FAKE_ORIGIN, "CRM_SF_CLIENT_ID": FAKE_CLIENT_ID, "CRM_SF_CLIENT_SECRET": FAKE_CLIENT_SECRET,
       "CRM_SF_API_VERSION": FAKE_API_VERSION}
MARK = SENTINEL.lower()


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


class ExplodingTransport:
    def send(self, request):
        raise ValueError(f"{SENTINEL} unexpected value in exception text")


class NoContentInLogsTest(TempDirMixin, unittest.TestCase):
    def run_cli(self, argv, transport=None, environ=ENV):
        out, err = io.StringIO(), io.StringIO()
        cap = Capture()
        logger = logging.getLogger(LOGGER_NAME)
        logger.addHandler(cap)
        try:
            rc = cli.main(argv, environ=dict(environ), transport=transport, stdout=out, stderr=err)
        finally:
            logger.removeHandler(cap)
        text = out.getvalue() + err.getvalue() + "\n".join(cap.lines)
        self.assertNotIn(MARK, text.lower(), f"sentinel leaked in {argv[0]} output")
        self.assertNotIn("example.test", text)
        self.assertTrue(text.strip(), "mode produced no output at all")
        return rc, out.getvalue(), err.getvalue(), cap.lines

    def outdir(self):
        return os.path.join(self.tmp(), "out")

    def assert_data_has_sentinel(self, root):
        """Sanity: the fixture data does carry the sentinel, so the log check is not vacuous."""
        import gzip
        with gzip.open(os.path.join(root, "objects", "Account.jsonl.gz"), "rt", encoding="utf-8") as fh:
            self.assertIn(MARK, fh.read().lower())

    # ---------------------------------------------------------- success paths
    def test_contract_check(self):
        rc, out, _, lines = self.run_cli(["contract-check", "--out", self.outdir()], make_fake(contract()))
        self.assertEqual(rc, 0)
        self.assertIn("status=PASS", out)
        self.assertTrue(any("gate_result" in ln for ln in lines))

    def test_count(self):
        rc, out, _, _ = self.run_cli(["count", "--out", self.outdir()], make_fake(contract()))
        self.assertEqual(rc, 0)
        self.assertIn("count object=Task query=26 queryAll=30", out)

    def extract_snapshot(self):
        d = self.outdir()
        rc, out, _, _ = self.run_cli(["extract", "--out", d], make_fake(contract()))
        self.assertEqual(rc, 0)
        self.assertIn("status=RECONCILED", out)
        self.assert_data_has_sentinel(d)
        return d

    def test_extract(self):
        self.extract_snapshot()

    def test_extract_drift_and_incomplete_exit_codes(self):
        rc, out, _, _ = self.run_cli(["extract", "--out", self.outdir()], make_fake(contract(), "continuous"))
        self.assertEqual(rc, 10)
        rc, out, _, _ = self.run_cli(["extract", "--out", self.outdir()],
                                     make_fake(contract(), "permanent_delete_unlogged"))
        self.assertEqual(rc, 11)
        self.assertIn("status=INCOMPLETE", out)

    def test_reconcile(self):
        snap = self.extract_snapshot()
        rc, out, _, _ = self.run_cli(["reconcile", "--snapshot", snap, "--out", self.outdir()])
        self.assertEqual(rc, 0)
        self.assertIn("snapshot_status=RECONCILED", out)

    def test_selftest(self):
        rc, out, _, _ = self.run_cli(["selftest", "--quick", "--out", self.outdir()])
        self.assertEqual(rc, 0)
        self.assertIn("status=RECONCILED", out)

    def test_hostcheck(self):
        rc, out, _, _ = self.run_cli(["hostcheck", "run-id", SENTINEL])
        self.assertEqual(rc, 1)
        self.assertIn("invalid run id", out)

    # ---------------------------------------------------------- error paths
    def test_gate_failure(self):
        fake = make_fake(contract(), org_kwargs={"describe_overrides": {"Account": {"deletable": True}}})
        rc, _, err, _ = self.run_cli(["extract", "--out", self.outdir()], fake)
        self.assertEqual(rc, 3)
        self.assertIn("metadata_gate_failed", err)
        fake = make_fake(contract(), org_kwargs={"field_overrides": {"Account.Name": None}})
        rc, _, _, _ = self.run_cli(["contract-check", "--out", self.outdir()], fake)
        self.assertEqual(rc, 3)
        rc, out, _, _ = self.run_cli(["count", "--out", self.outdir()], fake)
        self.assertEqual(rc, 3)

    def test_instance_url_mismatch(self):
        fake = make_fake(contract(), instance_url="https://other.my.salesforce.com")
        rc, _, err, _ = self.run_cli(["count", "--out", self.outdir()], fake)
        self.assertEqual(rc, 4)
        self.assertIn("instance_url_mismatch", err)

    def test_redirect(self):
        rc, _, err, _ = self.run_cli(["extract", "--out", self.outdir()],
                                     make_fake(contract(), redirect_paths=(r"/queryAll",)))
        self.assertEqual(rc, 4)
        self.assertIn("redirect_refused", err)

    def test_error_body_with_sentinel(self):
        rc, _, err, _ = self.run_cli(["extract", "--out", self.outdir()],
                                     make_fake(contract(), error_paths=(r"/query/01gS7000004-",)))
        self.assertEqual(rc, 4)
        self.assertIn("status=500 sf_error=UNKNOWN_EXCEPTION", err)

    def test_bad_credentials(self):
        env = dict(ENV, CRM_SF_CLIENT_SECRET="wrong-" + SENTINEL)
        rc, _, err, _ = self.run_cli(["contract-check", "--out", self.outdir()], make_fake(contract()), env)
        self.assertEqual(rc, 4)
        self.assertIn("INVALID_CLIENT", err)

    def test_absolute_next_records_url(self):
        rc, _, err, _ = self.run_cli(["extract", "--out", self.outdir()], make_fake(contract(), absolute_next=True))
        self.assertEqual(rc, 4)
        self.assertIn("next_records_url_refused", err)

    def test_missing_config(self):
        env = {k: v for k, v in ENV.items() if k != "CRM_SF_CLIENT_SECRET"}
        rc, _, err, _ = self.run_cli(["contract-check", "--out", self.outdir()], make_fake(contract()), env)
        self.assertEqual(rc, 2)
        self.assertIn("missing CRM_SF_CLIENT_SECRET", err)

    def test_invalid_origin_config(self):
        env = dict(ENV, CRM_SF_ORIGIN=f"https://{SENTINEL}.example.test")
        rc, _, err, _ = self.run_cli(["contract-check", "--out", self.outdir()], None, env)
        self.assertEqual(rc, 4)
        self.assertIn("origin_refused", err)

    def test_non_empty_output_dir(self):
        d = self.tmp()
        with open(os.path.join(d, SENTINEL), "w") as fh:
            fh.write(SENTINEL)
        rc, _, err, _ = self.run_cli(["extract", "--out", d], make_fake(contract()))
        self.assertEqual(rc, 2)
        self.assertIn("output_dir_not_empty", err)

    def test_corrupt_snapshot(self):
        snap = self.extract_snapshot()
        with open(os.path.join(snap, "objects", "Note.jsonl.gz"), "ab") as fh:
            fh.write(SENTINEL.encode())
        rc, _, err, _ = self.run_cli(["reconcile", "--snapshot", snap, "--out", self.outdir()])
        self.assertEqual(rc, 5)
        self.assertIn("checksum_mismatch", err)

    def test_unexpected_exception_prints_class_only(self):
        rc, _, err, _ = self.run_cli(["extract", "--out", self.outdir()], ExplodingTransport())
        self.assertEqual(rc, 1)
        self.assertIn("ValueError", err)

    def test_bad_arguments_not_echoed(self):
        rc, _, err, _ = self.run_cli(["extract", "--passes", SENTINEL, "--out", self.outdir()])
        self.assertEqual(rc, 2)
        rc, _, err, _ = self.run_cli([SENTINEL])
        self.assertEqual(rc, 2)


class CountsLogTest(unittest.TestCase):
    def test_values_outside_vocabulary_are_redacted(self):
        cap = Capture()
        logger = logging.getLogger("crm_migrate.test")
        logger.addHandler(cap)
        logger.setLevel(logging.INFO)
        log = CountsLog(logger)
        log.allow_contract(contract())
        log.event("x", object="Account", name=SENTINEL, code="http_error", sf_error="INVALID_FIELD",
                  n=3, flag=True, **{"Bad-Key": SENTINEL})
        log.event(SENTINEL, obj="SELECT Id FROM Account")
        logger.removeHandler(cap)
        text = "\n".join(cap.lines)
        self.assertNotIn(MARK, text.lower())
        self.assertIn("object=Account", text)
        self.assertIn("name=<redacted>", text)
        self.assertIn("sf_error=INVALID_FIELD", text)
        self.assertIn("obj=<redacted>", text)
        self.assertIn("event=invalid_event", text)


if __name__ == "__main__":
    unittest.main()
