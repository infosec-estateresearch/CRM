# CRM-002, round 1: DevSecOps review

- **Worktree:** `/srv/CRM/worktrees/CRM-002`. It is read-only; don't touch any other path.
- **Candidate SHA:** `29c74a2936e2f3d6ea7c7fb04c88f8040cdb4c36`
- **Base SHA:** `fa1ed80eed749cb2c0e7908ff72ad60a793e3e24` (main, containing the approved WO; WO commit `0b954dcdb2bcaeed57184c92c264e604a651e374`)
- **Scratch directory:** `/srv/CRM/worktrees/.forge-scratch/CRM-002`

Assess the candidate against the Work Order below, independently, and according to your role.

**This is the security-critical component.** The extractor will later run against the live Salesforce org. Treat these as the highest-priority checks:
- the read-only request allowlist (`migrate/lib/crm_migrate/policy.py`, `client.py`, `transport.py`);
- the origin and redirect rules;
- the no-content-in-logs rule.

Try to construct a request that writes, deletes or leaves the configured origin and still passes the policy. Treat any such bypass as **blocking**.

**Facts from the Project Lead:**
- The specialist sandbox has no network, loopback, Docker or root. Operator stage O1 (the real container and sealing) is outside this run.
- The engineer's round 1 timed out. The work was completed and verified in round 2, so the candidate is the combined result.
- On the README scope question the engineer raised: the PL accepts a new "Migration extractor" section as "the usage section of README.md".

## Work Order (verbatim, `work-orders/CRM-002.md` v1.2 at the base SHA)

WO: CRM-002
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main
BROWSER: no

# CRM-002 — Read-only Salesforce extractor (`crm-migrate`), source-field contract and reconciled baseline (synthetic fixtures only)

- **Version:** v1.2, 2026-11-10.
  - v1.0 was reviewed at `5c45d0a` and came back CHANGES REQUESTED (Architect, recorded on #8 and #9).
  - v1.1 makes the seven targeted corrections, listed in § Revision v1.1. The objectives, scope and authorisation gates are unchanged.
  - v1.2 aligns authentication with the verified existing ERiC integration (§ Existing integration). Nothing else changes.
- **Status:** DRAFT. It needs CGPT's exact-version approval on Issue #9, naming this path and the commit that contains it.
- **Parent PBI:** CRM-PBI-005, part 1 (M1–M3, R18, R25).
- **Governing FOUNDRY:** `5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0`.
- **Engine:** ForgeV2 `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, plugin 0.3.0, from `/srv/forgev2/plugin`, run as `forgev2-pl`.
- **`KNOWN_COMMIT`:** the commit named in the approval comment.
- **Inputs:**
  - `docs/SALESFORCE-DATA-INVENTORY.md` (accepted 2026-11-10, PR #7);
  - `docs/MIGRATION-DECISIONS.md`;
  - `docs/SALESFORCE-ADMIN-SETUP.md`;
  - `docs/REQUIREMENTS-TRACEABILITY.md`.

## Outcome

A containerised extractor, `crm-migrate`, that:
- reads Salesforce **only**;
- selects fields explicitly from a versioned source-field contract, after validating it against live metadata;
- produces a **reconciled baseline** with an honest completeness status, instead of claiming a transaction-consistent snapshot;
- writes checksummed snapshots into operator-restricted storage;
- produces a counts-only reconciliation report covering counts, relationships, fill rates, the deletion classes and drift.

It is built and proven entirely against **in-process synthetic fixtures**. This WO grants **no Salesforce access** and extracts **no customer record**. The live stages (§ Live stages) each need their own recorded PO authorisation.

## Revision v1.1 (Architect corrections)

| # | Correction | Where |
|---|---|---|
| 1 | External Client App with client credentials and a Run As read-only integration user. An existing Connected App is only a verified fallback. | Change 3, `docs/SALESFORCE-ADMIN-SETUP.md` |
| 2 | Reconciled baseline: catch-up passes with an overlap window, a quiet-window check, post-extraction counts and id sets, and a completeness status. Concurrent change is tested. | Change 2 (`extract`, `reconcile`), AC6 |
| 3 | Deletion classes. `queryAll` cannot return permanently deleted rows. Absence is never treated as deletion. | Change 2 (`reconcile`), AC7 |
| 4 | Isolated-mode layout: a fixed-path entry script, run as `python -I -B`, tested by subprocess and in the real container settings. | Change 4, AC9, O1 |
| 5 | A dedicated non-root UID writes into a per-run directory, which is then sealed root-only. The host parent directories stay root `0700`. | Change 4, AC10, O1 |
| 6 | No sockets in loop tests. An injected in-process transport replaces the `http.server` fake. | Changes 3 and 5, AC3 |
| 7 | Live metadata gate before SOQL; owner checks only where the metadata says they apply; exact-origin rules with no redirects. | Changes 1–3, AC2–AC4 |

## Existing integration (verified 2026-11-10, PO-authorised check)

| Item | Finding |
|---|---|
| Mechanism | ERiC's shared library call passes `security_token=""`, which selects **SOAP `login()`** (username and password) at `login.salesforce.com`, API **59.0**, the library default. The stored consumer key and secret are **never used**. |
| Test | One SOAP `login()`, then one global describe, 2026-11-10 17:04Z. **Login succeeded**: password not expired, production org, `userType=Standard`, server on My Domain. **API access works**: 831 objects visible. No records were read. |
| Privilege | The account can create, update or delete on **457 objects**, including User, Profile and UserRole. It is a full-licence, administrator-level identity, and its username does not look like a dedicated integration account. **Not suitable for CRM-002.** |
| Retirement | SOAP `login()` for API versions 31.0 to 64.0 is announced for retirement in **Summer '27**, and it is absent from API 65.0 onwards (Salesforce admin notice, recorded by ERiC on 2026-07-09). ERiC and WIP must migrate before then. |
| Connected App | A Connected App exists (the stored key has the Salesforce format), but its flows and policies are unverified because it has never been exercised. |
| Dependants | ERiC's `eric-sf-sync` (disabled), ERiC's `user_sync`, and **WIP's hourly and nightly Account sync**, which falls back to the ERiC credentials. |
| Current state | Both syncs have failed since the 2026-11-06 OS upgrade (`ModuleNotFoundError: pymysql` under python3 3.13). This is unrelated to Salesforce authentication. The last successful syncs were on 2026-11-06 at about 11:00. |

**Decision for CRM-002:**
- Reuse the org and its My Domain. Matt makes the setup changes with his own existing administrator login.
- Create **one** new identity: a read-only Salesforce Integration user, which is a free licence. It is designed so that ERiC and WIP can later move to it when they migrate off SOAP `login()`.
- Create **one** new External Client App for CRM-002, so it can be revoked independently.
- ERiC's credentials, app, timers and service are **not changed**.

## Change

1. **Source-field contract: `migrate/contract/salesforce-fields.json` (contract version 2).**
   - **Per object:**
     - the API name;
     - `ownerCheck` (true only where `OwnerId` exists and should resolve to User or Group);
     - `softDelete` (whether the object has `IsDeleted`);
     - `changeKey` (normally `SystemModstamp`).
   - **Per field:**
     - its purpose, as an R/M reference;
     - the expected type;
     - for references, the expected `referenceTo` list;
     - `required: true` or `false`.
   - SOQL is built **only** from this file:
     - object and field names must match `^[A-Za-z][A-Za-z0-9_]*$`;
     - `FIELDS(...)` and wildcards are refused;
     - compound address fields are never selected, only their components;
     - literals are generated from typed values, never from interpolated strings.
   - **Objects and fields, version 2:**

   | Object | Fields |
   |---|---|
   | `User` | Id, FirstName, LastName, Name, Email, Username, Alias, IsActive, ProfileId, UserRoleId, UserType, CreatedDate, LastLoginDate, SystemModstamp |
   | `Profile` | Id, Name, UserLicenseId, SystemModstamp |
   | `UserRole` | Id, Name, ParentRoleId, SystemModstamp |
   | `Account` | Id, Name, ParentId, MasterRecordId, Type, Industry, Phone, Website, Description, AccountSource, OwnerId, `Shipping{Street,City,State,PostalCode,Country}`, `Billing{Street,City,State,PostalCode,Country}`, NumberOfEmployees, LastActivityDate, `TLP__c`, `Interested_in_integration__c`, `Bankruptcy_Special_Rate__c`, IsDeleted, CreatedDate, CreatedById, LastModifiedDate, SystemModstamp |
   | `Contact` | Id, AccountId, MasterRecordId, FirstName, LastName, Salutation, Title, Department, Email, Phone, MobilePhone, `Mailing{Street,City,State,PostalCode,Country}`, OwnerId, IsDeleted, CreatedDate, CreatedById, LastModifiedDate, SystemModstamp |
   | `Opportunity` | Id, AccountId, Name, StageName, Amount, Probability, CloseDate, Type, LeadSource, Description, OwnerId, IsClosed, IsWon, `Loss_Reason__c`, `Paid_geneology_enquiry__c`, `Opportunity_Service__c`, `Post_code__c`, `Key_Information__c`, IsDeleted, CreatedDate, CreatedById, LastModifiedDate, SystemModstamp |
   | `OpportunityContactRole` | Id, OpportunityId, ContactId, Role, IsPrimary, IsDeleted, CreatedDate, SystemModstamp |
   | `Task` | Id, AccountId, WhoId, WhatId, OwnerId, Subject, Status, Priority, ActivityDate, Description, TaskSubtype, CallType, CallDurationInSeconds, CallDisposition, CompletedDateTime, IsClosed, IsArchived, IsRecurrence, IsDeleted, CreatedDate, CreatedById, LastModifiedDate, SystemModstamp |
   | `Event` | Id, AccountId, WhoId, WhatId, OwnerId, Subject, Type, Location, Description, StartDateTime, EndDateTime, ActivityDateTime, IsAllDayEvent, DurationInMinutes, IsArchived, IsRecurrence, IsDeleted, CreatedDate, CreatedById, LastModifiedDate, SystemModstamp |
   | `EmailMessage` | Id, ParentId, ActivityId, RelatedToId, Subject, TextBody, FromName, FromAddress, ToAddress, CcAddress, MessageDate, Incoming, Status, MessageIdentifier, ThreadIdentifier, HasAttachment, IsDeleted, CreatedDate, CreatedById, LastModifiedDate, SystemModstamp |
   | `EmailMessageRelation` | Id, EmailMessageId, RelationId, RelationType, RelationAddress, RelationObjectType, CreatedDate, SystemModstamp |
   | `Note` | Id, ParentId, Title, Body, OwnerId, IsPrivate, IsDeleted, CreatedDate, LastModifiedDate, SystemModstamp |

   - **Owner checks:** `ownerCheck` is true for Account, Contact, Opportunity, Task, Event and Note only. It is false for User, Profile, UserRole, OpportunityContactRole, EmailMessage and EmailMessageRelation.
   - **`required: false`** applies to fields whose availability is unproven until L1. These are the three Opportunity custom fields absent from ERiC's copy (`Opportunity_Service__c`, `Post_code__c`, `Key_Information__c`), plus `IsArchived`, `MasterRecordId`, and the EmailMessage threading fields (`MessageIdentifier`, `ThreadIdentifier`). The other five custom fields are known to exist from the inventory and are required. If L1 reports one as unavailable, it is left out of SOQL and listed in the manifest as `unavailable`, with its fill rate reported as unavailable rather than 0%.
   - **Reasons for v2 additions:**
     - `MasterRecordId` distinguishes merges from deletions;
     - `IsArchived` exists because archived activities come back only through `queryAll`.
   - Unchanged from v1.0:
     - `Note` is extracted and preserved; whether it is imported is a separate decision (M5).
     - `HtmlBody`, `BccAddress` and attachment content are **excluded** (D5).
     - Picklist value sets are read through `describe` and stored with the snapshot.
2. **Extractor package: `migrate/lib/crm_migrate/`** (entry point `migrate/bin/crm-migrate.py`). Python 3.13, **standard library only**, with these modes:
   - **`contract-check`** is the metadata gate. It reads `describe` only, with no records. Per object it requires:
     - `queryable` and `retrieveable` are true;
     - every `required` contract field is present in the describe result (which means the user can read it), with the expected type and `referenceTo`.

     It also records the object's `createable`, `updateable` and `deletable` flags as seen by the Run As user, and **fails if any is true**. The one exception would be a waiver listed in the contract and approved by the Architect. None is pre-granted. If `User` reports `updateable` because users can edit their own record, that is reported as an L1 finding for decision, not silently waived.

     The result is a counts-and-flags report plus the effective contract (required and available optional fields).
   - **`count`** runs `SELECT COUNT()` per object, once through `query` (current rows) and once through `queryAll` (current plus soft-deleted and archived). It returns no records.
   - **`extract`** builds the reconciled baseline (correction 2). It **always runs `contract-check` first** and builds SOQL only from the effective contract.
     1. **Pass 0 (base):**
        - record `T_start` from the server's `Date` header;
        - extract each object fully through `queryAll`, ordered by `Id`, paging only through `nextRecordsUrl`;
        - keep each row's `SystemModstamp`.
     2. **Catch-up passes 1 to N** (N defaults to 3):
        - for each object, query `SystemModstamp >= W - overlap`, where `W` is the start time of the previous pass;
        - the overlap defaults to 15 minutes and is configurable;
        - merge by `Id`, so the row with the latest `SystemModstamp` wins.

        The overlap exists because Salesforce can make a row visible **after** a query that already covered its `SystemModstamp`, for example through in-flight transactions or clock skew. The overlap is an assumption, not a guarantee. It is recorded in the manifest.
     3. **Quiet-window check:** stop early when a catch-up pass finds no row changed since the previous pass.
     4. **Verification:**
        - take `COUNT()` through both `query` and `queryAll` again;
        - run an id-only `queryAll` (`SELECT Id, IsDeleted, SystemModstamp`) for every object;
        - compare both with the merged baseline.
     5. **Completeness status**, per object and overall, written to the manifest:
        - **`RECONCILED`:** the last pass was quiet, and the counts and id sets match exactly.
        - **`RECONCILED_WITH_DRIFT`:** changes were still arriving after N passes. The drift is reported per object as counts, the watermark is recorded, and a later delta run is required. Use needs PO acceptance.
        - **`INCOMPLETE`:** any error, missing required field, or unexplained count or id-set mismatch. An `INCOMPLETE` snapshot must never be used for a load. It stays only for diagnosis.
     6. **Output:**
        - one gzip JSONL file per object;
        - the pass log, counts only;
        - `manifest.json`, holding `T_start`, the pass times, the overlap, N, the API version, the exact SOQL per pass, the contract version and sha256, the effective contract, counts and durations per object and pass, the status, and a sha256 per file.
     - Files are created with umask `077`, so they are `0600`. The run directory must be new and empty, and is never overwritten.
   - **`reconcile`** reads one snapshot, plus optionally the previous one, and writes `reconciliation.json` and a Markdown summary. Both contain **counts only**. It covers:
     - extracted counts against the verification counts;
     - duplicate ids;
     - **relationship integrity**, with orphans counted per relation:
       - `Account.ParentId` → Account;
       - `Contact.AccountId` → Account;
       - `Opportunity.AccountId` → Account;
       - OpportunityContactRole → Opportunity and Contact;
       - Task and Event `WhatId`, `WhoId` and `AccountId`, resolved by key prefix against the object's own describe `referenceTo`;
       - `EmailMessage.ActivityId` → Task;
       - EmailMessageRelation → EmailMessage, and `RelationId` → Contact or User. Unmatched addresses are counted, not treated as orphans.
     - **Owner reconciliation** (correction 7), only for `ownerCheck` objects. Owners are classified as:
       - active user;
       - inactive user;
       - queue or group (the `00G` prefix, where describe allows Group);
       - unresolved.

       Only "unresolved" counts as an orphan.
     - **Fill rate** per available contract field.
     - **Deletion classes** (correction 3), kept separate and never merged:

       | Class | Source | Meaning |
       |---|---|---|
       | `current` | `IsDeleted = false` | Exists now |
       | `soft_deleted_available` | `queryAll` with `IsDeleted = true` | In the Recycle Bin now, within Salesforce's retention |
       | `merged` | soft-deleted with `MasterRecordId` set | Merged into a surviving record, not lost |
       | `deletion_evidence` | `GET sobjects/<Object>/deleted/?start=&end=`, for objects whose describe shows `replicateable` | Ids and deletion dates only, within Salesforce's deletion-log window (about 30 days). Older history is unavailable. |
       | `absent_since_previous_explained` | in the previous snapshot, absent now, and matched by one of the classes above | Deletion confirmed |
       | `absent_since_previous_unexplained` | in the previous snapshot, absent now, no evidence | **Not** treated as deleted. Possible causes: permanent deletion outside the log window, a sharing or permission change, or an extraction fault. It is reported for investigation, and downstream must keep such records, flagged as `sfAbsentUnverified`. |

       `docs/MIGRATION.md` must state that `queryAll` **cannot** return permanently deleted records: rows emptied from the Recycle Bin, past its retention, or hard-deleted.
     - **Drift:** the counts of rows changed in each catch-up pass, plus the residual after the last pass.
3. **Read-only HTTP client, by design.**
   - All HTTP goes through one `SalesforceClient` that takes an injected `Transport` (correction 6).
   - **Permitted:**
     - `POST {origin}/services/oauth2/token`, with `grant_type=client_credentials` only;
     - `GET {origin}/services/data/vNN.N/` under:
       - `query`;
       - `queryAll`;
       - `sobjects/<Object>/describe`;
       - `sobjects/<Object>/deleted/`;
       - `limits`;
       - a `nextRecordsUrl` returned by the server.

     Anything else raises **before** the transport is called.
   - **Origin rules** (correction 7):
     - `{origin}` is exactly the configured `https://<mydomain>.my.salesforce.com`, or `https://<mydomain>.sandbox.my.salesforce.com` if one is configured explicitly;
     - the token response's `instance_url` must equal it exactly, otherwise the run aborts;
     - `nextRecordsUrl` must be a relative path matching `^/services/data/v\d+\.\d+/query/[A-Za-z0-9-]+$`, and an absolute URL is refused;
     - the `Authorization` header is attached only by the client and only to `{origin}`;
     - **no redirect is ever followed**: any 3xx response is an error;
     - no proxies are used, and environment proxy settings are ignored;
     - certificates and hostnames are always verified, with TLS 1.2 or later;
     - response size is limited;
     - error bodies are never logged, only the status and the Salesforce `errorCode`.
   - **`HttpsTransport`**, the only real transport, uses `http.client.HTTPSConnection` with no redirect handling. It **repeats the origin check itself**, as defence in depth.
   - **Authentication: OAuth 2.0 client credentials** through a **CRM-002 External Client App**, with a Run As dedicated read-only integration user (correction 1; see § Existing integration).
     - An existing Connected App configured the same way, **other than ERiC's**, is allowed only as a verified fallback, recorded at L1.
     - There is no username/password flow and no SOAP.
     - The ERiC identity is never used. It would also fail `contract-check`, because it can write.
   - The origin, client id and client secret come from the runtime env file only.
4. **Container: `deploy/migrate/compose.json`** (corrections 4 and 5).
   - Project `crm-migrate`, with two one-off services:
     - **`crm-migrate`** for live modes. Its own project network `crm-migrate-net` gives HTTPS egress only. No `ports`.
     - **`crm-migrate-selftest`**, with `network_mode: none`. It runs the synthetic suite end to end.
   - Image `python:3.13.9-slim-trixie@sha256:326df678c20c78d465db501563f3492d17c42a4afe33a1f2bf5406a1d56b0e86`, unmodified. No image is built.
   - **Isolated-mode layout:**
     - `migrate/` is mounted read-only at `/opt/crm-migrate`;
     - the command is `python -I -B /opt/crm-migrate/bin/crm-migrate.py <mode>`.

     `-I` ignores `PYTHONPATH` and does not add the script's directory or the working directory to `sys.path`. So the entry script inserts **one fixed absolute path**, `/opt/crm-migrate/lib`, which sits on the read-only mount, then imports `crm_migrate`. `-B` avoids writing bytecode on the read-only filesystem.

     The package layout is `migrate/bin/crm-migrate.py` and `migrate/lib/crm_migrate/…`.
   - **Hardening:**
     - `user: "64021:64021"`, a dedicated UID and GID that `migrate.sh` checks are unused on the host;
     - `read_only: true`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`;
     - `tmpfs` `/tmp` with `noexec`;
     - no external networks or volumes;
     - `crm-` names and no `container_name`.
   - **Storage model** (correction 5):
     - `/srv/CRM/runtime/migrate` and `…/snapshots` are root-owned and `0700`, so only root operators can traverse them;
     - for each run, `migrate.sh` (running as root) creates `snapshots/<UTC-id>/`, owned `64021:64021` with mode `0700`, and bind-mounts **only that directory** read-write at `/out`. Docker resolves the bind as root on the host, so the container needs no access to the parents;
     - after the run, `migrate.sh` **seals** the directory: `chown -R root:root`, directories `0700`, files `0400`. It then re-verifies the manifest checksums;
     - the container UID cannot reach the directory again, and no non-root host user can reach it at any time.
   - **Secrets:**
     - they come from `/srv/CRM/runtime/migrate/env` (root, `0600`) through `env_file`, which Compose reads as root. They are not visible to non-root users on the host;
     - `migrate.sh credentials` prompts with `read -s` and writes the file atomically with mode `0600`. Values are never echoed, logged or passed as arguments.
   - Add `deploy/migrate/env.example`, with names only.
   - **Add `scripts/migrate.sh`.** It refuses to run unless:
     - the target is `migrate`;
     - the runtime directory is `/srv/CRM/runtime/migrate`, root-owned and `0700`;
     - no secret is exported in the shell;
     - the run directory does not already exist.

     It runs Compose with every env-file name removed from its environment, following the CRM-001-C2 pattern. Ownership and permission logic lives in `migrate/lib/crm_migrate/hostcheck.py`, as pure functions that take an `os.stat` result, so it can be unit-tested without root.
5. **Synthetic fixtures and an in-process fake: `tests/migrate/`** (correction 6).
   - `FakeSalesforceTransport` implements the `Transport` interface in memory, with no sockets and no loopback. It covers:
     - token issuance, including a wrong `instance_url` case;
     - query and queryAll pagination;
     - `COUNT()`;
     - describe with flags and fields;
     - the deleted-records resource;
     - the `Date` header;
     - injected 3xx responses and absolute `nextRecordsUrl` values.
   - **Mutation hooks** fire between pages and passes:
     - update, insert and soft-delete;
     - permanent delete (the row disappears with no evidence, or appears only in the deletion log);
     - merge;
     - a **late-visible row** whose `SystemModstamp` falls before a query that has already run;
     - changes that keep arriving, to force `RECONCILED_WITH_DRIFT`.
   - **Fixtures** are deterministic and seeded. They cover everything in v1.0, plus:
     - archived activities;
     - queue-owned records;
     - unavailable optional fields;
     - objects that are not `replicateable`.
   - Every value is synthetic: domains are `example.test`, and every record carries a sentinel marker.
6. **Tests: `tests/migrate/`.** These need no network, no loopback, no Docker and no root. They cover:
   - the contract-to-SOQL rule;
   - the metadata gate;
   - the read-only refusal matrix;
   - origin and redirect rules;
   - `HttpsTransport` with `http.client.HTTPSConnection` replaced by a recording stub, which shows that refusal happens before construction and that the TLS context settings are right;
   - the reconciled-baseline algorithm under every mutation hook;
   - the deletion classes;
   - owner classification;
   - the no-content-in-logs rule;
   - the Compose policy;
   - the `hostcheck` functions;
   - `bash -n` of `migrate.sh`;
   - **isolated-mode import:** a subprocess runs `python3 -I -B <tmp copy>/bin/crm-migrate.py selftest --quick` from an unrelated working directory that contains a planted `crm_migrate/` package and a planted `json.py`. The test asserts that the mounted package runs and that neither planted file is imported.

   Each policy rule must fail against a deliberately broken fixture.
7. **Docs.**
   - `docs/MIGRATION.md`, the operator guide, covering:
     - the modes;
     - the storage model and sealing;
     - the completeness statuses;
     - the deletion classes, including the permanent-deletion limit;
     - retention and disposal;
     - the live-stage gates.
   - `security/EXTERNAL_CODE_REGISTER.yaml`: a candidate entry for the Python image.
   - The README usage section.

   The administrator guide `docs/SALESFORCE-ADMIN-SETUP.md` is delivered with this WO's PR, not by the engineer.

## Scope

**Allowlist:**
- `migrate/**`, `deploy/migrate/**`, `tests/migrate/**`
- `scripts/migrate.sh`
- `docs/MIGRATION.md`, `security/EXTERNAL_CODE_REGISTER.yaml`
- the usage section of `README.md`
- `.forge/CRM-002/**`

**Excluded:**
- **Any Salesforce access**, real credentials or real records. That includes the pseudonymised sample (PoC P2, separate approval).
- Loading into EspoCRM, and any change to `custom/`, `deploy/compose.json` or `crm-dev`.
- ERiC/ELT data stores and services.
- Writes to Salesforce of any kind; the Bulk API; SOAP.
- `HtmlBody`, Bcc and attachments.
- New dependencies beyond the standard library and the one registered image.
- Additional product scope.

## Roles and verification

The ForgeV2 roles, sequence and limits are unchanged. Specialists have no network, no loopback, no Docker and no browser, so every loop test uses the in-process transport.
- **Engineer:** implements Changes 1–7 and runs the tests.
- **Auditor:** checks scope and the allowlist, and that every policy and gate test can fail.
- **Tester:**
  - runs `python3 -I -B -m unittest discover -s tests/migrate -t . -v` and `bash -n scripts/migrate.sh`;
  - records the exact counts.
- **DevSecOps:**
  - gitleaks;
  - `env.example` holds names only;
  - no write path exists;
  - origin and redirect rules;
  - digest equals the register;
  - no new dependency.

**Expected loop outcome:** DELIVERED.

## Acceptance criteria

**In the loop** (synthetic, in-process, no network):
1. **AC1:** all tests pass, with exact counts reported. Every policy rule fails against its broken fixture.
2. **AC2:** generated SOQL equals the **effective** contract exactly. Wildcards, `FIELDS(...)`, compound fields, invalid names and non-contract fields are refused.
3. **AC3:** these are each refused **before** the transport is called:
   - every method or path outside the permitted list, including `POST`, `PATCH`, `PUT` and `DELETE` on data URLs, composite, sObject collections, the Bulk API, SOAP and Apex REST;
   - every redirect;
   - a foreign or absolute `nextRecordsUrl`;
   - a mismatched `instance_url`;
   - a non-HTTPS origin;
   - a non-`my.salesforce.com` origin.

   The fake records zero write requests across the whole suite.
4. **AC4:** `contract-check`, and `extract` through it, fails without issuing any data query when:
   - an object is not queryable;
   - a required field is missing or of the wrong type;
   - a reference target differs;
   - any object is createable, updateable or deletable.

   A missing optional field is excluded and reported as `unavailable`.
5. **AC5:** on a fixture with no mutation, extraction gives the exact counts over several pages, status `RECONCILED`, valid checksums, and identical record content on a second run.
6. **AC6:** under each mutation hook (update, insert, soft delete, permanent delete, merge, late-visible row), the baseline contains the correct final state and the per-pass drift counts are exact. Continuous change yields `RECONCILED_WITH_DRIFT`. An injected id-set or count mismatch yields `INCOMPLETE`.
7. **AC7:** the deletion classes report exactly the planted counts. An unexplained absence is never counted as deleted. Objects that are not `replicateable` report `deletion_evidence: unavailable`.
8. **AC8:** reconciliation reports exactly the planted orphans, duplicates, fill rates and owner classes. Owner checks run only on `ownerCheck` objects, and queue owners are not orphans.
9. **AC9:** the isolated-mode subprocess test passes, ignoring the planted modules. No fixture content (the sentinel) appears in any stdout, stderr or log line in any mode, including on errors.
10. **AC10:** policy checks:
    - `deploy/migrate/compose.json`:
      - pinned digest equal to the register;
      - no ports;
      - `read_only`, `cap_drop: ALL`, `no-new-privileges`, `user: 64021:64021`;
      - the selftest service has `network_mode: none`;
      - `crm-` names, no `container_name`, nothing external;
      - the only writable bind is the per-run `/out`.
    - The `hostcheck` and `migrate.sh` guards refuse:
      - a wrong target or runtime;
      - a runtime that is not root-owned `0700`;
      - an exported secret;
      - an existing run directory;
      - a UID already in use;
      - an unsealed result after a run.

**Operator stage** (synthetic only, on DOCKER1; needs Matt's operator authorisation for `/srv/CRM/runtime/migrate`):
- **O1:** `migrate.sh selftest` runs `crm-migrate-selftest` under the real Compose settings (`network_mode: none`) and writes into a real per-run directory. Evidence:
  - the import works under `-I -B` on the read-only mount;
  - the run directory is `64021`-owned during the run and sealed to `root 0700/0400` afterwards;
  - `runuser -u nobody` cannot list or read it;
  - checksums are re-verified;
  - the status is `RECONCILED`.

No Salesforce access is involved.

## Live stages (NOT authorised by this WO; each needs its own recorded PO authorisation on #9)
- **L1, metadata only.** `contract-check` with the External Client App and its Run As user. Evidence:
  - the app type: External Client App, or the verified Connected App fallback;
  - every required field is available, and the optional-field availability;
  - no object is createable, updateable or deletable.

  No records are read.
- **L2, counts only.** `count` mode, through both `query` and `queryAll`, compared with the inventory. Large gaps indicate sharing or visibility limits and are resolved before L3.
- **L3, records.** Only under the PO's data-scope authorisation (objects, date range, purpose, storage, retention, disposal). It runs on DOCKER1. Only the sanitised reconciliation is published, and the completeness status is stated.

## Prerequisites (entry gates)
1. Issue #9 exists, and CGPT's exact-version approval of this file is recorded on it.
2. `docs/MIGRATION-DECISIONS.md` and `docs/SALESFORCE-ADMIN-SETUP.md` are on `main`.
3. **For O1:** Matt's operator authorisation, with `/srv/CRM/runtime/migrate` prepared root-owned `0700`.
4. **For L1–L3:**
   - the integration user and External Client App, configured per `docs/SALESFORCE-ADMIN-SETUP.md`;
   - the credentials entered on the host by Matt through `migrate.sh credentials`;
   - the PO authorisation for that stage recorded on #9.
