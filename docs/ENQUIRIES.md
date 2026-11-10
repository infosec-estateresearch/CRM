# Enquiries (CRM-004)

Enquiries use EspoCRM's standard **Opportunity** entity, relabelled "Enquiry" / "Enquiries" in the UI (decision D9: reuse Opportunity). The entity name, API path and database table stay `Opportunity`. All data used to build and test this is synthetic.

## Workflow

Stages: **Enquiry → Quoted → Instructed**, or **Lost** at any point.

| Stage | Probability | Meaning |
|---|---|---|
| Enquiry | 10 | A new enquiry. The default for new records. |
| Quoted | 50 | A fee has been quoted (`amount`, labelled "Quoted fee"). |
| Instructed | 100 | Instructed. EspoCRM's core "Won" filter shows these. |
| Lost | 0 | Lost. A loss reason is required. EspoCRM's core "Lost" filter shows these. |

The stage, quoted fee, assigned user, close date, loss reason and service type are audited. Each change appears in the record's history with the user and the time.

**Quoted fee and close date are optional.** EspoCRM 10.0.12 makes the core Opportunity fields `amount` and `closeDate` required. The custom entityDefs set `"required": false` on both, and both stay audited. Two things need this:
- the quick create (R8) does not ask for them;
- the importer must never invent a fee, and in Salesforce only 2–68% of enquiries carry one, depending on stage.

`name` stays required. The policy rule `fee_and_close_date_optional` fails if either field is required again.

**Quick create (R8).** The quick-create form (layout `detailSmall`) asks only for the firm (account), contact, service type, name and description, so an enquiry can be logged during a phone call.

**Loss reason (R7, D3).**
- In the browser, the loss reason appears and becomes required when the stage is Lost.
- On the server, the `beforeSave` hook `custom/Espo/Custom/Hooks/Opportunity/RequireLossReason.php` refuses (400 Bad Request) to save an enquiry as Lost without a loss reason. There are two exceptions, and both apply only to records flagged `lossReasonLegacyMissing` (Salesforce records closed as lost without a reason):
  - the `ER Import` API user may write such a record. The hook checks both that the user's type is `api` and that its userName is `er-import`, as in `config/access/api_users.json`. Any other API user is treated like a person.
  - anyone may save such a record as long as neither the stage nor the loss reason changes. This lets people edit other fields on old lost records.
- People cannot set the flag, because their roles make it read-only. Admins bypass role field ACL, so an admin can edit the flag and the other legacy fields. This is an accepted limit.
- Browser-side, the loss reason is not required on a flagged record. Otherwise the form would block the edits the server allows.

**Stages are merged with core.** EspoCRM merges custom metadata into core recursively. Core keys that the custom stage definition does not override (for example core entries in `probabilityMap` or `style`) may therefore survive the merge. This is an accepted limit, and the rules check only the keys this change sets.

**Labels elsewhere.** The `opportunities` relation on firms (Account) and contacts (Contact) is labelled "Enquiries". This is done in `i18n/en_US/Account.json`, merged into the CRM-003 labels, and in a new `i18n/en_US/Contact.json`. Both override only `links.opportunities`.

**Lists.** The default list is **Open enquiries**: stage Enquiry or Quoted, and not legacy stale. The other primary filters are **My open enquiries** (open enquiries assigned to me), **Legacy stale** (D2), and EspoCRM's core Won and Lost filters. The search filters cover stage, assigned user, service type, enquiry category and legacy stale. The list columns are name, firm, stage, quoted fee, service type, assigned user and close date.

**Access** (`config/access/roles.json`, CRM-003):
- ER Staff edit only their own enquiries. ER Intake and ER Manager edit all enquiries.
- No role except ER Manager deletes enquiries.

## Fields

| Field | Label | Meaning |
|---|---|---|
| `amount` | Quoted fee | The fee quoted to the client |
| `serviceType` | Service type | Link to **Service Type**, a reference list (60+ values) that admins maintain. A service type has a unique `name`, `isActive` and `sfValue`, the Salesforce picklist value it maps. Human roles can only read service types. `ER Import` can create and edit them, but not delete them (see below). |
| `lossReason` | Loss reason | The reason a Lost enquiry was lost. Required for Lost. |
| `introducedBy` | Introduced by | The user who introduced the enquiry. The importer fills it only from the PO-approved lead-source table (D7). |
| `channel` | Channel | Currently only "Unmapped (legacy)". More values are added once the PO approves the D7 table. |
| `clientReference`, `deceasedName`, `caseNumber` | Case details | Parsed by the importer from the Salesforce enquiry name (D8) |
| `businessType` | Business type | New Business or Existing Business |
| `enquiryCategory` | Enquiry category | Salesforce "Paid genealogy enquiry": Yes, No, Ancillary, Legal rights check, Overseas Assets, Share Sale |
| `postcode`, `keyInformation` | Case details | Free text |

**Service types and the import (accepted deviation).** The WO says only admins maintain service types. The PL has accepted one deviation: the importer creates the 60+ ServiceType records from the Salesforce snapshot. This write access is held only by the `ER Import` API user (`er-import`), and that user cannot delete service types. The user is deactivated after the load. From then on, only admins maintain the list.

**Contacts with roles (deferred by PL decision).**
- An enquiry's contacts use EspoCRM's core `contacts` relation. The detail view shows them in the "Enquiry contacts" panel.
- The importer stores each Salesforce OpportunityContactRole value raw, unchanged, in the relation's `role` column.
- The Salesforce picklist values become known only after L1, when the Salesforce describe picklist is read. Inventing them is forbidden. The picklist options will therefore be added after L1, from the real describe values, in a later change. Until then the UI shows only EspoCRM's core options.
- CRM-004 does not change `Contact`'s metadata, and a test asserts this.

## Legacy fields

These are shown on the detail view in the collapsed **Legacy** panel, and in no other layout except the "legacy stale" search filter.

| Field | Meaning |
|---|---|
| `sfId` | Salesforce Opportunity ID (18 characters). It has a unique index and is `readOnlyAfterCreate`: it can be set when a record is created and never changed afterwards. It is hidden from human roles (read no, edit no), as on firms, contacts and users. The access rule `sf_id_admin_only` checks this. |
| `sfStageName` | The original Salesforce stage |
| `sfLeadSource` | The original Salesforce lead source |
| `sfOwnerId` | The original Salesforce owner ID |
| `sfCreatedAt` | When the record was created in Salesforce |
| `legacyStale` | Set by the importer on old Salesforce enquiries that were never closed (D2). Excluded from "Open enquiries". |
| `lossReasonLegacyMissing` | Set by the importer on Salesforce records closed as lost without a reason (D3) |

Under WO Amendment v1.1, none of these fields is `readOnly` in the entityDefs. That setting is a global restriction that would also block the importer. Instead, role `fieldData` makes them read-only (`edit: no`) for ER Staff, ER Intake and ER Manager. `ER Import` keeps read and edit access.

## Decisions referenced

| Ref | Meaning here |
|---|---|
| D2 | Old open Salesforce enquiries are flagged `legacyStale` and kept out of the default list |
| D3 | A loss reason is required for Lost, with the legacy-missing exemption described above |
| D7 | `introducedBy` and `channel` come only from the PO-approved lead-source table |
| D8 | The client reference, deceased name and case number are parsed from the Salesforce name |
| D9 | Enquiries reuse EspoCRM's Opportunity entity |
| D1, D4 | Listed in the WO (item 10) but not stated in it or in this repository. The PL is to supply their text. |

## Verification

- `python3 -m unittest discover -s tests/unit -v`. `tests/unit/enquiry_policy.py` holds the rules, and `tests/unit/test_enquiries.py` breaks each one with a mutated fixture. The hook is checked statically, and its rule table is mirrored in Python (`loss_reason_allowed`).
- The operator-stage checks (AC3–AC7) run on `crm-dev` with synthetic data.
