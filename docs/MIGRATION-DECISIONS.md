# Migration decisions, entity contract and route to a real-data beta

- **Status:** PROPOSED, 2026-11-10 (rev. 2: D13 and §5 now name the External Client App and add O1), for CGPT Architect review. Business decisions marked **PO** need Matt's validation before they are final.
- **Evidence:** the accepted inventory (`docs/SALESFORCE-DATA-INVENTORY.md`), plus read-only aggregates of the ERiC copy (latest version of each record, 66,103 opportunities). Counts only; no record content.

## 1. Enquiry stage mapping (R7)

Every enquiry keeps its **original Salesforce stage** in a read-only field `sfStageName`. The mapped stage is derived from it, so nothing is lost and the mapping can be re-run.

| Salesforce stage | Count | Fee present | Avg probability | Loss reason set | Proposed target | Confidence |
|---|---:|---:|---:|---:|---|---|
| Qualification | 109 | 2.8% | 10 | 0.9% | Enquiry | high (rare, early stage) |
| Needs Analysis | 26,063 | 2.3% | 35 | 0.1% | Enquiry | **needs PO**: 99.6% have a close date in the past (see D2) |
| Proposal | 13,689 | 37.5% | 75 | 0.1% | Quoted | medium: only 37.5% carry a fee |
| Negotiation | 126 | 29.4% | 90 | 2.4% | Quoted | medium (rare) |
| Closed Won | 24,677 | 67.7% | 100 | 0.1% | Instructed | high |
| Closed Lost | 1,439 | 27.6% | 0 | 71.7% | Lost | high |

## 2. Business decisions, with recommended defaults

| # | Decision | Recommended default | Owner |
|---|---|---|---|
| D1 | Stage mapping above | Adopt the table. Keep `sfStageName` on every record. | **PO** confirms Proposal and Negotiation → Quoted |
| D2 | 26k "Needs Analysis" enquiries whose close date has passed | Import them as **Enquiry**, with a derived flag `legacyStale = true` (open, close date past). Do **not** auto-convert them to Lost, and do not invent a loss reason. Default list views hide stale ones. | **PO** |
| D3 | 28% of Closed Lost have no loss reason, but R7 requires one | The rule applies to records created or edited in the CRM. Legacy records keep a blank value and `lossReasonLegacyMissing = true`. Nothing is invented. | **PO** |
| D4 | Enquiries owned by the shared "Ancillary Services" login | Create a **disabled** legacy user, "Ancillary Services (shared, legacy)", and make it the owner of those enquiries, assigned to an **Ancillary intake team**. The original owner id is preserved. Nobody is guessed. The team works the queue; re-attribution is a later, explicit business task. | **PO** |
| D5 | Inactive Salesforce users | Create them as **inactive** users, with no login, so historic ownership stays recognisable. | default |
| D6 | Legacy Notes (M5) | Extract and **preserve** them in the snapshot (CRM-002). Deciding whether to import them as read-only history is separate. Nothing is discarded. | **PO** |
| D7 | `LeadSource`: staff initials mixed with channels (M4) | Keep the raw value in `sfLeadSource`. Derive "introduced by" (a user) and "channel" only through an explicit lookup table that the PO approves value by value. Unmapped values stay blank. | **PO** approves the lookup table |
| D8 | References inside the enquiry name (client ref, deceased name, case number; M4, ≥95%) | Parse with tested patterns. Keep the original name. Failures are listed in the rejects/notes report and never guessed. | default; the threshold is checked at L3 |
| D9 | Enquiry entity | Reuse EspoCRM's **Opportunity** entity, labelled **"Enquiry"**, with ER's own stages and fields. This keeps the standard pipeline, reports and activity links with the least engineering. A separate custom entity is only needed if the PO wants Opportunity kept for something else. | **PO** |
| D10 | Untyped Events (1,627) | Import them as Meetings, with type "Unspecified (legacy)". | default |
| D11 | Email history | Archived, read-only Email records, linked to the enquiry, contact and firm. Body only; no attachments, no HTML, no sending, no live mailbox. | default (R10/R11, D5) |
| D12 | Firms with no activity (M4) | Import everything. Archiving is decided after the beta. | default |
| D13 | Salesforce access | A dedicated read-only integration user (Salesforce Integration licence, API only) as the Run As user of an **External Client App** using OAuth client credentials, set up per `docs/SALESFORCE-ADMIN-SETUP.md`. An existing Connected App is only a verified fallback. ERiC's credentials are not reused. | **PO / Salesforce admin** |

## 3. Shared entity contract for CRM-003 to CRM-005 (proposed)
- **Salesforce id fields.** Every migrated entity has `sfId` (varchar 18, unique index, read-only in the UI) and, where useful, `sfCreatedDate` and `sfCreatedById`. Loads are idempotent on `sfId` (M2).
- **Users.** `User.sfId`, with teams `Enquiries`, `Ancillary intake` and `Firm management`. The access model is R12: everyone reads; enquiries are edited by the owner and intake; admin only for setup; deleting a firm that has enquiries is blocked; field history on stage, fee and owner.
- **Enquiry (Opportunity).**
  - Links: `account`, `assignedUser`, `contacts` (enquiry contacts with role), `teams`.
  - Fields: `stage` (Enquiry, Quoted, Instructed, Lost), `quotedFee`, `serviceType` (a reference list, 60+ values, admin-editable), `lossReason`, `introducedBy`, `channel`, `clientReference`, `deceasedName`, `caseNumber`, `businessType` (new/existing), `category`, `postcode`, `keyInformation`.
  - Legacy: `sfStageName`, `sfLeadSource`, `legacyStale`, `lossReasonLegacyMissing`.
- **Activities.** Standard Task, Call, Meeting and Email, each with `parent` (Enquiry or Account), `contacts` and `assignedUser`. Emails are archived (`status = Archived`), with `sfId` taken from the EmailMessage.
- **API.** Everything is reached through the EspoCRM REST API, using an import user with an API key. ERiC reads through a read-only API user (PBI-007).
- **File ownership.**
  - CRM-003 owns users, teams, roles and the audit metadata.
  - CRM-004 owns the Opportunity/Enquiry metadata and layouts.
  - CRM-005 owns the activity metadata and layouts.
  - Account and Contact layout changes are serialised: CRM-004 first, then CRM-005.

## 4. Dependency-aware sequence

1. **Accept CRM-001.** This needs Matt's AC10 walkthrough. Then merge #5, then #6. CRM-003 onward builds on `custom/` and the scripts, which exist only in those PRs.
2. **In parallel, because file ownership is separate:**
   - **CRM-002**, the extractor. It sits only under `migrate/`, `deploy/migrate/` and `tests/migrate/`, and is based on `main`.
   - **CRM-003**, users, roles and audit. It is based on `main` after #5 and #6 merge.
   - **CRM-006a, hardening.** It covers:
     - restore source confinement;
     - the extraction-scope check;
     - CSV formula neutralisation;
     - the `mv -T` test;
     - export's LAN default.

     It touches only `scripts/` and `tests/unit/` and is parallel to CRM-003.
3. **CRM-004**, the Enquiry workflow, after CRM-003, because it needs teams and roles.
4. **CRM-005**, activities and the email archive, after CRM-004, because it needs Enquiry as a parent.
5. **L1 → L2** live metadata and counts, as soon as CRM-002 is accepted, each under its PO authorisation. The contract is corrected if L1 finds missing fields.
6. **PBI-005 part 2: the loader and reconciliation.** It needs CRM-002 to CRM-005. It is developed against synthetic and pseudonymised snapshots (PoC P2).
7. **PBI-016, release packaging** (`crm-espocrm` image, release bundle), then **PBI-017, clean-host acceptance** (retained, per the Architect's decision of 2026-11-10).
8. **PBI-011, the `crm-beta` environment**, from the accepted release, with:
   - TLS on the PO's HAProxy, and subnet enforcement there, where real client addresses are visible;
   - named logins, roles and audit;
   - daily backups with a tested restore;
   - access and disposal rules.
9. **The PO's data-protection approval**, then **L3** extraction, then the **beta load** (PBI-012), with reconciliation published sanitised.
10. **Staff beta** (PBI-013).

## 5. Evidence required before any Salesforce access
- **Before L1 (metadata):**
  - CRM-002 is accepted by the Architect;
  - the integration user and External Client App exist per `docs/SALESFORCE-ADMIN-SETUP.md` (or the verified Connected App fallback), with no Create, Edit or Delete granted;
  - O1, the synthetic self-test in the real container on DOCKER1, has passed;
  - `/srv/CRM/runtime/migrate` is prepared;
  - the PO's L1 authorisation is recorded on the CRM-002 Issue.
- **Before L2 (counts):** the L1 result shows every object as non-createable, non-updateable and non-deletable, and every field readable, plus the PO's L2 authorisation.
- **Before L3 (records):**
  - the PO's data-scope authorisation, naming the objects, date range, purpose, storage path, retention and disposal;
  - for the beta, the data-protection approval as well (PBI-011);
  - the snapshot location verified as root-only;
  - an agreed sanitised-evidence format.
