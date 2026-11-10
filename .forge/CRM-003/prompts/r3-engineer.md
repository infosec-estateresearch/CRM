# CRM-003, round 3: Engineer correction (blocking issue found by the PL)

- **Worktree:** `/srv/CRM/worktrees/CRM-003`. The expected HEAD is `39b7cb5213de31aafdaea5c22fab63d3f664a0d8`, with your round 1–2 work **uncommitted** in the working tree. Keep it. The PL's commit attempt was refused (see item 0). Do not modify `.forge/`.
- The WO is quoted verbatim below. The PL **amends Change 1** as described here. The scope allowlist is unchanged; role `fieldData` sits in `config/access/roles.json`, which is already allowlisted.

## Blocking: `readOnly` makes the Salesforce keys unwritable, including by the importer
The PL verified this in the real EspoCRM 10.0.12 source:
- `Espo\Core\Acl\GlobalRestriction::buildData()` reads `entityDefs.<Scope>.fields.<field>.readOnly` and turns it into the global `readOnly` restriction. That restriction applies to **every** user, including the API user `ER Import` (`AclManager` line ~475). A field with `"readOnly": true` therefore can never be set through the REST API, which is exactly the problem you flagged.
- `Espo\Core\Record\Service` (lines ~560–577) strips the attributes of fields with `FieldParam::READ_ONLY_AFTER_CREATE` (`readOnlyAfterCreate`) from the input **on update only**. So such fields can be set on create and are immutable afterwards.

## Required change (minimal)
0. **gitleaks false positive (blocking for the commit).** `tests/unit/test_provision.py:33` `API_KEY_SENTINEL = "APIKEY-SENTINEL-<redacted: gitleaks false positive>"` trips the `generic-api-key` rule, and the commit is refused. Replace it with a low-entropy sentinel that is obviously not a key, for example `"NOT-A-REAL-KEY-SENTINEL"`. Check that no other test literal looks like a credential: a high-entropy string next to key, secret, token or password.
1. **`sfId`** on User, Account and Contact: replace `readOnly: true` with `readOnlyAfterCreate: true`. Keep the unique index, maxLength 18, not audited, and hidden from edit layouts.
2. **The other legacy keys** (`sfOwnerId`, `sfCreatedAt`): remove `readOnly`. Make them read-only for people through **role field-level permissions**:
   - in `config/access/roles.json` `fieldData`, set `{"read":"yes","edit":"no"}` on these fields, and on `sfId`, for `ER Staff`, `ER Intake` and `ER Manager`;
   - `ER Import` gets `edit: yes`;
   - leave them out of edit layouts.
3. Update the policy and tests:
   - **no** `sf*` field may carry `readOnly: true`;
   - `sfId` must carry `readOnlyAfterCreate: true`;
   - every human role has `edit: no` on every `sf*` field;
   - `ER Import` has `edit: yes`.

   Add a broken fixture for each rule, replacing `keys_bad_sfid_writable` and `keys_bad_owner_writable` where they now contradict the rules. Update `docs/ACCESS.md` and the acceptance test AC8.
4. While the WO is in front of you, briefly confirm Change items 1–8 and AC1–AC8. List any remaining gaps under "Known gaps" rather than adding scope.

Run `python3 -m unittest discover -s tests/unit -v` and report exact counts and non-vacuity. Return within about 20 minutes. Finish in the Engineer final message format.

---
## Work Order (verbatim)

WO: CRM-003
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-001-LAN
BROWSER: yes

# CRM-003 — Users, teams, roles, audit and Salesforce keys (synthetic users)

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10 (Issue #9): "CRM-003 — Users and permissions".
- **Parent PBI:** CRM-PBI-002 (R12, R13), and the shared entity contract in `docs/MIGRATION-DECISIONS.md` §3.
- **Base:** stacked on `forge/CRM-001-LAN` (PR #6 head `39b7cb5`), because `custom/` and the scripts exist only there until CRM-001 is accepted. If CRM-001 changes before acceptance, this branch is rebased by merge, never by force.

## Outcome

Named EspoCRM logins with Estate Research roles and teams, defined in Git and provisioned idempotently through the API:
- historic Salesforce users preserved, inactive where they are inactive in Salesforce;
- deletion of a firm that has enquiries is blocked;
- field history on the key firm and contact fields;
- an immutable `sfId` key on User, Account and Contact for the importer.

## Facts verified by the operator against the running EspoCRM 10.0.12 image
- Core entities exist: Account, Contact, Opportunity, Call, Meeting, Task and Email (in the Crm module), plus User, Team, Role, Note, ActionHistoryRecord and AuthLogRecord.
- `User` fields include `userName`, `type`, `password`, `isActive`, `teams`, `roles`, `defaultTeam`, `auth2FA`, `sendAccessInfo` and `lastAccess`.
- **There is no "password change required on next login" flag** in 10.0.12. Password-change links need outbound email, which is out of scope.

## Change

1. **Salesforce keys** (`custom/…/entityDefs/{User,Account,Contact}.json`, merged into the CRM-001 files where they exist):
   - `sfId`: varchar, maxLength 18, `readOnly: true`, `isCustom: true`, not audited, with a **unique** index named `sfId`. It is hidden from edit layouts and shown read-only on detail views for admins only.
   - On Account and Contact also:
     - `sfOwnerId` (varchar 18, read-only): the original owner, preserved even when it is mapped to a legacy user (D4);
     - `sfCreatedAt` (datetime, read-only).
2. **Access as code: `config/access/teams.json` and `config/access/roles.json`.**
   - **Teams:** `Enquiries`, `Ancillary intake`, `Firm management`.
   - **Roles** (EspoCRM role `data` format; `stream` access as for `read`):

     | Role | Account | Contact | Opportunity | Call, Meeting, Task | Email | Others |
     |---|---|---|---|---|---|---|
     | `ER Staff` | create, read all, edit all, **delete no** | create, read all, edit all, delete no | create, read all, **edit own**, delete no | create, read all, edit own, delete own | read all, create yes, edit own, delete no | read all, no admin |
     | `ER Intake` | as Staff | as Staff | create, read all, **edit all**, delete no | as Staff | as Staff | |
     | `ER Manager` | create, read all, edit all, delete no | edit all, delete all | edit all, delete all | edit all, delete all | edit all, delete no | |
     | `ER Import` (API only) | create and edit all | create and edit all | create and edit all | create and edit all | create and edit all | No delete. Used only by the importer, and deactivated after the load. |

     Administration stays with EspoCRM admin users only. There is no shared login.
3. **`scripts/provision_access.py`** (stdlib, reusing `scripts/crm_api.py`, guarded to a named environment):
   - create or update teams and roles **by name**, so it is idempotent;
   - create the `ER Import` API user with the API-key auth method. The key is generated by EspoCRM and written only to a root-only output file given on the command line.
4. **`scripts/provision_users.py`:**
   - **Input:** a JSON list of `{sfId, userName, firstName, lastName, emailAddress, isActive, teams[], roles[]}`. It is produced later by the importer from the snapshot. Tests use synthetic data only.
   - Idempotent by `sfId`. It updates names, active state, teams and roles, and never touches passwords on re-runs.
   - **Inactive** Salesforce users become inactive EspoCRM users with no usable password. The legacy shared intake identity (D4) is created **inactive**.
   - **Active** users each get a new strong random temporary password (`secrets`, at least 20 characters across mixed character classes), with `sendAccessInfo: false`. The passwords are written **only** to a root-only (`0600`) CSV at a path given on the command line, which must not already exist. They are never printed or logged, and never sent by email.
   - `--reset <sfId>` issues a new temporary password for one user.
   - The missing forced-change flag is a known gap. `docs/ACCESS.md` documents the mitigation: passwords are handed over individually, users change them in Preferences, and an operator report lists users who have never logged in (`lastAccess` empty).
5. **Firm deletion guard:** `custom/Espo/Custom/Hooks/Account/RestrictDeleteWithEnquiries.php`, a `beforeRemove` hook. It refuses (Forbidden) if the Account has any related Opportunity. This applies to admins too, so cleaning up must be deliberate.
6. **Audit (field history):** `audited: true` on Account `name`, `type`, `industry`, `assignedUser`, `parent` and `learningPlatformAccess`, and on Contact `account` and `emailAddress`. Opportunity audit belongs to CRM-004. Action history and the auth log stay enabled (defaults). `docs/ACCESS.md` says where an admin finds them.
7. **Tests** (unit, in-process, with no network):
   - metadata consistency (JSON parses; fields, indexes and layouts agree);
   - role policy (non-admin roles never `delete` Account; Staff edits only its own Opportunity; Intake edits all; Import never deletes);
   - provisioning idempotency against a fake transport (a second run makes no changes and issues no new passwords);
   - password generation strength;
   - a password sentinel never appears in stdout, stderr or logs;
   - the CSV is created `0600` and never overwritten;
   - the hook source contains the guard, checked statically;
   - each policy rule fails against a broken fixture.
8. **Docs:** `docs/ACCESS.md` (roles, teams, provisioning, temporary passwords and their gap, audit locations) and the README usage section.

## Scope

**Allowlist:**
- `custom/**`, limited to the User, Account and Contact entityDefs and layouts, and `Hooks/Account/**`
- `config/access/**`
- `scripts/provision_access.py`, `scripts/provision_users.py`
- `tests/unit/**`, `tests/acceptance/**`
- `docs/ACCESS.md`, the README usage section
- `.forge/CRM-003/**`

**Excluded:**
- Opportunity, activity and email metadata (CRM-004 and CRM-005);
- the importer;
- real users or data;
- outbound email;
- `deploy/**`;
- Salesforce access.

## Acceptance criteria
**In the loop:**
- **AC1:** the unit tests pass, with exact counts, and every policy rule fails against its broken fixture.
- **AC2:** gitleaks is clean. No secrets, real names or IP addresses.

**Operator stage** (on `crm-dev`, synthetic users only):
- **AC3:** provisioning twice gives the same teams, roles and users, with no new passwords on the second run.
- **AC4:** a synthetic Staff user signs in, can read all firms and contacts, and cannot delete a firm.
- **AC5:** an inactive synthetic user cannot sign in.
- **AC6:** deleting a firm with an Opportunity is refused, even for an admin.
- **AC7:** an edit to an audited field appears in the record's stream or history, with the user and time.
- **AC8:** the `sfId` unique index rejects a duplicate value.

**Product acceptance:** a real staff member signing in (demonstration item 1). That happens later, on `crm-beta`.
