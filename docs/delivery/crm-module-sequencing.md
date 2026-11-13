# Foundry delivery sequencing — CRM FirmGroup and WIP/Revenue MVP

> **Provenance:** CGPT Architect delivery package of 2026-11-13 (`ER_CRM_FOUNDRY_DELIVERY_2026-11-13.zip`, sha256 `a75b5f0d1768a2a1bd945d35710e6e2067c4a7fb5e0228773946446ad9104488`), reconciled into the CRM repository by Rogue under the documentation-only assignment of 2026-11-13. CANDIDATE: not approved. Changes made during reconciliation are listed in [`docs/initiation/2026-11-13-existing-product-reassessment.md`](../initiation/2026-11-13-existing-product-reassessment.md#7-reconciliation-log).

**Status: candidate sequence — no engineering dispatch, no GitHub writes.** FOUNDRY Stage 1 v0.4 (EXISTING reassessment), project-specific PIM and exact WO contract apply. Each WO is one bounded ForgeV2 cycle with separate immutable Architect approval and independent reviews. Existing CRM beta data and external WIP source stay unchanged until separately authorised operator steps.

## Gate A — Product record alignment (documentation-only, NEXT)

Rogue receives a bounded docs-only instruction **after** CGPT/Matt direction review. Verify CRM main, Foundry revision, `DOCKER1:/srv/CRM` actual canonical checkout/worktree paths, actual Forge version and existing Issues/PRs. Prepare CRM-only candidate PR updating: README, living Product Vision, Backlog, Decisions, a dated PIM addendum, requirements/architecture/data dictionary/UX contracts, requirements traceability and external-code-register **truthful coverage**. Preserve original records and rationale. Return exact head and file hashes for CGPT/Matt approval. **No implementation, no beta writes, no legacy WIP writes, no Forge dispatch, no Foundry/ForgeV2 edits.**

## Gate B — Foundry product and implementation authority

Matt explicitly approves exact revised Vision & Backlog versions, and relevant major business decisions, via durable record. CGPT completes critical review/accepts initiation reconciliation. Rogue prepares first *bounded* implementation WO with exact Issue and version; CGPT approves that exact version. PIM does not authorise engineering by itself. No combined blanket WO for all features.

## Gate C — FirmGroup core and Account Group Members UX

WO `CRM-FG-001` (candidate name only): new `FirmGroup` entity, Account link, manager-only membership edits and audit, independent Group Members Account tab and clickable navigation; no legacy data seed. Synthetic fixtures including two unrelated peers, branch hierarchy and duplicate names; direct API denial, real browser and Account regression. Released to beta only after operator backup/upgrade/rollback review. **No automatic creation of 1,366 groups**. Separate group seed candidate WO after curated mapping/PO authority.

## Gate D — WIP entity foundation and ACL

WO `CRM-WIP-001` (candidate name): use actual verified Espo extension packaging. Create module-owned WipCase and WipFinancialPeriod models and relationships, Account foreign keys, current group ID resolution, source-provenance audit, deny-by-default WIP role and server policy tests. **Synthetic only**, no Account/Contact/Group/Opportunity writes, no real data, no production import. If too broad split by functionality, never as counter reset. Independent same-candidate review and regression. Financial readers/editors remain unassigned until PO decision; admin may run synthetic UAT.

## Gate E — Functional Account WIP/Revenue MVP

WO `CRM-WIP-002` (candidate name): Account **WIP/Revenue** tab beside Stream/Account; firm-only list, empty state, cases/observations drill-through, simple **Add/Edit** form; Account ID auto-bound and validated server-side; controlled enums/GBP decimals/date limits/duplicate and audit rules. Show fees invoiced/WIP/source-labelled yield; **no recognised revenue metric**. Group ID read-only derived. Browser tests create/edit/deny/wrong-account tampering and WIP outage containment. First prove on synthetic dev and release to beta only via operator gate; user UAT. **This is the WIP MVP.**

## Gate F — Current group WIP view (bounded increment)

Candidate `CRM-WIP-003`: Group record optionally shows member-firm WIP *records* (not fabricated revenue totals), with group read ACL, correct no-duplicate membership query, current group changes reflected, financial rows unchanged. Can be combined with later functional left-menu workspace only if small enough to test independently. Group summaries are deferred until metric semantics set.

## Gate G — WIP left-menu workspace

Candidate `CRM-WIP-004`: visible **WIP/Revenue** left nav opens real cross-firm case list/search and firm/group filters, with WIP ACL and links back to Account; not a dummy/inert menu. Modular views, tests and separate acceptance. No source import requirement for initial functional cross-firm list.

## Gate H — Transitional workbook/CSV import and data migration

Verify current source format and authority first; later candidates `CRM-WIP-005+` handle Excel/CSV parser port/reimplementation, ten skipped sheet labels, revisions and Decimal preservation, exact `sfId` crosswalk, import batches/rejects, performance and reconciliation. Synthetic parser tests precede restricted operator import. 18 unmatched legacy cases and other rejects are reviewed; no guessed Accounts. Workbook/POC remain source and historical evidence until independent cutover. **Does not block Gate E manual entry.**

## Gate I — FirmGroup curated population, historical WIP and Revenue

Separate group mapping/seed, legacy financial historical import, actual revenue definitions and historical group-as-of reporting. Each needs its own PO semantic/data authority, targeted WO and acceptance. No blanket Salesforce parent grouping or additive unverified financial totals.

## Per-WO immutable entry and stop contract (from FOUNDRY)

- Unique PBI/WO ID, exact GitHub Issue, immutable artifact (path/commit), timestamped CGPT approval and Matt decision when required.
- Verified CRM repository main SHA, DOCKER1 host/root, canonical checkout and isolated worktree parent; actual Forge engine revision and protected path, remote route if needed. Do not use an inherited path without proof.
- **ForgeV2 sandbox entry gate (verified separately for each WO).**
  - The only recorded sandbox acceptance, `maff0000/forgev2#5` comment 6746699026 (2026-11-09), was **accepted for CRM-001 only**, against engine `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`. It was explicitly not a general ForgeV2 certification.
  - Later WOs (CRM-002 to CRM-009-I) **ran** on that engine under exact-version WO approvals. That is execution evidence, not sandbox acceptance.
  - General sandbox acceptance (ENGINE-SANDBOX-TEST-001, forgev2#5, still open) is **unverified**.
  - Before the next FirmGroup WO is dispatched, the PL must show a sandbox entry gate that CGPT accepts as applying to that WO. Without one, the WO is **BLOCKED**, with evidence and escalation to CGPT.
  - The original PIM blocker B1 is **not** globally cleared. No ForgeV2 change is authorised.
- **Unit-suite baseline defect.** `tests/unit/test_beta.py` `TestBetaRuntimePinned.test_shell_guard` fails on `main` at `330978598ac6` because the real beta runtime now exists on the host. It is unresolved pre-existing evidence, not a passing test.
  - The unit suite cannot be claimed green for the next release until a narrowly bounded repair WO, or an independently accepted resolution, closes it.
  - The repair is not to be mixed into FirmGroup or WIP functionality.
- **Release-packaging compatibility (PBI-016/017).**
  - The current beta release deviates from PBI-016: it runs the pinned upstream EspoCRM image with `custom/` deployed into the runtime, not a baked `crm-espocrm` image (CRM-D017).
  - A working beta release is **not** evidence that the baked-image or clean-host packaging requirements are met.
  - Every FirmGroup/WIP release keeps the verified existing release process (`scripts/release.sh` and `release.py verify`, `deploy_release.sh --sha256 --upgrade`, the beta-safe suite), and must not claim full PBI-016/017 acceptance without that evidence.
- Bounded component/file allowlist and exclusions including FOUNDRY, ForgeV2, legacy WIP repo, Salesforce, CRM beta data and unrelated services; no silent change to application core.
- Explicit positive/negative acceptance criteria, synthetic fixtures and reproducible tests; every UI WO includes independent *real-browser* journeys and screenshots or equivalent recorded evidence.
- Engineer → independent Auditor → independent Tester → independent DevSecOps on **same unchanged candidate**; changed candidate resets evidence gates, not role execution limits. **Hard maximum of four executions per specialist per WO, including the first** (FOUNDRY). No WO, approval or exception can authorise a fifth: an exhausted limit is **FAIL** with escalation to CGPT. Documented exact log paths and owner; a missing entry gate is **BLOCKED**, with evidence and escalation to CGPT.
- Test role/REST/API denial, dependencies and supply-chain provenance, no customer/financial data in GitHub or specialists, master field fingerprints and backup/rollback. Skipped acceptance check is **not PASS**.
- After independent PASS Rogue returns exact reviewed head/evidence to CGPT for architectural acceptance, then operator release with explicit appropriate authorisation, then Matt UAT. Do not treat PR/green tests as business acceptance.

## Single-current-step discipline

At the end of each milestone Rogue reports `WORKING`, `BLOCKED`, `READY_FOR_CGPT` or `COMPLETED`, with exact artifact and next gate. **Do not dispatch a later WO just because this document lists it.** Cross-project/concurrent PLs require explicit isolation; default one CRM WO at a time.
