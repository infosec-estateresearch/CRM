# CRM-008-G, round 2: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-008-G`. HEAD should be candidate `09ad66eb4f8cea9c69f82e7e72c47c7e4da7f03e`; confirm it.
- **Same rules, same 30-minute box.** Report `STATUS: completed`.

## Blocking (all reviewers): a Completed record with no source date gets the import time, with no code
PL count on the real extract (counts only):
- **3** Completed Tasks have no CompletedDateTime, all with TaskSubtype ListEmail;
- every recipient-less EmailMessage has a MessageDate.

EspoCRM always stamps a completion date for a Completed Task, and there is no source value to preserve. **PL decision:** keep the record Completed, and record the code `date_completed_server_stamped` (record id only) whenever a Completed Task or email-as-Task is **created** with no source completion date.
- Document that EspoCRM shows the import time for these records.
- Add tests for both paths (Task and email-as-Task), with mutation evidence.

## Advisory (DevSecOps): re-completion by the importer
When the importer re-applies `status: Completed` to an existing Task that staff reopened, core stamps "now" and the hook does not fire.
- **Fix in the hook:** also apply `dateCompleted = sfCompletedAt` when `status` changes to Completed **and** the saving user is an API user. Only ER Import is an API user (`User::isApi()`). Inject the current user the way EspoCRM hooks do (constructor injection of `Espo\Entities\User`).
- A staff (non-API) re-completion still gets core's "now".
- Add static or harness tests for both cases.
- Make the fake model it, and test the reviewer's probe: reopen, then a rerun gives `dateCompleted == source`.

Run both suites, report exact counts, give mutation evidence, and re-run A2 (run 1 has 0 `write_rejected`, run 2 has 0 writes). Finish in the Engineer final message format.
