# tester review, CRM-WIP-INT-001D, round 1

Worktree: /srv/CRM/worktrees/CRM-WIP-INT-001D
Candidate SHA: 2f8312561b9e63d769e24a9bfee219acad876337
Base SHA: 1a1e80873b3abe5ba049923447f4fc2ee3784e6d
Scratch directory: /srv/CRM/worktrees/.forge-scratch/CRM-WIP-INT-001D

Assess as Tester: run the tests (whole suite and new tests) in your sandbox as the unprivileged account, and judge whether the new tests are real and discriminating. Assess independently. Do not modify the worktree (use a scratch copy for any mutation). Start your final message with exactly one verdict word: pass, findings or inconclusive, then your evidence. Use placeholders for any URL/token.

## Work Order text (verbatim)

WO: CRM-WIP-INT-001D
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: 1a1e80873b3abe5ba049923447f4fc2ee3784e6d
KNOWN_COMMIT: 1a1e80873b3abe5ba049923447f4fc2ee3784e6d

# CRM-WIP-INT-001D: pin TLS hostname verification with a behavioural test (test-only)

- **Version:** v1.0 **DRAFT**, 2026-11-17. **Not approved. No dispatch.** Dispatch needs a CGPT exact-version approval naming this path and the commit that contains it, recorded on the Issue below. The approval is recorded outside this text, so this text cannot show it; the Orchestrator's dispatch record (`APPROVAL.md` in the WO directory) carries it, the exception and the gate evidence, and the PL reads it with the WO before deciding intake.
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/71 (the integration chain's status and escalation record). The `CRM-WIP-INT-001C` BLOCKED report and decision request: comment 6953885556.
- **Authority:** CGPT's decision of 2026-11-17 ("CRM RECOVERY, WIP APPROVAL AND OPERATIONAL READINESS", section 2): "CGPT selects the additional test approach. Do not accept the residual risk." CGPT approved preparing this Work Order and, **in principle**, one exceptional additional Engineer execution (cumulative allowance four to five), as an explicit architectural exception, "not a reset of ForgeV2 counters or permission to bypass its controls". **Only permitted implementation change: `tests/unit/test_wip_panel.py`. No PHP source modification. No other production code changes.**
- **What this builds on, unchanged:** the `CRM-WIP-INT-001C` candidate, commit `1a1e80873b3abe5ba049923447f4fc2ee3784e6d` (one commit on `167f2a9acf543f171f1db45ab1f3e83d1031fe38`, tree `d7ee7483b6e2ee985f90e46de9b732cbb65d3d6d`, 644 files; changes against its parent: `WipLoader.php` one hunk in `process()` and `tests/unit/test_wip_panel.py`). Its DevSecOps verdict was PASS, its Auditor returned advisory FINDINGS (the same survivor, plus a note that the Engineer's report was not visible to it), and its Tester returned one blocking finding (`CURLOPT_SSL_VERIFYHOST` 2 to 0 leaves the suite green), which this WO closes. The candidate, branch `forge/CRM-WIP-INT-001C` (tip `b8bb92118a8b24b139cd8cfd0091fc2c9bbad4c8`, which carries the PL's records commit), branch `forge/CRM-WIP-INT-001R2` and draft PR #75 are preserved and never touched. The result of this WO is **one commit on top of the candidate**, on a new branch `forge/CRM-WIP-INT-001D`.
- **Header note (base).** `BASE` and `KNOWN_COMMIT` are the candidate's commit id, not a branch: the engine resolves `BASE` with `git rev-parse --verify <base>^{commit}` in the PL repository (it did so for `CRM-WIP-INT-001C`, whose `base_sha` equalled a commit id), where the candidate exists (verified read-only; it is an ancestor of `forge/CRM-WIP-INT-001C`). The branch tip carries the PL's records commit and is **not** substituted. A refusal of the commit id is **BLOCKED**, no workaround.
- **Header note (browser).** There is no `BROWSER: yes` line. The real EspoCRM browser check and the end-to-end proof are **not** part of this WO and remain outstanding.
- **Prepared by:** Rogue (Orchestrator). No implementation and no dispatch.

## 0. Chain and budget

| Item | Value |
|---|---|
| Chain | `CRM-WIP-INT-001` (1, BLOCKED) → `001R` (1, BLOCKED) → `001R2` (1, DELIVERED, candidate `167f2a9a…`) → `001C` (1, BLOCKED, candidate `1a1e8087…` not pushed) → **`CRM-WIP-INT-001D`** (this WO) |
| **Engineer budget** | The original cumulative cap of **4** is spent. CGPT's **exceptional** allowance raises the cumulative cap to **5**. **This WO may use exactly 1.** No second Engineer execution under the exception, no automatic recovery WO. The engine's own limit (4 per specialist per WO) cannot be lowered, so the cap is held by the dispatch record. **Any reviewer FAIL or FINDINGS after the Engineer's one execution ends the WO as BLOCKED** and returns to CGPT |
| Reviewers | Auditor, Tester and DevSecOps review the **exact new candidate**; each must return PASS on the same unchanged commit |

## 1. Outcome

A behavioural test fails when the loader's TLS **host-name** check (`CURLOPT_SSL_VERIFYHOST`) is weakened, while certificate verification (`CURLOPT_SSL_VERIFYPEER`) stays pinned by the existing F4 test. **The production code does not change.** The candidate stays a draft: no merge, no deployment, no live integration step.

## 2. Required work (everything else is out of scope)

**Allowlist (exact path):** `tests/unit/test_wip_panel.py`. That is the only file that may differ from the base. `WipLoader.php` must stay **byte-identical** to the base (blob `a1582260c90b598854406b2320af1df679461649`).

**The technique (demonstrated by the Orchestrator on a probe, 2026-11-17, with the host's PHP 8.4.27, libcurl 8.14.1 and OpenSSL 3.5.7).** A certificate generated at test time and **explicitly trusted** by pointing PHP's `curl.cainfo` at it (`php -d curl.cainfo=<certificate file>`) passes chain verification. Against a loopback URL `https://127.0.0.1:<port>`, `VERIFYHOST` 2 then accepts it only if the certificate names the target:

| Certificate | `VERIFYHOST` 2 | `VERIFYHOST` 0 |
|---|---|---|
| names `IP:127.0.0.1`, trusted | accepted, stub receives 1 request | accepted |
| names only `DNS:wrong.example`, trusted | **refused (curl error 60), stub receives 0 requests** | **accepted, stub receives 1 request** |
| any certificate, **not** trusted | refused | refused (so `VERIFYPEER` hides `VERIFYHOST`, which is why the delivered F4 test cannot see it) |

**Tests to add (names are indicative; one test each):**

| ID | Behaviour | Required test |
|---|---|---|
| **H1** | A **trusted** certificate whose name does not match the URL is refused | Generate a self-signed certificate and key **only in the test's temporary directory** with the `openssl` command, `-addext subjectAltName=DNS:wrong.example` (no IP name). Start the HTTPS loopback stub with it. Run the production loader against `https://127.0.0.1:<port>` with PHP started as `php -d curl.cainfo=<that certificate>`. Expect `{"wipStatus": "WIP unavailable", "wipCases": ""}`, **zero requests received by the stub**, and a log line carrying only the failure class (as the F4 test asserts). Also assert, independently of the loader, that the certificate **is** trusted: a Python `ssl` client with `cafile=<certificate>` and `check_hostname=False` gets a 200 from the stub, and the same client with host-name checking on fails with a certificate-verification error. This proves the refusal is caused by the name and not by trust |
| **H2** | Positive control: the same trust arrangement with a **matching** name is accepted | A second certificate generated the same way, `-addext subjectAltName=IP:127.0.0.1`, trusted the same way. The loader returns "WIP data available" for a valid contract reply and the stub receives exactly one request. This fails if the trust mechanism itself stops working, so that H1 cannot pass vacuously |

**Support change inside the same file.** The test harness's `run_loader` needs a way to pass extra PHP command-line settings (for `-d curl.cainfo=…`). Add an optional parameter whose default leaves every existing call unchanged. Do not change any existing test's behaviour or expectations. **No key or certificate is committed.** If `openssl` is missing the tests **fail loudly** (no skip), as the existing F4 test does. **TLS verification stays enabled** in the loader and in every test.

**Non-vacuity evidence required in the Engineer's report.** In a scratch copy that is **never committed**, change `CURLOPT_SSL_VERIFYHOST` from `2` to `0` in `WipLoader.php` and show **H1 failing** (and H2 still passing); restore. Then change it to `1` and report what happens (libcurl 8.x is expected to treat 1 as 2, which would make it an equivalent mutant; report the observed result, do not assume it). Report the test name and the failure. The existing F4 test must continue to fail when `VERIFYPEER` is turned off. The Orchestrator repeats this independently (AC6).

**Exclusions.** No other file: no PHP, metadata, layout, role, i18n, `deploy/`, `config/`, `scripts/`, no other test file, no documentation. No refactoring, renaming or reformatting. No new framework or dependency. No WIP change, no WIP data, no environment file. No role grant (PO-W1 stays open). No beta step, no ForgeV2, Foundry or scan change, no firewall rules. **Known and out of scope:** other surviving mutations in the Orchestrator's sweep (for example the 60-second connect timeout and the `CURLOPT_PROTOCOLS`-only removal, a documented equivalent) are **not** part of this WO; they are reported, not hidden.

## 3. Verification

- Run as the unprivileged specialist account: the whole existing unit suite (599 tests at the base, `OK (skipped=1)`: the known unrelated Git-metadata test in an export) plus the new tests. **0 failures.** Report counts before and after. The PHP tests must have run; **a skip does not count.**
- Static checks in the report: the diff touches only `tests/unit/test_wip_panel.py`; `WipLoader.php` is byte-identical to the base; gitleaks on the diff shows 0 findings; **no key or certificate material in the diff**; no `skip` introduced.
- **Auditor:** conformance to this WO and the allowlist, no production change. **Tester:** the new tests are real (H1 breaks under `VERIFYHOST` 0), the whole suite, H2 is a true positive control. **DevSecOps:** key and certificate handling (temporary directory only, nothing committed, nothing logged), TLS stays enabled, logs carry the class only.
- **Do not call advisory FINDINGS a PASS.** A FINDINGS verdict from any reviewer ends the WO as BLOCKED (section 0).

## 4. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| AC1 | The diff against `1a1e8087…` is exactly `tests/unit/test_wip_panel.py`; `WipLoader.php` is byte-identical to the base | `git diff --stat`, Auditor, Orchestrator |
| AC2 | H1 fails when `VERIFYHOST` is changed from 2 to 0 and passes at 2; H2 passes at 2 and at 0; the `VERIFYHOST` 1 result is reported | Engineer's non-vacuity evidence, Tester |
| AC3 | The whole unit suite passes with 0 failures, with counts before (599, 1 skip) and after reported | delivery record, Orchestrator re-run |
| AC4 | Auditor, Tester and DevSecOps return **PASS on the same unchanged candidate SHA**. The Tester returns no FINDINGS | ledger, delivery record |
| AC5 | gitleaks 0 findings; no key or certificate in the diff or the tree | scan |
| AC6 | **Orchestrator independent checks:** a fresh re-run from an export of the new candidate; a **source-identity check** (every file except the allowlisted one hashes equal to the base, and the allowlisted file differs only by the added tests and the optional `run_loader` parameter); the **mutation sweep**: the 31 mutations of the `001C` sweep plus `VERIFYHOST` 2 to 0 now **caught**. Expected survivors, reported not hidden: `CURLOPT_PROTOCOLS` removal (equivalent), `VERIFYHOST` 1 (equivalent if libcurl treats it as 2), the connect-timeout change (out of scope) and the `pass`-only URL check (equivalent: PHP's `parse_url` always sets `user` when a password is present) | Orchestrator report |
| AC7 | The candidate `1a1e8087…`, `167f2a9a…`, branches `forge/CRM-WIP-INT-001C` and `forge/CRM-WIP-INT-001R2`, draft PR #75 and every earlier ledger are unchanged; the three earlier ledgers and the `001C` ledger still show their execution counts | Orchestrator before and after record |
| AC8 | No merge, no deployment, no crm-dev or beta change, no WIP step | state record |

## 5. Gates

| Gate | Requirement | State |
|---|---|---|
| G1 | CGPT exact-version approval of this WO | open |
| G2 | Budget: the dispatch record states exactly one Engineer execution under CGPT's recorded exception (cumulative five), no second execution, no automatic recovery WO | at dispatch |
| G3 | Exact-base gate EB1 to EB8 below | open |

**Exact-base gate (all read-only, `GIT_OPTIONAL_LOCKS=0`).** EB1: in the PL repository `1a1e80873b3abe5ba049923447f4fc2ee3784e6d` is a commit with tree `d7ee7483b6e2ee985f90e46de9b732cbb65d3d6d`, one parent `167f2a9acf543f171f1db45ab1f3e83d1031fe38`, an ancestor of `forge/CRM-WIP-INT-001C` (`b8bb9211…`); `WipLoader.php` blob `a1582260…`, `tests/unit/test_wip_panel.py` blob `83a586a8…`. EB2: this WO's docs PR is merged at an exact commit `M`; GitHub `main` has only advanced by documents. EB3: the PL's local `main` equals `6e1766980e24d781d498727d4fe5db43cdeadbb7`, clean, canonical origin, no `url.*` rewrite. EB4: no `forge/CRM-WIP-INT-001D` branch, worktree, scratch directory, record directory or ledger exists; no other WO in flight; every preserved branch, worktree and closed ledger is untouched. EB5: the WO file given to the PL is byte-identical to the blob at `M` and readable by `forgev2-pl`. EB6: `forge-start` prints `base_sha` = `1a1e80873b3abe5ba049923447f4fc2ee3784e6d`; the committed ledger later shows the same. **Any other value is BLOCKED, no retry and no repair.** EB7: nobody advances or mutates the PL checkout (no root Git, no fetch, no ForgeV2 change). EB8: every staged file (WO, `APPROVAL.md`) passes a read test as `forgev2-pl` in a sandbox with its home hidden and no network.

## 6. Stop conditions

Any change outside the allowlist; any change to `WipLoader.php` or other production code. A new test that shows the loader is wrong: **BLOCKED and reported**, never fixed here. The `curl.cainfo` technique not working in the specialist sandbox (BLOCKED; no substitute technique, no mock of the TLS layer, no skip). A need for the network, a database, an environment file, a browser or WIP. A refusal of a commit id as `BASE`. A failed entry gate. A finding that cannot be reported safely (BLOCKED, never PASS). No firewall rules. No change to ForgeV2, Foundry or the host.

## 7. Communications and completion report

- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/71. **PL record:** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-WIP-INT-001D/` and, on the candidate branch, `.forge/CRM-WIP-INT-001D/`; per-specialist output under `dispatch/`. Communications mode: MANUAL fallback (CGPT's decisions are relayed by Matt; the Orchestrator records them on the Issue).
- **Escalation:** PL to Orchestrator; Orchestrator to CGPT (architecture) and Matt (product, permission, material risk).
- **Completion report (PL):** outcome, changed path, starting and final commit ids, acceptance criteria with results, the three verdicts and the candidate they assessed, the non-vacuity evidence, counts, deviations and remaining risks. Use placeholders for any URL or token. If the delivery fails, return BLOCKED with evidence; **do not create another replacement WO.**

Output format (mandatory): the FIRST line of your final message must be exactly 'VERDICT: PASS', 'VERDICT: FINDINGS' or 'VERDICT: INCONCLUSIVE'.
