# CRM-008-F, round 3: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-008-F`. HEAD should be candidate `4a826e92a215cd23d8277afafaf342837dc9c2d0`; confirm it.
- **Same rules.** Keep this round small. Report `STATUS: completed`.

1. **"Never moved" applies both ways.** If an EmailMessage already exists as a **Task** in EspoCRM (from an earlier run, where it had no recipient) and now has a valid To, keep it a Task: update it as a Task and never POST an Email. Record `email_kept_as_task` (record id only). Document it, and test with the reviewers' probe (run 1 with no To, run 2 with To): run 2 makes no POST Email and adds the code.
2. **Codes only for records that are sent.** Record `email_without_recipient_imported_as_task` and `priority_server_default` only when the record isn't refused (no refusing code in `exc`). Assert the counts in A2 with 0 users provisioned: both codes 0, and `owner_required_unresolved` = 35.
3. **HTML-only body.** Add a test pinning a null description when `TextBody` is absent (the reviewers' mutation `or "x"` must fail).

Run both suites, report exact counts, give mutation evidence for items 1–3, and re-run A2 with the users provisioned (run 1 has 0 `write_rejected`, run 2 has 0 writes). Finish in the Engineer final message format.
