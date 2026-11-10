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
| `load/contract/name_patterns.json` | The D8 enquiry-name patterns. They start empty and are added by the PL after L3. |
| `load/examples/role-map.example.json` | An example Profile/Role → team/role table, with placeholders only. |

## Operator procedure

Do these steps in order, as root, on DOCKER1.

1. **Prerequisites.**
   - The target stack is running with the CRM-003 to CRM-006R customisation deployed. This includes `Contact.opportunityRole` options and the `Import` scope on `ER Import`. Run `scripts/deploy_custom.sh` and then `scripts/provision_access.py`.
   - The snapshot is sealed under `/srv/CRM/runtime/migrate/snapshots/<id>/`: owned by root, directories `0700`, files `0400`. `migrate.sh` does this.
2. **Write the env file.** Create `/srv/CRM/runtime/<target>/load.env`, owned by root and mode `0600`, with exactly these lines:
   ```
   CRM_LOAD_HOST=127.0.0.1
   CRM_LOAD_PORT=<published loopback port of crm-app for this target>
   CRM_LOAD_API_KEY=<ER Import API key, from the provision_access.py 0600 output>
   ```
   The file is parsed, never sourced. Any other variable, a repeated name or a malformed line is refused.
3. **Export the users.** Run `python3 -I -B load/bin/crm-load.py users <snapshot> --role-map <table.json> --out <new dir>`. It writes `users.json` (0600) in the input format of `scripts/provision_users.py`.
   - Only `UserType = Standard` users are exported. Integration, automated-process and CsnOnly users are counted as `skipped_user_not_human`. Records they own get an `owner_unresolved` exception at load time.
   - The shared "Ancillary Services" login, listed in the role map under `legacyShared.sfIds`, becomes the inactive legacy user (D4). Inactive Salesforce users stay inactive (D5).
   - Teams and roles come **only** from the role map. A profile or role that isn't in the map gets nothing.
4. **Provision the users.** Run `scripts/provision_users.py <target>` with that `users.json`. The importer never creates users.
5. **Load.** Run `scripts/load.sh [--accept-drift <URL>] [--reconciliation <reconcile run dir>] [--resume <previous output dir>] <dev|beta> /srv/CRM/runtime/migrate/snapshots/<id> <new output dir>`.
   - `<id>` is in exactly one of two layouts (the CRM-002-W rule); anything else is refused:
     - client credentials: `<id>/manifest.json`, with no `<id>/run` and no `<id>/input`;
     - legacy mode (the real extraction): `<id>/run/manifest.json`, with no `<id>/manifest.json`, and only `input/` and `run/` at the top. `input/waiver.json` is never read.
   - `--reconciliation` names the separate, sealed reconcile run directory, directly under the snapshots directory. It is required for `beta` and optional for `dev`. Its layout is fixed: the name ends in `-reconcile`, the top level holds only the `report/` directory, and `report/manifest.json` is its own manifest with `"mode": "reconcile"` and `files` keys relative to `report/`, which must include `reconciliation.json`. Any other layout is refused (`reconciliation_layout_unknown`). The `snapshot` object in `reconciliation.json` must match the snapshot being loaded: `t_start`, `status`, `contract_sha256` and `contract_version` must equal the extract manifest's `t_start`, `status`, `contract.sha256` and `contract.version`. Otherwise the load is refused (`reconciliation_snapshot_mismatch`). The reconciliation supplies the `absent_unexplained` counts. Without it, those counts are reported as `"unknown"`. A report inside the snapshot is not used.
   - `--resume` names an earlier, interrupted output directory (root-owned `0700`, holding only root-owned `0600` `run.json` and `progress.jsonl`). Its `run.json` must record the same snapshot manifest sha256 and target. It is only read: its progress is copied into the new output directory, which must still not exist.
   - `dev` accepts only a synthetic snapshot, which means manifest `"mode": "selftest"`. `beta` refuses one. The real snapshot is loaded only into `crm-beta`.
   - The output directory must not exist. Its parent must be a root-owned `0700` directory. `crm-load` creates the output directory as `0700` and its files as `0600`.
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
- **Mode.** The manifest `mode` is `extract` or `selftest`. A snapshot is synthetic **if and only if** `mode` is `selftest`.
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
8. **Event** becomes a Meeting.
9. **EmailMessage**, with its EmailMessageRelation rows, becomes an archived Email.
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
  - Copied: names, salutation, title, email, and the Mailing address.
  - Phones go to `phoneNumberData`: `Phone` is `Office`, and is primary when present; `MobilePhone` is `Mobile`.
  - Also set: account and owner.
- **Opportunity.**
  - The stage follows D1, with `sfStageName` kept.
  - `legacyStale` (D2) is set when the stage is Enquiry or Quoted and the close date is before the manifest `t_start`.
  - `lossReason` and `lossReasonLegacyMissing` follow D3.
  - `amount` is set, with `amountCurrency: GBP` whenever there is an amount.
  - Also set: close date, description, `serviceType`, `enquiryCategory` and `businessType`.
  - `sfLeadSource` is kept raw. `introducedBy` and `channel` are filled only from the D7 table.
  - The D8 name parts come from `name_patterns.json`.
  - `postcode` and `keyInformation` stay empty, because those fields aren't in the contract.
- **Contact roles.** EspoCRM validates the role against `Contact.opportunityRole.options`, which hold the Salesforce picklist. A null role is linked with `""`. A value outside the options is linked with `""` and gets the exception `role_unmapped`.
- **Task.**
  - Status: Open becomes `Not Started` and Completed becomes `Completed`.
  - Priority: Normal and High map to themselves.
  - The parent is resolved from `WhatId` by key prefix, falling back to `AccountId`.
- **Call.** Status is `Held`. Direction is `Outbound`, unless `CallType` is Inbound.
- **Meeting.**
  - `meetingType` comes from `Type`. A null `Type` becomes `Unspecified (legacy)` (D10).
  - Status is `Held` if `EndDateTime` is before the manifest `t_start`, otherwise `Planned`.
  - Attendees are **the owner only**, because EventRelation isn't in the contract.
- **Email** (from an EmailMessage). The email is created as follows:
  - status is `Archived`;
  - set from the message: `from`, `to` and `cc` (`;`-separated), the subject, and `bodyPlain` and `body` from **TextBody only**, with `isHtml` false;
  - `dateSent`, and `messageId` from `MessageIdentifier`;
  - the thread and activity keys;
  - the parent comes from `RelatedToId`, otherwise from the parent of the linked Task;
  - users come from the User relations.

  **No Bcc and no attachments.**

  EmailMessageRelation rows hidden through a soft-deleted EmailMessage or Contact (contract v4 `visibleVia`) are **skipped** and counted as `parent_soft_deleted`.
- **Note.** Not imported (D6). Notes are counted as `out_of_scope`.
- **Not created.** Records soft-deleted in Salesforce are never created and are counted as `soft_deleted`. `absent_unexplained` counts come from the reconciliation. If such a record already exists in EspoCRM, it is flagged, not deleted.

### Owner resolution

- `OwnerId` resolves through the index of provisioned users (`GET User?select=id,sfId`).
- If the owner is a queue or group (`00G…`), or doesn't resolve (including non-human users), `assignedUser` stays **empty**, `sfOwnerId` is kept, and the exception `owner_queue_or_group` or `owner_unresolved` is recorded.
- Ownership is never guessed.

## `load-report.json` (counts only)

| Key | Content |
|---|---|
| `objects.<Object>.source_rows` / `source_current` | Rows in the snapshot, and how many are not soft-deleted. |
| `objects.<Object>.targets.<Entity>` | `created`, `updated`, `unchanged`, `failed`. |
| `objects.Account.second_pass` | Counts for the parent pass. |
| `objects.<Object>.skipped` | `soft_deleted`, `absent_unexplained` (`"unknown"` without `--reconciliation`), `out_of_scope` (Note), `represented_by_email_message` (Task), `parent_soft_deleted` (EmailMessageRelation), `user_not_human` (User). |
| `objects.<Object>.exceptions` | Exception counts by reason. |
| `existingNotCurrentInSnapshot` | Per entity: EspoCRM records flagged, never deleted. |
| `exceptions` | `total` and `byReason`. |
| `relationships` | `account_parents`, `contact_accounts`, `enquiry_contacts` and `activity_parents`, each `{snapshot, espocrm}`. They must be equal. |
| `requests` | `writes` and `reads`. |
| `deletes` | Always 0. |
| `snapshotStatus`, `acceptedDrift`, `synthetic`, `snapshotManifestSha` (sha256 of `manifest.json`), `reconciliation` (a reconciliation run was used), `mappingVersion`, `contractVersion`, `tool` | Run metadata. |

It holds no names, values or free text.

## `exceptions.jsonl` (root `0600`)

There is one line per `{object, sfId, reason}`. It holds ids and codes only.

| Reason | Meaning |
|---|---|
| `owner_queue_or_group` | The owner is a queue or group. `assignedUser` is empty and `sfOwnerId` is kept. |
| `owner_unresolved` | The owner is not a provisioned user: inactive and not provisioned, non-human, or missing. |
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
| `exists_soft_deleted_in_sf` | An EspoCRM record exists for an sfId that is soft-deleted in Salesforce. It is flagged, not deleted. |
| `exists_not_in_snapshot` | An EspoCRM record exists for an sfId that isn't in the snapshot. It is flagged, not deleted. |
| `duplicate_conflict` | 409 `DuplicateConflict` from EspoCRM. This isn't expected, because every POST skips the name check. |
| `write_rejected` | Any other 4xx on a write. |
| `write_failed` | 5xx after the bounded retries (5, with exponential backoff). The **likely cause on create** is a unique-index violation on `sfId`: EspoCRM's unique index also counts soft-deleted rows, so a soft-deleted EspoCRM record holding that key makes the create fail with HTTP 500. Find it in the database and decide by hand. The importer never deletes and never loops. |
| `user_not_exportable` | (`crm-load users`) The user has no valid user name or last name. |

## Re-runs, retries and resume

- **Re-run.** Running again on the same snapshot, with a new output directory, makes zero writes and reports every record as `unchanged`. A changed snapshot updates only the attributes that differ. Link-multiples are merged, never reduced.
- **Retries.** HTTP 429 and 5xx are retried up to 5 times, with exponential backoff. 4xx is not retried.
- **Interrupted run.** Every write is appended to `progress.jsonl` in the output directory (phase, sfId and action only). A run can be resumed in either of two ways:
  - run `load.sh` again with a **new** output directory. The index finds everything already written, so nothing is repeated. The counts show those records as `unchanged`;
  - or run `load.sh --resume <earlier output dir> <target> <snapshot> <new output dir>`. The earlier directory's `run.json` must hold the same snapshot manifest sha256 and target. Its progress log is copied into the new output and credits completed writes, so the report equals that of an uninterrupted run. `--resume` refuses a directory that already has a report, or holds anything besides `run.json` and `progress.jsonl`.
- **Network.** The only network use is plain HTTP to `http://127.0.0.1:<port>/api/v1/`. Any other host is refused, and redirects are never followed.
