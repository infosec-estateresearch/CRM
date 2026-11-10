"""Test-facing fake: ``FakeSalesforceTransport``, fixtures, mutation hooks and helpers.

The implementation lives in ``crm_migrate.synthetic`` because the container ``selftest``
mode needs it and only ``migrate/`` is mounted there. It is in-memory only: no sockets,
no loopback.
"""

import os
import tempfile

from crm_migrate.client import SalesforceClient
from crm_migrate.contract import load_contract, parse_contract
from crm_migrate.extract import ExtractOptions, run_extract
from crm_migrate.log import CountsLog
from crm_migrate.manifest import OutputDir
from crm_migrate.synthetic import (  # noqa: F401  (re-exported for the tests)
    CLOCK_START, FAKE_API_VERSION, FAKE_ORG_ID, FAKE_PASSWORD, FAKE_SESSION, FAKE_SOAP_VERSION, FAKE_USERNAME,
    SOAP_FAULT_RESPONSE, SOAP_SUCCESS_TEMPLATE, WRITE_CAPABLE, FAKE_CLIENT_ID, FAKE_CLIENT_SECRET, FAKE_ORIGIN, FAKE_TOKEN, KEY_PREFIX,
    PLANTED, SCENARIO_EXPECTED, SENTINEL, FakeOrg, FakeSalesforceTransport, FakeWriteAttempt, Hook, build_org,
    make_fake, scenario_hooks, sf_id)

from . import CONTRACT_PATH

_CONTRACT = None


def contract():
    global _CONTRACT
    if _CONTRACT is None:
        _CONTRACT = load_contract(CONTRACT_PATH)
    return _CONTRACT


def contract_bytes():
    with open(CONTRACT_PATH, "rb") as fh:
        return fh.read()


def contract_from_doc(doc):
    import json
    return parse_contract(json.dumps(doc).encode("utf-8"))


def client_for(fake, contract_=None, authenticate=True):
    c = SalesforceClient(FAKE_ORIGIN, FAKE_API_VERSION, fake, contract_ or contract())
    if authenticate:
        c.authenticate(FAKE_CLIENT_ID, FAKE_CLIENT_SECRET)
    return c


class TempDirMixin:
    def tmp(self):
        if not hasattr(self, "_tmpdirs"):
            self._tmpdirs = []
        d = tempfile.TemporaryDirectory(prefix="crm-migrate-test-")
        self._tmpdirs.append(d)
        self.addCleanup(d.cleanup)
        return d.name

    def extract(self, fake, options=None, contract_=None, name="snap"):
        out = os.path.join(self.tmp(), name)
        client = client_for(fake, contract_)
        manifest = run_extract(client, contract_ or contract(), OutputDir(out), CountsLog(), options or ExtractOptions())
        return out, manifest


DATA_PATH_KINDS = ("/query", "/queryAll")


def data_queries(fake):
    """Paths of record/count queries the fake received."""
    return [p for _, p in fake.requests if any(k in p for k in DATA_PATH_KINDS)]
