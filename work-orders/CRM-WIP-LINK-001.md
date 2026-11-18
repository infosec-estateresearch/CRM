WO: CRM-WIP-LINK-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: 07bfaf1c01c633d6c45aba16d6587733a8c7f6a1
KNOWN_COMMIT: 07bfaf1c01c633d6c45aba16d6587733a8c7f6a1

# CRM-WIP-LINK-001: "Open WIP / Revenue" action on the Account page (link only)

- **Version:** v1.0 **DRAFT**, 2026-11-18. **Not approved. No dispatch.** Dispatch needs a CGPT exact-version approval naming this path and the commit that contains it, recorded on the Issue below after that commit exists (the approval is recorded outside this text, so this text cannot show it). The Orchestrator's dispatch record (`APPROVAL.md`) carries the cap in section 0.
- **Issue (status, evidence, approval, escalation):** https://github.com/infosec-estateresearch/CRM/issues/82. **Product direction:** https://github.com/infosec-estateresearch/CRM/issues/81 (Product Owner and Architect, 2026-11-18). **Architecture:** `docs/architecture/2026-11-18-standalone-wip-poc.md` (PROPOSED in the same commit).
- **Parent PBI:** `CRM-PBI-030` (Account to WIP link) and, for the delivery base, `CRM-PBI-031` (client-asset delivery), in `PRODUCT-BACKLOG.md` (PROPOSED). Decisions: CRM-D035, CRM-D037, CRM-D039, CRM-D040 (PROPOSED).
- **Governing FOUNDRY:** `maff0000/foundry@84fedf0a74017237aa1bd650d8560350c91c7f0e`: `standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md`. **Engine:** ForgeV2 plugin 0.3.0, pinned `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82` (re-verify at dispatch). **PIM:** `PROJECT-INITIATION-MANDATE.md` with its 2026-11-18 amendment.
- **Prepared by:** Rogue (Orchestrator). Preparation only.
- **This WO depends on one open Architect decision (G-CLIENT, architecture record section 5).** It is written for **option 1**: the delivery of `client/custom/src` already built in the `CRM-CLIENT-001R2` candidate is the base. If CGPT instead chooses option 2 (delivery inside this WO), this WO must be revised and re-approved before dispatch, because the allowlist, the tests and the base change.
- **Header note (base).** `BASE` and `KNOWN_COMMIT` are the commit id of the `CRM-CLIENT-001R2` candidate (`07bfaf1c…`, one commit on the PL's local `main` `6e176698…`; tree `201c974e49b5069a802f2ed608f4f64165950966`; 14 files changed against `6e176698`). The engine resolves `BASE` with `git rev-parse --verify <base>^{commit}` in the PL repository, where the commit exists (verified 2026-11-18). That candidate is delivered and preserved (draft PR #69, do not merge from this WO). There is **no `BROWSER: yes` line**: the sandboxed Tester has no network and no browser, so the real-browser proof is the operator's annex (section 8) and is not a specialist's claim.

## 0. Chain and budget

| Item | Value |
|---|---|
| Identity and counters | A **new** Work Order for a new product goal. It does not continue, rename or reset the `CRM-WIP-INT-001` chain (whose Engineer budget of five is spent) or `CRM-CLIENT-001R2`. Its own ledger starts at 0/0/0/0 |
| **Engineer budget** | **At most 2** executions, held by the dispatch record (the engine's constant limit is 4 per specialist and cannot be lowered). A second execution is allowed only to correct a reviewer FAIL or FINDINGS on the first. Any further failure ends the WO as BLOCKED and returns to CGPT; **no automatic replacement or recovery WO** |
| Reviewers | Auditor, Tester and DevSecOps assess the **exact final candidate**; each returns PASS on the same unchanged commit. Any Engineer change restarts the sequence |
| Operator assurance | Annex (section 8): the Orchestrator's real-browser run. It is evidence for CGPT and Matt, not a specialist execution |

## 1. Outcome

On an EspoCRM Account's detail page, a user who may read Accounts sees an **Open WIP / Revenue** button. Clicking it opens `<wipBaseUrl>/crm/firm/<Account id>` in a new browser tab. Nothing else changes: no WIP data, SQL, API, token, PHP, entity, field, scope, ACL, layout or route enters the CRM; removing the change restores the original page. The independent WIP application (a separate repository and Work Order, `WIP-CRM-CONTEXT-001`) serves that route. The candidate stays a draft: no merge, no deployment.

## 2. Repository, workspace and what must stay untouched

| Item | Verified value (2026-11-18) |
|---|---|
| Repository | `infosec-estateresearch/CRM` (public). GitHub `main` `e157bd51429e2764a94cecaf85a06bf707bd876f` (documents only since `6e176698`) |
| Execution host and paths | `DOCKER1:/srv/CRM/main` (the PL's checkout, clean, local `main` `6e176698…`), worktrees `/srv/CRM/worktrees`; the specialist branch is `forge/CRM-WIP-LINK-001` in its own worktree |
| Base | commit `07bfaf1c01c633d6c45aba16d6587733a8c7f6a1` (see the header note) |
| Specialist limits | The sandbox has no network, no Docker, no browser, no Node.js, and cannot read the runtime directories. Unit tests are Python (`python3 -m unittest discover -s tests/unit`) |
| Protected | `/srv/forgev2`, `/srv/src/foundry`, every ledger, the runtime directories, the candidates `167f2a9a…`, `1a1e8087…`, `2f831256…`, branches `forge/CRM-WIP-INT-*` and `forge/CRM-CLIENT-001R2`, draft PRs #69, #75, #80 |

## 3. Required work (the allowlist; everything else is out of scope)

| Path | Change |
|---|---|
| `client/custom/src/handlers/account-open-wip.js` | **new.** An AMD module (`define([...], function (...) {...})`, no `import` or `export`) returning a class whose constructor takes the view and which has `openWip()`. Behaviour in section 3.1 |
| `custom/Espo/Custom/Resources/metadata/clientDefs/Account.json` | add one top-level key `menu`: `{"detail": {"buttons": [ <one item> ]}}`. The item is exactly: `name` `openWip`, `label` or `text` "Open WIP / Revenue", `handler` `custom:handlers/account-open-wip`, `actionFunction` `openWip`, `acl` `read`, `aclScope` `Account`, `style` `default`, optionally `iconClass`. **No** `link`, `url` or `data` that carries a URL. The existing `relationshipPanels` key is byte-identical |
| `custom/Espo/Custom/Resources/i18n/en_US/Account.json` | only if a label key is used: add the single label; no existing key changes |
| `tests/unit/test_wip_link.py` | **new.** Section 5 |
| `tests/unit/test_client_custom.py` | **edit, limited to what the new file makes untrue** (these tests were written for a tree with only the canary and no Account change). Allowed: the two directory-listing assertions (`src` may now contain `crm` and `handlers`; `handlers` contains exactly `account-open-wip.js`); the test that asserts `custom`, `config` and `deploy` are unchanged from `6e176698` (its path set may exclude exactly the two allowlisted `custom/` files above); the unreferenced-canary test keeps asserting that nothing references `release-canary` or `custom:crm`. No rule in the policy table is relaxed, no test is removed or skipped |
| `docs/WIP-LINK.md` | **new.** Operator note: the `wipBaseUrl` runtime parameter (what, where, how to set it per environment, with placeholders only), the verification steps, and rollback (deploy the base). No address, hostname or credential |

**Everything else is unchanged**, including `scripts/`, `deploy/`, `config/`, `security/`, `docs/BUILD.md`, the other tests and every file under `.forge/`.

### 3.1 Handler behaviour (the contract the Engineer implements and the operator's browser run checks)

1. **Inputs:** the record id is `this.view.model.id`; the base is `this.view.getConfig().get('wipBaseUrl')`.
2. **Id:** a non-empty string of letters and digits only (EspoCRM ids). Anything else: warn and stop.
3. **Base:** must parse as an absolute URL with protocol `http:` or `https:`, a host, **no user-info, no query, no fragment**. A path prefix is allowed. A single trailing `/` is ignored. Anything else, or a missing value: show the warning "The WIP link is not configured." and stop. It never falls back to a default address and never invents a host.
4. **Target:** `<base without trailing slash>/crm/firm/<encodeURIComponent(id)>`. It opens in a new tab with `noopener` (and `noreferrer`). No other parameter is added in this WO.
5. **Failure isolation:** the handler makes no network request and reads no storage; an exception is caught and shown as a warning. The Account page must still work if the handler fails.
6. **Policy:** the existing client-code rules apply unchanged (no remote URL literal, `eval`, `new Function`, `document.write`, `innerHTML` assignment, absolute-URL fetch or open, storage API, `import` or `export`).

Operator behaviour table (the browser run asserts every row):

| `wipBaseUrl` | id | Result |
|---|---|---|
| `http://wip.example:8310` | `ID1` | opens `http://wip.example:8310/crm/firm/ID1` |
| `https://wip.example/app/` | `ID1` | opens `https://wip.example/app/crm/firm/ID1` |
| missing, empty, or not a string | any | warning; nothing opens |
| `javascript:...`, `data:...`, `ftp:...` | any | warning; nothing opens |
| contains `user:pass@`, `?x=1` or `#x` | any | warning; nothing opens |
| valid | empty or not alphanumeric | warning; nothing opens |

## 4. Exclusions and protected items

No PHP file; no entity, field, link, scope, ACL, role, layout or route change; no change to `Account.json` entity metadata; no `client/custom/modules`; no change to `scripts/`, `deploy/`, compose files or the release tooling; no WIP loader, API call, token, database access or WIP table; no new dependency, image, CDN or vendored file; no change to the candidate `07bfaf1c` files other than the limited test edits above; no change to ForgeV2, Foundry, the host, `crm-dev`, `crm-beta`, WIP or Salesforce. No deployment or merge by any specialist.

## 5. Verification

- **Engineer (mechanical):** the whole unit suite on the base (report the count before: the candidate recorded 643 tests) and after; the new `tests/unit/test_wip_link.py`; the client-policy tests of `test_client_custom.py` on the real tree.
- **`test_wip_link.py` must prove, without Node, a browser or a network:** (a) `clientDefs/Account.json` parses, keeps `relationshipPanels` byte-identical (compare to the base blob) and the `menu` item has exactly the keys of section 3, with `handler` resolving to the new file by the `custom:` rule; (b) the diff touches no other `custom/` file and adds no PHP; (c) the handler passes the client policy and contains the required elements: `encodeURIComponent`, a protocol check for `http:` and `https:`, rejection of user-info, query and fragment, `noopener`, no other host; (d) a **table-driven reference model** of the section 3.1 rules written in Python and checked against the handler's constants and branch structure (static), so that a weakened check (for example dropping the user-info test) is detected; (e) removing the metadata item makes (a) fail (a non-vacuity proof).
- **Auditor:** conformance to this WO and the allowlist, the limited test edits, no scope creep. **Tester:** the new tests are real (the Tester breaks each rule and shows a test fail), the whole suite, and states plainly that **JavaScript behaviour is not executed in the sandbox**; the behaviour table is verified by the operator annex. **DevSecOps:** no URL, host or credential in the diff; open-redirect and scheme handling (javascript/data), `noopener`, no storage, no network; no dependency; gitleaks 0 findings.
- A FINDINGS verdict from any reviewer returns to the Engineer while the cap allows; it is never presented as PASS.

## 6. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| AC1 | The diff against `07bfaf1c…` is exactly the allowlist (section 3); `test_client_custom.py` is changed only as allowed; no other file differs | `git diff --stat`, Auditor, Orchestrator source-identity check |
| AC2 | `Account.json` keeps `relationshipPanels` byte-identical and adds exactly the one `menu` item of section 3 | `test_wip_link.py`, Auditor |
| AC3 | The handler meets section 3.1 and the client policy | static tests, Tester, DevSecOps |
| AC4 | No PHP, entity, field, scope, ACL, layout, route, script, deploy, compose or dependency change | Auditor, DevSecOps |
| AC5 | The whole unit suite passes with 0 failures and counts before and after are reported; no new skip | delivery record, Orchestrator re-run |
| AC6 | Auditor, Tester and DevSecOps return **PASS on the same unchanged candidate commit**; the Tester returns no FINDINGS | ledger, delivery record |
| AC7 | gitleaks 0 findings; no host, address or credential in the diff | scan |
| AC8 | **Orchestrator independent checks:** a fresh re-run from an export of the final candidate; a source-identity check against the base; a mutation sweep of the handler's rules (each of: drop the protocol check, drop the user-info check, drop the query or fragment check, drop `encodeURIComponent`, drop `noopener`, hard-code a host, add a fallback host) in which every mutation is **caught** or is reported as an equivalent | Orchestrator report |
| AC9 | **Operator browser assurance (section 8)** passes on the final candidate deployed to `crm-dev` with synthetic data | operator evidence package |
| AC10 | No merge, no deployment, no `crm-beta` or live change by any specialist; earlier candidates, branches, ledgers and PRs unchanged | state record |

## 7. Gates

| Gate | Requirement | State |
|---|---|---|
| G1 | CGPT exact-version approval of this WO | open |
| G2 | **G-CLIENT:** CGPT accepts the `CRM-CLIENT-001R2` candidate `07bfaf1c…` as the delivery base (option 1), or revises this WO (option 2) | open |
| G3 | Budget: the dispatch record states at most 2 Engineer executions and no replacement WO | at dispatch |
| G4 | Exact-base gate EB1 to EB8 (below) | open |

**Exact-base gate (read-only, `GIT_OPTIONAL_LOCKS=0`, run as the PL account).** EB1: in the PL repository `07bfaf1c01c633d6c45aba16d6587733a8c7f6a1` is a commit with tree `201c974e49b5069a802f2ed608f4f64165950966` and the single parent `6e1766980e24d781d498727d4fe5db43cdeadbb7`; blob ids at the base: `custom/Espo/Custom/Resources/metadata/clientDefs/Account.json` `40baa67e04c4…`, `custom/Espo/Custom/Resources/i18n/en_US/Account.json` `d3e201c088e2…`, `tests/unit/test_client_custom.py` `2b65738474f8…`, `scripts/deploy_custom.sh` `292d4b848ce8…`, `client/custom/src/crm/release-canary.js` `06dce13d8e60…` (the Orchestrator records the full ids at dispatch). EB2: this WO's documents are merged at an exact commit `M` and GitHub `main` has advanced by documents only. EB3: the PL's local `main` equals `6e1766980e24d781d498727d4fe5db43cdeadbb7`, clean, canonical origin, no `url.*` rewrite. EB4: no `forge/CRM-WIP-LINK-001` branch, worktree or scratch directory exists, and the ledger for this identity does not exist; the ledgers of every earlier WO are unchanged. EB5: the engine installation and plugin version are as pinned and protected. EB6: the exact approved WO file is staged for the PL with its dispatch record, and every reference file is readable as `forgev2-pl` inside the EB8 sandbox. EB7: the stage-1 knowledge check: the Orchestrator re-greps the tests that enumerate `client/custom`, `custom` metadata or the Account clientDefs and finds no pinned surface other than those already allowlisted. EB8: a read test as `forgev2-pl` in a sandbox that hides the PL home with no network.

## 8. Annex: operator real-browser assurance (Orchestrator-run; zero specialist executions)

Run after the candidate is DELIVERED and its three PASS verdicts are recorded, on **`crm-dev` with synthetic data only** and the independent WIP application serving synthetic data (see `WIP-CRM-CONTEXT-001`). It is the evidence for acceptance criteria A, B, C, F and G of Issue #81 for the CRM side.

1. **Prepare (operator, approved with this WO):** deploy the candidate to `crm-dev` with the established script (`scripts/deploy_custom.sh dev`, which on the base also delivers `client/custom/src` and advances the application timestamp); set `wipBaseUrl` in the `crm-dev` runtime configuration to the synthetic WIP service address; create synthetic firm A and firm B through the REST API (clearly synthetic names; firm A with a synthetic legacy key matching the WIP synthetic dataset, firm B likewise; and a third CRM-native firm with no legacy key); create one non-admin user with Account read.
2. **Browser:** Chrome for Testing in the digest-pinned Playwright image, run as an unprivileged user on a per-run network whose subnet is checked against every existing Docker network first (the earlier S4 stop was a subnet overlap). The run's access to the CRM is admitted only for the run (never a standing change to the allow-list) and removed after.
3. **Journeys:** J1 (admin) open firm A, click the button, assert a new tab at exactly `<wipBaseUrl>/crm/firm/<A id>`, the WIP page shows firm A and not B, and the "back to CRM" link returns to firm A; J2 the same for firm B and the CRM-native firm; J3 a non-admin user sees the button and it opens the right route (and, if the runtime parameter is not delivered to non-admin users, **this is the failing case that must be reported**: E8); J4 every row of the behaviour table, by setting `wipBaseUrl` to each value in turn (each change followed by a reload); J5 stop the WIP service and reload the Account: the page, relationships and Enquiries panel still work and clicking the button leaves the CRM page unharmed; J6 deploy the base (the customisation removed): the button is gone and the page matches the earlier screenshot; J7 console: no errors from the customisation; network: no request from the Account page to the WIP host and no credential in any URL.
4. **Evidence:** screenshots, a request log, the console log, the exact candidate and runtime commit ids, and the browser identity, assembled as the earlier annex's package (sanitised: no address, hostname or customer name in anything committed). A skipped or inconclusive journey is **not** a pass.

## 9. Execution limits, stop conditions, communications

- **Limits:** section 0. Auditor, Tester and DevSecOps counters start at 0; the engine limit 4 applies.
- **Stop (BLOCKED, reported, never worked around):** any change outside the allowlist; a need for PHP, a database, the network, Node or a browser; a test that cannot be made non-vacuous without relaxing a policy rule; the engine refusing a commit id as `BASE`; a failed entry gate; any finding that cannot be reported safely. No firewall rules. No change to ForgeV2, Foundry or the host.
- **Communications:** Issue https://github.com/infosec-estateresearch/CRM/issues/82. PL record `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-WIP-LINK-001/` and, on the candidate branch, `.forge/CRM-WIP-LINK-001/`; per-specialist output under `dispatch/`. Mode: MANUAL fallback (CGPT's decisions are relayed by Matt; the Orchestrator records them on the Issue). Escalation: PL to Orchestrator; Orchestrator to CGPT (architecture) and Matt (product, permission, material risk).
- **Completion report (PL):** outcome, changed paths, starting and final commit ids, acceptance criteria with results, the three verdicts and the candidate each assessed, the non-vacuity evidence, counts, deviations and remaining risks. If delivery fails, return BLOCKED with evidence; **do not create a replacement WO.**
