# Product Backlog — Estate Research CRM

> **Product reset, 2026-11-18 (PROPOSED, [Issue #81](https://github.com/infosec-estateresearch/CRM/issues/81)).** WIP is an independent application and the CRM carries a link only (CRM-D035). CRM-PBI-019 to 023 and 025 are **superseded**; the earlier 2026-11-17 amendment's API route is superseded too. New items CRM-PBI-030 to 034 are added after CRM-PBI-029, and a supersession map is added at the end. Rows are not rewritten or removed.

> **Amended in part, 2026-11-17 (PROPOSED, pending CGPT approval, [Issue #71](https://github.com/infosec-estateresearch/CRM/issues/71)).** CRM-PBI-019 to 023 and 025 describe a CRM-owned WIP model and are **superseded**; PBI-018, 024 and 027 (FirmGroup) are **held**. See [`docs/architecture/crm-wip-integration-amendment.md`](docs/architecture/crm-wip-integration-amendment.md) §4. The rows below are kept unchanged for the record.

- **Status:** DRAFT. This needs Matt's explicit approval. Backlog items are not Work Orders and grant no authority (FND-009, FND-012).
- **Revision 2026-11-13 (CANDIDATE):** CRM-PBI-018 to 029 added for Firm Groups and the WIP/Revenue module (FOUNDRY Stage 1 v0.4 existing-product reassessment, [`docs/initiation/2026-11-13-existing-product-reassessment.md`](docs/initiation/2026-11-13-existing-product-reassessment.md)). CRM-PBI-001 to 017 are unchanged. A delivery-evidence table is added at the end. **This exact version needs Matt's explicit approval.** New IDs were collision-checked against `main` at `330978598ac6`.
- **Ordering:** smallest useful increment first. Each later item depends on the ones above it unless it says otherwise.
- **Traceability:** requirement IDs (R*, M*) are listed in `docs/REQUIREMENTS-TRACEABILITY.md`.
- **Release path:** CRM-001 dev instance → pseudonymised sample → **container release, accepted on a clean host** → **customer beta on approved Salesforce data** → cutover. Salesforce remains the system of record until cutover (CRM-D014).
- **Containerised delivery is mandatory (CRM-D017).** Beta and production run the same container release. Compose services, networks, named volumes and ER images are prefixed `crm-`, with a distinct project name per environment (CRM-D018).

| ID | State | Item | Value / acceptance outline | Depends on |
|---|---|---|---|---|
| CRM-PBI-001 | DEFINED | **Firms, branches and contacts baseline** on a pinned EspoCRM. Synthetic data only. | Firms with a head office and branches; same-name branches kept distinct; firm fields; contacts linked to firms; search by name, postcode, phone and email; CSV export; backup and restore. R1–R5, R16. WO: `work-orders/CRM-001.md`. | ForgeV2 sandbox acceptance on the development host |
| CRM-PBI-002 | DEFINED | **Users, roles, audit and lists** | Named users; everyone reads all records; edit rules per team; protected deletion; field history on key fields; filtered list views with CSV export (R12, R13) | 001 |
| CRM-PBI-003 | DEFINED | **Activities:** calls, meetings, tasks, follow-ups, calendar | R9; the timed scenarios that touch activities | 001 |
| CRM-PBI-004 | DEFINED | **Enquiries** | Fields per R7: stages Enquiry → Quoted → Instructed / Lost (loss reason required); quoted fee; service-type reference list (60+, admin-editable); introduced-by and channel; client reference, deceased name, case number; new or existing business; category; enquiry contacts. Enquiry search (R6) and a phone-call enquiry created in under 60 s (R8). | 001, 002; CRM-D003 confirmed |
| CRM-PBI-005 | DEFINED | **Salesforce mapping, import and reconciliation tooling**, proven on a pseudonymised sample | Mapping specification, object by object and value by value (M1), including shipping address → firm address and legacy fields. Read-only extractor; transform with the clean-up rules (M4); idempotent loader keyed on the Salesforce id, with a rejects list (M2); reconciliation report (M3). Proven end to end on the pseudonymised sample (PoC §5). **It runs as a `crm-migrate` container (a one-off Compose profile), with Salesforce credentials supplied externally** (R25). Extracted data stays in the restricted runtime and never enters Git. | 001–004; Matt's approval of the sample extraction (PoC P2) |
| CRM-PBI-006 | PROVISIONAL | **Email filing spike:** an ER filing service and an Outlook task pane | PoC G3-1 to G3-6, on a test mailbox | 004; test mailbox and app registration |
| CRM-PBI-007 | PROVISIONAL | **ERic read-only API adapter** | ERic reads firms and contacts through a read-only token; write attempts fail; firm id mapped to ERic's company key (R14) | 001, 002 |
| CRM-PBI-010 | DEFINED | **Upgrade and rebuild proof** | An upstream patch release applies with ER customisations installed; a clean rebuild from image plus extension gives the same result; smoke tests pass (R15) | 001–004 |
| CRM-PBI-016 | DEFINED | **Container release packaging** | An ER application image `crm-espocrm`, built from the pinned upstream digest with `custom/` baked in. A versioned release bundle: Compose file, `env.example`, install / backup / restore / upgrade / rollback guide. Services `crm-app`, `crm-daemon`, `crm-db`. Maintenance and migration jobs as `crm-*` one-off services. Named volumes `crm-*` under a per-environment project name (`crm-beta`, `crm-prod`). Secrets and environment configuration kept outside the images. Every image pinned by digest (R19–R24, R27). | 001–005, 010 |
| CRM-PBI-017 | DEFINED | **Clean-host deployment acceptance** | On a disposable clean Docker host with only Docker Engine and Compose, and no ForgeV2, Claude, Git checkout or development-host paths, the release bundle: installs; starts; contains every ER customisation; keeps data when containers are recreated; restores from backup; upgrades and rolls back; and loads the sample twice through `crm-migrate` with identical reconciliation. No host PHP, MariaDB or Python is needed (R19–R26). | 016; a clean test host |
| CRM-PBI-011 | DEFINED | **Beta environment readiness** | A separate beta environment, deployed from the PBI-016 release accepted under PBI-017 (the same architecture as production, R26); TLS; reachable only by named beta users on the LAN; named logins; daily backup with a tested restore; documented access and disposal rules; Matt's data-protection approval for loading real data | 002, 016, 017 |
| CRM-PBI-012 | DEFINED | **Beta data load**, using approved Salesforce data | The PBI-005 tooling is run, as the `crm-migrate` container, against the objects Matt approves: firms, contacts, enquiries, activities and historic emails (R11). Reconciliation is 100%, with every mismatch explained. Full-volume search is p95 < 1.5 s (R6). The load can be re-run. | 005, 011 |
| CRM-PBI-013 | DEFINED | **Customer beta: user acceptance and feedback** | Estate Research staff use the beta against the beta acceptance criteria. Feedback is recorded and triaged. Blocking items are fixed and retested (R17). | 012, 003, 004 |
| CRM-PBI-014 | PROVISIONAL | **Production email filing** (Outlook "File to CRM") | Production authorisation, de-duplication, audit, deployment to staff mailboxes (R10). **Required for cutover, not for the beta.** | 006, 011 |
| CRM-PBI-008 | PROVISIONAL | **Staff rollout:** training and all users | Every user on a named login, trained; timed scenarios confirmed across teams | 013, 014 |
| CRM-PBI-015 | PLACEHOLDER | **Cutover and Salesforce switch-off** | Production deployed from the accepted container release; rehearsed full reload and reconciliation; final delta; parallel run with Salesforce read-only; ERic switched to the CRM adapter (007); switch-off before summer 2027, timed to the contract renewal (M6) | 007, 008, 013, 014 |
| CRM-PBI-018 | DEFINED | **P0.** Independent **FirmGroup** entity with Account belongsTo relationship, CRUD membership by manager, peer-firm grouping, clickable Account Group Members tab, current group name, audited moves, server ACL | See `docs/requirements/crm-modules-requirements.md` and the traceability section *Expanded scope (2026-11-13)*. | Current Account UI inspection, full regression and browser audit; no source seeding |
| CRM-PBI-019 | DEFINED | **P0.** **CRM–WIP boundary contract** and module scaffolding: CRM authoritative firms/contacts/groups, WIP financial entities, distinct code ownership, no WIP core writes, finance ACL and change isolation | See `docs/requirements/crm-modules-requirements.md` and the traceability section *Expanded scope (2026-11-13)*. | Approved Vision/decision, real Espo packaging check |
| CRM-PBI-020 | DEFINED | **P0.** **WIP/Revenue Account tab and manual entry MVP**: Account-specific WIP list, clear empty state, add/edit validated WipCase + first financial observation, permissions, audit, correct immutable account reference, no billing logic inventions | See `docs/requirements/crm-modules-requirements.md` and the traceability section *Expanded scope (2026-11-13)*. | WIP entities/ACL; can ship with synthetic/manual UAT independent of XLSX migration |
| CRM-PBI-021 | DEFINED | **P0.** **WIP identity & current FirmGroup visibility**: read-only `firmId`/derived `groupId`, group retrieval by CRM membership, no duplicate counting or stale group copies, group move behaviour tested | See `docs/requirements/crm-modules-requirements.md` and the traceability section *Expanded scope (2026-11-13)*. | FirmGroup entity, WipCase Account link; group totals only when metric semantics established |
| CRM-PBI-022 | DEFINED | **P1.** **WIP module workspace/navigation skeleton**: left menu WIP/Revenue opens a functional landing page; reuse WIP entity forms, begin cross-firm filtered case list; no fake dashboard or revenue metrics | See `docs/requirements/crm-modules-requirements.md` and the traceability section *Expanded scope (2026-11-13)*. | Account-tab MVP accepted; menu not an inert placeholder in live UI |
| CRM-PBI-023 | DEFINED | **P1.** **Transitional source investigation and verified importer**: XLSX/CSV interface verification, all valid month tabs, source IDs, Decimal-safe mapping, provenance, idempotent batches, rejects, signed-off reconciliation | See `docs/requirements/crm-modules-requirements.md` and the traceability section *Expanded scope (2026-11-13)*. | HELM evidence; separate operator data access; do not block manual entry |
| CRM-PBI-024 | PROVISIONAL | **P1.** **FirmGroup curated mapping and controlled population**: inspect 36 approved legacy groups, conflicts/unmatched, protect manually changed membership, verified idempotent seed, review queue | See `docs/requirements/crm-modules-requirements.md` and the traceability section *Expanded scope (2026-11-13)*. | Independent PO approval of group-membership mapping; never seed all 1,366 hierarchy trees automatically |
| CRM-PBI-025 | PROVISIONAL | **P2.** **Legacy WIP case & financial history transition**: source-to-CRM reconciled import; unmatched 18 case assignments not guessed; multiple cohort revisions preserved; workbook remains source until cutover | See `docs/requirements/crm-modules-requirements.md` and the traceability section *Expanded scope (2026-11-13)*. | Import contract, source authority, financial data and cutover decisions |
| CRM-PBI-026 | PROVISIONAL | **P2.** **Revenue definitions and calculation rules**: decide recognised revenue vs fees invoiced vs revised/actual yield; period treatment; reconcile against business-approved reference | See `docs/requirements/crm-modules-requirements.md` and the traceability section *Expanded scope (2026-11-13)*. | PO definition; neither WIP & Rev nor summaries proves revenue |
| CRM-PBI-027 | PROVISIONAL | **P2.** **Group-level financial reporting** and optional historical membership-as-of views with correct case revision selection, controlled access and no double counting | See `docs/requirements/crm-modules-requirements.md` and the traceability section *Expanded scope (2026-11-13)*. | FirmGroup data, WIP MVP, approved metric semantics; historical basis undecided |
| CRM-PBI-028 | PLACEHOLDER | **P3.** Advanced cross-firm workflow, business reports, exception-review cockpit, optional Case/Enquiry linkage after evidence | See `docs/requirements/crm-modules-requirements.md` and the traceability section *Expanded scope (2026-11-13)*. | Later Agile refinement; not implementation-ready |
| CRM-PBI-029 | DEFINED | **P0.** **Documentation/provenance reconciliation**: update Vision/Backlog/README/decisions/PIM amendment/requirements/security register to truthful current product and beta evidence | See `docs/requirements/crm-modules-requirements.md` and the traceability section *Expanded scope (2026-11-13)*. | Stage 1 reassessment, exact PO artifact approval, docs-only GitHub gate |
| CRM-PBI-030 | DEFINED | **P0.** **Open WIP / Revenue action on the Account page**: one supported EspoCRM menu action that opens the independent WIP application at that Account in a new tab; non-secret per-environment base URL; fails closed; CRM unaffected if WIP is down | Acceptance A, B, C, F, G of Issue #81 §6. WO `work-orders/CRM-WIP-LINK-001.md` (DRAFT v1.1) | 031 (delivered inside the same Work Order) and the WIP firm page (private WIP repository, `WIP-CRM-CONTEXT-001`) |
| CRM-PBI-031 | DEFINED | **P0.** **Client-asset delivery (minimal, inside `CRM-WIP-LINK-001` v1.1)**: browser code under `client/custom/src` reaches the CRM runtime from Git with the same stop, stage and rename discipline as `custom/Espo/Custom`, a cache-bust, restore on failure and managed removal (so deploying the base restores the original page), and survives backup and restore | Decided by CGPT 2026-11-18 (CRM-D040, option 2). Built on current `main`; the candidate `07bfaf1c…` (draft PR #69) is read-only evidence and is **not** merged or inherited. Delivered by the same Work Order as 030 (no separate Work Order) | none (delivered by the same Work Order as 030) |
| CRM-PBI-032 | PROVISIONAL | **P1.** **Read-only CRM identity source for WIP beyond the synthetic proof**: a loopback-only, per-environment, off-by-default CRM database publication or an equivalent isolated path, with a restricted read-only login; amends CRM-D012 | Needs its own Work Order (`CRM-DB-READ-001`), operator verification and CGPT approval. Not needed for D1 | CGPT approval; amends CRM-D012 |
| CRM-PBI-033 | PLACEHOLDER | **P2.** **FirmGroup to WIP link**: from a CRM FirmGroup, open WIP's group view, which finds current members from the CRM; no WIP group master, no totals until the metric is defined | Committed to the roadmap as a separate bounded Work Order after D1 (`WIP-GROUP-001`, after `CRM-FG-001`); no WIP group master | CRM-PBI-018 (held, CRM-D034), the PO's group decision, and the WIP group view (`WIP-GROUP-001`) |
| CRM-PBI-034 | PROVISIONAL | **P1.** **Repeatable real-browser journey assurance** for the CRM-to-WIP path on synthetic data (operator run: Chrome for Testing in a pinned image, an evidence package, a clean teardown) | Capability exists (headless launch verified 2026-11-18); the harness and network arrangement are to be settled in the D1 operator plan (WIP `docs/operations/D1-SYNTHETIC-INTEGRATION-PLAN.md`) | 030 and 031 |

CRM-PBI-009 (full migration and switch-off) is replaced by PBI-005, PBI-012 and PBI-015.


## Expanded scope (2026-11-13): Firm Groups and WIP/Revenue

- **Release priority (recommended):**
  1. documentation alignment (029);
  2. FirmGroup, unseeded, with its UI (018);
  3. WIP module skeleton, entities and financial permissions (019);
  4. Account WIP/Revenue read/create/edit MVP (020);
  5. group-aware WIP retrieval (021);
  6. sidebar workspace (022);
  7. importer and validated migration (023, 025);
  8. formal Revenue and advanced group reporting (026, 027).
- **Data definitions:**
  - `WipCase`: financial case reference, linked to its Account identity;
  - `WipFinancialPeriod`: a source observation with provenance, not a month-end ledger;
  - later, `WipImportBatch` and `WipImportReject`.

  There is no additional WIP firm master. An operational Case Manager is not assumed to be superseded.
- **Explicit MVP exclusions:**
  - no WIP source imports;
  - no live revenue or fiscal-flow claims;
  - no full spreadsheet rewrite;
  - no unapproved group mass seeding;
  - no automatic Account creation;
  - no automatic Enquiry link.

  Financial access defaults to denial until explicitly assigned. Beta data entry is UAT until production cutover is separately approved.
- **Work Orders:** each item is delivered through its own exact-version Work Order on its own Issue. Candidate briefs are in [`docs/delivery/forge-wo-intake-briefs.md`](docs/delivery/forge-wo-intake-briefs.md); they grant no authority.

## Delivery evidence at 2026-11-13 (CRM-PBI-001 to 017)

Recorded facts only. The **State** column above shows refinement readiness and is unchanged. "Engineered" means a ForgeV2 outcome recorded in `.forge/<WO>/REPORT.md`. Product acceptance by Matt (CRM-D013) is not recorded for any item.

| PBI | Work Orders | Evidence |
|---|---|---|
| 001 | CRM-001 (+C1, C2, LAN) | ESCALATED (browser and live checks only); on `main` (#5, #43); `crm-dev` running on synthetic data |
| 002 | CRM-003, CRM-003-F | CRM-003 ESCALATED (browser and live only); 003-F DELIVERED; provisioned on beta |
| 003 | CRM-005 | DELIVERED; activities loaded on beta |
| 004 | CRM-004 | DELIVERED; enquiries loaded on beta. R8 (phone enquiry under 60 s) is not yet measured |
| 005 | CRM-002 (+S to W), CRM-006R/006S, CRM-008 (+F, G), CRM-009-H, CRM-009-I | Extractor and loader DELIVERED. The real extract reconciled with drift (1 accepted EmailMessage). No pseudonymised-sample run is evidenced in this repository; real extraction proceeded under the PO priority override (Issue #9) |
| 011 | CRM-007/007R, CRM-009 (+F, G) | Beta in **UAT mode** (plain HTTP, LAN-only, PO risk acceptance). TLS/production mode is retained as the default but **not** in use; named logins; the common UAT password used at first load was replaced with unique passwords on 2026-11-26 |
| 012 | Operator load (CRM-009 direction) | BETA_POPULATED reported on Issue #9; 160 write rejections (0.08%) and 1 recurring Contact update are open. Full-volume p95 search (R6) is not measured. Reconciliation with "every mismatch explained" is incomplete: the rejection field reasons are not captured |
| 013 | — | UAT in progress (Matt) |
| 016, 017 | CRM-007/007R | Release bundles built reproducibly (`scripts/release.sh`); clean-host deploy evidence is per CRM-007R. **Deviation to review:** beta runs the pinned upstream image with `custom/` deployed into the runtime, not a baked `crm-espocrm` image (PBI-016 text, CRM-D017) |
| 006, 007, 008, 010, 014, 015 | — | Not started |

## Supersession map, 2026-11-18

Nothing is deleted. "Replacement" names where the intent now lives.

| PBI | State from 2026-11-18 | Why | Replacement or owner |
|---|---|---|---|
| CRM-PBI-018 FirmGroup | HELD | The CRM still owns FirmGroup identity (CRM-D023); group work waits for the confirmed requirement and the PO decision (CRM-D034) | stays here |
| CRM-PBI-019 CRM-WIP boundary and module scaffolding | **SUPERSEDED** | There is no WIP module inside the CRM | CRM-D035; architecture record §2; WIP repository boundary record |
| CRM-PBI-020 WIP/Revenue Account tab and manual entry | **SUPERSEDED** | WIP is its own application; the CRM keeps only the action | CRM-PBI-030 plus the WIP repository's firm page and later `WIP-WRITE-001` |
| CRM-PBI-021 WIP identity and current FirmGroup visibility | **SUPERSEDED** | The identity rules move into the WIP application and CRM-D036 | CRM-D036; later CRM-PBI-033 |
| CRM-PBI-022 WIP module workspace and navigation | **SUPERSEDED** | WIP has its own navigation | WIP repository |
| CRM-PBI-023 Transitional source investigation and verified importer | **SUPERSEDED** for the CRM | The WIP import and sync are WIP's operational pipeline | WIP repository (`WIP-OPS-001` is the existing issue) |
| CRM-PBI-024 FirmGroup curated population | HELD | Unchanged (CRM-D024) | stays here |
| CRM-PBI-025 Legacy WIP history transition | **SUPERSEDED** for the CRM | WIP keeps its history; any reconciliation is a WIP-owned, separately approved cutover | WIP repository |
| CRM-PBI-026 Revenue definitions | RETAINED, owner moves | The revenue definition is a PO decision; the calculation lives with WIP | PO, then WIP |
| CRM-PBI-027 Group-level reporting | HELD | Needs the CRM FirmGroup, the group view and the metric | later |
| CRM-PBI-028 Advanced cross-firm workflow | PLACEHOLDER | Unchanged; now a WIP matter | WIP repository |
| CRM-PBI-029 Documentation and provenance reconciliation | DEFINED, in review | Fulfilled for the reset by this document set, pending approval | this branch |

## Delivery direction (2026-11-26)

Items for the direction in [Issue #91](https://github.com/infosec-estateresearch/CRM/issues/91) and decisions CRM-D044 to CRM-D054. Listing an item grants no dispatch.

| ID | State | Item | Value / acceptance outline | Depends on |
|---|---|---|---|---|
| CRM-PBI-035 | PROVISIONAL | **P0.** **Identity integrity controls** | Every identity relationship change audited or refused; identity records retired or superseded, not deleted; identity audit protected and retained (CRM-IDINT-001) | 001 |
| CRM-PBI-036 | PROVISIONAL | **P0.** **Two user types, sign-in security and administrator user management** | One `ER User` role; Admin section with Users; native temporary passwords and resets; second factor enforced; tested by browser and API | 002, 035 |
| CRM-PBI-037 | PROVISIONAL | **P0.** **Logging, audit and retention baseline** | Coverage, structured events, bounded storage and checks in `docs/LOGGING.md` | 035, 036 |
| CRM-PBI-038 | PROVISIONAL | **Post-MVP.** **Forward ERm events to the existing Graylog** | Encrypted transport, search by identity, dashboards, alerts, catch-up after outage | 037 |
| CRM-PBI-039 | PROVISIONAL | **P0.** **Backup, off-host copy, restore proof and identity register** | Scheduled encrypted copies; verified full application restore including identifiers; bounded retention; failures visible; register tests of `docs/IDENTITY.md` | 016, 035 |
| CRM-PBI-040 | PROVISIONAL | **P0.** **Contact and firm workflow with group selection** | Create or choose firm and group without leaving the contact; browser accepted | 018, 034 |
| CRM-PBI-041 | PROVISIONAL | **P0.** **Non-destructive source delta, rejected records and historical Notes** | No overwritten ERm changes; originals preserved; Salesforce Notes handled; reconciliation and rollback | 005, 035 |
| CRM-PBI-042 | PROVISIONAL | **P0.** **Production target and identity-preserving cutover** | Rehearsed promotion, recorded identity start date, rollback criteria; Outlook filing (014) unless deferred | 014, 039, 041 |
| CRM-PBI-043 | PROVISIONAL | **P1.** **Transitional Salesforce Sync (administrator only)** | CRM-D050; on the existing extractor and loader; synthetic proof first; removable | 036, 041 |

### Changes of state, 2026-11-26 (rows above are not rewritten)

| PBI | State from 2026-11-26 | Why |
|---|---|---|
| CRM-PBI-018 FirmGroup | RESUMED, before MVP | CRM-D045 |
| CRM-PBI-006, CRM-PBI-014 Email filing | Back on the active roadmap | CRM-D054 |
| CRM-PBI-030, 031 | ON HOLD for further WIP-specific work; merged work preserved | CRM-D051 |
| CRM-PBI-032, 033 | ON HOLD | CRM-D051 |
| CRM-PBI-034 Browser assurance | Re-scoped to ERm journeys without any WIP dependency | CRM-D045, CRM-D051 |
