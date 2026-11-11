# CRM-008-G - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-008-G   Candidate: d483bc02b468217cc6de4ae58627ce281da44f62   Base: f26ad4eaa0f88f02d9ba0f42b4d706efe44275b5 (CRM-008-F delivery record)   WO: work-orders/CRM-008-G.md v1.0
Change: the Salesforce Task completion date is now kept. In EspoCRM, `dateCompleted` is readOnly and core stamps "now", so the importer could not store it.
1. **New field `sfCompletedAt`** (datetime; "Completed in Salesforce", in the Legacy panel). It is read-only for Staff, Intake and Manager. The importer sends it in place of `dateCompleted`.
2. **Custom hook `PreserveSalesforceCompletedDate`** (order 20, after core):
   - for a Completed Task, it sets `dateCompleted = sfCompletedAt` on create or when `sfCompletedAt` changes;
   - it also does this when the status changes to Completed in a save by the ER Import API user (type api and userName er-import, the same check as the other hooks);
   - a staff re-completion keeps core's "now".
3. **Code `date_completed_server_stamped`** (record id only). It is recorded on every run, from the stored state, for each Task or email-as-Task that is Completed with `sfCompletedAt` null, where EspoCRM shows the save time. Refused and rejected records get no code. On the real extract this covers 3 ListEmail Tasks.
The fake models core's DateCompleted hook, the custom hook and the saving-user identity. The PHP harness runs the real hook file.
Tests: unit ran 342, OK; load ran 202, OK. There is mutation evidence for every item.
A2 on the full selftest: run 1 made 284 writes with 0 `write_rejected`; run 2 made 0 writes. All 45 of 45 Completed Tasks have `dateCompleted` equal to the source date.
DevSecOps resume sweep: for every interruption point, the resumed exceptions and report equal those of a clean run.
Reviews:
- Round 1: blocking. A Completed record with no source date got the import time with no code.
- Round 2: blocking. The code was lost after a staff reopen followed by an importer re-completion, and on resume.
- Round 3: Auditor, Tester and DevSecOps all PASS. gitleaks found no leaks.
Advisories carried to the next WO:
- if a later snapshot clears CompletedDateTime on a Completed Task, the earlier Salesforce date is kept, yet the stamp code's text says "save time";
- pre-existing, from CRM-006R: if a run is interrupted between a POST and its progress line, the resumed report counts that Task as "unchanged" instead of "created" (`targets` only; the exceptions are identical).
