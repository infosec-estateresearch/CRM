# CRM core ↔ FirmGroup ↔ WIP/Revenue module — architecture decision candidate

> **Provenance:** CGPT Architect delivery package of 2026-11-13 (`ER_CRM_FOUNDRY_DELIVERY_2026-11-13.zip`, sha256 `a75b5f0d1768a2a1bd945d35710e6e2067c4a7fb5e0228773946446ad9104488`), reconciled into the CRM repository by Rogue under the documentation-only assignment of 2026-11-13. CANDIDATE: not approved. Changes made during reconciliation are listed in [`docs/initiation/2026-11-13-existing-product-reassessment.md`](../initiation/2026-11-13-existing-product-reassessment.md#7-reconciliation-log).

**Status: proposed for CRM decision register; no code change authority.** One CRM product/repository and release, module-owned financial code, minimal supported EspoCRM integration. Preserve original WIP repo `infosec-estateresearch/WIP` unchanged as historical POC. CRM core and ForgeV2/FOUNDRY are immutable outside exact approved application WOs.

## Ownership and data flows

```
CRM authority (existing EspoCRM/MariaDB)
  Account(id, sfId, firmGroupId?, parentId?) ────┐
  Contact / Opportunity(Enquiry) / User           │ read identity and verified links
  FirmGroup(id, name)  <── Account.firmGroupId     │
                                                  ▼
       WIP/Revenue (CRM-owned extension/module, same release)
       WipCase(id, accountId REQUIRED, caseReference, status, instructionDate, ...)
          └── WipFinancialPeriod(id, wipCaseId, observationDate/period,
                                 wipValue, feesInvoiced,
                                 revisedOrActualYield, estimatedYield, currency,
                                 provenance, createdBy, updatedBy)
       (later) WipImportBatch, WipImportReject, reporting services
```

- `firmId` is the **CRM Account internal ID** exposed by WIP; implementation field may use native EspoCRM `account`/`accountId`. Legacy Salesforce `sfId` is only an external migration crosswalk.
- `groupId` is the **CRM FirmGroup internal ID**. Expose on WIP records/queries as a **read-only derived current `firmGroupId`** via `WipCase.account.firmGroup`, nullable for ungrouped firms. Do not accept a client-provided group ID on WIP writes; do not maintain a second independent membership mapping or silently cache a mutable group ID as authority.
- Group retrieval is `FirmGroup → member Accounts → WipCase → selected financial observations`, with permission checks at each financial boundary, pagination and no duplicate case counting. Group reassignments change *current-membership views* without changing financial source rows.
- Do not present historical group-as-of membership until CRM has an auditable temporal membership history and approved reporting policy; show current-group label where relevant.
- WIP APIs never mutate Account, Contact, Opportunity, FirmGroup, User or Salesforce source fields. Group membership APIs belong exclusively to CRM's FirmGroup component.

## Deployment and boundaries

New WIP source belongs inside `infosec-estateresearch/CRM`, tentatively `modules/wip/` for reusable module logic, `custom/Espo/Custom/...` and `client/custom/...` for minimal EspoCRM integration, plus module-specific unit/integration/browser tests. Paths and packaging must be adjusted to **actual verified** EspoCRM conventions and the existing release bundle; these are design intentions, not approved WO path allowlists.

Each module has its own data models, migrations, service functions, tests, extension hooks, compatibility contract and rollback notes. It is a *logical* module in one PHP process/MariaDB deployment; faults cannot be guaranteed process-isolated. Require fail-closed WIP panel behaviour and core CRM smoke tests/fault injection after every candidate release.

### FirmGroup: independent CRM identity

`FirmGroup(id, name, description, ...)` has many member Accounts; each Account belongs to at most one group. Group names need not be unique, no Salesforce `sfId` for CRM-native groups. Server controls: ER Manager/Admin may create/rename/move/unlink; ER Staff/Intake view only. Group Members tab on Account lists *other members*, linked to their Account records; independently manage groups without changing `Account.parent/branches`. Never infer legal ownership from membership.

**Superseded:** blanket one-off auto-seed of 1,366 Salesforce parent trees. HELM found 36 approved legacy groups: 31 subsets of a parent tree, 4 cross-tree, 1 no-parent. FirmGroup UI is delivered **empty/curated first**, and any later data seeding requires per-member evidence, PO-approved rule, idempotent operator plan and review queue.

## Data integrity / revision semantics

- Workbook monthly sheets are predominantly **instruction-month cohorts**, not balance snapshots or monthly income flows. Repeated cases are observations/revisions; selecting an effective current record must be explicit and tested.
- Source `actual_yield` is a **blended revised-estimated/actual field**; call it `revisedOrActualYield` or visibly label the original meaning. Do not treat it as realised revenue or a ledger transaction.
- Historic source row WIP often follows `IF(fees_invoiced>1, 0, revisedOrActualYield)` but has exceptions and hard-coded/blank values. Preserve source entered amounts; never silently recompute on import or user edit without a separately approved business rule.
- Manual forms may capture values directly (validated Decimal GBP); do not force the historic workbook formula on manual entries without the business approving its interpretation.
- Observations should preserve source date/sheet/row and import batch where applicable; manual entry records provenance type, author and edit audit. Distinguish empty/not known from zero.
- `WipFinancialPeriod` is a provisional technical name: field semantics are observations associated with an instruction/source period, **not guaranteed monthly snapshots**. Do not impose unique(case,year,month) if repeated observations legitimately exist without a revision identity.
- No reliable Case↔Opportunity match exists; optional link empty unless confirmed by business evidence. Case Manager's ownership of operational and legal cases is a *proposed* boundary (CRM-D006 and D031), not a verified integration: HELM could not inspect Case Manager, and the WIP module must not replace its functions without separate product authority. That external operational/legal case master remains outside scope.

## Failure containment and authorisation

- Finance-only scopes are explicitly deny-by-default, tested for GUI, direct REST API, list/search, exports and nested related panels. Do not inherit broad CRM contact read permissions for financial records.
- No WIP UI code may intercept normal Account render, search or enquiry workflows such that a WIP failure brings down the page. If extension compatibility cannot prove this, return to Architect for redesign.
- Reuse existing EspoCRM APIs and custom metadata, preserve upgradeability and release provenance; no core fork/direct SQL core writes, runtime CDN code or unapproved cross-repo source dependency.
- No WIP data entered in beta is automatically promoted to production, and no live workbook source retired, without separate explicit operator/cutover approval.
