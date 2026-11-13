# CRM-TEST-001, round 1: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-TEST-001`, branch `forge/CRM-TEST-001`. The PL has verified that HEAD is `c5a8cc3f78aae5f6b100c53ed9430d031e36c441` (main, with the approved WO merged) and that the worktree is clean. Do not modify `.forge/`. **Do not run `git` and do not read any `.git` file or directory**: under this WO, specialists use no Git (WO §6b). The PL commits your change.
- **Scratch:** `/srv/CRM/worktrees/.forge-scratch/CRM-TEST-001`. Use only `<scratch>/dev/engineer-1/` for your own copies.
- **Work order:** `/srv/CRM/main/work-orders/CRM-TEST-001.md` v1.2, which is CGPT-approved at `7e7c2d0c`. Read §2 to §6b. It is binding.

## Task
1. **Allowlist:** change only `tests/unit/test_beta.py`, implementing WO §4 items 1 to 6:
   - `FAKE_NONROOT_DIR` in `FAKE_STAT`. It reports `1000 <real mode>` for exactly that path and takes precedence over `FAKE_ROOT_DIR`. When it is unset, behaviour is byte-for-byte unchanged.
   - **T-a:** the no-seam case with `FAKE_NONROOT_DIR=/srv/CRM/runtime/beta`, asserting exit 2, `refusing to run`, `/srv/CRM/runtime/beta` in stderr, and no `RUNTIME=`.
   - **T-a′:** the pinning message assertion `the beta runtime is /srv/CRM/runtime/beta` on the `tmp runtime without seam` and `other runtime` subtests.
   - **T-b:** a present, non-private synthetic runtime under the seam: (i) via `FAKE_NONROOT_DIR`, and (ii) as fake-root with mode 0750.
   - **T-c:** a fixture self-test of the fake `stat`.
   - **T-d:** a defective-guard fixture working on temporary copies of `scripts/lib/common.sh`, `deploy/env.example` and `deploy/beta/env.example`. It must assert that the `return 0` substitution happened exactly once.

   No assertion of the original test may be removed or weakened. `scripts/`, `deploy/` and every other file are read-only to you. If the fix genuinely needs any other path, stop and report `STATUS: blocked` with evidence.
2. **Tests:** run them as your own non-root uid, with `PYTHONDONTWRITEBYTECODE=1`, from the worktree:
   - `python3 -B -m unittest discover -s tests/unit -v`
   - `python3 -I -B -m unittest discover -s tests/load -t . -v`
   - and `-k TestBetaRuntimePinned` on its own.

   Report the counts. Report, verbatim, the stderr line that the T-a case produces in your sandbox, so we know which guard branch refused it.
3. **AC1(b) and AC2:**
   - Show that T-b, T-c and T-d prove the guard branches with synthetic directories.
   - Name the guard lines and fixture lines involved in the host dependency (WO §2, item 3).
4. **Development diagnostics only (WO §6b, step 8):**
   - Copy the worktree without `.git` or `.forge`, for example: `tar -C /srv/CRM/worktrees/CRM-TEST-001 --exclude=./.git --exclude=./.forge -cf - . | tar -x -C <scratch>/dev/engineer-1/<copy>`.
   - Make one `control` copy and one copy each for M1 to M4.
   - Apply exactly the WO §6a edits to the mutation copies. For each, show proof that it applied exactly once (`grep -c` before and after, and a non-empty `diff` against `control`), and the named test's result. The control must pass.
   - These results are diagnostics, not final AC6 evidence.
5. **Do not:**
   - run anything as root;
   - read `/srv/CRM/runtime/beta/env` or any file inside `/srv/CRM/runtime`;
   - start containers;
   - use the network;
   - add dependencies.
6. **Time box:** 40 minutes.

## Final message
- `STATUS: completed | blocked`
- `CHANGED:` the paths you changed
- `TESTS:` the exact commands, the uid, and the counts
- `T-a STDERR:` the verbatim line
- `MUTATIONS:` M1 to M4, each with the edit, the applied-once proof, the named test and its signal, and the control result
- `COMMANDS:` a complete list of the shell commands you ran, which must include no `git`
- `NOTES:` deviations or limitations
