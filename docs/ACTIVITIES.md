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
| `sfCompletedAt` | Task | "Completed in Salesforce" (datetime, CRM-008-G). The Salesforce completion time, which the Task hook below copies to `dateCompleted`. People can read it but not edit it (role `fieldData`). |
| `sfEmailMessageId` | Email | The Salesforce EmailMessage id. The RFC message id goes in the core `messageId`. |
| `sfThreadIdentifier` | Email | The Salesforce ThreadIdentifier (varchar 255) |
| `sfActivityId` | Email | The Salesforce Task id of a logged email |

As in CRM-004 Amendment v1.1, none of these fields is `readOnly`, because that would block the `ER Import` API user too. People are kept off them through `config/access/roles.json`.

`Meeting.meetingType` is an editable enum with the options Meeting (the default), Presentation, Bag Drop, Call, Other, Email and Unspecified (legacy). It is shown on the Meeting list and detail views.

The detail views of Call, Meeting and Task keep every core field (Task keeps `dateCompleted`, under `dateEnd`) and end with a collapsed **Legacy** panel. Admins see `sfId` there; the human roles see the owner and created date (and, on a Task, `sfCompletedAt`). The Email layouts stay core, so the Email legacy fields are reachable only by admins and through the API.

## 2. Archived email is read-only history

- **The hook.** `custom/Espo/Custom/Hooks/Email/ProtectArchivedEmail.php` refuses, with `403 Forbidden`, any save of an existing Email whose stored status is `Archived` if it changes any of these core Email attributes of 10.0.12:
  - subject and content: `name`, `subject`, `body`, `bodyPlain`, `isHtml`;
  - addresses: `from`, `to`, `cc`, `bcc`, `replyTo`, `fromString`, `replyToString`, `fromName`, `fromAddress`, `replyToName`, `replyToAddress`, `addressNameMap`;
  - address links: `fromEmailAddressId`, `toEmailAddressesIds`, `ccEmailAddressesIds`, `bccEmailAddressesIds`, `replyToEmailAddressesIds`;
  - attachments: `attachmentsIds`, `hasAttachment`;
  - dates: `dateSent`, `deliveryDate`, `sendAt`;
  - message ids: `messageId`, `messageIdInternal`;
  - `status`.

  The status is protected too, so an archived email cannot be un-archived and then edited. Re-linking the parent (to an enquiry, firm or contact), assignment, teams and users stay allowed. A static test checks that the hook list is exactly this set.
- **Emails logged by hand.** Emails logged by hand are archived, and from then on cannot be changed. They can be told apart from imported Salesforce history by `createdBy` and by the empty `sfId`, which only admins can see. (New records are not guarded, so staff can log a historic email by creating it as Archived; that is accepted as legitimate correspondence logging.)
- **The exemptions** are admins and the `ER Import` API user only: type `api` and userName `er-import`, as in `config/access/api_users.json`. Any other API user is guarded.
- **Roles.** Email edit is `no` for `ER Staff` and `ER Intake`, so the edit button does not appear for them. `ER Manager` keeps `all`, but the hook still applies to it.
- **The plain-text body.** The importer writes archived emails with `isHtml = false` and the text in `body` (and `bodyPlain`), so the core Email detail view shows it as plain text. The core Email layouts are not overridden.
- **The decision table** is mirrored in `tests/unit/activity_policy.py` (`archived_save_allowed`) and checked statically against the hook.

## 2a. The Salesforce completion date of a Task (CRM-008-G)

Core `Task.dateCompleted` is `readOnly`: the API discards it on create and update. The core hook `Espo\Modules\Crm\Hooks\Task\DateCompleted` sets it whenever the status changes: null for any status other than Completed, and **now** for Completed (the REST API does not set the IMPORT option that would skip this). Without a custom rule, every imported completed Task would show the import time.

- **The field.** The importer sends the Salesforce value in `Task.sfCompletedAt` (a datetime, not `readOnly`, so the API accepts it).
- **The hook.** `custom/Espo/Custom/Hooks/Task/PreserveSalesforceCompletedDate.php` is a `beforeSave` hook with `$order = 20`, so it runs after the core hook. It receives the saving user by constructor injection (`Espo\Entities\User`). When the status is `Completed`, `sfCompletedAt` is set, **and** the Task is new, or `sfCompletedAt` changed in this save, or the status changed in a save by ER Import (type `api` **and** userName `er-import`, the same check as `ProtectArchivedEmail` and `RequireLossReason`; CRM-008-G round 3), it sets `dateCompleted = sfCompletedAt`. The last case is the importer re-completing a Task that staff reopened (CRM-008-G round 2). Every other save is left to core:
  - an unrelated edit leaves `dateCompleted` unchanged;
  - reopening a Task sets it to null (core);
  - a staff member re-completing a reopened Task gets core's "now", because `sfCompletedAt` did not change and a person is not ER Import; so does any other API user;
  - a Task that is not Completed keeps a null `dateCompleted`, even with `sfCompletedAt` set;
  - a Completed Task with no `sfCompletedAt` (no source completion date) gets core's "now": **EspoCRM shows the import time** for it. Every importer run records each Task stored in that state as `date_completed_server_stamped` (see [IMPORT.md](IMPORT.md)).
- **The decision table** is mirrored in `tests/unit/activity_policy.py` (`completed_date_after_save`), checked statically against the hook, and run against the real hook file under `php` with stubs when `php` is installed.

## 3. No email sending or receiving (D5)

There are no email accounts, no SMTP, no sending and no inbound mail. **Operator setting:** in Administration > Outbound Emails, leave the SMTP server unset, so nothing can be sent. Check this at the operator stage; the exact labels are not verified in this repository. Do not create Group or Personal Email Accounts. The roles keep `EmailAccountScope` and `ExternalAccount` false.

## 4. Activities and History panels

The core clientDefs of Opportunity (the Enquiry), Account and Contact already have the `activities`, `history` and `tasks` side panels, so CRM-005 does not recreate or change them. Activities lists upcoming Calls and Meetings; History lists held ones and Emails, including archived ones linked by `parent`. The operator checks this in AC3 on an enquiry with synthetic data.

## 5. Calendar and follow-ups

- **Calendar** (core). Each user's Calendar shows their meetings, calls and tasks. For a team view, open Calendar, choose **Shared** mode, and pick the users or the team (Enquiries, Ancillary intake or Firm management). Every human role has the Calendar scope.
- **Follow-ups** use the core Task with `dateEnd` (the due date) and `reminders`.
- **The "ER Staff" dashboard template** in `config/access/dashboards.json` has a Tasks dashlet titled "My open tasks" (the current user's open tasks) and a Calendar dashlet. `scripts/provision_access.py dev --key-file …` creates or updates it by name, idempotently. It is deployed to the Enquiries team **only** with `--deploy-dashboards`, because deploying replaces the dashboards of every user in that team (`append: false`). Run that flag once, after the users are provisioned, and again only when users should lose their own dashboard layouts.

## 6. Tests

- `tests/unit/test_activities.py` covers metadata consistency, the unique indexes, the meeting type, the layouts, the dashboard template, the archived-email hook and the Task completion-date hook. Each rule fails against a mutated (broken) copy of the repository.
- `tests/unit/test_access_policy.py` covers the role changes: Email edit, and the activity `sf*` `fieldData` (including `Task.sfCompletedAt`).
- `tests/unit/test_provision.py` covers the dashboard provisioning against the fake EspoCRM.
- AC3 to AC7 run at the operator stage on `crm-dev`.
