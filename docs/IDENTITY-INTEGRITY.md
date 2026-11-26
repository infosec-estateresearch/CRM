# Identity integrity (CRM-IDINT-001R)

ERm can be the authoritative source of FirmID and ContactID for Estate Research's applications only if no identity relationship or identifier can be changed, removed or lost without authorisation and a durable audit record, by anyone, including administrators and service accounts. This page describes what the build does, how each route is covered, how to prove it, and what has **not** been verified yet.

CRM-IDINT-001R corrects CRM-IDINT-001. That candidate did not start: its hooks implemented platform interfaces that do not exist, and the platform calls no before-relation hook at all. Every control below uses only extension points the pinned EspoCRM really calls, each cited from its sources (section 8).

This page is written for the build. It is not the identity register or the restore reconciliation (CRM-OPS-001) and it does not replace `docs/IDENTITY.md` or `docs/LOGGING.md`, which the records change adds separately.

## 1. Terms

- **FirmID** is `Account.id`; **ContactID** is `Contact.id`. `sfId` is a legacy cross-reference only.
- **Identity relationships:** a firm's parent firm (`parentFirm`), a contact's primary firm (`primaryFirm`), a contact's other firm links (`contactFirmLink`), an enquiry's firm (`enquiryFirm`) and a successor link (`successor`). A status change is audited as `status`.
- **Account kinds:** an administrator, every human role (`ER Staff`, `ER Intake`, `ER Manager`) and the import service account (`ER Import`).

## 2. What the release enforces

| Rule | Mechanism (all under `custom/Espo/Custom/`) |
|---|---|
| Audit or fail (3.1) | `Classes/Identity/IdentityAuditor.php` writes one `IdentityAudit` record and reads it back. On any failure it throws `Forbidden` and the change is refused. **A save** (edit, mass update, retire, supersede) is audited in the before-save hook, before it is written. **A relation change** (link, unlink, a link-multiple save) has already happened when the platform calls the after-relation hook, so that hook audits it and, if the audit cannot be stored, **puts the change back** (a query on the junction row or the foreign key; no hook runs again) and refuses. **A create** is audited in the after-save hook and is **undone** (its row, and for a contact its firm link rows) if the audit cannot be stored. |
| Audit protection (3.2) | `Hooks/IdentityAudit/ProtectIdentityAudit.php`: a record is created only with a save option that only server code sets, and is never edited or deleted. `recordDefs/IdentityAudit.json` also disables mass delete and mass update. Administrators bypass role ACL, not hooks. Every role reads the audit and nobody creates, edits or deletes it. |
| Primary firm (3.3) | `IdentityGuard`: the primary firm must be among the linked firms in the same save; unlinking the primary firm from either side is refused by the record unlink hook (a clean refusal before anything changes) and, for code that unrelates through the ORM directly, by the after-unrelate hook (which puts the link back). Setting another linked firm as primary, or clearing the primary firm, in the same change is allowed. Existing exceptions are not repaired: `scripts/identity_report.py` lists them. |
| No loss (3.4) | Delete: `recordDefs/{Account,Contact}.json` `beforeDeleteHookClassNameList` (the record delete hook) and `Hooks/{Account,Contact}/IdentityBeforeRemove.php` (the ORM remove, so mass delete and any code that removes a record are covered). Mass delete: `massActions.delete.disabled`. **Merge: `actions.merge.disabled`**, which the platform's merge route (`POST /api/v1/Action`) honours. `ER Manager`'s contact delete level is `no`. Cleanup never removes them: see the settings row. |
| Retire and supersede (3.5) | `Account` and `Contact` have `identityStatus` (`active`, `retired`, `superseded`), `successor` and `predecessors`. Any role that may edit the record may change them (option (a)); `IdentityGuard` refuses a self, cyclic, wrong-kind or missing successor. Setting a successor by linking is refused (record link and unlink hooks, then the after hooks). The `branchesIds` and `predecessorsIds` of a record save are refused (record create and update hooks): they change through the link routes, which audit the identifier they replace. A mistaken or test record is retired or superseded, never deleted. |
| Settings (3.6) | `config/release-settings.json`: `cleanupDeletedRecords` false, `cleanupAudit` false, `cleanupActionHistoryPeriod` `6 months`, `cleanupAuthLogPeriod` `13 months`; applied and read back by `scripts/deploy_release.sh` (step 6b). The scopes `Account`, `Contact`, `Opportunity` and `IdentityAudit` also carry `preserveAuditLog`. |
| Identifiers only from ERm (3.7) | The platform assigns a new record's identifier **before** the before-save hooks run, and its API discards a client-supplied one (`Core/Record/Service.php`); a request that supplies one is therefore performed with ERm's own identifier (and audited), never with the supplied one. CSV import is refused: `Tools/Import/Import.php` saves each row with the `import` option and hooks active, and `IdentityBeforeSave` refuses it. (`importable: false` in the scopes only hides the client menu; the server never reads it.) No human role holds the Import scope. |
| Clean refusal (3.8) | `IdentityGuard::checkLengths` refuses a string longer than its field's `maxLength` with a validation error before anything is stored. |

Nothing has an administrator, service-account or option bypass. The hooks do not read the user type; a unit test fails if `isAdmin`, `isApi`, `er-import`, or a skip-hooks option appears in them.

### Hook order

`Core/HookManager` sorts hooks by their static `$order` (default 9). The save hooks run at 99, **after** the platform's own Contact hook (`Modules/Crm/Hooks/Contact/Accounts`), so a primary firm that hook assigns is the value audited. The relation hooks run at 1, **before** the platform's own relation hooks, so a refused unlink is put back before the platform's Account hook clears the contact's primary firm. Unit tests fail if either order is changed.

### A repeated relation change

The platform can report one change twice (when a contact's primary firm is cleared it unrelates a firm the link-multiple save has just unrelated). `IdentityGuard` keeps, for the request, the last audited state of each link and does not audit an identical second change. A refused change clears that entry.

## 3. The route matrix

`tests/acceptance/identity_matrix.py` defines every cell: 5 relationships × 16 routes × 5 account kinds. `tests/unit/test_identity.py` fails if a cell is missing; `tests/acceptance/test_identity.py` drives every cell against a live stack and requires either **refused with nothing changed** or **performed with its audit record**. A refused cell must also show that a control refused it on a route that exists (A18): every call answers 400 or 403, never 404, 405 or a server error; an import answers 200 with an error count and nothing created.

| Route | How it is covered |
|---|---|
| Record create, record edit, mass update | `BeforeSave` / `AfterSave` hooks on Account, Contact and Opportunity |
| Link and unlink from either side, panel selection | record link and unlink hooks (refusals), then `AfterRelate` / `AfterUnrelate` hooks (audit, put back) |
| Link-multiple saved with a record (a contact's firms) | `AfterRelate` / `AfterUnrelate`, because the platform saves it by relating |
| Bulk linking | `relationships.<link>.massLink` is `false` for every identity link, so `Core/Record/Service::massLink` refuses it; `AfterMassRelate` hooks put back and refuse code that mass-relates through the ORM |
| Delete, mass delete | record delete hook, `massActions.delete.disabled`, `BeforeRemove` hooks |
| Merge | `actions.merge.disabled` on Account and Contact (the old merge controllers are gone) |
| CSV import | the `import` save option refused in `BeforeSave`; the Import scope |
| Creation with a supplied identifier | the platform discards it; the record gets its own identifier, audited |
| Retire and supersede | record edit, validated in `BeforeSave` and audited |
| Scheduled cleanup job | the settings of 3.6 and `preserveAuditLog` |

## 4. Retention settings

`config/release-settings.json` lists four EspoCRM settings. `scripts/release_settings.py` validates the file (it may add settings but never relax these), and `deploy_release.sh` sets each with `bin/command config:set` (with its type), checks the platform knows it, and reads it back from `data/config.php`. Any difference fails the deploy.

"Knows" means the name is in `application/Espo/Resources/defaults/config.php`, **or** the platform's cleanup code reads it with a default of its own: `cleanupAuthLogPeriod` is read in `Classes/Jobs/Cleanup.php` and is absent from the defaults. `cleanupAuditLog` (the name CRM-IDINT-001 used) is neither, so a release that names it fails. The audit-history switch is `cleanupAudit` (default on). `tests/unit/test_platform_reference.py` runs the real check against the pinned sources.

## 5. The primary-firm report

```
export CRM_BASE_URL=...  CRM_ADMIN_USERNAME=...  CRM_ADMIN_PASSWORD=...
python3 scripts/identity_report.py
```

It sends only GET requests (the transport refuses anything else) and prints `{"count": N, "contactIds": [...]}`. It repairs nothing and invents no primary firm.

## 6. Running the proof

The build sandbox has no EspoCRM, Docker or browser. What runs here:

```
CRM_PLATFORM_REFERENCE=/path/to/espocrm python3 -m unittest discover -s tests/unit
```

`CRM_PLATFORM_REFERENCE` names the pinned EspoCRM sources (the directory that holds `application/` and `vendor/`; read-only, never copied into the repository, its digest is checked). With it set and php present the suite (a) loads every custom PHP class through the platform's own autoloader and fails on any missing class or interface or incompatible signature, (b) checks that every class named in custom metadata exists and implements the interface its list needs, (c) checks the test stand-ins declare only platform symbols with the platform's signatures, and (d) runs the identity PHP, in the order the platform runs it, with the platform's real hook interfaces. The tests are skipped only when the variable is unset; set to a wrong path they fail.

The operator stage runs the rest: deploy with the real release scripts, the live suite (see the header of `tests/acceptance/test_identity.py` for the environment; it needs operator commands to make audit storage unwritable, to age data and run the cleanup job, and to count rows, including audit-history entries), the 3.6 read-back, and a real-browser check of the firm, contact and enquiry screens for each human role.

## 7. Not verified, and known limits

- **EspoCRM was not run here.** The hook interfaces, record hook lists, metadata switches, routes and settings are verified against the reference sources, not against a running instance. The fake persistence layer reproduces the order in which the sources call the hooks; the operator proof settles the rest.
- **After-the-fact relation audits.** A relation change is audited after it happens and put back if the audit fails. The put-back is a query; if it too cannot run, the refusal is still raised but the change remains (host- or database-level failure; CRM-OPS-001's register is the answer). For a link whose key is on the record in hand (a `belongsTo` relate) the platform has already overwritten the previous value, so the audit records the previous key as empty; the platform's own use of that relate only sets a primary firm where there was none. A foreign key overwritten by a code path that relates by identifier alone is likewise recorded with an empty previous value; no application route does this (branches and predecessors cannot be set in a record save, section 2).
- **Undone create.** The undo removes the record and, for a contact, its rows in the firm link table (`AccountContact`) with a delete query that fires no hooks. If either removal fails, the refusal still stops the request, but the record or those link rows may remain, and audit records already written for the create remain (over-recording).
- **Over-recording.** Audit records are written before an update is saved; a rejected update can leave a record for a change that did not happen. Readers must treat a record as "attempted or made".
- **Mass delete answers 403** because it is disabled; code that mass-removes through the ORM is refused record by record by `BeforeRemove` (the platform's mass delete catches each refusal and continues, which is why the switch is the refusal that answers).
- **Mass relate by code** (not reachable from any application route, since `massLink` is off) is put back for junction links; a foreign key it overwrote is set to empty, not restored.
- A contact's status and successor are on the API and the firm's detail layout, not on a custom Contact layout (the core Contact layouts are not overridden, see [ACCESS.md](ACCESS.md)).
- Host-level and database-level tampering remains possible (3.2): someone with database access can change or delete an audit record and any identifier. The independent identity register and restore reconciliation (CRM-OPS-001) are the answer to that, not this work order.
- WIP is on hold: the "Open WIP / Revenue" item and handler are unchanged.

## 8. Platform facts relied on (rule 3C.1)

Paths are under `application/Espo/` of the pinned reference; `tests/unit/test_platform_reference.py` asserts each of them.

| Fact | File |
|---|---|
| Before hooks for custom code: `BeforeSave`, `BeforeRemove`; after hooks: `AfterSave`, `AfterRelate`, `AfterUnrelate`, `AfterMassRelate`. There is no `BeforeRelate`, `BeforeUnrelate` or `BeforeMassRelate` | `Core/Hook/Hook/*.php` |
| The hook mediator overrides only `afterRelate`, `afterUnrelate`, `afterMassRelate` | `Core/ORM/Repository/HookMediator.php` |
| Hooks sort by static `$order` (default 9); every public method of a hook class is a hook type; a repeated short class name is skipped | `Core/HookManager.php` |
| The identifier of a new record is generated before the before-save hooks run | `Core/Repositories/Database.php` (`save`, `prepareSaveInternal`) |
| An API client's `id` is discarded on create; single link and unlink run the record link and unlink hooks, then relate; mass link needs `recordDefs.<Entity>.relationships.<link>.massLink`; a `belongsTo` link has no link route | `Core/Record/Service.php` |
| Record hook interfaces `LinkHook`, `UnlinkHook`, `DeleteHook`, `CreateHook`, `UpdateHook` and their `recordDefs` lists | `Core/Record/Hook/*.php`, `Core/Utils/Metadata/Builder.php` |
| `recordDefs.<Entity>.actions.<action>.disabled` disables an action (merge); `POST /Action` | `Core/Action/ActionFactory.php`, `Core/Action/Service.php`, `Core/Action/Api/PostProcess.php`, `Resources/routes.json` |
| `recordDefs.<Entity>.massActions.<action>.disabled` disables a mass action; mass delete swallows a per-record refusal | `Core/MassAction/MassActionFactory.php`, `Core/MassAction/Actions/MassDelete.php` |
| The mapper changes the relation first, then the after hook runs | `ORM/Repository/RDBRelation.php` |
| Link-multiple values are saved by relating, with hooks | `Core/FieldProcessing/Relation/LinkMultipleSaver.php` |
| The platform's own Contact and Account hooks change the primary firm and the links | `Modules/Crm/Hooks/Contact/Accounts.php`, `Modules/Crm/Hooks/Account/Contacts.php` |
| CSV import saves each row with the `import` option, hooks active; `importable` is not read by the server | `Tools/Import/Import.php`, `Core/ORM/Repository/Option/SaveOption.php`, `Resources/routes.json` |
| `cleanupDeletedRecords`, `cleanupAudit` (default on), `cleanupActionHistoryPeriod`, `cleanupAuthLogPeriod` (read, not in the defaults); `preserveAuditLog` | `Classes/Jobs/Cleanup.php`, `Classes/Cleanup/Audit.php`, `Resources/defaults/config.php` |
| `bin/command config:set` with `--type=bool` and `--type=string` | `Resources/metadata/app/consoleCommands.json`, `Classes/ConsoleCommands/SetConfigParam.php` |
| A hook receives `Espo\Entities\User` and `Espo\ORM\EntityManager` by type | `Binding.php` |
| The contact and firm junction entity is `AccountContact` | `Modules/Crm/Hooks/Contact/Accounts.php` |
