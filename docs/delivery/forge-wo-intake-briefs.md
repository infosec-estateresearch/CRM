# Work Order intake briefs for Rogue — NOT IMPLEMENTATION AUTHORITY

> **Provenance:** CGPT Architect delivery package of 2026-11-13 (`ER_CRM_FOUNDRY_DELIVERY_2026-11-13.zip`, sha256 `a75b5f0d1768a2a1bd945d35710e6e2067c4a7fb5e0228773946446ad9104488`), reconciled into the CRM repository by Rogue under the documentation-only assignment of 2026-11-13. CANDIDATE: not approved. Changes made during reconciliation are listed in [`docs/initiation/2026-11-13-existing-product-reassessment.md`](../initiation/2026-11-13-existing-product-reassessment.md#7-reconciliation-log).

Work Orders must be drafted as project-specific, versioned artifacts in `infosec-estateresearch/CRM/work-orders/`, each tied to its **own verified Issue URL**, separate exact CGPT approval and one bounded Forge cycle. Do not invent Issue numbers, worktree paths, engine versions, SHA references or file allowlists in advance. These briefs define intended outcomes to refine once prerequisites verified.

## CRM-FG-001 — FirmGroup and Account Group Members (first engineering WO)

**Parent:** CRM-PBI-018. **Dependencies:** revised Vision/Backlog approved; real Account metadata/role baseline and actual browser tab extension confirmed. **In:** entity/links/roles/audit, two-peer group, manager add/move/unlink, Account and group member UI; no source seeding. **Out:** WIP entities, XLSX migration, Salesforce writes, bulk group derivation. **Acceptance:** `FG-01..FG-10`; synthetic parent graph fingerprint; direct API denial; real browser navigation and edit/empty-state tests; release/rollback evidence. **Bound:** if actual Espo UI needs heavy custom code, first present a narrow technical design and reduce scope rather than guessing.

## CRM-WIP-001 — Module data foundation and financial ACL

**Parent:** CRM-PBI-019, CRM-PBI-021. **Dependencies:** FirmGroup link present; verified Espo custom packaging/role framework. **In:** WipCase/FinancialPeriod relationships, Account foreign identity, derived FirmGroup API, validation/domain service and role policy with synthetic fixtures; source/audit metadata. **Out:** GUI, Excel import, live data, revenue calculations. **Acceptance:** `WIP-01..WIP-03`, `WIP-07..WIP-12`, `WIP-16..WIP-17`, `WIP-19`, `GRP-02..GRP-03`; API/ACL denial and core master fingerprint; migration rollback. Treat field dictionary as semantic contract; exact field spellings checked against installed Espo.

## CRM-WIP-002 — Account WIP/Revenue tab and manual entry MVP

**Parent:** CRM-PBI-020. **Dependencies:** WIP-001 accepted; financial-role decision (default deny/admin UAT until PO assignment); real-browser staging. **In:** firm-only list, empty state, clickable case, controlled add/edit case + observation form, date/GBP/required status validation, audit; automatic server-side Account ID. **Out:** left menu, imports, annual or group Revenue chart, data seeding. **Acceptance:** `WIP-04..WIP-18` as applicable, synthetic CRUD, wrong-ID attack test, duplicate rejects, UI and API denial, Account/Stream and core regression, WIP-failure simulation, verified beta release and Matt acceptance.

## CRM-WIP-003 — current group WIP retrieval

**Parent:** CRM-PBI-021. **Dependencies:** FG-001 + WIP-001/002. **In:** current group list via CRM member IDs, no duplicate case counting, clear current basis. **Out:** sums of observations, revenue recognition, group seeding. **Acceptance:** `GRP-01..GRP-04`; firm move alters group view without WIP row mutation. May be attached to later sidebar workspace **only after** small-scope review.

## CRM-WIP-004 — functional WIP/Revenue left navigation

**Parent:** CRM-PBI-022. **Dependencies:** Account MVP accepted. **In:** navigable WIP/Revenue menu and real cross-firm case/firm/group filtering; reuse existing domain/presentation services. **Out:** spreadsheet importer, unverifiable Revenue KPIs. **Acceptance:** `MOD-01..MOD-02`, role scoping, real-browser test, UAT.

## CRM-WIP-005+ — source importer and historical transition (future separate gates)

**Parents:** CRM-PBI-023/025/026/027. **Dependencies:** verified source XLSX/CSV contract, legal/provenance, reconciliation baselines, PO financial definitions/real-data authority; test ten skipped sheets, duplicate header variants and revision semantics. **In:** staged source mapping/rejects/idempotency, restricted operator import. **Out:** auto-guess names or Case→Enquiry, workbook edits and production source switch without approval. **Acceptance:** `IMP-01..IMP-08`, `REV-01..REV-02` after semantic gates.

## Mandatory per-WO FOUNDRY intake checklist

Every WO must identify exact Issue and authored artifact/version; parent PBI and relevant requirements; immutable Foundry revision and exact approved CRM direction; original PIM/reassessment; real repo main/worktree/host:/path and verified engine boundary; PL/specialist ownership; scoped files and exclusions; risks/deps/approved components; exact per-role `.log` locations with writers/readers; test commands and real browser journeys; independent Engineer→Auditor→Tester→DevSecOps same unchanged candidate PASS; each role has a **hard maximum of four executions per WO, including the first**: no exception can authorise more, and an exhausted limit is FAIL with escalation to CGPT; the ForgeV2 sandbox entry gate is verified for that WO (see `crm-module-sequencing.md`), or the WO is BLOCKED; completion evidence, incident/rollback and stop conditions. Separate review/approval for every WO and beta operator deployment.
