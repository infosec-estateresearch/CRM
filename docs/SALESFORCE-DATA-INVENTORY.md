# Salesforce data inventory on DOCKER1 (read-only), 2026-11-10

- **Status:** READY_FOR_CGPT.
- **Authority:** PO / Architect product-direction correction of 2026-11-10, which authorised a read-only inventory of the ELT/ERiC data sources.
- **Sanitised:** this document holds counts, field names and business reference values only. It contains no personal data, firm names, user names, addresses or record contents.

## 1. Method
- **Source:** the ERiC Salesforce copy in the ERiC MariaDB (`nif_elt`) on DOCKER1. Salesforce is source 93 in `raw_ingestion`, plus the derived tables `sf_activity_materialised`, `sf_user_lookup`, `sf_account_company_bridge` and `sf_opportunity_case_link`.
- **How it was read:**
  - each session was set `READ ONLY` before any query (`@@tx_read_only = 1`);
  - queries used a throwaway MariaDB client container;
  - only `SELECT`s against information_schema and aggregates were run;
  - only the latest version of each record (highest ingestion id per Salesforce id) was counted.
- **Not touched:** no ERiC/ELT service, container, timer or file was changed, restarted or written. Salesforce itself was **not** queried for this inventory.
- **Compared against:**
  - the November usage assessment (`/home/ELT/docs/crm/01_salesforce_usage_and_selection.md`, from read-only SOQL);
  - this repository's `docs/REQUIREMENTS-TRACEABILITY.md` (R1–R18, M1–M6).

## 2. What exists locally

| Salesforce object | Records (latest) | Created range | Freshness |
|---|---:|---|---|
| Account | 9,003 | 2016-07 → 2026-11 | last synced 2026-11-06 |
| Contact | 25,677 | 2016-07 → 2026-11 | 2026-11-06 |
| Opportunity (enquiries) | 66,103 | 2016-07 → 2026-11 (16,124 created in 2026) | 2026-11-06 |
| Task | 43,841, of which **34,037 are Email**, 9,297 Task and 507 Call; 1,205 open | 2018-02 → 2026-11 | 2026-11-06 |
| Event | 2,581 (Meeting 475, Presentation 439, untyped 1,627, other 40) | 2021-03 → 2026-11 | 2026-11-06 |
| User (lookup only) | 29 (26 active): id, name, email, active flag | — | 2026-07-06 |

**Freshness and completeness caveats:**
- The ERiC Salesforce sync timer is **inactive**. The last run was 2026-11-06, so the copy is about 4 days old and getting older.
- The sync is incremental on `LastModifiedDate`. It **does not record deletions**, so the local counts may include records that have since been deleted in Salesforce.
- The local copy is a working copy for ERiC, not a migration source of record.

**Captured fields:**
- **Account:** Id, Name, Type (tier), Phone, Website, Industry, **Billing** address, Description (= practice management system), NumberOfEmployees, AccountSource, OwnerId, LastActivityDate, Created/LastModified, `Interested_in_integration__c`, `Bankruptcy_Special_Rate__c`, `TLP__c`.
- **Contact:** Id, AccountId, First/Last name, Email, Phone, Mobile, Title, Department, Mailing address, Created/LastModified. **No OwnerId.**
- **Opportunity:** Id, AccountId, Name, StageName, Amount, Probability, CloseDate, Type, LeadSource, Description, Created/LastModified, `Loss_Reason__c`, `Paid_geneology_enquiry__c`. **No OwnerId.**
- **Task:** Id, AccountId, WhoId, WhatId, Subject, Status, Priority, ActivityDate, Description, CallType, CallDurationInSeconds, CallDisposition, TaskSubtype, CompletedDateTime, IsClosed, OwnerId, Created/LastModified.
- **Event:** Id, AccountId, WhoId, WhatId, Subject, ActivityDate/DateTime, Start/End, DurationInMinutes, Location, Description, Type, OwnerId, Created/LastModified.

**Reference values present (counts, latest versions):**
- **Opportunity stage:** Needs Analysis 26,063 · Closed Won 24,677 · Proposal 13,689 · Closed Lost 1,439 · Negotiation 126 · Qualification 109. These are Salesforce defaults that staff use as enquiry stages, so mapping them to Enquiry → Quoted → Instructed / Lost (R7) is a business decision.
- **Opportunity type:** Existing Business 45,885 · New Business 10,596 · blank 9,622.
- **Loss reason:** set on 1,092. Top values: No longer needed, Unable to work in that country, Other, Lost to Competitor, Price.
- **`Paid_geneology_enquiry__c`:** Yes 12,371 · No 12,005 · Ancillary 4,468 · Legal rights check 398 · Overseas Assets 62 · Share Sale 11 · blank 36,788.
- **LeadSource:** 37 distinct values (staff initials and channels, per the assessment); blank 3,374. The values are not reproduced here.
- **Account type:** Tier 1–5, Prospect, Closed/Ceased Trading, Enquiring Client, Client, Partner, Integrator; blank 1,488.
- **Account industry:** Solicitor 6,464, then Barrister, Other Legal Service, Accountant, Will Writer, Other Financial Institution, Trust Company and others.
- **TLP access:** No 6,466 · TLP 670 · Full Access 216 · E-Course 70 · blank 1,581.

**Activities and correspondence (ERiC-materialised view):**
- **Email Tasks:** all 34,791 materialised Email Tasks carry a body in `Description`, averaging about 5,000 characters. This is the Outlook-logged email text, body only.
  - 31,980 of them link to an Opportunity (`WhatId`) and 25,217 to a Contact (`WhoId`).
  - Header fields (from, to, cc, direction, message id) are **not** present; those live on EmailMessage and EmailMessageRelation.
- **Ownership:** every materialised Task and Event owner resolves to a known Salesforce user (13 distinct Task owners, 15 Event owners).
- **Upcoming work:** open and future-dated items exist, with activity dates up to 2027, so "work to do next" can be shown.

## 3. Coverage against the migration requirements (M1) and a credible demo

| Needed (requirement) | Locally available | Gap |
|---|---|---|
| Firms with branch hierarchy (R1, R2) | Accounts | **`ParentId` missing.** The branch hierarchy cannot be rebuilt. 42.5% of accounts are branches. |
| Firm address from the **shipping** address (R4) | Billing only, 0.8–1.5% filled | **Shipping address missing** (82–84% filled in Salesforce) |
| Firm fields: tier, industry, PMS, TLP (R3) | Yes | — |
| Contacts linked to firms (R5) | Yes | Contact owner missing (not required) |
| Enquiries with stage, fee, loss reason, type (R7) | Opportunity core fields | **OwnerId missing.** Also missing: `Opportunity_Service__c` (service type, 60+ values, since 08/2026), `Post_code__c`, `Key_Information__c`, and **OpportunityContactRole** (23,125 enquiry contacts). The deceased name, client reference and case number must be parsed from Name (M4). Opportunity→case links (2,021) exist in ERiC. |
| Enquiry owner, so staff recognise their records (R12) | LeadSource initials (37 values) | Opportunity OwnerId needed. The "Ancillary Services" shared login must be mapped to named people (M4); the source has no data for this, so it is a business decision. |
| Named users (R12) | 29 users (name, email, active) | Profile and permission data missing. The assessment found 5 System Administrators and 17 Standard Users, and no roles. |
| Activities: tasks, calls, meetings, presentations (R9) | Yes, with owners | Reminders and recurrence not captured |
| Historic emails (R11) | **Bodies via Email Tasks** (34k) | EmailMessage headers and EmailMessageRelation (sender and recipient matching) missing. The assessment counts 34,005 EmailMessages. Attachments: 77% had them, but only 3 files are stored in Salesforce, so the import is body-only (D5). |
| Notes (M5) | None | Not captured. They were all imported in 2016, and there is a pending decision on whether to import them. |
| Deletions / authoritative snapshot (M2, M3) | No deletion tracking | A fresh extraction is needed for reconciliation |

**Conclusion:**
- The local ERiC copy is enough to **analyse and prototype** activities, email bodies, tiers and reference values.
- It is **not enough** to migrate a recognisable CRM. The branch hierarchy, shipping addresses, enquiry owners, service types, enquiry contacts, email headers and relations, and deletions are all missing, and the copy is going stale.
- A **fresh, read-only, full extraction from Salesforce** is required. The ERiC copy then serves as a cross-check in reconciliation.

**L1 schema result (2026-11-10, CRM-002-U):**
- Salesforce has **no enquiry postcode field**: `Opportunity.Post_code__c` is a self-lookup to Opportunity, not a postcode. It is not extracted, and CRM-004 `postcode` stays empty on import.
- Salesforce has **no key-information field**: `Opportunity.Key_Information__c` does not exist. CRM-004 `keyInformation` stays empty on import.

## 4. Shortest safe sequence of bounded work orders

Each one is a separate work order with Architect exact-version approval, the ForgeV2 loop with independent review, and no real data in Git, CI or specialist prompts.

1. **CRM-002: Salesforce extraction and mapping specification (PBI-005, part 1).**
   - A read-only `crm-migrate` extractor container runs a full snapshot of Account (+ParentId, Shipping), Contact, Opportunity (+OwnerId and custom fields), OpportunityContactRole, Task, Event, EmailMessage, EmailMessageRelation and User.
   - The snapshot is stored in a root-only restricted runtime and never enters Git.
   - The work order also delivers the object-by-object mapping specification (M1) and a profiling report with counts and fill rates.
   - Development uses a **pseudonymised sample only** (PoC P2, needing Matt's approval).
2. **CRM-003: Named users, roles and audit (PBI-002).**
   - Users are created from Salesforce Users, with the R12 access model: everyone reads; enquiries are edited by owner and intake; admin for setup only; protected deletion; field history on stage, fee and owner.
   - Each user gets a strong unique temporary password with a forced change at first login, if EspoCRM supports it; otherwise a documented equivalent.
   - Salesforce passwords are never read, and no invitations are emailed.
3. **CRM-004: The Enquiry workflow (PBI-004).** An Enquiry in Estate Research's own terms (R7):
   - Enquiry → Quoted → Instructed / Lost, with a required loss reason;
   - quoted fee, service-type reference list, introduced-by and channel;
   - client reference, deceased name, case number, new or existing business;
   - enquiry contacts.
4. **CRM-005: Activities and the email archive (PBI-003 with R11).**
   - Tasks and calls, meetings and presentations, follow-ups with reminders, and the calendar.
   - Historic emails as read-only archived Email records linked to the enquiry, contact and firm. No live mailbox and no sending.
5. **CRM-006: Beta environment (PBI-011).**
   - A separate `crm-beta` project and runtime, never mixed with `crm-dev`.
   - TLS via the PO's HAProxy, and subnet enforcement at a component that sees real client addresses (see §5).
   - Named logins, a daily backup with a tested restore, audit enabled, and documented access and disposal rules.
6. **CRM-007: Load and reconciliation (PBI-005 part 2, PBI-012).**
   - An idempotent loader keyed on the Salesforce id, with a rejects list.
   - Reconciliation per object, per parent firm and per owner, with every mismatch explained.
   - It runs only after the data-protection gate. Salesforce stays read-only and authoritative.

Steps 2–4 can be built and reviewed on synthetic data and the pseudonymised sample, in parallel with step 1. Steps 5–7 are serial.

**Decision for the PO:** the backlog requires the beta to be deployed from the release bundle that has passed clean-host acceptance (PBI-016 and PBI-017). Keeping that gate adds two work orders before step 5. Deferring it to before production is shorter, but it departs from the documented plan.

## 5. Security and data-protection prerequisites before any real record is loaded
- **Matt's data-protection approval** (PBI-011), covering lawful basis, access list, retention and disposal. It is the hard gate before identifiable data. The pseudonymised sample needs its own approval (PoC P2).
- **TLS** on the beta endpoint. The PO has stated that HAProxy will terminate it.
- **Effective source restriction.** On DOCKER1, Docker relays published-port connections through `docker-proxy`, so the application cannot see client addresses. The restriction must therefore sit in a component that sees them: the PO's HAProxy, or a host-network proxy inside the CRM project. The dev stack currently runs bind-only under a PO override, which is not acceptable for real data.
- **Individual authentication**, with no shared logins, roles enforced and audit on.
- **Protected storage:**
  - the extract and backups in a root-only runtime;
  - backups encrypted, or held on an access-controlled store;
  - Salesforce credentials for `crm-migrate` supplied at runtime and never stored in the CRM repository, images or prompts;
  - preferably a dedicated read-only integration user rather than ERiC's credentials.
- **Process controls:**
  - no real data in Git, GitHub, CI or ForgeV2 specialist prompts or scratch;
  - real-data loads run only by the operator;
  - evidence posted publicly is sanitised (counts only).
- **Salesforce stays read-only:** no write path in the extractor, verified by test and by the integration user's permissions.
- **The deferred restore and export hardening is fixed first:**
  - restore source confinement;
  - the extraction-scope check;
  - CSV formula neutralisation.
