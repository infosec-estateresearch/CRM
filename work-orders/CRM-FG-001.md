WO: CRM-FG-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main — CONDITIONAL: the `main` commit that delivers an accepted CRM-CLIENT-001 (does not exist yet; no SHA is asserted)

> **Header note (v1.2).** There is no `BROWSER: yes` line. This WO changes what a user sees, so under the installed ForgeV2 `deliver` skill (§3, *Browser gate*) the sandboxed Tester would have to drive a browser itself. It cannot, so the PL would return ESCALATED.
>
> Real-browser assurance is therefore given by the CRM-CLIENT-001 operator runner and a companion **CRM-FG-001-BA** WO, on the CL-D7 pattern (FG-D5). This holds once CGPT accepts CL-D7 for CRM-CLIENT-001.

# CRM-FG-001: FirmGroup entity and Account Group Members tab

- **Version:** v1.3 **CONDITIONAL DRAFT**, 2026-11-16. **It is not approval-ready.** That requires a later version that pins the base commit (gate G0, §10). This version is identified by the commit that adds it.
- **History:**
  - v1.0 is commit `6c78099d0cdea5b8cb306cae863bd7eeaab38841`.
  - v1.1 records CGPT decisions FG-D1, FG-D2 and FG-D3 (2026-11-16, Phase D). It replaces the unverified P4 risk with route facts verified against the 10.0.12 source (§2), and fixes the membership design to a single guarded Account-side operation (§3).
  - v1.1 is commit `0f9372447fcad03f24d841dc0cb55347008ceb9b`.
  - v1.2 answers *CRM Architect Review and Continuation Mission* (CGPT, 2026-11-16), Phase C:
    - P4b and P6 are resolved from source;
    - P9–P14 are added, including a **newly found membership bypass** through FirmGroup `accountsIds` (P9), which is now closed;
    - §3 point 4, AC4, AC6, §8, §10 and §11 are updated;
    - FG-D5 (browser assurance pattern) is proposed.
  - v1.2 is commit `ced9670209a6a338eff2b48c699c314114774418`.
  - **v1.3** answers *CRM/WIP Delivery Mission* (CGPT, 2026-11-16), Phase 2. *Do not substitute a detective-only control for a required preventive control*:
    - the Formula, merge and `accountsIds` paths are now closed **preventively** by an ORM relation guard (P15, §3 point 4);
    - the dependency is updated to CRM-CLIENT-001 v1.3;
    - FG-D5 follows the accepted CL-D7.
  - G0 is unchanged.
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/61
- **Prepared by:** Rogue (Orchestrator). Preparation only: **no implementation, no dispatch.**
- **Approval:** none. Dispatch needs a CGPT approval comment on Issue #61 that names this path and the immutable commit of an approval-ready version.

## 1. Authority and governing records

| Item | Value |
|---|---|
| Governing FOUNDRY | provenance `5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0` (v1.0–v1.1); adopted main `84fedf0a74017237aa1bd650d8560350c91c7f0e` for the v1.2 decisions. The WO contract is byte-identical at both: `standards/work-order-contract.md` sha256 `cbb6eb3ae62bf7877ae470abf2297a5af5ffb23ca617581a9a85077dd9a8ebcc` |
| Product authority | Matt's PO approval at `dc6fb4ced68d9139c2332af973084239492104b3` (Issue #54, 2026-11-13T12:04:29Z): the Vision and the Backlog, including **CRM-PBI-018**, and CRM-D020..D032 (D023: FirmGroup; D031: parent and branch kept) |
| Architect decisions | **FG-D1, FG-D2 and FG-D3**: CGPT directive of 2026-11-16, within the approved FirmGroup direction (§11) |
| Requirements | `docs/requirements/crm-modules-requirements.md` **FG-01..FG-10** (FG-11 is out of scope); `docs/requirements/firmgroup-ux-contract.md`, journeys 1–6; `docs/architecture/crm-wip-module-boundary.md`; `docs/delivery/crm-module-sequencing.md` Gate C |
| Dependency | **CRM-CLIENT-001**: Issue #59, PR #60, **v1.3 at `323b7a8c90af22a3b0fda7536604201140d01218`** (pending approval). CL-D7 accepted and CL-D8 accepted conditionally (CGPT, 2026-11-16). This WO needs its client delivery, cache-bust, browser runner and evidence route |
| Main at drafting | `6e1766980e24d781d498727d4fe5db43cdeadbb7`. For information only; it is **not** the engineering base |
| Technical preflight | §2 is the PL's durable, read-only source preflight. CGPT has ruled that no separate HELM report is required. Unverified claims are labelled **UNVERIFIED** |

## 2. PL technical preflight

Sources: `main` @ `6e176698` and EspoCRM 10.0.12 inside the pinned image, read via `docker export`; no container was started. Hashes are of the upstream files in the image.

| # | Fact | Source | Consequence |
|---|---|---|---|
| P1 | `Account` custom fields are name, type, industry, assignedUser, practiceManagementSystem, learningPlatformAccess, parent, branches, sfId, sfOwnerId and sfCreatedAt; the links are `parent` and `branches`. There is no group concept. | `custom/Espo/Custom/Resources/metadata/entityDefs/Account.json` | Add `firmGroup` (belongsTo) only. `parent`, `branches` and every `sf*` field are untouched. |
| P2 | ER Staff, ER Intake and ER Import have **edit all** on Account. | `config/access/roles.json` | Membership cannot rely on scope ACL alone (§3). |
| P3 | Every scope must be explicit in every role. | `tests/unit/access_policy.py` | `FirmGroup` is added to the policy constants and the expected data. |
| P4a | Record-level (API) hooks `beforeLink` and `beforeUnlink` exist. `Record\Service` calls `processBeforeLink` after the ACL link checks and **before** `relate()`. They are configured through `recordDefs.<Entity>.beforeLinkHookClassNameList` and `beforeUnlinkHookClassNameList`. | `Core/Record/Hook/Type.php` `10bc4b79f9057e9fd2786cf068f1489413a460af46aa1504836bb507cdda74f0`; `Core/Record/Hook/Provider.php` `febbc0e49b5a21d65ceafe646baa3016e17926c154516da9a2b294639503cc31`; `Core/Record/Service.php` `d298edb4648a69c6ac500cecb106984e7dc9e4e1a532e3557abb37813e1f20c3` | The group-side link and unlink can be refused before any write, including for admin. |
| P4b | **There is no ORM-level before-relate hook.** The available hook types are BeforeSave, AfterSave, LateAfterSave, BeforeRemove, AfterRemove, LateAfterRemove, AfterRelate, AfterUnrelate and AfterMassRelate. `HookMediator` implements no `beforeRelate`. **Resolved (v1.2): a hasMany relate is a direct `UPDATE account SET firm_group_id`** (`BaseMapper::addRelation` HAS_MANY; `removeRelation` sets null). The Account entity is never loaded or saved, so **Account `beforeSave` does not fire**. | `ORM/Mapper/BaseMapper.php` `3ed78470…a28` lines 963–1005 and 1195–1236; `Core/ORM/Repository/HookMediator.php` `c20cda38…11c1`; `ORM/Repository/EmptyHookMediator.php` `e104b610…e78e` | Every route that reaches `relate()`/`relateById()` must be refused **before** it runs (P4a, P9, P10, P11). The membership service never uses relate. |
| P4c | `massLink` is allowed only when `recordDefs.<E>.relationships.<link>.massLink` is set, and **it does not run the `beforeLink` record hooks**. | `Record/Service.php` line 1210 and following | `massLink` must stay **unset** for both sides. AC4 proves a 403. |
| P4d | `LinkCheck::processLink` requires `edit` on the parent record. Field-level forbidden links are enforced through `getScopeForbiddenLinkList`. | `Core/Record/Access/LinkCheck.php` `439fc8e88b839be98bfbbd5c0c5c630f567949ba79c01bd57434f51d2549bb5c` | This is defence in depth only, because admin bypasses ACL. |
| P5 | The stream writes "Update" audit notes for audited fields on **every ORM save that is not `SILENT`**. Audited links write relate and unrelate notes. | `Hooks/Common/Stream.php`; `Tools/Stream/HookProcessor.php` `7e3a69ac952cb1132c6a329aa922b7f869bd3b2d15966aba3bab43c84a593839` | With `firmGroup` audited and a non-silent save, the audit records who, when, the old value and the new value. The membership service never saves silently. |
| P6 | **Resolved (v1.2).**<br>• `Route::unify()` reads **`custom/Espo/Custom/Resources/routes.json` first**, then module routes, then core. A duplicate (route, method) loaded later is dropped.<br>• `actionClassName` is supported (`RouteProcessor` creates it through the injectable factory; core uses this pattern for `/MassAction`).<br>• Routes are cached under `data/cache/application`, so `clear-cache`/`rebuild` are needed (the CRM-CLIENT-001 deploy runs both).<br>• Transactions: `getTransactionManager()->run()` with savepoints for nesting, on the single cached PDO. `forUpdate()` renders `SELECT … FOR UPDATE`. beforeSave and afterSave, including the stream notes, run inside the same transaction. | `Core/Utils/Route.php` `ddc6ac80…6db0` lines 92–129, 154–172, 241–252; `Core/Api/RouteProcessor.php` `ac387994…0c0a` lines 142–162; `ORM/TransactionManager.php` `bf833d3c…d7cc`; `ORM/QueryComposer/BaseQueryComposer.php` `fb737826…6387` lines 1994–2001; `ORM/Repository/RDBRepository.php` `e2ec35d8…3124` lines 170–200 | The custom action, its route and its locked expected-old check are implementable. Locking: the Account row first, then a plain existence read of the target FirmGroup, always in that order. The **full** Account entity is loaded under the lock, because audited attributes must be fetched (P13). |
| P7 | `Hooks/Account/RestrictDeleteWithEnquiries.php` refuses deletion of an Account that has enquiries, even for admin. | `main` | It is **untouched** (FG-D3) and is regression-tested. |
| P8 | Client code loads as AMD from `client/custom/src` with `appTimestamp` cache-busting. | CRM-CLIENT-001 §2 F3 and F8 | The Group Members view is an AMD view delivered through CRM-CLIENT-001. |
| **P9** | **Bypass found (v1.2):**<br>• FirmGroup create or update with **`accountsIds`** (the hasMany stub attribute created by the HasMany field converter) is saved by `FieldProcessing/Relation/Saver` and `LinkMultipleSaver`, through `relateById`/`unrelateById`. That is a direct UPDATE (P4b), with **no Account beforeSave and no record link hooks**.<br>• Without an `accounts` linkMultiple field, an update clears and ignores the ids, but a **create accepts one id** (`LinkCheck` refuses only more than one). | `Core/Utils/Database/Orm/FieldConverters/HasMany` `aefc978c…f0cf` lines 67–79; `FieldProcessing/Relation/Saver.php` `32291e7c…8d18`; `LinkMultipleSaver.php` `06a8773c…cca9` lines 52–245; `LinkCheck.php` `439fc8e8…bb5c` lines 189–191 | **New guard:** an ORM `beforeSave` on FirmGroup (`Hooks/FirmGroup/GuardMembershipAttributes.php`) refuses any save where `accountsIds` or `accountsColumns` is set. FirmGroup has **no** `accounts` linkMultiple field. AC4(f). |
| **P10** | **Merge.**<br>• Account merge runs in a transaction. The target is saved through `service->update` (Account beforeSave fires). Sources are removed through `service->delete` (beforeRemove fires), and a refusal rolls back the whole merge. belongsTo links are **not** merged.<br>• **Merging FirmGroups** moves `accounts` through `relate()`, a direct UPDATE. | `Core/Action/Actions/Merge/Merger.php` `c0e11981…59fd5159` lines 75, 157, 168, 325–330 | Account merge is covered by the existing guards. **FirmGroup merge must be disabled** (AC4(g); technical gate FG-T2: the exact disabling mechanism is to be confirmed in source at engineering time, or FirmGroup `beforeRemove` refuses any source that had members at transaction start). |
| **P11** | **Other paths.**<br>• Account PUT/PATCH, create, Duplicate, massUpdate, Import (create and update) and Lead convert all go through `saveEntity`, so Account beforeSave fires. No API path can set `skipHooks`.<br>• The Account-side link `POST /Account/{id}/firmGroup` is refused by core for belongsTo (`processForbiddenLinkEditCheck`).<br>• `massLink` requires metadata and **skips** `processBeforeLink`.<br>• Formula `record\relate`/`unrelate` call `relateById`, a direct UPDATE. | `Record/Service.php` `d298edb4…20c3` lines 740–790, 1093–1322; `Tools/MassUpdate/Processor.php` `893c9576…a489f39` lines 213–226; `Tools/Import/Import.php` lines 574–579 | The guards hold for every API path. **v1.3:** the Admin Formula `record\relate` path is closed preventively by the P15 relation guard (AC4(i)); the v1.2 detective-only control is withdrawn. |
| **P12** | **Mass operations swallow per-record exceptions.** massUpdate and massDelete catch and log refusals, so a refused record is **skipped silently** and the request does not fail. | `MassUpdate/Processor.php`; `Core/MassAction/Actions/MassDelete.php` `70488ec1…6d6ade` lines 95–99 | AC4 and AC7 assert *unchanged rows and the returned count*, not an HTTP error, for mass routes. |
| **P13** | **Audit.**<br>• An audited link writes an `Update` note with `attributes.was`/`became` (`firmGroupId`, `firmGroupName`) in afterSave, inside the transaction, only for attributes that were *fetched*.<br>• `silent`, `noStream` (always set by Import) and `skipAudited` suppress the note.<br>• The note is written even when the stream is off. | `Tools/Stream/HookProcessor.php` `7e3a69ac…3839` lines 433–461 and 649–663; `Tools/Stream/Service.php` `ee280ab9…e0af` | The membership save is non-silent, from a fully fetched entity. Both `firmGroupId` and `firmGroupName` are set (FG-T3 verifies `became.firmGroupName`). Import cannot change membership (P11), so its `noStream` cannot hide a change. |
| **P14** | **Deletion.** API delete, massDelete, merge sources and import revert all reach `remove`, so beforeRemove fires. No live-row direct delete exists; purge jobs touch only rows that are already soft-deleted. | `Record/Service.php` lines 808–835; `MassDelete.php`; `Classes/Jobs/Cleanup.php` `f537e390…433a` line 357 | `RestrictDeleteWhileGrouped` and `RestrictDeleteWithMembers` cover every path. Mass delete skips refused rows silently (P12). |
| **P15 (v1.3)** | **A preventive ORM relation guard is possible.**<br>• Every `relate`, `unrelate`, `relateById`, `unrelateById` and `massRelate` on an `RDBRelation` first calls `$this->hookMediator->beforeRelate` / `beforeUnrelate` / `beforeMassRelate` (`ORM/Repository/RDBRelation.php` lines 494–535, 585–627, 692–727).<br>• That mediator is the owning repository's `protected HookMediator $hookMediator`, which `RDBRepository::getRelation()` passes to the relation (`RDBRepository.php` lines 68, 85, 254).<br>• Core's `HookMediator` extends `EmptyHookMediator` and leaves the `before*` relate methods empty.<br>• A repository class is resolved first from `entityDefs.<E>.repositoryClassName`, then by class finder (`Repositories/<E>`, where Custom has precedence), then by the entity template (`Core/ORM/ClassNameProvider.php` lines 125–160).<br>• The Formula `record\relate`/`unrelate` (`RelateType.php` lines 100–114), the FirmGroup merge (`Merger.php` lines 273–285) and `LinkMultipleSaver` (lines 230–257) all use `getRelation()`.<br>• `transactionalSave` (`entityDefs.<E>.transactionalSave`) wraps a save, including its relation savers, in a transaction (`RDBRepository.php` lines 154 and 262) | listed files in the pinned 10.0.12 image | **New preventive control (§3 point 4):** custom repositories `Repositories/FirmGroup.php` and `Repositories/Account.php` install a guarding mediator. It **refuses every** relate, unrelate or mass-relate on `FirmGroup.accounts` and `Account.firmGroup`, for every caller including admin and Formula, and delegates everything else to the core mediator. The membership service never uses relate, so no bypass option exists. This closes **P9 (`accountsIds`), P10 (FirmGroup merge) and P11 (admin Formula) preventively**. FG-T6: the Account repository must extend the class EspoCRM would otherwise resolve (the `Company` template repository if `scopes.Account.type` is `Company`, otherwise core `Database`) |

## 3. Intended outcome and membership design

1. **`FirmGroup` entity:**
   - `name` is required and not unique;
   - `description` is optional;
   - a CRM-native immutable ID; there is **no** `sfId`;
   - a hasMany link `accounts`;
   - the stream is enabled, with `name` and `description` audited.
2. **`Account.firmGroup`:** an optional, audited belongsTo. An Account has at most one group, and null means *Not part of a group*.
3. **One membership write route (FG-D2).** The custom action `POST /FirmGroupMembership` (an `actionClassName` route; P6) takes `{accountId, operation, toGroupId?, expectedCurrentGroupId?}` and runs one service. That service:
   - **Authorises.** The caller must be Admin or hold FirmGroup edit "yes" (ER Manager), and must be able to read the Account. Everyone else gets **403**, including ER Staff, ER Intake and ER Import.
   - **Validates the operation (FG-D1):**
     - **assign:** the current group must be null; `expectedCurrentGroupId` must be absent or null.
     - **unlink:** `expectedCurrentGroupId` must equal the current group.
     - **move:** an explicit `operation: "move"`; `expectedCurrentGroupId` must equal the current group; `toGroupId` must differ from it and must exist.
   - **Checks for staleness in the same transaction.** It reads the Account with `forUpdate()` inside a transaction and compares the stored value with the expected value. A mismatch returns **409** and changes nothing.
   - **Writes** with a non-silent save carrying the custom save option `crmFirmGroupMembership`, which produces the audited stream note (P5). The response carries the old and new IDs.
4. **Guards that close every other route (FG-D2):**
   - **ORM `beforeSave` on Account** (`Hooks/Account/GuardFirmGroupMembership.php`). Any create (including Duplicate) with a non-null `firmGroupId`, or any update that changes `firmGroupId`, without `crmFirmGroupMembership` is refused. This covers `PUT`/`PATCH /Account`, create, duplicate, mass update, import, Lead convert, the Account merge target, and admin (P11).
   - **ORM `beforeSave` on FirmGroup** (`Hooks/FirmGroup/GuardMembershipAttributes.php`, **new in v1.2**). It refuses any save carrying `accountsIds` or `accountsColumns` (P9). FirmGroup defines **no** `accounts` linkMultiple field.
   - **FirmGroup merge disabled** (P10, FG-T2).
   - **Preventive ORM relation guard (v1.3, P15):**
     - `custom/Espo/Custom/Repositories/FirmGroup.php` and `Repositories/Account.php` wrap the repository mediator;
     - `beforeRelate`, `beforeUnrelate` and `beforeMassRelate` throw `Forbidden` for the `accounts` relation (FirmGroup) and the `firmGroup` relation (Account), unconditionally;
     - FirmGroup has `transactionalSave: true`, so a refused relate during a FirmGroup save rolls back the whole save.

     This **replaces** the v1.2 detective-only control and covers Formula `record\relate`, FirmGroup merge, `accountsIds` and any future relate caller.
   - **Residual outside membership:** an Admin able to upload EspoCRM **extensions** can install arbitrary PHP, which can defeat any in-application control. That is platform administration, not a membership route. It is handled in release readiness by setting `adminUpgradeDisabled` for customer environments (Phase 6 plan), not in this WO.
   - **Record `beforeLink` and `beforeUnlink`** on `FirmGroup.accounts` and `Account.firmGroup` (P4a). Each always refuses, so the group-side relate and unrelate are **disabled** for every user, admin included.
   - **`massLink`** stays unset (P4c).
   - **Field ACL:** `Account.firmGroup` is read "yes" and edit "no" for every role. This is defence in depth; the action does not depend on it.
   - **Grouped Account delete or merge** (`Hooks/Account/RestrictDeleteWhileGrouped.php`, a **new** separate hook that leaves P7 untouched). Removing an Account that has a group, including merge sources, is refused until it has been unlinked through the action. Otherwise membership would disappear without an audited unlink. **This is PL design under FG-D2**, not product scope: no membership change without audit.
5. **FirmGroup scope.**

   | Role | create | read | edit | delete |
   |---|---|---|---|---|
   | ER Manager | yes | yes | yes | yes |
   | ER Staff, ER Intake | no | yes | no | no |
   | ER Import | no | no | no | no |

   Admin has everything. Delete of a populated group is refused (point 6).
6. **Populated groups cannot be deleted (FG-D3).** `Hooks/FirmGroup/RestrictDeleteWithMembers.php` is an ORM `beforeRemove` hook. It covers the UI, the API, mass delete and admin. Deleting an empty group is allowed for ER Manager and Admin only.
7. **Account detail Group Members tab** (AMD view, CRM-CLIENT-001):
   - it sits beside the existing areas;
   - its header links the group name to the FirmGroup record;
   - it lists the *other* members with name, address/postcode, tier/type and phone, each clickable;
   - it paginates, and shows every same-name peer;
   - the empty state is *Not part of a group*;
   - for Manager and Admin only, it offers assign, unlink and move, all through the action. A move needs an explicit confirmation dialog that names the old and the new group.
8. **FirmGroup detail:**
   - name, description and a read-only member list linking to each Account;
   - add, unlink and move are done from the Account side, through the action (FG-D2).
9. **No seeding.** No group is created from Salesforce trees, legacy WIP or names. Synthetic fixtures only.

## 4. In scope (allowlist — finalised in the approval-ready version against the pinned base)

| Path | Change |
|---|---|
| `custom/Espo/Custom/Resources/metadata/scopes/FirmGroup.json`, `entityDefs/FirmGroup.json`, `clientDefs/FirmGroup.json`, `recordDefs/FirmGroup.json` | new entity, with record link hooks |
| `custom/Espo/Custom/Resources/metadata/entityDefs/Account.json`, `clientDefs/Account.json`, `recordDefs/Account.json` | the `firmGroup` field and link (audited), the Group Members tab, and record link hooks only |
| `custom/Espo/Custom/Resources/routes.json` | the `POST /FirmGroupMembership` route only |
| `custom/Espo/Custom/Tools/FirmGroup/**` | the membership action and service |
| `custom/Espo/Custom/Classes/RecordHooks/FirmGroup/**` | `beforeLink` and `beforeUnlink` refusal |
| `custom/Espo/Custom/Hooks/Account/GuardFirmGroupMembership.php`, `Hooks/Account/RestrictDeleteWhileGrouped.php`, `Hooks/FirmGroup/RestrictDeleteWithMembers.php` | new ORM guards |
| `custom/Espo/Custom/Resources/layouts/FirmGroup/*.json`, `layouts/Account/detail.json` and/or `bottomPanelsDetail.json` | FirmGroup layouts; the Account change adds the tab only |
| `custom/Espo/Custom/Resources/i18n/en_US/FirmGroup.json`, `Account.json`, `Global.json` | labels |
| `client/custom/src/crm/views/account/group-members-panel.js`, plus a template and the move-confirmation view if needed | AMD views |
| `config/access/roles.json` | the FirmGroup scope for every role, and `Account.firmGroup` field data |
| `tests/unit/access_policy.py`, `test_access_policy.py`, `test_metadata.py`, new `tests/unit/test_firmgroup.py` | policy, metadata and static guard tests |
| `scripts/seed_synthetic.py` and its tests | synthetic fixtures only: two unrelated peers, one branch hierarchy, duplicate names, and one ungrouped firm |
| `tests/acceptance/test_firmgroup_api.py`, `tests/browser/` journeys | the route matrix and the browser journeys |
| `docs/ACCESS.md`, `docs/BUILD.md`, `docs/REQUIREMENTS-TRACEABILITY.md` | documentation |

## 5. Exclusions

- `Account.parent`, `branches` and every `sf*` field, together with their ACL.
- `Hooks/Account/RestrictDeleteWithEnquiries.php` (FG-D3).
- The CRM-002 extractor and loader, and Salesforce.
- The legacy WIP repository and its data, the WIP entities, and FG-11 seeding.
- Delivery scripts, `release.py`, `deploy/**`.
- The running beta, FOUNDRY, ForgeV2 and other host applications.

## 6. Acceptance criteria

| AC | Criterion (requirement) | Evidence |
|---|---|---|
| AC1 | FirmGroup has a required, non-unique name, an optional description and no sfId. Two groups may share a name. (FG-01) | metadata tests and an API test |
| AC2 | An Account has at most one group, and null is allowed. A FirmGroup has 0..n Accounts. (FG-02) | metadata and API |
| AC3 | The **parent graph fingerprint** (sha256 of the sorted (id, parentId) pairs over all synthetic Accounts) is identical before and after every journey and API test. (FG-03) | acceptance and browser evidence |
| AC4 | **Route matrix** (FG-05, FG-D2), for ER Staff, ER Intake, ER Import, ER Manager and Admin:<br>(a) the action's assign, unlink and move: only Manager and Admin succeed; everyone else gets 403;<br>(b) `PUT /Account` with `firmGroupId`, Account create with `firmGroupId`, mass update, import and merge: refused for **every** role, admin included;<br>(c) `POST` and `DELETE /FirmGroup/{id}/accounts`, and the Account-side `firmGroup` link: refused for every role, admin included;<br>(d) `massLink` on both sides: 403;<br>(e) FirmGroup create, rename and delete follow §3 point 5;<br>**(f) FirmGroup create and update carrying `accountsIds`/`accountsColumns` are refused for every role, admin included (P9);**<br>**(g) FirmGroup merge is refused (P10);**<br>**(h) Account Duplicate and Lead convert carrying a group are refused (P11);**<br>**(i) as Admin, the Formula sandbox run of `record\relate('FirmGroup', <g>, 'accounts', <a>)` and of `record\unrelate(...)`, and the same from the Account side, are refused with rows unchanged (P15; FG-T7 confirms the sandbox endpoint in 10.0.12).**<br>For mass routes the request may succeed with refused rows skipped (P12). Evidence is unchanged rows plus the returned count.<br>Every refusal leaves the Account and FirmGroup row fingerprints byte-identical. | `test_firmgroup_api.py` on synthetic crm-dev |
| AC5 | **Move semantics** (FG-D1):<br>• a move without `operation: "move"`, or with a stale or absent `expectedCurrentGroupId`, returns 409 or 400 and changes nothing;<br>• an assign while a group is already set returns 409;<br>• two concurrent moves from the same expected group: exactly one succeeds and the other returns 409. | API, including a concurrency test |
| AC6 | **Audit** (FG-04): each successful assign, unlink and move produces exactly one attributable record with user, time, old group ID and new group ID. Refused attempts produce none. The record carries `firmGroupId` and `firmGroupName` for both was and became (P13). | API (stream and audit-log query) and browser |
| AC7 | **Deletion** (FG-10, FG-D3):<br>• a populated group cannot be deleted by Manager or Admin through the UI, the API or mass delete;<br>• Manager and Admin can delete an empty group, and Staff, Intake and Import cannot;<br>• a grouped Account cannot be deleted or merged away;<br>• the enquiry protection holds, as a regression check. | API and browser |
| AC8 | The Group Members tab sits beside the existing areas. Stream, Account details, branches, contacts, enquiries and activities are unchanged (FG-06, journey 6). | before and after screenshots, plus DOM assertions in the trace |
| AC9 | **Tab content** (FG-06, FG-07):<br>• the group name link opens the group;<br>• only other members are listed, with all four attributes, and each one is clickable;<br>• the list paginates, and same-name peers are all shown;<br>• the empty state is *Not part of a group*;<br>• Staff and Intake have no edit actions;<br>• the Manager can assign, unlink and move, with the move confirmation dialog. | browser |
| AC10 | **Consistency:** after a refresh, a change shows identically on both member Accounts and on the FirmGroup detail (FG-08). | browser |
| AC11 | **No inference:** zero groups exist except those created by the journeys, and no code derives groups (FG-09). | static and API |
| AC12 | **Containment:** with the Group Members view forced to error, the Account page still renders the other panels and shows a bounded error in the tab. | browser fault injection |
| AC13 | **Regression:**<br>• the unit suite passes as non-root, with at least the starting count;<br>• `tests/load` passes;<br>• the beta-safe suite passes against synthetic dev;<br>• the CRM-TEST-001 mutations still kill;<br>• the access policy passes. | host procedure and Tester |
| AC14 | **Release:**<br>• the bundle verifies;<br>• an upgrade from the pre-FG release, followed by a rollback on crm-dev, keeps every Account and its `parent`;<br>• the rollback removes the FirmGroup UI and its routes;<br>• the leftover `firmgroup` table and `account.firm_group_id` column are documented (FG-D4). | host procedure |

## 7. Security controls

- Server-side authorisation, with a single write route (§3).
- Hidden buttons are never relied on.
- No privilege is granted through default scopes.
- Data is synthetic only, with `@example.test` users.
- No customer data, sfIds, addresses or credentials appear in Git, tests, screenshots, prompts or logs.
- gitleaks runs on the candidate and on the evidence.
- **DevSecOps reviews:**
  - the route matrix, including the `SILENT` and `skipHooks` save options used in import and merge paths;
  - that the custom save option cannot be set by a client: request data never maps to save options;
  - escaping in the client view: no `innerHTML` with record data.

## 8. Roles and independent criteria

| Role | PASS only if |
|---|---|
| Engineer | Only §4 changes (the final allowlist adds `Hooks/FirmGroup/GuardMembershipAttributes.php`, `Repositories/FirmGroup.php`, `Repositories/Account.php` and the guarding mediator class under `Classes/FirmGroup/`). FG-T1..T5 are verified first, or the Engineer stops. Every AC has a test or a journey. |
| Auditor | The allowlist is exact. FG-01..FG-10 and FG-D1..D3 are traced to ACs. `parent`, `branches`, `sf*` and the enquiry hook are untouched. The documentation is truthful. |
| Tester | All non-browser ACs are evidenced on the same unchanged candidate, including the full AC4 matrix and the AC5 concurrency test. The browser verdicts (AC8–AC10, AC12, journeys) are given by the Tester of **CRM-FG-001-BA** from operator evidence (FG-D5). |
| DevSecOps | No route bypass, no hook bypass, no XSS, no secret or customer data. |

- **Execution limit:** four executions per specialist, including the first. Exhaustion is FAIL and is escalated.
- **Engine records:** `…/records/3b6369e4f8e78d83/CRM-FG-001/`.
- **PL evidence:** `/home/forgev2-pl/crm-evidence/CRM-FG-001/`.

## 9. Real-browser journeys

Run on synthetic crm-dev, with the CRM-CLIENT-001 annex B runner and evidence route.

1. The Manager creates a group from two unrelated peer firms; neither firm's parent changes (AC3).
2. Open each Account, go to Group Members, navigate to the other Account and back (AC9).
3. Unlink one member. The empty state shows on that Account and the list updates on the other after a refresh. Re-run the seed and confirm nothing is reseeded (AC10, AC11).
4. Add a differently named firm. Move one Account to another group through the confirmation dialog. A stale move attempted from a second tab is refused, with no change. Inspect the audit (AC5, AC6).
5. Staff and Intake: no edit actions, and direct API attempts are denied with records unchanged. The Manager and Admin succeed. Deleting a populated group is refused; deleting an empty group succeeds (AC4, AC7).
6. The parent fingerprint is unchanged, the Stream, Account, branches and History panels are preserved, and the fault-injected tab is contained (AC3, AC8, AC12).

## 10. Entry gates

| Gate | Requirement | State |
|---|---|---|
| **G0** | CRM-CLIENT-001 delivered and accepted. Its merge commit becomes this WO's base, pinned in an approval-ready version (v1.2 or later) with a final allowlist. | **open — blocks approval** |
| G1 | CGPT exact-version approval of the approval-ready version | open |
| G2 | Sandbox entry gate accepted for CRM-FG-001 | open |
| G3 | CRM-CLIENT-001's browser runner proven in its own cycle (its BA WO delivered and accepted) | open |
| **G0b** | **Exact engineering base.** Either FV2-SYNC-001 is installed, or the CL-D8 pattern is accepted. The base is the PL's local `forge/CRM-CLIENT-001-BA` head or the merged `main`. A GitHub compare must prove the docs-only delta, with no root Git mutation | open |
| **G6** | **Technical gates (Engineer verifies first; stop on failure):**<br>• FG-T1: routes.json custom route reachable after `clear-cache`/`rebuild` on crm-dev;<br>• FG-T2: FirmGroup merge disabling mechanism;<br>• FG-T3: `became.firmGroupName` correct when the action sets id and name;<br>• FG-T4: `SELECT … FOR UPDATE` behaviour under the crm-db engine and isolation level (two-session test, AC5);<br>• FG-T5: whether `readOnly` field metadata feeds `GlobalRestriction` for every user (it would be an extra API guard, not relied on);<br>• **FG-T6:** the Account repository base class (P15);<br>• **FG-T7:** the Formula sandbox endpoint, used to prove AC4(i) | open |
| G4 | FG-D1..D3 decided (2026-11-16); the PL designs in §3 points 3–4 accepted by CGPT | design acceptance open |
| G5 | Dispatch preflight: base unchanged; synthetic crm-dev backed up; beta untouched | open |

**Stop conditions:**
- those in CRM-CLIENT-001 §11;
- any membership route that cannot be both refused or authorised and audited;
- any of FG-T1..FG-T4 failing;
- any change to `parent` or `branches`;
- any need for real data.

## 11. Decisions

| ID | Decision | Provenance and status |
|---|---|---|
| FG-D1 | A move from one group to a different group needs explicit server-validated move intent, an expected-old-membership check and an attributable audit record. UI confirmation alone is insufficient. A first assignment and an unlink use the authorised route. A stale or unauthorised move fails without changing data. | CGPT 2026-11-16, within the PO-approved FirmGroup direction (CRM-D023). Implemented by §3 point 3 and AC5. **Limitation:** "stale" is defined by the expected value under a row lock, not by a version counter. |
| FG-D2 | Every membership write route that cannot be equivalently authorised and audited is disabled. Membership is managed through the Account-side operation, and no unprotected alternative API remains. | CGPT 2026-11-16. Implemented by §3 point 4 and AC4. P4b is now verified: a relate is a direct UPDATE, so every relate route is refused before execution. The P9 bypass is closed by the FirmGroup guard. The grouped-Account delete refusal is PL design under this decision. **v1.3:** the Formula, merge and `accountsIds` relate paths are closed **preventively** by the P15 relation guard. No detective-only substitution remains. The extension-upload residual is out of scope and handled in release readiness. |
| FG-D3 | ER Manager and Admin may delete empty FirmGroups. Neither may delete a populated group by any route. The Account-with-Enquiries protection is untouched. | CGPT 2026-11-16. Implemented by §3 points 5–6 and AC7. |
| FG-D4 | On rollback, the `firmgroup` table and the `account.firm_group_id` column stay in place, unused, because rebuild does not drop columns. This is acceptable for synthetic dev, and beta is reviewed at the operator release gate. | Recorded |
| **FG-D5** | **Browser assurance pattern:** operator-run journeys with the CRM-CLIENT-001 runner, plus a companion `CRM-FG-001-BA` WO whose Tester and DevSecOps assess the sealed evidence. This is the CL-D7 pattern, needed because this WO is user-visible and the sandboxed Tester cannot drive a browser. | **Follows accepted CL-D7** (CGPT, 2026-11-16). The BA WO is drafted at G0 |
