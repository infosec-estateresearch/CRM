WO: CRM-WIP-LINK-001R3
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: cbfeca7668374a8c02945b21930845394501fad6
KNOWN_COMMIT: cbfeca7668374a8c02945b21930845394501fad6

# CRM-WIP-LINK-001R3: corrective successor of CRM-WIP-LINK-001R2 (the deploy script's stored-timestamp read, and one recovery message)

- **Version:** v1.0 **DRAFT**, 2026-11-23. **Not approved. No dispatch.** Dispatch needs a CGPT governance ruling that permits this successor (section 0) **and** an exact-version approval naming this path and the commit that contains it, recorded on the Issue below after that commit exists (the approval is recorded outside this text, so this text cannot show it).
- **Issue (status, evidence, approval, escalation):** https://github.com/infosec-estateresearch/CRM/issues/85 (the same chain as `CRM-WIP-LINK-001R2`). **Finding and evidence:** Issue #85, the Orchestrator's addendum of 2026-11-23 (comment 7105551032). **Original Work Order and Issue:** `CRM-WIP-LINK-001` v1.1, Issue #82. **Product direction:** Issue #81.
- **Governing FOUNDRY:** `maff0000/foundry@84fedf0a74017237aa1bd650d8560350c91c7f0e` (`standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md`). **Engine:** ForgeV2 plugin 0.3.0, pinned `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, unmodified (re-verified at dispatch).
- **Prepared by:** Rogue (Orchestrator). Preparation only.
- **Why a new identity exists.** The engine closes a ledger as `DELIVERED` and refuses every further dispatch on it. `CRM-WIP-LINK-001` and `CRM-WIP-LINK-001R2` are terminal, **stay closed and unchanged**, and are not reopened, edited or re-marked. `CRM-WIP-LINK-001R2` states that there is **no further successor without a new governance ruling**; this Work Order therefore exists only if CGPT rules that a defect found after delivery, by an operator check on a real runtime, justifies one more corrective unit. It is not a new budget (section 0), not a statement that the delivered candidates passed their assurance in this respect, and not a precedent.

## 0. Chain, provenance and cumulative budget (binding across all three ledgers)

| Item | Value |
|---|---|
| Original Work Order | `CRM-WIP-LINK-001` v1.1 (Issue #82). Candidate `3a5e7cd13bb31bd84c7f21ff4c9a5dc42ee40aea`. Ledger terminal **DELIVERED**, project key `3b6369e4f8e78d83`, closed and unchanged. Executions: Engineer **1**, Auditor **1**, Tester **1**, DevSecOps **1** |
| Corrective Work Order | `CRM-WIP-LINK-001R2` v1.0, merged documents-only as #86. Candidate `cbfeca7668374a8c02945b21930845394501fad6` (parent `3a5e7cd1…`, tree `1ea73494069eabae565604456f23788c222bb8a3`, three paths: `docs/WIP-LINK.md`, `tests/unit/test_client_delivery.py`, `tests/unit/test_wip_link.py`). Ledger terminal **DELIVERED** (three explicit PASS verdicts on one unchanged candidate), closed and unchanged. Delivery tip `9005286eefb99ca76ae70b96ce7e462eabdf49f8` on branch `forge/CRM-WIP-LINK-001R2`, **draft PR #87: not merge-approved, not touched by this Work Order**. Executions: Engineer **1**, Auditor **1**, Tester **1**, DevSecOps **1** |
| Cumulative before this Work Order | **Engineer 2, Auditor 2, Tester 2, DevSecOps 2** |
| **Engineer budget (this WO)** | **At most 1** execution, so the cumulative total is **at most 3** (the originally approved cap for the chain). A FINDINGS or FAIL from a reviewer therefore cannot be corrected inside this Work Order: the result is then BLOCKED or ESCALATED to CGPT with the evidence, and **no replacement Work Order** is created. If CGPT prefers a margin it states a different Engineer cap in the approval; the engine's limit of 4 per specialist is not exceeded either way |
| **Reviewer budget (this WO)** | Auditor, Tester and DevSecOps **at most 2 each**, so the cumulative total is **at most 4 each** (the engine limit). Each assesses the **exact final candidate** |
| Counters | The new engine ledger technically starts at 0/0/0/0. **That is not a fresh budget.** The dispatch record and Issue #85 carry the cumulative counters |
| PASS | Explicit **PASS from each of Auditor, Tester and DevSecOps on one unchanged final candidate**, recorded in the ledger. `FINDINGS` is not a PASS and is never recorded as advisory: it is returned or escalated. The ledger is closed `DELIVERED` only on three current PASS verdicts |

## 1. Outcome

`scripts/deploy_custom.sh` completes a real deployment on the EspoCRM build this repository targets (10.0.12) and keeps every behaviour the delivered candidates have. Nothing else changes.

**The defect (found by the Orchestrator on 2026-11-23, evidence on Issue #85).** After `update-app-timestamp` the script requires the stored `appTimestamp` to strictly increase (`read_app_timestamp`, before and after). It reads the value from `data/config.php` merged with `data/config-internal.php`. On EspoCRM 10.0.12 the application stores `appTimestamp` and `cacheTimestamp` in **`data/state.php`** (the image's own `InternalConfigHelper` lists them as state parameters), so the script reads **0 before and 0 after** and every real deployment ends at step 27 (`appTimestamp did not advance (0 -> 0)`) and is rolled back. The failure is safe (both trees restored, previous handler served, failed trees kept) but the deployment can never succeed. The byte-identical script is in both `3a5e7cd1…` and `cbfeca76…`. The unit tests did not catch it because the fake `docker` answers any call whose text contains `appTimestamp` with a counter, and the test asserts the literal command text: the PHP expression is never evaluated against a configuration layout.

**Secondary (minor).** If `fail_step`'s recovery has already restarted the stack (`compose up` succeeded) and a later cache step then fails, the script prints `RECOVERY FAILED: crm-app and crm-daemon are left stopped` while the services are running.

## 2. Repository, workspace, base and what must stay untouched

| Item | Value |
|---|---|
| Repository | `infosec-estateresearch/CRM` (public) |
| Execution host and paths | `DOCKER1:/srv/CRM/main` (the PL's checkout), worktrees `/srv/CRM/worktrees`; the specialist branch is `forge/CRM-WIP-LINK-001R3` in its own worktree |
| **Base** | **The clean R2 implementation candidate `cbfeca7668374a8c02945b21930845394501fad6`**, passed as both `BASE` and `KNOWN_COMMIT` (preferred to the delivery tip `9005286e…` so that generated `.forge/CRM-WIP-LINK-001R2` records are not inherited as application content). Whether the engine's own `forge-start` accepts it is **gate G3, proved at dispatch** on a scratch copy of the PL checkout, as it was for R2; nothing in this text asserts it beforehand |
| Baseline | The whole unit suite on the candidate: **619 tests, OK** (Orchestrator re-run, 2026-11-23). Re-run at dispatch |
| Specialist limits | The sandbox has no network, no Docker, no browser, no Node.js, and no EspoCRM; PHP is **not** assumed. Unit tests are Python (`python3 -m unittest discover -s tests/unit`) |
| Protected | `/srv/forgev2`, `/srv/src/foundry`, every ledger (including those of `CRM-WIP-LINK-001` and `CRM-WIP-LINK-001R2`), the branches `forge/CRM-WIP-LINK-001` and `forge/CRM-WIP-LINK-001R2`, draft PRs #84 and #87, the live runtime directories, every earlier candidate and PR |

## 3. Required work (the allowlist; everything else is out of scope)

| Path | Change |
|---|---|
| `scripts/deploy_custom.sh` | **edit, two places only.** (a) `read_app_timestamp` also reads `data/state.php` when it is a regular file, merged after the two configuration files, so the value is found wherever the application stores it. Reference form (proved on a real runtime by the Orchestrator): add `$c = is_file("data/state.php") ? include "data/state.php" : [];` and `array_merge($a, $b, $c)`. Any equivalent that reads the value the application itself uses is allowed. It stays fail-closed exactly as now: an unreadable or non-numeric value is `cannot read appTimestamp`, and a value that does not strictly increase after the one retry is `appTimestamp did not advance`. (b) The `RECOVERY FAILED` message of `fail_step` no longer says the services are left stopped when `compose up` had succeeded; it says the previous trees were restored, the services were started and a cache step failed. The case where `compose up` itself failed keeps its present wording. Every exit code, step name, call sequence and other message is unchanged |
| `tests/unit/test_scripts.py` | **edit, narrow.** (1) The fake `docker` answers the stored-timestamp read from a fixture data directory laid out as EspoCRM 10.0.12 lays it out (`appTimestamp` only in `state.php`; none in `config.php` or `config-internal.php`), taking **only the files the expression actually includes**, and `update-app-timestamp` writes the new value to `state.php`, so reading the wrong files yields 0. PHP is not required: the fake derives the included file names from the expression text. (2) The `READ_TS` constant follows the script's new expression. (3) The scenarios of section 5 and the two positive controls. No existing test is removed, skipped, renamed or weakened; every changed existing line is listed in the report with the reason |
| `docs/WIP-LINK.md` | **edit, one sentence:** the timestamp check names the file the value is read from (`data/state.php` beside the two configuration files). Nothing else |

**Everything else is byte-identical to the candidate `cbfeca76…`**, in particular `client/custom/src/handlers/account-open-wip.js`, `custom/Espo/Custom/Resources/metadata/clientDefs/Account.json`, `tests/unit/test_client_delivery.py`, `tests/unit/test_wip_link.py`, all other scripts, `deploy/`, compose files and every other file. No new dependency, package, image or vendored file.

## 4. Exclusions and protected items

No functionality, entity, field, scope, ACL, layout, route, PHP file, WIP loader, API call, token, database access or compose change; no change to the handler or the Account metadata; no change to scripts other than the two places of section 3; no `deploy/`, `backup.sh`, `restore.sh`, `up.sh` or release tooling change; no new dependency, image, CDN or vendored file; no refactor; no change to ForgeV2, Foundry, the host, `crm-dev`, `crm-beta`, WIP or Salesforce. No firewall rules. No merge or deployment by any specialist. Branches `forge/CRM-WIP-LINK-001` and `forge/CRM-WIP-LINK-001R2` and PRs #84 and #87 are not modified.

## 5. Verification

- **Tests that must exist and fail on the defect.** On the unmodified candidate's script the new scenarios fail (the 10.0.12 layout reads 0). Scenarios: (i) 10.0.12 layout: the deployment completes, the stored value strictly increases, exit 0; (ii) legacy layout (value only in `config-internal.php`): still completes (the fix is not a regression); (iii) value in no file: fails closed at step 27 as before, trees restored; (iv) the recovery case of section 1 (secondary): `compose up` succeeds, a later cache step fails: the message does not claim the stack is stopped; (v) `compose up` itself fails: the present wording. Positive controls: (i) and (ii).
- **Mutation list (the Orchestrator's sweep and the specialists' proofs).** Each is an exact one-place edit of `scripts/deploy_custom.sh` that the tests must catch: **N01** the state file is not read (the defect itself); **N02** the state file name is wrong (`state-internal.php`); **N03** the message of section 3(b) is restored to the old wording after a successful `compose up`. The 16 mutations of the R2 sweep (marker guard `M05` to `M05d`, handler rules, metadata, `M07` and the rest) are re-run in full on the final candidate: every mutation is caught or reported as an equivalent, and the sweep fails on any mutation that could not be applied.
- **Engineer (mechanical):** the whole unit suite before and after (counts, no new skip, nothing removed), the new scenarios, the revert-and-rerun proof for N01 to N03 naming the catching test for each, every edit confined to section 3, every changed existing test line listed.
- **Auditor:** conformance to this Work Order and the allowlist; the diff against `cbfeca76…` is only the allowlisted paths and the byte-identical items are unchanged (blob ids); the two script edits are exactly those of section 3; the fake does not weaken any existing assertion. **Explicit verdict PASS or FINDINGS.**
- **Tester:** the new tests are real (the Tester applies N01 to N03 and the R2 mutations it can and shows a test fail for each; the positive controls pass); states plainly that **PHP and JavaScript are not executed in the sandbox**, so the PHP expression itself is proved by the Orchestrator's real-runtime run (AC7), not by the unit tests.
- **DevSecOps:** no URL, host or credential in the diff; no new write path; the marker and path checks are unchanged; no dependency; gitleaks 0 findings.

## 6. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| R1 | The diff against `cbfeca7668374a8c02945b21930845394501fad6` is exactly the allowlist (section 3); every other file is byte-identical (blob ids recorded); the handler and the Account metadata are unchanged | `git diff --stat`, Auditor, Orchestrator source-identity check |
| R2 | The scenarios and controls of section 5 exist; the layout-faithful fake takes only the included files; the tests fail on the unmodified script and on N01 to N03 | tests, revert-and-rerun, Tester, Orchestrator sweep |
| R3 | The recovery message of section 3(b) is accurate in both cases and every other message, exit code and call sequence is unchanged | tests, Auditor |
| R4 | The whole unit suite passes with 0 failures; counts before and after are reported; no new skip; nothing removed or weakened | delivery record, Orchestrator re-run |
| R5 | **Auditor, Tester and DevSecOps return PASS on the same unchanged candidate commit** | ledger, delivery record |
| R6 | gitleaks 0 findings; no host, address or credential in the diff | scan |
| R7 | **Orchestrator independent checks:** a fresh run of the whole suite from an export of the final candidate; the source-identity check; the full mutation sweep (N01 to N03 and the R2 sixteen); **and the real-runtime script journeys of section 8 on the unmodified final candidate** (no diagnostic edit of any kind) | Orchestrator report and evidence archive |
| R8 | The ledgers and records of `CRM-WIP-LINK-001` and `CRM-WIP-LINK-001R2`, their branches and PRs #84 and #87 are byte-identical before and after; no merge or deployment; the cumulative counters are recorded | state record (hashes before and after) |

## 7. Gates

| Gate | Requirement | State |
|---|---|---|
| G1 | CGPT governance ruling permitting this successor **and** exact-version approval of this Work Order at an immutable commit (path, commit, SHA-256, base, ledger continuity, allowlist, budget) | open |
| G2 | Budget: the dispatch record states Engineer at most 1 and each reviewer at most 2 for this Work Order (or the cap CGPT states), the cumulative totals of section 0, and the PASS rule | at dispatch |
| G3 | Exact base: in the PL repository `cbfeca76…` resolves to a commit whose parent is `3a5e7cd1…` and whose tree is `1ea73494069eabae565604456f23788c222bb8a3`; local `main` clean with canonical origin and no `url.*` rewrite, `core.hooksPath`, `core.fsmonitor` or `include`; GitHub `main` differs from the PL's `main` by documents only; no `forge/CRM-WIP-LINK-001R3` branch, worktree, scratch directory, ledger or record exists; the earlier ledgers recorded by hash; engine and plugin as pinned and clean; the engine's `forge-start` accepts the base (the proof is run on a scratch copy); the suite on the base gives 619 tests, OK. Git on the PL checkouts is read with `GIT_OPTIONAL_LOCKS=0` and never fetched, pulled or reset by the Orchestrator | at dispatch |
| G4 | **Execution isolation:** the single PL session is launched only through the hardened private mount and PID namespace launcher with a clean allowlisted environment and working directory `/`; immediately before dispatch the in-context denial of every known sensitive host path, a positive synthetic control and a live `/proc` sentinel check are run and recorded; any adverse result blocks dispatch with no execution spent | at dispatch |
| G5 | Sequential sessions: no other `claude` session under the PL account is in flight and no other Work Order is dispatched for this repository | at dispatch |
| G6 | The Work Order and the dispatch record given to the PL are staged read-only; the Work Order is byte-identical to the approved blob | at dispatch |

## 8. Annex: real-runtime script journeys (Orchestrator-run; zero specialist executions)

After DELIVERED, the Orchestrator re-runs, on a disposable runtime of the same EspoCRM build (own project name, own internal network, synthetic data only) and on the **unmodified** final candidate, the script journeys of 2026-11-23: the real `scripts/up.sh`, `scripts/deploy_custom.sh` and `scripts/backup.sh` run through a shim that allows only `docker compose`, renames the project and can inject one failure at a named step. **D1** first install (exit 0, handler served byte for byte, marker written, stored timestamp strictly advanced); **D2** update with a changed label (new bytes served, timestamp advanced, previous trees cleaned up); **D3** rollback with a repository that has no `client/custom/src`, then redeploy; **D4** a failure injected once at `rebuild` (exit 26) and once at `update-app-timestamp` (exit 27): `RECOVERED`, both trees byte-identical to before, previous handler served; **D5** an operator canary and an unmanaged `client/custom` entry byte-identical after every step, and a base deploy without the marker leaves `src` untouched with its notice; **D7** `backup.sh` archives the handler; **D8** the marker as a symlink, a dangling symlink, a directory and a FIFO, and a symlink inside the repository's `client/custom/src`: each refused before the stack stops. A skipped or inconclusive journey is not a pass. The browser journeys of `CRM-WIP-LINK-001R2` are **not** repeated, because the handler and the metadata are byte-identical to the candidate they were run on (blob ids recorded). Nothing in this annex is claimed as passed by the delivery of this Work Order.

## 9. Execution limits, stop conditions, communications

- **Limits:** section 0 (cumulative). The engine's limit of 4 applies to each specialist.
- **Stop (BLOCKED, reported, never worked around):** any change outside the allowlist; a defect that needs a change to the handler, the metadata or any file outside section 3; a need for PHP, a database, the network, Node or a browser in the sandbox; a test that cannot be made non-vacuous without weakening a rule; the engine refusing the base or the known commit; a failed entry gate; any finding that cannot be reported safely. If ForgeV2 cannot accept the candidate as base without breaking its normal execution contract, the result is **one** concrete compatibility finding with an alternative plan, **not** a further Work Order identity. No firewall rules. No change to ForgeV2, Foundry or the host.
- **Communications:** Issue #85 (this chain; it also carries the cumulative counters). PL record under `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-WIP-LINK-001R3/` and, on the candidate branch, `.forge/CRM-WIP-LINK-001R3/`; per-specialist output under `dispatch/`. Mode: MANUAL fallback (CGPT's decisions are relayed by Matt; the Orchestrator records them on the Issues). Escalation: PL to Orchestrator; Orchestrator to CGPT (architecture) and Matt (product, permission, material risk).
- **Delivery:** the engine's candidate branch `forge/CRM-WIP-LINK-001R3` descends from `cbfeca76…`. After delivery the Orchestrator opens a **new draft PR** from it; PRs #84 and #87 and their branches are left exactly as they are until CGPT directs otherwise. Nothing is merged or deployed.
- **Completion report (PL):** outcome, changed paths, starting and final commit ids, acceptance criteria with results, the three verdicts and the candidate each assessed, the revert-and-rerun evidence for N01 to N03, the list of changed existing test lines, counts, deviations and remaining risks. If delivery fails, return BLOCKED with evidence.
