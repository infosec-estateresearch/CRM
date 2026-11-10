# Estate Research CRM

Estate Research's self-hosted replacement for Salesforce. It is delivered incrementally under [FOUNDRY](https://github.com/maff0000/foundry) governance, starting with law firms (head office and branches) and their contacts.

**Status: in delivery.** The crm-dev stack (EspoCRM 10.0.12, synthetic data only) runs on the development host. crm-beta, the first environment with customer data, is installed only from a verified release bundle (CRM-007). EspoCRM is the build candidate (CRM-D010).

| Record | Purpose |
|---|---|
| [PROJECT-INITIATION-MANDATE.md](PROJECT-INITIATION-MANDATE.md) | Identity, execution target, scope, security context, blockers |
| [PRODUCT-VISION.md](PRODUCT-VISION.md) | Why, for whom, and the Product Goal |
| [PRODUCT-BACKLOG.md](PRODUCT-BACKLOG.md) | Ordered increments. These are not Work Orders. |
| [DECISIONS.md](DECISIONS.md) | Proposed and approved decisions |
| [docs/BUILD.md](docs/BUILD.md) | How the CRM is built, where it runs, its isolation boundary and how it is verified |
| [security/EXTERNAL_CODE_REGISTER.yaml](security/EXTERNAL_CODE_REGISTER.yaml) | External code and images |
| [work-orders/](work-orders/) | Work Orders. Each is approved by exact version on its own Issue. |

Rules:
- GitHub is the authoritative record.
- This repository is public, so it must not contain secrets, host addresses, staff names, customer or firm names, or Salesforce identifiers.
- Salesforce is read-only and is never written to.

## Usage

The CRM-001 dev stack is EspoCRM 10.0.12 plus MariaDB 11.4.13, both pinned by digest, with Estate Research's customisations in `custom/`, deployed into the runtime by script. It runs only on the development host, as Compose project `crm-dev`. All of its data is synthetic.

### Access

- `crm-app` is published on port 8180 of one host LAN address, `CRM_BIND_IP`. It is not published on `127.0.0.1` or `0.0.0.0`.
- Apache inside `crm-app` admits only the authorised internal networks in `CRM_ALLOWED_SOURCES`, plus loopback for the healthcheck. Every other source gets 403 (`deploy/apache/crm-access.conf`, CRM-D019).
- The values exist only in the runtime env file, never in this repository. Start the stack only with `scripts/up.sh dev`, which checks them (`scripts/check_access.py`) before every `up`. A raw `docker compose up` skips that check.
- The database publishes nothing.
- The connection is plain HTTP. TLS is mandatory before any real data.
- Operator steps, including moving the existing install: [docs/BUILD.md §7.6](docs/BUILD.md#76-lan-access-crm-d019).

### Runtime and operations

- EspoCRM's persistent directories (`data/`, `custom/`, `client/custom/`) are bind-mounted individually and read-write from `/srv/CRM/runtime/dev`. `/var/www/html` itself is never mounted.
- Git is authoritative for the customisation. `scripts/deploy_custom.sh dev` deploys `custom/Espo/Custom/` into the runtime, before the first start and after every change. It stops `crm-app` and `crm-daemon` for the swap and refuses to run if any path it works on is a symlink or diverges from the env file. If the app was running, it then starts it again, clears the cache and rebuilds. Admin-UI changes to custom metadata are overwritten by the next deploy.
- Backups cover the database, `data/`, `custom/` and `client/custom/`.
- Deploy, seed, back up, restore and export: see [docs/BUILD.md §7](docs/BUILD.md#7-usage-crm-001-dev-stack).
- Users and access (CRM-003): named logins only. Teams and roles are defined in `config/access/`. `scripts/provision_access.py dev` provisions the teams, the roles and the `ER Import` API user, and `scripts/provision_users.py dev` provisions users by `sfId`. Both are idempotent. Temporary passwords and the API key go only to new `0600` files, never to the terminal or email. A firm with enquiries cannot be deleted, even by an admin. See [docs/ACCESS.md](docs/ACCESS.md), which covers roles, provisioning, the missing forced-password-change flag and where to find the audit history.
- Enquiries (CRM-004): EspoCRM's Opportunity entity, relabelled "Enquiry", with stages Enquiry → Quoted → Instructed / Lost. A lost enquiry needs a loss reason, and the server enforces it. Service types are an admin-maintained reference list. See [docs/ENQUIRIES.md](docs/ENQUIRIES.md).
- Activities (CRM-005): core Calls, Meetings (with a meeting type), Tasks and archived Emails, with their Salesforce keys. An archived email is read-only history for everyone but admins and the importer. There is no email sending or receiving. `provision_access.py` also provisions the "ER Staff" dashboard ("My open tasks" and Calendar); `--deploy-dashboards` deploys it and replaces those users' dashboards. See [docs/ACTIVITIES.md](docs/ACTIVITIES.md).
- Import (CRM-006): `crm-load` loads one sealed Salesforce snapshot (contract v4) into EspoCRM through the REST API as the `ER Import` user, keyed on `sfId`. Re-running it makes no writes and it never deletes. Run it only as root with `scripts/load.sh [--accept-drift URL] [--reconciliation DIR] [--resume DIR] <dev|beta> <snapshot-dir> <new-output-dir>`: `dev` takes only a synthetic snapshot (`<name>-selftest/run-1` or `run-2` under a sealed, verified selftest directory) and `beta` only a `<name>-extract` snapshot. The API key comes from the root-only `/srv/CRM/runtime/<target>/load.env`. It writes a counts-only `load-report.json` and an ids-and-codes-only `exceptions.jsonl`. Users are written to `users.json` by `crm-load users` and provisioned by `provision_users.py`. See [docs/IMPORT.md](docs/IMPORT.md).
- Beta (CRM-007): crm-beta is the first environment with customer data. It is installed only from a verified release bundle:
  - build and verify the bundle with `scripts/release.sh <commit>` and `python3 scripts/release.py verify <bundle> --sha256 <hex>`;
  - deploy, as root, with `scripts/deploy_release.sh beta <bundle> --sha256 <hex> [--upgrade]`.

  It runs as Compose project `crm-beta` behind the edge proxy `crm-beta-edge`. The edge is reached only by the PO's TLS-terminating HAProxy; crm-app itself listens only on `127.0.0.1`.

  The other scripts take `beta` as their target: `up.sh`, `backup.sh`, `restore.sh`, `export.sh`, `deploy_custom.sh`, `provision_access.py` and `provision_users.py`. `restore.sh beta --restoretest <backup>` restores a backup into the throwaway project `crm-beta-restoretest`, prints record counts and tears it down. `tests/acceptance/test_beta_safe.py` is the read-only (GET-only) suite for a live beta.

  See [docs/BETA.md](docs/BETA.md) and [docs/RELEASE.md](docs/RELEASE.md).
- Checks that need no stack: `python3 -m unittest discover -s tests/unit -v` and `python3 -I -B -m unittest discover -s tests/load -t . -v`.
- Checks against the running stack (operator stage): `python3 -m unittest discover -s tests/acceptance -v`. These need `CRM_BASE_URL`, `CRM_ADMIN_USERNAME`, `CRM_ADMIN_PASSWORD` and `CRM_EXPECTED_BIND_IP` in the environment. The CRM-003 access tests (`-p test_access.py`) need `CRM_ACCESS_OUTPUT_DIR` instead of `CRM_EXPECTED_BIND_IP`, and are skipped without it.
