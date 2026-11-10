# CRM-004, round 2: Tester review

- **Worktree:** `/srv/CRM/worktrees/CRM-004`. It is read-only; don't touch any other path.
- **Candidate SHA:** `d9b615826cb3cc357fa6896137b943ab05825e67`
- **Base SHA:** `ec493f8678de75730c61c900f424e67a9953ddc5` (CRM-003 delivery, stacked on the CRM-001 LAN branch)
- **Scratch directory:** `/srv/CRM/worktrees/.forge-scratch/CRM-004`

Assess the candidate against the Work Order below, independently and according to your role. The priorities are:
- the stage model and the loss-reason rule (server-side hook, legacy exemption);
- ACL: the new ServiceType scope must be explicit in every role, because EspoCRM runs in non-strict mode, and the legacy fields must be read-only for people;
- that the importer can still write `sfId` on create (`readOnlyAfterCreate`, not `readOnly`).

**PL scope clarification for this run (authorised):** the engineer may change:
- `config/access/roles.json` and `tests/unit/access_policy.py`, only for the ServiceType scope and the Opportunity legacy `fieldData`;
- the ServiceType scope, entityDefs, layouts and i18n;
- `Global.json` `scopeNames` and `scopeNamesPlural`, only for Opportunity and ServiceType.

**Names verified by the PL in the EspoCRM 10.0.12 image:**
- `Espo\Entities\User::TYPE_API = 'api'`, `getType(): ?string` and `isApi(): bool` exist.
- `Espo\ORM\Query\Part\Condition::and(WhereItem ...$items)` exists.
- clientDefs `defaultFilterData` is used by the client.
- Layout panels support `"collapsed"`.
- The core `layouts/Opportunity/relationships.json` is `["documents"]`.

**PL acceptances:**
- the engineer's decisions 1–5;
- the client-side required rule also needs `lossReasonLegacyMissing` false, which matches the server rule.

D1–D4 are defined in `docs/MIGRATION-DECISIONS.md` on `main`. That file isn't in this stacked branch, so don't penalise their absence from `docs/ENQUIRIES.md`.

**Facts:** the specialist sandbox has no php, Docker or browser. AC3–AC7 run at the operator stage.


**Round 2.** Engineer round 2 is in the candidate. These are the PL decisions on the round-1 findings. Verify that each is implemented, and judge the result independently.
- **Raised by the PL as blocking:** the core Opportunity `amount` and `closeDate` are `required: true`, verified in the image. Both are now `required: false` and still audited. Without that, the quick create and the import (most Salesforce enquiries have no fee) would fail.
- **contact-role-options: closed by PL decision.** The Salesforce OpportunityContactRole picklist values are known only after L1, from the describe step. Inventing them would break the PO's "do not silently manufacture missing data" rule. Roles are stored raw in the relation's `role` column. The options are added after L1 in a later change, and Contact metadata stays unchanged. **Don't re-raise this as blocking.** Check only that `docs/ENQUIRIES.md` states it accurately.
- **ServiceType import create and edit: accepted.** It is documented as a deviation.
- **API exemption: narrowed.** It is now `TYPE_API` **and** userName `er-import`, tied to `config/access/api_users.json`. `getUserName(): ?string` was verified by the PL in the image.
- **Opportunity.sfId:** the human-read rule and fixture are added.
- **Enquiries labels:** Account and Contact `links.opportunities`. The PL verified that core i18n has `opportunities` under `links` only; there is no `fields` entry.
- **stage-map merge and admin legacy edit:** accepted as limits documented in `docs/ENQUIRIES.md`.
- **Engineer residual:** `docs/ACCESS.md` doesn't mention that Opportunity.sfId is hidden. Classify it.

## Work Order (verbatim, `work-orders/CRM-004.md` v1.1 on main)

WO: CRM-004
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-003
BROWSER: yes

# CRM-004 — Enquiries (EspoCRM Opportunity relabelled "Enquiry"; synthetic data)

- **Version:** v1.1, 2026-11-10. v1.1 corrects how the Salesforce key and legacy fields are made read-only (§ Amendment v1.1).
- **Authority:** the PO priority override of 2026-11-10 (Issue #9).
- **Parent PBI:** CRM-PBI-004 (R7, R8). Decision D9: reuse Opportunity.
- **Base:** stacked on `forge/CRM-003`.

## Outcome

Estate Research's enquiry workflow in standard EspoCRM:
- Opportunity, relabelled **Enquiry**;
- stages **Enquiry → Quoted → Instructed / Lost**;
- quoted fee, service type, specialist fields and linked firm and contacts with roles;
- the original Salesforce stage and values preserved;
- a phone-call quick create.

## Facts verified by the operator (EspoCRM 10.0.12)
- Core Opportunity fields: `name`, `amount`, `account`, `contacts`, `contact`, `stage` (audited), `lastStage`, `probability`, `leadSource`, `closeDate`, `description`, `contactRole`, `assignedUser` and `teams`.
- Core stage options: Prospecting, Qualification, Proposal, Negotiation, Closed Won and Closed Lost, with a `probabilityMap`.
- Links include `meetings`, `calls`, `tasks`, `emails` and `documents`.

## Change

1. **Labels** (`i18n/en_US`): the scope name "Enquiry" and plural "Enquiries" everywhere in the UI. `amount` is labelled "Quoted fee". The entity name stays `Opportunity`.
2. **Stage** (custom entityDefs `Opportunity.json`):
   - options `Enquiry`, `Quoted`, `Instructed`, `Lost`; default `Enquiry`;
   - `probabilityMap` Enquiry 10, Quoted 50, Instructed 100, Lost 0;
   - audited; styles set.
3. **Fields** (all `isCustom`):

   | Field | Type | Notes |
   |---|---|---|
   | `serviceType` | link to the new custom entity **`ServiceType`** | `ServiceType` has `name` (unique), `isActive` and `sfValue`. It holds 60+ reference values that admins can edit; only admins can create or edit records. |
   | `lossReason` | enum | Options: "", No longer needed, Unable to work in that country, Other, Lost to Competitor, Price, No Decision / Non-Responsive, Solicitor carried out in house, No Budget / Lost Funding, Lost to Lay Client. Audited. |
   | `introducedBy` | link to User | From the PO-approved lead-source table (D7) only |
   | `channel` | enum | Options "" and "Unmapped (legacy)". Further values are added only once the PO approves the D7 table. |
   | `clientReference`, `deceasedName`, `caseNumber` | varchar | Parsed from the Salesforce name by the importer (D8) |
   | `businessType` | enum | "", New Business, Existing Business |
   | `enquiryCategory` | enum | "", Yes, No, Ancillary, Legal rights check, Overseas Assets, Share Sale (Salesforce "Paid genealogy enquiry") |
   | `postcode` | varchar | |
   | `keyInformation` | text | |
   | Legacy, read-only | | `sfId` (varchar 18, **unique index**), `sfStageName`, `sfLeadSource`, `sfOwnerId`, `sfCreatedAt`, `legacyStale` (bool), `lossReasonLegacyMissing` (bool) |

   `amount`, `assignedUser` and `closeDate` are also audited.
4. **Loss reason rule (R7, D3).**
   - Server side: a `beforeSave` hook refuses saving `stage = Lost` with an empty `lossReason`, unless `lossReasonLegacyMissing` is true **and** neither the stage nor the loss reason is being changed.
   - Client side: dynamic logic marks `lossReason` as required when the stage is Lost.
   - The `ER Import` API user is exempt, but only for records that carry `lossReasonLegacyMissing = true`.
5. **Contacts with roles:**
   - the core `contacts` relation, with the core role column;
   - the role options are the Salesforce OpportunityContactRole values, plus the core values;
   - an Enquiry Contacts panel on the detail view.
6. **Lists and filters:**
   - **list layout:** name, account, stage, quoted fee, service type, assigned user, close date;
   - **filters:** stage, assigned user, service type, enquiry category, legacy stale;
   - **primary filters:** "Open enquiries" (stage Enquiry or Quoted, and not legacy stale) as the default, "My open enquiries", and "Legacy stale" (D2). Use EspoCRM's select framework primary-filter classes and `selectDefs`.
7. **Quick create (R8):** a minimal quick-create layout (account, contact, service type, name, description) so an enquiry can be created from a phone call in under 60 seconds.
8. **Detail layout:**
   - panels: Enquiry, Case details (client reference, deceased name, case number, postcode, key information) and Legacy (read-only, collapsed);
   - the activities and history panels stay at the core defaults.
9. **Tests (unit, in-process):**
   - metadata consistency;
   - stage options and probabilities;
   - the hook logic, checked statically plus a PHP-free rule table mirrored in a Python spec test;
   - layouts reference only existing fields;
   - every policy rule fails against a broken fixture.
10. **Docs:** `docs/ENQUIRIES.md` covering the workflow, the field meanings, D1–D4 and D7–D9, and the legacy fields.

## Scope

**Allowlist:**
- `custom/**`, limited to Opportunity, ServiceType, the Opportunity hooks and select classes, and the related layouts and i18n
- `tests/unit/**`, `tests/acceptance/**`
- `docs/ENQUIRIES.md`, the README usage section
- `.forge/CRM-004/**`

**Excluded:**
- activities and email (CRM-005);
- the importer;
- roles (CRM-003);
- real data.

## Acceptance criteria
- **AC1 / AC2:** as for CRM-003 (unit tests with non-vacuity; gitleaks).

**Operator stage** (`crm-dev`, synthetic data):
- **AC3:** a Staff user creates an enquiry through quick create, then updates its stage Enquiry → Quoted → Instructed. Each change appears in the history with user and time.
- **AC4:** setting Lost without a reason is refused. A legacy Lost record with the flag saves without a reason.
- **AC5:** the default list shows open, non-stale enquiries only. The filters by owner and stage return the seeded counts.
- **AC6:** a Staff user cannot edit another user's enquiry. An Intake user can.
- **AC7:** an enquiry shows its firm, its contacts with roles, and its service type.

## Amendment v1.1 (2026-11-10, PL, from the EspoCRM 10.0.12 source)
`readOnly: true` in entityDefs becomes a **global** read-only restriction (`Espo\Core\Acl\GlobalRestriction`). It applies to every user, including the `ER Import` API user, so the importer could never write those fields. Therefore, everywhere this WO says "read-only" for `sf*` or legacy fields:
- `sfId` uses **`readOnlyAfterCreate: true`**. It can be set on create and is immutable afterwards (`Espo\Core\Record\Service`).
- Other legacy fields (`sfStageName`, `sfLeadSource`, `sfOwnerId`, `sfCreatedAt`, `legacyStale`, `lossReasonLegacyMissing`, `sfEmailMessageId`, `sfThreadIdentifier`, `sfActivityId`) carry **no** `readOnly` param. They are read-only for people through role `fieldData` (`edit: no` for ER Staff, ER Intake and ER Manager; `edit: yes` for ER Import) in `config/access/roles.json`, which is added to this WO's allowlist for those entries only. They are also left out of edit layouts.
- Tests: no `sf*` or legacy field may carry `readOnly: true`; `sfId` has `readOnlyAfterCreate`; human roles cannot edit these fields.
