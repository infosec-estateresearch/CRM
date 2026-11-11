# CRM-008-G, round 3: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-008-G`. HEAD should be `9f8fa1e747a9c7cd335c06ae7c8f39762cfa6cba`; confirm it.
- **Same rules and box.** Report `STATUS: completed`.

## Blocking (all reviewers): the stamp code is lost on rerun re-completion and on resume
1. Staff reopen a no-date Completed Task. The importer rerun PUTs status Completed, core stamps the rerun time, and no code is recorded.
2. A run is interrupted after it POSTs a no-date Completed Task. `--resume` finds it in the index, the code is never recorded, and the resumed report differs from a clean one.

**PL decision: make the rule state-based.** After the upsert, on **every** run, record `date_completed_server_stamped` (record id only) for each Task or email-as-Task whose stored state is Completed with `sfCompletedAt` null.
- Count only records that were actually stored, or already exist and were not refused or rejected.
- This fixes both cases and also resolves advisory `stamp-code-run1-only`: the latest report lists every such record.
- Update IMPORT.md and ACTIVITIES.md: drop "Recorded only when the Task is created".
- Tests:
  - rerun after a staff reopen records the code;
  - resume after an interruption past the POST records it, and the resumed report equals the clean report;
  - a plain rerun records it again;
  - a rejected POST (400) records no code (this covers advisory `stamped-guard-untested`).
- Give mutation evidence for each.

## Advisory, fix it: the hook trusts any API user
Use the same identity check as ProtectArchivedEmail and RequireLossReason: type api **and** userName `er-import`. Update the policy mirror, the static regex, the php harness and the fake. Test that another API user re-completing a Task gets "now".

Run both suites (exact counts) and A2 (run 1 has 0 write_rejected; run 2 has 0 writes). Use the Engineer final message format.
