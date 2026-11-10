# Import: Salesforce snapshot → EspoCRM (CRM-006)

`crm-load` reads one sealed snapshot, produced by `crm-migrate` (CRM-002), and creates or updates EspoCRM records through the REST API as the `ER Import` API user. Every record is keyed on its immutable Salesforce id (`sfId`).

- Re-running it on the same snapshot makes **zero** writes.
- It **never deletes** anything.
- It never invents ownership or values. Anything it can't map is left empty and recorded in the exception file.

| Path | Purpose |
|---|---|
| `scripts/load.sh` | The operator wrapper. Root only. |
| `load/bin/crm-load.py` | The entry point, run as `python3 -I -B`. Standard library only. |
| `load/lib/crm_load/` | Gate, reader, mapping, upsert engine, report and transport. |
| `load/contract/mapping.json` | The versioned mapping (`mappingVersion` 2, `contractVersion` 4). |
| `load/contract/lead_source_map.json` | The PO-approved D7 LeadSource table. It starts empty. |
| `load/contract/name_patterns.json` | The D8 enquiry-name patterns. The table ships **empty** (PL decision): until patterns are added, every enquiry gets `name_unparsed` and the name parts stay empty. The patterns are derived after the load from a counts-only analysis of the loaded names, then added by the PL; a re-run fills the parts. |
| `load/examples/role-map.example.json` | An example Profile/Role → team/role table, with placeholders only. |

**Usage note.** `load/bin/crm-load.py` and `scripts/crm_api.py` have the executable bit but no shebang, by design. Always run them through the interpreter as `python3 -I -B <file> …`, never as `./<file>`. `-I` keeps the environment and the current directory off the import path, and `-B` writes no `.pyc` files.

## Operator procedure

Do these steps in order, as root, on DOCKER1.

1. **Prerequisites.**
   - The target stack is running with the CRM-003 to CRM-006R customisation deployed. This includes `Contact.opportunityRole` options and the `Import` scope on `ER Import`. Run `scripts/deploy_custom.sh` and then `scripts/provision_access.py`.
   - The snapshot is sealed under `/srv/CRM/runtime/migrate/snapshots/`: owned by root, directories `0700`, files `0400`. `migrate.sh` does this. For `dev` that is the `<name>-selftest/` directory; for `beta` it is the `<name>-extract/` directory.
   - **Target Settings (operator precondition).** The target must have these four Settings values:
     - `currencyList` `["GBP"]`, `defaultCurrency` `GBP` and `baseCurrency` `GBP`. The EspoCRM 10.0.12 install default is USD only. Without GBP in `currencyList`, **every Opportunity with an amount** is refused with `400 amount validCurrency` (`write_rejected`), because the loader sends `amountCurrency: GBP`.
     - `phoneNumberInternational` `false` (see the phone setting below).

     `scripts/provision_access.py <target>` applies all four from `config/settings.json`. It is idempotent: it reads `GET Settings`, sends only the keys that differ, and a second run reports `settings: unchanged`. `PUT Settings` needs the admin account, so run `provision_access.py` before the load.
   - **Phone setting.** `phoneNumberInternational` must be `false` on the target. `scripts/provision_access.py <target>` sets it, with the currency settings above. With the default `true`, EspoCRM refuses UK national formats such as `01632 960000` (`400 phoneNumber valid`) and rewrites `+44 …` as `+441632960000`. Those phones are then dropped with `phone_rejected`, and every re-run tries them again, so re-runs are not write-free. With `false`, numbers are stored verbatim and only junk such as `n/a` is refused.
2. **Write the env file.** Create `/srv/CRM/runtime/<target>/load.env`, owned by root and mode `0600`, with exactly these lines:
   ```
   CRM_LOAD_HOST=127.0.0.1
   CRM_LOAD_PORT=<published loopback port of crm-app for this target>
   CRM_LOAD_API_KEY=<ER Import API key, from the provision_access.py 0600 output>
   ```
   The file is parsed, never sourced. Any other variable, a repeated name or a malformed line is refused. `load.sh` hands the three values to `crm-load` only as exported environment variables (with `PATH` and `LANG`, in an otherwise cleared environment), never as command-line arguments, so the key never appears in any process's argv.
3. **Export the users.** Run `python3 -I -B load/bin/crm-load.py users <snapshot> --role-map <table.json> --out <new dir>`. It writes `users.json` (0600) in the input format of `scripts/provision_users.py`.
   - Only `UserType = Standard` users are exported. Integration, automated-process and CsnOnly users are counted as `skipped_user_not_human`. Records they own get an `owner_unresolved` exception at load time.
   - The shared "Ancillary Services" login, listed in the role map under `legacyShared.sfIds`, becomes the inactive legacy user (D4). Inactive Salesforce users stay inactive (D5).
   - Teams and roles come **only** from the role map. A profile or role that isn't in the map gets nothing.
4. **Provision the users.** Run `scripts/provision_users.py <target>` with that `users.json`. The importer never creates users.
5. **Load.** Run `scripts/load.sh [--accept-drift <URL>] [--reconciliation <reconcile run dir>] [--resume <previous output dir>] <dev|beta> <snapshot> <new output dir>`, where `<snapshot>` is `/srv/CRM/runtime/migrate/snapshots/<name>-selftest/run-1` (or `run-2`) for `dev`, and `/srv/CRM/runtime/migrate/snapshots/<name>-extract` for `beta`.
   - `<id>` is in exactly one of two layouts (the CRM-002-W rule); anything else is refused:
     - client credentials: `<id>/manifest.json`, with no `<id>/run` and no `<id>/input`;
     - legacy mode (the real extraction): `<id>/run/manifest.json`, with no `<id>/manifest.json`, and only `input/` and `run/` at the top. `input/waiver.json` is never read.
   - `--reconciliation` names the separate, sealed reconcile run directory, directly under the snapshots directory. It is required for `beta` and optional for `dev`. Its layout is fixed: the name ends in `-reconcile`, the top level holds only the `report/` directory, and `report/manifest.json` is its own manifest with `"mode": "reconcile"` and `files` keys relative to `report/`, which must include `reconciliation.json`. Any other layout is refused (`reconciliation_layout_unknown`). The `snapshot` object in `reconciliation.json` must match the snapshot being loaded: `t_start`, `status`, `contract_sha256` and `contract_version` must equal the extract manifest's `t_start`, `status`, `contract.sha256` and `contract.version`. Otherwise the load is refused (`reconciliation_snapshot_mismatch`). The reconciliation supplies the `absent_unexplained` counts. Without it, those counts are reported as `"unknown"`. A report inside the snapshot is not used.
   - `--resume` names an earlier, interrupted output directory (root-owned `0700`, holding only root-owned `0600` `run.json` and `progress.jsonl`). Its `run.json` must record the same snapshot manifest sha256 and target. It is only read: its progress is copied into the new output directory, which must still not exist.
   - **Synthetic means exactly this:** the snapshot path is `<SNAPSHOT_BASE>/<name>-selftest/run-1` or `/run-2`; the parent `<name>-selftest/manifest.json` exists, verifies (every file below the parent listed with a matching sha256) and has `"mode": "selftest"`; and the parent is sealed. The run manifests themselves have `"mode": "extract"` and `"origin_kind": "production"`; their mode never makes a snapshot synthetic. `load.sh` checks the path, canonical form and seal on the parent; `crm-load` checks the name, the seal (owned by the running user, which is root under `load.sh`), and the parent manifest's checksums and mode.
   - `dev` loads only a synthetic snapshot (`target_dev_requires_synthetic`).
   - `beta` loads only a `<name>-extract` directory, in either layout, directly under the snapshots directory. Anything under a `*-selftest` directory is refused by `load.sh` and by `crm-load` (`target_beta_requires_extract`). As defence in depth, `crm-load` also refuses (`synthetic_content_in_beta`) a snapshot in which any Account `Name` contains `SENTINEL-7f3a`, the marker on every synthetic record. The real snapshot is loaded only into `crm-beta`.
   - The output directory must not exist and must not be under the snapshots directory. Its parent must be a root-owned `0700` directory. `crm-load` creates the output directory as `0700` and its files as `0600`.
   - For a `RECONCILED_WITH_DRIFT` snapshot, pass `--accept-drift https://github.com/infosec-estateresearch/CRM/issues/9#issuecomment-<digits>`. `load.sh` checks the URL format and passes it to `crm-load`, which refuses it for a `RECONCILED` snapshot.
6. **Review.**
   - Check `load-report.json`. The `relationships` snapshot and EspoCRM totals must be equal, and `deletes` is always 0.
   - Work through `exceptions.jsonl` by reason code.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Loaded. There may be exceptions, but there were no write failures. |
| 2 | Usage or config refused: a `load.sh` guard, a missing env, the wrong target for the snapshot type, or the output directory exists. |
| 3 | The input gate refused the snapshot. |
| 4 | Transport: EspoCRM is unreachable, a redirect, or a failed list. |
| 5 | Finished, but some writes failed (`write_failed` or `write_rejected`). Investigate, then run again. |

## Input gate

`crm-load` refuses the snapshot, with exit 3 and no request to EspoCRM, unless every one of these holds:

- **Layout.** `manifest.json` is in exactly one of the two layouts above.
- **Checksums.** `manifest.json` lists every file with a matching sha256. A missing or unlisted file, a symlink or a special file is refused.
- **Mode.** The manifest `mode` is `extract`. Whether the snapshot is synthetic is decided by its location (see the `dev`/`beta` rules above), never by this mode.
- **Rows.** Every row is a JSON object with a string `Id`. A dict or list in any field the mapping reads is not a refusal: that record gets the exception `value_shape` and is not written (counted as `skipped.value_shape`).
- **Status.** The status is `RECONCILED`, or `RECONCILED_WITH_DRIFT` with `--accept-drift https://github.com/infosec-estateresearch/CRM/issues/9#issuecomment-<n>`.
- **Contract version.** The contract version is exactly the integer `4`. `4.0`, `"4"` and `true` are refused.

The snapshot is opened read-only.

## Order of work

1. **Index.** One paged read per entity (User, ServiceType, Account, Contact, Opportunity, Task, Call, Meeting, Email), using `where isNotNull sfId` (`sfValue` for ServiceType) and `maxSize=200`.
2. **ServiceType.** One record per distinct `Opportunity_Service__c` value: `name` and `sfValue`.
3. **Account.** Then a **second pass** sets `parentId` once every Account exists.
4. **Contact.**
5. **Opportunity** (Enquiry).
6. **OpportunityContactRole.** `contactsIds` and `contactsColumns` on the Opportunity, merged with what is already there.
7. **Task.** By `TaskSubtype`:
   - Task becomes Task;
   - Call becomes Call;
   - Email and ListEmail become an archived Email.

   A Task-Email that has an EmailMessage is skipped (`represented_by_email_message`).
   A Task-Email (Email or ListEmail) that **no** EmailMessage represents (no EmailMessage `ActivityId` is its Id) is imported as a **Task** (CRM-008), with the fields of a plain Task: Subject is the name, Description the description, status, priority and dates are kept, and so is its parent. It is recorded as `task_email_imported_as_task`. An Email needs a `from` address, which only an EmailMessage has. A row an earlier run already created as an Email stays an Email (it is never moved).
8. **Event** becomes a Meeting.
9. **EmailMessage**, with its EmailMessageRelation rows, becomes an archived Email. One whose To list is empty after validation becomes a Task (CRM-008-F, see the mapping summary).
10. **Flag.** EspoCRM records whose `sfId` isn't current in the snapshot are flagged as exceptions, **never deleted**.
11. **Report.** The report and exceptions files are written, and a fresh read computes the relationship totals.

Every create sends `X-Skip-Duplicate-Check: true`, because branch firms share names. Uniqueness is on `sfId`, through the index. Updates send only the attributes that changed.

## Mapping summary

The full mapping is in `load/contract/mapping.json`. The decisions are in `MIGRATION-DECISIONS.md` D1–D13.

- **Account.**
  - Copied: name, type (tier), industry, phone, website, description, and `learningPlatformAccess` from `TLP__c`.
  - Addresses are swapped (R4): Salesforce **Shipping** goes to EspoCRM **billing**, and Salesforce Billing goes to EspoCRM shipping.
  - `parentId` is set in the second pass.
  - Also set: owner, `sfOwnerId` and `sfCreatedAt`.
- **Contact.**
  - Copied: names, title, email, and the Mailing address.
  - **Title needs an account (CRM-008-F).** EspoCRM 10.0.12 stores a Contact's `title` through its account link: without an account, a sent `title` reads back as null. So when the Contact has no resolved account, `title` is **not sent** and not compared, and a non-blank Title is recorded as `title_unstorable_without_account` (record id only). In the real extract every Contact with a Title has an AccountId. A Contact whose account later becomes unresolved keeps the title EspoCRM already holds.
  - `Salutation` goes to the core enum `salutationName`, which EspoCRM validates (options `""`, `Mr.`, `Ms.`, `Mrs.`, `Dr.`; an unlisted value is `400 valid`). A value outside the options is sent as `null` with `enum_unmapped`; it is never forced into an option.
  - Phones go to `phoneNumberData`: `Phone` is `Office`, and is primary when present; `MobilePhone` is `Mobile`. A value without a digit (`n/a`) is never sent (`phone_rejected`). If a create or update still fails with `400` on the field `phoneNumber`, it is retried **once** without the phone attributes, the record is kept, and `phone_rejected` is recorded. The phone is never invented. Account `Phone` follows the same rules.
  - EspoCRM reads `phoneNumberData` back with extra keys (`optOut`, `invalid`). Only `(phoneNumber, type, primary)` is compared, as an order-insensitive set. With `phoneNumberInternational=false` EspoCRM trims each number on save (`"  01632 960000  "` is stored as `"01632 960000"`), so numbers are compared trimmed, in `phoneNumberData` as in the `phoneNumber` attribute.
  - **Phone comparison (CRM-008-F).** EspoCRM's list read does not return `phoneNumberData`, only `phoneNumber` (the primary number); a single-record read `GET Contact/{id}` does. The index therefore holds the primary only, and an existing record is compared like this:
    - the source primary (trimmed) differs from the listed `phoneNumber`: the phones are written, with no extra read;
    - they are equal and the source has **exactly one** number: no difference (the type is not re-checked);
    - they are equal and the source has **two or more** numbers: the record is read once with `GET Contact/{id}` and the full set is compared as above. These reads are bounded by such records and counted in `requests.reads`. A refused read stops the run with `read_failed` (exit 4).
    - no source phone and no listed `phoneNumber`: no difference.
  - Also set: account and owner.
- **Opportunity.**
  - The stage follows D1, with `sfStageName` kept.
  - `legacyStale` (D2) is set when the stage is Enquiry or Quoted and the close date is before the manifest `t_start`.
  - `lossReason` and `lossReasonLegacyMissing` follow D3.
  - `amount` is set, with `amountCurrency: GBP` whenever there is an amount. It is compared numerically (`100.5` equals `"100.50"`).
  - Also set: close date, description, `serviceType`, `enquiryCategory` and `businessType`.
  - `sfLeadSource` is kept raw. `introducedBy` and `channel` are filled only from the D7 table.
  - The D8 name parts come from `name_patterns.json`.
  - `postcode` and `keyInformation` stay empty, because those fields aren't in the contract.
- **Contact roles.** EspoCRM validates the role against `Contact.opportunityRole.options`, which hold the Salesforce picklist. A null role is linked with `""`. A value outside the options is linked with `""` and gets the exception `role_unmapped`.
- **Task.**
  - Status: Open becomes `Not Started` and Completed becomes `Completed`.
  - Priority: Normal and High map to themselves.
  - The parent is resolved from `WhatId` by key prefix, falling back to `AccountId`.
  - **`dateCompleted` only when Completed (CRM-008-F).** EspoCRM keeps `dateCompleted` only for status `Completed`; for any other status a sent value reads back null. It is sent (from `CompletedDateTime`, or null) only when the mapped status is `Completed`. Otherwise it is neither sent nor compared, and a set `CompletedDateTime` is recorded as `date_completed_not_storable`. In the real extract no row has this combination.
- **Call.**
  - Status is `Held`.
  - `CallType` `Inbound` and `Outbound` map exactly to `direction`. For a blank `CallType`, **no direction is sent** and `call_direction_unknown` is recorded; EspoCRM then shows its core default (`Outbound`), which is not a Salesforce value. Any other (unmapped, non-blank) `CallType` is treated the same way: no direction is sent, with `call_direction_unknown` plus `enum_unmapped`.
  - `dateStart` (required in core) is `CompletedDateTime`. When it is null, `ActivityDate` at `00:00:00` is used with `date_start_from_activity_date`, else `CreatedDate` with `date_start_from_created`.
- **Meeting.**
  - `meetingType` comes from `Type`. A null `Type` becomes `Unspecified (legacy)` (D10).
  - `dateStart` (required in core) is `StartDateTime`, else `ActivityDateTime`, else `CreatedDate` with `date_start_from_created`.
  - Status is `Held` if `EndDateTime` is before the manifest `t_start`, otherwise `Planned`.
  - Attendees are **the owner only**, because EventRelation isn't in the contract.
- **Email** (from an EmailMessage). The email is created as follows:
  - status is `Archived`;
  - set from the message: `from` (the **bare** `FromAddress`; EspoCRM drops a `"Name <addr>"` value there), `fromString` (`"FromName <FromAddress>"`, or the address alone when there is no name), `to` and `cc` (`;`-separated, as EspoCRM reads them back), the subject, and `bodyPlain` and `body` from **TextBody only**, with `isHtml` false;
  - `dateSent` from `MessageDate`. It is not required, so it stays null when it can't be derived; it is never taken from `CreatedDate`. A Task-Email's `dateSent` is its `CompletedDateTime` or null;
  - **`MessageIdentifier` is not mapped.** EspoCRM 10.0.12 replaces `messageId` with `dummy:<id>` on every API write, so it is neither sent nor compared (`notMapped` in `mapping.json`). `ThreadIdentifier` goes to `sfThreadIdentifier`;
  - the thread and activity keys;
  - the parent comes from `RelatedToId`, otherwise from the parent of the linked Task;
  - users come from the User relations;
  - **no contact links are written.** EspoCRM associates contacts with an archived email through the email addresses in `from`, `to` and `cc`.

  **No Bcc and no attachments.**

  **No recipient: a Task (CRM-008-F).** `Email.to` is required (`400 to required`). An EmailMessage whose To list is empty after validation (a blank `ToAddress`, or every address in it dropped as `email_address_invalid`) is imported as a **Task**, following the CRM-008 Task-Email rule, with the code `email_without_recipient_imported_as_task`:
  - Subject is the name; the plain body (`TextBody`) is the description, as-is; status is `Completed`; `dateCompleted` comes from `MessageDate`; `dateEndDate` is null; the parent is resolved as for the Email.
  - The HTML body is not in contract v4 (D5 excludes `HtmlBody`), so a message with only an HTML body has a null description. No HTML is converted.
  - The owner (required on a Task) is, in this order:
    1. the owner of the linked Task (`ActivityId`), resolved as usual;
    2. if there is no linked Task, or its owner doesn't resolve, the EmailMessage's `CreatedById` (contract v4) when it resolves to a provisioned user: the Salesforce user who logged the message, a recorded fact. This is recorded as `owner_from_created_by`, `sfOwnerId` holds that `CreatedById`, and the linked Task's `owner_unresolved` / `owner_queue_or_group` is not recorded (the record has an owner);
    3. otherwise the record is refused with `owner_required_unresolved`, never guessed and never sent.
  - `priority` has no source and is not sent, so EspoCRM stores its core default (`Normal`). This is recorded once per such record as `priority_server_default`, the same treatment as `call_direction_unknown`.
  - It is counted under `EmailMessage` → `targets.Task`; on a re-run it is found in the Task index (not flagged as `exists_not_in_snapshot`).
  - An EmailMessage already created as an Email by an earlier run **stays an Email**. Its `to` is then left out of the update (a null `to` would be refused), so EspoCRM keeps the stored recipients.

  EmailMessageRelation rows hidden through a soft-deleted EmailMessage or Contact (contract v4 `visibleVia`) are **skipped** and counted as `parent_soft_deleted`.
- **Note.** Not imported (D6). Notes are counted as `out_of_scope`.
- **Datetimes and dates.** Every datetime sent is `YYYY-MM-DD HH:MM:SS` UTC and every date `YYYY-MM-DD`, the forms EspoCRM reads back, so the comparison on a re-run is exact.
- **Soft-deleted parents.** A current record is never linked to a parent, account, contact or opportunity that is soft-deleted in the snapshot, even if EspoCRM still holds it from an earlier load. The link stays empty and `parent_soft_deleted_in_sf` is recorded.
- **Not created.** Records soft-deleted in Salesforce are never created and are counted as `soft_deleted`. `absent_unexplained` counts come from the reconciliation. If such a record already exists in EspoCRM, it is flagged, not deleted.

### Owner resolution

- `OwnerId` resolves through the index of provisioned users (`GET User?select=id,sfId`).
- If the owner is a queue or group (`00G…`), or doesn't resolve (including non-human users), `assignedUser` stays **empty**, `sfOwnerId` is kept, and the exception `owner_queue_or_group` or `owner_unresolved` is recorded.
- Ownership is never guessed.
- **Required owner (CRM-008).** `assignedUser` is required on core Task, Call and Meeting. For these, an unresolved owner (including a queue or group) **refuses the record**: it is not sent, the code is `owner_required_unresolved` (with `owner_queue_or_group` for a queue), and it is counted in `skipped.owner_required_unresolved`. No placeholder owner is used. Account, Contact, Opportunity and Email keep `owner_unresolved` and are still created without an owner.

### Length limits and email addresses (CRM-008)

- **Length limits.** `mapping.json` `maxLength` holds the target limits: Account `name` 249; address city, state and country 100 and postal code 40; Contact `title` 255 (raised in the custom Contact entityDefs); `sfStageName`, `sfLeadSource`, `clientReference` and `caseNumber` 100; ServiceType `name` 150; phone numbers 36. Before sending, each such value (trimmed) is checked. A value that is too long is sent as **null** and recorded as `value_too_long` with the record id and the **attribute name** only. It is never truncated. A phone number longer than 36 is dropped with `phone_rejected`.
  - **Attribute names are qualified** by the target entity, for example `Account.billingAddressCity`, `ServiceType.name` or `Opportunity.sfLeadSource`. A ServiceType is reported against the first Opportunity that names it, so `ServiceType.name` on an Opportunity line means the service-type name was too long, not the Opportunity's own name.
  - **Required attributes refuse the record.** Account `name` and ServiceType `name` are required in EspoCRM (null is `400 required`). `mapping.json` `requiredAttributes` lists them. If one of them is too long, the record is **not sent** (on create or update). It gets `value_too_long` with its attribute name and is counted in `skipped.value_too_long`. An Account already in EspoCRM keeps its stored name. A refused ServiceType is counted under `objects.Opportunity.skipped.value_too_long`. Opportunities naming it are still written, with `serviceTypeId` empty, and each gets `service_type_refused`. A refused record (an over-length required attribute, or `enum_blank_unrepresentable`) gets **no write at all** in that run: no parent link (Account second pass) and no contact roles (Opportunity). It is counted once, in `skipped`, never also as `updated`.
  - **Update clears the field.** A non-required over-length value is also sent as null on **update**, so it **clears** whatever that field held in EspoCRM (for example, a value stored by an earlier run before the source value grew).
- **Email addresses.** Each address is validated against an approximation of EspoCRM's check (PHP `FILTER_VALIDATE_EMAIL`). The rule is deliberately **stricter** than PHP's, so a borderline address is refused here rather than sent and refused by the server. Some addresses PHP would accept are therefore dropped. On the real extract, the PL counted (counts only) **3** addresses dropped with `email_address_invalid` (2 To, 1 Cc) and **0** `from` addresses refused. An address is valid only if it is ASCII, at most 254 characters, has no whitespace, and is `local@domain` where:
  - the local part is a dot-atom (letters, digits and ``!#$%&'*+/=?^_`{|}~-``, single dots not at either end), at most 64 characters, never quoted;
  - the domain has at least two dot-separated labels of letters, digits and hyphens (1 to 63 characters, no leading or trailing hyphen), ending in an alphabetic top-level label of 2 to 63 letters; IP literals are refused.

  An invalid To or Cc address is dropped from the list (`email_address_invalid`, record id only). An invalid or blank `from` refuses the EmailMessage (`email_from_invalid`, counted in `skipped.email_from_invalid`).

## `load-report.json` (counts only)

| Key | Content |
|---|---|
| `objects.<Object>.source_rows` / `source_current` | Rows in the snapshot, and how many are not soft-deleted. |
| `objects.<Object>.targets.<Entity>` | `created`, `updated`, `unchanged`, `failed`. |
| `objects.Account.second_pass` | Counts for the parent pass. |
| `objects.<Object>.skipped` | `soft_deleted`, `absent_unexplained` (`"unknown"` without `--reconciliation`), `out_of_scope` (Note), `represented_by_email_message` (Task), `value_shape` (any object), `parent_soft_deleted` (EmailMessageRelation), `user_not_human` (User), `owner_required_unresolved` (Task, Event), `email_from_invalid` (EmailMessage), `value_too_long` (Account; Opportunity for a refused ServiceType). |
| `objects.<Object>.exceptions` | Exception counts by reason. |
| `existingNotCurrentInSnapshot` | Per entity: EspoCRM records flagged, never deleted. |
| `exceptions` | `total` and `byReason`. |
| `relationships` | `account_parents`, `contact_accounts`, `enquiry_contacts` and `activity_parents`, each `{snapshot, espocrm}`. They must be equal. |
| `requests` | `writes` and `reads`. |
| `deletes` | Always 0. |
| `snapshotStatus`, `acceptedDrift`, `synthetic`, `snapshotManifestSha` (sha256 of `manifest.json`), `reconciliation` (a reconciliation run was used), `mappingVersion`, `contractVersion`, `tool` | Run metadata. |

It holds no names, values or free text.

## `exceptions.jsonl` (root `0600`)

There is one line per `{object, sfId, reason}`. It holds ids and codes only; a `value_too_long` line also has `attributes`, the qualified attribute names (`Entity.attribute`).

| Reason | Meaning |
|---|---|
| `owner_queue_or_group` | The owner is a queue or group. `assignedUser` is empty and `sfOwnerId` is kept. |
| `owner_unresolved` | The owner is not a provisioned user: inactive and not provisioned, non-human, or missing. |
| `owner_required_unresolved` | (Task, Call, Meeting) The owner is unresolved and `assignedUser` is required: the record is not written. |
| `task_email_imported_as_task` | A Task-Email with no EmailMessage was imported as a Task. |
| `value_too_long` | A value exceeds the target `maxLength`: sent as null (create and update), never truncated. For a required attribute (Account and ServiceType `name`), the record is refused instead and counted in `skipped.value_too_long`. The line carries `attributes` (qualified names only). |
| `email_address_invalid` | An invalid To or Cc address was dropped from the list. |
| `email_without_recipient_imported_as_task` | (EmailMessage) The To list is empty after validation; `Email.to` is required, so the message was imported as a Task. |
| `owner_from_created_by` | (EmailMessage imported as a Task) No linked Task, or its owner is unresolved; the owner is the provisioned user in the EmailMessage's `CreatedById`. |
| `priority_server_default` | (EmailMessage imported as a Task) `priority` has no source and was not sent; EspoCRM stores its core default (`Normal`). |
| `title_unstorable_without_account` | (Contact) The Contact has a Title but no resolved account; EspoCRM stores no title without an account, so it was not sent. |
| `date_completed_not_storable` | (Task) `CompletedDateTime` is set but the mapped status isn't `Completed`; EspoCRM keeps no `dateCompleted` then, so it was not sent. |
| `email_from_invalid` | The EmailMessage `from` is blank or invalid: the record is not written. |
| `service_type_refused` | (Opportunity) The ServiceType this Opportunity names was refused (`value_too_long` on ServiceType `name`). The Opportunity is written with `serviceTypeId` null. The line carries the record id only. |
| `account_unresolved` | `AccountId` doesn't resolve, for example because the account is soft-deleted. |
| `parent_unresolved` | The Account `ParentId` doesn't resolve. |
| `contact_unresolved` / `opportunity_unresolved` | The contact role or relation endpoint doesn't resolve. |
| `activity_parent_unresolved` | No Opportunity or Account parent resolves. |
| `enum_unmapped` | The value isn't one of the target options, so it is left empty. |
| `stage_unmapped` | The StageName isn't in D1. `stage` is empty and `sfStageName` is kept. |
| `status_unmapped` | The Task status isn't in the table. |
| `role_unmapped` | The contact role isn't in `Contact.opportunityRole.options`, so it is linked with `""`. |
| `name_unparsed` | The enquiry name matched no D8 pattern, so the name parts are empty. |
| `datetime_invalid` | A date or datetime couldn't be parsed. |
| `phone_rejected` | A phone was not stored: it has no digit, or EspoCRM refused it (`400` on `phoneNumber`) and the write was retried once without it. The record is kept. |
| `call_direction_unknown` | The Call's `CallType` is blank or unmapped (then also `enum_unmapped`), so no direction was sent. EspoCRM shows its core default. |
| `synthetic_enum_mapped` | (selftest snapshots on dev only) A synthetic picklist value (`Value A`/`B`/`C`) was mapped through `syntheticEnumMap`. Counted once per record. Never occurs for a real snapshot. |
| `date_start_from_activity_date` / `date_start_from_created` | The required `dateStart` came from `ActivityDate` or `CreatedDate`, because the primary datetime is null. |
| `parent_soft_deleted_in_sf` | The referenced parent, account, contact or opportunity is soft-deleted in the snapshot, so no link was written. |
| `value_shape` | A field the mapping reads holds a dict or list. The record is not written. |
| `exists_soft_deleted_in_sf` | An EspoCRM record exists for an sfId that is soft-deleted in Salesforce. It is flagged, not deleted. |
| `exists_not_in_snapshot` | An EspoCRM record exists for an sfId that isn't in the snapshot. It is flagged, not deleted. |
| `duplicate_conflict` | 409 `DuplicateConflict` from EspoCRM. This isn't expected, because every POST skips the name check. |
| `write_rejected` | Any other 4xx on a write. |
| `write_failed` | 5xx after the bounded retries (5, with exponential backoff). The **likely cause on create** is a unique-index violation on `sfId`: EspoCRM's unique index also counts soft-deleted rows, so a soft-deleted EspoCRM record holding that key makes the create fail with HTTP 500. Find it in the database and decide by hand. The importer never deletes and never loops. |
| `enum_blank_unrepresentable` | A mapped enum target without a `""` option (`Opportunity.stage`, `Task.status`, `Task.priority`) would receive a blank or unmapped value. The record is not written (never defaulted); see "Importer fidelity". |
| `call_duration_unknown` | The Call's `CallDurationInSeconds` is blank: `duration` is sent as null and EspoCRM shows 0 minutes. |
| `phone_refused` | EspoCRM refused this phone number (400 on `phoneNumber`); the record and its other numbers are kept, the refusal is remembered by hash in `phone-refusals.json`. |
| `user_not_exportable` | (`crm-load users`) The user has no valid user name (real snapshots: the Username local part; selftest snapshots: derived from the sfId, see below) or last name, or shares the Username local part (case-insensitive) with another exported user; then **both** are refused. |

## Re-runs, retries and resume

- **Re-run.** Running again on the same snapshot, with a new output directory, makes zero writes (given `phoneNumberInternational = false`, see the prerequisites) and reports every record as `unchanged`. A changed snapshot updates only the attributes that differ. Link-multiples are merged, never reduced.
- **Retries.** HTTP 429 and 5xx are retried up to 5 times, with exponential backoff. 4xx is not retried.
- **Interrupted run.** Every write is appended to `progress.jsonl` in the output directory (phase, sfId and action only). A run can be resumed in either of two ways:
  - run `load.sh` again with a **new** output directory. The index finds everything already written, so nothing is repeated. The counts show those records as `unchanged`;
  - or run `load.sh --resume <earlier output dir> <target> <snapshot> <new output dir>`. The earlier directory's `run.json` must hold the same snapshot manifest sha256 and target. Its progress log is copied into the new output and credits completed writes, so the report equals that of an uninterrupted run. `--resume` refuses a directory that already has a report, or holds anything besides `run.json` and `progress.jsonl`.
- **Network.** The only network use is plain HTTP (`LoopbackHttpTransport`) to `http://127.0.0.1:<port>/api/v1/`. Any other host is refused, and redirects are never followed.

## Importer fidelity (CRM-006S)

- **No stored server defaults.** On create and update every mapped attribute whose source value is blank is sent as an explicit `null`; it is never omitted, because EspoCRM then stores the entityDefs default (a manufactured value). After the first run every blank source value reads back as blank. The single exception is `Call.direction` (CRM-006R rule, unchanged): a blank `CallType` sends no direction, with `call_direction_unknown`, so EspoCRM shows its core default `Outbound`.
- **`learningPlatformAccess` blank option.** The field has `""` as its first option (default `No` and the order of the other options unchanged), so a blank `TLP__c` is stored as blank, not `No`.
- **Enums without a blank option.** `load/contract/mapping.json` `enumNoBlank.attributes` lists the mapped enum targets whose options have no `""` (`Opportunity.stage`, `Task.status`, `Task.priority`): EspoCRM refuses `null` and `""` there, and omitting stores the default. A record whose value for one of them is blank or unmapped is **not written**: exception `enum_blank_unrepresentable` (record id only), counted under `skipped.enum_blank_unrepresentable`; an unmapped stage also keeps `stage_unmapped`. `Meeting.meetingType` accepts an explicit null (PL-verified) and is listed in `nullAccepted`. A test fails if a blankable mapped enum target has neither `""` nor one of these listings.
- **Call duration.** Salesforce `CallDurationInSeconds` is blank on Calls; the importer sends `duration: null` and records `call_duration_unknown` per record. EspoCRM derives the duration from `dateEnd − dateStart`, so **these calls show 0 minutes** in EspoCRM. A stored `0` compares equal to a blank source, so it never causes a write.
- **Compared as stored.** varchar values are trimmed on save by EspoCRM (core `StringTrim`); `text` attributes (`description`, Email `body`/`bodyPlain`, listed in `mapping.json` `textAttributes`) are stored verbatim. The importer compares varchar values trimmed and text values verbatim, so padded source values cause no writes on a re-run. The ServiceType key (`Opportunity_Service__c`) is trimmed the same way, so a padded value never creates a second ServiceType.
- **Phone precondition.** Before any write `crm-load load` reads `GET Settings`. With `--target beta` it refuses (exception code `phone_international_enabled`, exit 3) unless `phoneNumberInternational` is exactly `false`; a refused or incomplete read counts as "not confirmed false". The API user of the beta load must be allowed to read Settings. Dev logs the value (`event=settings`) and continues.
- **Per-phone handling.** When EspoCRM refuses a write with `400` on `phoneNumber`, the record is written without its phones, then each number is tried once (one write per number on the record, so at most two for a Contact): accepted numbers are kept (the first kept one is primary), each refused number is reported as `phone_refused` with the record id only. The refusal is remembered in `phone-refusals.json` of the output directory (`0600`): a sorted JSON list of `sha256(["<sfId>","<field>","<number>"])` hex digests, no number in clear. The hashed number is the trimmed one (as EspoCRM stores it), so a number differing only in surrounding blanks is the same refusal. **Pass the previous run's file on every re-run**: `crm-load load … --phone-refusals <previous out>/phone-refusals.json` (`load.sh --phone-refusals FILE`); without it every refused number is probed again and the re-run is not write-free. `load.sh` requires the file to be a canonical, root-owned `0600` regular file (no symlink) under a root-owned `0700` parent (the `--resume` rule); `crm-load` opens it with `O_NOFOLLOW` and checks on the open descriptor (`fstat`) that it is a regular file owned by the running user (root under `load.sh`) with mode `0600` (`phone_refusals_not_sealed`, `phone_refusals_unreadable` otherwise). The load report's `phoneRefusals` states whether a file was supplied (`supplied`), how many hashes it held (`remembered`) and how many refusals this run holds (`refusedThisRun`). A number whose hash is listed is not sent and not retried while its source value is unchanged; the record still reports `phone_refused`, and the run makes no write for it. A changed number has a new hash and is tried again. Only a completed run writes the file, so an interrupted output stays resumable. Note: a phone number has little entropy; the hash keeps the file free of numbers in clear but is not a secret, so keep the file root-only like `exceptions.jsonl`.
- **Synthetic users on dev.** In a synthetic selftest snapshot the user filter also accepts the synthetic `UserType` values `Value A`, `Value B`, `Value C` (what `crm-migrate selftest` writes into every picklist), so the dev owner path runs end to end. A real snapshot accepts `Standard` only. Selftest Usernames (`"<marker> User Username 0"`: a space, no `@`) are never valid EspoCRM user names, so for a selftest snapshot only the user name is derived from the sfId: `syn-` followed by the first 10 hex characters of `sha256(sfId)`, lowercase. A real snapshot keeps the Username local-part rule unchanged.
- **Synthetic enum values on dev (`syntheticEnumMap`).** `crm-migrate selftest` fills every picklist with `Value A`/`B`/`C`, which no stage, status, priority or direction accepts. For a **selftest snapshot only**, `mapping.json` `syntheticEnumMap` maps those values of `StageName` (to stage), Task `Status` and `Priority`, `CallType` (to direction), `TaskSubtype` (to Task/Call/Email) and Event `Type` (to `meetingType`: Meeting, Call, Other; CRM-008) to valid target values, so dev exercises the Opportunity, Task, Call and contact-role paths end to end. Each mapped record gets `synthetic_enum_mapped` (counted). A real snapshot never consults the map: it gets `stage_unmapped`, `status_unmapped`, `enum_unmapped` and `enum_blank_unrepresentable` exactly as without it.
- **Counting phone-only updates.** When an update writes nothing because its only change was phones and every phone probe was refused, the record counts as `unchanged`, not `updated`.
