# CRM-008-G, round 3 review: Auditor

- **Worktree:** `/srv/CRM/worktrees/CRM-008-G`, read-only. Scratch: `/srv/CRM/worktrees/.forge-scratch/CRM-008-G`.
- **Candidate:** `d483bc02b468217cc6de4ae58627ce281da44f62`
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

## Round 3 context
In round 2, every reviewer blocked on two cases where the `date_completed_server_stamped` code was lost: after a staff reopen and importer re-completion, and on `--resume` past the POST. All three also gave an advisory that the hook trusted any API user.

**PL decisions applied in this candidate:**
1. **State-based rule.** After every Task or email-as-Task upsert, on every run, the code (record id only) is recorded when the stored record is Completed with `sfCompletedAt` null. A refused or rejected record gets no code.
2. **Identity check.** The hook re-completion uses type api **and** userName `er-import`, the same as ProtectArchivedEmail and RequireLossReason.

**Verify independently:**
- both fixes;
- the rerun-after-reopen and resume probes;
- that the resumed report equals the clean report;
- that no earlier rule is weakened.

Classify each issue as blocking or advisory.
