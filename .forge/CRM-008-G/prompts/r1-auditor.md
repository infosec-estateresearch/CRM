# CRM-008-G, round 1 review: Auditor

- **Worktree:** `/srv/CRM/worktrees/CRM-008-G`, read-only. Scratch: `/srv/CRM/worktrees/.forge-scratch/CRM-008-G`.
- **Candidate:** `09ad66eb4f8cea9c69f82e7e72c47c7e4da7f03e`
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
