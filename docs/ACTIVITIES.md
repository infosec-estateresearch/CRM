# Activities and historic correspondence (CRM-005)

Calls, meetings (including presentations and bag drops), tasks, the calendar, follow-ups and archived historic email, all in standard EspoCRM 10.0.12 entities. Every example uses synthetic data.

## 1. Mapping intent (implemented by the importer, CRM-006)

| Salesforce | EspoCRM |
|---|---|
| Task, subtype Task | Task, with the status taken from the Salesforce status |
| Task, subtype Call | Call, status Held |
| Task, subtype Email (a logged email) | Email, `status = Archived`. The body is the `TextBody` of the linked EmailMessage, otherwise the Task description. |
| Event | Meeting. `meetingType` carries the Salesforce Type. An untyped Event becomes "Unspecified (legacy)" (D10). |
| EmailMessage and its relations | Email (Archived), with from, to and cc addresses, the core `messageId` and threading, linked to Contacts and Users by address and id |

Legacy fields, all `isCustom`, unaudited, and kept out of list and mass-update layouts:

| Field | Entities | Notes |
|---|---|---|
| `sfId` | Call, Meeting, Task, Email | varchar 18, `readOnlyAfterCreate`, unique index `sfId`. Hidden from the human roles. |
| `sfOwnerId`, `sfCreatedAt` | Call, Meeting, Task, Email | The original owner and creation date. People can read them but not edit them (role `fieldData`). |
| `sfEmailMessageId` | Email | The Salesforce EmailMessage id. The RFC message id goes in the core `messageId`. |
| `sfThreadIdentifier` | Email | The Salesforce ThreadIdentifier (varchar 255) |
| `sfActivityId` | Email | The Salesforce Task id of a logged email |

As in CRM-004 Amendment v1.1, none of these fields is `readOnly`, because that would block the `ER Import` API user too. People are kept off them through `config/access/roles.json`.

`Meeting.meetingType` is an editable enum with the options Meeting (the default), Presentation, Bag Drop, Call, Other, Email and Unspecified (legacy). It is shown on the Meeting list and detail views.

The detail views of Call, Meeting and Task end with a collapsed **Legacy** panel. Admins see `sfId` there; the human roles see the owner and created date. The Email layouts stay core, so the Email legacy fields are reachable only by admins and through the API.

## 2. Archived email is read-only history

- **The hook.** `custom/Espo/Custom/Hooks/Email/ProtectArchivedEmail.php` refuses, with `403 Forbidden`, any save of an existing Email whose stored status is `Archived` if it changes the subject (`name`), `body`, `bodyPlain`, `isHtml`, `from`, `to`, `cc`, `bcc`, `fromString`, `dateSent`, `messageId` or `status`. The status is protected too, so an archived email cannot be un-archived and then edited. Re-linking the parent (to an enquiry, firm or contact), assignment and teams stay allowed.
- **The exemptions** are admins and the `ER Import` API user only: type `api` and userName `er-import`, as in `config/access/api_users.json`. Any other API user is guarded.
- **Roles.** Email edit is `no` for `ER Staff` and `ER Intake`, so the edit button does not appear for them. `ER Manager` keeps `all`, but the hook still applies to it.
- **The plain-text body.** The importer writes archived emails with `isHtml = false` and the text in `body` (and `bodyPlain`), so the core Email detail view shows it as plain text. The core Email layouts are not overridden.
- **The decision table** is mirrored in `tests/unit/activity_policy.py` (`archived_save_allowed`) and checked statically against the hook.

## 3. No email sending or receiving (D5)

There are no email accounts, no SMTP, no sending and no inbound mail. **Operator setting:** in Administration > Outbound Emails, leave the SMTP server unset, so nothing can be sent. Check this at the operator stage; the exact labels are not verified in this repository. Do not create Group or Personal Email Accounts. The roles keep `EmailAccountScope` and `ExternalAccount` false.

## 4. Activities and History panels

The core clientDefs of Opportunity (the Enquiry), Account and Contact already have the `activities`, `history` and `tasks` side panels, so CRM-005 does not recreate or change them. Activities lists upcoming Calls and Meetings; History lists held ones and Emails, including archived ones linked by `parent`. The operator checks this in AC3 on an enquiry with synthetic data.

## 5. Calendar and follow-ups

- **Calendar** (core). Each user's Calendar shows their meetings, calls and tasks. For a team view, open Calendar, choose **Shared** mode, and pick the users or the team (Enquiries, Ancillary intake or Firm management). Every human role has the Calendar scope.
- **Follow-ups** use the core Task with `dateEnd` (the due date) and `reminders`.
- **The "ER Staff" dashboard template** in `config/access/dashboards.json` has a Tasks dashlet titled "My open tasks" (the current user's open tasks) and a Calendar dashlet. `scripts/provision_access.py dev --key-file …` creates or updates it by name, idempotently. It is deployed to the Enquiries team **only** with `--deploy-dashboards`, because deploying replaces the dashboards of every user in that team (`append: false`). Run that flag once, after the users are provisioned, and again only when users should lose their own dashboard layouts.

## 6. Tests

- `tests/unit/test_activities.py` covers metadata consistency, the unique indexes, the meeting type, the layouts, the dashboard template and the archived-email hook. Each rule fails against a mutated (broken) copy of the repository.
- `tests/unit/test_access_policy.py` covers the role changes: Email edit, and the activity `sf*` `fieldData`.
- `tests/unit/test_provision.py` covers the dashboard provisioning against the fake EspoCRM.
- AC3 to AC7 run at the operator stage on `crm-dev`.
