WO: CRM-008-G
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-008-F
BROWSER: no

# CRM-008-G — Preserve the Salesforce Task completion date, plus the CRM-008-F advisories

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10 (Issue #9). Without this, every imported completed Task shows the import time as its completion date, which is a manufactured value.
- **Why:** the PL's third crm-dev load (CRM-008-F) had 0 failures on run 1. Run 2 still made 44 writes, all `PUT Task [dateCompleted]`, and the stored value was the time of the first load, not the Salesforce value.

## Facts verified by the PL live on crm-dev (EspoCRM 10.0.12, synthetic probes; the probe is reverted and the runtime matches Git)
1. **Core `Task.dateCompleted` is `readOnly: true`.** The API discards it on create and update.
2. **The core hook `Espo\Modules\Crm\Hooks\Task\DateCompleted::beforeSave`** runs when `status` changes:
   - for a status other than Completed, it sets `dateCompleted = null`;
   - for Completed, it sets **now**, unless the save has the IMPORT option, which the REST API does not set.
3. **A custom `Task.sfCompletedAt` field works:** it is a datetime, **not** readOnly (a readOnly field is also discarded from API input). Together with a custom `beforeSave` hook at `$order = 20`, which runs after core and sets `dateCompleted = sfCompletedAt` when the status is Completed:
   - create Completed with `sfCompletedAt` → `dateCompleted` equals the Salesforce value;
   - an unrelated PUT → unchanged;
   - reopen → null (core);
   - a Task that is not Completed and has `sfCompletedAt` → `dateCompleted` stays null.
4. **Real extract (counts only):** 8,079 Tasks are Completed with a CompletedDateTime. Every EmailMessage imported as a Task (status Completed) has a MessageDate. 1,045 Tasks are Open with none.

## Change
1. **`custom/.../entityDefs/Task.json`:** add `sfCompletedAt` (datetime, not readOnly), with i18n "Completed in Salesforce".
   - Add it to the detail layout as read-only display if layouts are used.
   - In `config/access/roles.json` `fieldData`, make `Task.sfCompletedAt` read-only for ER Staff, ER Intake and ER Manager. ER Import keeps edit.
   - Update the access-policy tests to match.
2. **`custom/Espo/Custom/Hooks/Task/PreserveSalesforceCompletedDate.php`:** a `BeforeSave` hook with `$order = 20`.
   - When `status` is Completed and `sfCompletedAt` is set **and** (the entity is new **or** `sfCompletedAt` changed), it sets `dateCompleted = sfCompletedAt`.
   - A staff member re-completing a reopened task gets core's "now".
   - Add a static unit test, in the style of the existing hook tests.
3. **Importer.**
   - Send `sfCompletedAt` (from CompletedDateTime; for an EmailMessage imported as a Task, from MessageDate) instead of `dateCompleted`.
   - Compare `sfCompletedAt`, never `dateCompleted`.
   - Keep the CRM-008-F rule for a status other than Completed: don't send it, and record `date_completed_not_storable`.
   - Model fact 2 and the hook in the fake.
4. **CRM-008-F advisories:**
   - an EmailMessage that already exists as a Task stays a Task (`email_kept_as_task`) and never also POSTs an Email;
   - `email_without_recipient_imported_as_task` and `priority_server_default` are recorded only for records that are actually sent;
   - add a test pinning a null description for an HTML-only body.
5. **Docs:** IMPORT.md and ACTIVITIES.md.

## Allowlist
- `custom/Espo/Custom/Resources/metadata/entityDefs/Task.json` (`sfCompletedAt` only), its i18n, and the Task detail layout if needed
- `custom/Espo/Custom/Hooks/Task/PreserveSalesforceCompletedDate.php` (new)
- `config/access/roles.json` (`fieldData` `Task.sfCompletedAt` only)
- `load/**`
- `tests/**`
- `docs/IMPORT.md`
- `docs/ACTIVITIES.md`
- `docs/ACCESS.md`

## Acceptance
- **A1:** both suites pass, with mutation evidence per item.
- **A2:** on a full selftest against the fake: run 1 has 0 `write_rejected`, run 2 has 0 writes, and every Completed Task's `dateCompleted` equals its source completion time.
- **A3 (operator, PL, crm-dev):** after `deploy_custom` and `provision_access`, run `load.sh dev` twice: run 1 has 0 failures, and run 2 makes **0 writes**. A completed Task shows its Salesforce completion date.
