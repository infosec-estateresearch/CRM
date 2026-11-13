# CRM enhancement requirements — FirmGroup and WIP/Revenue MVP

> **Provenance:** CGPT Architect delivery package of 2026-11-13 (`ER_CRM_FOUNDRY_DELIVERY_2026-11-13.zip`, sha256 `a75b5f0d1768a2a1bd945d35710e6e2067c4a7fb5e0228773946446ad9104488`), reconciled into the CRM repository by Rogue under the documentation-only assignment of 2026-11-13. CANDIDATE: not approved. Changes made during reconciliation are listed in [`docs/initiation/2026-11-13-existing-product-reassessment.md`](../initiation/2026-11-13-existing-product-reassessment.md#7-reconciliation-log).

**Status: candidate requirements for Foundry reassessment (13 Nov 2026).** IDs are proposed stable requirement IDs subject to collision check. Acceptance is evidence-driven and includes core CRM regression. One requirement can be implemented over multiple exact-approved Forge WOs. No source data or host secrets permitted in this public file.

## FirmGroup functional requirements

| ID | Requirement | Observable acceptance |
|---|---|---|
| FG-01 | `FirmGroup` is a CRM-native record with immutable internal ID, name and optional description | Create two peer Account members in one group; neither becomes parent |
| FG-02 | Optional `Account.firmGroup` belongsTo; one group max; empty means no group | Ungrouped Account has null membership; one Account cannot have two active groups |
| FG-03 | Preserve Salesforce `Account.parent` and `branches` | Before/after parent graph fingerprints exactly equal across group operations |
| FG-04 | Add, move, remove membership by authorised user; audit before/after | Manager changes membership; audit identifies who, when, old/new ID; explicit move confirmation |
| FG-05 | Staff/Intake see, Managers/Admin edit; server enforces | Direct REST POST/PATCH/DELETE denied for Staff and Intake, even if UI manipulated |
| FG-06 | Account has **Group Members** tab near existing Stream/Account controls | Shows group name link, all *other* firm members with name/address/tier/phone and openable record links; paginates |
| FG-07 | Empty state and creation action appropriate to role | No group message; no edit action for Staff; manager can select/create group |
| FG-08 | FirmGroup detail shows members and authorised add/unlink actions | Membership from either entry point remains consistent after refresh |
| FG-09 | No automatic inference by names or Salesforce parent trees | Initial beta release has zero unapproved automatic group assignments; 39 duplicate-name candidates untouched |
| FG-10 | Group deletion cannot silently orphan active memberships | Refuse deletion with members, or explicitly unlink via separately confirmed controlled workflow; test API |
| FG-11 | Seed curated groups only under separate gate | Independent, reconciled source mapping, conflict review and PO authority before real-data seed |

## WIP model / Account-tab functional requirements

| ID | Requirement | Observable acceptance |
|---|---|---|
| WIP-01 | WIP entities belong to a separately maintained CRM-owned module | Source/layout/extensions scoped; release can be changed without touching unrelated core business logic |
| WIP-02 | Every WipCase references exactly one existing CRM Account | Required immutable `accountId`; no case writes to Account, auto-create or name-join |
| WIP-03 | WIP API exposes `firmId` and current `groupId` | `firmId` equals WipCase Account ID; `groupId` equals Account current FirmGroup ID or null; group input ignored/rejected on writes |
| WIP-04 | CRM Account **WIP/Revenue** tab exists by Stream/Account | Current firm list with case references/status/latest observation and clear no-records state; no unrelated firms |
| WIP-05 | Authorised users can add new WIP from an Account | Firm ID server-derived from Account route, prefilled/read-only in form, checked again on save; new row shown after refresh |
| WIP-06 | Manual case form uses validated fields | Required case reference, controlled status, valid dates, optional controlled fee/case/contingency types as defined; 400/422 for invalid submissions |
| WIP-07 | Financial entry is typed and precision-safe | Nonnegative GBP Decimal with two fractional digits; blank != £0; no numeric strings silently truncated; reject NaN/infinity/oversized amounts |
| WIP-08 | Duplicate-safe and edit-safe | Explicit per-firm case uniqueness policy; duplicate creation rejected; permitted edits audited; no accidental duplicate observation on retry |
| WIP-09 | Case and financial observations remain separate entities | WipCase linked to zero/many WipFinancialPeriod observations; controls preserve revision identity and provenance |
| WIP-10 | WIP data belongs to the Account, not the visual route string | Direct cross-Account tampering with submitted IDs is rejected; no WIP leak via alternate route/API |
| WIP-11 | WIP financial permissions separate from CRM contacts | Deny-by-default role in first synthetic MVP; direct GET/LIST/POST/PATCH/export/nested relationship tests block unauthorised users |
| WIP-12 | WIP records are auditable | Creator, last updater, created/modified times and changed-value history or immutable domain event evidence established |
| WIP-13 | WIP failure does not break core CRM | With WIP unavailable/error, Account/Enquiry/Contact/Activities core tasks still load; WIP panel displays bounded error |
| WIP-14 | No real data migration prerequisite for manual MVP | End-to-end UAT with synthetic WIP data on accepted CRM release before any workbook import |
| WIP-15 | Existing Account tabs preserved | Real-browser test existing Stream, Account, History/Activities and new WIP tab; no menu regression |
| WIP-16 | WIP record never writes CRM master attributes | Before/after fingerprint of Account/Contact/FirmGroup/Opportunity/master fields unchanged after create/update/import failures |
| WIP-17 | Correct display labels, no invented revenue | WIP and fees invoiced labelled as source/manual values; `revisedOrActualYield` not called actual revenue; no Revenue KPI until PO definition |
| WIP-18 | Manual form protects against spreadsheet-era input defects | Invalid years, malformed dates, repeat headers where relevant, currency precision and cross-field validation are rejected or flagged clearly |

## Group-WIP and subsequent workspace requirements

| ID | Requirement | Observable acceptance |
|---|---|---|
| GRP-01 | Query current group WIP via authoritative FirmGroup membership | Two member firms appear in one current-group WIP list; ungrouped excluded; no duplicates |
| GRP-02 | Firm moved groups changes current group visibility, not WIP rows | Old group query loses that firm's cases; new gains them; WIP financial hashes unchanged |
| GRP-03 | Group views honour finance ACL | A user who can see group names but lacks WIP role cannot retrieve financials via UI/API |
| GRP-04 | Group totals require approved financial observation selection policy | No additive multi-revision 'revenue' result; before approved metric display records/lists only or clearly labelled non-additive summaries |
| MOD-01 | Future left nav **WIP/Revenue** is functional, not dummy | After Account MVP, menu opens a real cross-firm list/search with appropriate ACL and links back to firms/cases |
| MOD-02 | Original WIP repo never becomes a runtime source dependency | CRM release succeeds from CRM repository and pinned external dependencies only; legacy repository unchanged |

## Source importer and later financial reporting requirements (not first MVP)

| ID | Requirement | Observable acceptance |
|---|---|---|
| IMP-01 | Establish actual workbook/CSV transport contract | Operator evidence states file type, version, authorship, checksum, source authority and update cadence |
| IMP-02 | Accept all ten missed valid monthly worksheet names | Synthetic fixtures cover all variants; no silent skipped valid sheet; unexpected sheets logged explicitly |
| IMP-03 | Preserve instruction-month cohorts and revisions | Distinguish source instruction cohort from observation/revision timestamp; repeated cases never automatically sum as flows |
| IMP-04 | Deterministic Account matching only | Exact source Salesforce Account ID → CRM `sfId` → CRM Account ID; unmatched review queue; no fuzzy auto-create |
| IMP-05 | Consistent idempotent import | Source file hash and immutable row/observation identity; repeated source load yields zero unintended writes; counts/sums reconcile |
| IMP-06 | Transparent rejects & corrections | Missing firm names, invalid dates/Decimals, ambiguous identities and impossible years recorded; no silent drops |
| IMP-07 | Finance import read/write least privilege | Import actor can create/update WIP module records only; Account/Contact/FirmGroup mutation refused |
| IMP-08 | Preserve spreadsheet while transition | Workbook and legacy POC unchanged; data source retirement requires independent PO cutover gate |
| REV-01 | Revenue definition precedes Revenue metric | PO approved recognition basis, source, period, exception and reconciliation rules; no WIP/fees/yield relabel |
| REV-02 | Financial aggregation avoids double counting | Representative revised cases/cohort data reconcile to approved reference and group membership basis |

## Cross-cutting release acceptance

- Preserve all current customer records and the Salesforce import exception backlog (160 write rejections plus one recurring Contact update, as reported at beta); do not silently repair via these WOs.
- Maintain independent CRM beta and dev data; WIP synthetic acceptance must not touch live CRM source data or workbook.
- Repeat core CRM regression (Account, Contact, FirmGroup, Enquiry, Task, Meeting, Call, archived Emails, login/logout and role denial) before/after upgrade and rollback.
- Verify server-side ACL even when buttons hidden. No new privilege granted by permissive default scopes.
- Check no secrets, private customer/financial values, real Salesforce IDs, workbook rows or host addresses enter public GitHub/CI output. Record only anonymised counts and immutable restricted evidence references.
- Require Foundry WO contract: exact Issue, approved immutable WO version, verified host/worktree/engine separation, Engineer→Auditor→Tester→DevSecOps same-candidate PASS, real-browser tests, capped executions and evidence. Each WO/accepted release separately approved; beta deployment separately authorised.
