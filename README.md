# Estate Research CRM

Estate Research's self-hosted replacement for Salesforce. It is delivered incrementally under [FOUNDRY](https://github.com/maff0000/foundry) governance, starting with law firms (head office and branches) and their contacts.

**Status: initiation.** Nothing is installed or released. EspoCRM is the leading candidate and has not been selected.

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

### Usage


- EspoCRM's persistent directories (`data/`, `custom/`, `client/custom/`) are bind-mounted individually and read-write from `/srv/CRM/runtime/dev`. `/var/www/html` itself is never mounted.
- Git is authoritative for the customisation. `scripts/deploy_custom.sh dev` deploys `custom/Espo/Custom/` into the runtime, before the first start and after every change. It stops `crm-app` and `crm-daemon` for the swap and refuses to run if any path it works on is a symlink or diverges from the env file. If the app was running, it then starts it again, clears the cache and rebuilds. Admin-UI changes to custom metadata are overwritten by the next deploy.
- Backups cover the database, `data/`, `custom/` and `client/custom/`.
- Deploy, seed, back up, restore and export: see [docs/BUILD.md §7](docs/BUILD.md#7-usage-crm-001-dev-stack).
- Checks that need no stack: `python3 -m unittest discover -s tests/unit -v`.
- Checks against the running stack (operator stage): `python3 -m unittest discover -s tests/acceptance -v`. These need `CRM_BASE_URL`, `CRM_ADMIN_USERNAME`, `CRM_ADMIN_PASSWORD` and `CRM_EXPECTED_BIND_IP` in the environment.
