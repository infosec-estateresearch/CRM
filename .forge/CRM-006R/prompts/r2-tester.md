# CRM-006R, round 2 review: Tester

- **Worktree:** `/srv/CRM/worktrees/CRM-006R`. It is read-only; don't touch any other path.
- **Candidate SHA:** `375e1ca890161b0a9d569432e28f1e21905bbd6a`
- **Base SHA:** `188af96db1f032a993448accb7ed6657f2ed2f6d` (CRM-005 delivery record)
- **Scratch directory:** `/srv/CRM/worktrees/.forge-scratch/CRM-006R`
- **Reference** (the read-only extractor at contract v4): `/srv/CRM/worktrees/.forge-scratch/CRM-006R/ref/`

Assess the candidate against **CRM-006 v1.0**, as continued by **CRM-006R**, both below, independently and according to your role.

This importer will load **real customer data** into `crm-beta`. **Any of these is blocking:**
- any record content (names, emails, bodies, addresses, phone numbers) reaching logs, stdout, `load-report.json` or `exceptions.jsonl` (ids and reason codes only), or an exception message. `users.json` holds names and emails by design: it is root 0600 input for `provision_users.py`;
- any path that deletes an EspoCRM record;
- any guessed owner;
- any manufactured value;
- loading a snapshot that is not sealed, does not verify, is INCOMPLETE, or is RECONCILED_WITH_DRIFT without a valid `--accept-drift` URL;
- a reconciliation not bound to the snapshot;
- a `selftest` snapshot loading into beta, or a real snapshot into dev;
- a second run that writes anything;
- any network destination other than `127.0.0.1`;
- any change outside the allowlist, including the CRM-006R additions limited to `roles.json` (ER Import `Import`), `access_policy.py`, `Contact.opportunityRole.options` with its i18n, and the related tests.

**PL facts:**
- **EspoCRM 10.0.12, verified live on crm-dev (synthetic):**
  - list `select` returns `contactsIds`, `contactsColumns` and `contactsNames`;
  - an invalid relation role gives 400 `columnsValid`;
  - 409 is the duplicate-name check, which is skipped with `X-Skip-Duplicate-Check: true`;
  - a unique sfId violation is a PDOException, which is HTTP 500;
  - core `CheckFromAddress` requires the `Import` scope for a foreign `from`.
- **From the real extraction:**
  - the snapshot and reconcile layouts, and the binding keys;
  - the contact-role picklist (9 values);
  - the value tables in `mapping.json`.
- **History:** the engineer worked in four rounds across CRM-006 and CRM-006R. The first CRM-006 round was BLOCKED by tooling.

The sandbox has no network, Docker or root.

**Round 2.** Engineer round 4 (the final permitted one) is in the candidate. Verify each round-1 blocking finding independently:
- **`selftest-snapshot-classed-real` / `synthetic-marker-never-produced`.** Synthetic now means exactly this: `<base>/<name>-selftest/run-1|run-2`, under a parent manifest with `mode: "selftest"` that is sealed and verifies. Beta accepts only `<base>/<name>-extract`, and refuses any snapshot whose Account `Name` contains `SENTINEL-7f3a`.
- **`second-run-writes-phones`.** The fake now reproduces the EspoCRM 10.0.12 behaviours that the PL verified live:
  - phone read-back carries the extra keys `optOut` and `invalid`;
  - `phoneNumberInternational=true` refuses national numbers and normalises `+44`; `false` stores numbers verbatim;
  - `from` with a display name is dropped, so the bare address goes in `from` and the name in `fromString`;
  - `messageId` is always replaced by `dummy:<id>`, so it is not mapped;
  - `dateSent` reads back as `YYYY-MM-DD HH:MM:SS`.

  A second run makes zero writes against that fake.
- **`call-direction-manufactured`.** No direction is sent for a blank CallType (`call_direction_unknown`). The required-date fallbacks carry per-record exception codes. Email `dateSent` never falls back to the created date.
- **`scope-outside-allowlist`: closed by PL decision.** The `test_access_policy.py` and `access_bad_*.json` changes, and `overrides_bad_opportunity_role_required.json`, are authorised retroactively as "the related tests". They follow mechanically from the authorised changes. **Don't re-raise this.** Check only that nothing *else* outside the allowlist changed between round 1 and this candidate.
- **Advisories fixed:** the API key is not in argv; the output and resume directories are refused under the snapshot base; username collisions are caught; `value_shape` is handled; a soft-deleted Salesforce parent is not linked; `LoopbackHttpTransport` is renamed.
- **PL decision:** the empty D8 pattern table is accepted. Patterns come after the load, from a counts-only analysis.

**The engineer has no executions left on this WO.** Report only defects that matter, and mark something blocking only if it would harm the real beta load or the controls listed above.

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
