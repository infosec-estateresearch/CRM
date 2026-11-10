# CRM-008-F, round 2: Engineer

Same worktree (`/srv/CRM/worktrees/CRM-008-F`), same rules and box. Your round-1 work is uncommitted. Keep it. Report `STATUS: completed`.

## PL decisions on your notes
1. **Owner of an email imported as a Task.**
   - PL count on the real extract: of the 54 recipient-less EmailMessages, 41 have a linked Task owned by a Standard user, and **13 have no linked Task**.
   - Keep your rule: the linked Task's owner comes first.
   - **Fallback:** if there is no linked Task, or its owner doesn't resolve, use the EmailMessage's `CreatedById` when it resolves to a provisioned user. This is the recorded Salesforce user who logged the message, so it is a fact, not a guess. Record `owner_from_created_by`.
   - Only when neither resolves, refuse with `owner_required_unresolved`.
   - Check that `CreatedById` is in contract v4 for EmailMessage (`migrate/contract/salesforce-fields.json` in the reference copy). If it isn't, keep round 1's behaviour and say so.
   - Add tests and mutation evidence. Document it in IMPORT.md.
2. **Priority left to the default (Normal)** is accepted; record `priority_server_default` once per such record and document it. This is the same treatment as `call_direction_unknown`.
3. Notes 3, 4 and 5 are accepted as documented.

Run both suites, report exact counts, and re-run A2 (full selftest: run 1 has 0 `write_rejected`, run 2 has 0 writes). Finish in the Engineer final message format.
