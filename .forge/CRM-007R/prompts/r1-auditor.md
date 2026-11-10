# CRM-007R, round 1 review: Auditor

- **Worktree:** `/srv/CRM/worktrees/CRM-007R`, read-only. Scratch: `/srv/CRM/worktrees/.forge-scratch/CRM-007R`.
- **Candidate:** `48810aba327252b58722069ba162cc7b09b507e9`
- **Base:** `e09dfb8a2478be2ce31f66735d3e724651ad2c6a` (the CRM-007 escalation record; CRM-007 was reviewed through `82c05ef`).
- **WOs:** `/srv/CRM/main/work-orders/CRM-007R.md` v1.0, plus `CRM-007.md` v1.1 (same allowlist).

Assess the candidate independently. Earlier reviewers' probes are in `/srv/CRM/worktrees/.forge-scratch/CRM-007/`. Re-run them against this candidate.

**Blocking:**
- any path where beta reaches crm-dev resources or data, or the reverse (backups, restore, export, provisioning, compose, deploy);
- synthetic data reaching beta;
- a secret in argv, logs or the repo;
- a bundle that verifies when tampered;
- a deploy that reports success unverified;
- a change outside the allowlist;
- host firewall tooling.

**PL decisions:**
- `--legacy-unmarked` is dev-only, for pre-CRM-007R dev backups under the dev backup dir.
- Dev provisioning requires exactly dev's own URL, `http://<CRM_BIND_IP>:8180` from the dev env file.
- `CRM_TEST_ROOT` (only under `/tmp`) is the only test seam.
- The operator stage (AC3–AC7, browser) is run later by the PL.
