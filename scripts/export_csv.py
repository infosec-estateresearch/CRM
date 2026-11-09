#!/usr/bin/env python3
"""CSV export of Accounts and Contacts through the EspoCRM REST API.

Called by scripts/export.sh. Credentials come from CRM_ADMIN_USERNAME /
CRM_ADMIN_PASSWORD. Values are written verbatim (no spreadsheet-formula
escaping) so the export is a faithful copy of the data.
"""

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import crm_api  # noqa: E402

EXPORTS = {
    "Account": ("accounts.csv", [
        "id", "name", "parentId", "parentName", "type", "industry",
        "practiceManagementSystem", "learningPlatformAccess",
        "billingAddressStreet", "billingAddressCity", "billingAddressPostalCode",
        "billingAddressCountry", "phoneNumber", "emailAddress", "website",
        "createdAt", "modifiedAt",
    ]),
    "Contact": ("contacts.csv", [
        "id", "firstName", "lastName", "emailAddress", "phoneNumber",
        "accountId", "accountName", "createdAt", "modifiedAt",
    ]),
}


def export(client, out_dir):
    """Write one CSV per entity type; return {entityType: row_count}."""
    os.makedirs(out_dir, mode=0o700, exist_ok=True)
    counts = {}
    for entity_type, (filename, columns) in EXPORTS.items():
        records = client.list_all(entity_type, {"select": ",".join(columns)})
        path = os.path.join(out_dir, filename)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for record in records:
                writer.writerow({c: "" if record.get(c) is None else record.get(c)
                                 for c in columns})
        counts[entity_type] = len(records)
    return counts


def main(argv=None, transport=None, environ=None):
    environ = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=environ.get(crm_api.ENV_BASE_URL, ""))
    parser.add_argument("--out", required=True, help="output directory")
    args = parser.parse_args(argv)
    try:
        username, password = crm_api.credentials_from_env(environ)
        client = crm_api.EspoClient(args.base_url, username, password, transport)
        counts = export(client, args.out)
    except crm_api.ConfigError as err:
        print(f"export_csv: {err}", file=sys.stderr)
        return 2
    except crm_api.ApiError as err:
        print(f"export_csv: {err}", file=sys.stderr)
        return 1
    print(json.dumps({"out": args.out, "counts": counts}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
