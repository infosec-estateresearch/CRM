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
