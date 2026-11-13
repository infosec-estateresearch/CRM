WO: CRM-FG-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main — CONDITIONAL: the `main` commit that delivers an accepted CRM-CLIENT-001 (does not exist yet; no SHA is asserted)
BROWSER: yes (real-browser journeys against synthetic crm-dev; see §9)

# CRM-FG-001: FirmGroup entity and Account Group Members tab

- **Version:** v1.0 **CONDITIONAL DRAFT**, 2026-11-13. **Not approval-ready.** It becomes approval-ready only in a later version that pins the base commit (§10, gate G0). This version is identified by the commit that adds it.
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/61
- **Prepared by:** Rogue (Orchestrator), under the CGPT Architect *Extended Autonomous Delivery Run*, Phase C (preparation only, **no implementation, no dispatch**).
- **Approval:** none. Dispatch needs a CGPT approval comment on Issue #61 naming this path and the immutable commit of an approval-ready version.

## 1. Authority and governing records

| Item | Value |
|---|---|
| Governing FOUNDRY | `5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0`; `standards/work-order-contract.md` sha256 `cbb6eb3ae62bf7877ae470abf2297a5af5ffb23ca617581a9a85077dd9a8ebcc` |
| Product authority | Matt's PO approval at `dc6fb4ced68d9139c2332af973084239492104b3` (Issue #54, 2026-11-13T12:04:29Z): Vision, Backlog incl. **CRM-PBI-018**, decisions CRM-D020..D032 (FirmGroup: D023; parent/branch kept: D031) |
| Requirements | `docs/requirements/crm-modules-requirements.md` **FG-01..FG-10** (FG-11 out of scope); `docs/requirements/firmgroup-ux-contract.md` (journeys 1–6); `docs/architecture/crm-wip-module-boundary.md` *FirmGroup: independent CRM identity*; `docs/delivery/forge-wo-intake-briefs.md` *CRM-FG-001*; `docs/delivery/crm-module-sequencing.md` Gate C |
| Dependency | **CRM-CLIENT-001** (Issue #59, PR #60) must be delivered and accepted: the Group Members tab lists *other* members of the Account's group, which is not a standard relationship panel and needs a CRM-owned client view under `client/custom/src/` |
| Main at drafting | `6e1766980e24d781d498727d4fe5db43cdeadbb7` (information only; **not** the engineering base) |
| Technical preflight | No separate HELM CRM-FG-001 preflight artifact was found in the repository or on Issue #54; this WO's §2 is the PL read-only preflight. If CGPT holds a HELM preflight, it must be attached to Issue #61 and reconciled in the approval-ready version |

## 2. PL technical preflight (read-only, `main` @ `6e176698`, EspoCRM 10.0.12)

| # | Fact / risk | Consequence for this WO |
|---|---|---|
| P1 | `Account` custom fields: name, type, industry, assignedUser, practiceManagementSystem, learningPlatformAccess, parent, branches, sfId, sfOwnerId, sfCreatedAt; links `parent`/`branches`. No group concept exists | Add `firmGroup` (belongsTo) only; `parent`/`branches` untouched (FG-03) |
| P2 | `config/access/roles.json`: ER Staff and ER Intake **edit all** on Account; ER Import **edit all** on Account (API) | Membership must be controlled at **field level** (`Account.firmGroup` edit **no** for Staff, Intake, Import) **and** at scope level (`FirmGroup` create/edit/delete no for Staff, Intake, Import), plus a server hook as defence in depth (P4) |
| P3 | `tests/unit/access_policy.py` requires every scope to be explicit in every role (`ACL_ENTITY_SCOPES`, `EXPECTED_DATA`) | `FirmGroup` is added to the policy constants and expected data; the policy test fails closed if any role omits it |
| P4 | **Risk (to verify, not assumed):** in EspoCRM a membership can change through more than one path: `PUT /Account/{id}` (`firmGroupId`), `POST`/`DELETE /FirmGroup/{id}/accounts` (relate/unrelate from the group side), mass update, import, merge, and create with a preset `firmGroupId`. Field-level ACL may not govern the relate endpoint | AC4 tests **every** path for every role; a server-side `beforeSave` hook on Account refuses a `firmGroupId` change by any user lacking FirmGroup edit, and a relate/unrelate guard does the same; any path that cannot be authorised **and** audited is disabled, or the WO stops |
| P5 | Audit: Account already audits name, type, industry, assignedUser, parent, learningPlatformAccess (ACCESS.md) | `firmGroup` is `audited: true`; AC5 proves who/when/old/new for add, move and remove **through every permitted path**, including the group-side relate |
| P6 | `Hooks/Account/RestrictDeleteWithEnquiries.php` refuses Account deletion with enquiries, even for admin | A parallel `Hooks/FirmGroup/RestrictDeleteWithMembers` refuses deletion of a group with members (FG-10), incl. admin and mass delete; the Account hook stays and is regression-tested |
| P7 | Account `clientDefs` has a `branches` relationship panel; relationships layout lists branches, contacts, opportunities, cases, documents | The Group Members tab is **added**; existing panels, Stream and activities unchanged (AC7) |
| P8 | Client loading needs `update-app-timestamp` after deploy (CRM-CLIENT-001 F3) | Satisfied only through the CRM-CLIENT-001 mechanism; this WO does not touch deploy scripts |

## 3. Intended outcome

1. `FirmGroup` entity: `name` (required, not unique), `description` (optional), CRM-native immutable ID, **no** `sfId` (UX contract); hasMany `accounts`.
2. `Account.firmGroup`: optional belongsTo; at most one group per Account; null means *Not part of a group*.
3. ER Manager and Admin create/rename groups and add, move or remove members; ER Staff and ER Intake read only; **ER Import cannot create/edit groups or change membership**. Enforced server-side on every path (P4).
4. Every membership change audited (who, when, old group ID, new group ID). A move from one group to another requires explicit confirmation in the UI.
5. A group with members cannot be deleted (API, UI, mass delete, admin).
6. Account detail gains a **Group Members** tab beside the existing areas: header with the group name linking to the FirmGroup record; *other* members (name, address/postcode, tier/type, phone), clickable, paginated, duplicates by name all shown; empty state *Not part of a group*; manager-only actions.
7. FirmGroup detail: name, description, member list, manager add/select and unlink.
8. **No seeding**: no group created from Salesforce parent trees, legacy WIP or names. Synthetic fixtures only.

## 4. In scope (allowlist — to be finalised in the approval-ready version against the pinned base)

| Path | Change |
|---|---|
| `custom/Espo/Custom/Resources/metadata/scopes/FirmGroup.json`, `entityDefs/FirmGroup.json`, `clientDefs/FirmGroup.json`, `recordDefs/FirmGroup.json` (if needed) | new entity |
| `custom/Espo/Custom/Resources/metadata/entityDefs/Account.json`, `clientDefs/Account.json` | add `firmGroup` field/link (audited) and the Group Members tab/panel definition only |
| `custom/Espo/Custom/Resources/layouts/FirmGroup/*.json`, `layouts/Account/detail.json` and/or `bottomPanelsDetail.json` | new FirmGroup layouts; Account adds the tab only |
| `custom/Espo/Custom/Resources/i18n/en_US/FirmGroup.json`, `Account.json`, `Global.json` | labels incl. *Group Members*, *Not part of a group* |
| `custom/Espo/Custom/Hooks/FirmGroup/RestrictDeleteWithMembers.php`, `custom/Espo/Custom/Hooks/Account/GuardFirmGroupMembership.php` (+ relate guard if required by P4) | new server guards |
| `client/custom/src/crm/views/account/group-members-panel.js` (+ template if needed) | new view (requires CRM-CLIENT-001) |
| `config/access/roles.json` | FirmGroup scope for all roles; `Account.firmGroup` fieldData |
| `tests/unit/access_policy.py`, `test_access_policy.py`, `test_metadata.py`, new `tests/unit/test_firmgroup.py` | policy and metadata tests |
| `scripts/seed_synthetic.py` (synthetic fixtures only) and its tests | two unrelated peers, one branch hierarchy, duplicate names, ungrouped firm |
| `tests/acceptance/test_firmgroup_api.py` (synthetic crm-dev only) and `tests/browser/` journeys | API denial matrix; browser journeys |
| `docs/ACCESS.md`, `docs/BUILD.md`, `docs/REQUIREMENTS-TRACEABILITY.md` | truthful documentation |

## 5. Exclusions

- `Account.parent`, `branches`, `sfId` and every `sf*` field and their ACL; the CRM-002 extractor/loader and Salesforce (no read or write); legacy WIP repo/data; WIP entities (CRM-WIP-001+); FG-11 curated seed (PBI-024).
- `scripts/deploy_*.sh`, `release.py`, `backup.sh`, `restore.sh`, `deploy/**` (delivery is CRM-CLIENT-001's mechanism, unchanged).
- The running beta, beta data and `/srv/CRM/deploy`; FOUNDRY; ForgeV2; other host apps.

## 6. Acceptance criteria

| AC | Criterion (requirement) | Evidence |
|---|---|---|
| AC1 | FirmGroup with required non-unique name, optional description, no sfId; two groups may share a name (FG-01) | metadata tests; API test |
| AC2 | Account has at most one group; null allowed; FirmGroup has 0..n Accounts (FG-02) | metadata + API |
| AC3 | **Parent graph fingerprint**: sha256 of the sorted (id, parentId) set over all synthetic Accounts identical before and after every journey and API test (FG-03) | acceptance + browser records |
| AC4 | **Server ACL matrix** (FG-05): for ER Staff, ER Intake, ER Import, ER Manager, Admin × {create/rename/delete FirmGroup; `PUT /Account` firmGroupId; Account create with firmGroupId; `POST/DELETE /FirmGroup/{id}/accounts`; mass update; merge} → only Manager/Admin succeed; every denial returns 403 (or the documented EspoCRM denial) **and** the stored records are byte-identical afterwards (row fingerprint) | `test_firmgroup_api.py` on synthetic crm-dev |
| AC5 | Audit: add, move (A→B) and remove each produce an attributable record with user, time, old and new group ID, via each permitted path (FG-04) | API + browser (Stream/Audit Log) |
| AC6 | Delete refusal: a group with members cannot be deleted by Manager or Admin via UI, API or mass delete; an empty group can be deleted by Manager/Admin only (FG-10); Account-with-enquiries delete refusal still holds (CRM-003 regression) | API + browser |
| AC7 | Group Members tab beside the existing detail areas; Stream, Account details, branches, contacts, enquiries and activities unchanged (FG-06, UX contract, journey 6) | screenshots before/after on the same synthetic Account |
| AC8 | Tab content: group name link opens the FirmGroup; lists other members only, with name, address/postcode, tier/type, phone; each opens the Account; paginates beyond page size; same-name peers all shown; empty state *Not part of a group*; no edit action for Staff/Intake; manager can create/select (FG-06, FG-07) | browser |
| AC9 | Consistency: membership changed from either the Account or the FirmGroup side is identical after refresh on both (FG-08) | browser |
| AC10 | No inference: after deploy and synthetic seed, zero groups exist except those created by the journeys; no code path derives groups from parent trees or names (FG-09) | unit (static) + API count |
| AC11 | Client failure containment: with the Group Members view forced to error, the Account detail page still renders all other panels and shows a bounded error in the tab | browser fault injection |
| AC12 | Regression: unit suite (≥ starting count, non-root, `git archive` copy), `tests/load`, beta-safe suite against synthetic dev, CRM-TEST-001 mutation guard, existing access policy | host procedure + Tester |
| AC13 | Release: candidate bundle verifies (`release.py verify --sha256`); upgrade from the pre-FG release and rollback to it on synthetic crm-dev keep all Accounts and their `parent` unchanged; rollback removes the FirmGroup UI; data in `firmgroup` table after rollback is documented (left in place, unused) | host procedure |

## 7. Security controls

Server-side authorisation on every path (P4) with hidden buttons never relied on; no new privilege via default scopes; synthetic `@example.test` users and synthetic firms only; no customer data, sfIds, addresses or credentials in Git, tests, screenshots, prompts or logs; gitleaks on the candidate; DevSecOps reviews the ACL matrix, hooks (bypass via `skipHooks`/import options), and client view escaping (no `innerHTML` with record data; templates escape).

## 8. Roles and independent criteria

| Role | PASS only if |
|---|---|
| Engineer | §4 only; every AC has a test or a defined browser journey; P4 paths enumerated from the 10.0.12 source and each covered |
| Auditor | allowlist exact; FG-01..FG-10 traced to AC; `parent`/`branches`/`sf*` untouched; docs truthful |
| Tester | all AC evidenced on the same unchanged candidate, incl. AC4 full matrix and browser journeys 1–6 of the UX contract |
| DevSecOps | no ACL bypass, no hook bypass, no XSS path in the client view, no secret/customer data |

Four executions per specialist maximum, including the first; exhaustion is FAIL and escalation. Evidence: engine records `…/records/3b6369e4f8e78d83/CRM-FG-001/`; PL evidence `/home/forgev2-pl/crm-evidence/CRM-FG-001/`.

## 9. Real-browser journeys (synthetic crm-dev, tool per CRM-CLIENT-001 CL-D2)

1. Manager creates a group from two unrelated peer firms; neither becomes `parent` (AC3).
2. Open each Account → Group Members → navigate to the other and back (AC8).
3. Remove one member; empty state on that Account and updated list on the other after refresh; re-run the seed and confirm no reseeding (AC9, AC10).
4. Add a differently named firm; move one Account to another group with the confirmation; inspect the audit (AC5).
5. Staff and Intake: no edit actions; direct API attempts denied and records unchanged; Manager/Admin allowed; delete of a populated group refused (AC4, AC6).
6. Parent graph fingerprint unchanged; Stream, Account, branches and History panels preserved (AC3, AC7); fault-injected tab (AC11).

## 10. Entry gates

| Gate | Requirement | State |
|---|---|---|
| **G0** | CRM-CLIENT-001 delivered and accepted; its merge commit becomes this WO's base, pinned in an approval-ready version (v1.1+) with a final allowlist | **open — blocks approval** |
| G1 | CGPT exact-version approval of the approval-ready version | open |
| G2 | Sandbox entry gate accepted for CRM-FG-001 (engine identity re-verified at that time) | open |
| G3 | Browser component (CL-D2) approved and proven in CRM-CLIENT-001 | open |
| G4 | Open decisions FG-D1..FG-D3 answered | open |
| G5 | Dispatch preflight: base unchanged; synthetic crm-dev backed up; beta untouched | open |

**Stop conditions:** as CRM-CLIENT-001 §11, plus: any membership path that cannot be both authorised and audited; any change to `parent`/`branches`; any need for real data.

## 11. Open decisions

- **FG-D1 (PO/CGPT):** server-side *move* semantics — is UI confirmation plus audit sufficient, or must the API require an explicit move intent for A→B changes? (Draft assumes UI confirmation + audit; no invented server rule.)
- **FG-D2 (CGPT):** if EspoCRM's group-side relate endpoint cannot be audited equivalently, may membership edits be restricted to the Account side only (FirmGroup detail read-only list + link to Account)?
- **FG-D3 (PO):** whether ER Manager may delete empty groups or Admin only (draft: Manager and Admin).
- **FG-D4 (recorded):** rollback leaves the `firmgroup` table and `account.firm_group_id` column in place (EspoCRM does not drop columns on rebuild); acceptable for synthetic dev; beta implications reviewed at the operator release gate.
