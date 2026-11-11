# CRM-008-F - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-008-F   Candidate: 4a826e92a215cd23d8277afafaf342837dc9c2d0   Base: 4bab43e7515fb171fecac453cb297ab86a3946ba (CRM-008 delivery record)   WO: work-orders/CRM-008-F.md v1.0
Change: live-server fidelity from the second crm-dev load.
1. **Phones:** compared against the list's primary `phoneNumber`. Records with two or more numbers whose primary matches are compared with one bounded GET each.
2. **Title:** a Contact with no account doesn't send `title`, and gets `title_unstorable_without_account`.
3. **dateCompleted:** sent only when the status is Completed; otherwise the record gets `date_completed_not_storable`.
4. **EmailMessage with no recipient:** imported as a Task (`email_without_recipient_imported_as_task`).
   - Owner: the linked Task's owner, else the provisioned `CreatedById` (`owner_from_created_by`), else refused.
   - Priority is left to the server default (`priority_server_default`).
   - An existing Email stays an Email.
The fake now models list rows without `phoneNumberData`, title needing an account, dateCompleted only when Completed, and `to` required.
Tests: unit ran 333, OK; load ran 178, OK. There is mutation evidence for every item.
- A2 on the full selftest (users provisioned): run 1 had 0 `write_rejected`; run 2 made 0 writes, with 78 reads including 60 single-record GETs.
- Baseline before the fixes, against the extended fake: 35 rejected writes and 114 rerun writes. crm-dev showed the same pattern.
PL facts (live on crm-dev, synthetic): list reads omit `phoneNumberData`; title needs an account; dateCompleted is kept only when Completed; `Email.to` is required.
- Real extract (counts only):
  - 54 recipient-less EmailMessages: 41 have a linked Task owned by a Standard user, and 13 have no linked Task;
  - all 22,623 titled Contacts have an account;
  - Task status and completion dates are consistent.
Reviews: round 1, Auditor, Tester and DevSecOps all reported advisory findings only, which the tooling treats as PASS.
Advisories carried to the next WO:
- an EmailMessage imported as a Task that later gains a recipient is also created as an Email (a duplicate, with no code). This needs a changed snapshot, so it doesn't affect a single initial load;
- `email_without_recipient_imported_as_task` and `priority_server_default` are also recorded on refused records;
- no test pins a null description for an HTML-only body. The behaviour is correct.
