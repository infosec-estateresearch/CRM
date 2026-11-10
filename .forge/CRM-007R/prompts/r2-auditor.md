# CRM-007R, round 2 review: Auditor

- **Worktree:** `/srv/CRM/worktrees/CRM-007R`, read-only. Scratch: `/srv/CRM/worktrees/.forge-scratch/CRM-007R`.
- **Candidate:** `dd89164b76489ae6331dc1fef2f777d6088039bf`
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

**Round 2.** The round-1 blocker went to the engineer: `export.sh` was not bound to its target.

**PL decisions:**
- an export goes only to a new bare-named directory under the target's own backup dir;
- the export URL is pinned for both targets;
- `--legacy-unmarked` is accepted only for stamps before `20261111T000000Z`;
- restoretest gets the beta network allowlist, local volumes only, and no secrets/configs.

Re-run your probes, verify each finding is fixed, and look for new defects.
