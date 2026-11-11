WO: CRM-009-G
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main
BROWSER: no

# CRM-009-G — beta-safe suite: check roles with the admin credentials (GET only)

- **Version:** v1.0, 2026-11-11.
- **Authority:** the PO final UAT direction (2026-11-11).
- **Defect:** the crm-beta deploy of crm-release-980105951aed (UAT mode) completed every step, including provisioning. Its beta-safe suite then failed `test_roles_from_config_exist`, because the API key got a 403 on `GET Role`, so the deploy report was not written.

## Facts (verified by the PL live on crm-beta, EspoCRM 10.0.12)
- An API-key user (ER Import) cannot read `Role`: the response is 401/403. In EspoCRM, Role is an administration entity and no ACL role can grant read on it.
- The admin user (`Espo-Authorization` basic, `CRM_ADMIN_USERNAME`/`CRM_ADMIN_PASSWORD`) gets 200 on `GET Role`, and all four roles from `config/access/roles.json` exist.
- With the API key, `GET Settings` and `GET App/user` return 200.

## Change
1. **`tests/acceptance/test_beta_safe.py`.** The role check uses a second read-only client authenticated as the EspoCRM admin.
   - The credentials come from `CRM_ADMIN_USERNAME`/`CRM_ADMIN_PASSWORD` in the environment, which `deploy_release.sh` already requires and exports to its own process.
   - The client sends GET only, enforced in the same way as `ReadOnlyClient`, and only to `Role`.
   - The credentials are never printed, logged, put in argv or kept.
   - If either name is missing, the test **fails**; it never skips.
   - All other checks keep using the API key.
2. **`scripts/deploy_release.sh`.** Pass the admin credentials to the in-process suite through the environment, if they aren't already passed. No other change.
3. **`tests/unit/test_beta.py`.** Extend the static and fake checks:
   - the admin client sends GET only;
   - the role check fails when the admin credentials are missing;
   - the credentials never appear in any output.
4. **docs/BETA.md:** the suite section and the manual-run command.

## Allowlist
- `tests/acceptance/test_beta_safe.py`
- `scripts/deploy_release.sh`
- `tests/unit/test_beta.py`
- `docs/BETA.md`

## Acceptance
- **A1:** the unit suite passes, run as non-root, with mutation evidence.
- **A2 (operator):** `deploy_release.sh beta --upgrade` on crm-beta passes the beta-safe suite and writes the deploy report.
