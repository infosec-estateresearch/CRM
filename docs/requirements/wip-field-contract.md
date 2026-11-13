# WIP/Revenue MVP — field/data dictionary and validation contract

> **Provenance:** CGPT Architect delivery package of 2026-11-13 (`ER_CRM_FOUNDRY_DELIVERY_2026-11-13.zip`, sha256 `a75b5f0d1768a2a1bd945d35710e6e2067c4a7fb5e0228773946446ad9104488`), reconciled into the CRM repository by Rogue under the documentation-only assignment of 2026-11-13. CANDIDATE: not approved. Changes made during reconciliation are listed in [`docs/initiation/2026-11-13-existing-product-reassessment.md`](../initiation/2026-11-13-existing-product-reassessment.md#7-reconciliation-log).

**Candidate implementation specification.** Not a source-certified exhaustive field inventory. Legacy workbook source columns/status picklists are subject to HELM evidence; implementation must not invent financial semantics. Map standard EspoCRM field names to actual version during PL technical preflight; distinguish UI labels from storage names.

## WipCase — first MVP

| Logical field | Type | Entry / rule | Notes |
|---|---|---|---|
| `id` | immutable internal ID | System generated | Not Salesforce ID |
| `accountId` / `firmId` | link(Account), required | **Server derives current route Account ID; foreign key validated; cannot be edited in the Account form** | CRM is authoritative; prevents wrong-firm entry |
| `firmGroupId` / `groupId` | **derived** link(FirmGroup), nullable, read-only | From current `Account.firmGroupId` at query time | Never accepted as independent editable WIP field |
| `caseReference` | trimmed string, required | Unicode-safe length and disallowed-control validation; duplicate check using per-firm case identity, with approved normalisation policy | Confirm legacy/global uniqueness before a real import; don't silently merge |
| `instructionDate` | date, optional for legacy, proposed required for **new manual** entries | Valid calendar date, plausible configured year bounds; invalid/impossible dates rejected | Historic missing/invalid dates remain exceptions |
| `status` | controlled enum, required | Proposed initial Open, Instructed, Pending, No income; confirm precise source vocabulary before freeze | Never allow arbitrary spelling as stored state |
| `caseType` | controlled lookup, optional | Options from approved WIP source dictionary, not free text | May defer until choices verified |
| `feeType` | controlled lookup, optional | Options from approved WIP source dictionary | May defer until choices verified |
| `contingencyStatus` | controlled lookup, optional | Options from approved WIP source dictionary | May defer until choices verified |
| `opportunityId` | nullable link(Opportunity) | **No auto-link**; only separately evidenced/verified manual choice | Source cases cannot reliably auto-match enquiries |
| `sourceKind` | enum | manual, workbook, migration | New manually entered record = manual |
| `createdAt`, `createdBy`, `modifiedAt`, `modifiedBy` | audit | Server maintained | Preserve before/after changes; no direct staff delete by default |

## WipFinancialPeriod — observation, NOT a month-end WIP ledger

| Logical field | Type | Entry / rule | Notes |
|---|---|---|---|
| `id` | immutable internal ID | System generated | Supports provenance and revisions |
| `wipCaseId` | required link(WipCase) | Must resolve to a WIP case the actor may edit | Enforce at API and UI |
| `sourcePeriod` | year-month or date | Optional for manual, required for imported cohort data | Source workbook uses instruction-month cohorts |
| `observedAt` / `effectiveAt` | date or datetime | Required when multiple observations exist | Revisions need stable ordering, never guess old month-end balances |
| `wipValue` | GBP Decimal(precision/scale per tested DB constraints), nullable | ≥0, max 2 fraction digits, range bounded; null ≠0 | Direct value; no automatic spreadsheet formula on manual entry |
| `feesInvoiced` | GBP Decimal, nullable | same constraints | Not recognised revenue |
| `revisedOrActualYield` | GBP Decimal, nullable | same constraints | Explicitly combined, not proven actual income |
| `estimatedYield` | GBP Decimal, nullable | same constraints | Original source interpretation may vary by era |
| `currency` | enum | GBP only for MVP | Reject silently converted currencies |
| `origin` | enum | manual, workbook, migration | Source provenance, no silent override |
| `sourceHash`, `sourceSheet`, `sourceRow`, `batchId` | nullable and restricted | For later imports; never user-input on manual form | Only restricted data environments, no private workbook content in Git |
| author/timestamps/audit | server maintained | Trace each create/update | Source row history immutable for future imports |

## Form/API contract

- **New entry:** from `#Account/view/<id>` → WIP/Revenue tab → Add; choose case fields and (optionally) first financial observation in a single guided form; save atomically or roll back both on error.
- **Existing case:** open linked case, add/edit observation through a separate audited action. Prevent accidental duplicate observations on retries with request identity or explicit stable constraints, without assuming (case,month) must be unique for legacy revisions.
- **Numbers:** input format decimal in GBP with optional human-facing separators only when reliably parsed; canonical API uses exact decimal strings; rejects scientific notation, NaN, infinity, extra fractional digits, negatives, malformed separators and range overflow. Use Decimal end to end, not float.
- **Validation:** browser hints **plus server enforcement**. Required references, types, date plausibility, nonnegative currency, legal statuses, authorised roles, input lengths, duplication and cross-record relationship protection are server-side gates.
- **Errors:** clear field-level messages for user mistakes; no internal SQL/path/stack or real data leaks. Writes must be authorised at both entity and foreign-reference level.
- **Permissions:** finance scope deny-by-default; allow admin in operator tests; PO to confirm ordinary users, finance manager role and whether read and write grants differ. No inherited blanket ER Staff visibility.
- **History:** user-supplied changes cannot rewrite the original imported financial row or its source hash; use tracked revisions with clear current/earlier meaning.

## Explicitly deferred / pending PO decisions

Definition of recognised revenue, authoritative workbook/CSV interchange format, whether input `instructionDate` may be missing for new manual cases, legacy caseReference uniqueness scope, approved case/status/fee-type vocabularies, exact finance reader/editor roles, historical group-as-of reporting. These do not block synthetic model and Account UI scaffolding; test fixtures can use conservative documented values until approved.
