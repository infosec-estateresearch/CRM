# Identity integrity (CRM-IDINT-001)

ERm can be the authoritative source of FirmID and ContactID for Estate Research's applications only if no identity relationship or identifier can be changed, removed or lost without authorisation and a durable audit record, by anyone, including administrators and service accounts. This page describes what the build does, how each route is covered, how to prove it, and what has **not** been verified yet.

This page is written for the build. It is not the identity register or the restore reconciliation (CRM-OPS-001) and it does not replace `docs/IDENTITY.md` or `docs/LOGGING.md`, which the records change adds separately.

## 1. Terms

- **FirmID** is `Account.id`; **ContactID** is `Contact.id`. `sfId` is a legacy cross-reference only.
- **Identity relationships:** a firm's parent firm (`parentFirm`), a contact's primary firm (`primaryFirm`), a contact's other firm links (`contactFirmLink`), an enquiry's firm (`enquiryFirm`) and a successor link (`successor`). A status change is audited as `status`.
- **Account kinds:** an administrator, every human role (`ER Staff`, `ER Intake`, `ER Manager`) and the import service account (`ER Import`).

## 2. What the release enforces

| Rule | Mechanism (all under `custom/Espo/Custom/`) |
|---|---|
| Audit or fail (3.1) | `Classes/Identity/IdentityAuditor.php` writes one `IdentityAudit` record and reads it back. On any failure it throws `Forbidden` and the change is refused. Updates and links are audited **before** the change; a create is audited right after the record gets its identifier and is **undone** (`deleteFromDb`, and the contact's firm link rows are deleted) if the audit cannot be stored. A new contact's firm links (`accountsIds`) are each audited from the saved record, not from core's relate hooks; a link already audited by a relate hook is not recorded twice. |
| Audit protection (3.2) | `Hooks/IdentityAudit/ProtectIdentityAudit.php`: a record is created only with a save option that only server code sets, and is never edited or deleted. Administrators bypass role ACL, not hooks. The roles give every role read access and nobody create, edit or delete. |
| Primary firm (3.3) | `IdentityGuard`: the primary firm must be among the linked firms in the same save, and unlinking the primary firm (from either side) is refused. Setting another linked firm as primary, or clearing the primary firm, in the same change is allowed. Existing exceptions are not repaired: `scripts/identity_report.py` lists them. |
| No loss (3.4) | `Hooks/{Account,Contact}/IdentityBeforeRemove.php` refuse every delete and mass delete; `Controllers/{Account,Contact}.php` refuse merge before it starts. `ER Manager`'s contact delete level is now `no`. |
| Retire and supersede (3.5) | `Account` and `Contact` have `identityStatus` (`active`, `retired`, `superseded`), `successor` and `predecessors`. Any role that may edit the record may change them (option (a)); `IdentityGuard` refuses a self, cyclic, wrong-kind or missing successor, and links to `successor` or `predecessors` (use the record edit). A mistaken or test record is retired or superseded, never deleted. |
| Settings (3.6) | `config/release-settings.json`, applied and read back by `scripts/deploy_release.sh` (step 6b, `apply_release_settings`). |
| Identifiers only from ERm (3.7) | `IdentityGuard` refuses a new record that carries an identifier and any save made by the CSV import; the scopes of firms, contacts and enquiries are `importable: false` and no human role holds the Import scope. |
| Clean refusal (3.8) | `IdentityGuard::checkLengths` refuses a string longer than its field's `maxLength` with a validation error before anything is stored. |

Nothing has an administrator, service-account or option bypass. The hooks do not read the user type; a unit test fails if `isAdmin`, `isApi`, `er-import`, or a skip-hooks option appears in them.

### Why audit before for updates, and after for creates

A new record has no identifier until it is stored, so its audit record can only be written afterwards; the create is then undone if the audit fails. For an update, the audit is written first, so that no change can succeed without its record. The cost is that an update may leave an audit record for a change that a later layer then rejected. Over-recording is accepted; under-recording is not. **Residual risk:** if the save then fails (a validation or database error after the audit was written), an audit record remains for a change that did not happen. Readers of the audit must treat a record as "attempted or made"; the record's actor and time still say who tried what.

## 3. The route matrix

`tests/acceptance/identity_matrix.py` defines every cell: 5 relationships × 16 routes × 5 account kinds. `tests/unit/test_identity.py` fails if a cell is missing; `tests/acceptance/test_identity.py` drives every cell against a live stack and requires either **refused with nothing changed** or **performed with its audit record** (and the stricter expectation the matrix names).

| Route | How it is covered |
|---|---|
| Record create, record edit, mass update | `BeforeSave` / `AfterSave` hooks on Account, Contact and Opportunity |
| Link and unlink from either side, panel selection | `BeforeRelate` / `BeforeUnrelate` hooks (both sides) |
| Bulk linking | `BeforeMassRelate` hooks refuse it for identity links |
| Delete, mass delete | `BeforeRemove` hooks |
| Merge | `postActionMerge` of the Account and Contact controllers |
| CSV import | `importable: false`, the Import scope, and the `import` save option refused in `BeforeSave` |
| Creation with a supplied identifier | `BeforeSave` |
| Retire and supersede | record edit, validated in `BeforeSave` and audited |
| Scheduled cleanup job | the settings of 3.6 and the refusal to delete anything |

## 4. Retention settings

`config/release-settings.json` lists four EspoCRM settings: `cleanupDeletedRecords` false, `cleanupAuditLog` false, `cleanupActionHistoryPeriod` `6 months` and `cleanupAuthLogPeriod` `13 months`. `scripts/release_settings.py` validates the file (it may add settings but never relax these), and `deploy_release.sh` sets each with `bin/command config:set` (with its type), checks the key is defined in the image's defaults, and reads it back from `data/config.php`. Any difference fails the deploy.

The setting names are the best available and **have not been checked against the EspoCRM 10.0.12 image**. If one is wrong the deploy fails loudly at the "is not a known EspoCRM setting" check, rather than passing silently; correct the name in `config/release-settings.json`.

## 5. The primary-firm report

```
export CRM_BASE_URL=...  CRM_ADMIN_USERNAME=...  CRM_ADMIN_PASSWORD=...
python3 scripts/identity_report.py
```

It sends only GET requests (the transport refuses anything else) and prints `{"count": N, "contactIds": [...]}`. It repairs nothing and invents no primary firm.

## 6. Running the proof

The build sandbox has no EspoCRM, Docker or browser, so the following are the operator stage's job and have **not** been run by the build:

1. `php -l` and the unit suite with PHP present: `python3 -m unittest discover -s tests/unit` (the PHP tests execute the identity PHP against stand-ins, with mutations).
2. Deploy with the real release scripts, then the live suite: see the header of `tests/acceptance/test_identity.py` for the environment (it needs operator commands to make audit storage unwritable, to age data and run the cleanup job, and to count rows). The existing suites `test_acceptance.py` and `test_access.py` no longer delete firms; they retire them.
3. A real-browser check of the firm, contact and enquiry screens for each human role.

## 7. Not verified, and known limits

- **Undone create.** The undo removes the record (`deleteFromDb`) and, for a contact, its rows in the firm link table (`AccountContact`) with a delete query that fires no hooks. If either removal itself fails, the refusal still stops the request, but that record or those link rows may remain, and audit records already written for the create remain (over-recording). Other link tables are not touched.
- **EspoCRM was not run.** Hook interfaces `BeforeRelate`, `BeforeUnrelate` and `BeforeMassRelate`, the `import` save option, the identifier-on-create check and the controller override of `postActionMerge` rest on the EspoCRM sources as understood, not on the 10.0.12 image. The new hook methods declare a tolerant tail (`mixed ...$rest`) so a different parameter list does not break loading, but a different **name or behaviour** would. The operator proof is what settles them.
- If EspoCRM assigns an identifier to a new record before the `BeforeSave` hooks run, the supplied-identifier check would refuse every create; the live suite's plain-create cells would show it at once.
- A contact's status and successor are on the API and the firm's detail layout, not on a custom Contact layout (the core Contact layouts are not overridden, see [ACCESS.md](ACCESS.md)).
- Audit records are written before an update; a rejected update can leave a record (see section 2).
- Host-level and database-level tampering remains possible (3.2): someone with database access can change or delete an audit record and any identifier. The independent identity register and restore reconciliation (CRM-OPS-001) are the answer to that, not this work order.
- WIP is on hold: the "Open WIP / Revenue" item and handler are unchanged.
