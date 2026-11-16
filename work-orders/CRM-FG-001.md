WO: CRM-FG-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main — CONDITIONAL: the `main` commit that delivers an accepted CRM-CLIENT-001 (does not exist yet; no SHA is asserted)
BROWSER: yes (real-browser journeys against synthetic crm-dev, using the CRM-CLIENT-001 runner and evidence route)

# CRM-FG-001: FirmGroup entity and Account Group Members tab

- **Version:** v1.1 **CONDITIONAL DRAFT**, 2026-11-16. **It is not approval-ready.** That requires a later version that pins the base commit (gate G0, §10). This version is identified by the commit that adds it.
- **History:**
  - v1.0 is commit `6c78099d0cdea5b8cb306cae863bd7eeaab38841`.
  - v1.1 records CGPT decisions FG-D1, FG-D2 and FG-D3 (2026-11-16, Phase D). It replaces the unverified P4 risk with route facts verified against the 10.0.12 source (§2), and fixes the membership design to a single guarded Account-side operation (§3).
  - G0 is unchanged.
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/61
- **Prepared by:** Rogue (Orchestrator). Preparation only: **no implementation, no dispatch.**
- **Approval:** none. Dispatch needs a CGPT approval comment on Issue #61 that names this path and the immutable commit of an approval-ready version.

## 1. Authority and governing records

| Item | Value |
|---|---|
| Governing FOUNDRY | `5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0`; `standards/work-order-contract.md` sha256 `cbb6eb3ae62bf7877ae470abf2297a5af5ffb23ca617581a9a85077dd9a8ebcc` |
| Product authority | Matt's PO approval at `dc6fb4ced68d9139c2332af973084239492104b3` (Issue #54, 2026-11-13T12:04:29Z): the Vision and the Backlog, including **CRM-PBI-018**, and CRM-D020..D032 (D023: FirmGroup; D031: parent and branch kept) |
| Architect decisions | **FG-D1, FG-D2 and FG-D3**: CGPT directive of 2026-11-16, within the approved FirmGroup direction (§11) |
| Requirements | `docs/requirements/crm-modules-requirements.md` **FG-01..FG-10** (FG-11 is out of scope); `docs/requirements/firmgroup-ux-contract.md`, journeys 1–6; `docs/architecture/crm-wip-module-boundary.md`; `docs/delivery/crm-module-sequencing.md` Gate C |
| Dependency | **CRM-CLIENT-001**: Issue #59, PR #60, v1.1 at `0fba12cf5395800d02db5801e4772506c849cb1a`. This WO needs its client delivery, cache-bust, browser runner and evidence route |
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
| P4b | **There is no ORM-level before-relate hook**, only `AfterRelate`, `AfterUnrelate` and `AfterMassRelate`. Relating through the hasMany side writes the foreign key through `RDBRelation`. **UNVERIFIED:** whether that path triggers Account `beforeSave`. | `Core/Hook/Hook/` listing; `AfterRelate.php` `d97078e1db8c138c53452bd15d60ac1ea54927a3fd33f72c5215dd06e96dbcf9`; `ORM/Repository/RDBRelation.php` `19eab65eda7db116bb8afd0f76d44a2c15d1ba1cd96a8a15d52db7b3f7913259` | An ORM guard cannot be relied on for relate routes. They are refused at the record layer (P4a), and an internal relate is never used for membership. |
| P4c | `massLink` is allowed only when `recordDefs.<E>.relationships.<link>.massLink` is set, and **it does not run the `beforeLink` record hooks**. | `Record/Service.php` line 1210 and following | `massLink` must stay **unset** for both sides. AC4 proves a 403. |
| P4d | `LinkCheck::processLink` requires `edit` on the parent record. Field-level forbidden links are enforced through `getScopeForbiddenLinkList`. | `Core/Record/Access/LinkCheck.php` `439fc8e88b839be98bfbbd5c0c5c630f567949ba79c01bd57434f51d2549bb5c` | This is defence in depth only, because admin bypasses ACL. |
| P5 | The stream writes "Update" audit notes for audited fields on **every ORM save that is not `SILENT`**. Audited links write relate and unrelate notes. | `Hooks/Common/Stream.php`; `Tools/Stream/HookProcessor.php` `7e3a69ac952cb1132c6a329aa922b7f869bd3b2d15966aba3bab43c84a593839` | With `firmGroup` audited and a non-silent save, the audit records who, when, the old value and the new value. The membership service never saves silently. |
| P6 | Custom API routes support `actionClassName`, and `forUpdate()` row locking is available in the ORM select builder. | `Resources/routes.json` `8a724e7c49ee971f30ee370eef2de9c395440163daee30df73bfbd468aed4871`; `ORM/Repository/RDBSelectBuilder.php` `004f2c273b6af16b249d9015fefd450c6a7b6f34d240bf8ba6b532b231ffe1ed` | A dedicated membership action with a transactional expected-old check is implementable. **UNVERIFIED:** whether `custom/Espo/Custom/Resources/routes.json` is merged at 10.0.12. The Engineer verifies this first, and it is a stop if not. |
| P7 | `Hooks/Account/RestrictDeleteWithEnquiries.php` refuses deletion of an Account that has enquiries, even for admin. | `main` | It is **untouched** (FG-D3) and is regression-tested. |
| P8 | Client code loads as AMD from `client/custom/src` with `appTimestamp` cache-busting. | CRM-CLIENT-001 §2 F3 and F8 | The Group Members view is an AMD view delivered through CRM-CLIENT-001. |

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
   - **ORM `beforeSave` on Account** (`Hooks/Account/GuardFirmGroupMembership.php`). Any create or update that changes `firmGroupId` without `crmFirmGroupMembership` is refused. This covers `PUT /Account`, Account create with a group set, mass update, import, merge, formula, workflow and admin.
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
| AC4 | **Route matrix** (FG-05, FG-D2), for ER Staff, ER Intake, ER Import, ER Manager and Admin:<br>(a) the action's assign, unlink and move: only Manager and Admin succeed; everyone else gets 403;<br>(b) `PUT /Account` with `firmGroupId`, Account create with `firmGroupId`, mass update, import and merge: refused for **every** role, admin included;<br>(c) `POST` and `DELETE /FirmGroup/{id}/accounts`, and the Account-side `firmGroup` link: refused for every role, admin included;<br>(d) `massLink` on both sides: 403;<br>(e) FirmGroup create, rename and delete follow §3 point 5.<br>Every refusal leaves the Account and FirmGroup row fingerprints byte-identical. | `test_firmgroup_api.py` on synthetic crm-dev |
| AC5 | **Move semantics** (FG-D1):<br>• a move without `operation: "move"`, or with a stale or absent `expectedCurrentGroupId`, returns 409 or 400 and changes nothing;<br>• an assign while a group is already set returns 409;<br>• two concurrent moves from the same expected group: exactly one succeeds and the other returns 409. | API, including a concurrency test |
| AC6 | **Audit** (FG-04): each successful assign, unlink and move produces exactly one attributable record with user, time, old group ID and new group ID. Refused attempts produce none. | API (stream and audit-log query) and browser |
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
| Engineer | Only §4 changes. It has verified P4b and P6 (UNVERIFIED items), or stopped on them. Every AC has a test or a journey. |
| Auditor | The allowlist is exact. FG-01..FG-10 and FG-D1..D3 are traced to ACs. `parent`, `branches`, `sf*` and the enquiry hook are untouched. The documentation is truthful. |
| Tester | All ACs are evidenced on the same unchanged candidate, including the full AC4 matrix and the AC5 concurrency test. Browser verdicts are its own, from the CRM-CLIENT-001 evidence route. |
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
| G3 | CRM-CLIENT-001's browser runner proven in its own cycle | open |
| G4 | FG-D1..D3 decided (2026-11-16); the PL designs in §3 points 3–4 accepted by CGPT | design acceptance open |
| G5 | Dispatch preflight: base unchanged; synthetic crm-dev backed up; beta untouched | open |

**Stop conditions:**
- those in CRM-CLIENT-001 §11;
- any membership route that cannot be both refused or authorised and audited;
- P6 not supported;
- any change to `parent` or `branches`;
- any need for real data.

## 11. Decisions

| ID | Decision | Provenance and status |
|---|---|---|
| FG-D1 | A move from one group to a different group needs explicit server-validated move intent, an expected-old-membership check and an attributable audit record. UI confirmation alone is insufficient. A first assignment and an unlink use the authorised route. A stale or unauthorised move fails without changing data. | CGPT 2026-11-16, within the PO-approved FirmGroup direction (CRM-D023). Implemented by §3 point 3 and AC5. **Limitation:** "stale" is defined by the expected value under a row lock, not by a version counter. |
| FG-D2 | Every membership write route that cannot be equivalently authorised and audited is disabled. Membership is managed through the Account-side operation, and no unprotected alternative API remains. | CGPT 2026-11-16. Implemented by §3 point 4 and AC4. **Limitation:** P4b is unverified, so the design does not depend on it. The grouped-Account delete refusal is PL design under this decision. |
| FG-D3 | ER Manager and Admin may delete empty FirmGroups. Neither may delete a populated group by any route. The Account-with-Enquiries protection is untouched. | CGPT 2026-11-16. Implemented by §3 points 5–6 and AC7. |
| FG-D4 | On rollback, the `firmgroup` table and the `account.firm_group_id` column stay in place, unused, because rebuild does not drop columns. This is acceptable for synthetic dev, and beta is reviewed at the operator release gate. | Recorded |
