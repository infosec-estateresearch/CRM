WO: CRM-WIP-INT-001C
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: 167f2a9acf543f171f1db45ab1f3e83d1031fe38
KNOWN_COMMIT: 167f2a9acf543f171f1db45ab1f3e83d1031fe38

# CRM-WIP-INT-001C: corrective assurance of the Part B candidate (four test findings and a fail-closed ACL exception)

- **Version:** v1.0 **DRAFT**, 2026-11-17. **Not approved. No dispatch.** Dispatch needs a CGPT exact-version approval naming this path and the commit that contains it, recorded on the Issue below. The approval is recorded outside this text, so this text cannot show it; the Orchestrator's dispatch record (`APPROVAL.md` in the WO directory) carries it and the gate evidence, and the PL reads it with the WO before deciding intake.
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/71 (the integration chain's status and escalation record). Plan comment: 6951631092.
- **Authority:** CGPT's decision of 2026-11-17: "Prepare a narrow corrective Work Order covering the four identified test findings and the ACL exception fail-closed behaviour. The only permitted PHP functional correction is preventing WIP fields from being set when the ACL permission check itself throws. No other feature or loader refactoring is authorised. Engineer budget: one remaining execution across the existing CRM integration delivery chain. Tester, Auditor and DevSecOps must review the new exact candidate. Do not call advisory FINDINGS a PASS. No CRM merge or live integration deployment yet."
- **What this builds on, unchanged:** the Part B candidate of `CRM-WIP-INT-001R2`, commit `167f2a9acf543f171f1db45ab1f3e83d1031fe38` (one commit on `6e1766980e24d781d498727d4fe5db43cdeadbb7`, tree `a5b8f5e5c2f8b3831630eb67b00a90f80e57a704`, 18 files; Auditor PASS, DevSecOps PASS, **Tester FINDINGS**), draft PR #75 and branch `forge/CRM-WIP-INT-001R2`. They are preserved and never touched. The result of this WO is a **second commit on top of the candidate**, on a new branch `forge/CRM-WIP-INT-001C`.
- **Header note (base).** `BASE` and `KNOWN_COMMIT` are the candidate's commit id, not a branch: the engine resolves `BASE` with `git rev-parse --verify <base>^{commit}` in the PL repository, where that commit exists (verified read-only), and never fetches. If the engine or the PL refuses a commit id as `BASE`, the result is **BLOCKED** and goes to CGPT. No workaround, and the R2 branch tip is **not** substituted (it carries the PL's record commit).
- **Header note (browser).** There is no `BROWSER: yes` line. The real EspoCRM browser check and the end-to-end proof are **not** part of this WO and remain outstanding.
- **Prepared by:** Rogue (Orchestrator). No implementation and no dispatch.

## 0. Chain and budget

| Item | Value |
|---|---|
| Chain | `CRM-WIP-INT-001` → `CRM-WIP-INT-001R` → `CRM-WIP-INT-001R2` (DELIVERED, candidate `167f2a9a…`) → **`CRM-WIP-INT-001C`** (this WO) |
| **Engineer budget** | CGPT's cumulative cap is **4** Engineer executions for this outcome. **3 are spent** (1, 1, 1). **This WO may use exactly 1.** The engine's own limit (4 per specialist per WO) cannot be lowered, so the cap is held by the dispatch record. **Any reviewer FAIL or FINDINGS after the Engineer's one execution ends the WO as BLOCKED.** No second Engineer execution, no automatic recovery WO. The options then return to CGPT |
| Reviewers | Auditor, Tester and DevSecOps review the **exact new candidate** (the corrective commit on the base) |

## 1. Outcome

The Part B tests discriminate the guards they are meant to protect, and the loader fails closed if the permission check itself throws. Nothing else changes. The candidate stays a draft: **no merge, no deployment, no live integration step.**

## 2. Required work (everything else is out of scope)

**Allowlist (exact paths):**
- `tests/unit/test_wip_panel.py` (new and changed tests)
- `tests/unit/test_access_policy.py` and `tests/unit/access_policy.py`, **only** to resolve finding T5
- `custom/Espo/Custom/Classes/FieldProcessing/Account/WipLoader.php`, **only** the change in A1

| ID | Guard or behaviour (in `WipLoader.php`) | Why the delivered test misses it | Required test (behaviour pinned to the code as it stands) |
|---|---|---|---|
| **F1** | Body cap, `MAX_BODY` 262144 bytes | `test_oversize_reply_is_unavailable` sends a 300,000-character `companyName`. Without the cap the body is read in full and then refused by the 255-character field rule, so the test passes either way. **This is also the Tester's finding** | A reply that is **otherwise valid** (correct contract, echoing the Account's Salesforce id) padded with whitespace, so it stays valid JSON, to more than `MAX_BODY`. Expect "WIP unavailable" and empty case text. Include the unpadded reply as a control that is accepted, so the oversize result cannot be a side effect of the content. Pin the boundary the code implements |
| **F2** | `user:pass@` in the configured URL is refused | `test_bad_urls_are_refused` uses `http://user:pw@127.0.0.1:1`. Port 1 is dead, so the request fails whatever the guard does | The same shape of URL **pointed at the stub** (`http://user:pw@127.0.0.1:<stub port>`, and a user-only form). Expect "WIP unavailable" **and zero requests received by the stub** |
| **F3** | Scheme must be `http` or `https` (in `buildUrl`) | `ftp://` and `gopher://` are also refused by `CURLOPT_PROTOCOLS`, so a second layer masks the first | Call the private `buildUrl` directly through reflection (PHP 8.4 here; no `setAccessible` is needed) with `ftp://`, `file:///`, `gopher://`, `javascript:` and a scheme-less string: each returns `null`. Control: an `http://` and an `https://` URL return a non-null URL that contains the Salesforce id. This pins the first layer on its own. **The second layer (`CURLOPT_PROTOCOLS`) is an accepted redundant defence;** removing only it is an equivalent mutant and is documented as such |
| **F4** | TLS verification (`CURLOPT_SSL_VERIFYPEER` true, `CURLOPT_SSL_VERIFYHOST` 2) | The harness is HTTP-only | An HTTPS loopback stub using a **self-signed certificate generated at test time** with the `openssl` command into the test's temporary directory (feasibility verified in the sandbox pattern: OpenSSL 3.5.7, PHP 8.4.27 with curl). The loader pointed at it must answer "WIP unavailable" and the stub must receive **no request**. **No key or certificate is committed.** If `openssl` is missing the test **fails loudly** (no skip), as the PHP tests do |
| **A1** | ACL exception fails closed | `process()` runs `checkScope` inside the same `try`; if it throws, the `catch` sets "WIP unavailable" for a user whose permission was never established | **The one permitted functional correction:** if `$this->acl->checkScope()` throws, `process()` sets **no** WIP field (neither status nor cases), sends **no** request, and logs only the exception **class**. Every other path, constant, method and message in the file is byte-for-byte unchanged. Expected size: about 10 changed lines, **one hunk in `process()`**. Test: a harness `Acl` whose `checkScope` throws an exception whose message contains a recognisable marker. Assert no field is set, the stub saw zero requests, and the marker appears nowhere in the output or logs |
| **T5** | The Tester's note on the `load_access_fixture` helper in `test_access_policy.py` | Advisory note with no stated defect | Read the helper. If a real defect exists, fix it inside the allowlist. If not, say why in the report. The Tester decides whether it is resolved |

**Non-vacuity evidence required in the Engineer's report.** For F1, F2, F3, F4 and A1, in a scratch copy that is **never committed**, remove or reverse the guard and show the named new test failing; then restore. Report the test name and the failure for each. The Orchestrator repeats this independently (§6, AC7).

**Exclusions.** No change to any other file: no `deploy/`, `config/`, `scripts/`, no other PHP, metadata, layout, role or i18n file, no other test file. No refactoring, renaming or reformatting of the loader. No new test framework or dependency. No WIP change, no WIP data, no environment file. No role grant (PO-W1 stays open). No beta step, no ForgeV2, Foundry or scan change, no firewall rules.

## 3. Verification

- Run as the unprivileged specialist account: the whole existing unit suite (594 tests at the base of this WO, 1 known unrelated skip: the Git-metadata test in an export) plus the new tests. Report counts before and after. **0 failures.**
- Static checks in the report: the diff touches only the allowlisted paths; `WipLoader.php` has exactly one changed hunk, inside `process()`; gitleaks on the diff shows 0 findings; no key or certificate material in the diff.
- **Auditor:** conformance to this WO, only the allowed PHP change, no loader refactoring. **Tester:** the new tests are real (each guard breaks its test), the full suite, and the status of T5. **DevSecOps:** the fail-closed behaviour, no secret or key material, TLS stub handling, logs carry the class only.
- **Do not call advisory FINDINGS a PASS.** A FINDINGS verdict from any reviewer ends the WO as BLOCKED (§0).

## 4. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| AC1 | The diff against `167f2a9a…` is only the allowlisted paths; `WipLoader.php` has one hunk in `process()` | `git diff --stat`, Auditor, Orchestrator |
| AC2 | F1, F2, F3, F4 and A1 each have a test that fails when its guard is removed (the equivalent mutant in F3 is documented) | Engineer's non-vacuity evidence, Tester |
| AC3 | The whole unit suite passes with 0 failures; counts before and after reported | delivery record, Orchestrator re-run |
| AC4 | Auditor, Tester and DevSecOps return **PASS on the same unchanged candidate SHA**. The Tester returns no FINDINGS | ledger, delivery record |
| AC5 | gitleaks 0 findings; no key or certificate in the diff | scan |
| AC6 | The R2 candidate `167f2a9a…`, branch `forge/CRM-WIP-INT-001R2`, draft PR #75 and every earlier ledger and branch are unchanged | Orchestrator before and after record |
| AC7 | **Orchestrator independent checks:** a fresh re-run from an export of the new candidate; a **source-identity check** (every file except the allowlisted ones hashes equal to the base, and the loader differs by the one hunk); the **mutation sweep**: the original 16 mutations plus the new ones. Target: every mutation caught except documented equivalents, and survivors reported, not hidden | Orchestrator report |
| AC8 | No merge, no deployment, no crm-dev or beta change, no WIP step | state record |

## 5. Gates

| Gate | Requirement | State |
|---|---|---|
| G1 | CGPT exact-version approval of this WO | open |
| G2 | Budget: the dispatch record states exactly one Engineer execution and no automatic recovery WO | at dispatch |
| G3 | Exact-base gate EB1 to EB8 below | open |

**Exact-base gate (all read-only, `GIT_OPTIONAL_LOCKS=0`).** EB1: GitHub shows the candidate `167f2a9a…` with tree `a5b8f5e5…`, parent `6e176698…` and the 18 R2 paths, and the branch `forge/CRM-WIP-INT-001R2` at `34b50af7…`. EB2: this WO's docs PR is merged at an exact commit `M`; GitHub `main` has only advanced by documents. EB3: the PL's local `main` equals `6e1766980e24d781d498727d4fe5db43cdeadbb7`, clean, canonical origin, no `url.*` rewrite; `167f2a9a…` is a commit object in the PL repository. EB4: no `forge/CRM-WIP-INT-001C` branch, worktree, scratch directory or ledger exists; no other WO in flight; every preserved branch, worktree and closed ledger (including `CRM-WIP-INT-001R2`'s) is untouched. EB5: the WO file given to the PL is byte-identical to the blob at `M` and readable by `forgev2-pl`. EB6: `forge-start` prints `base_sha` = `167f2a9acf543f171f1db45ab1f3e83d1031fe38`; the committed ledger later shows the same. **Any other value is BLOCKED, no retry and no repair.** EB7: nobody advances or mutates the PL checkout (no root Git, no fetch, no ForgeV2 change). EB8: every staged file (WO, `APPROVAL.md`, reference) passes a read test as `forgev2-pl`.

## 6. Stop conditions

Any change outside the allowlist, or a second hunk or any refactoring in `WipLoader.php`. A new test that shows the loader is wrong anywhere other than A1: **BLOCKED and reported**, never fixed here. A need for the network, a database, an environment file, a browser or WIP. A refusal of a commit id as `BASE`. A failed entry gate. A finding that cannot be reported safely (BLOCKED, never PASS). No firewall rules. No change to ForgeV2, Foundry or the host.

## 7. Communications and completion report

- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/71. **PL record:** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-WIP-INT-001C/` and, on the candidate branch, `.forge/CRM-WIP-INT-001C/`; per-specialist output under `dispatch/`. Communications mode: MANUAL fallback (CGPT's decisions are relayed by Matt; the Orchestrator records them on the Issue).
- **Escalation:** PL to Orchestrator; Orchestrator to CGPT (architecture) and Matt (product, permission, material risk).
- **Completion report (PL):** outcome, changed paths, starting and final commit ids, acceptance criteria with results, the three verdicts and the candidate they assessed, the non-vacuity evidence, counts, deviations and remaining risks.
