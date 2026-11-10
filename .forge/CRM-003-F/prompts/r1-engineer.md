# CRM-003-F, round 1: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-003-F`, branch `forge/CRM-003-F`. The expected HEAD is `a34a9516005e899c916675e9aa15b4933150370b`, the CRM-006S delivery record. Confirm it first. Do not modify `.forge/`.
- **Work order:** `/srv/CRM/main/work-orders/CRM-003-F.md` v1.0. It is small. Keep strictly to its allowlist.
- The facts in the WO were verified live by the PL. Change nothing in `roles.json` except `Currency`.
- **Time box:** 30 minutes. Report `STATUS: completed`, with Known gaps if there are any.

Run both suites (`python3 -m unittest discover -s tests/unit`; `python3 -I -B -m unittest discover -s tests/load -t .`), report exact counts, and give mutation evidence: putting back `read: all` on Currency fails the suite, and so does an unknown action such as `delete` on Currency. Also show `git diff --stat` and the `roles.json` diff. Finish in the Engineer final message format.
