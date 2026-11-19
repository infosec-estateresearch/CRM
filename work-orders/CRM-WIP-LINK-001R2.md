WO: CRM-WIP-LINK-001R2
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: 3a5e7cd13bb31bd84c7f21ff4c9a5dc42ee40aea
KNOWN_COMMIT: 3a5e7cd13bb31bd84c7f21ff4c9a5dc42ee40aea

# CRM-WIP-LINK-001R2: corrective successor of CRM-WIP-LINK-001 (marker-guard tests, advisory reconciliation, explicit reviewer PASS)

- **Version:** v1.0 **DRAFT**, 2026-11-19. **Not approved. No dispatch.** Dispatch needs a CGPT exact-version approval naming this path and the commit that contains it, recorded on the Issue below after that commit exists (the approval is recorded outside this text, so this text cannot show it). The Orchestrator's dispatch record (`APPROVAL.md`) carries the cumulative budget of section 0.
- **Issue (status, evidence, approval, escalation):** https://github.com/infosec-estateresearch/CRM/issues/85. **Original Work Order and Issue:** `CRM-WIP-LINK-001` v1.1, https://github.com/infosec-estateresearch/CRM/issues/82. **Authority:** CGPT's closed-ledger recovery ruling, Issue #82, comment 7010313116 (2026-11-19), which supersedes the earlier suggestion (comment 7009707171) to run a second Engineer execution on the original, terminal ledger. **Product direction:** https://github.com/infosec-estateresearch/CRM/issues/81.
- **Governing FOUNDRY:** `maff0000/foundry@84fedf0a74017237aa1bd650d8560350c91c7f0e` (`standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md`). CGPT reviewed current Foundry `main` `39cc45c25aa5305b60f4c4af1557bee8cec0bf20` on 2026-11-19: its terminology and development-host guidance waive neither role separation, audit, exact approvals nor budget bounds. **Engine:** ForgeV2 plugin 0.3.0, pinned `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, unmodified (re-verified at dispatch).
- **Prepared by:** Rogue (Orchestrator). Preparation only.
- **Why a new identity exists.** The engine closes a ledger as `DELIVERED` and then refuses every further dispatch and result on it; there is no reopen. The original ledger is therefore terminal, **stays closed and unchanged**, and is not reopened, edited, renamed, relabelled or re-marked. This Work Order is a *corrective delivery unit* that finishes the unfinished assurance of the same candidate. It is **not** a new budget, not a declaration that the original assurance passed, and not a precedent for further successors: **no further successor without a new governance ruling.**

## 0. Chain, provenance and cumulative budget (binding across both ledgers)

| Item | Value |
|---|---|
| Original Work Order | `CRM-WIP-LINK-001` v1.1, approved at CRM commit `c941e9296048022bd741980f0e9585d9715ac6bb` (`work-orders/CRM-WIP-LINK-001.md`, SHA-256 `dd4f720f5158031664cbf164294f321f63900e5f8612bfd26ceb56e97e0e0f52`), merged on `main` as `df6599f8a63b58ff5e0402f4730831d5fd4b8226` (PR #83). Issue #82 |
| Original ledger | terminal **DELIVERED**, project key `3b6369e4f8e78d83`, **closed and unchanged**. Its recorded verdicts: **Auditor FINDINGS** (two advisory findings, below), Tester PASS, DevSecOps PASS (gitleaks 0). Architectural acceptance is **withheld** (CGPT, comment 7010313116) |
| Original candidate | `3a5e7cd13bb31bd84c7f21ff4c9a5dc42ee40aea` (parent `6e1766980e24d781d498727d4fe5db43cdeadbb7`, 8 paths, no `.forge` content) |
| Original delivery tip | `dcd4f7c1164bc4507aa4774e0f11d7b70fff43a6` on branch `forge/CRM-WIP-LINK-001` (the candidate plus 10 generated `.forge/CRM-WIP-LINK-001/` record files), draft PR #84: **DRAFT, NOT merge-approved, not touched by this Work Order** |
| Original executions | Engineer **1**, Auditor **1**, Tester **1**, DevSecOps **1** |
| **Engineer budget (this WO)** | **At most 2** executions, so the cumulative total for the chain is **at most 3** (the original approved cap). Held by the dispatch record (the engine's limit of 4 per specialist cannot be lowered). A second execution is allowed only to correct a reviewer FINDINGS or FAIL on the first |
| **Reviewer budget (this WO)** | Auditor, Tester and DevSecOps **at most 3 each**, so the cumulative total is **at most 4 each** (the engine limit). Each assesses the **exact final candidate**; any Engineer change restarts all three |
| Counters | The new engine ledger technically starts at 0/0/0/0. **That is not a fresh budget.** The dispatch record and Issue #82 carry the cumulative counters (Engineer 1 + this WO's; each reviewer 1 + this WO's); the Orchestrator reports both |
| Failure | Any further failure ends this Work Order as BLOCKED or ESCALATED with evidence and returns to CGPT. **No replacement, recovery or further successor Work Order** |

**What PASS means here (binding; CGPT's ruling item 5).** The closing evidence is an explicit **PASS from each of Auditor, Tester and DevSecOps on one unchanged final candidate**, recorded in the ledger. A reviewer verdict of `FINDINGS` is **not** a PASS, and it is not turned into one by recording its findings as advisory: findings of a `FINDINGS` verdict are recorded as blocking and returned to the Engineer while the cap allows. The ledger is closed `DELIVERED` only when the three current verdicts are PASS; otherwise `ESCALATED` or `BLOCKED`. The original FINDINGS verdict stays recorded as it is.

## 1. Outcome

Finish the originally approved candidate **without adding any application functionality**: (a) non-vacuous tests that a symlinked or non-regular deployment-marker file is refused on **install** and on **update**, with a valid-regular-marker positive control; (b) tests that kill the marker-guard mutation that survived (`M05`) and its variants; (c) reconcile the two original Auditor advisories (section 3.2 and 3.3) and obtain an explicit Auditor PASS; (d) preserve everything the candidate already does: the Account button and its URL validation, the minimal client-asset delivery (install, update, managed removal, restore on failure, cache-bust), exit codes and error handling. The result stays a draft: no merge, no deployment.

## 2. Repository, workspace, base and what must stay untouched

| Item | Verified value (2026-11-19) |
|---|---|
| Repository | `infosec-estateresearch/CRM` (public). GitHub `main` `df6599f8a63b58ff5e0402f4730831d5fd4b8226` differs from the original base `6e176698…` by documents only (re-checked at dispatch, gate G3) |
| Execution host and paths | `DOCKER1:/srv/CRM/main` (the PL's checkout, clean, local `main` `6e176698…`, which also holds the candidate and the delivery tip), worktrees `/srv/CRM/worktrees`; the specialist branch is `forge/CRM-WIP-LINK-001R2` in its own worktree |
| **Base (proved)** | **The clean implementation candidate `3a5e7cd13bb31bd84c7f21ff4c9a5dc42ee40aea`**, passed as both `BASE` and `KNOWN_COMMIT`. It is preferred to the delivery tip `dcd4f7c1…` so that generated `.forge/CRM-WIP-LINK-001` records are not inherited as application content. Proof (Orchestrator, 2026-11-19, scratch copy of the PL checkout, private ledger directory): the engine's own `forge-start --base 3a5e7cd1… --known-commit 3a5e7cd1…` accepts it (decision BUILD, counts 0/0/0/0, branch `forge/CRM-WIP-LINK-001R2`), the new worktree's tree equals the candidate's tree (`11f2a8faf373ab9974ae2172590ed1f4c3cd6440`), a re-run resumes without a reset, an unknown known-commit is refused, the engine also accepts the delivery tip (a control; not chosen), and the **full suite on the new worktree gives 609 tests, OK** in the engine-shaped sandbox (as the specialist account, no network); an export of the same tree without `.git` reports the same suite OK with one pre-existing, environment-dependent skip. Evidence: Issue #85 |
| Baseline for the surviving mutations | On this base, the marker-guard mutations `M05`, `M05a`, `M05b`, `M05c` and `M05d` (section 5) were applied by the Orchestrator and **every one SURVIVED the existing suite** (the full unit suite, run on a copy of the base without `.git`: OK in each case): the starting condition this Work Order must change |
| Specialist limits | The sandbox has no network, no Docker, no browser, no Node.js, and cannot read the runtime directories. Unit tests are Python (`python3 -m unittest discover -s tests/unit`). JavaScript is **not** executed in the sandbox |
| Protected | `/srv/forgev2`, `/srv/src/foundry`, every ledger (including `CRM-WIP-LINK-001`'s), the branch `forge/CRM-WIP-LINK-001` and draft PR #84 (its head `dcd4f7c1…`), the live runtime directories, the earlier candidates `07bfaf1c…`, `167f2a9a…`, `1a1e8087…`, `2f831256…`, branches `forge/CRM-WIP-INT-*` and `forge/CRM-CLIENT-001R2`, draft PRs #69, #75, #80 |

## 3. Required work (the allowlist; everything else is out of scope)

| Path | Change |
|---|---|
| `tests/unit/test_client_delivery.py` | **edit, additions only.** The marker-guard scenarios and positive controls of section 3.1, and entries for the marker mutations in the file's own mutation table (`TestEveryRuleIsNonVacuous`). No existing test is removed, skipped, renamed or weakened |
| `tests/unit/test_wip_link.py` | **edit, additions only.** The base-URL rows of section 3.2 (the `@` rule), checked against the handler's source as the file already does. No existing test is removed, skipped or weakened |
| `docs/WIP-LINK.md` | **edit, limited** to the two statements that name user-info (the `wipBaseUrl` bullet and verification step 2), so that they state the rule of section 3.2. Nothing else |
| `scripts/deploy_custom.sh` | **conditional edit.** Byte-identical to the candidate **unless** a new marker test proves, by failing against the unmodified script, a real defect in the marker handling; then the **smallest** fix, listed in the report with the failing test, with every existing exit code, message and call sequence unchanged. A mutation that merely makes a guard weaker is not a defect |

**Everything else is byte-identical to the candidate `3a5e7cd1…`**, in particular `client/custom/src/handlers/account-open-wip.js`, `custom/Espo/Custom/Resources/metadata/clientDefs/Account.json`, `docs/BUILD.md`, `tests/unit/test_scripts.py`, all other scripts, `deploy/`, compose files, `.forge/` (the PL's engine records for this Work Order are the only addition, made by the engine), and every other file. No new dependency, package, image or vendored file.

### 3.1 Marker-guard tests (the contract)

The guard under test is the marker rule of `scripts/deploy_custom.sh`: if `client/custom/.src-managed-by-git` exists (or is a symlink, including a dangling one) it must be a regular file that is not a symlink, otherwise the script refuses to deploy (`refusing to deploy: the marker is not a regular file: <path>`). It runs in the first pass before the stack is touched and again after the stack stops. The tests use the file's existing fake-`docker` harness and temporary directories (no real Docker, no network, no privilege) and must prove, for **each** run kind and **each** marker kind:

| Run kind | Setup |
|---|---|
| **install** | the repository has `client/custom/src`; the runtime has no `client/custom/src` |
| **update** | the repository has `client/custom/src`; the runtime has a managed `src` from an earlier good install |
| **removal** (rollback by deploying the base) | the repository has no `client/custom/src`; the runtime has `src` |

| Marker kind (in place of the regular marker file) |
|---|
| a symlink to a regular file inside `client/custom` · a **dangling** symlink · a symlink to a canary file **outside** `client/custom` · a **directory** · a **FIFO** (named pipe) |

**Required for every (run kind, marker kind) pair:** the script exits non-zero; stderr carries the refusal message above; **no** `docker` call that stops, removes or rebuilds the stack is recorded (the first pass refuses before any stop); the runtime trees are byte-identical before and after (`src`, `modules/`, every other `client/custom` entry, and the marker itself, including its type and link target); the canary is byte-identical (nothing is written through or removed via the link); no working name (`.src.deploy-*`, `.src.old-*`, `.src.failed-*`) was created. In addition, **one scenario** per run kind `install` and `update` in which the marker is replaced by a symlink *while the stack stops* (the second pass), following the file's existing planted-while-stopping pattern, with the outcome that pattern already pins for the second pass.

**Positive controls (must pass in the same harness with the guard intact):** an `update` with a **regular** marker (exit 0, tree equal to the repository's, marker still a regular file holding the script's line); an `install` with **no** marker (exit 0, marker created as a regular file); a `removal` with a regular marker (exit 0, `src` and marker gone). A test that cannot pass for the regular marker is vacuous and is rejected.

**Non-vacuity (Engineer, Tester and Orchestrator):** the five mutations of section 5 are each caught by at least one new test, shown by revert-and-rerun, with the test named for each mutation.

### 3.2 Reconciliation of `handler-at-sign` (the base-URL `@` rule)

The original Auditor finding: the handler rejects an `@` anywhere in `wipBaseUrl`, which is stricter than v1.1 section 3.1 item 3 (user-info only, a path prefix allowed). **Decision of this Work Order (the one point CGPT's approval of this exact version settles): the stricter, fail-closed behaviour is kept and made the written rule; the handler is not changed.** Rule: `wipBaseUrl` is rejected if it contains the character `@` anywhere (user-info or otherwise), as well as any query or fragment; a path prefix is allowed as long as it contains no `@`; the existing behaviour table row "contains `user:pass@`, `?x=1` or `#x`" now reads "contains `@`, `?x=1` or `#x`". *Reason:* the check is working and fail-closed; loosening it would weaken validation to satisfy a finding, with no product need (the base is `http(s)://host[:port][/prefix]`). *Alternative not chosen:* relax to user-info only; CGPT may direct it at approval, and the Work Order is then re-issued, not guessed. Tests (additions to `test_wip_link.py`): rows for `@` in user-info, in the host, in a path prefix, with a query and with a fragment, each rejected by the file's reference model **and** tied to the handler's own `@` rejection by the static check the file already uses, so that deleting the handler's `@` check fails a test.

### 3.3 Reconciliation of `harness-edit-scope`

The original finding: `tests/unit/test_scripts.py` gained two fake-`docker` fixture cases that v1.1 section 3 did not name (it allowed "runtime-layout fixtures and assertions"). **Ratified register (exhaustive; the diff of `tests/unit/test_scripts.py` between the original base `6e176698…` and the candidate is exactly these four edits, and this Work Order changes none):** (1) in the `FAKE_DOCKER` fixture, two new `case` lines for `update-app-timestamp` and `appTimestamp`; (2) the new constant `READ_TS`; (3) `test_running_app_gets_clear_cache_then_rebuild`: the expected call list gains `READ_TS`, `update-app-timestamp`, `READ_TS`; (4) `test_writable_dirs_are_made_private_after_the_stop`: the expected `chown` list gains `client/custom`. None weakens an assertion. The Auditor verifies the register against that diff and reports it as resolved or not; any further edit to `test_scripts.py` is outside this Work Order.

## 4. Exclusions and protected items

No functionality, entity, field, scope, ACL, layout, route, PHP, WIP loader, API call, token, database access or compose change; no change to the handler or the Account metadata; no change to scripts other than the conditional `deploy_custom.sh` edit; no `deploy/`, `backup.sh`, `restore.sh` or release tooling change; no new dependency, image, CDN or vendored file; no Node or browser tooling in the repository; no refactor of existing code; no change to ForgeV2, Foundry, the host, `crm-dev`, `crm-beta`, WIP or Salesforce. No firewall rules. No merge or deployment by any specialist. The branch `forge/CRM-WIP-LINK-001` and PR #84 are not modified.

## 5. Verification

- **Mutation list (the Orchestrator's sweep and the specialists' proofs).** Each is an exact one-place edit of `scripts/deploy_custom.sh` that the new tests must catch: **M05** the guard body removed; **M05a** the symlink test dropped (only `-f` stays); **M05b** the regular-file test dropped (only `! -L` stays); **M05c** the guard entered only when `-e` is true (a dangling symlink escapes); **M05d** the refusal downgraded to a warning (the run continues). The Orchestrator's earlier sweep of this candidate (eleven mutations of the script, the handler and the metadata, of which only the marker guard survived) and the handler rules of the v1.1 criterion AC8 are re-run in full on the final candidate: every mutation is caught or reported as an equivalent.
- **Engineer (mechanical):** the whole unit suite on the base (609 tests, OK; report the count and skip count of its own baseline run and after, with no new skip, no removed test); the new scenarios; the revert-and-rerun proof for M05 to M05d, naming the catching test for each; every edit confined to section 3.
- **Auditor:** conformance to this Work Order, the original Work Order and the allowlist; the diff against `3a5e7cd1…` is only the allowlisted paths and the byte-identical items are unchanged (blob ids); the `handler-at-sign` and `harness-edit-scope` findings are each stated as resolved or not, by key, with evidence; the register of section 3.3 equals the `test_scripts.py` diff. **Explicit verdict PASS or FINDINGS.**
- **Tester:** the new tests are real (the Tester applies M05 to M05d and the file's own mutations and shows a test fail for each; the positive controls pass); the whole suite; states plainly that **JavaScript is not executed in the sandbox**.
- **DevSecOps:** no URL, host or credential in the diff; the marker handling cannot be steered through a link (no write or removal follows a symlinked marker; the canary stays untouched); no dependency; gitleaks 0 findings.
- A FINDINGS verdict from any reviewer returns to the Engineer while the cap allows (the findings recorded as blocking); it is never presented as PASS.

## 6. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| R1 | The diff against `3a5e7cd13bb31bd84c7f21ff4c9a5dc42ee40aea` is exactly the allowlist (section 3); every other file is byte-identical (blob ids recorded); the handler and the Account metadata are unchanged | `git diff --stat`, Auditor, Orchestrator source-identity check |
| R2 | The marker scenarios of section 3.1 exist for every run kind and marker kind, refuse as specified, and the positive controls pass; the tests fail when the guard is weakened (M05 to M05d) | tests, revert-and-rerun, Tester, Orchestrator sweep |
| R3 | The `@` rule of section 3.2 is pinned by tests and stated in `docs/WIP-LINK.md`; URL validation behaviour is unchanged | tests, Auditor |
| R4 | The `test_scripts.py` diff against the original base equals the register of section 3.3 | Auditor |
| R5 | The whole unit suite passes with 0 failures; counts before and after are reported; no new skip; nothing removed or weakened; every existing test of the candidate still passes | delivery record, Orchestrator re-run |
| R6 | **Auditor, Tester and DevSecOps return PASS on the same unchanged candidate commit** (explicit verdict words; the Auditor's verdict is PASS, not FINDINGS) | ledger, delivery record |
| R7 | gitleaks 0 findings; no host, address or credential in the diff | scan |
| R8 | **Orchestrator independent checks:** a fresh re-run of the whole suite from an export of the final candidate; the source-identity check; the mutation sweep above, every mutation caught or reported equivalent | Orchestrator report |
| R9 | **Operator browser assurance** (section 8) is a separate post-delivery step on the final candidate; it is **planned and is not claimed** by this Work Order's delivery | annex evidence package |
| R10 | The original ledger, its records, the branch `forge/CRM-WIP-LINK-001`, PR #84 and every earlier ledger and PR are byte-identical before and after; no merge or deployment; the cumulative counters are recorded | state record (hashes before and after) |

## 7. Gates

| Gate | Requirement | State |
|---|---|---|
| G1 | CGPT exact-version approval of this Work Order at an immutable commit (path, commit, SHA-256, base proof, ledger continuity, allowlist) | open |
| G2 | Budget: the dispatch record states Engineer at most 2 and each reviewer at most 3 for this Work Order, the cumulative totals of section 0, and the PASS rule | at dispatch |
| G3 | Exact base: in the PL repository `3a5e7cd1…` resolves to a commit whose parent is `6e176698…` and whose tree is `11f2a8faf373ab9974ae2172590ed1f4c3cd6440`; local `main` is `6e176698…`, clean, canonical origin, no `url.*` rewrite, `core.hooksPath`, `core.fsmonitor` or `include`; GitHub `main` differs from `6e176698…` by documents only; no `forge/CRM-WIP-LINK-001R2` branch, worktree, scratch directory, ledger or record exists; every earlier ledger and the original ledger are recorded by hash; engine and plugin as pinned and clean; the engine's `forge-start` accepts the base (the proof of section 2 is re-run on a scratch copy); the suite on the base gives 609 tests, OK | at dispatch |
| G4 | **Execution isolation:** the single PL session is launched only through the hardened private mount and PID namespace launcher (v2.1) with a clean allowlisted environment and working directory `/`; immediately before the dispatch, the in-context denial of every known sensitive host path, a positive synthetic control and a live `/proc` sentinel check are run and recorded; no inherited session or credential variable. Any adverse result blocks dispatch with no Engineer execution spent. No earlier run is assumed to have been safe merely because no reference appeared in its logs | at dispatch |
| G5 | Sequential sessions: no other `claude` session under the PL account is in flight, and no other Work Order is dispatched for this repository, at dispatch | at dispatch |
| G6 | The Work Order and the dispatch record given to the PL are staged read-only; the Work Order is byte-identical to the approved blob | at dispatch |

## 8. Annex: operator real-browser assurance (Orchestrator-run; zero specialist executions)

After the candidate is DELIVERED with its three PASS verdicts, the annex of `CRM-WIP-LINK-001` v1.1 (section 8: preparation, browser, journeys J1 to J7, delivery journeys D1 to D6, evidence) applies **unchanged** to the final candidate, on a synthetic CRM target with synthetic data only and with the independent WIP application serving synthetic data. One delivery journey is added: **D8, marker integrity:** replace the marker with a symlink to an operator canary file, run `scripts/deploy_custom.sh`, and observe the refusal before the stack stops, the canary and every runtime tree byte-identical and the application still serving; then restore a regular marker and observe a normal update. A skipped or inconclusive journey is not a pass. Nothing in this annex is claimed as passed by the delivery of this Work Order.

## 9. Execution limits, stop conditions, communications

- **Limits:** section 0 (cumulative). The engine's limit of 4 applies to each specialist.
- **Stop (BLOCKED, reported, never worked around):** any change outside the allowlist; a defect that needs a change to the handler, the metadata or any file outside section 3; a need for PHP, a database, the network, Node or a browser; a test that cannot be made non-vacuous without weakening a rule; a reviewer finding that can only be resolved by loosening a validation check; the engine refusing the base or the known commit; a failed entry gate; any finding that cannot be reported safely. If ForgeV2 cannot accept the candidate as base without breaking its normal execution contract, the result is **one** concrete compatibility finding with an alternative plan, **not** a further Work Order identity. No firewall rules. No change to ForgeV2, Foundry or the host.
- **Communications:** Issue https://github.com/infosec-estateresearch/CRM/issues/85 (this Work Order) and https://github.com/infosec-estateresearch/CRM/issues/82 (the original, which also records the cumulative counters). PL record `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-WIP-LINK-001R2/` and, on the candidate branch, `.forge/CRM-WIP-LINK-001R2/`; per-specialist output under `dispatch/`. Mode: MANUAL fallback (CGPT's decisions are relayed by Matt; the Orchestrator records them on the Issues). Escalation: PL to Orchestrator; Orchestrator to CGPT (architecture) and Matt (product, permission, material risk).
- **Delivery:** the engine's candidate branch `forge/CRM-WIP-LINK-001R2` descends from `3a5e7cd1…`. After delivery the Orchestrator opens a **new draft PR** from it (it contains the complete candidate plus the corrections); PR #84 and its branch are left exactly as they are until CGPT directs otherwise. Nothing is merged or deployed.
- **Completion report (PL):** outcome, changed paths, starting and final commit ids, acceptance criteria with results, the three verdicts and the candidate each assessed, the revert-and-rerun evidence for each mutation, the resolution of each original advisory, counts, deviations and remaining risks. If delivery fails, return BLOCKED with evidence.
