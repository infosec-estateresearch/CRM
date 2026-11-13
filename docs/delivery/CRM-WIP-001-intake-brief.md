# CRM-WIP-001 intake brief — WIP data foundation and financial ACL

> **Not a Work Order. No implementation, approval or dispatch authority.** Preparatory brief by Rogue (Orchestrator), 2026-11-13, under the CGPT *Extended Autonomous Delivery Run*, Phase D. It refines `docs/delivery/forge-wo-intake-briefs.md` *CRM-WIP-001* for a later WO draft.

## 1. References

- Parents: **CRM-PBI-019** (CRM–WIP boundary contract and module scaffolding), **CRM-PBI-021** (WIP identity and current FirmGroup visibility). PO-approved at `dc6fb4ced68d9139c2332af973084239492104b3` (Issue #54).
- Requirements: `docs/requirements/crm-modules-requirements.md` WIP-01..03, WIP-07..12, WIP-16, WIP-17, WIP-19, GRP-02, GRP-03; `docs/requirements/wip-field-contract.md`; `docs/architecture/crm-wip-module-boundary.md`.
- Decisions: CRM-D020 (CRM is the master), D021 (WIP is a CRM module), D022 (new WIP code in this repo; legacy repo unchanged), D028 (no revenue interpretation), D029 (deny-by-default finance ACL), D030 (importer separate), D031.
- Sequencing: `docs/delivery/crm-module-sequencing.md` Gate D.

## 2. Invariants the WO must preserve (each needs a negative test)

| # | Invariant | Test shape |
|---|---|---|
| I1 | The CRM **Account is the single firm master**. WIP never creates, renames, merges or edits Account/Contact/Opportunity/FirmGroup/User | Before/after master-field fingerprint across all WIP create/update/failure paths (WIP-16) |
| I2 | `WipCase.account` is **required and immutable** after create; it is the `firmId`; no name-join, no auto-create | Edit attempt of `accountId` refused for every role incl. admin via API (WIP-02) |
| I3 | `groupId` is **derived** at read time from `WipCase.account.firmGroup`; never stored as authority, never accepted on write | Write with a `firmGroupId` ignored/rejected; moving the Account between groups changes the derived value and leaves WIP rows' hashes unchanged (WIP-03, GRP-02) |
| I4 | WIP financial records are **separate entities** from CRM core (WipCase, WipFinancialPeriod), in a separately maintained module | Module path ownership test; core regression with WIP disabled (WIP-01, WIP-09, WIP-13) |
| I5 | **Deny-by-default** financial access: no existing role (ER Staff/Intake/Manager/Import) gains WIP read; only Admin for synthetic UAT | GET/LIST/search/export/nested-panel/stream/global-search denial matrix (WIP-11, GRP-03) |
| I6 | Decimal-safe GBP: nonnegative, ≤2 fraction digits, bounded; null ≠ 0; reject NaN/∞/exponent/oversize | Boundary fixtures through the API (WIP-07) |
| I7 | No workbook import, no financial migration, no invented revenue; labels say WIP / fees invoiced / revised-or-actual yield, never "revenue" | Static label test; no importer code in scope (WIP-17, D028, D030) |
| I8 | Account with WIP history cannot be deleted/merged/mass-deleted, even by admin (WIP-19); existing enquiry delete guard kept | API + admin merge/mass-delete paths |

## 3. Technical preflight findings and risks (to resolve in the WO draft)

1. **Module packaging path.** The boundary document proposes a separate module. EspoCRM reserves `custom/Espo/Modules/<Name>` for modules, but `scripts/deploy_custom.sh` deploys **only** `custom/Espo/Custom` (CRM-CLIENT-001 F5). Either (a) WIP-001 lives under `custom/Espo/Custom` with a strict `Wip*` naming and path ownership test, or (b) a delivery extension for `custom/Espo/Modules/Wip` is needed first (a CRM-CLIENT-001-style delivery WO). **Decision needed (CGPT): WIP-D1.**
2. **Decimal storage.** WIP-07 requires exact decimals. EspoCRM's `currency`/`float` field storage and API serialisation in 10.0.12 must be verified (float storage would violate I6). If no exact-decimal native type is verified, the WO must specify a validated decimal representation and stop rather than accept floats.
3. **ACL completeness.** New scopes must be explicit in every role (`tests/unit/access_policy.py`); global search, stream, export, mass update, and relationship panels on Account are separate leak paths to test.
4. **Dependency.** CRM-WIP-001 requires **CRM-FG-001** accepted (derived group, GRP-02). It has no GUI, so it does not itself need CRM-CLIENT-001, but WIP-002 (Account tab) does.
5. **Audit.** WIP-12 needs creator/updater/time plus changed-value history; verify `audited` on new entities and Stream behaviour under deny-by-default (audit must not leak values to non-finance users).
6. **Rollback.** Entity removal on rollback leaves tables; document and test that core CRM works with WIP metadata absent.

## 4. Missing PO business decisions (block parts of WIP-001/002, not the synthetic scaffold)

| ID | Decision | Default for synthetic work |
|---|---|---|
| PO-W1 | Which staff may read / add / edit WIP financials; whether read and write differ; finance-manager role | Deny all; Admin only for synthetic UAT |
| PO-W2 | Case status vocabulary; case type, fee type, contingency status lists | Conservative documented placeholder list, marked provisional |
| PO-W3 | `caseReference` uniqueness scope (per firm vs global) and normalisation | Per-firm uniqueness, trimmed, case-sensitive; provisional |
| PO-W4 | Whether `instructionDate` is mandatory for new manual cases | Required for new manual entries (field contract proposal) |
| PO-W5 | Permitted amount range/upper bound for GBP fields | Bounded by the verified DB precision; provisional |
| PO-W6 | Whether staff may delete WIP cases/observations, or only void/revise | No delete for any non-admin role |
| PO-W7 | Revenue definition (PBI-026) — not needed for WIP-001; recorded to prevent scope creep | No revenue metric |

## 5. Entry conditions for drafting the WO

CRM-FG-001 accepted and merged (base SHA pinned then); WIP-D1 decided; Decimal storage verified on 10.0.12; PO-W1 at least confirmed as *deny-by-default + admin UAT*; sandbox entry gate assessed for the WO; synthetic fixtures only; no beta, Salesforce, legacy WIP or workbook contact.
