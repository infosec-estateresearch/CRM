# CRM-WIP-001 intake brief — WIP data foundation and financial ACL

> **Not a Work Order. No implementation, approval or dispatch authority.** Preparatory brief by Rogue (Orchestrator), 2026-11-13, updated 2026-11-16 (WIP-D1 verification), under the CGPT *Extended Autonomous Delivery Run*, Phase D. It refines `docs/delivery/forge-wo-intake-briefs.md` *CRM-WIP-001* for a later WO draft.

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

## 3. Technical preflight findings (updated 2026-11-16; source-verified unless marked UNVERIFIED)

Sources are EspoCRM 10.0.12 in the pinned image, read via `docker export` with no container started, and `main` @ `6e176698`.

1. **Module location: resolved by Architect direction WIP-D1 (2026-11-16) and verified.** See §6.
2. **Exact decimals are supported.**
   - The `currency` field type has a `decimal` parameter (`metadata/fields/currency.json`, sha256 `244b2fcf0c1ff718cc622a4b5fb0509a6a1e7a63c4f84a90ff88d29ad4d227f9`).
   - With `decimal: true`, the amount is stored as SQL `DECIMAL`, with a default precision of 13 and a default scale of **4**, and handled as a **string** attribute (`VARCHAR` in PHP and the API) rather than a float (`Core/Utils/Database/Orm/FieldConverters/Currency.php`, sha256 `537d2403003b7595f9a38b15554f65243050fb61b05772469f5a73841438ea58`).
   - **Consequences for the WO:**
     - set `decimal: true` with an explicit scale of 2 and a reviewed precision;
     - validate on the server that no amount has more than two fraction digits, and reject anything beyond that, because the database would otherwise round silently;
     - keep amounts as decimal strings end to end;
     - test that a null amount stays distinct from `"0.00"`.
   - **UNVERIFIED:** the exact API serialisation of a decimal currency field with scale 2 in list, detail and export output. The WO tests it and stops if it ever yields a float.
3. **Deny-by-default must be explicit.**
   - The CRM runs EspoCRM in **non-strict ACL mode**: a scope that a role leaves unset is **allowed** (`docs/ACCESS.md`).
   - Every new `Wip*` scope must therefore be listed as `no` in every role (ER Staff, Intake, Manager and Import) and added to `tests/unit/access_policy.py`, so that an omission fails the policy test.
   - Global search, stream, export, mass update and the relationship panels on Account are separate leak paths, and each needs a test.
4. **Dependency.** CRM-WIP-001 needs **CRM-FG-001** accepted, for the derived group (GRP-02). WIP-001 has no GUI, so it does not need CRM-CLIENT-001 itself; WIP-002 does, and its client code would go under `client/custom/src/wip/` (CL-D1).
5. **Audit.**
   - WIP-12 relies on audited fields and the stream. Audited fields write notes on every save that is not `SILENT` (see CRM-FG-001 §2 P5).
   - **UNVERIFIED:** whether stream notes for `Wip*` records could expose amounts to users who can read the parent Account. The WO must disable the stream or the Account-parent stream propagation for the `Wip*` entities, or prove that no such leak exists.
6. **Rollback.** Removing an entity leaves its tables in place. The WO must document this, and test that core CRM works with the WIP metadata absent.

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

CRM-FG-001 accepted and merged (base SHA pinned then); WIP-D1 contract adopted (§6); decimal serialisation (§3.2 UNVERIFIED item) checked; PO-W1 at least confirmed as *deny-by-default + admin UAT*; sandbox entry gate assessed for the WO; synthetic fixtures only; no beta, Salesforce, legacy WIP or workbook contact.

## 6. WIP-D1: module location (Architect direction, 2026-11-16) and its verification

- **Direction.** A logically separate, `Wip*`-namespaced implementation, delivered through the existing `custom/Espo/Custom` mechanism, with no new deployment machinery.
- **Verified compatibility.**
  - The image's Composer PSR-4 map binds `Espo\Custom\` to `custom/Espo/Custom`, ahead of `Espo\` (`vendor/composer/autoload_psr4.php`, sha256 `f52c83d4a2643657e09a43122213b27ebadbe8825493fdb4a1192ddb9ca307d7`, line 98).
  - `Espo\Modules\` maps to `custom/Espo/Modules`, line 97, but `deploy_custom.sh` does not deliver that path (CRM-CLIENT-001 F5). The direction therefore avoids a delivery gap.
  - Custom entity metadata under `custom/Espo/Custom/Resources/metadata/*/<Entity>.json` is already used and delivered by the CRM (for example `ServiceType`, CRM-004).
- **Proposed binding contract**, which becomes binding when the WIP-001 WO is approved:
  - entity names `WipCase` and `WipFinancialPeriod`, with every later WIP entity prefixed `Wip`;
  - PHP code only under `custom/Espo/Custom/{Classes,Tools,Hooks,Controllers}/Wip/**`, or as entity-named files `…/WipCase*` where EspoCRM requires its own naming (for example `Entities/WipCase.php`, `Hooks/WipCase/`);
  - metadata, layouts and i18n only in files named `Wip*.json`, except the Account link and panel definitions, which are listed one by one in the WO's allowlist;
  - client code later only under `client/custom/src/wip/**`;
  - tests under `tests/unit/test_wip_*.py`, `tests/acceptance/test_wip_*.py` and `tests/browser/wip/`.
- **Ownership test.** A unit test fails if a `Wip*` path changes core CRM files, or if a non-WIP path references WIP classes, apart from the listed Account integration points.
- **Limitation.** This is a *logical* separation in one PHP process and one database (CRM-D021). It is not process isolation. WIP-13 containment still has to be proven by fault injection.
- **Alternative**, only if a blocker appears later: a `custom/Espo/Modules/Wip` module, which first needs a bounded delivery extension of `deploy_custom.sh` in the style of CRM-CLIENT-001. This is not proposed now.

PO decisions PO-W1 to PO-W7 stay recorded and do not block the next work. Synthetic engineering keeps deny-by-default access and admin-only UAT, with no staff grants and no recognised revenue.
