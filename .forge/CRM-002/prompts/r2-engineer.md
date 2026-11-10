# CRM-002, round 2: Engineer (continuation after a timeout)

Your round-1 run hit the 30-minute limit before it returned a result. **Your work is still in the worktree, uncommitted.** About 7,400 lines are in place:
- `migrate/` (the contract, plus `auth`, `client`, `cli`, `contract`, `extract`, `hostcheck`, `log`, `manifest`, `metadata`, `policy`, `reconcile`, `selftest`, `synthetic` and `transport`);
- `deploy/migrate/`;
- `scripts/migrate.sh`;
- `docs/MIGRATION.md`;
- the register entry;
- 11 test modules under `tests/migrate/`.

- **Worktree:** `/srv/CRM/worktrees/CRM-002`. The expected HEAD is `fa1ed80eed749cb2c0e7908ff72ad60a793e3e24`, with a dirty working tree. Do not modify `.forge/`. Do **not** discard or restart the existing work.
- **Specification:** `work-orders/CRM-002.md` v1.2 in the worktree, and the round-1 brief, both unchanged. The scope allowlist is unchanged.

## Task: finish, verify and report, all within about 20 minutes
1. Run `python3 -I -B -m unittest discover -s tests/migrate -t . -v` immediately. Fix the failures.
2. Check the WO for anything still missing, and close the gaps **minimally**. Check in particular:
   - AC6, the mutation hooks: update, insert, soft delete, permanent delete, merge, late-visible row, continuous drift → `RECONCILED_WITH_DRIFT`, and a mismatch → `INCOMPLETE`;
   - AC7, the deletion classes;
   - AC9, the isolated-mode subprocess test with a planted `crm_migrate/` and `json.py`;
   - AC10, the Compose and hostcheck policy, each with a broken fixture.

   Leave out anything non-essential, and list what you left out under "Known gaps". Don't keep polishing.
3. Run `bash -n scripts/migrate.sh` and `git status --short`, and confirm that only allowlisted paths changed.
4. **Return your final message before you run out of time.** If you're near the limit, stop and report the exact state. A partial, honest report beats no report.

## Constraints (unchanged)
No network, no loopback, no Docker, no root. Standard library only. Synthetic data only. No secrets, real hostnames or IPs.

Finish in the Engineer final message format. Include the exact test counts and non-vacuity evidence.
