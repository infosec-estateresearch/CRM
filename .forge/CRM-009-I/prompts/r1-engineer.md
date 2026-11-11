# CRM-009-I, round 1: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-009-I`, branch `forge/CRM-009-I`. The expected HEAD is `c3c0fefbac3a45360325b1ccb4e0cd56fc63525b` (main, with the WO merged). Confirm it first. Do not modify `.forge/`.
- **Work order:** `/srv/CRM/main/work-orders/CRM-009-I.md` v1.0. Its facts were verified live by the PL. Keep to the allowlist.
- **Time box:** 30 minutes. Run the unit and load suites as a non-root user (`python3 -I -B -m unittest discover -s tests/load -t .`). Report `STATUS: completed`.

Give exact counts and mutation evidence for each change item, and use the Engineer final message format.
