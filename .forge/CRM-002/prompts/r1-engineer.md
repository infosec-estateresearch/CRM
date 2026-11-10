# CRM-002, round 1: Engineer

- **Work Order:** `work-orders/CRM-002.md` **v1.2**, approved by the Architect at exact commit `0b954dcdb2bcaeed57184c92c264e604a651e374` (Issue #9). Read it in full first. It is the specification, and this brief only adds practical guidance. Where they differ, the WO wins.
- **Worktree:** `/srv/CRM/worktrees/CRM-002`, branch `forge/CRM-002`. The expected HEAD is `fa1ed80eed749cb2c0e7908ff72ad60a793e3e24` (main, containing the WO). Confirm it first. Do not modify `.forge/`.
- **Scope allowlist (from the WO):**
  - `migrate/**`, `deploy/migrate/**`, `tests/migrate/**`
  - `scripts/migrate.sh`
  - `docs/MIGRATION.md`, `security/EXTERNAL_CODE_REGISTER.yaml`
  - the usage section of `README.md`

  Nothing else. In particular, do not touch `work-orders/`, `docs/MIGRATION-DECISIONS.md`, `docs/SALESFORCE-*.md` or `DECISIONS.md`.
- **Inputs you may read:** everything under `docs/` and `work-orders/`. The source-field contract in WO Change 1 is authoritative for object and field names.

## What to build (WO Changes 1–7), with practical guidance

1. **`migrate/contract/salesforce-fields.json` (contract version 2).**
   - The objects and fields are exactly as in the WO table. Expand `Shipping{…}`, `Billing{…}` and `Mailing{…}` into their component fields.
   - Per object: `ownerCheck`, `softDelete` and `changeKey`, as in the WO. Per field: `purpose` (an R/M reference), `type`, `referenceTo` for references, and `required`.
   - `required: false` applies exactly to the fields listed in the WO: `Opportunity_Service__c`, `Post_code__c`, `Key_Information__c`, `IsArchived`, `MasterRecordId`, `MessageIdentifier` and `ThreadIdentifier`.
   - Use plausible Salesforce types. Where you are unsure of a standard type, choose the documented Salesforce type and record the uncertainty in `docs/MIGRATION.md` as "to be confirmed at L1". `contract-check` compares types, so a wrong type fails safe.
2. **Package layout.**
   - Entry point: `migrate/bin/crm-migrate.py`. Library: `migrate/lib/crm_migrate/…`.
   - The entry script must work under `python -I -B` with **no** reliance on the working directory, the script's directory or `PYTHONPATH`. It inserts exactly one absolute path, computed **from a constant**, into `sys.path`. Use `/opt/crm-migrate/lib`, with a guarded fallback derived from `os.path.realpath(__file__)` only for the test copy, so the subprocess test in Change 6 can run from a temporary copy.
   - Design the fallback so that a planted `crm_migrate/` in the current working directory can never win. `sys.path[0]` must be the library directory.
   - Modes: `contract-check`, `count`, `extract`, `reconcile`, and `selftest` (with `--quick`), which runs the synthetic suite end to end through the fake transport and writes to a given output directory.
   - Suggested modules (adjust as needed):
     - `contract.py` (load, validate, build SOQL);
     - `client.py` (`SalesforceClient`, the allowlist, origin rules);
     - `transport.py` (the `Transport` protocol and `HttpsTransport`);
     - `auth.py` (client credentials only);
     - `metadata.py` (the gate);
     - `extract.py` (the reconciled baseline);
     - `reconcile.py`;
     - `manifest.py`;
     - `hostcheck.py`;
     - `log.py`, a counts-only logger that never emits record values;
     - `cli.py`.
3. **Read-only client (WO Change 3).**
   - The allowlist is checked in `SalesforceClient` **and** again in `HttpsTransport`. Use exact method and path patterns: anchored regexes, API version `v\d+\.\d+`, and object names validated against the contract.
   - Refuse any query string on `describe`.
   - For `query` and `queryAll`, the only parameter is `q`.
   - For `deleted/`, the only parameters are `start` and `end`, in ISO-8601.
   - Origin: exact match. No redirect is followed (raise on any 3xx). No proxy: use `http.client.HTTPSConnection` directly, never `urllib`. Use an SSL context with verification and a minimum of TLS 1.2.
   - Limit response size, and never log an error body.
   - **Authentication: OAuth client credentials only.** POST to `{origin}/services/oauth2/token` with `grant_type=client_credentials`. Refuse any other grant type, and refuse SOAP outright.
4. **Reconciled baseline (WO Change 2, `extract`).**
   - Follow the WO algorithm exactly:
     - pass 0;
     - catch-up passes using `SystemModstamp >= W - overlap`;
     - the quiet-window stop;
     - verification with counts from both `query` and `queryAll`, plus an id-only `queryAll`;
     - the status `RECONCILED`, `RECONCILED_WITH_DRIFT` or `INCOMPLETE`.
   - `T_start` comes from the server's `Date` header. Never use the local clock for watermarks.
   - SOQL datetime literals use the format `YYYY-MM-DDThh:mm:ssZ`.
   - `extract` always runs the metadata gate first and builds SOQL only from the effective contract.
   - Output files are gzip JSONL, with umask 077 and mode 0600. The run directory must be new and empty. Never overwrite.
5. **Reconcile (WO Change 2, `reconcile`).**
   - Implement every relation, the owner classes, fill rates and the six deletion classes exactly as tabled.
   - An unexplained absence is **never** counted as deleted.
   - The output is counts only.
6. **Container (WO Change 4).**
   - `deploy/migrate/compose.json` defines:
     - project `crm-migrate`;
     - service `crm-migrate`, on its own project network `crm-migrate-net`;
     - service `crm-migrate-selftest`, with `network_mode: none`.
   - Image: `python:3.13.9-slim-trixie@sha256:326df678c20c78d465db501563f3492d17c42a4afe33a1f2bf5406a1d56b0e86`.
   - `user: "64021:64021"`, `read_only: true`, `cap_drop: [ALL]`, `security_opt: ["no-new-privileges:true"]`, and `tmpfs` `/tmp:noexec,nosuid,size=64m`.
   - Mounts: `migrate/` is read-only at `/opt/crm-migrate`. The only read-write bind is the per-run directory, at `/out`. Take its host path from an env variable such as `${CRM_MIGRATE_RUN_DIR:?…}`, which `migrate.sh` sets per run.
   - `env_file`: `/srv/CRM/runtime/migrate/env`, for the live service only. The selftest service gets no env file.
   - `crm-` names, no `container_name`, no `ports`, nothing external.
   - Add `deploy/migrate/env.example`, with names only:
     - `CRM_SF_ORIGIN`;
     - `CRM_SF_CLIENT_ID`;
     - `CRM_SF_CLIENT_SECRET`;
     - `CRM_SF_API_VERSION`.
7. **`scripts/migrate.sh`.**
   - Subcommands: `selftest`, `contract-check`, `count`, `extract`, `reconcile` and `credentials`.
   - Its guards follow the existing project pattern:
     - refuse unless run as root;
     - refuse unless the target is `migrate`;
     - refuse unless `/srv/CRM/runtime/migrate` and `…/snapshots` exist, are root-owned and are mode `0700`;
     - refuse if **any** variable named in `env.example` is exported in the calling shell;
     - run `docker compose` under `env -u <every env-file name> …`, so the process environment cannot override the env file;
     - refuse an existing run directory;
     - refuse if UID 64021 belongs to an existing host account (`getent passwd 64021`).
   - **Per run:**
     1. create `snapshots/<UTC id>/` as `64021:64021`, mode `0700`;
     2. run the container;
     3. **seal**: `chown -R root:root`, directories `0700`, files `0400`;
     4. re-verify the manifest checksums;
     5. fail if the seal or the verification fails.
   - `credentials` prompts with `read -rs`. It writes the env file atomically (a temporary file in the same directory with mode 0600, then `mv -T`) and never echoes values.
   - Put the ownership, mode, name and UID decisions in `migrate/lib/crm_migrate/hostcheck.py` as **pure functions** that take `os.stat_result`-like values and strings. Call them from the script, for example with `python3 -I -B /srv/CRM/main/migrate/bin/crm-migrate.py hostcheck …`, or implement the same logic directly in bash. Either way, the logic must be unit-tested without root.
8. **Fake and fixtures (WO Change 5).**
   - `FakeSalesforceTransport` lives in `tests/migrate/`. It is in-memory, with **no sockets and no loopback**: the specialist sandbox denies both, so any test that opens a socket fails.
   - Implement the mutation hooks and fixtures exactly as the WO lists them.
   - All values are synthetic: `example.test` domains, and a sentinel marker in every record, for example `SENTINEL-7f3a`.
   - Use Salesforce-shaped 18-character ids, generated deterministically with correct key prefixes (`001` Account, `003` Contact, `006` Opportunity, `005` User, `00G` Group, `00T` Task, `00U` Event, `02s` EmailMessage, and so on).
9. **Tests (WO Change 6) under `tests/migrate/`.**
   - They must run with `python3 -I -B -m unittest discover -s tests/migrate -t . -v` from the repository root. Make `tests/` and `tests/migrate/` packages, with an `__init__.py` that adds `migrate/lib` to `sys.path` by absolute path.
   - Cover every item in Change 6.
   - The isolated-mode subprocess test copies `migrate/` into a temporary directory, creates a separate working directory that contains a planted `crm_migrate/__init__.py` and a planted `json.py` (each writes a marker file or raises), then runs `sys.executable -I -B <copy>/bin/crm-migrate.py selftest --quick --out <tmp>`. It asserts:
     - success;
     - no marker file;
     - the output status is `RECONCILED`.
   - Every policy rule (Compose, hostcheck, the allowlist) must have a deliberately broken fixture that makes it fail. Report this non-vacuity evidence.
   - Test the no-content-in-logs rule by capturing stdout, stderr and the logger in every mode, including error paths, and asserting that the sentinel never appears.
10. **Docs.**
    - `docs/MIGRATION.md`, the operator guide. It covers everything the WO lists, and must explicitly state:
      - the permanent-deletion limit of `queryAll`;
      - that the overlap is an assumption.
    - `security/EXTERNAL_CODE_REGISTER.yaml`: add a candidate entry `python` with:
      - version `3.13.9-slim-trixie`;
      - digest `sha256:326df678c20c78d465db501563f3492d17c42a4afe33a1f2bf5406a1d56b0e86`;
      - licence `PSF-2.0`;
      - usage "crm-migrate extractor (CRM-002)";
      - `approval: none`.

      Keep the existing entries byte-identical.
    - `README.md`: add one short "Migration extractor" usage section and change nothing else.

## Constraints
- No network, no loopback, no Docker, no browser and no root. Python **standard library only**. Do not download anything.
- **No Salesforce access of any kind.** No real data, no secrets, no real hostnames (use `example.my.salesforce.com` in tests), no IP addresses and no staff, firm or customer names in the repository.
- Do not run `scripts/migrate.sh` beyond `bash -n`. It needs root and Docker; it is exercised at the operator stage O1, which is not part of this run.

## Tests you must run and report
- `python3 -I -B -m unittest discover -s tests/migrate -t . -v`, with exact counts.
- `bash -n scripts/migrate.sh`.
- Non-vacuity evidence for each policy rule.
- `git diff --stat` against the base, to show that only allowlisted paths changed.

Finish in the Engineer final message format.
