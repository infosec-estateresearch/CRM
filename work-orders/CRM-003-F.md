WO: CRM-003-F
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-006S
BROWSER: no

# CRM-003-F — Role ACL levels that EspoCRM 10.0.12 accepts (Currency)

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10 (Issue #9). This is an operator-stage defect that blocks CRM_FUNCTIONAL.
- **Why:** on the first deploy of CRM-003 to CRM-006S on crm-dev, `provision_access.py dev` failed with `POST Role -> HTTP 400`. The server said: "Level `all` is not allowed for action *read* for *Currency*". All four roles in `config/access/roles.json` give `Currency` the entity levels `{create, read: all, edit, delete, stream}`.

## Facts verified by the PL live on crm-dev (synthetic probes, deleted)
- `scopes.Currency` has `aclActionList: ["read", "edit"]`, `aclLevelList: ["yes", "no"]` and `aclHighestLevel: "yes"`.
- When each scope of each role was posted on its own, **only `Currency` was refused**, in all 4 roles. `fieldData` and every permission were accepted.
- With `Currency: {"read": "yes", "edit": "no"}`, all 4 full roles post with 200.

## Change
1. In `config/access/roles.json`, set `Currency` to exactly `{"read": "yes", "edit": "no"}` in all 4 roles. Nothing else changes.
2. Add a rule to `tests/unit/access_policy.py` (and the mirror in the checks it feeds):
   - a scope whose ACL is level-based (`yes`/`no`) must use only its own actions and those levels;
   - `Currency` is level-based, with `read: yes` and `edit: no`;
   - `READ_ONLY_SCOPES` keeps meaning read-only, expressed per scope kind: entity scopes use `read: all` and nothing else, and level-based scopes use `read: yes`, `edit: no`.
   - Add a broken fixture (`access_bad_currency_all.json`) that the suite shows failing.
3. In `docs/ACCESS.md`, update the Currency line.

## Allowlist
- `config/access/roles.json` (Currency only)
- `tests/unit/access_policy.py`
- `tests/unit/test_access_policy.py`
- `tests/unit/fixtures/access_bad_*.json` (only the files this rule needs)
- `docs/ACCESS.md`

## Acceptance
- **A1:** `python3 -m unittest discover -s tests/unit` and `python3 -I -B -m unittest discover -s tests/load -t .` both pass. Mutation evidence: putting back `read: all` on Currency fails the suite.
- **A2 (operator):** `provision_access.py dev` completes on crm-dev, and a second run reports no changes.
- **A3:** no other role content changes (shown by the diff).
