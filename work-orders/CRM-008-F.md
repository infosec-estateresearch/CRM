WO: CRM-008-F
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-008
BROWSER: no

# CRM-008-F — Live-server fidelity from the second crm-dev load

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10 (Issue #9).
- **Why:** the PL deployed CRM-008 on crm-dev:
  1. `deploy_custom`;
  2. `provision_access` twice; the second run makes no changes, including Settings, so A2 passed;
  3. `load.sh dev` on the full selftest.

  Run 1 created or updated everything except **34 Emails**, which got `400 to required`. An immediate re-run made **88 writes besides those 34 failures**: 54 `PUT Contact [phoneNumberData]`, 5 `PUT Contact [phoneNumberData, title]` and 29 `PUT Task [dateCompleted]`. The faithful fake does not model these behaviours. A PL diagnostic, run on crm-dev with synthetic data only, compared what was sent with what was stored.

## Facts verified by the PL live on crm-dev (EspoCRM 10.0.12)
1. **List reads do not return `phoneNumberData`.** `GET Contact?select=…,phoneNumberData` returns `phoneNumber` (the primary number) but no `phoneNumberData` key. A single-record `GET Contact/{id}` does return it, and it equals what was sent, plus `optOut`/`invalid`. The importer's index therefore never sees stored phones, and it PUTs them on every run.
2. **Contact `title` is stored through the account link.** With no account, a sent `title` reads back as null; with an account, it reads back as sent. **In the real extract, all 22,623 Contacts with a Title have an AccountId.**
3. **Task `dateCompleted` is kept only when the status is Completed.** For a Task whose status is not Completed, a sent `dateCompleted` reads back as null. **In the real extract** (counts only): 8,079 Tasks are Completed with a CompletedDateTime, and 1,045 are Open without one. There are no inconsistent rows.
4. **`Email.to` is required.** An Email whose To list is empty gets `400 to required`. **In the real extract, 54 EmailMessages have a blank ToAddress.** Synthetic emails also become To-less once their invalid addresses are dropped.

## Change
1. **Phones.** For an existing record, compare the source phones with the stored `phoneNumberData`, using the existing set comparison.
   - When the list row's `phoneNumber` (the primary number) differs from the source primary number, a phone write is needed.
   - When the primary matches and the source has more than one number, read the record with one `GET {Entity}/{id}` and compare the full set. Count these reads in `requests.reads`.
   - When the source has exactly one number and it matches `phoneNumber` (trimmed), there is no difference.
   - Model this in the fake: list rows omit `phoneNumberData`, and single-record GETs include it.
2. **Title without an account.** When a Contact has no resolved account, don't send `title`. Record the code `title_unstorable_without_account` (record id only), and leave `title` out of the comparison for that record. Model it in the fake.
3. **dateCompleted.** Send `dateCompleted` only when the mapped status is `Completed`. When CompletedDateTime is set but the status isn't Completed, record `date_completed_not_storable` and leave the attribute out of the comparison. Model it in the fake.
4. **An email with no recipient becomes a Task.** An EmailMessage whose To list is empty after validation is imported as a Task, following the CRM-008 Task-Email rule:
   - Subject becomes the name, the plain body becomes the description, status is Completed, the date comes from MessageDate, and the parent is resolved as for the Email;
   - it gets the code `email_without_recipient_imported_as_task`;
   - an Email that already exists from an earlier run stays an Email.

   Model `to required` in the fake.
5. **IMPORT.md** documents items 1–4.

## Allowlist
- `load/**`
- `tests/load/**`
- `docs/IMPORT.md`

## Acceptance
- **A1:** both suites pass, with mutation evidence per item.
- **A2:** on a full selftest against the extended fake, run 1 has 0 `write_rejected` and run 2 has **0 writes**.
- **A3 (operator, PL, crm-dev):** `load.sh dev` on the full selftest: run 1 has 0 `write_rejected`, and run 2 makes 0 writes.
