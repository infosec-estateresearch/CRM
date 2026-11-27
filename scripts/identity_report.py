#!/usr/bin/env python3
"""Read-only report of contacts whose primary firm is not among their linked firms
(CRM-IDINT-001, 3.3).

A contact's primary firm (Contact.accountId) must be one of its linked firms
(Contact.accounts). Records that predate the control may break that. This report
lists them, as a count and the contact identifiers. It changes nothing: it sends
GET requests only, does not repair a contact and invents no primary firm.

    export CRM_BASE_URL=http://<host>:<port>
    export CRM_ADMIN_USERNAME=...  CRM_ADMIN_PASSWORD=...      # never stored or printed
    python3 scripts/identity_report.py [--base-url URL]

Output (stdout): {"count": N, "contactIds": ["...", ...]} with identifiers in sorted order.
Exit codes: 0 report written, 1 the API refused a read, 2 configuration missing.
Standard library only; no identifier other than contact ids is printed.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import crm_api  # noqa: E402


class ReadOnlyTransport:
    """Wraps a transport and refuses anything but GET (so the report cannot write)."""

    def __init__(self, inner):
        self.inner = inner

    def request(self, method, url, headers, body):
        if method != "GET" or body is not None:
            raise RuntimeError("identity_report.py is read-only")
        return self.inner.request(method, url, headers, body)


def find_exceptions(client):
    """Sorted ids of contacts that have a primary firm which is not one of their linked firms."""
    contacts = client.list_all("Contact", {"select": "id,accountId"})
    by_firm = {}
    for contact in contacts:
        firm = contact.get("accountId")
        if firm:
            by_firm.setdefault(firm, set()).add(contact["id"])
    broken = set()
    for firm, primary_ids in by_firm.items():
        linked = {row["id"] for row in client.list_all(f"Account/{firm}/contacts", {"select": "id"})}
        broken |= primary_ids - linked
    return sorted(broken)


def report(client):
    ids = find_exceptions(client)
    return {"count": len(ids), "contactIds": ids}


def main(argv=None, transport=None, environ=None, out=None):
    environ = os.environ if environ is None else environ
    out = sys.stdout if out is None else out
    parser = argparse.ArgumentParser(description="List contacts whose primary firm is not a linked firm.")
    parser.add_argument("--base-url", default=environ.get(crm_api.ENV_BASE_URL, ""))
    args = parser.parse_args(argv)
    try:
        username, password = crm_api.credentials_from_env(environ)
        client = crm_api.EspoClient(args.base_url, username, password,
                                    transport=ReadOnlyTransport(transport or crm_api.UrllibTransport()))
    except crm_api.ConfigError as err:
        print(f"identity_report.py: {err}", file=sys.stderr)
        return 2
    try:
        print(json.dumps(report(client), sort_keys=True), file=out)
    except crm_api.ApiError as err:
        print(f"identity_report.py: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
