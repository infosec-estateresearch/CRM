# CRM-007R, round 1: Engineer (continuation of CRM-007)

- **Worktree:** `/srv/CRM/worktrees/CRM-007R`, branch `forge/CRM-007R`. The expected HEAD is `e09dfb8a2478be2ce31f66735d3e724651ad2c6a`, the CRM-007 escalation record. Confirm it first. Do not modify `.forge/`.
- **Work orders:** `/srv/CRM/main/work-orders/CRM-007R.md` v1.0, with CRM-007 v1.1 still governing (same allowlist).
- **Everything happens in-process:** no containers, no Docker, no network, no writes under `/srv/CRM`.
- **Scratch:** `/srv/CRM/worktrees/.forge-scratch/CRM-007R/`. The previous reviewers' probe scripts are under `/srv/CRM/worktrees/.forge-scratch/CRM-007/` (look for `probe_cross.py`, `probe_deployroot.py` and `r5/allow_probe.py`). Turn their cases into unit tests.
- **Time box:** 30 minutes; return by about 25. Report `STATUS: completed` with Known gaps if needed. Order: items 1 and 2 (blocking), then 3, 4, 5.

## Notes
- **Backup marker.** `backup.sh` writes a `TARGET` file into the backup and lists it in `SHA256SUMS`. Existing dev backups have no marker. For **dev only**, a legacy backup with no marker is accepted when it is named `crm-dev-*`, sits under the dev backups dir, and the operator passes the explicit flag `--legacy-unmarked`. Beta never accepts a backup without the marker. Document this.
- **Provision URL, dev.** The dev URL is `http://<CRM_BIND_IP>:8180`, read from the dev env file with the existing env-file reader (`CRM_BIND_IP` is already validated by `check_access.py dev`). `CRM_BASE_URL` must equal it exactly.
- Keep dev behaviour otherwise unchanged, and prove it with the existing tests.

Run the unit and load suites, report exact counts, and give mutation evidence per item. Finish in the Engineer final message format.
