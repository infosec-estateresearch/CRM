# CRM-TEST-001, round 1 review: tester

- **Candidate:** `f514f55e9143067f92e61ecc806508332f183dde`. **Base:** `c5a8cc3f78aae5f6b100c53ed9430d031e36c441` (main, with the approved WO merged).
- **WO:** `/srv/CRM/main/work-orders/CRM-TEST-001.md`. CGPT approved it at exact commit `7e7c2d0c` (Issue #56, comment 6856984724). The file still reads "v1.2 DRAFT" because the approved artifact is never edited. It is binding. Read §2 to §8.
- **Worktree:** `/srv/CRM/worktrees/CRM-TEST-001`, read-only. **Scratch:** `/srv/CRM/worktrees/.forge-scratch/CRM-TEST-001`. Write only under `<scratch>/work/tester-1/`.
- **PL snapshot (WO §6b):** `<scratch>/snapshot-f514f55e9143/`, with manifest `<scratch>/snapshot-f514f55e9143.sha256`.
  - The manifest's sha256 must be `4f9e21f8e779f4b286b60eb05dfd21b720994db51b69b3406ba7c73a0a489a32` (295 files; the PL cross-checked it against the commit's blobs).
  - Verify it first: check the manifest's sha256, then run `cd <scratch>/snapshot-f514f55e9143 && sha256sum -c --strict --quiet ../snapshot-f514f55e9143.sha256`.
  - Make your own copies with `cp -a <scratch>/snapshot-f514f55e9143/. <scratch>/work/tester-1/<copy>/`. Never write to the snapshot, the worktree, or another role's directory.
- **Diff record (WO §6b, step 6):** `<scratch>/diff-f514f55e9143/`, containing `name-status.txt` (sha256 `ccaf2e9f…84db`) and `diff.patch` (sha256 `87d0c2d2…417c`).
- **Rules:**
  - **Run no `git` command and read no `.git` or `.forge` path.**
  - Do not run as root.
  - Do not read, list or stat anything under `/srv/CRM/runtime`; that is reserved to the Orchestrator.
  - Start no containers and use no network.
  - Run Python tests with `-B` and `PYTHONDONTWRITEBYTECODE=1`.
  - **Clarification on the full unit suite (WO AC5 requires it):** `test_isolation_007r.py::test_beta_without_the_test_seam_uses_the_real_runtime_and_refuses` tries, as its own test code, to open `/srv/CRM/runtime/beta/env`, and refuses because the file is unreadable to a non-root uid. This is the recorded latent dependency (WO §2, item 6). Running the suite as your non-root uid is required and permitted. Do not otherwise read, list or stat `/srv/CRM/runtime`.
- **Engineer's reported deviation:** the Engineer ran one metadata-only `stat` of `/srv/CRM/runtime` and `/srv/CRM/runtime/beta` in the sandbox. It saw `65534:65534` (the overflow uid), and read no content.
- **Host record (Orchestrator, test code run as `nobody`):** `<scratch>/host-record/`. Its sha256 values:
  - `00-stat-before.txt`: `504ce16a…b139`
  - `01-base.txt`: `bf8ee6c2…7ea6`
  - `02-candidate.txt`: `139590a5…f1cf`
  - `03-stat-after.txt`: `504ce16a…b139`

## Assess independently. Run the tests yourself; do not rely on others' results.
- **AC1(b):** in your own `control` copy, show that T-b, T-c and T-d prove the guard branches with synthetic directories. Report the stderr lines.
- **AC5:** in your `control` copy, run
  - `python3 -B -m unittest discover -s tests/unit -v`
  - `python3 -I -B -m unittest discover -s tests/load -t . -v`

  Report the counts. The only acceptable skip is `no Git metadata`.
- **AC6, the final sandbox evidence:** make fresh copies `M1` to `M4` from the snapshot. Apply exactly the WO §6a edits, with proof that each applied exactly once (`grep -c` before and after, and a non-empty `diff` against `control`). For each, run the named test and report its signal. The control copy must pass.
  - Count T-a under M2 as **not** sandbox evidence.
  - For M4, the host-only row is the host record's evidence.
- **AC4: evaluate the host record critically.** Does it show all of the following?
  - the base failing and the candidate passing `TestBetaRuntimePinned` on a host where the real runtime exists;
  - separate immutable copies;
  - execution as `nobody`;
  - identical before and after metadata;
  - the recorded commands, identity and SHAs;
  - M1 to M4 detected on the host, including the host-only rows for M2 and M4.

  State whether it supports AC4, and name any gap. Operator evidence is not, by itself, a PASS.
- **AC7:** the browser test is NOT APPLICABLE, by CGPT's decision. You still own the unit, regression and negative security assessment.

**Blocking findings:**
- any named test that does not detect its mutation with the stated signal;
- a failing suite;
- host evidence that does not support AC4.

Report `VERDICT: PASS | FINDINGS | FAIL`, with the candidate SHA you assessed. Classify each finding as blocking or advisory, and give its evidence. Also list `COMMANDS:`, every shell command you ran.
