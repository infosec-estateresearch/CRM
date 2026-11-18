# Architecture: standalone WIP/Revenue proof of concept (EspoCRM link only)

- **Date:** 2026-11-18. **Status:** PROPOSED. Not approved; it grants no Work Order, dispatch or deployment authority.
- **Authority:** the Product Owner's direction and the CGPT Architect baseline recorded in [Issue #81](https://github.com/infosec-estateresearch/CRM/issues/81) (the Product Owner's clarification of 2026-11-18 is the latest word), and the CGPT directive for the D0 documentation mission (relayed by Matt, 2026-11-18). Prepared by Rogue (Orchestrator).
- **Governing FOUNDRY:** `maff0000/foundry@84fedf0a74017237aa1bd650d8560350c91c7f0e` (the current `main`, checked 2026-11-18): `stages/01-product-discovery.md`, `standards/product-records.md`, `standards/work-order-contract.md`, `standards/secure-engineering.md`.
- **Base:** `infosec-estateresearch/CRM` `main` at `e157bd51429e2764a94cecaf85a06bf707bd876f`.
- **Companion record (private repository):** `infosec-estateresearch/WIP` `docs/architecture/2026-11-18-crm-context-wip-poc.md` holds the WIP-side design, the reuse/rebuild decision and the WIP evidence. This public record carries no customer data, host addresses or credentials (CRM-D011).
- **Labels:** VERIFIED (observed on 2026-11-18 by Rogue, read-only), INFERRED (follows from verified facts), UNKNOWN (not established).

## 1. The product, in one paragraph

A user opens a firm in EspoCRM and sees an **Open WIP / Revenue** button. It opens the **independent WIP web application** in a new tab at that firm's page. WIP reads the firm's name and legacy key from the CRM's database (read-only) and the firm's WIP cases and amounts from its **own** database. WIP links back to the exact CRM firm. EspoCRM contains **no WIP data, WIP SQL, WIP calculation or WIP entity**: it contains one navigation action. Fixing a WIP screen or calculation never touches EspoCRM.

## 2. Ownership and code boundary (invariants)

| Concern | Owner | Rule |
|---|---|---|
| Account (firm), Contact, address, FirmGroup entity and membership | EspoCRM (this repository) | WIP reads; it never creates or updates them. WIP derives group membership on read and keeps no group master |
| WIP cases, values, fees invoiced, yields, status, observation history, WIP business logic and SQL | The WIP application and its MariaDB (private WIP repository) | Nothing of it lives here |
| The Account action | A tiny EspoCRM customisation (this repository) | Navigation only: no WIP SQL, no PHP loader, no API adapter, no WIP table, no core patch |
| Cross-application sign-on and a common security gateway | A later programme (D4) | Not a prerequisite for the synthetic PoC. No new token, API or identity service for the link |
| CRM-to-WIP context | Browser navigation | Only the opaque CRM record id (and, later, a non-authoritative group id). Never a credential, token or financial value in a URL |

"Module" here means a **supported, independently maintained custom extension that adds an Account detail action**. It is not a WIP financial module inside EspoCRM and it runs no WIP code in the EspoCRM runtime.

## 3. Identity semantics (three different identifiers)

1. **`crmAccountId`** is the immutable EspoCRM `Account.id`, an opaque 17-character id (VERIFIED: `account.id varchar(17)`, primary key). It is the canonical key for **new** WIP records and for the URL.
2. **`sfId`** is the Salesforce Account id held on the CRM Account (VERIFIED: `account.sf_id varchar(18)`, unique index `UNIQ_SF_ID`; entity metadata `sfId`, read-only after create). It is the **legacy join only**: WIP's existing `wip_company.salesforce_account_id` is matched to it exactly.
3. **`crmFirmGroupId`** is the CRM FirmGroup id of the Account's current group, which may be null. A link may carry it only as interface context; WIP confirms membership by reading the CRM.

**VERIFIED gap:** `main` declares **no** FirmGroup field, link or table (`custom/` has none, and the beta database has no FirmGroup table). The first milestone is therefore firm-level and must not depend on FirmGroup. A group view is a later increment that needs the real CRM entity first (CRM-D023, held under CRM-D034).

**Resolution.** `/crm/firm/{crmAccountId}` (proposed route; the WIP design records the exact spelling) → WIP reads the CRM Account by id → obtains name and `sfId` → for legacy cases only, matches `sfId` exactly to `wip_company.salesforce_account_id` → reads cases and observations from WIP. A CRM-native Account without a `sfId` is valid and shows "no legacy WIP mapping". There is no fuzzy name matching and no automatic firm creation. A nullable CRM-id crosswalk on WIP data is allowed later if its schema and migration safety are proven (WIP-WRITE-001).

## 4. Verified evidence

| # | Fact | Label | Source or method |
|---|---|---|---|
| E1 | CRM `main` is `e157bd51…`; FOUNDRY `main` is `84fedf0a…` (equal to the governing revision) | VERIFIED | GitHub API, 2026-11-18 |
| E2 | Account storage: table `account`; `id` varchar(17) PK; `name`; `deleted`; `sf_id` varchar(18) unique; `parent_id`. EspoCRM 10.0.12, MariaDB 11.4.13 | VERIFIED | `information_schema` on the beta database, schema only |
| E3 | There is no FirmGroup storage: only unrelated e-mail-folder group tables exist, and the repository defines no `firmGroup` | VERIFIED | `information_schema`; repository search at `e157bd51` |
| E4 | Identity coverage: the beta CRM holds 8,732 live Accounts, every one with an 18-character `sfId`; none is deleted | VERIFIED | counts only |
| E5 | Legacy mapping: WIP holds 8,941 companies and 11,776 cases. 8,730 companies and **11,758 cases (99.85%)** match a live CRM Account exactly on `sfId`; **18 cases** do not (they belong to companies that have no CRM Account; 211 WIP companies in all have none); no case matches a deleted Account; matching ignoring letter case gives the same count | VERIFIED | counts only, WIP and beta read-only sessions |
| E6 | Observations: 12,003 observation rows for 11,776 cases (every case has at least one); 223 cases have two or three; no case has two observations with the same date; every row is GBP | VERIFIED | counts only |
| E7 | EspoCRM 10.0.12 supports the planned action: the client reads `clientDefs.<scope>.menu.<view>` (`buttons`, `dropdown`, `actions`) and, for an item with `handler` and `actionFunction`, loads the module with `Espo.loader.require` and calls the function; `acl` and `aclScope` hide it from users without access. A `custom:` module name maps to `client/custom/src/<name>.js` | VERIFIED | the installed client bundle (`espo-main.js`), read as data; upstream reference <https://docs.espocrm.com/development/custom-buttons/> |
| E8 | A non-internal runtime configuration value reaches the browser through the settings payload (`getAllNonInternalData()`, then access filtering) | VERIFIED (source) | `Tools/App/SettingsService.php`. Whether a **non-admin** user receives an unregistered custom parameter is **INFERRED** and must be shown by the browser test |
| E9 | **Delivery gap.** `scripts/deploy_custom.sh` on `main` deploys only `custom/Espo/Custom`. The runtime mounts and backups already cover `client/custom`, but nothing in Git delivers browser code there, and `main` has no `client/` directory | VERIFIED | `deploy_custom.sh`, `scripts/lib/common.sh`, the Compose files |
| E10 | The unmerged candidate of `CRM-CLIENT-001R2` (`07bfaf1c01c633d6c45aba16d6587733a8c7f6a1`, draft PR #69, Auditor, Tester and DevSecOps PASS) implements that delivery (`deploy_custom.sh` +256/−21, tests, a browser harness). It is based on `9ea7b725…`, i.e. one commit ahead of and 20 behind current `main`; its operator browser assurance (S4) stopped on a network-subnet finding and was stood down on 2026-11-17 | VERIFIED | GitHub compare and PR record |
| E11 | Each CRM database runs on its own private Compose network and publishes no port. A host process can reach it through the container's network address (TCP handshake and server greeting observed for both `crm-dev` and `crm-beta`); that address is assigned by Docker at start-up | VERIFIED; stability across recreation INFERRED | host-side TCP probe, no login |
| E12 | A headless browser is available: Chrome for Testing 158.0.8127.18 launched in the digest-pinned image `mcr.microsoft.com/playwright/python@sha256:ce84a3d75a47e81657d2ec2c0a949e6e0ef790abdc32ce6819220a3df987ff9a` (no network, unprivileged, read-only file system, all capabilities dropped) and rendered a page. The Playwright Python package is **not** in that image; hash-locked Playwright 1.65.1 wheels exist in the operator store from the earlier chain | VERIFIED | local run, 2026-11-18 |
| E13 | A synthetic firm A with several cases and a synthetic firm B resolve to disjoint, correct WIP rows under the proposed SQL; a restricted read-only database user can run those queries and nothing else (column-level grants tested) | VERIFIED | disposable, network-less MariaDB 11.0.3 with synthetic rows only, destroyed afterwards; details in the private WIP record |
| E14 | The legacy WIP views are not safe for this product: `v_eric_wip_current_cases` hides closed cases and repeats a case whose latest two observations share a date, and `v_eric_wip_company_summary.current_wip_value` adds every period of open cases | VERIFIED | the same synthetic proof |
| E15 | Group membership on live WIP data cannot be derived from WIP's own group tables for this purpose: they are WIP-owned (CRM-D034) and are not used as authority | VERIFIED (by direction) | Issue #81 §3 |
| E16 | FOUNDRY copy on this host (`/srv/src/foundry/main`) is behind the governing revision; the cited standards are unchanged between them. It is protected and unchanged by this work | VERIFIED | GitHub compare |
| E17 | The CRM identity statements C1 and C2 (the WIP repository's architecture record, section 6) ran **as written** on a disposable, network-less MariaDB **11.4.13** container (the CRM's version) against a synthetic `account` table of the same column shape. A login holding `SELECT` on `id`, `name`, `sf_id`, `deleted` only, in a read-only session, got the expected rows, saw a deleted firm with `deleted = 1` and no row for an unknown id, and was refused another column, an update and `mysql.user`. The real CRM `account` table was not touched. The container was destroyed. The output is held in the Orchestrator's restricted evidence store (location not recorded in this public repository) | VERIFIED (synthetic table) |

## 5. The EspoCRM link extension (design)

**Scope of the customisation (CRM repository):**

| Path | Purpose |
|---|---|
| `custom/Espo/Custom/Resources/metadata/clientDefs/Account.json` | add `menu.detail.buttons`: one item `openWip`, label "Open WIP / Revenue", `handler` `custom:handlers/account-open-wip`, `actionFunction` `openWip`, `acl` `read`, `aclScope` `Account`; the existing `relationshipPanels` key is unchanged |
| `client/custom/src/handlers/account-open-wip.js` | AMD module. `openWip(data, event)` reads `this.view.model.id` and the runtime parameter `wipBaseUrl`, validates it, and opens `<wipBaseUrl>/crm/firm/<encodeURIComponent(id)>` in a new tab with `noopener`. If the parameter is missing or invalid, or the record has no id, it shows a short notification and navigates nowhere |
| `custom/Espo/Custom/Resources/i18n/en_US/Account.json` (or Global) | the label text |
| tests | a static policy test for the metadata and the module (no network, DOM or storage, no URL other than the configured base, no secret, no `eval`), a JavaScript handler test with a stub view, and the existing regression suites |

**Runtime configuration (not in Git):** `wipBaseUrl`, a non-secret URL kept in the environment's `data/config.php` and set by the operator per environment (CRM-D011: no host details in this repository). It carries no credential and is validated as `http(s)://host[:port][/path]` with no user-info, query or fragment.

**What the action must not do:** call WIP from the EspoCRM runtime (browser or server), load any WIP data, send a token, patch EspoCRM core, replace the Account page, or add a PHP class. Removing the customisation restores the original Account page (acceptance B).

**Access.** For the synthetic PoC the button is visible to users who may read Accounts. Live finance data needs a separate access decision (section 9, G-LIVE).

**Delivery prerequisite (E9, E10) is the one open implementation gate on the CRM side.** A browser handler can only reach the runtime if `client/custom/src` is delivered by script. Options, in order of preference:
1. **Adopt the delivery already built and reviewed in `CRM-CLIENT-001R2`** (candidate `07bfaf1c`): CGPT accepts its delivery mechanism, its S4 browser assurance is replaced by the D1 browser journey (which needs the same harness), and it is merged after reconciling its one-ahead/20-behind divergence by a re-validated rebase or merge. The link Work Order is then a small change on the merged base. No new Engineer execution is spent on delivery.
2. **A minimal, separate delivery change inside `CRM-WIP-LINK-001`:** more code to review, duplicates the candidate, and repeats the risk that produced three recoveries in that chain.

The draft Work Order `work-orders/CRM-WIP-LINK-001.md` is written for option 1 (its base is the merged delivery) and states what changes if CGPT chooses option 2. This is escalated in the consolidated report; it is not decided here.

## 6. Database topology for the WIP service

**Required flow:** browser → WIP web route; WIP backend → its own MariaDB (read for the PoC) and → the CRM MariaDB with a **separate, read-only** login that can select only what identity needs (`account(id, name, sf_id, deleted)`, later the FirmGroup columns). EspoCRM never connects to WIP and never proxies it.

| Option | Verdict |
|---|---|
| **A. A host process uses the CRM database container's network address** (verified reachable, E11) | **Used for the synthetic D1 proof on `crm-dev` only.** No CRM change is needed. The address is configuration, and it can change when the container is recreated |
| **B. Loopback-only host publication** of the CRM database port (127.0.0.1, one port per environment, off by default, environment-gated) | **Recommended for anything that outlives the PoC.** A bounded CRM Compose/operator change with its own Work Order (`CRM-DB-READ-001`, outline in the delivery sequence) and a restricted database user. Not an unrestricted LAN port |
| C. Attach the WIP service to the CRM Compose network | Rejected: couples the two deployments' lifecycles |
| D. A JSON API or a bridge | Rejected by direction (no new API, token service or WipLoader) |

The CRM database credential for WIP is a **new** read-only login created for this purpose by an authorised operator, kept in server-side runtime configuration and never in code, a URL or Git. No credential that was exposed in earlier history is reused (SEC-1 stays a separate responsibility).

## 7. Acceptance matrix (Issue #81 §6) and where each item is proved

| # | Criterion | Proved by |
|---|---|---|
| A | Correct identity: A shows A only; B never appears in A; legacy `sfId` match exact; a CRM-native firm without `sfId` shows the empty state | `WIP-CRM-CONTEXT-001` unit tests; operator integration run on disposable data; browser |
| B | The Account action appears and opens the right route; existing Account, Contacts and Enquiries unaffected; removing the extension restores the page | `CRM-WIP-LINK-001` tests; operator browser run (admin and non-admin) |
| C | WIP off: CRM still works; missing database gives a bounded WIP error page | operator browser run (stop the WIP service, reload the Account); `WIP-CRM-CONTEXT-001` error-path tests |
| D | Data fidelity: 0, 1, many cases; null versus zero; ties; unexpected status; provenance; no invented totals | `WIP-CRM-CONTEXT-001` and `WIP-UX-001` tests on a defined synthetic dataset |
| E | Group (later): peers, moves, hierarchy unaffected | later `WIP-GROUP-001`; needs the CRM FirmGroup entity first |
| F | Real browser click path from CRM to WIP and back; empty and error states; desktop legibility | operator-run browser journey (Chrome for Testing, E12) plus Matt's manual walkthrough |
| G | Change isolation: the CRM diff is limited to the action, its configuration, client asset and tests; WIP logic only in the WIP repository; independent deploy and rollback | diff allowlists in both Work Orders; the Auditor's path check |
| H | Data safety: synthetic data first; backup and restore and an operator gate before any live write; no direct SQL writes to CRM master | the operator plan; the WIP database user is read-only in D1 |
| I | No accidental exposure | WIP binds only to the approved internal interface; no public bind; finance pages are not cached; credentials server-side |
| J | Evidence: immutable commits, distinct PASS/FAIL per role on one unchanged candidate, browser evidence, GitHub records | the Work Order contracts |

## 8. Resolved routine decisions (not questions for Matt)

Recorded so a later agent need not re-ask; consequential ones are in `DECISIONS.md` (CRM-D035 to CRM-D042).

- The WIP application is **rebuilt** around the existing WIP database (option B of three: reuse, rebuild, clean slate). The evidence and reasoning are in the WIP repository's architecture record.
- The CRM-side action is a handler on the Account detail menu (E7), not a link field, a PHP loader or an extension package.
- Label: "Open WIP / Revenue". It opens in a new tab with `noopener`. Placement: the first button in the detail header.
- The CRM URL carries only the 17-character Account id.
- The WIP page labels values as source facts ("WIP value", "Fees invoiced", "Actual or revised yield (source field)", "Estimated yield") and shows no total and no "revenue".
- The first browser acceptance is run by the operator with Playwright and Chrome for Testing in the pinned image; specialists never run a browser (they have no network).

## 9. Genuine gates that remain (and why)

| Gate | Owner | Why it is genuine | Blocks |
|---|---|---|---|
| G-CLIENT: how browser code reaches the CRM runtime (section 5) | CGPT | It concerns a delivered, reviewed candidate and a merge decision; both options change what the CRM Work Order may touch | dispatch of `CRM-WIP-LINK-001` |
| G-ISOLATION: specialist access to sensitive history in the WIP repository (the earlier G10) | Helm (SEC-1) and CGPT | The WIP delivery checkout exposes the whole Git history to the sandbox; the isolation control is a security decision | dispatch of both WIP Work Orders |
| G-APPROVAL: exact-version approval of each Work Order and of the operator plan for synthetic environments | CGPT | Foundry Work Order contract | every dispatch |
| G-PRODUCT: Matt's acceptance of the exact Vision and Backlog versions | Matt | FOUNDRY product-record standard | Stage 1 closure |
| G-LIVE: pointing WIP at live data, or exposing finance records beyond the internal PoC | Matt | Issue #81 §8 | any live activation. **Not** part of D1 |
| G-SEC: sign-on and a common security layer | later (D4) | Not a PoC prerequisite | none now |

Everything else (framework, templating, CSS, route spelling, fixtures, helper names, ports for disposable services, parallel sequencing) is decided in the Work Orders and is not escalated.

## 10. Delivery sequence

The full sequence, dependencies and the autonomy plan are in [`docs/delivery/crm-module-sequencing.md`](../delivery/crm-module-sequencing.md) (section "Sequence from 2026-11-18"). In short: D0 documents (this record), then D1: `CRM-WIP-LINK-001` and `WIP-CRM-CONTEXT-001` in parallel once approved and unblocked, then `WIP-UX-001`, then the operator's end-to-end browser run on synthetic data and **one** demonstration to Matt.

## 11. Supersession register (nothing is deleted)

| Artifact | Identity | Status from 2026-11-18 |
|---|---|---|
| `WIP-API-001` v1.2 (WIP repository) | commit `83c80d352b192a13b1aaebc88ccb000f04c7087f`, file SHA-256 `83e62acab5c2a05f1463495b308c83f305479456a4dad2ae700be2df5a95efc4` | **SUPERSEDED by the Product Owner; not dispatchable.** The commit is not modified; a status record is added in the WIP repository |
| `CRM-WIP-INT-001R2` candidate | `167f2a9a…`, draft PR #75 | Superseded in implementation direction. Preserved; do not merge |
| `CRM-WIP-INT-001C` candidate | `1a1e8087…` (local to the PL repository; never pushed) | Superseded. Preserved |
| `CRM-WIP-INT-001D` candidate | `2f831256…`, draft PR #80 | Superseded; READY_FOR_CGPT was reported on 2026-11-17 and is withdrawn as a merge candidate. Preserved |
| `CRM-WIP-INT-001`, `001R`, `001R2`, `001C`, `001D` and `001-W` Work Orders | merged on `main` | Historic and immutable |
| PR #77 (`WIP-API-001` v1.0 in this repository) | draft | Stale. Close as superseded once CGPT confirms |
| `docs/architecture/crm-wip-integration-amendment.md` | CGPT-approved 2026-11-17 (SHA-256 `7838cf44…`) | Its principle (WIP independent, CRM owns identity) is retained; its mechanism (JSON API to a CRM panel) is superseded. Not edited |
| `docs/architecture/crm-wip-module-boundary.md` | candidate | The CRM-owned WIP module is superseded. Not edited |
| CRM-D021, D022, D025, D026, D027; D031's re-reading of D006; D033's mechanism | PROPOSED | Superseded in part by CRM-D035 |
| CRM-PBI-019, 020, 021, 022, 023, 025 | | Superseded (see the Backlog) |
| CRM-PBI-018, 024, 027 (FirmGroup) | | Held; the FirmGroup entity stays CRM-owned (CRM-D023, D034) |
| `CRM-CLIENT-001R2` candidate | `07bfaf1c…`, draft PR #69 | **Re-purposed as the proposed client-asset delivery base** (G-CLIENT); not superseded |

Execution counters of the earlier chains are history: this direction is a new product goal and **does not reset, reuse or rename any counter**. The new Work Orders have new identities and their own counters under the engine limit (CGPT sets the stricter cap in the dispatch record).

## 12. Risks

- **Finance data without sign-on.** The PoC WIP service has no authentication (sign-on is deferred, D4). Anyone who can reach its port and holds a CRM Account id could read that firm's figures. Controls for the PoC: synthetic data only, an approved internal interface, no public bind, no credential or finance data in a URL. Live data waits for G-LIVE.
- **Legacy data quality is visible, not corrected.** About 83% of observation rows carry a WIP value of exactly 0.00, status text has case variants and the literal text "NULL", and 18 cases belong to no CRM firm. The page shows the facts and labels them; it neither normalises nor totals them.
- **WIP's own operational problem (scheduled jobs failing since 2026-11-06) is separate** (`WIP-OPS-001`). Passing PoC tests prove nothing about live data freshness.
- **The host test interpreter** (Python 3.9, apt auto-installed) is a recorded risk for the WIP Work Orders, not remedied here.
