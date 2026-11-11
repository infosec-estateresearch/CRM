WO: CRM-009-F
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main
BROWSER: no

# CRM-009-F — deploy_release.sh: set phoneNumberInternational as a boolean

- **Version:** v1.0, 2026-11-11.
- **Authority:** the PO final UAT direction (2026-11-11).
- **Defect:** the first crm-beta deploy (bundle crm-release-f36f0c1af08d, UAT mode) stopped at step 6 with `phoneNumberInternational read back as ''false'', not exactly false`. The read-back check worked as designed. The setter is wrong.

## Fact (verified by the PL on crm-beta, EspoCRM 10.0.12)
`bin/command config:set <name> <value>` defaults to `--type=string` (`Espo\Classes\ConsoleCommands\SetConfigParam`, allowed types: string, bool, int, float, json, auto).

`php bin/command config:set phoneNumberInternational false --type=bool` stores the PHP boolean `false`. Reading `data/config.php` back with `var_export` then gives `false`.

## Change
1. In `scripts/deploy_release.sh` step 6, pass `--type=bool` to the `phoneNumberInternational` `config:set`. `siteUrl` stays a string; you may pass `--type=string` explicitly.
2. Keep the strict read-back exactly as it is.
3. Tests in `tests/unit/test_beta.py` (stubbed docker):
   - the step sends `--type=bool`;
   - a stub that returns the string `'false'` still fails the read-back.
4. Update the step description in docs/BETA.md.

## Allowlist
- `scripts/deploy_release.sh`
- `tests/unit/test_beta.py`
- `docs/BETA.md`

## Acceptance
- **A1:** the unit suite passes, run as non-root, with mutation evidence.
- **A2 (operator):** `deploy_release.sh beta --upgrade` on crm-beta passes step 6 and the beta-safe suite.
