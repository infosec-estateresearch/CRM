# CRM-008, round 4: Engineer (final execution)

- **Worktree:** `/srv/CRM/worktrees/CRM-008`. HEAD should be candidate `ea07c2f25ff37160633573dd953979a9519ce763`; confirm it.
- **This is your last execution.** Keep the change minimal and tested. Report `STATUS: completed`.

1. **Blocking (Auditor).** A record refused with `value_too_long` (an over-length required attribute) is still partly written by the second pass: `run()` → `_upsert_quiet("account_parent", …)` (engine.py around lines 497-500) PUTs `parentId`.
   - Track the records refused in this run (by object and sfId), and skip **every** later write for them, including second passes such as account parent and opportunity contact roles.
   - Count each in `skipped` only, never also as `updated`.
   - Turn the Auditor's probe (an existing Account re-loaded with Name of 250 characters, a changed ParentId and a changed city) into a test that asserts **no** write to that Account and the counts. Give mutation evidence.
2. **ServiceType traceability.** Every Opportunity whose ServiceType was refused is written with `serviceTypeId` null **and** gets its own code `service_type_refused` (record id only). Document the code in IMPORT.md's code table, and add a test.
3. **IMPORT.md:** move the "Usage note" paragraph below the end of the Path/Purpose table, so all rows stay in one table.

Run both suites, report exact counts, and give mutation evidence for items 1 and 2. Finish in the Engineer final message format.
