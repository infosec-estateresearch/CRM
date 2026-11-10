# Access: users, teams, roles and audit (CRM-003)

Named EspoCRM logins with Estate Research roles and teams. The roles and teams are defined in Git and provisioned idempotently through the API (CRM-D008: named users only, so the shared login ends). All examples use synthetic data.

| What | Where |
|---|---|
| Teams | `config/access/teams.json` |
| Roles (EspoCRM role `data` format) | `config/access/roles.json` |
| The importer's API user | `config/access/api_users.json` |
| Provisioning | `scripts/provision_access.py`, `scripts/provision_users.py` |
| Salesforce keys and field history | `custom/Espo/Custom/Resources/metadata/entityDefs/{User,Account,Contact}.json` |
| Firm deletion guard | `custom/Espo/Custom/Hooks/Account/RestrictDeleteWithEnquiries.php` |
| Policy tests | `tests/unit/access_policy.py`, `tests/unit/test_access_policy.py`, `tests/unit/test_provision.py` |
| Live acceptance tests (AC3–AC8) | `tests/acceptance/test_access.py` |

## 1. Teams

`Enquiries`, `Ancillary intake` and `Firm management`. Teams group users. Access comes from roles: every role reads "all", so team membership does not limit what anyone can see.

## 2. Roles

Levels follow EspoCRM's role table. `create` is yes or no; `read`, `edit`, `delete` and `stream` are all, team, own or no. In every scope, `stream` is the same as `read`.

| Role | Account (firm) | Contact | Opportunity (enquiry) | Call, Meeting, Task | Email | Other scopes |
|---|---|---|---|---|---|---|
| `ER Staff` | create; read all; edit all; **delete no** | create; read all; edit all; delete no | create; read all; **edit own**; delete no | create; read all; edit own; delete own | create; read all; edit own; delete no | see §2.1 |
| `ER Intake` | as Staff | as Staff | create; read all; **edit all**; delete no | as Staff | as Staff | see §2.1 |
| `ER Manager` | create; read all; edit all; delete no | create; read all; edit all; delete all | create; read all; edit all; delete all | create; read all; edit all; delete all | create; read all; edit all; delete no | see §2.1 |
| `ER Import` (API only) | create; read all; edit all; delete no | the same | the same | the same | the same | see §2.1 |

### 2.1 Every ACL scope is explicit

EspoCRM 10.0.12 has no `aclStrictMode` setting here, so it runs in non-strict mode: **a scope a role leaves unset is allowed**. Every role therefore lists every ACL-enabled scope of the image (verified by the PL in the running espocrm 10.0.12 image; the list is the `ACL_ENTITY_SCOPES` / `ACL_BOOLEAN_SCOPES` constants in `tests/unit/access_policy.py`):

| Scopes | `ER Staff`, `ER Intake`, `ER Manager` | `ER Import` |
|---|---|---|
| Account, Contact, Opportunity, Call, Meeting, Task, Email | as the table above | as the table above |
| Document, DocumentFolder, User, Team | read all only (no create, edit or delete) | the same |
| Currency (level-based ACL in EspoCRM 10.0.12: actions `read` and `edit` only, levels `yes`/`no`; `read: all` is refused with HTTP 400) | `read: yes`, `edit: no` (read-only) | the same |
| Lead, Campaign, TargetList, TargetListCategory, KnowledgeBaseArticle, KnowledgeBaseCategory, Template, EmailTemplate, EmailTemplateCategory, Case (generic CRM features Estate Research does not use) | `false` (no access, hidden) | `false` |
| Activities, Calendar, GlobalStream, WorkingTimeCalendar (boolean) | `true` | `false` |
| Import, Webhook, OpenApi, ExternalAccount, EmailAccountScope (boolean) | `false` | `false` (the importer uses REST, not EspoCRM's Import tool) |

`ER Import` has no `delete` in any scope. A scope missing from a role, a scope not in the verified list, or a boolean scope given as anything but `true`/`false` fails the policy test. To add a scope (CRM-004 adds `ServiceType`), add it to one of the two constants and give it a row in `EXPECTED_DATA`; every rule then requires it of every role.

Other role permissions:
- **Assignment and user permissions:** "all" for every role, so enquiries can be assigned to anyone.
- **Export, portal, group email accounts, data privacy and lock:** "no" for every role. Exports are made by the operator with `scripts/export.sh`.
- **Mass update, follower management and the audit log:** only `ER Manager` has them.
- **`ER Import`:** has no message, mention or calendar permission.

Field-level access:
- `sfId` on User, Account and Contact is hidden (read no, edit no) from `ER Staff`, `ER Intake` and `ER Manager`.
- `sfId` is also hidden on Opportunity, Call, Meeting, Task and Email (CRM-004, CRM-005).
- `sfOwnerId` and `sfCreatedAt` on Account and Contact are read yes, edit no for those three roles.
- `ER Import` has read yes, edit yes on every one of these fields, so the importer can write them.
- Admins see sfId on the firm detail view. It cannot be changed after the record is created (see section 5).

Administration stays with EspoCRM **admin** users, the user type `admin`. No role grants it. Every login is named; there is no shared login.

`tests/unit/test_access_policy.py` enforces these rules:
- roles.json equals the tables above;
- every role sets every verified ACL scope explicitly, unused CRM scopes are `false`, reference scopes are read-only and boolean scopes are as in §2.1;
- no role deletes an Account;
- Staff edits only its own Opportunities, and Intake edits all of them;
- Import never deletes, and only API users hold it;
- stream equals read, and every level is valid; a level-based scope (Currency) uses only its own actions (`read`, `edit`) and levels (`yes`, `no`);
- sfId is hidden from the human roles;
- no human role can edit any `sf*` field, and `ER Import` can edit all of them.

Each rule has a broken fixture (`tests/unit/fixtures/access_bad_*.json`) that the suite shows failing.

## 3. Provisioning

Credentials are read only from the environment, as for the CRM-001 scripts (docs/BUILD.md §7.3). Export them only inside a `( ... )` subshell. Both scripts take the target environment first, and it must be exactly `dev` (exit 2 otherwise). Output files go to a root-only directory, and each one must be a **new** file. The scripts create it with mode `0600` and refuse an existing path or symlink before making any API call.

```sh
install -d -m 0700 /root/crm-access      # once

( export CRM_BASE_URL=http://<CRM_BIND_IP>:8180 CRM_ADMIN_USERNAME=... CRM_ADMIN_PASSWORD=...
  # 1. Teams, roles and the ER Import API user (create or update by name)
  python3 scripts/provision_access.py dev --key-file /root/crm-access/import-key-$(date -u +%Y%m%dT%H%M%SZ).env
  # 2. Users from the importer's JSON list (idempotent by sfId)
  python3 scripts/provision_users.py dev --input /root/crm-access/users.json \
      --password-file /root/crm-access/passwords-$(date -u +%Y%m%dT%H%M%SZ).csv \
      --legacy-shared <sfId of the legacy shared intake identity>
  # One user's new temporary password
  python3 scripts/provision_users.py dev --reset <sfId> --password-file /root/crm-access/reset-<UTC>.csv
  # Users who have never signed in
  python3 scripts/provision_users.py dev --report-never-logged-in
  # After the import: deactivate the API user (it keeps its key)
  python3 scripts/provision_access.py dev --key-file /root/crm-access/unused-<UTC>.env --import-user-active no )
```

### `provision_access.py`

- **Settings (CRM-008).** `config/settings.json` holds the Settings the CRM must have: `currencyList ["GBP"]`, `defaultCurrency "GBP"`, `baseCurrency "GBP"` (the importer sends `amountCurrency "GBP"`; with the EspoCRM default `USD`, every enquiry with an amount is refused `400 amount validCurrency`) and `phoneNumberInternational false` (UK national numbers are stored verbatim). The script reads `GET Settings` and sends only the keys that differ with `PUT Settings`, which needs admin; a second run reports `settings` unchanged. The access policy tests enforce these values. An unknown key in the file is refused before any HTTP.
- **Teams and roles** are looked up by name. Missing ones are created. For existing ones, only the attributes that differ from Git are sent. A second run makes no changes. Several records with the same name are an error, never a guess.
- **A role's `info`** in `roles.json` is documentation only. EspoCRM has no such attribute (it drops it), so it is never sent or compared (CRM-008).
- **The `ER Import` API user** (`er-import`) has type `api` and the auth method `ApiKey`. EspoCRM generates the key, and it is written only to `--key-file`, as `CRM_IMPORT_USERNAME=` and `CRM_IMPORT_API_KEY=` lines.
  - An existing API user keeps its key. Nothing is written, and the key file is not created.
  - A key can only be regenerated by an admin, in Administration > API Users.
  - Its active state changes only with `--import-user-active yes|no`. Deactivate it after each load.
  - A regular user that already has that userName is refused, never converted.

### `provision_users.py`

The input is a JSON list of `{sfId, userName, firstName, lastName, emailAddress, isActive, teams[], roles[]}`. The importer produces it later from the Salesforce snapshot.
- **Validation, before any API call.** Exactly those keys are allowed. The sfId is 15 or 18 letters and digits. Team and role names must exist in `config/access`. Neither sfId nor userName may repeat. The API-only role `ER Import` is refused.
- **Matching is by sfId only.** A new sfId whose userName already exists is refused, never adopted. An sfId held by an admin or API user is refused.
- **Re-runs** update first and last name, email address, active state, teams and roles. They never send a password, and they leave the userName unchanged.
- **Inactive Salesforce users** become inactive EspoCRM users with no usable password: a random one is sent once and never recorded. Every `--legacy-shared` sfId is always provisioned inactive, whatever the input says. This covers the legacy shared intake identity (D4).
- **Active users** get a new temporary password: 24 characters from `secrets`, always including lower case, upper case, digits and symbols. `sendAccessInfo` is always false, so EspoCRM sends no email.
- **Where passwords go.** They are written only to `--password-file`, a CSV with the columns `sfId,userName,temporaryPassword`. It is created at the first password, so a run that issues none creates no file. Passwords are never printed or logged. If a run fails part-way, the file still holds the passwords already issued, and stderr says how many.
- **A user re-activated by a later input** has no known password. The script says so; issue one with `--reset <sfId>`.
- **`--reset <sfId>`** sets a new temporary password for one active regular user.

Delete each password CSV once its passwords have been handed over.

## 4. Temporary passwords: the known gap

EspoCRM 10.0.12 has **no "change password at next sign-in" flag**. Password-reset links need outbound email, which is out of scope. The mitigation:
1. Each temporary password is handed to its user individually, never by email and never in a shared channel. Then its CSV is deleted.
2. The user signs in and changes the password at once: own user menu > **Preferences**, then **Change Password**.
3. The operator runs `provision_users.py dev --report-never-logged-in` after hand-over and again later. It lists active regular users whose `lastAccess` is empty. Such a user's temporary password is still the only one, so follow it up or `--reset` it.

## 5. Salesforce keys

| Field | On | Type | Notes |
|---|---|---|---|
| `sfId` | User, Account, Contact | varchar 18 | `readOnlyAfterCreate`: set on create, immutable afterwards. Not audited, unique index `sfId`. Hidden from the human roles. |
| `sfOwnerId` | Account, Contact | varchar 18 | Read-only for people through role field-level access. The original Salesforce owner, kept even when it is mapped to a legacy user (D4). |
| `sfCreatedAt` | Account, Contact | datetime | Read-only for people through role field-level access. The Salesforce creation time. |

- They are not in list layouts or mass update.
- On the firm detail view, they are in a separate **Salesforce** panel.
- On Contact and User, the core detail layouts are not overridden. The fields can be read through the API or added in the Layout Manager, but deploys overwrite Layout Manager changes.

Why not `readOnly`: in EspoCRM 10.0.12 a field's `readOnly` becomes a global ACL restriction that applies to every user, the `ER Import` API user included, so the importer could never write the key. Instead:
- `sfId` uses `readOnlyAfterCreate`. The record service accepts it on create and strips it from every update, for admins too.
- `sfOwnerId` and `sfCreatedAt` carry no metadata restriction. `ER Staff`, `ER Intake` and `ER Manager` have edit "no" on them in `config/access/roles.json`; `ER Import` has edit "yes".
- `tests/unit/test_access_policy.py` enforces this: no `sf*` field may be `readOnly`, `sfId` must be `readOnlyAfterCreate`, every human role has edit "no" on every `sf*` field, and `ER Import` has edit "yes".

Points for the operator stage and the importer:
- **Admins are not limited by role field access.** An admin can still change `sfOwnerId` and `sfCreatedAt`, through the API or in the firm edit form, which uses the detail layout. Only admins can do it, and only deliberately.
- **AC8** also checks that an update cannot change `sfId` and that a Staff user cannot change `sfOwnerId`.
- **Soft-deleted records.** EspoCRM soft-deletes records, so a deleted record keeps its sfId in the unique index. Re-importing that sfId then fails until the deleted record is purged.
- **Labels.** The fields have no i18n labels, which are outside the CRM-003 allowlist. EspoCRM shows its generated labels.

## 6. Firm deletion guard

Before an Account is removed, `RestrictDeleteWithEnquiries` (a `beforeRemove` hook) counts its related Opportunities. If there are any, it throws `Forbidden`, which the API returns as HTTP 403.
- There is no exception for admins, or for any option.
- To remove such a firm, move or delete its enquiries first. The clean-up must be deliberate.
- The roles already deny Account delete to every non-admin, so the hook is what stops admins.

## 7. Audit: where an admin finds it

- **Field history.** These fields are audited: on Account, `name`, `type` (Tier), `industry`, `assignedUser`, `parent` (Head Office) and `learningPlatformAccess`; on Contact, `account` and `emailAddress`. Each change appears as an "Update" entry in the record's **Stream** panel, with the user, time, old value and new value. Admins and `ER Manager` (audit permission) can also open the record's **Audit Log** from the detail view's menu. Opportunity audit belongs to CRM-004.
- **Action history.** This shows who viewed, created, edited or deleted which record. Find it in Administration > **Action History**, or in a user's detail view.
- **Sign-ins.** Successful and failed sign-ins, with IP and time, are in Administration > **Auth Log**.

Action history and the auth log stay at EspoCRM's defaults (enabled). CRM-003 changes neither.

## 8. Checks

- **In the loop:** `python3 -m unittest discover -s tests/unit -v`. To show a rule failing, point it at a fixture:

  ```sh
  CRM_ACCESS_UNDER_TEST=tests/unit/fixtures/access_bad_staff_deletes_account.json \
      python3 -m unittest discover -s tests/unit -p test_access_policy.py
  CRM_KEYS_UNDER_TEST=tests/unit/fixtures/keys_bad_sfid_not_unique.json \
      python3 -m unittest discover -s tests/unit -p test_access_policy.py
  CRM_HOOK_UNDER_TEST=tests/unit/fixtures/hook_bad_admin_bypass.php \
      python3 -m unittest discover -s tests/unit -p test_access_policy.py
  ```

- **Operator stage (AC3–AC8):** run these on `crm-dev`, after `scripts/deploy_custom.sh dev`, on the seeded synthetic data.

  ```sh
  install -d -m 0700 /root/crm-003-acceptance
  ( export CRM_BASE_URL=http://<CRM_BIND_IP>:8180 CRM_ADMIN_USERNAME=... CRM_ADMIN_PASSWORD=... \
           CRM_ACCESS_OUTPUT_DIR=/root/crm-003-acceptance
    python3 -m unittest discover -s tests/acceptance -p test_access.py -v )
  ```

  The tests provision four synthetic users: `acc.staff`, `acc.intake`, `acc.former` and `acc.leaver`, at `@example.test`. If this run creates the `ER Import` API user, its key file also lands in `CRM_ACCESS_OUTPUT_DIR`. Delete that directory afterwards. Without the four variables, the module is skipped.
