# Requirements traceability — Salesforce replacement

- **Status:** DRAFT.
- **Sources:** these are sanitised extracts of Estate Research's restricted requirements records:
  - the Salesforce usage assessment of 2026-11-03;
  - the PoC design, with gates G1–G7, timed scenarios S1–S6 and decisions D1–D9;
  - the management briefing.

  This public file names no firms or staff and gives no Salesforce identifiers or financial figures.
- **Status values:**
  - **Planned:** in an approved or drafted increment.
  - **Missing:** added to the backlog by this revision.
  - **Deferred:** deliberately later, with the reason given.

Nothing is built yet. "Planned" therefore means traced to a backlog item, not delivered.

*Note (2026-11-13):* the sentence above is historical, written at bootstrap. Implementation now exists on `main` and on the beta (see the Backlog's *Delivery evidence* table). The per-requirement status column below has **not** been re-assessed against that evidence; that needs a separate evidence pass. Statuses are left as written rather than claimed.

## Business requirements

| ID | Requirement (source) | Backlog | Status |
|---|---|---|---|
| R1 | Firms with head office and branch offices; 42% of firms are branches; the largest parent has 34 (G1-1, G1-2) | PBI-001 | Planned (CRM-001) |
| R2 | Same-name branches kept distinct (G1-3) | PBI-001 | Planned (CRM-001) |
| R3 | Firm fields: tier, industry, practice management system, **learning platform access** (G1-5) | PBI-001 | Planned (CRM-001 v1.2). Learning platform access was missing before v1.2. |
| R4 | Firm address taken from the Salesforce *shipping* address (82–84% filled; billing is about 1%) | PBI-001, PBI-005 | Planned. The mapping is stated in PBI-005. |
| R5 | Contacts at firms, 56% of them on branch offices; duplicate warnings (G1-4) | PBI-001 | Planned (CRM-001) |
| R6 | Search for firms, contacts and enquiries, with p95 under 1.5 s at full volume (G4-1 to G4-4) | PBI-001, PBI-004, PBI-012 | Firm and contact search planned. Enquiry search and full-volume timing **missing**; now in PBI-004 and PBI-012. |
| R7 | Enquiries: firm, contacts, stage Enquiry → Quoted → Instructed / Lost (loss reason required), quoted fee, service type as reference data (60+), introduced-by and channel (split from the Salesforce lead source), client reference, deceased name, case number, new or existing business, enquiry category (G2-1, G2-2, G2-5) | PBI-004 | Partly planned. The field list, required loss reason and split fields were **missing**; added to PBI-004. |
| R8 | Create an enquiry from a phone call in under 60 s (G2-4) | PBI-004, PBI-013 | **Missing.** Added to the acceptance criteria. |
| R9 | Activities: follow-up tasks with reminders, meetings and presentations, calls, calendar | PBI-003 | Planned |
| R10 | File a chosen Outlook email against a chosen enquiry; de-duplicate on Message-ID; unknown senders allowed; body only (G3-1 to G3-5, D5) | PBI-006 spike, PBI-014 | The production filer was **missing**; added as PBI-014. It is required for cutover, not for the beta. |
| R11 | Historic logged emails imported and linked to enquiries (G3-7) | PBI-005, PBI-012 | **Missing.** Now in the migration scope. |
| R12 | Named users only (no shared login); everyone reads everything; enquiries editable by owner and intake; admin only for setup; deletion of firms with enquiries blocked; field history on stage, fee and owner (G5-1, G5-2, G5-4, D8) | PBI-002 | Planned |
| R13 | Tabular lists with filters and CSV export, e.g. tier and region lists (S6) | PBI-001, PBI-002 | Full export is planned. **Missing:** filtered list exports, now in PBI-002. |
| R14 | ERic reads the CRM through a read-only API adapter; CRM firm id mapped to ERic's company key (G5-5, D6) | PBI-007 | Planned |
| R15 | Upstream upgrade with ER customisations, plus a clean rebuild from image + extension (G6-1, G6-2) | PBI-010 | **Missing.** Added. |
| R16 | Backup, restore and full export (G7-1, G7-2) | PBI-001 | Planned (CRM-001) |
| R17 | Staff at least as fast as in Salesforce on the six timed scenarios (S1–S6) | PBI-013 | **Missing.** Now the beta acceptance criterion. |
| R18 | Salesforce stays read-only throughout | All | Planned (constraint) |

## Container delivery requirements (mandatory, Product Owner 2026-11-09)

| ID | Requirement | Backlog | Status |
|---|---|---|---|
| R19 | The whole CRM deploys with Docker Compose: web application, background services, MariaDB, ER customisations, migration and maintenance jobs | PBI-016, PBI-017 | Dev stack planned (CRM-001). The release was **missing**; added as PBI-016. |
| R20 | Pinned images; reproducible configuration | PBI-001, PBI-016 | Planned (CRM-001 pins by digest) |
| R21 | Customer installation independent of ForgeV2, Claude, development-host paths and a Git checkout | PBI-016, PBI-017 | **Missing.** Added. |
| R22 | Runtime secrets and environment configuration kept outside the images | PBI-001, PBI-016 | Planned (CRM-001 uses an external env file) |
| R23 | Persistent data survives container replacement and upgrades | PBI-017 | **Missing.** Added. CRM-001 AC8 covers backup and restore only. |
| R24 | Tested installation, backup, restore, upgrade and rollback procedures | PBI-016, PBI-017 | **Missing.** Rollback and clean installation added. |
| R25 | Salesforce migration tooling runs as a reproducible container | PBI-005 | **Missing.** Added (`crm-migrate`). |
| R26 | The beta uses the same container architecture as production; no host PHP, MariaDB or application runtime | PBI-011, PBI-017 | **Missing.** Added. |
| R27 | Compose services, networks, named volumes and ER images are prefixed `crm-`; projects distinct per environment; container names generated by Compose | PBI-001, PBI-016 | Planned (CRM-001 v1.3) |

## Migration requirements

| ID | Requirement | Backlog | Status |
|---|---|---|---|
| M1 | Field and relationship mapping, object by object: Account, Contact, Opportunity → Enquiry, enquiry contact roles, Task, Event, EmailMessage and its relations, User | PBI-005 | **Missing.** Added. |
| M2 | Repeatable, idempotent import keyed on the Salesforce record id, with a rejects list | PBI-005 | **Missing.** Added. |
| M3 | Reconciliation per object, per parent firm and per owner, with every mismatch explained (G5-3) | PBI-005, PBI-012 | Planned in outline; now explicit. |
| M4 | Clean-up rules: split the lead source into introduced-by and channel; parse references out of enquiry names (≥95%, G2-3); map shared-login records to named users; fill missing countries; decide on archiving firms with no activity; resolve flagged duplicate sets before migrating | PBI-005 | **Missing.** Added. Two of these need business decisions. |
| M5 | Legacy notes (all imported in 2016) | PBI-005 | **Deferred.** A decision is needed: import as read-only history, or archive. |
| M6 | Parallel run, then switch-off, before summer 2027 and timed to the contract renewal | PBI-015 | Planned |

## Deferred and out of scope

| Item | Reason |
|---|---|
| Side-by-side Frappe CRM trial and re-scoring (PoC §9) | Replaced by a single EspoCRM build with Frappe as a gated fallback (CRM-D010) |
| Calendly connection; iOS app | Light use. Check during the beta whether a mobile browser suffices and whether a calendar link is needed. |
| Storing email attachments | D5: body only. Attachments would be a new capability. |
| Dashboards, forecasting, leads, campaigns, quotes, products, the social feed | Unused in Salesforce |
| Legal-entity firm model (D4) | Office-level records with a parent, as today; revisit only if billing or reporting needs it |

## Expanded scope (2026-11-13): Firm Groups and WIP/Revenue

- **Status:** CANDIDATE (2026-11-13), from the CGPT delivery package. It is merged here rather than kept as a separate addendum.
- **IDs:** collision-checked against `main` at `330978598ac6`; none of them is in use. The requirements themselves are in [`docs/requirements/crm-modules-requirements.md`](requirements/crm-modules-requirements.md).
- **Gate names:** CRM-FG-001 and CRM-WIP-001 to 004 are candidate WO titles. Their numbering is an open Architect decision (see the reassessment record, §7 row 8).

| Requirement family | Business intent | Proposed PBIs | Acceptance owner / delivery gate |
|---|---|---|---|
| FG-01..FG-10 | Group peers independent of parent, browse and edit membership, secure audit | 018 | CRM-FG-001; independent browser/API and PO UAT |
| FG-11 | Curated group population, no automatic tree seeding | 024 | Later mapping/seed operator gate and Matt decision |
| WIP-01..WIP-03 | CRM master identity, WIP domain model, derived group ID | 019, 021 | CRM-WIP-001, domain/API checks |
| WIP-04..WIP-19 | Simple Account WIP tab, validated manual entry, isolated finance permissions, no fabricated revenue | 020 | CRM-WIP-002, browser + backend + Matt UAT |
| GRP-01..GRP-04 | Query WIP across member firms using current CRM Group; no duplicate counts | 021, 027 | CRM-WIP-003, data/permissions/relationship evidence |
| MOD-01..MOD-02 | Dedicated left menu WIP/Revenue workspace after MVP | 022 | CRM-WIP-004, live functional navigation |
| IMP-01..IMP-08 | Reuse/transition current spreadsheet with reliable source data, reconciled history | 023, 025 | Later WOs, restricted operator import; source decisions |
| REV-01..REV-02 | Define and evidence real revenue and group financial calculations | 026, 027 | PO business semantics then independent financial validation |
| Foundry record reconciliation | Truthful Vision/PBI/status/provenance/external-code coverage | 029 | Next Rogue docs-only, exact candidate review |

### Existing requirement compatibility

- R1–R5 (firm/address/contact) remain CRM authority; FirmGroup does not replace R1 branch parent relation.
- R7–R11 (Enquiries/activities/email) remain unchanged and need regression, not reimplementation.
- R12 (staff generally read CRM) must **not** be interpreted as unrestricted WIP finance read; explicit WIP ACL exception in expanded product scope.
- R15, R19–R27 (upgradeability, pinned release, rollback, Docker) apply to every WIP/Group release.
- M1–M6 Salesforce migration remains separately bounded; WIP never writes Salesforce.

### Status mapping

Every PBI/requirement and release acceptance record must distinguish proposal, reviewed draft, exact approved, engineered/tested, operator deployed, Matt UAT accepted and production cutover. 'Delivered' in an agent report is not synonymous with product acceptance. Existing CRM repo documents have stale status claims; update based on exact GitHub/runtime evidence and preserve earlier historical text in Git history.
