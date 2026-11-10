# CRM-003, round 2: Engineer (continuation after a timeout)

Your round-1 run hit the 30-minute limit before it returned a result. **Your work is still in the worktree, uncommitted**:
- `custom/` changes;
- `config/access/`;
- `scripts/provision_access.py` and `scripts/provision_users.py`;
- `docs/ACCESS.md`;
- the README;
- `tests/unit/**` and `tests/acceptance/**`.

- **Worktree:** `/srv/CRM/worktrees/CRM-003`. The expected HEAD is `39b7cb5213de31aafdaea5c22fab63d3f664a0d8`, with a dirty working tree. Do not modify `.forge/`. Do **not** discard or restart the existing work.
- **Specification:** the round-1 brief, with the WO quoted verbatim and the verified EspoCRM facts, unchanged. The scope allowlist is unchanged.

## Task: finish, verify and report, all within about 20 minutes
1. Run `python3 -m unittest discover -s tests/unit -v` immediately. Fix the failures. **Every CRM-001 test must still pass.**
2. Check the WO Change items 1–8 and AC1–AC8 for anything still missing, and close the gaps **minimally**. Leave out anything non-essential and list it under "Known gaps". Don't keep polishing.
3. Run `bash -n` on every script and `git status --short --untracked-files=all`, and confirm that only allowlisted paths changed.
4. **Return your final message before you run out of time.** If you're near the limit, stop and report the exact state.

## Constraints (unchanged)
No network, no Docker, no root, no php. Standard library only. Synthetic data only. No secrets, real names or IPs.

Finish in the Engineer final message format. Include the exact test counts (before and after) and non-vacuity evidence.
