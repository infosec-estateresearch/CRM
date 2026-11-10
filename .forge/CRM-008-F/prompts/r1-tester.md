# CRM-008-F, round 1 review: Tester

- **Worktree:** `/srv/CRM/worktrees/CRM-008-F`, read-only. Scratch: `/srv/CRM/worktrees/.forge-scratch/CRM-008-F`.
- **Candidate:** `4a826e92a215cd23d8277afafaf342837dc9c2d0`
- **Base:** `4bab43e7515fb171fecac453cb297ab86a3946ba` (the CRM-008 delivery record).
- **WO:** `/srv/CRM/main/work-orders/CRM-008-F.md` v1.0. Its facts were verified live by the PL on crm-dev.
- **Reference extractor:** copy `/srv/CRM/worktrees/.forge-scratch/CRM-006R/ref/` and set `CONTRACT_VERSION` from 3 to 4. Use the full selftest.

Assess the candidate independently.

**Blocking:**
- record content in logs, reports or exceptions;
- a delete path;
- a guessed or placeholder owner;
- a manufactured value without a code;
- `write_rejected` on run 1 or any write on run 2 against the faithful fake;
- a non-GET read path that could write;
- weakening any earlier rule;
- a change outside the allowlist.

**PL decisions:**
- The owner of a recipient-less EmailMessage imported as a Task is the linked Task's owner, else the provisioned `CreatedById` (`owner_from_created_by`; it is the recorded Salesforce user, not a guess), else the record is refused.
- Priority is left to the server default, with `priority_server_default`.
- An HTML-only body gives a null description (HtmlBody is excluded by contract).

**PL real-extract counts:** 54 recipient-less EmailMessages (41 with a linked Task owned by a Standard user, 13 without a linked Task); all 22,623 titled Contacts have an account; Tasks are consistent between status and completion date.
