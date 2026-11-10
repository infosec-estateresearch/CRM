# Migration extractor (`crm-migrate`): operator guide

- **Work Order:** CRM-002 v1.2. **Status:** delivered for review. Nothing here authorises any Salesforce access. Each live stage (L1, L2, L3) needs its own recorded PO authorisation on Issue #9.
- **What it is:** a containerised, read-only Salesforce extractor. Python 3.13, standard library only, in the pinned image `python:3.13.9-slim-trixie@sha256:326df678c20c78d465db501563f3492d17c42a4afe33a1f2bf5406a1d56b0e86`.
- **What it produces:** a *reconciled baseline* with an honest completeness status. It does not claim a transaction-consistent snapshot. It also produces a counts-only reconciliation report.
- **Administrator setup:** see `docs/SALESFORCE-ADMIN-SETUP.md`.

## Layout

| Path | Contents |
|---|---|
| `migrate/contract/salesforce-fields.json` | Source-field contract, version 3 (CRM-002-U, L1 corrections). SOQL is built only from this file. The tool refuses any other `contractVersion` with `contract_version`. |
| `migrate/bin/crm-migrate.py` | Entry point. It runs only as `python -I -B` and inserts exactly one library path. |
| `migrate/lib/crm_migrate/` | The package. `policy.py` holds the request allowlist, `client.py` the single Salesforce client, `transport.py` the only real transport, and `hostcheck.py` the host guard decisions. |
| `deploy/migrate/compose.json` | Compose project `crm-migrate`, with services `crm-migrate` (live) and `crm-migrate-selftest` (no network). |
| `deploy/migrate/env.example` | Variable names only. |
| `scripts/migrate.sh` | The operator wrapper. Root only. |
| `tests/migrate/` | Unit tests. They need no network, no loopback, no Docker and no root. |

## Modes

Always run the tool through `scripts/migrate.sh`, as root, on DOCKER1. The optional first argument is the target, which must be `migrate`.

| Command | Service | Reads | Writes (in a new run directory) |
|---|---|---|---|
| `migrate.sh selftest [--quick]` | `crm-migrate-selftest` (`network_mode: none`, no env file) | The in-memory synthetic org only | Two synthetic snapshots, a reconciliation and `selftest.json`. The full run adds every mutation scenario. |
| `migrate.sh contract-check` | `crm-migrate` | `describe` for each contract object. **No records.** | `contract-check.json` (counts and flags), `describe.json` (types, `referenceTo`, picklist values), `manifest.json` |
| `migrate.sh count` | `crm-migrate` | The metadata gate, then `SELECT COUNT()` through both `query` and `queryAll`. No records. | `contract-check.json`, `counts.json`, `manifest.json` |
| `migrate.sh extract [--passes N] [--overlap-minutes M]` | `crm-migrate` | The metadata gate, then records for the effective contract fields | The snapshot (see below) |
| `migrate.sh reconcile <snapshot-id> [<previous-id>]` | `crm-migrate-selftest` (no network, no secrets) | One or two sealed snapshots | `report/reconciliation.json`, `report/reconciliation.md`, `report/manifest.json` |
| `migrate.sh credentials` | none | The operator's keyboard | `/srv/CRM/runtime/migrate/env` |

`count` and `extract` both run the metadata gate first. If the gate fails, no data query is issued.

**Metadata gate.** For each contract object, the gate requires all of the following:
- `queryable` and `retrieveable` are true;
- `createable`, `updateable` and `deletable` are false. The only exception is a waiver listed in the contract with `approvedBy: Architect`, and none is granted. If `User` reports `updateable`, the gate fails and records an L1 finding for decision;
- every `required` field is present, with the expected type and `referenceTo`.

`referenceMatch: superset` marks the polymorphic fields whose `referenceTo` list depends on the org (`Task.WhatId`, `Event.WhatId`, `EmailMessage.RelatedToId`, `EmailMessageRelation.RelationId` and `Note.ParentId`). For those, the listed targets must be present, and extra targets are allowed. A missing optional field is left out of the SOQL and reported as `unavailable`.

**Mismatch report (CRM-002-U).** In `contract-check.json`, every `type_mismatch` and `reference_mismatch` entry is an object, not a bare field name:
- `field`: the contract field name;
- `expected`: the contract type;
- `described`: the type name Salesforce describes;
- `expectedReferenceTo`: the contract targets (reference fields only);
- `referenceTo`: the described target object names (only when `described` is `reference`).

Example: `{"field": "X", "expected": "boolean", "described": "picklist"}`. These values are schema identifiers only. Any described value that does not match `[A-Za-z][A-Za-z0-9_]{0,79}` is recorded as `"unrecognised"`, and so is a `referenceTo` that is not a list. Log lines (`gate_object`) keep counts only.

**Exit codes:**

| Code | Meaning |
|---:|---|
| 0 | Success, or `RECONCILED` |
| 2 | Usage or configuration error |
| 3 | Metadata gate failed |
| 4 | Refused request, origin, redirect or HTTP error |
| 5 | Snapshot checksum or format error |
| 10 | `RECONCILED_WITH_DRIFT` |
| 11 | `INCOMPLETE` |
| 12 | Selftest failed |
| 20 | `migrate.sh` could not seal the run directory |
| 21 | The manifest checksums did not re-verify after sealing |

## What the client may do

All HTTP goes through `SalesforceClient`. The allowlist is checked before the transport is called, and checked again inside `HttpsTransport`. The client may only:
- `POST {origin}/services/oauth2/token`, with exactly `grant_type=client_credentials`, `client_id` and `client_secret`. There is no username/password flow and no SOAP;
- `GET {origin}/services/data/vNN.N/` followed by one of:
  - `query/?q=` or `queryAll/?q=`, where `q` is the only parameter and must be one of the generated SOQL shapes, with contract objects and fields only;
  - `query/<locator>`, a `nextRecordsUrl`, which must be relative and match `^/services/data/v\d+\.\d+/query/[A-Za-z0-9-]+$`;
  - `sobjects/<ContractObject>/describe/`, with no query string;
  - `sobjects/<ContractObject>/deleted/?start=&end=`, with ISO-8601 UTC values only;
  - `limits/`.

**Origin rules:**
- The origin is exactly `https://<mydomain>.my.salesforce.com`, or `https://<mydomain>.sandbox.my.salesforce.com`.
- The token's `instance_url` must equal the origin exactly.
- Any 3xx response is an error, and no redirect is followed.
- No proxy is used. `http.client.HTTPSConnection` is used directly, and environment proxy settings are ignored.
- TLS 1.2 is the minimum, and certificates and hostnames are always verified.
- Responses are limited to 64 MiB.
- Error bodies are never logged: only the HTTP status and the Salesforce `errorCode` are kept.

**Logs.** Logs are counts only. Every line has the form `crm-migrate event=<name> key=value`. The values are numbers, statuses, error codes, or contract object and field names. Anything else is printed as `<redacted>`.

## The reconciled baseline (`extract`)

1. **Pass 0.** `T_start` is taken from the server's `Date` header, never from the local clock. Each object is then read fully through `queryAll`, ordered by `Id`, paging only through `nextRecordsUrl`.
2. **Catch-up passes 1 to N** (N defaults to 3). Each pass queries `SystemModstamp >= W - overlap`, where W is the start of the previous pass. The overlap defaults to 15 minutes. Rows are merged by `Id`, and the latest `SystemModstamp` wins. The run stops early after a quiet pass, meaning one in which no row changed.

   The overlap is an **assumption**, not a guarantee. It exists because Salesforce can make a row visible after a query that already covered its `SystemModstamp`, for example through long transactions or clock skew. A row that becomes visible later than the overlap allows is detected at verification and makes the run `INCOMPLETE`. It is never silently missed. The overlap is recorded in the manifest.
3. **Verification.** For each object, the run takes:
   - `COUNT()` through `query` and through `queryAll`;
   - an id-only `queryAll` (`SELECT Id, IsDeleted, SystemModstamp`);
   - for `replicateable` objects, the deleted-records log for the last 29 days.

   A row that is in the baseline but no longer returned counts as deleted during the run **only** if the deletion log shows it. Otherwise it is kept, and the object is `INCOMPLETE`.

   The verification reads are assumed to be free of concurrent change. A change that lands between the verification `COUNT()` and the id-only query shows up as a mismatch, and the run fails safe to `INCOMPLETE`.
4. **Output.** The run directory holds:
   - `objects/<Object>.jsonl.gz`, sorted by Id, holding only the effective contract fields;
   - `deleted/<Object>.jsonl.gz`, ids and deletion dates for replicateable objects;
   - `describe.json` and `contract-check.json`;
   - `passlog.jsonl`, counts only;
   - `manifest.json`, holding `T_start`, the pass times, the overlap, N, the API version, the exact SOQL for every pass, the contract version and sha256, the effective contract, counts and durations per object and pass, the status and the deletion-log window. It also lists the sha256 of every other file.

   The gzip output is deterministic, so the same data gives the same checksums.

## Completeness statuses

| Status | When | Use |
|---|---|---|
| `RECONCILED` | The last catch-up pass was quiet, and the counts and id sets match the baseline exactly | May be loaded |
| `RECONCILED_WITH_DRIFT` | Changes were still arriving after N passes, or arrived after the last pass. The drift is reported per object and per pass, and so is the residual. | Needs PO acceptance, or a later delta run |
| `INCOMPLETE` | Any error, a gate failure, an unexplained missing or new row, a `SystemModstamp` regression, or a count or id-set mismatch | **Never** used for a load. It is kept for diagnosis only. |

The overall status is the worst object status.

## Deletion classes

`reconcile` keeps these classes separate and never merges them:

| Class | Source | Meaning |
|---|---|---|
| `current` | `IsDeleted = false` | Exists now |
| `soft_deleted_available` | `queryAll`, `IsDeleted = true`, no `MasterRecordId` | In the Recycle Bin now |
| `merged` | Soft-deleted with `MasterRecordId` set | Merged into a surviving record, not lost |
| `deletion_evidence` | `sobjects/<Object>/deleted/` (replicateable objects only, about 30 days) | Ids and deletion dates only. Objects that are not replicateable report `unavailable`. |
| `absent_since_previous_explained` | `current` in the previous snapshot, not `current` now, and matched by one of the classes above | Deletion confirmed. The breakdown says which class explained it. |
| `absent_since_previous_unexplained` | `current` in the previous snapshot, not `current` now, with no evidence | **Not** treated as deleted. Possible causes are a permanent deletion outside the log window, a sharing or permission change, or an extraction fault. Downstream keeps such records, flagged `sfAbsentUnverified`. |

`queryAll` **cannot** return permanently deleted records. That covers rows emptied from the Recycle Bin, rows past its retention, and hard-deleted rows. Older deletion history is unavailable. The deleted-records log covers only about 30 days, and only for replicateable objects.

`reconcile` also reports, as counts only:
- the extracted counts against the verification counts;
- duplicate ids;
- orphans for each relation:
  - `Account.ParentId`, `Contact.AccountId` and `Opportunity.AccountId`;
  - OpportunityContactRole to Opportunity and to Contact;
  - Task and Event `WhatId`, `WhoId` and `AccountId`, resolved by key prefix against the describe `referenceTo`;
  - `EmailMessage.ActivityId`;
  - EmailMessageRelation to EmailMessage, and `RelationId` to Contact or User. Unmatched addresses are counted separately, not as orphans;
- owner classes, for `ownerCheck` objects only: active user, inactive user, queue or group (`00G`, only where describe allows Group), and unresolved. Only unresolved owners are orphans;
- the fill rate per available field. An unavailable field reports `unavailable`, not 0%;
- the drift per pass.

## Storage model and sealing

- `/srv/CRM/runtime/migrate` and `/srv/CRM/runtime/migrate/snapshots` must exist, be owned `root:root` and be mode `0700`. `migrate.sh` refuses to run otherwise.
- The containers run as UID/GID `64021:64021`. `migrate.sh` refuses to run if that UID or GID belongs to a host account or group (`getent`).
- **For each run,** `migrate.sh`:
  1. creates `snapshots/<UTC id>-<mode>/`, owned `64021:64021` with mode `0700`. It refuses if the directory already exists;
  2. bind-mounts only that directory, read-write, at `/out`. `migrate/` is mounted read-only at `/opt/crm-migrate`;
  3. runs the container: read-only root filesystem, `cap_drop: ALL`, `no-new-privileges`, and a `noexec` `/tmp` tmpfs;
  4. **seals** the directory: `chown -R root:root`, directories `0700`, files `0400`. It refuses symlinks and special files;
  5. re-verifies every checksum in the manifest. If the seal or the verification fails, it exits with 20 or 21.
- Inside the container the tool sets umask `077` and creates files `0600` with `O_EXCL`. It never overwrites a file and only writes into an empty directory.
- `reconcile` copies its input snapshots into `<run>/input/` (root-only tree, readable by the run UID during the run), and deletes that copy before sealing.
- Secrets are kept in `/srv/CRM/runtime/migrate/env` (`root:root`, `0600`), which only the live service reads, through `env_file`.
- `migrate.sh credentials` prompts with `read -rs`, writes a temporary file in the same directory with mode `0600`, then runs `mv -T`. It never echoes, logs or passes the values as arguments.
- `migrate.sh` refuses to run if any variable named in `env.example` is exported in the shell. It runs `docker compose` under `env -u <every name>` and with `--env-file /dev/null`.

**Check after O1:** `runuser -u nobody -- ls <run dir>` must fail.

## Retention and disposal

- Snapshots hold customer data from L3 onward. They stay on DOCKER1 under `/srv/CRM/runtime/migrate/snapshots` (root-only) and never enter Git, GitHub, CI or ForgeV2 prompts and scratch.
- The retention period and disposal method are set in the PO's L3 data-scope authorisation. If it sets none, nothing is extracted.
- **Disposal:** as root, run `rm -rf --one-file-system /srv/CRM/runtime/migrate/snapshots/<id>`, then record the snapshot id and date on Issue #9. Delete `INCOMPLETE` snapshots once they have been diagnosed.
- **Credential disposal** (see the admin guide, step 7): remove `/srv/CRM/runtime/migrate/env`, then deactivate the integration user and the External Client App.
- Only sanitised, counts-only output is published (`reconciliation.json` / `.md`), together with the completeness status.

## Live-stage gates

| Stage | Precondition | Command | Evidence |
|---|---|---|---|
| **O1** (synthetic) | Matt's operator authorisation, and `/srv/CRM/runtime/migrate{,/snapshots}` created root-owned `0700` | `migrate.sh selftest` | The import works under `-I -B` on the read-only mount; the run directory is `64021`-owned during the run and sealed `root 0700/0400` afterwards; `runuser -u nobody` cannot list or read it; the checksums re-verify; the status is `RECONCILED`. |
| **L1** (metadata only) | O1 passed; the integration user and External Client App are set up; `migrate.sh credentials` has been run; the PO's L1 authorisation is on #9 | `migrate.sh contract-check` | The app type; every required field is available; the optional-field availability; no object is createable, updateable or deletable. No records are read. |
| **L2** (counts only) | L1 clean, plus the PO's L2 authorisation | `migrate.sh count` | `query` and `queryAll` counts compared with the inventory. Large gaps are resolved before L3. |
| **L3** (records) | The PO's data-scope authorisation: objects, date range, purpose, storage, retention, disposal | `migrate.sh extract`, then `migrate.sh reconcile <id> [<previous-id>]` | The sanitised reconciliation, with the completeness status |

## Contract v3: L1 corrections (2026-11-10)

L1 (`contract-check --auth soap-legacy`, schema only) failed the v2 gate on 3 of 12 objects. Contract v3 makes these changes, and no others:

| Object.field | Contract v2 | Contract v3 |
|---|---|---|
| `Account.Interested_in_integration__c` | boolean, required | picklist, required |
| `EmailMessageRelation.RelationAddress` | email, required | string, required |
| `Opportunity.Post_code__c` | string, optional | removed. In Salesforce it is a self-lookup to Opportunity (`Post_code__r`), not a postcode. |
| `Opportunity.Key_Information__c` | textarea, optional | removed. There is no such field in Salesforce. |

The removals follow the data-minimisation rule: neither field carries the data its purpose names.

## To be confirmed at L1

The tables below are the original v2 assumptions; rows corrected at L1 are marked. These contract details come from Salesforce documentation and the inventory, not from the live org. `contract-check` compares them, so a wrong guess fails safe and is fixed in the contract.

**Custom field types:**

| Field | Type in the contract |
|---|---|
| `Account.TLP__c` | picklist |
| `Account.Interested_in_integration__c` | ~~boolean~~ picklist (v3, L1) |
| `Account.Bankruptcy_Special_Rate__c` | boolean |
| `Opportunity.Loss_Reason__c` | picklist |
| `Opportunity.Paid_geneology_enquiry__c` | picklist |
| `Opportunity.Opportunity_Service__c` | picklist |
| `Opportunity.Post_code__c` | ~~string~~ removed in v3 (L1: self-lookup reference) |
| `Opportunity.Key_Information__c` | ~~textarea~~ removed in v3 (L1: absent) |

**Standard types and references:**

| Field | In the contract |
|---|---|
| `Task.Subject`, `Event.Subject` | combobox |
| `EmailMessage.ToAddress`, `EmailMessage.CcAddress` | string |
| `EmailMessageRelation.RelationAddress` | ~~email~~ string (v3, L1) |
| `Task.CallDisposition` | string |
| `UserRole.ParentRoleId` | references `[UserRole]` |
| `Profile.UserLicenseId` | references `[UserLicense]` |
| `Task.OwnerId` | references `[Group, User]` |
| `Event.OwnerId` | references `[Calendar, User]` |
| `Task.WhoId`, `Event.WhoId` | reference `[Contact, Lead]` |
| `EmailMessage.ParentId` | references `[Case]` |

**Other details:**
- The `deleted/` parameter format is sent as `YYYY-MM-DDThh:mm:ssZ`.
- Which objects are `replicateable` in this org.
- The REST API version to configure (`CRM_SF_API_VERSION`).

## Notes for reviewers

- The synthetic org and `FakeSalesforceTransport` live in `migrate/lib/crm_migrate/synthetic.py`, because `selftest` must run in the container, where only `migrate/` is mounted. `tests/migrate/fake_salesforce.py` re-exports them. They are in memory only, with no sockets. Every record carries the marker `SENTINEL-7f3a`, and every domain is `example.test`.
- Run the tests from the repository root with `python3 -I -B -m unittest discover -s tests/migrate -t . -v`.

## Network egress

`crm-migrate-net` is a **plain Docker bridge network**. It does not restrict destinations
by itself. The destination is restricted by the client policy (`RequestPolicy`, enforced in
`SalesforceClient` and again in `HttpsTransport`): one origin (`CRM_SF_ORIGIN`), port 443,
HTTPS only, no proxies or redirects. Under `--auth soap-legacy` the constant SOAP login host
is the only addition. Host-firewall changes are prohibited by a PO standing rule, so no
firewall rule backs this up.

## Temporary legacy credential

**Authority.** The PO priority override of 2026-11-10, recorded on Issue #9 (CRM-002-S). It
authorises temporary reuse of the existing Salesforce username and password for the read-only
migration only. Every request must pass the read-only allowlist. Only the trusted operator
handles the credential and runs the extraction. No secret goes anywhere public, or into a
prompt or a log.

**Risk.** The legacy identity **can write**. Only the request allowlist limits it. The
allowlist gains exactly two SOAP partner entries, `login` (to the constant
`login.salesforce.com`, or `test.salesforce.com` with `--sandbox`) and `logout` (to the
origin `serverUrl` gives). Each is matched on host, path, `SOAPAction`, and a body
byte-identical to a fixed template. No other SOAP operation can be expressed. The
`serverUrl` origin must equal `CRM_SF_ORIGIN` exactly, otherwise the run aborts before any
REST call. The session id is used only as the Bearer token for that origin and is held only
in memory. SOAP faults are reduced to `faultcode` and the first `exceptionCode` token, each
from a fixed set: a `faultcode` outside `auth_soap.FAULTCODES` is reported as `unrecognised`,
and an `exceptionCode` (or REST `errorCode`) outside `errors.SF_ERROR_CODES` as `UNKNOWN`.
`CountsLog` re-checks `sf_error` against `errors.SF_ERROR_CODES` before writing a log line
and writes `UNKNOWN` for anything else.
SOAP responses must be strict UTF-8 (no UTF-16/UTF-32, with or without BOM, and no other
declared `encoding`). Any `<!DOCTYPE` or `<!ENTITY` in the decoded text is refused, and the
expat parser itself raises on any DTD, entity declaration or external entity. A failed
`logout` is logged as `soap_logout ok=false code=<exception class>` and never changes the
exit code.

**Operator-only procedure** (root, on the host):

1. `/srv/CRM/runtime/migrate/env` holds only `CRM_SF_ORIGIN`, `CRM_SF_API_VERSION`
   (31.0 to 64.0; the tool defaults to `59.0`) and `CRM_LEGACY_ENV_FILE`; see
   `deploy/migrate/env.legacy.example`. `CRM_LEGACY_ENV_FILE` is the absolute path of the
   existing ELT env file. The path is never committed. While it is empty the legacy commands
   refuse ("not configured"). `hostcheck` requires it to be absolute, with no symlinked
   component (`realpath` equals the path), and to name a regular file owned by root that is
   not group- or world-writable.
2. Optional waiver, `/srv/CRM/runtime/migrate/waiver.json` (root:root, `0600`):
   `{"authorisation": "<Issue #9 comment URL>", "identity": "legacy-eric", "expires": "YYYY-MM-DD"}`.
   `expires` must be today or later, and at most 30 days ahead. If the waiver is expired,
   malformed or has extra keys, the run fails before any request. If it is missing, a
   write-capable identity fails `contract-check`, and no data query runs. The waiver applies
   to `--auth soap-legacy` only; client-credentials mode ignores it completely. The manifest
   and the report state `identity: write-capable (waived: <url>)` and `writable_objects`.
3. `scripts/migrate.sh --auth soap-legacy contract-check` (then `count`, then `extract`).
   The script reads only `NIF_SRC_SALESFORCE_USER` and `NIF_SRC_SALESFORCE_PASS` from the
   existing ELT env file. It opens the file read-only and never follows a symlink.
   `hostcheck.parse_legacy_env` (CRM-002-T) reads the two values exactly as the file's only
   consumer, the ERiC loader, reads them. The file is never sourced by a shell. For each line,
   the parser strips it, skips it if it is empty, starts with `#` or has no `=`, splits it
   at the first `=`, and strips the key and the value. There is no quote, escape, comment
   or shell processing, so the value is literal: a later `=` and any `#` are part of it, and
   so are the characters `;&|<>()#!*?{}[]~^%@=+,.:/-_`. The parser is stricter than the
   consumer where a reading could be ambiguous:
   - The whole file is refused if it holds any CR character, any other line break that
     Python's `splitlines` honours besides LF, or a non-comment line ending in a backslash.
   - A target value is refused if it is empty, or holds a quote, a backtick, `$`, a
     backslash, any whitespace or control character, or any non-printable character. So
     `PASS=abc # x` is refused, because the consumer would read `abc # x`.
   - A duplicate definition of a target name is refused, where the consumer would take the
     first one. So is an `export ` prefix, which the consumer would read as a different key.
   - Other lines are not interpreted beyond the whole-file checks.

   Errors give only a line number and a reason code (`refused-character`, `empty-value`,
   `duplicate-definition`, `export-prefix`, `missing-user`/`missing-pass`, or the
   whole-file reason). They never give a value or a character class. The script pipes the
   two values as JSON on stdin to
   `docker compose run -T --rm crm-migrate … --auth soap-legacy --credentials-stdin`. The
   values are never written under `/srv/CRM/runtime/migrate`, into arguments or into the
   environment. The script records the file's sha256 and mtime before and after the run, and
   fails (exit 22) if either changed. The run's output is in `snapshots/<id>/run/`. The
   waiver copy used is in `snapshots/<id>/input/`.

**Retirement.** Disable the adapter as soon as extraction is complete, or when the dedicated
read-only identity exists. In any case, do so before Summer '27, when Salesforce retires SOAP
`login()`. To retire it, remove `auth_soap.py`, the `soap-legacy` CLI and script paths, and
the waiver file.
