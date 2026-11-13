# CRM-TEST-001, round 1 review: auditor

- **Candidate:** `f514f55e9143067f92e61ecc806508332f183dde`. **Base:** `c5a8cc3f78aae5f6b100c53ed9430d031e36c441` (main, with the approved WO merged).
- **WO:** `/srv/CRM/main/work-orders/CRM-TEST-001.md`. CGPT approved it at exact commit `7e7c2d0c` (Issue #56, comment 6856984724). The file still reads "v1.2 DRAFT" because the approved artifact is never edited. It is binding. Read §2 to §8.
- **Worktree:** `/srv/CRM/worktrees/CRM-TEST-001`, read-only. **Scratch:** `/srv/CRM/worktrees/.forge-scratch/CRM-TEST-001`. Write only under `<scratch>/work/auditor-1/`.
- **PL snapshot (WO §6b):** `<scratch>/snapshot-f514f55e9143/`, with manifest `<scratch>/snapshot-f514f55e9143.sha256`.
  - The manifest's sha256 must be `4f9e21f8e779f4b286b60eb05dfd21b720994db51b69b3406ba7c73a0a489a32` (295 files; the PL cross-checked it against the commit's blobs).
  - Verify it first: check the manifest's sha256, then run `cd <scratch>/snapshot-f514f55e9143 && sha256sum -c --strict --quiet ../snapshot-f514f55e9143.sha256`.
  - Make your own copies with `cp -a <scratch>/snapshot-f514f55e9143/. <scratch>/work/auditor-1/<copy>/`. Never write to the snapshot, the worktree, or another role's directory.
- **Diff record (WO §6b, step 6):** `<scratch>/diff-f514f55e9143/`, containing `name-status.txt` (sha256 `ccaf2e9f…84db`) and `diff.patch` (sha256 `87d0c2d2…417c`).
- **Rules:**
  - **Run no `git` command and read no `.git` or `.forge` path.**
  - Do not run as root.
  - Do not read, list or stat anything under `/srv/CRM/runtime`; that is reserved to the Orchestrator.
  - Start no containers and use no network.
  - Run Python tests with `-B` and `PYTHONDONTWRITEBYTECODE=1`.
- **Engineer's reported deviation:** the Engineer ran one metadata-only `stat` of `/srv/CRM/runtime` and `/srv/CRM/runtime/beta` in the sandbox. It saw `65534:65534` (the overflow uid), and read no content.

## Assess
- **AC2:** is the host dependency correctly identified? Check the guard lines (`scripts/lib/common.sh`, read it from the snapshot) and the fixture lines.
- **AC3:** from the diff record, confirm that only `tests/unit/test_beta.py` changed.
  - `FAKE_STAT` must be byte-for-byte unchanged when `FAKE_NONROOT_DIR` is unset.
  - No assertion of the original `test_shell_guard` may be removed or weakened: exit 2, `/srv/CRM/runtime/beta` named, the five wrong-path subtests, the private test runtime passing, and dev unchanged.
  - T-a′ may only add assertions.
- **WO §4 items 1 to 6:** confirm they are implemented as specified, including T-b reaching the ownership branch on an existing directory, T-c, and T-d's exactly-once substitution with the repository's `common.sh` left untouched.
- **Scope and hygiene:** no change to production behaviour; no new dependencies; no customer data, secrets or IPs added.
- **Tests:** run `TestBetaRuntimePinned` once yourself, in a `control` copy of the snapshot.

**Blocking findings:**
- a weakened or removed original assertion;
- a change outside the allowlist;
- a fixture change that alters behaviour when `FAKE_NONROOT_DIR` is unset;
- a T-b, T-c or T-d that is vacuous.

Report `VERDICT: PASS | FINDINGS | FAIL`, with the candidate SHA you assessed. Classify each finding as blocking or advisory, and give its evidence. Also list `COMMANDS:`, every shell command you ran.
