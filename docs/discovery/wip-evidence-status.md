# HELM evidence reconciliation — legacy WIP to CRM (13 November 2026)

> **Provenance:** CGPT Architect delivery package of 2026-11-13 (`ER_CRM_FOUNDRY_DELIVERY_2026-11-13.zip`, sha256 `a75b5f0d1768a2a1bd945d35710e6e2067c4a7fb5e0228773946446ad9104488`), reconciled into the CRM repository by Rogue under the documentation-only assignment of 2026-11-13. CANDIDATE: not approved. Changes made during reconciliation are listed in [`docs/initiation/2026-11-13-existing-product-reassessment.md`](../initiation/2026-11-13-existing-product-reassessment.md#7-reconciliation-log).

**Evidence type: HELM host-audit report, submitted to CGPT.** HELM reports read-only inspection of the source workbook, WIP application and DB, and CRM; it disclosed an earlier side effect on the host's Git configuration (see *Audit side effect*). Architect verified CRM GitHub baseline but cannot directly inspect legacy WIP repository via its GitHub connector (NOT_FOUND despite HELM's unauthenticated API success). Treat WIP source findings as **HELM-reported verified**, not personally source-code audited by CGPT.

## Baselines

- CRM `infosec-estateresearch/CRM@330978598ac6147d4a1bce3f713113d59045d465` (GitHub main confirmed 2026-11-13). CRM BETA_POPULATED on Issue #9 is Rogue/operator-reported.
- WIP `infosec-estateresearch/WIP@91b2af19877b498ed307ee9f1218b3243b2b60ba` (HELM-reported local and remote identical; 33 commits). The legacy WIP application (Python/FastAPI/uvicorn with its own MariaDB database, on the development host) is unchanged; web inactive, hourly importer failures since 2026-11-06 due to missing Python modules. No running WIP write flow assumed.
- The master WIP workbook (restricted; an XLSX file with 163 sheets), SHA-256 prefix `4945089d…97944`. User describes a temporary spreadsheet/CSV feed; exact current transport file to verify, not assume audited XLSX means all future data is XLSX.

## Firm identity reconciliation

| WIP companies | CRM Account ID present by exact Salesforce sfId | Absent from CRM |
|---|---:|---:|
| With ERic-derived canonical ID | 7,856 | 188 |
| Without canonical ID | 874 | 23 |
| **Total** | **8,730** | **211** |

8,044 with canonical IDs and 8,730 matching CRM are different statistics. 7,919 distinct canonical IDs cover 8,044 companies (123 keys shared among 248 records), hence **name canonical IDs are not unique identities**. 1,719 of 1,730 case-bearing WIP companies match CRM, covering **11,758 of 11,776 cases**. The remaining 11 firms/18 cases need review. No guessed firm creation or name match. CRM contains 2 Accounts without WIP row. No reliable Case→Enquiry join exists (Opportunity `caseNumber` and `clientReference` blank; 286 weak text candidates, often cross-account).

## Financial semantics

- Ten valid monthly case sheets skipped by filename parser (June/July 2015, Nov17, MAr/Sept 2018, Jan–Apr and Jun 2021), ~960 source rows and ~940 case references otherwise absent from WIP. Sheet1–Sheet10 and a later Summary sheet are empty.
- Historic WIP formula generally `IF(fees_invoiced>1,0,revised_or_actual_yield)` but source has blank/hard-coded WIP and mismatches. WIP should not silently alter source.
- `actual_yield` stored in WIP mixes revised estimated and actual yield due to header alias collision; label truthfully.
- `WIP & Rev` contains a WIP cohort matrix, **no revenue calculation**, and workbook does not define revenue. Other summary `Total` rows sum blended yield, not verified revenue. One February 2025 summary WIP formula points to March.
- Sheet month indicates mostly **instruction-month cohort**, not period movement/balance. Cases sometimes recur with value revisions, so do not sum revisions as monthly revenue. WIP DB 11,776 cases and 12,003 financial rows. 1,456 missing case instruction dates; 19 invalid/impossible; 27,302 reject records including substantial unresolved queue.

## Group reconciliation

CRM has 1,366 Salesforce parent trees (5,098 Accounts). WIP has 36 approved groups / 137 approved members (2 absent CRM), plus proposed/review records. Of approved groups 31 are strict **subsets** of a CRM tree, 4 span multiple trees, 1 has no parent link. Approved WIP PRIMARY/BRANCH roles are not Account parent-child. Do not seed all 1,366 trees or infer missing siblings. FirmGroup UI before any curated operator mapping; seeding separate later gate.

## Source reuse and defects

Reusable concepts: alias/header parser, source hashes, Decimal, rejects, audit, provenance; date parser requires correction, same-header duplicate risk, source money semantics tests. Do **not** reuse legacy wip_company master, name resolver, FastAPI GUI, Salesforce sync, group tables or 6 GB reject-bloat backup. WIP dependencies include PyMySQL/PyYAML/openpyxl, FastAPI/uvicorn, Bootstrap/htmx CDNs; copying code/licensed dependencies into CRM is subject to approved provenance and build register. Public repository without LICENSE does not imply a general redistribution licence; Estate Research ownership/right-to-reuse should be confirmed.

## Audit side effect

HELM reports adding two Git `safe.directory` entries to the host's root Git configuration. They alter Git trust behavior. The next host-maintenance authority should verify attribution and remove **only** any audit-added unneeded entries. This is not a reason to change WIP, CRM or Forge code.

**Impact on MVP:** FirmGroup and manual-entry WIP Account tab can be engineered with synthetic data without waiting for workbook-revenue semantics. Later source import, historical group membership and revenue metrics remain held behind separate evidence/PO gates.
