# CRM-006R, round 1: Engineer (continuation of CRM-006)

- **Worktree:** `/srv/CRM/worktrees/CRM-006R`, branch `forge/CRM-006R`. The expected HEAD is `188af96db1f032a993448accb7ed6657f2ed2f6d`, the CRM-005 delivery record. Confirm it first. Do not modify `.forge/`.
- **Step 0: restore the previous round's work.** Apply `/srv/CRM/worktrees/.forge-scratch/CRM-006R/r1-work.patch` with `git apply --whitespace=nowarn <patch>`. It contains the CRM-006 round-1 work: 51 files under `load/`, `tests/load/`, `config/access/roles.json` and others, with 353 tests OK at the time. Then run both suites to confirm the starting point.
- **Reference material** is at `/srv/CRM/worktrees/.forge-scratch/CRM-006R/ref/`. The same layout as before, and `migrate/contract/salesforce-fields.json` is now **contract v4**.
- **Status reporting.** If the time box ends before you finish, report **`STATUS: completed`** with a precise "Known gaps" list. Use `failed` only if the work cannot be done at all. The tooling treats `failed` as terminal.
- **Time box:** the dispatcher stops you at 30 minutes. Return by about 25 minutes.

Your previous round reported these as done: steps 1–6 (gate, reader, mapping, upsert, report and exceptions, OCR, activities), with these known gaps: load.sh, IMPORT.md and README, plus questions 3–10. The PL answers follow.

## Answers to your round-1 questions (verified by the PL in 10.0.12, and in the extracted schema and counts)
1. **Synthetic marker.** Don't invent a key. A snapshot is synthetic if and only if `manifest.json` has `"mode": "selftest"` (written by `crm-migrate selftest`). Real extractions have `"mode": "extract"`.
   - `load.sh dev` refuses any manifest whose mode isn't `selftest`.
   - `load.sh beta` refuses `selftest`.
2. **Contract version.** The extractor is moving to **contract v4** (CRM-002-V, in progress). It adds one per-object key, `visibleVia`, on EmailMessageRelation, and changes no fields. Accept `contractVersion == 4` only, as an int.
   - The reconciliation adds the deletion class `parent_soft_deleted`: rows of EmailMessageRelation hidden through a soft-deleted EmailMessage or Contact. **Don't import** those rows; count them as skipped, with the reason `parent_soft_deleted`.
   - For each row, derive it yourself: the relation's `EmailMessageId` is a soft-deleted EmailMessage, or its `RelationId` is a soft-deleted Contact.
3. **List reads return link-multiples.** `GET Opportunity?select=id,contactsIds,contactsColumns` returns `contactsIds`, `contactsNames` and `contactsColumns` (`{id: {role}}`). Verified live.
4. **Duplicate handling:**
   - `409` is EspoCRM's *duplicate-name* check (`DuplicateConflict`). Branch firms share names, so **every POST must send `X-Skip-Duplicate-Check: true`**. That header is checked in core `CreateParamsFetcher`. Keep a `duplicate_conflict` exception code in case it ever happens.
   - A **unique-index violation on `sfId`** surfaces as an uncaught PDOException, which is **HTTP 500**, not 409. After the bounded 5xx retries, record `write_failed`. Note in the docs that a soft-deleted EspoCRM row holding the key is the likely cause.
5. **Contact roles must be valid options.** EspoCRM validates `contactsColumns.role` against `Contact.opportunityRole.options`. A raw value outside the options gives `400 columnsValid` (verified live). The L1 describe gives the Salesforce `OpportunityContactRole.Role` picklist: Business User, Decision Maker, Economic Buyer, Economic Decision Maker, Evaluator, Executive Sponsor, Influencer, Technical Buyer, Other. All are active.
   - L3 data: 3,209 rows have one of these values and 20,097 are null. No other values occur.
   - **Scope addition (authorised):** add `custom/Espo/Custom/Resources/metadata/entityDefs/Contact.json` with `fields.opportunityRole.options` set to `["", "Business User", "Decision Maker", "Economic Buyer", "Economic Decision Maker", "Evaluator", "Executive Sponsor", "Influencer", "Technical Buyer", "Other"]`, and the matching i18n labels if needed. This completes the CRM-004 deferral "options added after L1".
   - Update `tests/unit/test_enquiries.py::test_contact_metadata_unchanged` to assert exactly this options list, and nothing else in Contact entityDefs.
   - Map a null role to `""`. Any role outside the list becomes the exception `role_unmapped` and is linked with `""`.
6. **Users.** Salesforce UserType counts: Standard (25), CloudIntegrationUser (1), AutomatedProcess (1), CsnOnly (2). Export **Standard only**. Count the others as skipped with the reason `user_not_human`. Their ids still resolve to "unresolved owner" exceptions if they own records.
7. **Value tables from the real data** (counts only). Put them in `mapping.json`:
   - Task `TaskSubtype`: Task (9,124), Email (34,503), ListEmail (3), Call (497).
     - Email and ListEmail become Email (Archived).
     - Task Status is Open or Completed. Open becomes `Not Started` and Completed becomes `Completed`.
     - Priority is Normal or High, mapping to `Normal` and `High`.
     - A Call becomes status `Held` with direction `Outbound`, unless `CallType` says otherwise.
   - Event `Type`: Meeting (847), Presentation (414), Other (22), Call (12), Email (10), Bag Drop (6), and null (1,658), which becomes `Unspecified (legacy)` (D10). Meeting status is `Held` if `EndDateTime < manifest t_start`, otherwise `Planned`.
   - EmailMessage `Status`: "3" with `Incoming=false` (11,747), and "1" with `Incoming=true` (22,445). Every one becomes Email `Archived`.
8. **Fields to add (round-1 gaps):**
   - Contact `Phone` and `MobilePhone` both go to `phoneNumberData`: `[{"phoneNumber", "type": "Office"|"Mobile", "primary"}]`, with Phone primary when it is present.
   - `amountCurrency: "GBP"` whenever `amount` is set.
   - Account and Opportunity `Description` go to `description`, since they are in the contract.
   - Meeting attendees: the owner only. EventRelation is not in the contract; note this in the docs.
9. **gitleaks** isn't available in the sandbox. The PL runs it.

## Still to build (round-1 known gaps 1 and 2)
- **`scripts/load.sh`.** It is root only, with the same guard pattern as `scripts/migrate.sh`, which is not on this branch (the reference is at `.forge-scratch/CRM-006R/ref/`).
  - Targets: `dev` (synthetic, `selftest` mode only) or `beta` (refuses `selftest`).
  - The snapshot path must be under `/srv/CRM/runtime/migrate/snapshots/` and sealed root 0700/0400.
  - The output directory must not already exist, is created root 0700, and its files are 0600.
  - `CRM_LOAD_HOST`, `CRM_LOAD_PORT` and `CRM_LOAD_API_KEY` come from a root-only env file: `/srv/CRM/runtime/<target>/load.env`, 0600, and refused otherwise.
  - Run `python3 -I -B load/bin/crm-load.py`.
  - Add tests for the script guards in the style of the CRM-001 script tests.
- **`docs/IMPORT.md`** and the **README usage** section.

Run both suites: `python3 -m unittest discover -s tests/unit -v` and `python3 -I -B -m unittest discover -s tests/load -t . -v`. Report exact counts and mutation evidence. Finish in the Engineer final message format.

---

## Round-1 brief of CRM-006 (still applies)

## Reference material (read-only, synthetic or schema only)
The extractor isn't on this branch. A read-only copy of the delivered extractor at contract **v3** is at `/srv/CRM/worktrees/.forge-scratch/CRM-006R/ref/`:
- `migrate/contract/salesforce-fields.json`: contract **v3**, giving the exact fields per object;
- `migrate/lib/crm_migrate/manifest.py`, `extract.py` and `reconcile.py`: the snapshot format;
- `migrate/lib/crm_migrate/synthetic.py`: the synthetic org (SENTINEL-7f3a, example.test);
- `docs/MIGRATION.md`, covering the snapshot layout, statuses and deletion classes;
- `docs/MIGRATION-DECISIONS.md`, covering D1–D13.

The snapshot holds:
- `manifest.json`, with the status, contract version and sha256 of every file;
- `objects/<Object>.jsonl.gz`, sorted by Id, effective contract fields only;
- `deleted/<Object>.jsonl.gz`;
- `report/reconciliation.json` with the deletion classes, from `reconcile`.

Build the synthetic fixtures under `tests/load/` yourself, in the same format, for example a small generator that writes a manifest and gzip JSONL into a temp dir. Don't import from `ref/` at runtime: `load/` must be self-contained.

## PL clarifications (authorised)
1. **Contract v3:**
   - `Opportunity.Post_code__c` and `Key_Information__c` are **not** in the snapshot. L1 found that one is a self-lookup and the other doesn't exist. `postcode` and `keyInformation` stay empty, with no exception.
   - The importer accepts `contractVersion == 3` only (an int, not a bool or float).
2. **Scope addition:**
   - `config/access/roles.json`: set `"Import": true` for the **ER Import** role only;
   - `tests/unit/access_policy.py`: update the matching expectation.

   This is needed because EspoCRM 10.0.12 core `Classes/RecordHooks/Email/CheckFromAddress.php` refuses a non-admin creating an Email whose `from` isn't their own, unless `acl->checkScope('Import')`. Without the change, every archived email import fails with 403.
3. **EspoCRM 10.0.12 REST facts** (verified by the PL in the image):
   - Base `/api/v1/`, header `X-Api-Key: <key>`.
   - List: `GET {Entity}?select=id,sfId,...&maxSize=200&offset=N` (`recordListMaxSizeLimit = 200`), with `where[0][type]=isNotNull&where[0][attribute]=sfId`. Create: `POST {Entity}`. Update: `PUT {Entity}/{id}`, sending only the changed attributes.
   - **Opportunity contacts with role:** linkMultiple `contacts` with `columns: {"role": "opportunityRole"}`. Write `contactsIds: [...]` together with `contactsColumns: {"<contactId>": {"role": "<raw SF Role>"}}`. Roles are stored raw (CRM-004 decision); there are no options yet.
   - **Meeting attendees:** `usersIds` and `contactsIds`. The `users` columns are `{status: acceptanceStatus}`; leave them at the default.
   - **Email create**, archived: `status: "Archived"`, `from` (address string), `to` and `cc` (`;`-separated address strings), `name` (subject), `bodyPlain` and `body` from **TextBody only**, `isHtml: false`, `dateSent`, `parentType` + `parentId`, `usersIds`, `sfId` and the `sf*` fields.
     - **No attachments and no Bcc** (PO: "Exclude attachments, Bcc"). There is no `HtmlBody`; the contract doesn't extract it.
     - `messageId` is the SF `MessageIdentifier` when present.
     - **The unique index counts soft-deleted rows** (CRM-005 advisory): if a create fails on the unique `sfId`, because a soft-deleted EspoCRM row holds that key, record the exception `sfid_conflict_hidden_row` and continue. Never delete and never retry in a loop.
   - **Target field names** are in this worktree: `custom/Espo/Custom/Resources/metadata/entityDefs/{Account,Contact,User,Opportunity,ServiceType,Call,Meeting,Task,Email}.json`. Use exactly those names, and add a static test that every attribute in `mapping.json` exists in entityDefs or core. The core field lists for Call, Meeting, Task and Email are in `tests/unit/activity_policy.py`.
4. **Users:**
   - Users are created by `scripts/provision_users.py` (CRM-003; read its input format in this worktree), **not** by the importer.
   - `crm-load users` writes `users.json`. `crm-load load` resolves the owner `sfId` through `GET User?select=id,sfId`.
   - The Profile/Role → team/role table is an operator-supplied JSON (`--role-map`). Ship an example with **no real names**, using placeholders only.
5. **D8 name parsing.** No real enquiry name formats are available to you. Implement a pattern table in `load/contract/name_patterns.json`, **initially empty**, plus the engine and tests with synthetic patterns. Unparsed names give `clientReference` etc. empty and an exception `name_unparsed`, counted only. The PL adds the real patterns after L3, from counts-only analysis.
6. **`load-report.json`** may contain only counts, codes and object names. **`exceptions.jsonl`** may contain only `{object, sfId, reason}`, where the reason is from a fixed code set. Test this with the sentinel `SENTINEL-7f3a`: it must appear in no output file, log or exception message.
7. **No network in tests:** an injected transport, and a fake EspoCRM that records writes. `HttpsTransport` for the real run: plain HTTP to `http://127.0.0.1:<port>` only, with the host and port from the root-only env. Any other host is refused, and no redirects are followed.

## Tests
- Run `python3 -m unittest discover -s tests/unit -v` (the existing 310 must still pass) and `python3 -I -B -m unittest discover -s tests/load -t . -v`.
- Report exact counts and mutation evidence for the gate, idempotency, owner resolution and the no-content rule.

Finish in the Engineer final message format.

## Work Orders (verbatim, on main)

WO: CRM-006R
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-005
BROWSER: no

# CRM-006R — Continuation of CRM-006 (idempotent importer)

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10 (Issue #9).
- **Why:** CRM-006 was closed BLOCKED by the delivery tooling. Its first engineer round was a planned partial round of a large WO, reported "STATUS: failed" with 6 of 8 build steps done and tested, and the tooling treats that status as terminal. Nothing was reviewed under that id.

## Scope, change and acceptance
**Identical to `work-orders/CRM-006.md` v1.0**, which is authoritative and incorporated here by reference.

There are three PL clarifications, recorded in the delivery prompts:
1. **Contract v4.** The importer accepts snapshots of contract **v4**, which comes from CRM-002-V and adds `visibleVia`. Rows of EmailMessageRelation hidden through a soft-deleted parent are skipped with the reason `parent_soft_deleted`.
2. **ER Import role.** The role gets the EspoCRM boolean scope `Import: true` in `config/access/roles.json`. Core 10.0.12 requires it to archive emails whose `from` is not the API user's own.
3. **Contact roles.** `Contact.opportunityRole.options` is set to the Salesforce `OpportunityContactRole.Role` picklist read at L1, which completes the CRM-004 deferral. Core validates relation roles against these options.

All three are allowlist additions limited to exactly these files and keys:
- `config/access/roles.json` (ER Import `Import` only);
- `tests/unit/access_policy.py`;
- `custom/Espo/Custom/Resources/metadata/entityDefs/Contact.json` (`opportunityRole.options` only), with its i18n;
- `tests/unit/test_enquiries.py` (the Contact metadata assertion).

WO: CRM-006
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-005
BROWSER: no

# CRM-006 — Repeatable, idempotent importer: Salesforce snapshot → EspoCRM, with reconciliation and exceptions (synthetic fixtures)

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10 (Issue #9), § 4 "Reconcile and import".
- **Parent PBI:** CRM-PBI-005, part 2, and PBI-012 (the beta load).
- **Base:** stacked on `forge/CRM-005`, which holds the target fields.
- **Inputs:**
  - the snapshot format of CRM-002 (`manifest.json` plus gzip JSONL per object);
  - `docs/MIGRATION-DECISIONS.md` (D1–D13, §3);
  - the CRM-003 to 005 field contracts.

## Outcome

`crm-load`, run by the trusted operator, reads one **sealed** snapshot and creates or updates EspoCRM records through the REST API using the `ER Import` API user. It is keyed on immutable Salesforce ids (`sfId`). Re-running it changes nothing. It produces:
- a counts-only reconciliation;
- a root-only exception file containing ids and reason codes only.

Nothing is silently discarded, ownership is never invented, and no missing value is made up.

## Change

1. **Package `load/lib/crm_load/` with entry point `load/bin/crm-load.py`.** Standard library only, the same `-I -B` fixed-path layout as `crm-migrate`, and an injected transport.
2. **Input gate.** The importer refuses unless:
   - the manifest verifies, meaning every file's sha256 matches;
   - the status is `RECONCILED`, or `RECONCILED_WITH_DRIFT` together with `--accept-drift <Issue #9 comment URL>`;
   - the contract version is known.

   It reads the snapshot read-only.
3. **Mapping** (`load/contract/mapping.json`, versioned; values per `MIGRATION-DECISIONS.md`):
   - **User:**
     - writes `users.json` for `scripts/provision_users.py` (CRM-003): sfId, names, email, active state, and teams and roles derived from the Profile and Role names through an operator-supplied table;
     - the shared "Ancillary Services" login becomes the inactive legacy user (D4);
     - inactive users become inactive (D5).

     Users are created by `provision_users.py` and **not** by the importer, which only resolves `sfId` → EspoCRM user id.
   - **Account:**
     - name, type (tier), industry and phone;
     - website;
     - learning platform access, from `TLP__c`;
     - the Salesforce **Shipping** address goes to the EspoCRM **billing** address, which is the firm address shown in the UI (R4). The Salesforce Billing address goes to the EspoCRM shipping address;
     - `parent` comes from `ParentId`, applied in a **second pass** after every Account exists;
     - `assignedUser` from `OwnerId`, with `sfOwnerId` kept;
     - `sfCreatedAt`.

     Records soft-deleted in Salesforce, or with `absent_unexplained` status, are **not** created. They are counted, and any that already exist are flagged rather than deleted.
   - **Contact:** names, salutation, title, email and phones, and the Mailing address. `account` from `AccountId`; owner as above.
   - **ServiceType:** distinct `Opportunity_Service__c` values, created by name with `sfValue`.
   - **Opportunity (Enquiry):**
     - the stage mapping follows D1, with `sfStageName` kept;
     - `legacyStale` (D2): the stage maps to Enquiry or Quoted and the close date is in the past;
     - `lossReason` and `lossReasonLegacyMissing` (D3);
     - `amount`, `closeDate`, `serviceType`, `enquiryCategory` (`Paid_geneology_enquiry__c`), `businessType` (`Type`), `postcode`, `keyInformation`;
     - `sfLeadSource` is kept raw. `introducedBy` and `channel` are filled **only** from the PO-approved D7 table, `load/contract/lead_source_map.json`, which starts empty;
     - name parsing (D8): `clientReference`, `deceasedName` and `caseNumber` come from tested patterns, and anything unparsed goes to the exception file;
     - `assignedUser`, `account`, `sfId`, `sfOwnerId` and `sfCreatedAt`.
   - **OpportunityContactRole:** relates the Contact to the Opportunity with its role.
   - **Activities**, per the CRM-005 mapping intent:
     - Task subtypes Task, Call and Email go to Task, Call and Email (Archived);
     - Event goes to Meeting, with `meetingType`;
     - EmailMessage and EmailMessageRelation go to Email (Archived), with addresses, `messageId` and threading, linked to its Task or Opportunity or Account, and to contacts and users;
     - `parent` resolved from `WhatId` by key prefix, falling back to `AccountId`;
     - owners and dates preserved.
   - **Note:** **not imported** (D6). Counted only.
4. **Owner resolution.**
   - An owner id that resolves to a provisioned user is assigned.
   - An owner that is a queue or group, or that is unresolved, leaves `assignedUser` **empty**, with `sfOwnerId` kept and an exception recorded.
   - Ownership is never guessed.
5. **Idempotent upsert.**
   - For each record, find it by `sfId`, using an in-memory index built from one paged read per entity at start. Create it if absent. Update it only if mapped values differ.
   - A second run on the same snapshot makes **zero** writes.
   - Retries handle HTTP 429 and 5xx with backoff.
   - The importer never deletes.
   - Progress is checkpointed, so an interrupted run resumes safely.
6. **Reconciliation and exceptions.**
   - **`load-report.json`** (counts only), per object:
     - source current;
     - created, updated, unchanged;
     - skipped by reason (soft-deleted, unexplained, out of scope);
     - exceptions by reason code;
     - relationship totals in EspoCRM against the snapshot (parents, contacts, enquiry contacts, activity parents).
   - **`exceptions.jsonl`** (root `0600`): `{object, sfId, reason}`, with ids and codes only. It carries no field values.
7. **Script `scripts/load.sh`.** Root only, using the same guard pattern as `migrate.sh`. Arguments: the target environment (`beta` only; `dev` refuses unless the snapshot is synthetic, marked so in its manifest), the snapshot path, and an output directory that must not already exist. The ER Import API key is read from the root-only runtime env.
8. **Tests (in-process, synthetic):**
   - a synthetic snapshot generator, or reuse of the CRM-002 synthetic fixtures copied under `tests/load/`;
   - a fake EspoCRM transport;
   - mapping per object;
   - the second-pass parents;
   - the stage, stale and loss-reason rules;
   - owner resolution, including queue and unresolved owners;
   - name-parsing patterns and their exceptions;
   - idempotency: the second run makes zero writes;
   - resume after an interruption;
   - the gate refuses bad checksums or status;
   - the no-content-in-logs rule, using a sentinel;
   - the policy rules have broken fixtures.
9. **Docs:** `docs/IMPORT.md` covering the operator procedure, ordering, the report fields, the exception codes and the re-run behaviour.

## Scope

**Allowlist:** `load/**`, `tests/load/**`, `scripts/load.sh`, `docs/IMPORT.md`, the README usage section, `.forge/CRM-006/**`.

**Excluded:** changes to `custom/`, `migrate/`, Salesforce access, real data, and deleting EspoCRM records.

## Acceptance criteria
- **AC1 / AC2:** unit tests with non-vacuity; gitleaks.
- **AC3:** against the fake, the synthetic snapshot loads with exact counts per object, and the relationship totals match.
- **AC4:** a second run makes zero writes. An interrupted run resumes to the same result.
- **AC5:** no owner is invented. Every unresolved owner appears in the exceptions file.
- **AC6:** soft-deleted and unexplained-absent records are never created and never deleted. They are counted.
- **AC7:** the logs and the report contain no record content.

**Operator stage:** the synthetic snapshot loads into `crm-dev`. The real snapshot loads **only** into `crm-beta` (PBI-011/012) once that environment is accepted.
