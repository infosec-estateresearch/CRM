WO: CRM-WIP-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main — CONDITIONAL: the commit that delivers an accepted CRM-FG-001 (does not exist yet; no SHA is asserted)

# CRM-WIP-001: WIP data foundation (WipCase, WipFinancialPeriod) and financial access control

- **Version:** v0.1 **CONDITIONAL DRAFT**, 2026-11-16. **Not approval-ready.** That requires a version that pins the base (gate W0) and finalises the allowlist.
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/63
- **Prepared by:** Rogue (Orchestrator), under the CGPT *CRM/WIP Delivery Mission* (2026-11-16), Phase 3. **No implementation, no dispatch.**
- **Inputs:**
  - `docs/delivery/CRM-WIP-001-intake-brief.md` (invariants I1–I8, verified preflight §3, WIP-D1 §6);
  - `docs/requirements/wip-field-contract.md`;
  - `docs/requirements/crm-modules-requirements.md` WIP-01..03, 07..13, 16, 17, 19;
  - `docs/architecture/crm-wip-module-boundary.md`.
- **Header note.** There is no `BROWSER:` line. This WO adds **no** navigation, layout or client code (I4; WIP-002 adds the UI), and acceptance is API and static. If the Tester nevertheless judges browser behaviour material, the result is ESCALATED and the CL-D7 BA pattern applies.

## 1. Authority

| Item | Value |
|---|---|
| FOUNDRY | adopted main `84fedf0a74017237aa1bd650d8560350c91c7f0e`; WO contract sha256 `cbb6eb3ae62bf7877ae470abf2297a5af5ffb23ca617581a9a85077dd9a8ebcc` |
| Product authority | Matt's PO approval at `dc6fb4ced68d9139c2332af973084239492104b3` (Issue #54): PBI-019 and PBI-021; CRM-D020, D021, D022, D028, D029, D030 |
| Architect decisions | WIP-D1 (`Wip*` naming under `custom/Espo/Custom`, verified); CL-D7 and CL-D8 (CGPT, 2026-11-16) |
| Dependencies | CRM-FG-001 accepted and merged (the derived group, and the Account relation-guard repository of FG P15, which this WO extends) |
| PO decisions open | PO-W1..W7. This WO uses the conservative synthetic defaults of intake brief §4 and needs **none** of them decided |

## 2. Intended outcome

Two CRM-owned entities, with no UI beyond EspoCRM's generic admin record views:

1. **`WipCase`.** A case belongs to exactly one Account.
   - **`account`:** belongsTo, required, **immutable after create** for every user including admin.
   - **`caseReference`:** required. It is trimmed, has no control characters, is limited to 100 characters, and is **unique per Account** (case-sensitive after trim; PO-W3 default).
   - **`instructionDate`:** a date, required for new manual cases (PO-W4 default), between 1990-01-01 and today + 1 year.
   - **`status`:** an enum (Open, Instructed, Pending, No income), marked provisional per PO-W2.
   - **`caseType`, `feeType`, `contingencyStatus`:** optional enums with a provisional placeholder list, or omitted if PO-W2 is not ready.
   - **`sourceKind`:** server-set to `manual`; any other value is refused through the API.
   - **No `opportunity` auto-link.** An optional `opportunity` link is deferred.
   - **Derived and read-only:** `firmGroupId` and `firmGroupName`, from `account.firmGroup` at **read time** (technical gate WT-1). Any submitted value is refused (I3).
2. **`WipFinancialPeriod`.** An observation, not a ledger.
   - **`wipCase`:** belongsTo, required, immutable.
   - **`sourcePeriod`:** year-month, optional for manual entry.
   - **`observedAt`:** a date, required.
   - **Amounts:** `wipValue`, `feesInvoiced`, `revisedOrActualYield` and `estimatedYield`, each `currency` with `decimal: true`, **precision 13, scale 2**, and GBP only.
   - **`origin`:** server-set to `manual`.
   - **Restricted fields:** `sourceHash`, `sourceSheet`, `sourceRow` and `batchId` are present but **refused on API write** (they are reserved for a future import WO).
   - **`requestId`:** an optional client idempotency key, unique per `wipCase` (WIP-08).
3. **Server-side validation** (a hook or validator, not just a UI hint).
   - **Each amount:**
     - is null or an exact decimal string matching `^(0|[1-9][0-9]{0,10})(\.[0-9]{1,2})?$`;
     - is non-negative, has at most 2 fraction digits, and fits DECIMAL(13,2);
     - is never an exponent, NaN, ∞ or a float;
     - null stays distinct from `"0.00"`.
   - This closes the core `inPermittedRange` gap (intake brief §3.2).
   - The currency is GBP only; anything else is refused.
   - The API output is checked to be a string (no float). The `*Converted` attributes are never exposed in layouts, export or tests.
4. **Integrity (I1, I2, I8, WIP-19):**
   - **Immutable links:** `WipCase.accountId` and `WipFinancialPeriod.wipCaseId` are refused on update, for admin too.
   - **No orphan at create:** the Account must exist and not be deleted, and the case must exist.
   - **Relation guard:** `Account.wipCases` and `WipCase.financialPeriods` relate, unrelate and mass-relate are refused **preventively**. This extends the FG P15 repository-mediator guard, and closes merge reassignment, Formula and link endpoints.
   - **Delete:** deleting a `WipCase`, or a `WipFinancialPeriod`, is refused for **every** role including admin (PO-W6 default; corrections are new observations). Deleting an **Account with any WipCase**, including mass delete and merge sources, is refused by the new `Hooks/Account/RestrictDeleteWithWip.php`. `RestrictDeleteWithEnquiries` is untouched.
   - **I1:** WIP never writes Account, Contact, Opportunity, FirmGroup or User.
5. **Access (I5).**
   - **Scopes:** `WipCase` and `WipFinancialPeriod` have `entity: true`, `object: true`, `acl: true`, `stream: false`, no `accountLink`, and are not in `tabList` or global search.
   - **Roles:** **every** role (ER Staff, Intake, Manager and Import) gets an explicit `no` for create, read, edit, delete and export, plus field-level `no`. `tests/unit/access_policy.py` gains both scopes, so an omission fails.
   - **Admin:** has access, but only for synthetic UAT.
   - **Relationship panels:** the `Account.wipCases` panel is not added (WIP-002 adds the tab).
6. **Audit (WIP-12).**
   - Every field is `audited`, so non-silent saves write attributable Update notes. These notes attach to the WIP record (parent), not the Account (intake brief §3.5), and stay ACL-filtered.
   - `createdBy`, `modifiedBy` and the timestamps are kept.
   - Saves are never silent.
7. **Containment (WIP-13).** With the WIP metadata absent, or a WIP hook throwing, the core Account, Enquiry and Contact flows still work.

## 3. In scope (draft allowlist; finalised at W0)

- `custom/Espo/Custom/Resources/metadata/{scopes,entityDefs,recordDefs,clientDefs}/Wip*.json`
- `custom/Espo/Custom/Resources/metadata/entityDefs/Account.json`: the `wipCases` hasMany link only
- `custom/Espo/Custom/Resources/i18n/en_US/Wip*.json`: labels per WIP-17 ("WIP value", "Fees invoiced", "Revised or actual yield (source)", "Estimated yield"; never "revenue")
- `custom/Espo/Custom/Entities/WipCase.php` and `Entities/WipFinancialPeriod.php`, if needed
- `custom/Espo/Custom/Hooks/WipCase/**`, `Hooks/WipFinancialPeriod/**` and `Hooks/Account/RestrictDeleteWithWip.php`
- `custom/Espo/Custom/Classes/Wip/**`: validators and the guard-list extension
- `custom/Espo/Custom/Repositories/Account.php`: adding `wipCases` to the FG-P15 guarded relations **only**
- `custom/Espo/Custom/Repositories/WipCase.php`
- `config/access/roles.json`: the two scopes, explicit `no`
- `tests/unit/access_policy.py`, `test_access_policy.py`, `test_metadata.py`, new `tests/unit/test_wip_*.py`, new `tests/acceptance/test_wip_*.py`
- `scripts/seed_synthetic.py` and its tests: synthetic WIP fixtures only
- `docs/ACCESS.md`, `docs/BUILD.md`, `docs/REQUIREMENTS-TRACEABILITY.md`

## 4. Exclusions

- Any client code, layout, navigation or tab (WIP-002).
- Any import, workbook, CSV or migration code (D030, I7); no revenue metric or aggregation (D028, PO-W7).
- Salesforce, the legacy WIP repository (`infosec-estateresearch/WIP`) and its data.
- Account `parent`, `branches` and `sf*`; FirmGroup membership logic beyond the guard-list extension.
- Beta, FOUNDRY, ForgeV2.

## 5. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| W-AC1 | The metadata matches §2: required fields, immutable links, GBP DECIMAL(13,2), derived group read-only, scopes per §2.5 | `test_metadata.py`, `test_wip_metadata.py` |
| W-AC2 | **Denial matrix.** For each of ER Staff, Intake, Manager and Import, for both scopes: GET, LIST, search, `where` filters, export, mass update, mass delete, create, PATCH, link endpoints, the Account nested `wipCases` list, the Account stream, the global stream and notes search all return 403 or zero WIP rows and zero WIP-derived note content. An ER Staff user with Account read and WIP deny is used throughout | `test_wip_access.py` on synthetic crm-dev |
| W-AC3 | **Immutability and tamper.** Changing `accountId`, `wipCaseId`, `firmGroupId`, `sourceKind`, `origin` or `source*` through PATCH, mass update or Formula sandbox is refused for admin, with row fingerprints unchanged. A create naming a deleted or nonexistent Account or case is refused | API |
| W-AC4 | **Relation guard.** Link and unlink from either side, `massLink`, Account merge with a WIP-bearing source (refused and rolled back), and Formula `record\relate` all leave rows unchanged | API |
| W-AC5 | **Decimal boundary set.** These are accepted and returned as exact strings: `"0"`, `"0.00"`, `"0.01"`, `"99999999999.99"`, null. These are refused with field-level 400: `"-0.01"`, `"0.001"`, `"1e3"`, `"NaN"`, `"Infinity"`, `"100000000000.00"`, `"1,000.00"`, `" 1.00"`, a numeric float in JSON, and a non-GBP currency. Null and `"0.00"` round-trip distinctly. `*Converted` is not consumed | API |
| W-AC6 | **Duplicates and idempotency.** A duplicate `caseReference` within an Account is refused (409/400). The same reference under another Account is allowed. A repeat create with the same `requestId` returns or refuses without a second row | API |
| W-AC7 | **Audit.** Each create and update writes attributable notes with was and became values, and refused attempts write none. No WIP note appears in the Account stream for any role | API |
| W-AC8 | **Delete integrity.** Deletes of cases and observations are refused for all roles, including admin. An Account with a case cannot be deleted, mass-deleted or merged away. The enquiry delete guard still holds | API |
| W-AC9 | **Master fingerprint (WIP-16).** The Account, Contact, Opportunity, FirmGroup and User fingerprints are unchanged across every W-AC test, including failures | acceptance |
| W-AC10 | **Containment (WIP-13).** With WIP metadata removed and a rebuild, core works. With a WIP hook forced to throw, core Account, Enquiry and Contact operations succeed | host procedure |
| W-AC11 | **Regression and release.** The unit suite runs as non-root with at least the starting count; `tests/load`; CRM-TEST-001 mutations; the FG-001 acceptance suite; bundle verify. Rollback documentation (tables are left in place; intake brief §3.6) | host procedure |
| W-AC12 | **Labels (WIP-17).** A static test finds no "revenue" in WIP labels, and `revisedOrActualYield` is never labelled as actual income | unit |

## 6. Roles

The standard Engineer, Auditor, Tester and DevSecOps criteria apply, as in CRM-FG-001 §8.
- DevSecOps additionally checks that the denial matrix is complete (non-strict ACL means an unset scope is *allowed*), that there is no float path, and that the relation guard has no bypass.

## 7. Gates

| Gate | Requirement | State |
|---|---|---|
| **W0** | CRM-FG-001 accepted and merged. The base is pinned per CL-D8 (or FV2-SYNC-001), and the allowlist is finalised | **open, blocks approval** |
| W1 | CGPT exact-version approval on #63 | open |
| W2 | Sandbox entry gate accepted for this WO | open |
| **WT** | **Technical gates (Engineer verifies first; stop on failure):**<br>• WT-1: read-time derived `firmGroupId`/`firmGroupName` through a `notStorable` field with `select` and `leftJoins` in 10.0.12;<br>• WT-2: `currency` `precision`/`scale` params honoured as DECIMAL(13,2);<br>• WT-3: crm-db `sql_mode` behaviour with surplus decimals;<br>• WT-4: per-Account uniqueness under concurrency (a lock on the Account row, or a unique index including `deleted`);<br>• WT-5: export and `where` paths respect the denial | open |

**Stop:** any need for real data, import code, a revenue calculation, a change outside the allowlist, or a role grant other than admin.
