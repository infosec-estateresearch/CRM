# CRM-009-G, round 1 review: tester

- **Worktree:** `/srv/CRM/worktrees/CRM-009-G`, read-only. Scratch: `/srv/CRM/worktrees/.forge-scratch/CRM-009-G`.
- **Candidate:** `b77f355df3998fda6cc99f62f7cc422b0a0f10e9`
- **Base:** `468ffe5719990831e66f0fdcdc4351a62222d294`
- **WO:** `/srv/CRM/main/work-orders/CRM-009-G.md` v1.0. Its facts were verified live by the PL.

Assess the candidate independently, according to your role. Run the unit suite as non-root. Start no containers.

**Blocking:**
- the suite able to send anything but GET, or to use the admin credentials for anything but `Role`;
- the admin credentials reaching argv, output, logs or the repo;
- a role check that skips or passes without credentials;
- any other deploy behaviour changed;
- a change outside the allowlist (note: `test_crm009.py` is unchanged).

Classify each issue as blocking or advisory.
