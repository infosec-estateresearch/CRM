"""Register, docs, repository hygiene, and the suite-wide zero-write check (runs last)."""

import hashlib
import os
import re
import unittest

from . import DOC_PATH, REGISTER_PATH, REPO
from .fake_salesforce import FakeSalesforceTransport

ORIGINAL_REGISTER_BYTES = 1394
ORIGINAL_REGISTER_SHA256 = "5d6c851e7b407cc209362304a856f8d67c954e3a2d8ec4e5b5957f418b3a5b9a"


class RegisterTest(unittest.TestCase):
    def setUp(self):
        with open(REGISTER_PATH, "rb") as fh:
            self.raw = fh.read()

    def test_existing_entries_byte_identical(self):
        self.assertEqual(hashlib.sha256(self.raw[:ORIGINAL_REGISTER_BYTES]).hexdigest(), ORIGINAL_REGISTER_SHA256)

    def test_python_candidate_entry(self):
        tail = self.raw[ORIGINAL_REGISTER_BYTES:].decode("utf-8")
        self.assertTrue(tail.startswith("  - name: python\n"))
        for line in ('version: "3.13.9-slim-trixie"',
                     'digest: "sha256:326df678c20c78d465db501563f3492d17c42a4afe33a1f2bf5406a1d56b0e86"',
                     "licence: PSF-2.0", "usage: crm-migrate extractor (CRM-002)", "approval: none"):
            self.assertIn(line, tail)


class DocsTest(unittest.TestCase):
    def test_operator_guide_states_the_limits(self):
        with open(DOC_PATH, encoding="utf-8") as fh:
            doc = fh.read()
        self.assertRegex(doc, r"`queryAll` \*\*cannot\*\* return permanently deleted records")
        self.assertRegex(doc, r"overlap is an \*\*assumption\*\*")
        for heading in ("## Modes", "## Storage model and sealing", "## Completeness statuses",
                        "## Deletion classes", "## Retention and disposal", "## Live-stage gates"):
            self.assertIn(heading, doc)


class HygieneTest(unittest.TestCase):
    """No real hostnames, addresses or secrets in the delivered tree."""

    ROOTS = ("migrate", "deploy/migrate", "tests/migrate", "scripts/migrate.sh", "docs/MIGRATION.md")

    def files(self):
        for root in self.ROOTS:
            path = os.path.join(REPO, root)
            if os.path.isfile(path):
                yield path
                continue
            for d, _, names in os.walk(path):
                if "__pycache__" in d:
                    continue
                for n in names:
                    yield os.path.join(d, n)

    ALLOWED_HOST_RE = re.compile(
        r"^(?:[a-z0-9-]+\.)*example\.test$"
        r"|^(?:example|other|ex-ample--uat|<mydomain>)(?:\.sandbox)?\.my\.salesforce\.com$"
        r"|^(?:login|test|example|my)\.salesforce\.com$"          # generic hosts used only as refused fixtures
        r"|^example\.lightning\.force\.com$"
        r"|^hub\.docker\.com$")

    def test_no_ip_addresses_or_foreign_hosts(self):
        url_re = re.compile(r"https?://([^/\s\"'`)\]]+)")
        mail_re = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
        for path in self.files():
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            with self.subTest(path=os.path.relpath(path, REPO)):
                ips = [ip for ip in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text) if ip != "127.0.0.1"]
                self.assertEqual(ips, [])
                hosts = {h.split(":")[0].split("@")[-1].lower() for h in url_re.findall(text)}
                hosts |= {h.lower() for h in mail_re.findall(text)}
                hosts = {h.rstrip(".") for h in hosts if not set(h) & set("{%<[")}
                bad = {h for h in hosts if not self.ALLOWED_HOST_RE.match(h)}
                self.assertEqual(bad, set())


class ZeroWritesTest(unittest.TestCase):
    def test_fake_recorded_zero_write_requests_across_the_suite(self):
        self.assertGreater(FakeSalesforceTransport.total_requests, 1000)
        self.assertEqual(FakeSalesforceTransport.total_write_requests, 0)


if __name__ == "__main__":
    unittest.main()
