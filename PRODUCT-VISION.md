# Product Vision — Estate Research CRM

- **Status:** CANDIDATE revision (2026-11-13), FOUNDRY Stage 1 v0.4 existing-product reassessment. Matt has agreed the product concepts in conversation; **this exact version is not yet approved**. It needs Matt's explicit approval of the exact path and commit (FOUNDRY product-record standard).
- **Prepared by:** CGPT Architect (content, 2026-11-13); reconciled into this repository by Rogue (2026-11-13). See [`docs/initiation/2026-11-13-existing-product-reassessment.md`](docs/initiation/2026-11-13-existing-product-reassessment.md).
- **History:** the previous Vision (Rogue, 2026-11-06, DRAFT, never approved) is kept below under [Retained from the 2026-11-06 Vision](#retained-from-the-2026-11-06-vision), with its supersessions marked. Its full text is in Git history.
- **Governing FOUNDRY:** `maff0000/foundry@5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0`.

## Purpose, problem and beneficiaries

Estate Research Limited is replacing Salesforce with its self-hosted EspoCRM. Its spreadsheet-driven WIP proof of concept has a separate copy of firm identities, a broken legacy importer, and financial terminology that has not been fully established. Multiple interfaces and competing customer masters are costly to operate, reconcile and improve.

Users are business-development staff, enquiries/ancillary teams, firm management, finance/WIP staff and administrators. They should work against one authoritative firm/contact/relationship set, using independently maintainable CRM modules. Commercially sensitive WIP information must be restricted independently of ordinary contact access.

## Product Goal

**A single Estate Research CRM in which firms, contacts, Firm Groups, enquiries, activities and users are authoritative; authorised staff can open any firm, view and maintain that firm's WIP records through a simple validated WIP/Revenue tab, and later manage WIP across firms and groups through a dedicated module — without maintaining another customer master or breaking core CRM workflows.**

## First MVP outcomes (priority over broad financial reporting)

1. A **FirmGroup** is an independent CRM record: two peers may join the same group without declaring either parent. Each Account may have zero or one `firmGroup`; managers can maintain membership, staff can navigate linked members. Salesforce `Account.parent/branches` remains a separate historical relationship.
2. An Account detail record has **WIP/Revenue** alongside its existing Stream/Account areas. It lists WIP cases and their associated financial observations for **that Account only**, with a clear empty state, clickable cases, and an **Add WIP entry** action for authorised users.
3. The **New WIP entry** form automatically resolves the current immutable `Account.id`; firm identity is not typed or chosen. Controlled fields, meaningful type/date/GBP validation, duplicate checks, server-side authorisation and an auditable create/edit path prevent incorrect entries.
4. The WIP model exposes both `firmId` (the case's CRM `Account.id`) and **current** `groupId` (the Account's CRM-derived `firmGroup.id`, nullable). Group WIP retrieval uses CRM membership, not a WIP-maintained mapping. Moving a firm updates its current group view without rewriting historical financial rows.
5. WIP is separately owned within the **CRM repository and release**. CRM keeps running if WIP data or imports are unavailable. The original WIP repository, database, workbook and existing workflow remain unchanged until independently approved transition.
6. Revenue is **not invented**: the source workbook has no proven revenue calculation. MVP accurately shows WIP, fees invoiced and correctly labelled source yield/estimate fields; the Revenue component remains deferred until Estate Research defines it.
7. Later: an explicit **WIP/Revenue left-navigation module** for cross-firm, group, case, import/reconciliation and approved financial reporting. It builds upon the Account-tab model rather than replacing it.

## Observable success criteria

- Given two independent CRM Accounts with a common FirmGroup, both are selectable from Group Members without altering either `parent` link. Unlinking and moving are auditable and have server-side manager permissions.
- From an Account record, permitted staff can create a WIP case plus one financial observation with valid data, see it on the same firm's tab and later edit it; it never appears under an unrelated firm.
- A staff user without finance access cannot see, retrieve by URL or API, or edit financial rows; direct REST requests are denied.
- A grouped firm exposes a derived group identity and group WIP listing includes all and only current member Accounts with no duplicate cases. Changing membership does not alter WIP records.
- No CRM Account, Contact, FirmGroup, Salesforce ID, parent hierarchy, Enquiry, Task, Call, Meeting or Email is modified by a WIP operation. Regression tests and real-browser flows remain green after release and rollback.
- Invalid or duplicate entries are rejected clearly; null differs from £0; saved amounts use Decimal/GBP precision. Relevant changes have author, timestamp and before/after evidence.
- Existing CRM beta UAT data remains intact; every release is traceable to an exact source revision and recoverable backup.

## Ownership, modularity and dependencies

CRM is authoritative for Account/Firm/Branch, Contact, FirmGroup, Opportunity/Enquiry, staff identity and business relationships. WIP owns its **financial case references**, financial observations, manual entry, imports, validation and future reporting. WIP's financial-case record is not a replacement for any independent operational/legal Case Manager system. Both use one EspoCRM application/MariaDB deployment, with WIP-owned code and data models plus minimal platform-supported integration. This is **logical modularity, not independent process isolation**. Engineering must test failure containment.

A WIP case stores a required `accountId` (CRM Account foreign reference). `firmGroupId` is exposed as **derived current membership**, not an independently editable field. Historic group-as-of reports, if required, need a later versioned membership-history policy.

## Scope and non-goals

**In scope:** FirmGroup model and Account Group Members tab; WIP Account tab; synthetic-only WIP entities; validated manual entry; financial access control; native module architecture; later left-navigation scaffold and incremental reports/imports.

**Not MVP:** workbook/CSV migration, revenue recognition, source-retirement, historical group-as-of financial reporting, automatic case-to-enquiry matching, ERP/general ledger, blanket import of all Salesforce parent trees as groups, or automatic Account creation from WIP names.

**Never incidental:** changes to `maff0000/foundry`, `maff0000/forgev2`, original `infosec-estateresearch/WIP`, Salesforce, legacy host jobs or unrelated ER systems.

## Constraints, evidence and open business decisions

- CRM beta reported populated at `infosec-estateresearch/CRM@330978598ac6147d4a1bce3f713113d59045d465` (Issue #9; host UAT from Rogue). Salesforce remains the authoritative external source until separate CRM cutover.
- HELM host audit (2026-11-13) reports WIP repo `91b2af19877b498ed307ee9f1218b3243b2b60ba`; 11,758/11,776 cases tie deterministically to CRM Accounts through exact Salesforce IDs; 18 cases have unresolved firms; no reliable case↔Enquiry match.
- HELM verified month sheets are mainly instruction-month cohorts, not monthly flows/snapshots; `actual_yield` is a blended revised estimated/actual field; no workbook revenue formula exists; ten source sheets were skipped; historical data requires later reconciliation before migration.
- 36 curated WIP groups do **not** match the 1,366 CRM parent trees; initial FirmGroup module stays unseeded. Curated member review is later.
- Workbook is a transitional input, but whether the current exchange is XLSX or CSV needs an evidence-backed interface contract; do not block *manual entry MVP* on that.
- Financial viewing/editing roles, operational WIP source retirement, historical group reporting, revenue meaning and some legacy case/status mapping need PO decisions before dependent functionality. Initial synthetic MVP may use a dedicated no-access-by-default finance role and admin UAT.
- UK GDPR personal data and financial commercial sensitivity; public GitHub contains no customer IDs, names, spreadsheet content or secrets. Temporary beta HTTP/common-password exception is **UAT-only**, not production approval.

## Provenance and approval

This is a proposed revision to the existing product's living Vision. When Rogue stages it in a GitHub docs candidate, CGPT must critically review its exact immutable path/commit, and Matt must explicitly approve that same version and the Backlog in a traceable GitHub record. This document does not grant a Work Order or deployment authority.

## Retained from the 2026-11-06 Vision

The purpose, users, measured use and outcomes below remain valid. The expanded scope above adds to them, and the supersessions are marked inline.

### Purpose

Estate Research uses Salesforce as three things:
- an address book of law firms and their people;
- an enquiry log;
- an email filing cabinet.

We will replace it with a self-hosted CRM that we own, with no licence fees, shaped around how we actually work. It must be in place before Salesforce retires the login method ERic depends on (summer 2027).

### Who it serves

- **Business development:** looks up firms, records meetings and presentations, sets follow-ups, pulls regional lists.
- **Enquiry and ancillary services:** logs requests from firms, files the related emails, quotes fees, records instructions.
- **Administration:** imports data and produces lists.

About 21 staff use it daily. Everyone gets a named login; there will be no shared accounts.

### What matters most (measured daily use in Salesforce)

| Use | Per day |
|---|---|
| Open a firm record | ~430 |
| Search for a firm, person or enquiry | ~110 |
| Log an enquiry | ~75 |
| File a chosen Outlook email to an enquiry | ~28 |
| Add a contact | ~25 |
| Set a follow-up | ~23 |
| Record a meeting | ~4 |

### Product Goal for the first releases (2026-11-06)

**Staff can find any firm, see its head office and branches, and find and maintain the people at those firms at least as fast as in Salesforce, on a CRM Estate Research runs itself.**

### Outcomes (2026-11-06)

1. Firms and contacts are managed in the new CRM, including head office and branch structure. 42% of firms are branches. *(2026-11-13: the parent/branch structure is kept; independent Firm Groups are added alongside it, CRM-D023.)*
2. Activities (calls, meetings, follow-ups) and enquiries follow in later increments.
3. Selective Outlook email filing works with any CRM, through an ER-owned service.
4. ERic reads the CRM through a read-only API, never through SQL.
5. Salesforce data is migrated with record-by-record reconciliation, and Salesforce is switched off.

### Out of scope (2026-11-06)

Dashboards, forecasting, quotes, products, marketing campaigns (these stay in the existing email platform), an internal social feed, and recreating Salesforce in general.

*Note (2026-11-13):* still out of scope. WIP/Revenue reporting is a separately gated capability (CRM-PBI-026/027), and no Revenue metric is shown until revenue is defined (CRM-D028).

### Constraints (2026-11-06)

- Open source and free. Estate Research keeps its own version.
- Core changes are kept separate (ER extension plus numbered patches), so upstream security fixes still apply.
- Salesforce stays **read-only** throughout.
- No real personal data until the security gates are met.
- Marketing, Email Builder, EmailEngine, ERic, WIP and Case Manager are not affected by CRM work.
  - *Superseded in part (2026-11-13):* this still holds for the **legacy** WIP application, database, workbook and repository, which CRM work never changes. A new WIP/Revenue module is now proposed **inside** the CRM (CRM-D020 to D022).
