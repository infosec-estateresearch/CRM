# CRM-TEST-001, round 1 review: devsecops

- **Candidate:** `f514f55e9143067f92e61ecc806508332f183dde`. **Base:** `c5a8cc3f78aae5f6b100c53ed9430d031e36c441` (main, with the approved WO merged).
- **WO:** `/srv/CRM/main/work-orders/CRM-TEST-001.md`. CGPT approved it at exact commit `7e7c2d0c` (Issue #56, comment 6856984724). The file still reads "v1.2 DRAFT" because the approved artifact is never edited. It is binding. Read §2 to §8.
- **Worktree:** `/srv/CRM/worktrees/CRM-TEST-001`, read-only. **Scratch:** `/srv/CRM/worktrees/.forge-scratch/CRM-TEST-001`. Write only under `<scratch>/work/devsecops-1/`.
- **PL snapshot (WO §6b):** `<scratch>/snapshot-f514f55e9143/`, with manifest `<scratch>/snapshot-f514f55e9143.sha256`.
  - The manifest's sha256 must be `4f9e21f8e779f4b286b60eb05dfd21b720994db51b69b3406ba7c73a0a489a32` (295 files; the PL cross-checked it against the commit's blobs).
  - Verify it first: check the manifest's sha256, then run `cd <scratch>/snapshot-f514f55e9143 && sha256sum -c --strict --quiet ../snapshot-f514f55e9143.sha256`.
  - Make your own copies with `cp -a <scratch>/snapshot-f514f55e9143/. <scratch>/work/devsecops-1/<copy>/`. Never write to the snapshot, the worktree, or another role's directory.
- **Diff record (WO §6b, step 6):** `<scratch>/diff-f514f55e9143/`, containing `name-status.txt` (sha256 `ccaf2e9f…84db`) and `diff.patch` (sha256 `87d0c2d2…417c`).
- **Rules:**
  - **Run no `git` command and read no `.git` or `.forge` path.**
  - Do not run as root.
  - Do not read, list or stat anything under `/srv/CRM/runtime`; that is reserved to the Orchestrator.
  - Start no containers and use no network.
  - Run Python tests with `-B` and `PYTHONDONTWRITEBYTECODE=1`.
  - **Clarification on the full unit suite (WO AC5 requires it):** `test_isolation_007r.py::test_beta_without_the_test_seam_uses_the_real_runtime_and_refuses` tries, as its own test code, to open `/srv/CRM/runtime/beta/env`, and refuses because the file is unreadable to a non-root uid. This is the recorded latent dependency (WO §2, item 6). Running the suite as your non-root uid is required and permitted. Do not otherwise read, list or stat `/srv/CRM/runtime`.
- **Engineer's reported deviation:** the Engineer ran one metadata-only `stat` of `/srv/CRM/runtime` and `/srv/CRM/runtime/beta` in the sandbox. It saw `65534:65534` (the overflow uid), and read no content.

- **Host record (Orchestrator):** `<scratch>/host-record/`. After the Tester's review, the Orchestrator added `04-addendum-complete-rerun.txt` (sha256 `aa8b411e…0731`), a complete-transcript re-run of the same procedure. It answers the Tester's advisory about record completeness. Read it for AC8: test code ran as `nobody` only, and the real runtime metadata is identical before and after.

## Assess
- **AC8 and security:** using the diff record and a reading of the snapshot, confirm:
  - no production guard, script, deployment or application change;
  - no new dependency;
  - nothing that would make a test read the real beta env file or run as root;
  - no network use;
  - nothing that weakens the CRM-007 r4 runtime pinning.
- Confirm that the new fixture (`FAKE_NONROOT_DIR`) can only make the guard stricter in tests, never accept something it would otherwise refuse.
- Confirm that T-d writes only to its own temporary copy.
- Run gitleaks (`/usr/local/bin/gitleaks dir --no-banner --redact <path>`) on the snapshot and on `diff.patch`.
- In a `control` copy, run the unit and load suites as your own non-root uid, and report the counts.
- Assess the Engineer's reported deviation (a metadata-only stat of `/srv/CRM/runtime/beta` in the sandbox) and classify it.

**Blocking findings:**
- any weakening of a security guard;
- any path to root execution or to an env-file read;
- a secret;
- a change outside the allowlist.

Report `VERDICT: PASS | FINDINGS | FAIL`, with the candidate SHA you assessed. Classify each finding as blocking or advisory, and give its evidence. Also list `COMMANDS:`, every shell command you ran.
