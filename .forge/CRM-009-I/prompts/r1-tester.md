# CRM-009-I, round 1 review: tester

- **Worktree:** `/srv/CRM/worktrees/CRM-009-I`, read-only. Scratch: `/srv/CRM/worktrees/.forge-scratch/CRM-009-I`.
- **Candidate:** `4265b71501958ce30407eebc76ebe2b638f0a186`
- **Base:** `c3c0fefbac3a45360325b1ccb4e0cd56fc63525b`
- **WO:** `/srv/CRM/main/work-orders/CRM-009-I.md` v1.0. Its facts were verified live by the PL.

Assess the candidate independently, according to your role. Run the unit and load suites as non-root (`python3 -I -B -m unittest discover -s tests/load -t .`). Start no containers and contact no network service.

**Blocking:**
- a real difference that would no longer be written, beyond the WO's accepted usersIds limitation;
- unbounded single reads;
- any non-GET request added on the comparison path;
- a change to create bodies, retries, refusals or exception codes;
- a change outside the allowlist;
- any customer data, secret or IP added to the repo.

Report `VERDICT: PASS | FINDINGS | FAIL`. Classify each finding as blocking or advisory.
