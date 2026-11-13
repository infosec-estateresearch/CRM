WO: CRM-TEST-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main
BROWSER: no (NOT APPLICABLE for this exact test-fixture-only scope; CGPT decision, see §9)

# CRM-TEST-001: hermetic `test_shell_guard` (baseline unit-test repair)

- **Version:** v1.2 DRAFT, 2026-11-13. This is not approved. It identifies its own immutable version only by the commit that adds it; approval must name that commit.
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/56
- **Prepared by:** Rogue (Orchestrator), under the CGPT Architect's *Step 2A: Baseline Test Repair Work Order* assignment. That assignment authorises preparation only.
- **History:**
  - v1.0 was commit `1dc7cb3a7869f6160d5ecf52d261132b4e558fd5`.
  - v1.1 answers *CGPT Architect review of `1dc7cb3a`: CHANGES REQUESTED* (2026-11-13, items 1 to 8):
    - AC1 is split between the host and the sandbox;
    - AC6 is replaced by a mutation matrix (§6a);
    - the parent PBI is recorded;
    - the root-run latent defect is recorded and every run is non-root;
    - the conditions for the host evidence are added;
    - browser N/A is recorded;
    - the annex gains a fresh per-WO gate assessment.
  - v1.1 was commit `a8e95319a58e84577d1add09b267ecf81444f6ae`.
  - v1.2 answers *CGPT Architect review of `a8e95319`: CHANGES REQUESTED, one procedural correction* (2026-11-13):
    - specialists no longer use Git; the PL provides a manifest-verified candidate source snapshot (§6b);
    - every sandbox step that relied on specialist Git use is made consistent with that (AC3, AC5, AC6, AC8, §6a, §8);
    - the decisions in that review are recorded in §12.

    The AC1 to AC9 objectives are unchanged.
- **Approval:** none yet. Dispatch needs a CGPT approval comment on Issue #56 that names this path and the immutable commit containing this version (FOUNDRY `standards/work-order-contract.md`, *Approval provenance*).
- **Sandbox entry gate:** not yet accepted for this WO. See `work-orders/CRM-TEST-001-sandbox-annex.md` §7. The CRM-001 acceptance is **not** transferable automatically. If no CRM-TEST-001-specific acceptance exists, the WO is **BLOCKED** before dispatch.

## 1. Authority and governing records

| Item | Value |
|---|---|
| Governing FOUNDRY | `5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0` (`maff0000/foundry`) |
| WO standard | `standards/work-order-contract.md` at that revision, sha256 `cbb6eb3ae62bf7877ae470abf2297a5af5ffb23ca617581a9a85077dd9a8ebcc` |
| Security standards | `standards/secure-engineering.md` (sha256 `dcf3e616…7fa7`) and `skills/security-by-design.md` (sha256 `8a780e63…140a`) at that revision |
| PIM and amendment | `PROJECT-INITIATION-MANDATE.md` (historical record); `docs/initiation/2026-11-13-existing-product-reassessment.md` (the governing scope amendment, approved and merged in PR #55) |
| Product records | `PRODUCT-VISION.md`, `PRODUCT-BACKLOG.md` and `DECISIONS.md` at `8a40862`, approved by the PO (Issue #54, comment 6852325973). No backlog change is needed. |
| WO naming | Settled by the Architect, 2026-11-13: `CRM-TEST-001`, `CRM-CLIENT-001`, `CRM-FG-001`, `CRM-WIP-001` onward |
| Parent PBI | **Primary parent: CRM-PBI-011, beta environment readiness** (the CGPT decision on the v1.0 review, item 3). The test protects the CRM-007 r4 beta runtime pin. **Cross-cutting:** CRM-TEST-001 is a test-integrity prerequisite for CRM-FG-001 and the later WIP implementation WOs, none of which can claim a green unit suite without it. |
| PL assignment | `forgev2-pl` (uid 1002), the CRM application PL, as assigned by the Orchestrator (Rogue, root on DOCKER1) after approval |

## 2. Defect and verified facts

All facts below were verified by the Orchestrator on 2026-11-13. No repository or host change was made.

1. **Baseline.** CRM `main` is `8a40862535336dd126d36f82088af7435d2c1931`; the local checkout, `origin/main` and the GitHub API agree.
2. **Actual host reproduction.** This is already evidenced, for AC1.
   - Setup: a `git archive` of `8a40862` was extracted into a fresh directory under `/tmp`, owned by `nobody`, and the tests ran as `nobody` with `env -i PATH=/usr/bin:/bin`.
   - Command: `python3 -B -m unittest discover -s tests/unit -p test_beta.py -k TestBetaRuntimePinned -v`.
   - Result: `test_python_guard` passes, and `test_shell_guard` fails at `tests/unit/test_beta.py:578` with `AssertionError: 0 != 2`.
   - The full unit suite gives `Ran 561 tests … FAILED (failures=1, skipped=1)`. The one failure is this test. The skip is `no Git metadata`, an artifact of the `git archive` copy. The load suite gives `Ran 223 tests … OK`.
   - The copy was removed afterwards.
3. **Host dependency.**
   - The test's no-seam case (`tests/unit/test_beta.py:576-579`) runs `require_target beta` with no `CRM_TEST_ROOT` and no `CRM_RUNTIME_DIR`. It expects exit 2 and `/srv/CRM/runtime/beta` in stderr. Its own comment reads "absent in the sandbox".
   - `pin_beta_runtime` (`scripts/lib/common.sh:77-96`) then sets `CRM_RUNTIME_DIR=/srv/CRM/runtime/beta`.
   - `require_private_runtime` (`scripts/lib/common.sh:101-115`) checks two things in order:
     1. that the runtime is a real directory and not a symlink (`not a real directory`);
     2. only then, that `stat -c '%u %a'` is `0 700` (`must be owned by root with mode 0700`).
   - On DOCKER1 the real `/srv/CRM/runtime/beta` exists as a root-owned 0700 directory. Its parents are 0755, so even `nobody` can stat it. The guard therefore correctly accepts the runtime and exits 0.
   - The test fixture's `FAKE_STAT` (`tests/unit/test_beta.py:346-353`) delegates every path outside `FAKE_ROOT_DIR` to the real `stat`. Nothing in the fixture controls the real path.
4. **The sandbox masks the failure** (the mechanism is unverified; *corrected in v1.1*).
   - The ForgeV2 specialists' runs for CRM-009-H and CRM-009-I (2026-11-11, uid 1002 inside the ForgeV2 sandbox) report `tests/unit … Ran 561 tests, OK`. They ran on the same test and the same guard, while the real runtime already existed.
   - v1.0 attributed this to the path being invisible in the sandbox. That is not established, and is the less likely explanation:
     - the dispatch sandbox settings deny reads only to the PL's home, its Claude configuration and the ForgeV2 state directory (`forgelib.sandbox_settings` / `private_paths`, engine `63b6b8ab`);
     - a likelier cause is the bubblewrap user namespace, in which root-owned host files appear with an unmapped (overflow) uid, so the guard refuses at its ownership branch.
   - Neither explanation is verified, because preparation may not run a sandbox probe.
   - Consequences:
     - the sandbox cannot reproduce the host's actual accepted state;
     - the actual-host evidence (AC1 host part, AC4) is an Orchestrator-run, non-root host procedure (§7);
     - **the no-seam case's sandbox result is never counted as mutation evidence for the ownership/mode branch** (§6a, M2).
5. **Production is correct.** The guard's behaviour on DOCKER1 is the intended security behaviour. Only the test's assumption is wrong. No production change is needed or permitted.
6. **Separate latent defect (recorded, out of scope, no WO yet).**
   - `tests/unit/test_isolation_007r.py::test_beta_without_the_test_seam_uses_the_real_runtime_and_refuses` relies on `/srv/CRM/runtime/beta/env` being unreadable ("unreadable here, it refuses").
   - **Under root execution the existing test can access the genuine beta env file.**
   - It passes as non-root and is not changed by this WO. It is kept for later bounded remediation (CGPT, v1.0 review item 4).
   - Mitigation inside this WO: **every test execution for CRM-TEST-001 runs as an unprivileged identity.** That means uid 1002 in the sandbox and `nobody` for the Orchestrator's host procedure; never root. No step reads the real beta env file.

## 3. Intended outcome

`test_shell_guard` becomes hermetic. Its result does not depend on any of the following:
- whether `/srv/CRM/runtime/beta` exists;
- how its owner appears (root, as on the host, or an overflow uid, as possibly in the sandbox);
- its mode;
- the identity of the unprivileged runner.

It passes consistently both on DOCKER1 and in the ForgeV2 sandbox. It still proves that:
- without the test seam, beta is pinned to `/srv/CRM/runtime/beta`;
- that runtime is refused unless it is a real, root-owned 0700 directory;
- incorrect runtime overrides and seams are refused at the pinning guard;
- a valid private test runtime passes;
- dev is unchanged.

## 4. In scope (allowlist)

The Engineer may change only:
- `tests/unit/test_beta.py`

Required content. The Engineer may choose equivalent mechanics, with the reason recorded, but not weaker assertions.
1. **Extend `FAKE_STAT` with an opt-in variable, `FAKE_NONROOT_DIR`.** For exactly that path, the fake reports a non-root uid (`1000`) with the path's real mode. This overrides `FAKE_ROOT_DIR` when both match. When the variable is unset, `FAKE_STAT` behaves byte-for-byte as before, so no other `ShellEnv` test changes behaviour.
2. **Change the no-seam case (T-a)** in `test_shell_guard`. Pass `FAKE_NONROOT_DIR=/srv/CRM/runtime/beta` (the production constant). On every host and in the sandbox the case asserts:
   - exit code `2`;
   - `refusing to run` in stderr;
   - `/srv/CRM/runtime/beta` in stderr;
   - `RUNTIME=` not in stdout.

   The refusal arrives through the ownership branch when the directory is visible, or the not-a-real-directory branch when it is absent. Either is a correct refusal; neither is mutation evidence (see §6a).
3. **Strengthen the pinning subtests (T-a′).** The existing override subtests `tmp runtime without seam` and `other runtime` must also assert the pinning guard's own message, `the beta runtime is /srv/CRM/runtime/beta`, so that they can only pass through the pinning branch. The other seam subtests keep their current assertions.
4. **Add a present non-private runtime test (T-b)** in `TestBetaRuntimePinned`. With the seam, the synthetic `$tmp/runtime/beta` is a real directory, and:
   - (i) `FAKE_NONROOT_DIR` names it, so it appears non-root at mode 0700;
   - (ii) `FAKE_ROOT_DIR` covers it and it is `chmod 0750`, so it appears root at mode 0750.

   Each must exit 2, with `must be owned by root with mode 0700` and the synthetic path in stderr, and without `RUNTIME=`. This reaches the ownership/mode branch deterministically, because the directory exists in every context and does not depend on the runner's real uid.
5. **Add a fixture self-test (T-c).** Invoking the fake `stat -c '%u %a'` on a synthetic directory gives `1000 700` with `FAKE_NONROOT_DIR` set to it (also when `FAKE_ROOT_DIR` covers it), and `0 700` with only `FAKE_ROOT_DIR`.
6. **Add a defective-guard fixture (T-d), the in-suite form of M1.**
   - It copies `scripts/lib/common.sh`, `deploy/env.example` and `deploy/beta/env.example` into the test's own temporary directory. It keeps the relative layout from which `CRM_REPO_DIR` is derived.
   - It inserts `return 0` as the first statement of `require_private_runtime` in the copy, and asserts that the substitution happened exactly once.
   - It runs the T-a no-seam case against the copy, and asserts that the T-a refusal does **not** occur: exit 0 and `RUNTIME=/srv/CRM/runtime/beta` printed. In other words, the T-a assertions detect the defect.
   - The repository's `scripts/lib/common.sh` is only read, never written.

The PL writes `.forge/CRM-TEST-001/REPORT.md` (the delivery record) at closure. That file is a PL artifact, not Engineer scope.

## 5. Exclusions (no change permitted)

- Production shell guards: `scripts/lib/common.sh` and every other file under `scripts/`.
- Beta runtime path pinning: the `CRM_BETA_RUNTIME` constant, the `CRM_TEST_ROOT` seam rules, and `check_access.beta_runtime`.
- Deployment, release, backup, restore and upgrade scripts; `deploy/`; release bundles.
- CRM application logic or metadata (`custom/`, `config/`), the loader (`load/`), and the FirmGroup and WIP code and documents.
- Every other test file and fixture, including `tests/unit/test_isolation_007r.py` (§2, item 6).
- The real beta environment: `/srv/CRM/runtime/beta`, its data, env file, permissions and containers. Nothing may read the env file. The real runtime directory's metadata may be stat'ed, read-only, by the Orchestrator's host procedure only.
- Host security controls (the no-firewall-rules policy also applies), `/srv/CRM/deploy`, `/srv/CRM/releases` and `/srv/CRM/runtime`.
- ForgeV2 (`/srv/forgev2`) and FOUNDRY (`/srv/src/foundry`, the `maff0000/foundry` repo). The legacy WIP, Salesforce and ERic are also excluded.
- New dependencies of any kind; only the standard library and the existing test helpers may be used.
- Root execution of any test, by anyone.

**Stop condition:** if the fix genuinely needs a change outside `tests/unit/test_beta.py`, the Engineer stops and reports `BLOCKED` to the PL with technical evidence. The PL escalates to CGPT through the Orchestrator. No workaround is permitted.

## 6. Acceptance criteria

Each criterion needs evidence that names the exact candidate commit. Every execution is non-root (§2, item 6).

| # | Criterion | Owner / evidence |
|---|---|---|
| AC1 | **Baseline failure reproduced, in two separate parts.** **(a) Actual host baseline reproduction:** on DOCKER1, an isolated temporary source copy of the WO base runs as `nobody` (§7) and shows the `0 != 2` failure. This is already evidenced at `8a40862` (§2, item 2) and is repeated at the WO base in §7. **(b) Sandbox negative-path verification:** controlled synthetic directories and fixtures (T-b, T-c, T-d) prove the guard branches involved. This **does not** represent, and is not claimed to reproduce, the host's actual visibility of the beta runtime. No synthetic reproduction of the host condition is required. | (a) Orchestrator. (b) Engineer, then Tester independently. Logs: command, uid, source SHA, output tail. |
| AC2 | **Host dependency identified:** the evidence names the guard lines, the fixture lines and the real path state (owner, mode, type) that cause the failure (§2, item 3). | Engineer report; confirmed by Auditor. |
| AC3 | **Narrow fixture correction:** the diff from the base touches only `tests/unit/test_beta.py`. `FAKE_STAT` is unchanged when `FAKE_NONROOT_DIR` is unset. No original assertion is removed or weakened: exit `2`, `/srv/CRM/runtime/beta` named, the five wrong-path subtests, the private test runtime passing, and the dev case. T-a′ only adds assertions. | Auditor, reading the PL-provided diff record (§6b, step 6), not running Git. |
| AC4 | **Targeted regression on a host with an existing beta runtime.** On DOCKER1 (where the real runtime exists, root-owned, 0700), `TestBetaRuntimePinned` passes with the candidate and fails at the base (§7). The base and candidate run from separate immutable temporary copies, as `nobody`. The real runtime's metadata is identical before and after. Commands, identity, source SHA and outcomes are recorded. **The independent Tester critically evaluates this host record and reports whether it supports AC4.** Operator evidence is not, by itself, a Tester PASS. | Orchestrator (§7 record on Issue #56 and in the PL record). Tester (evaluation). |
| AC5 | **Full suites:** `python3 -B -m unittest discover -s tests/unit -v` and `python3 -I -B -m unittest discover -s tests/load -t . -v` pass. They are run non-root, both in the sandbox and on DOCKER1 (§7). In the sandbox, the Engineer runs them from the worktree, and the Tester and DevSecOps from an unmutated copy of the PL snapshot (§6b). Reports state the counts. The only acceptable skip is the known `no Git metadata` skip in a snapshot or `git archive` copy. The corrected test passes in both contexts. | Engineer, Tester, DevSecOps, Orchestrator. |
| AC6 | **Negative security assertions preserved and proven sensitive:** T-a to T-d pass on the unmutated candidate. Each mutation M1 to M4 in §6a, applied only to a temporary copy, is detected by its named test with the stated signal, in the stated context. Each mutation run is paired with a control run of the same named tests on an unmutated copy of the same candidate in the same context, which must pass. **The final sandbox AC6 evidence is tied to the immutable reviewed candidate through the PL snapshot (§6b).** | Engineer (development diagnostics only, on a working-source copy, §6b step 8). Tester (the final, independent sandbox evidence for M1 to M4, from the PL snapshot). Orchestrator (host, §7). |
| AC7 | **Independent Auditor, Tester and DevSecOps PASS** on one unchanged candidate, in the order Engineer → Auditor → Tester → DevSecOps. The Tester executes and assesses the unit, regression and negative security tests itself. | Ledger `candidate` equals the SHA each reviewer names. |
| AC8 | **No change to live beta, CRM application code or host security controls:** the diff is limited per AC3. The real runtime's metadata is unchanged (AC4). No process reads `/srv/CRM/runtime/beta/env`. No container, compose or network command runs. No test runs as root. Mutations never touch the worktree or the snapshot: the PL verifies, with Git outside the sandbox, that the worktree is clean at the candidate after every review. It also verifies that the snapshot still matches its manifest (§6b, step 7). | DevSecOps (assesses the PL's records); PL (Git and manifest verification); Orchestrator (before/after stat). |
| AC9 | **Provenance:** the completion report gives the base SHA, candidate SHA, final merge SHA, the WO artifact commit and its approval comment, the CRM-TEST-001 sandbox-gate acceptance reference, per-role verdicts with their candidate SHA, execution counts, commands, uids and outputs, the §6a matrix results, the §6b snapshot record (candidate SHA, manifest hash, verifications), changed paths, deviations and limitations. gitleaks (the approved build) is clean on `<base>..<candidate>`. | PL. |

### 6a. Mutation matrix (AC6)

**General rules:**
- Every mutation is applied only to a temporary copy, never to the worktree, the canonical checkout or the production guard.
  - In the sandbox, the copy is made from the PL's candidate source snapshot by a plain file copy, never with Git (§6b).
  - On the host, it is a fresh `/tmp/crm-test001-<sha12>-<Mn>`, owned by `nobody` (§7).
- The person applying a mutation records three things: the exact edit, proof that it applied exactly once (a `grep -c` before and after, and a non-empty `diff` against the unmutated copy), and the named test's output.
- **Control:** a successful run of the same named tests on an unmutated copy is required for every mutation.
- "Detected" means the named test fails with the stated signal. A mutation whose named test passes, or fails for a different reason, is **not** evidence.

| ID | Security property under test | Isolated mutation (in the copy only) | Detecting test (exact) | Expected failure signal | Context |
|---|---|---|---|---|---|
| M1 | The beta runtime must pass `require_private_runtime` (a real, root-owned 0700 directory) before anything runs | Insert `return 0` as the first statement of `require_private_runtime` in `scripts/lib/common.sh` | `TestBetaRuntimePinned.test_shell_guard`, no-seam case (T-a); T-b | T-a: `AssertionError: 0 != 2` (stdout contains `RUNTIME=/srv/CRM/runtime/beta`). T-b: `AssertionError: 0 != 2`. Both fail because no check runs, in every runtime state. | Both: sandbox and host. T-d is the permanent in-suite form. |
| M2 | Ownership uid 0 and mode 0700, checked on a directory **that exists** | Replace the condition `[ "$owner" != "0 700" ]` with `false` in `require_private_runtime` | T-b (i) and (ii): a synthetic, existing runtime under the seam | `AssertionError: 0 != 2` in each T-b sub-case (the existing directory is accepted) | Both. **Additionally on the host:** T-a, because the real directory exists there, also fails with `0 != 2`. In the sandbox, T-a's result under M2 is **not** counted, because its branch is not established (§2, item 4). |
| M3 | Without the seam, beta is pinned and an invalid `CRM_RUNTIME_DIR` override is refused **at the pinning guard** | In `pin_beta_runtime`, replace the override condition `[ -n "${CRM_RUNTIME_DIR:-}" ] && [ "$CRM_RUNTIME_DIR" != "$want" ]` with `false`, and `CRM_RUNTIME_DIR=$want` with `CRM_RUNTIME_DIR=${CRM_RUNTIME_DIR:-$want}`, so that the override is honoured | `test_shell_guard` subtest `tmp runtime without seam` (`CRM_RUNTIME_DIR` = the synthetic private runtime). The override reaches every later guard and is accepted. Also subtest `other runtime`, through the T-a′ message assertion. | `tmp runtime without seam`: `AssertionError: 0 != 2`, `RUNTIME=<synthetic path>` in stdout. `other runtime`: the assertion fails because `the beta runtime is /srv/CRM/runtime/beta` is absent from stderr (it is now refused later, as not a real directory). | Both |
| M4 | Test hermeticity: the fixture really presents the invalid ownership state for the named path | In a copy of `tests/unit/test_beta.py`, remove the `FAKE_NONROOT_DIR` branch from `FAKE_STAT` | T-c (fixture self-test) | `AssertionError: '0 700' != '1000 700'` (or the equivalent for the implemented values); T-b (i) also fails with `0 != 2` | Both. **Additionally on the host:** T-a fails with `0 != 2`, because the real root-owned runtime is then accepted. |

**Limitation, stated rather than claimed as coverage:**
- No mutation and no fixture can make the sandbox present the host's actual accepted runtime state.
- The real-path behaviour is evidenced only by the host procedure (AC1(a), AC4, and the host-only rows for M2 and M4).
- The seam-validation subtests (outside `/tmp`, `..`, missing, symlink) keep their existing coverage. They are not part of the mutation matrix, because a deterministic seam mutation would need a canonical directory outside `/tmp`, which the sandbox cannot provide within scope.

### 6b. Candidate source snapshot for sandbox specialists (v1.2)

Specialists have no Git access under the pinned ForgeV2 boundary. They are **not** given access to Git metadata or Git objects to work around this. Instead, the PL supplies a verified snapshot of the candidate.

1. **When.** After `forge-commit` records the candidate SHA in the ledger, and before the first reviewer dispatch, the PL (`forgev2-pl`, outside the sandbox) creates the snapshot. If the candidate changes, the PL makes a new snapshot of the new SHA, and earlier snapshots are not used as evidence.
2. **How.** `git -C /srv/CRM/worktrees/CRM-TEST-001 archive --format=tar <candidate> -- . ':(exclude).forge' | tar -x -C <scratch>/snapshot-<sha12>/`.
   - `<scratch>` is `/srv/CRM/worktrees/.forge-scratch/CRM-TEST-001`, the WO's permitted project-specific scratch location.
   - `git archive` writes no `.git`.
   - The pathspec excludes `.forge`.
   - The candidate tree holds no secrets, logs or runtime data. The PL verifies this in step 4.
3. **Manifest.**
   - The PL writes the sorted `sha256sum` of every file in the snapshot to `<scratch>/snapshot-<sha12>.sha256`.
   - It cross-checks that manifest against the candidate commit: the file set must equal `git ls-tree -r --name-only <candidate> | grep -v '^\.forge/'` (`ls-tree` does not accept the exclude pathspec), and each file's sha256 must equal that of `git cat-file blob <candidate>:<path>`. There must be no extra or missing files.
   - The authoritative copy of the manifest, its sha256, and the candidate SHA are recorded in the PL record. Specialists cannot read that record.
   - The manifest's sha256 and the candidate SHA are written into every reviewer prompt.
4. **Exclusion check.** No path in the snapshot may be:
   - `.git` or `.forge`;
   - a `*.log` file;
   - an `env` file other than an `*.example` template;
   - under a runtime directory.

   gitleaks (the approved build) must report the snapshot directory clean. If any check fails, the snapshot is not used, and the PL reports BLOCKED.
5. **Use by specialists, without Git.**
   - Each specialist first checks that the manifest's own sha256 equals the value in its prompt. It then runs `sha256sum -c --strict ../snapshot-<sha12>.sha256` from inside `<scratch>/snapshot-<sha12>/`; the manifest uses paths relative to that directory.
   - It then makes its own copies with `cp -a <scratch>/snapshot-<sha12>/. <scratch>/work/<role>-<n>/<copy>/`:
     - one `control` copy;
     - one copy per mutation, `M1` to `M4`.
     - `<n>` is the specialist's execution number.
   - It edits only its own mutation copies.
   - It never writes the snapshot, the worktree, or another specialist's directory, and never uses another specialist's copies as evidence.
   - Each mutation copy is independent of the candidate worktree and of every other copy.
6. **Diff record for review.**
   - The PL also writes `git diff --name-status <base> <candidate>` and `git diff <base> <candidate>` to `<scratch>/diff-<sha12>/`, with their sha256 recorded in the PL record and in the prompts.
   - The Auditor (AC3) and DevSecOps (AC8) assess the diff from this record. They do not run Git.
7. **PL verification after each review.** With Git outside the sandbox, the PL checks that:
   - the worktree HEAD equals the candidate, and `git status --porcelain` is empty;
   - `sha256sum -c` of the authoritative manifest still passes on the snapshot.

   A mismatch voids that review's evidence. It is reported, and the review does not count as a PASS.
8. **Engineer development diagnostics.**
   - Before a candidate is committed, the Engineer may copy its working files (not `.git` or `.forge`) into `<scratch>/dev/engineer-<n>/` and run mutations there, for diagnosis only.
   - These results are not final AC6 evidence. The final sandbox AC6 evidence comes from the Tester's runs on the PL snapshot of the immutable reviewed candidate.
9. **Cleanup.**
   - At closure, the PL archives the snapshot manifest and the specialists' reported results in the PL record.
   - It then removes `<scratch>/snapshot-*`, `<scratch>/work/` and `<scratch>/dev/`.

## 7. Orchestrator host procedure (AC1(a), AC4, AC5 host, AC6 host)

This runs on DOCKER1. Rogue performs the steps as root, but **all test code executes only as `nobody`**, never as root, and never in the PL account. Engineer code never runs in the PL account. Nothing reads `/srv/CRM/runtime/beta/env` or any other file inside the runtime.
1. Record `stat -c '%u:%g %a %F %Y %n' /srv/CRM/runtime/beta` (the directory's metadata only).
2. Create **separate immutable copies**: for each of `<base>` and `<candidate>`, take `git archive <sha>` into a fresh `/tmp/crm-test001-<sha12>` and `chown -R nobody:nogroup`. Record the source SHA of each copy. The copies are never edited.
3. In each copy, run as `nobody` with `env -i PATH=/usr/bin:/bin HOME=<copy> LANG=C.UTF-8`, recording the full command line, `id` output, SHA and exit status:
   - the targeted class `TestBetaRuntimePinned`;
   - the full unit suite;
   - the load suite.
4. For each of M1 to M4, use a further fresh copy of the candidate `/tmp/crm-test001-<sha12>-<Mn>`. Apply the §6a edit there only, with proof that it applied exactly once, and run the named test as `nobody`.
5. Record `stat` again; it must be byte-identical to step 1. If it differs, report **BLOCKED**.
6. Remove all `/tmp` copies.
7. Attach the record to Issue #56 and to the PL record: commands, identity, SHAs, outcomes and output tails, with no host secret or env content.

The Tester receives this record and evaluates it critically (AC4).

## 8. Roles, skills and evidence paths

| Role | Executions | Identity | Evidence written | Readers |
|---|---|---|---|---|
| PL | n/a | `forgev2-pl` (uid 1002) | Ledger `/home/forgev2-pl/.local/state/forgev2/ledgers/3b6369e4f8e78d83/CRM-TEST-001/ledger.json` (authoritative counts and candidate); records `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-TEST-001/` (`prompts/`, `REPORT.md`, the §7 record); repo `.forge/CRM-TEST-001/REPORT.md` at closure | PL, Orchestrator (root) |
| Engineer | ≤ 4 | sandboxed `claude -p` under uid 1002, via `forge-dispatch` | `…/ledgers/…/CRM-TEST-001/dispatch/<n>-engineer.json` | PL, Orchestrator |
| Auditor | ≤ 4 | same, read-only to the worktree (it can write scratch) | `…/dispatch/<n>-auditor.json` | PL, Orchestrator |
| Tester | ≤ 4 | same, read-only to the worktree (it can write scratch) | `…/dispatch/<n>-tester.json` | PL, Orchestrator |
| DevSecOps | ≤ 4 | same, read-only to the worktree (it can write scratch) | `…/dispatch/<n>-devsecops.json` | PL, Orchestrator |
| Orchestrator | n/a | Rogue, root on DOCKER1; test code runs as `nobody` only | §7 record on Issue #56 and in the PL record | CGPT, PO, Tester (through the PL prompt) |

- **Execution limit:** each specialist has a hard maximum of four executions in this WO, including the first. There is no fifth execution and no exception. Counts persist in the ledger across restarts. Exhaustion is a FAIL with its reason. The WO cannot be split, replaced or reopened to reset a counter.
- **Skills:** Python `unittest`; bash; the CRM-007 r4 guard design; mutation testing on isolated copies; secure engineering (fail-closed guards, keeping production code out of scope). Reviewers need no network, credentials or real-environment access.
- **Candidate identity:** the commit SHA at the head of `forge/CRM-TEST-001`, recorded by `forge-ledger` as `candidate`. Each reviewer states the SHA it assessed, and a mismatch is a FAIL. Any Engineer change invalidates earlier PASS results and restarts the sequence.
- **Specialist inputs:** this WO; `tests/unit/test_beta.py`; `scripts/lib/common.sh` as read-only; the FOUNDRY sources in §1. Reviewers also receive the §6b snapshot, its manifest hash and the diff record, and the Tester also receives the §7 host record. Specialists receive no Git access. No customer data, credentials or host secrets.

## 9. Real-browser assurance: NOT APPLICABLE (CGPT decision)

- **Decision:** CGPT Architect review of v1.0 (`1dc7cb3a`), item 6, 2026-11-13: *"For this exact test-fixture-only scope, real-browser testing is NOT APPLICABLE. Rationale: no UI, application behaviour, runtime configuration or deployment changes are permitted."*
- **Conditions:**
  - The independent Tester must still execute and assess the applicable unit, regression and negative security tests (AC4 to AC7).
  - **The decision lapses if the scope expands beyond the permitted test fixture.**
  - It must be recorded on Issue #56, through the CGPT approval of this exact version, so that the GitHub record is traceable.

## 10. Repository and workspace

- **Repository:** `infosec-estateresearch/CRM`, canonical checkout `DOCKER1:/srv/CRM/main` (`forgev2-pl`, 0750).
- **Base:** the merge commit on `main` that lands this approved WO version. Its parent on `main` must be `8a40862535336dd126d36f82088af7435d2c1931`, or a later main that the PL re-verifies and reports. Its tree must differ from `8a40862` only by the WO paths. The PL verifies this at the entry gate and records the exact SHA.
- **Branch and worktree:** `forge/CRM-TEST-001` at `DOCKER1:/srv/CRM/worktrees/CRM-TEST-001`. Scratch is `/srv/CRM/worktrees/.forge-scratch/CRM-TEST-001`, created by `forge-start`. Main and every other worktree stay untouched.
- **Engine:** ForgeV2 at `DOCKER1:/srv/forgev2`, revision `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, protected and read-only. FOUNDRY is reference only. No application path overlaps either one.
- **Host:** DOCKER1, the execution and orchestration host. There is no remote route.

## 11. Entry gates, stop conditions and reporting

The PL verifies FOUNDRY entry gates 1 to 11 and records them in the PL record before the first dispatch. The specific dispatch gates for this WO are:
- **G1:** a CGPT exact-version approval of this artifact on Issue #56.
- **G2:** an explicit CGPT acceptance of the sandbox entry gate **specific to CRM-TEST-001**, after it reviews the annex §7 assessment. The run-2 evidence may be reused as its basis, but the CRM-001 acceptance is not automatically transferable.
- **G3:** browser NOT APPLICABLE. This is decided (§9), but it must be recorded on GitHub with G1.
- **G4:** the approved WO merged on `main`, and the base verified (§10).
- **G5:** the engine revision still `63b6b8ab`, with a clean tracked tree, re-checked read-only with `GIT_OPTIONAL_LOCKS=0`. The Claude Code version, Claude binary hash and bubblewrap hash must also equal the annex §7 values. `FORGE_CLAUDE` must be unset, and no CRM-TEST-001 spawn event may carry a `claude` override (annex §7.7).

**Stop and report BLOCKED** if any of the following happens:
- a gate fails;
- the candidate needs a path outside the allowlist;
- a specialist reaches four executions without PASS;
- the real runtime's metadata differs before and after;
- any step would read or alter real beta data or configuration;
- any test would run as root.

**Reporting:** progress and escalation go PL → Orchestrator (Rogue) → CGPT, with evidence references on Issue #56. Product questions go to Matt, the PO.

**Completion report:** the outcome, changed paths, base, candidate and merge SHAs, AC1 to AC9 and §6a results, per-role verdicts and counts, the §7 record and the Tester's evaluation of it, evidence paths, deviations, limitations and open risks.

## 12. Architect decisions recorded (v1.0 review) and open items

**Decided:**
- Parent PBI CRM-PBI-011, cross-cutting (§1).
- `test_isolation_007r.py` is out of scope; the latent defect is recorded and all runs are non-root (§2, item 6).
- The host-only evidence is owned by Rogue, under the §7 conditions, and the Tester evaluates it (AC4).
- Browser is N/A (§9).
- Run-2 may be reused as the basis for a CRM-TEST-001-specific sandbox decision (annex §7).

**Decided in the v1.1 review (`a8e95319`):**
- The scope, ACs, host procedure and the M1 to M4 matrix are accepted in principle.
- Browser NOT APPLICABLE is confirmed for this exact scope.
- The run-2 evidence is sufficient as the basis for a narrowly bounded, CRM-TEST-001-only sandbox acceptance, conditional on the G5 checks. No new smoke test or ForgeV2 change is needed.
- The root-created bytecode cache is accepted as a documented, non-blocking deviation for this WO only; its creation remains a recorded boundary lapse.
- The missing run-2 Claude binary hash is an accepted evidence limitation, not a claim of cryptographic continuity.
- The specialist snapshot procedure is corrected in §6b.

**Open:**
- G1: exact-version approval of this version (CGPT).
- G2: the explicit CRM-TEST-001 sandbox acceptance recorded on Issue #56 (CGPT). G5 is then verified in the actual dispatch environment, and if any check fails, the WO is BLOCKED.
