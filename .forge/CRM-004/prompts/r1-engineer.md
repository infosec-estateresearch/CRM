# CRM-004, round 1: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-004`, branch `forge/CRM-004`. The expected HEAD is `ec493f8678de75730c61c900f424e67a9953ddc5`, the CRM-003 delivery: users, roles, the Salesforce key fields, and the access policy tests. Confirm it first. Do not modify `.forge/`.
- **The Work Order** (`work-orders/CRM-004.md` **v1.1**, on main; not in this worktree) is quoted verbatim below. It is authoritative, including the **Amendment v1.1**: `sfId` uses `readOnlyAfterCreate`, and the other legacy fields are read-only for people through role `fieldData`.
- **Time box:** the dispatcher stops you at 30 minutes. Work in this order:
  1. the entityDefs (Opportunity, ServiceType);
  2. i18n;
  3. the stage and loss-reason hook;
  4. the layouts;
  5. the primary filters;
  6. `roles.json`;
  7. the tests;
  8. the docs.

  Return your final message by about 25 minutes, even if it's partial, and list anything unfinished under "Known gaps".

## Scope clarification from the PL
These additions to the WO allowlist are authorised, and limited to:
- `config/access/roles.json` and `tests/unit/access_policy.py`, **only** to:
  - add the new `ServiceType` scope (read all for human roles, with create and edit for admins only; ER Import create and edit, no delete) to every role, and to the policy's verified scope constant (mark the addition "added by CRM-004");
  - add `fieldData` for the Opportunity legacy fields, per Amendment v1.1.
- `custom/Espo/Custom/Resources/metadata/scopes/ServiceType.json` and the ServiceType entityDefs, layouts and i18n.
- `custom/Espo/Custom/Resources/i18n/en_US/Global.json`, **only** for the `scopeNames` and `scopeNamesPlural` of Opportunity ("Enquiry"/"Enquiries") and ServiceType.

## EspoCRM 10.0.12 facts verified by the PL in the real image
- **Opportunity:**
  - core layouts: detail, detailSmall, filters, kanban, list, listForAccount, listForContact, listSmall, massUpdate and relationships;
  - clientDefs keys include `filterList`, `boolFilterList` and `relationshipPanels`;
  - i18n keys: fields, links, options, labels, presetFilters;
  - `Global.scopeNames.Opportunity` is "Opportunity".
- **`logicDefs/Opportunity.json` (core)** makes `lastStage` visible when the stage equals `"Closed Lost"`. Override it so the condition uses `"Lost"`. Put the dynamic logic for `lossReason` (required when the stage is Lost) in **`custom/…/metadata/logicDefs/Opportunity.json`**, which is the logic location in 10.x.
- **Core primary filters:** `selectDefs/Opportunity.json` maps `open`, `won` and `lost` to `Espo\Modules\Crm\Classes\Select\Opportunity\PrimaryFilters\{Open,Won,Lost}`. These use `StageListProvider`, which derives won and lost from the stage `probabilityMap` (100 means won, 0 means lost). Custom filters implement `Espo\Core\Select\Primary\Filter` with `apply(Espo\ORM\Query\SelectBuilder $queryBuilder): void`, using `Espo\ORM\Query\Part\Condition as Cond`, `Cond::in(Cond::column('stage'), [...])` and `Cond::equal(...)`. Register them in `custom/…/metadata/selectDefs/Opportunity.json` under `primaryFilterClassNameMap`, and list them in clientDefs `filterList`. "My open enquiries" may combine the open filter with core `boolFilterList` `onlyMy`, or implement its own filter.
- **Hooks:**
  - `Espo\Core\Hook\Hook\BeforeSave` declares `beforeSave(Espo\ORM\Entity $entity, Espo\ORM\Repository\Option\SaveOptions $options): void`;
  - custom hooks live in `custom/Espo/Custom/Hooks/Opportunity/`;
  - refuse with `Espo\Core\Exceptions\BadRequest` or `Forbidden`;
  - use `$entity->isAttributeChanged('stage')` and `$entity->get(...)`.
  - For the ER Import exemption, inject `Espo\Entities\User` (the current user) and check the user type is `api` and that the user is the import user. Simplest and robust: exempt only when the record carries `lossReasonLegacyMissing = true` **and** the current user's type is `api`.
- **Contacts relation:**
  - `Opportunity.contacts` is `hasMany` Contact through `contactOpportunity`, with a `role` column (varchar 50) mapped to `contactRole`;
  - the UI options come from `Contact.opportunityRole` (core: "", Decision Maker, Evaluator, Influencer);
  - **Don't change Contact.** The importer stores Salesforce role values raw in the role column. Document that the UI picklist shows core options only, until the PO approves role options in a later change.
- **ACL** runs in non-strict mode, which is why the new scope must be explicit in every role. The CRM-003 policy test enforces this.

## Constraints
No network, no Docker, no root, no php. Standard library only. Synthetic data only. Every CRM-001 and CRM-003 test must still pass.

## Report
- `python3 -m unittest discover -s tests/unit -v`, with exact counts before and after;
- non-vacuity evidence for each new rule;
- `git status --short --untracked-files=all`.

Finish in the Engineer final message format.

---
## Work Order (verbatim)

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
