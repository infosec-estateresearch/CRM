# CRM-003-F, round 1 review: Devsecops

- **Worktree:** `/srv/CRM/worktrees/CRM-003-F`, read-only. Scratch: `/srv/CRM/worktrees/.forge-scratch/CRM-003-F`.
- **Candidate:** `769d6cbf11abef42834e1b045c96b4cd7441f474`
- **Base:** `a34a9516005e899c916675e9aa15b4933150370b` (the CRM-006S delivery record)
- **WO:** `/srv/CRM/main/work-orders/CRM-003-F.md` v1.0

Assess the candidate independently against the WO.

**Blocking:**
- any role change other than Currency;
- a policy rule that doesn't catch `read: all` or an extra action on Currency;
- weakening any existing access rule;
- a change outside the allowlist.

**PL decision:** the 29 existing `access_bad_*.json` fixtures may change only in their Currency block. This follows mechanically, so that each fixture still breaks only its own rules. Verify that nothing else in them changed.

**PL facts** (live on crm-dev): `scopes.Currency` has `aclActionList [read, edit]` and `aclLevelList [yes, no]`. Only Currency was refused, and all 4 corrected roles post with 200.
