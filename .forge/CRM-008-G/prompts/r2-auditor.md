# CRM-008-G, round 2 review: Auditor

- **Worktree:** `/srv/CRM/worktrees/CRM-008-G`, read-only. Scratch: `/srv/CRM/worktrees/.forge-scratch/CRM-008-G`.
- **Candidate:** `9f8fa1e747a9c7cd335c06ae7c8f39762cfa6cba`
- **Base:** `f26ad4eaa0f88f02d9ba0f42b4d706efe44275b5` (the CRM-008-F delivery record).
- **WO:** `/srv/CRM/main/work-orders/CRM-008-G.md` v1.0. Its facts were probe-verified by the PL on crm-dev (the probe was reverted).
- **Reference extractor:** `/srv/CRM/worktrees/.forge-scratch/CRM-006R/ref/`, copied, with `CONTRACT_VERSION` set from 3 to 4. Use the full selftest.

Assess the candidate independently.

**Blocking:**
- record content in logs or reports;
- a delete path;
- a guessed owner;
- a manufactured value (including an import-time completion date) without a code;
- `write_rejected` on run 1 or any write on run 2;
- staff able to edit `sfCompletedAt`;
- a hook that overrides a staff re-completion with the Salesforce date;
- weakening an earlier rule;
- a change outside the allowlist.

**PL decision:** the 30 `access_*.json` fixtures change only by adding `Task.sfCompletedAt`, mechanically, so that each still breaks only its own rule.

## Round 2 context
In round 1, every reviewer blocked on this: a Completed record with no source date got the import time and no code. DevSecOps also raised an advisory: an importer rerun re-completed a reopened Task with "now".

**PL decisions applied in this candidate:**
1. A Task or email-as-Task created Completed with no source date stays Completed and gets the code `date_completed_server_stamped` (record id only). The docs say EspoCRM shows the import time. On the real extract, PL counts 3 such Tasks.
2. The hook restores `dateCompleted = sfCompletedAt` when the status changes to Completed and the saving user `isApi()`. A staff re-completion keeps core's "now".

**Verify:**
- both fixes, independently;
- that neither weakens any earlier rule;
- the engineer's notes on `isApi()` against the stricter er-import check, and on the resume edge case.

Classify each issue as blocking or advisory.
