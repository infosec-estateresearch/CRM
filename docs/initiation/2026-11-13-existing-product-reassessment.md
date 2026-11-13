# CRM Stage 1 existing-product reassessment — PIM addendum (2026-11-13)

- **Status:** CANDIDATE for CGPT critical review and Matt's exact-version approval. It grants no implementation, deployment or Work Order authority.
- **Route:** EXISTING, under FOUNDRY Stage 1 v0.4 (`stages/01-product-discovery.md`, "Existing-product discovery").
- **Governing FOUNDRY:** `maff0000/foundry@5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0`. Re-verified on GitHub on 2026-11-13: `stages/01-product-discovery.md` declares v0.4.
- **Prepared by:** Rogue (Orchestrator), 2026-11-13. Source: the CGPT Architect delivery package of the same date, reconciled against the current repository (see the [reconciliation log](#7-reconciliation-log)).
- **Relationship to the original PIM:** [`PROJECT-INITIATION-MANDATE.md`](../../PROJECT-INITIATION-MANDATE.md) (2026-11-06) is kept unchanged as the historical initiation record, apart from a pointer to this file. The original PIM did not authorise FirmGroup or WIP/Revenue work, and this addendum does not imply that it did.

## 1. Verified baselines (2026-11-13)

| Item | Value | How verified |
|---|---|---|
| CRM repository | `infosec-estateresearch/CRM`, public | — |
| CRM `main` at start of this reassessment | `330978598ac6147d4a1bce3f713113d59045d465` | Local canonical checkout, `origin/main` and the GitHub API all agree |
| Legacy WIP repository (read-only evidence) | `infosec-estateresearch/WIP@91b2af19877b498ed307ee9f1218b3243b2b60ba` | GitHub API (matches HELM's report). Not modified. |
| FOUNDRY | `maff0000/foundry@5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0` | GitHub API. Not modified. |
| Execution target | `DOCKER1:/srv/CRM`: canonical checkout `main/`, worktree parent `worktrees/`, both owned by the multi-project PL identity (not by root). Runtime state stays under `/srv/CRM/runtime/<env>/`, root-owned. | Host inspection by the PL |
| ForgeV2 installation | Revision `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, the same as the PIM pin | Read-only `git rev-parse` of the installation. Not modified. |

## 2. Current product truth

These facts replace the bootstrap statements "nothing is installed" and "no incorporated code". The original statements stay in Git history and in the original PIM.

- **Implementation exists on `main`:**
  - EspoCRM 10.0.12 with Estate Research customisations in `custom/`;
  - provisioning, release, deploy, backup and restore scripts;
  - the `crm-load` importer;
  - unit, load and acceptance suites.

  Delivery records for each Work Order are in `.forge/<WO>/REPORT.md`, and the merged PRs are #43 to #53.
- **Environments:**
  - `crm-dev` holds synthetic data only.
  - `crm-beta` runs release `crm-release-330978598ac6`, built twice reproducibly from `main` `3309785`, in **UAT mode** (CRM-009): plain HTTP, reachable only from the two authorised internal networks.
- **Beta data:** Rogue reported BETA_POPULATED on Issue #9 on 2026-11-11. This is an operator report; CGPT has not verified the runtime independently. The report, in counts only:
  - real Salesforce data from the verified extract (contract v4, RECONCILED_WITH_DRIFT with one accepted EmailMessage drift);
  - 8,732 firms, 23,697 contacts, 66,175 enquiries, 9,157 tasks, 495 calls, 2,943 meetings and 34,138 emails;
  - 160 writes rejected (0.08%);
  - the final re-run created 0 records; its only writes were 1 Contact update and retries of the rejected records;
  - 25 staff accounts, on a common temporary UAT password;
  - Salesforce untouched.
- **Open beta caveats (recorded, not fixed by this reassessment):**
  - 160 write rejections whose field-level reason is not captured;
  - 1 Contact re-updated on every re-run;
  - advisories carried from the CRM-009-H and CRM-009-I reviews.

  The HTTP and common-password arrangement is a UAT-only risk acceptance by the PO, not production architecture.
- **Acceptance state is not product acceptance:**
  - Several WOs ended as ESCALATED (browser and live checks only), for example CRM-001 and CRM-003.
  - Most WO PRs remain open because their branches reached `main` through `release/beta-1` (#43).
  - Matt's per-WO walkthrough and acceptance (CRM-D013) is not recorded for any WO.
  - Customer-beta UAT (CRM-PBI-013) is in progress.
- **Stale blocker:**
  - The PIM's B1 says ForgeV2 sandbox acceptance is BLOCKED (forgev2#5), with the stop rule "no ForgeV2 application WO runs while B1 is BLOCKED".
  - forgev2#5 is still **open** on 2026-11-13, yet application WOs from CRM-002 onwards were dispatched under Architect exact-version approvals recorded on Issue #9.
  - The Architect must confirm how B1 was superseded, or record it as an accepted exception. This addendum does not resolve it.

## 3. Reason for reassessment and the proposed direction

The product scope is being expanded in two ways:
- (a) independent commercial **FirmGroup** relationships;
- (b) a **WIP/Revenue** functional module inside the same CRM application and repository.

Under the proposed direction, CRM owns business identities and WIP owns financial case references and observations. WIP never changes CRM master data. A simple, validated Account WIP/Revenue tab comes first; a broad WIP workspace and source imports come later. The legacy WIP repository, database and workbook stay untouched.

The detail is in:
- [`PRODUCT-VISION.md`](../../PRODUCT-VISION.md)
- [`PRODUCT-BACKLOG.md`](../../PRODUCT-BACKLOG.md) (CRM-PBI-018 to 029)
- [`DECISIONS.md`](../../DECISIONS.md) (CRM-D020 to D032)
- [`docs/architecture/crm-wip-module-boundary.md`](../architecture/crm-wip-module-boundary.md)
- [`docs/requirements/`](../requirements/)
- [`docs/discovery/wip-evidence-status.md`](../discovery/wip-evidence-status.md)
- [`docs/delivery/`](../delivery/)

## 4. Evidence reviewed

- Issue #9 (BETA_POPULATED and the CRM-009-F to I delivery records);
- PRs #1 to #53;
- `.forge/*/REPORT.md`;
- the current README, Vision, Backlog, Decisions, PIM, traceability and external code register;
- FOUNDRY Stage 1 v0.4;
- HELM's WIP audits of 2026-11-12 and 2026-11-13, as summarised in the CGPT package. Rogue has **not** re-run HELM's audit; its figures are recorded as HELM-reported.

## 5. Security and dependency context (expanded scope)

- **Data:**
  - personal data under UK GDPR (professional contacts, estate enquiries);
  - commercially sensitive financial case data (WIP).

  WIP financial access is a separate, deny-by-default permission, enforced on the server and in the API as well as in the GUI (CRM-D029).
- **Trust boundaries added:**
  - staff browser → WIP/Revenue tab;
  - WIP module → CRM master records (read only);
  - later, a transitional source file → importer, in a restricted operator environment.
- **Shared fate:** WIP runs in the same PHP process and MariaDB as core CRM. This is logical separation, not process isolation. Fail-closed panels and core regression tests are required (WIP-13).
- **External code:** see the [external code reconciliation](#10-external-code-reconciliation) below and `security/EXTERNAL_CODE_REGISTER.yaml`. No legacy WIP code or dependency is incorporated by this reassessment.
- **Public repository:** CRM-D011 continues to apply. No firm or staff names, Salesforce identifiers, workbook rows, financial values, host addresses or secrets go in this repository.

## 6. Bounded authority and exit

This addendum supports one documentation-only candidate (this PR). Exit requires all of:
1. CGPT critical review of the exact candidate commit.
2. Matt's explicit approval of the exact Vision and Backlog versions, and of the decisions listed in §8, recorded after the candidate commit to avoid a circular SHA.
3. Architect acceptance of this reassessment.

After that, the first FirmGroup implementation WO is drafted separately, on its own Issue, and approved by exact version. **No WO is approved or dispatched by this document.**

## 7. Reconciliation log

The package was reconciled, not copied:
- **Package:** `ER_CRM_FOUNDRY_DELIVERY_2026-11-13.zip`, sha256 `a75b5f0d1768a2a1bd945d35710e6e2067c4a7fb5e0228773946446ad9104488`, 16 files.
- **Retained in the PR:** the handoff instruction (`docs/delivery/ROGUE-STEP-01-DOCS-ONLY.md`) and the package's `README-REVIEW.md` and `MANIFEST.md` are not product records, so they are not committed. The package hash above preserves their provenance.

| # | Package content | Reconciled as | Reason |
|---|---|---|---|
| 1 | `PRODUCT-VISION.md` (full replacement) | The revised living Vision in place. The 2026-11-06 Vision content is kept in a "Retained" section, with explicit supersessions. | Preserve approved history (it was a draft); no silent overwrite |
| 2 | `PRODUCT-BACKLOG.md` (addendum) | CRM-PBI-018 to 029 appended to the existing table (IDs collision-checked: none used before). 001 to 017 are unchanged; an evidence table is added. | Package instruction |
| 3 | `docs/decisions/crm-wip-reassessment.md`, IDs `CRM-D-W01` to `W14` | Merged into `DECISIONS.md` as **CRM-D020 to CRM-D032**, PROPOSED (mapping in §9). W14 is *not* a product decision; it is recorded as an open host item (§2, and `wip-evidence-status.md`). | Keep one register and one ID scheme |
| 4 | `docs/requirements/traceability-addendum.md` | Merged into `docs/REQUIREMENTS-TRACEABILITY.md` as a new section. R1 to R27 and M1 to M6 are unchanged. | One traceability record |
| 5 | `docs/security/external-code-reconciliation.md` | Applied to `security/EXTERNAL_CODE_REGISTER.yaml` (coverage corrected) and summarised in §10. Not committed as a separate file. | The register is the record |
| 6 | `docs/initiation/…-reassessment.md` | This file, extended with verified baselines, product truth, the log and the mappings | Truthful current state |
| 7 | Requirement IDs FG-, WIP-, GRP-, MOD-, IMP-, REV- | Kept; collision-checked against `main` (none in use) | — |
| 8 | Candidate WO names `CRM-FG-001`, `CRM-WIP-001` and later | Kept as *candidate titles*. The existing WO series is `CRM-0NN[-X]` (latest CRM-009-I). **Decision for the Architect:** keep the new prefixes, or number them CRM-010 onwards. | Naming is an Architect choice |
| 9 | `wip-evidence-status.md`: host paths, legacy database name, workbook filename, root Git-config path | Generalised ("legacy WIP application and database on the development host", "master WIP workbook (restricted)") | CRM-D011: host details beyond the bare hostname are not published |
| 10 | Package PIM addendum: "`main/` and `worktrees/` under root" | Corrected: owned by the multi-project PL identity; only runtime state is root-owned | Host evidence |
| 11 | Package: "prior PIM records ForgeV2 `63b6b8ab…`, not proof of current installed state" | Verified that the installed revision equals the pin (§1). Recorded B1 and forgev2#5 still open (§2). | Truthful engine state |
| 12 | Original Vision constraint "WIP … not affected by CRM work" and CRM-D006 "WIP owns financial WIP" | Kept for the **legacy** WIP system. Superseded for the new WIP module by CRM-D020 to D022 and CRM-D031 (amendment, not rewrite) | Explicit supersession |
| 13 | Original Vision "Out of scope: Dashboards, forecasting" | Still out of scope. WIP/Revenue reporting is a separate, gated capability (CRM-PBI-026/027); no Revenue KPI until defined | Avoid contradiction |
| 14 | README "Status: initiation. Nothing is installed or released" and "edge reached only by the PO's TLS HAProxy" | Updated to the current state (beta in UAT mode, CRM-009); production HTTPS stays the default mode | Stale |
| 15 | Traceability "Nothing is built yet" | Kept as the historical statement, with a dated note that implementation now exists and per-requirement delivery status needs a separate evidence pass | No unproven status claims |
| 16 | Package backlog states "DEFINED" for new P0/P1 items | Kept, but the whole Backlog remains DRAFT pending Matt's approval; "DEFINED" means refined enough to draft a WO, not approved | FND-009/012 |

## 8. Product decisions requiring Matt's approval

1. The revised **Product Vision**, at the exact version in this PR.
2. The revised **Product Backlog** at this exact version: CRM-PBI-018 to 029, their priorities and their order.
3. **CRM-D020 to CRM-D032** (proposed decisions), especially:
   - D023: an independent FirmGroup entity; managers and admins edit membership, Staff and Intake view;
   - D024: no automatic seeding from the 1,366 Salesforce parent trees;
   - D025: the Account WIP/Revenue tab is the first WIP MVP;
   - D027: `accountId` is required and `groupId` is derived and read-only;
   - D028: revenue is not defined and no Revenue metric is shown;
   - D029: WIP financial access is deny-by-default.
4. **Held, and not blocking the synthetic MVP:**
   - which staff may read, add or edit WIP financials;
   - the live transitional exchange format (XLSX or CSV);
   - the definition of revenue;
   - legacy case-reference uniqueness;
   - the status, fee-type and case-type vocabularies;
   - whether group reporting uses current or historical membership;
   - whether Case Manager keeps the operational case master.
5. **For the Architect, not Matt:** WO numbering (§7 row 8), and how PIM B1 was superseded (§2).

## 9. Decision ID mapping

| Package ID | Register ID | Package ID | Register ID |
|---|---|---|---|
| CRM-D-W01 | CRM-D020 | CRM-D-W08 | CRM-D027 |
| CRM-D-W02 | CRM-D021 | CRM-D-W09 | CRM-D028 |
| CRM-D-W03 | CRM-D022 | CRM-D-W10 | CRM-D029 |
| CRM-D-W04 | CRM-D023 | CRM-D-W11 | CRM-D030 |
| CRM-D-W05 | CRM-D024 | CRM-D-W12 | CRM-D031 |
| CRM-D-W06 | CRM-D025 | CRM-D-W13 | CRM-D032 |
| CRM-D-W07 | CRM-D026 | CRM-D-W14 | *(not a decision: open host item)* |

## 10. External code reconciliation

All statements below come from the repository at `330978598ac6` and the deployed beta.

- **Incorporated:**
  - EspoCRM 10.0.12, MariaDB 11.4.13 and HAProxy 3.2.26, pinned by digest in `deploy/compose.json`, `deploy/beta/compose.json` and `deploy/beta/restoretest/compose.json`, and checked by `scripts/release.py` and `tests/unit/test_compose_policy.py`;
  - Estate Research's own `custom/` metadata and PHP;
  - Python scripts and tests that use the standard library only (import scan of `scripts/`, `load/` and `tests/`).
- **Not inventoried:**
  - the contents of the upstream images (PHP, Apache, EspoCRM's bundled PHP and JS libraries, the Alpine and Debian base layers). Coverage is therefore **partial**; there is no SBOM.
- **Approval evidence:**
  - the register records no formal approval for any component;
  - use in dev and beta followed Architect-approved WOs (CRM-001, CRM-007/007R);
  - whether that counts as component approval is for the Architect to confirm.
- **Not incorporated (legacy WIP only):**
  - PyMySQL, PyYAML, openpyxl, FastAPI, uvicorn, and the Bootstrap and htmx CDNs;
  - legacy WIP and ERic parser source.

  Any future reuse needs ownership, licence and provenance assessment, plus pinning to an exact commit, under its own WO.
