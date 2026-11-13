# CRM-TEST-001, round 1, Tester reassessment: final host evidence (execution 2 of 4)

CGPT has authorised this one narrowly targeted reassessment. **The candidate is unchanged** from your first execution.

- **Candidate:** `f514f55e9143067f92e61ecc806508332f183dde`. **Base:** `c5a8cc3f78aae5f6b100c53ed9430d031e36c441`.
- **WO:** `/srv/CRM/main/work-orders/CRM-TEST-001.md`, approved at `7e7c2d0c`. The binding parts for this task are §7 and AC4/AC5/AC6/AC8.
- **Scratch:** `/srv/CRM/worktrees/.forge-scratch/CRM-TEST-001`. Write only under `<scratch>/work/tester-2/`, if you need to write at all.
- **Snapshot identity, to confirm the candidate is unchanged:**
  - manifest `<scratch>/snapshot-f514f55e9143.sha256`, whose sha256 must be `4f9e21f8e779f4b286b60eb05dfd21b720994db51b69b3406ba7c73a0a489a32`;
  - run `cd <scratch>/snapshot-f514f55e9143 && sha256sum -c --strict --quiet ../snapshot-f514f55e9143.sha256`.
- **Host record:** `<scratch>/host-record/`. The file under assessment is **`04-addendum-complete-rerun.txt`** (sha256 `aa8b411e4989b2a269a479f3c21230d1bd6b51f691bd5d20e0388b1491870731`), the Orchestrator's complete-transcript re-run of the §7 procedure. Files `00` to `03` are the first record, which you have already assessed.

## Rules
- **Run no `git`.** Read no `.git` or `.forge` path; do not even list it.
- Do not run as root.
- Do not read, list or stat anything under `/srv/CRM/runtime`.
- Start no containers and use no network.
- You do not need to re-run the suites or mutations. You may re-run any part in your own copy if it helps your assessment.

## Assess `04` critically, against WO §7 and AC4
1. **Base and candidate:** the base `c5a8cc3f` fails `TestBetaRuntimePinned`, and the candidate `f514f55e` passes it.
2. **Identity and outcomes:** for every test execution, check the exact identity (`id` output) and the command line with its `runuser -u nobody -- env -i …` wrapper, the exit status and the timestamps.
3. **Full results:** the complete unit and load results for both the base and the candidate, including counts and skip reasons.
4. **Mutations:** M1 to M4 must each be applied exactly once, in a separate fresh copy, with a diff against the unmutated candidate copy and the expected failure signals (WO §6a), including the host-only rows for M2 and M4.
5. **Runtime metadata:** the real runtime metadata must be identical before and after.
6. **Non-root execution:** check for evidence that all actual test execution was non-root. Root is used only to create, `chown` and remove the copies.
7. **Copies:** they must be separate, immutable `git archive` copies, recorded by command and SHA. Cleanup must be recorded.
8. **Consistency:** check that `04` agrees with `00` to `03` and with your own round 1 sandbox results. Note any gap or inconsistency, for example that the host copies include `.forge`.

Report `VERDICT: PASS | FAIL`, with the reasoning and the exact candidate SHA. Classify each finding as blocking or advisory, with evidence. List `COMMANDS:`, every shell command you ran.
