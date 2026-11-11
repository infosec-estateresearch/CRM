#!/usr/bin/env python3
"""Count crm-beta records created during UAT (CRM-009). Read-only: GET only.

    python3 scripts/uat_records.py beta [--list-ids NEW_FILE]

Imported records carry their Salesforce key in sfId; a record created in
crm-beta during UAT has an empty sfId (null or ""). For each of Account,
Contact, Opportunity, Task, Call, Meeting and Email this prints only the count
of such records, as JSON. They must be removed before the production
migration. --list-ids also writes their EspoCRM ids (entity,id lines; no names,
no field values) to a NEW file, mode 0600, never overwriting anything.

The first argument must be exactly "beta" (exit 2 otherwise). Credentials come
from CRM_ADMIN_USERNAME / CRM_ADMIN_PASSWORD; the base URL from --base-url or
CRM_BASE_URL, and it must be exactly beta's pinned loopback URL
(check_access.base_url_problem). Every request is a GET.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_access  # noqa: E402
import crm_api  # noqa: E402
import provision_access as access  # noqa: E402
from provision_access import ProvisionError  # noqa: E402

ENTITIES = ("Account", "Contact", "Opportunity", "Task", "Call", "Meeting", "Email")
PROG = "uat_records"


class GetOnlyTransport:
    """Wraps a transport and refuses anything but GET (defence in depth)."""

    def __init__(self, inner):
        self.inner = inner

    def request(self, method, url, headers, body):
        if method != "GET" or body is not None:
            raise ProvisionError(f"{PROG} sends only GET requests (refused {method})")
        return self.inner.request(method, url, headers, body)


def uat_ids(client, entity):
    """Sorted ids of entity records whose sfId is null or empty."""
    ids = set()
    for condition in (("isNull", "sfId", None), ("equals", "sfId", "")):
        params = dict(crm_api.where_params([condition]), select="id")
        ids.update(row["id"] for row in client.list_all(entity, params))
    return sorted(ids)


def main(argv=None, transport=None, environ=None):
    argv = sys.argv[1:] if argv is None else argv
    environ = os.environ if environ is None else environ
    if not argv or argv[0] != "beta":
        print(f"{PROG}: refusing to run: target environment must be 'beta' "
              f"(got '{(argv[0] if argv else '') or '<none>'}')", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(prog=PROG, description=__doc__.splitlines()[0])
    parser.add_argument("target")
    parser.add_argument("--base-url", default=environ.get(crm_api.ENV_BASE_URL, ""))
    parser.add_argument("--list-ids", metavar="NEW_FILE",
                        help="new file (mode 0600) for the entity,id of each UAT record")
    args = parser.parse_args(argv)
    problem = check_access.base_url_problem("beta", args.base_url, environ)
    if problem:
        print(f"{PROG}: refusing to run: {problem}", file=sys.stderr)
        return 2
    try:
        if args.list_ids:
            access.check_new_private_path(args.list_ids)
        client = access.client_from_env(args.base_url, environ,
                                        GetOnlyTransport(transport or crm_api.UrllibTransport()))
        found = {entity: uat_ids(client, entity) for entity in ENTITIES}
        if args.list_ids:
            fh = access.create_private_file(args.list_ids)
            with fh:
                for entity in ENTITIES:
                    for record_id in found[entity]:
                        fh.write(f"{entity},{record_id}\n")
    except crm_api.ConfigError as err:
        print(f"{PROG}: {err}", file=sys.stderr)
        return 2
    except (ProvisionError, crm_api.ApiError) as err:
        print(f"{PROG}: {err}", file=sys.stderr)
        return 1
    print(json.dumps({entity: len(ids) for entity, ids in found.items()}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
