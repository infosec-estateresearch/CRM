WO: CRM-007R
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-007
BROWSER: no

# CRM-007R — Continuation of CRM-007 (crm-beta isolation follow-up)

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10 (Issue #9).
- **Why:** CRM-007 was closed ESCALATED. Every round-1 and round-2 blocker was fixed and verified, but the round-3 reviewers found two new blocking isolation gaps after the engineer had used all 4 executions. `work-orders/CRM-007.md` v1.1 stays authoritative for everything else, including the allowlist.

## Change
1. **Backups are bound to their environment.**
   - `CRM_BACKUP_DIR` is the constant `$CRM_RUNTIME_DIR/backups` for both targets, never read from the environment; any test seam derives it from `CRM_TEST_ROOT`.
   - `restore.sh <target>` accepts only a backup directory that sits directly under that target's backup dir and is named `crm-<target>-<UTC stamp>`.
   - It also checks a target marker that `backup.sh` writes into the backup and covers with `SHA256SUMS` (for example a `TARGET` file containing `dev` or `beta`).
   - A backup from the other target, or with no marker, is refused before any docker call.
   - `export.sh` follows the same rule.
2. **Provisioning is pinned to its target.**
   - `provision_access.py` and `provision_users.py` with `beta` require the base URL to be exactly `http://127.0.0.1:<CRM_BETA_APP_PORT>`, read from the checked beta env file (as `export.sh beta` does).
   - With `dev`, they refuse any URL whose port equals the beta app port or 8181+ where that is ambiguous; in practice they require dev's own URL from the dev env file (`http://<CRM_BIND_IP>:8180`).
   - `deploy_release.sh` passes no free-form URL.
3. **The deploy root is constant.** `CRM_DEPLOY_ROOT` is `/srv/CRM/deploy`, derived from `CRM_TEST_ROOT` only under `/tmp`.
   - The deploy root and an existing `<short>` dest must be owned by uid 0 and not group- or other-writable; check this before `verify-tree` on `--upgrade`.
4. **Deploy completes only when fully verified.**
   - `deploy_release.sh` refuses to start unless the provisioning admin credentials, the key file and the acceptance inputs are all present. A deploy never reports success with `provisioning` or `acceptance` set to `skipped`.
   - Any test-only bypass stays under `CRM_TEST_ROOT`.
5. **Compose network specs.** A top-level network may be only `{}`, `{"driver": "bridge"}` or `{"internal": true}`, or a combination of those. `driver_opts`, `ipam`, any other driver and any other key are refused. Add broken fixtures.
6. **Tests.** Cover each item with mutation evidence, including:
   - the cross-environment restore refused in both directions;
   - backup/export with an overridden `CRM_BACKUP_DIR` refused;
   - provisioning against a dev URL with `beta` refused, and the reverse;
   - a macvlan or routed bridge network refused.

## Allowlist
As CRM-007 v1.1.

## Acceptance
- **A1:** the unit and load suites pass; gitleaks is clean.
- **A2:** the round-3 reviewers' cross-environment probes are refused, with no docker call.
- **A3:** the operator stage is as CRM-007 (AC3–AC7).
