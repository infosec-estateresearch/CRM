WO: CRM-TEST-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main
BROWSER: no (proposed; it needs CGPT's decision, see §9)

# CRM-TEST-001: hermetic `test_shell_guard` (baseline unit-test repair)

- **Version:** v1.0 DRAFT, 2026-11-13. This is not approved. It identifies its own immutable version only by the commit that adds it; approval must name that commit.
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/56
- **Prepared by:** Rogue (Orchestrator), under the CGPT Architect's *Step 2A: Baseline Test Repair Work Order* assignment. That assignment authorises preparation only.
- **Approval:** none yet. Dispatch needs a CGPT approval comment on Issue #56 that names this path and the immutable commit containing this version (FOUNDRY `standards/work-order-contract.md`, *Approval provenance*).
- **Sandbox entry gate:** not yet accepted for this WO. See `work-orders/CRM-TEST-001-sandbox-annex.md`. If it is missing, the WO is **BLOCKED** before dispatch.

## 1. Authority and governing records

| Item | Value |
|---|---|
| Governing FOUNDRY | `5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0` (`maff0000/foundry`) |
| WO standard | `standards/work-order-contract.md` at that revision, sha256 `cbb6eb3ae62bf7877ae470abf2297a5af5ffb23ca617581a9a85077dd9a8ebcc` |
| Security standards | `standards/secure-engineering.md` and `skills/security-by-design.md` at that revision |
| PIM and amendment | `PROJECT-INITIATION-MANDATE.md` (historical record); `docs/initiation/2026-11-13-existing-product-reassessment.md` (the governing scope amendment, approved and merged in PR #55) |
| Product records | `PRODUCT-VISION.md`, `PRODUCT-BACKLOG.md` and `DECISIONS.md` at `8a40862`, approved by the PO (Issue #54, comment 6852325973) |
| WO naming | Settled by the Architect, 2026-11-13: `CRM-TEST-001`, `CRM-CLIENT-001`, `CRM-FG-001`, `CRM-WIP-001` onward |
| Parent PBI | **Proposed:** CRM-PBI-011 (beta environment readiness). The test protects the CRM-007 r4 beta runtime pin. This WO is also a prerequisite for any later WO (such as CRM-FG-001) claiming a green unit suite. *Architect to confirm (§12, Q1).* |
| PL assignment | `forgev2-pl` (uid 1002), the CRM application PL, as assigned by the Orchestrator (Rogue, root on DOCKER1) after approval |

## 2. Defect and verified facts

All facts below were verified by the Orchestrator on 2026-11-13. No repository or host change was made.

1. **Baseline.** CRM `main` is `8a40862535336dd126d36f82088af7435d2c1931`; the local checkout, `origin/main` and the GitHub API agree.
2. **Reproduction.** The setup was safe and wrote nothing outside the test copy:
   - a `git archive` of `8a40862` was extracted into a fresh directory under `/tmp`, owned by `nobody`;
   - the tests ran as `nobody` with `env -i PATH=/usr/bin:/bin`.
   - Command: `python3 -B -m unittest discover -s tests/unit -p test_beta.py -k TestBetaRuntimePinned -v`.
   - Result: `test_python_guard` passes, and `test_shell_guard` fails at `tests/unit/test_beta.py:578` with `AssertionError: 0 != 2`.
   - The full unit suite gives `Ran 561 tests … FAILED (failures=1, skipped=1)`. The one failure is this test. The skip is `no Git metadata`, an artifact of the `git archive` copy. The load suite gives `Ran 223 tests … OK`.
3. **Host dependency.**
   - The test's no-seam case (`tests/unit/test_beta.py:576-579`) runs `require_target beta` with no `CRM_TEST_ROOT` and no `CRM_RUNTIME_DIR`. It expects exit 2 and `/srv/CRM/runtime/beta` in stderr. Its own comment reads "absent in the sandbox".
   - `pin_beta_runtime` (`scripts/lib/common.sh:77-96`) then sets `CRM_RUNTIME_DIR=/srv/CRM/runtime/beta`.
   - `require_private_runtime` (`scripts/lib/common.sh:101-115`) refuses only a symlink, a non-directory, or a directory whose `stat -c '%u %a'` is not `0 700`.
   - On DOCKER1 the real `/srv/CRM/runtime/beta` exists as a root-owned 0700 directory. Its parents are 0755, so even `nobody` can stat it. The guard therefore correctly accepts the runtime and exits 0.
   - The test fixture's `FAKE_STAT` (`tests/unit/test_beta.py:346-353`) delegates every path outside `FAKE_ROOT_DIR` to the real `stat`. Nothing in the fixture controls the real path.
4. **The sandbox masks the failure.**
   - The ForgeV2 specialists' runs for CRM-009-H and CRM-009-I (2026-11-11, uid 1002 inside the ForgeV2 sandbox) report `tests/unit … Ran 561 tests, OK`. They ran on the same test and the same guard, while the real runtime already existed.
   - Inferred, not proven: the sandboxed filesystem view does not show `/srv/CRM/runtime/beta`. It has not been verified in a sandbox, because preparation may not run one.
   - Consequence: **a specialist inside the sandbox cannot observe the failing host condition.** The host regression in AC4 is therefore an Orchestrator-run, non-root host procedure (§7).
5. **Production is correct.** The guard's behaviour on DOCKER1 is the intended security behaviour. Only the test's assumption is wrong. No production change is needed or permitted.

## 3. Intended outcome

`test_shell_guard` becomes hermetic: its result does not depend on whether `/srv/CRM/runtime/beta` exists on the host, or what its owner and mode are. It still proves the following:
- without the test seam, beta is pinned to `/srv/CRM/runtime/beta`;
- that runtime is refused unless it is a private root-owned directory;
- incorrect runtime paths and seams are refused;
- a valid private test runtime passes;
- dev is unchanged.

## 4. In scope (allowlist)

The Engineer may change only:
- `tests/unit/test_beta.py`

Within that file, the expected change is a narrow fixture correction. The preferred approach follows (the Engineer may choose an equivalent, with the reason recorded):
1. **Extend `FAKE_STAT` with an opt-in variable.** For example, `FAKE_NONROOT_DIR` would make the fake report a non-root uid (such as `1000`) with the path's real mode, for exactly that path. When the variable is unset, `FAKE_STAT` behaves exactly as before, so no other test that uses `ShellEnv` changes behaviour.
2. **Use it in the no-seam case.** Pass `FAKE_NONROOT_DIR=/srv/CRM/runtime/beta` (the production constant) in `test_shell_guard`. The case then presents a deliberately invalid ownership state when the real runtime exists, and refuses as "not a real directory" when it does not. On every host the case asserts:
   - exit code `2`;
   - `refusing to run` in stderr;
   - `/srv/CRM/runtime/beta` in stderr;
   - `RUNTIME=` not in stdout.
3. **Add a defective-guard fixture** (see §6, AC6). This is a new test in the same file. It copies `scripts/lib/common.sh`, `deploy/env.example` and `deploy/beta/env.example` into the test's own temporary directory, keeping the relative layout that `CRM_REPO_DIR` is derived from. It weakens the copy, for example by making `require_private_runtime` return 0 and removing its uid/mode check, then runs the same no-seam case against the copy. It must show that the assertions in item 2 do **not** hold against the weakened guard: the defect is detected. The repository's `scripts/lib/common.sh` is only read, never written.

The PL writes `.forge/CRM-TEST-001/REPORT.md` (the delivery record) at closure. That file is a PL artifact, not Engineer scope.

## 5. Exclusions (no change permitted)

- Production shell guards: `scripts/lib/common.sh` and every other file under `scripts/`.
- Beta runtime path pinning: the `CRM_BETA_RUNTIME` constant, the `CRM_TEST_ROOT` seam rules, and `check_access.beta_runtime`.
- Deployment, release, backup, restore and upgrade scripts; `deploy/`; release bundles.
- CRM application logic or metadata (`custom/`, `config/`), the loader (`load/`), and the FirmGroup and WIP code and documents.
- Every other test file and fixture, including `tests/unit/test_isolation_007r.py` (see §12, Q3).
- The real beta environment: `/srv/CRM/runtime/beta`, its data, env file, permissions and containers. Nothing may read the env file. The real runtime directory's metadata may be stat'ed, read-only, by the Orchestrator's host procedure only.
- Host security controls (the no-firewall-rules policy also applies), `/srv/CRM/deploy`, `/srv/CRM/releases` and `/srv/CRM/runtime`.
- ForgeV2 (`/srv/forgev2`) and FOUNDRY (`/srv/src/foundry`, the `maff0000/foundry` repo). The legacy WIP, Salesforce and ERic are also excluded.
- New dependencies of any kind; only the standard library and the existing test helpers may be used.

**Stop condition:** if the fix genuinely needs a change outside `tests/unit/test_beta.py`, the Engineer stops and reports `BLOCKED` to the PL with technical evidence. The PL escalates to CGPT through the Orchestrator. No workaround is permitted.

## 6. Acceptance criteria

Each criterion needs evidence that names the exact candidate commit.

| # | Criterion | Owner / evidence |
|---|---|---|
| AC1 | **Baseline failure reproduced safely** at the WO base, with nothing written outside a fresh temporary copy. In the sandbox, this is shown by forcing the host condition through the fixture (for example, `FAKE_STAT` reporting `0 700` for the real path through a scratch-only test harness). On DOCKER1 it is the Orchestrator's host procedure (§7) at the base commit. | Engineer (sandbox simulation) and Orchestrator (host). Logs: command, uid, output tail. |
| AC2 | **Host dependency identified:** the evidence names the guard lines, the fixture lines and the real path state (owner, mode, type) that cause the failure. | Engineer report; confirmed by Auditor. |
| AC3 | **Narrow fixture correction:** the diff from the base touches only `tests/unit/test_beta.py`. `FAKE_STAT` is unchanged when the new variable is unset. No assertion of the original test is removed or weakened: exit `2`, `/srv/CRM/runtime/beta` named, the five wrong-path subtests, the private test runtime passing, and the dev case. | Auditor (`git diff --name-status <base> <candidate>`, a reading of the diff). |
| AC4 | **Targeted regression on a host with an existing beta runtime:** with the candidate, on DOCKER1 (where the real runtime exists, root-owned, 0700), `TestBetaRuntimePinned` passes (run as `nobody`, §7). The same run at the base fails as in §2. The real runtime's `stat -c '%u:%g %a %F %Y'` is identical before and after. | Orchestrator host procedure; the record is attached to Issue #56 and the PL record. |
| AC5 | **Full suites:** `python3 -B -m unittest discover -s tests/unit -v` and `python3 -I -B -m unittest discover -s tests/load -t . -v` pass. They are run as non-root, both in the sandbox (Engineer and each reviewer, from a worktree or scratch `git archive`) and on the DOCKER1 host (§7). Reports state the counts. The only acceptable skip is the known `no Git metadata` skip in a `git archive` copy. | Engineer, Tester, DevSecOps, Orchestrator. |
| AC6 | **Negative security assertions preserved and proven sensitive:** (a) the in-suite defective-guard fixture (§4 item 3) passes. (b) **Mutation evidence:** on a scratch copy only, each of these makes `test_shell_guard` or the defective-guard test fail: (i) `require_private_runtime` made a no-op; (ii) the uid/mode comparison removed; (iii) `pin_beta_runtime` made to honour `CRM_RUNTIME_DIR` without the seam; (iv) `FAKE_NONROOT_DIR` ignored by `FAKE_STAT`. On DOCKER1, (ii) is detected because the real runtime exists; in the sandbox, (i), (iii) and (iv) are the deterministic set. | Engineer (mutations), Tester (independent re-run of at least (i) and (iii)), Orchestrator host procedure (ii). |
| AC7 | **Independent Auditor, Tester and DevSecOps PASS** on one unchanged candidate, in the order Engineer → Auditor → Tester → DevSecOps. | Ledger `candidate` equals the SHA each reviewer names. |
| AC8 | **No change to live beta, CRM application code or host security controls:** the diff is limited per AC3. The real runtime's metadata is unchanged (AC4). No process reads `/srv/CRM/runtime/beta/env`. No container, compose or network command runs. | DevSecOps; Orchestrator before/after stat. |
| AC9 | **Provenance:** the completion report gives the base SHA, candidate SHA, final merge SHA, the WO artifact commit and its approval comment, the sandbox-gate acceptance reference, per-role verdicts with their candidate SHA, execution counts, commands and outputs, changed paths, deviations and limitations. gitleaks (the approved build) is clean on `<base>..<candidate>`. | PL. |

## 7. Orchestrator host procedure (AC1, AC4, AC5 and AC6 (ii))

This runs on DOCKER1 as root, but **executes repository code only as `nobody`**. It does not run in the PL account, and never as root. Engineer code never runs in the PL account.
1. Record `stat -c '%u:%g %a %F %Y %n' /srv/CRM/runtime/beta`.
2. For each of `<base>` and `<candidate>`, take a `git archive` into a fresh directory `/tmp/crm-test001-<sha12>`, `chown -R nobody:nogroup`.
3. In each copy, run as `nobody` with `env -i PATH=/usr/bin:/bin HOME=<copy> LANG=C.UTF-8`:
   - the targeted class;
   - the full unit suite;
   - the load suite.
4. For mutation (ii), apply the mutation **only in a third copy** of the candidate, then run the targeted class.
5. Record `stat` again; it must be byte-identical to step 1.
6. Remove the `/tmp` copies.
7. Attach the command lines, uids and output tails to Issue #56 and to the PL record. Do not include any host secret or env content.

## 8. Roles, skills and evidence paths

| Role | Executions | Identity | Evidence written | Readers |
|---|---|---|---|---|
| PL | n/a | `forgev2-pl` (uid 1002) | Ledger `/home/forgev2-pl/.local/state/forgev2/ledgers/3b6369e4f8e78d83/CRM-TEST-001/ledger.json` (authoritative counts and candidate); records `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-TEST-001/` (`prompts/`, `REPORT.md`); repo `.forge/CRM-TEST-001/REPORT.md` at closure | PL, Orchestrator (root) |
| Engineer | ≤ 4 | sandboxed `claude -p` under uid 1002, via `forge-dispatch` | `…/ledgers/…/CRM-TEST-001/dispatch/<n>-engineer.json` | PL, Orchestrator |
| Auditor | ≤ 4 | same, read-only to the worktree | `…/dispatch/<n>-auditor.json` | PL, Orchestrator |
| Tester | ≤ 4 | same, read-only to the worktree | `…/dispatch/<n>-tester.json` | PL, Orchestrator |
| DevSecOps | ≤ 4 | same, read-only to the worktree | `…/dispatch/<n>-devsecops.json` | PL, Orchestrator |
| Orchestrator | n/a | Rogue, root on DOCKER1; repository code runs as `nobody` only | §7 record on Issue #56 | CGPT, PO |

- **Execution limit:** each specialist has a hard maximum of four executions in this WO, including the first. There is no fifth execution and no exception. Counts persist in the ledger across restarts. Exhaustion is a FAIL with its reason. The WO cannot be split, replaced or reopened to reset a counter.
- **Skills:** Python `unittest`; bash; the CRM-007 r4 guard design; secure engineering (fail-closed guards, keeping production code out of scope). Reviewers need no network, credentials or real-environment access.
- **Candidate identity:** the commit SHA at the head of `forge/CRM-TEST-001`, recorded by `forge-ledger` as `candidate`. Each reviewer states the SHA it assessed, and a mismatch is a FAIL. Any Engineer change invalidates earlier PASS results and restarts the sequence.
- **Specialist inputs:** this WO, the two files it names (`tests/unit/test_beta.py`, read-only `scripts/lib/common.sh`) and the FOUNDRY sources in §1. No customer data, credentials or host secrets.

## 9. Real-browser assurance: proposed non-applicability (CGPT decision required)

Proposed rationale: this WO changes one unit-test file.
- There is no change to the application, its UI, metadata, client code, server behaviour, configuration, deployment or data. Nothing a browser can observe changes.
- The behaviour under test is a bash guard run by operators' shell scripts, and its correct verification is the test run itself (AC4 to AC6).
- The Tester's independent assessment is still required: it must re-run the suites and mutations itself, not repeat the Engineer's result.

**Status:** this is a proposal only. It is not presumed approved. Until CGPT records a decision, real-browser assurance remains a dispatch gate.

## 10. Repository and workspace

- **Repository:** `infosec-estateresearch/CRM`, canonical checkout `DOCKER1:/srv/CRM/main` (owned by `forgev2-pl`).
- **Base:** the merge commit on `main` that lands this approved WO version. Its parent on `main` must be `8a40862535336dd126d36f82088af7435d2c1931`, or a later main that the PL re-verifies and reports. Its tree must differ from `8a40862` only by the WO paths. The PL verifies this at the entry gate and records the exact SHA.
- **Branch and worktree:** `forge/CRM-TEST-001` at `DOCKER1:/srv/CRM/worktrees/CRM-TEST-001`. Scratch is `/srv/CRM/worktrees/.forge-scratch/CRM-TEST-001`, created by `forge-start`. Main and every other worktree stay untouched.
- **Engine:** ForgeV2 at `DOCKER1:/srv/forgev2`, revision `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, protected and read-only. FOUNDRY is reference only. No application path overlaps either one.
- **Host:** DOCKER1, the execution and orchestration host. There is no remote route.

## 11. Entry gates, stop conditions and reporting

The PL verifies FOUNDRY entry gates 1 to 11 and records them in the PL record before the first dispatch. The specific dispatch gates for this WO are:
- **G1:** a CGPT exact-version approval of this artifact on Issue #56.
- **G2:** a sandbox entry gate that CGPT accepts as applying to CRM-TEST-001 (annex).
- **G3:** a CGPT decision on the browser non-applicability proposal (§9).
- **G4:** the approved WO merged on `main`, and the base verified (§10).
- **G5:** the engine revision still `63b6b8ab`, with a clean tracked tree (annex §2).

**Stop and report BLOCKED** if any of the following happens:
- a gate fails;
- the candidate needs a path outside the allowlist;
- a specialist reaches four executions without PASS;
- the real runtime's metadata differs before and after;
- any step would read or alter real beta data or configuration.

**Reporting:** progress and escalation go PL → Orchestrator (Rogue) → CGPT, with evidence references on Issue #56. Product questions go to Matt, the PO.

**Completion report:** the outcome, changed paths, base, candidate and merge SHAs, AC1 to AC9 results, per-role verdicts and counts, the §7 record, evidence paths, deviations, limitations and open risks.

## 12. Open questions for the Architect

1. **Parent PBI:** CRM-PBI-011 is proposed (the test protects the beta runtime pin), or record the WO as a cross-cutting quality prerequisite.
2. **Sandbox gate:** whether the run-2 evidence (annex) is sufficient for a narrowly scoped acceptance of this WO.
3. **Latent sibling dependency, kept out of scope:** `tests/unit/test_isolation_007r.py::test_beta_without_the_test_seam_uses_the_real_runtime_and_refuses` relies on `/srv/CRM/runtime/beta/env` being unreadable ("unreadable here, it refuses").
   - It passes for non-root users, but would behave differently if the suite were ever run as root, and would then open the real beta env file.
   - It is not failing, so it is excluded here. CGPT may decide whether to bring it into this WO (a second allowlisted file) or record it as a follow-up. Meanwhile this WO requires that every suite run is non-root.
4. **Host-only evidence:** AC4 depends on the Orchestrator's non-root host procedure (§7), because the sandbox hides the host condition (§2, item 4). Please confirm that this split of evidence is acceptable.
