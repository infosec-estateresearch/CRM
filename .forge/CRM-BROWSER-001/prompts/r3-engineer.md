# Engineer, execution 3 of 3 (final; no Engineer correction remains afterwards)

Worktree (the only path you may change): /srv/CRM/worktrees/CRM-BROWSER-001
Never touch any other path. Expected HEAD: abd1b04dd7d91f809ca3bf29fb29c15cf19c449a (the base: nothing is committed; do not commit). The worktree holds the uncommitted work of executions 1 and 2. Keep, correct and extend it.
Scratch directory: /srv/CRM/worktrees/.forge-scratch/CRM-BROWSER-001

**Dispatch time (UTC): 2026-11-27 17:50:03Z. Deadline: 2026-11-27 18:10:03Z.** Check `date` between items; at the deadline stop and report `STATUS: completed` with an `UNFINISHED:` list (`blocked` only for a real blocker). Report returned by minute 25; the engine kills a run at 30 minutes and keeps no report. Write files as you go, simplest complete path first. After you, the work is committed and reviewed by Auditor, Tester and DevSecOps as it stands.

## Scope: correct the work against the operator gate 2 report below
Fix every item in section B of the report (selectors, readiness, clean page per step, admin iframe setting in this run's own stack only, list search, related panels, select dialog, assigned user, switch primary), apply the declarations of section C exactly as observed, correct expectations per section D items 9-12 (declare what the base does; never label as "not offered" what is offered; do not weaken a check), and avoid step ids/evidence file names containing api, key, token, secret, auth, access, credential or password (rename J6 steps, e.g. request-create-user, request-edit-user, and keep the expectation data consistent; check every other id you add). Then the non-vacuity checks that execution 2 could not run (mutations showing new tests fail when a control is removed; restore files afterwards), and update tests. Note for the delivery record in BUILD.md or the report: items 7, 9, 10, 11, 12 behaviours. Keep host-side code small and readable. Report suite counts before and after, host-executing files, every changed existing test line, UNFINISHED list.

Your own unfinished list from execution 2: non-vacuity not run; J2-J6 untested in browser; declared refusal texts guessed (now observed, see section C); selectors unverifiable (see report); J5 expectations guesses (see report D).

## Operator gate 2 report (verbatim; for you only)

GATE: FAIL

Orchestrator runtime gate 2 for CRM-BROWSER-001 on the uncommitted work after Engineer execution 2.
Operator runtime evidence for the Engineer only. Not acceptance; it replaces no review or criterion.

All stages ran. Changed files: 11, all inside the delivery boundary.

| Stage | Verdict | Detail |
|---|---|---|
| unit | PASS | non-root, PHP and platform reference, no network: Ran 769 tests in 74.188s OK |
| fault-broken-screen | PASS | exit 1, 117 s, 35 evidence files |
| fault-wrong-expectation | PASS | exit 1, 126 s, 35 evidence files |
| fault-killed-app | PASS | exit 1, 51 s, 35 evidence files |
| interrupt-SIGINT | PASS | exit 1, 96 s, 0 evidence files |
| interrupt-SIGTERM | PASS | exit 1, 96 s, 0 evidence files |
| full-run | FAIL | exit 1, 927 s, 259 evidence files; exit 1, expected 0; secret scan reported findings or failed |
| verify-genuine | FAIL | exit 1, expected 0 |
| verify-other-commit | PASS | exit 1, expected rejection |
| verify-changed | PASS | exit 1, expected rejection |
| verify-removed | PASS | exit 1, expected rejection |
| verify-added | PASS | exit 1, expected rejection |
| verify-substituted | PASS | exit 1, expected rejection |
| host-inventory | PASS | before and after: 0 differences |
| host-events | PASS | 0 actions outside the run's own resources; 2 notices (anonymous volumes, images, unrelated activity) |

## fault-broken-screen: output (end)
```
[browser-assurance] running journeys ['J1'] in the runner container
WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager, possibly rendering your system unusable. It is recommended to use a virtual environment 
settings: updated (baseCurrency, currencyList, defaultCurrency, phoneNumberInternational)
team Enquiries: created
team Ancillary intake: created
team Firm management: created
role ER Staff: created
role ER Intake: created
role ER Manager: created
role ER Import: created
API user er-import: created; key written to /tmp/er-import-key
dashboardTemplate ER Staff: created
[runner] J1/administrator/create-firm: failed
[runner] J1/administrator/create-branch: failed
[runner] J1/administrator/create-contact: failed
[runner] J1/administrator/create-enquiry: failed
[runner] J1/er-staff/create-firm: failed
[runner] J1/er-staff/create-branch: failed
[runner] J1/er-staff/create-contact: failed
[runner] J1/er-staff/create-enquiry: failed
[runner] J1/er-intake/create-firm: failed
[runner] J1/er-intake/create-branch: failed
[runner] J1/er-intake/create-contact: failed
[runner] J1/er-intake/create-enquiry: failed
[runner] J1/er-manager/create-firm: failed
[runner] J1/er-manager/create-branch: failed
[runner] J1/er-manager/create-contact: failed
[runner] J1/er-manager/create-enquiry: failed
[runner] failed steps: ['J1/administrator/create-firm', 'J1/administrator/create-branch', 'J1/administrator/create-contact', 'J1/administrator/create-enquiry', 'J1/er-staff/create-firm', 'J1/er-staff/create-branch', 'J1/
[browser-assurance] FAILED: runner reported a failed step or error (exit 1)
```

## fault-wrong-expectation: output (end)
```
[browser-assurance] running journeys ['J1'] in the runner container
WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager, possibly rendering your system unusable. It is recommended to use a virtual environment 
settings: updated (baseCurrency, currencyList, defaultCurrency, phoneNumberInternational)
team Enquiries: created
team Ancillary intake: created
team Firm management: created
role ER Staff: created
role ER Intake: created
role ER Manager: created
role ER Import: created
API user er-import: created; key written to /tmp/er-import-key
dashboardTemplate ER Staff: created
[runner] J1/administrator/create-firm: failed
[runner] J1/administrator/create-branch: passed
[runner] J1/administrator/create-contact: passed
[runner] J1/administrator/create-enquiry: failed
[runner] J1/er-staff/create-firm: passed
[runner] J1/er-staff/create-branch: passed
[runner] J1/er-staff/create-contact: passed
[runner] J1/er-staff/create-enquiry: failed
[runner] J1/er-intake/create-firm: passed
[runner] J1/er-intake/create-branch: passed
[runner] J1/er-intake/create-contact: passed
[runner] J1/er-intake/create-enquiry: failed
[runner] J1/er-manager/create-firm: passed
[runner] J1/er-manager/create-branch: passed
[runner] J1/er-manager/create-contact: passed
[runner] J1/er-manager/create-enquiry: failed
[runner] failed steps: ['J1/administrator/create-firm', 'J1/administrator/create-enquiry', 'J1/er-staff/create-enquiry', 'J1/er-intake/create-enquiry', 'J1/er-manager/create-enquiry']
[browser-assurance] FAILED: runner reported a failed step or error (exit 1)
```

## fault-killed-app: output (end)
```
[browser-assurance] running journeys ['J1'] in the runner container
WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager, possibly rendering your system unusable. It is recommended to use a virtual environment 
settings: updated (baseCurrency, currencyList, defaultCurrency, phoneNumberInternational)
team Enquiries: created
team Ancillary intake: created
team Firm management: created
role ER Staff: created
role ER Intake: created
role ER Manager: created
role ER Import: created
API user er-import: created; key written to /tmp/er-import-key
dashboardTemplate ER Staff: created
[runner] J1/administrator/create-firm: passed
[runner] J1/administrator/create-branch: passed
[runner] J1/administrator/create-contact: failed
[runner] J1/administrator/create-enquiry: failed
[runner] J1/er-staff/create-firm: failed
[runner] J1/er-staff/create-branch: failed
[runner] J1/er-staff/create-contact: failed
[runner] J1/er-staff/create-enquiry: failed
[runner] J1/er-intake/create-firm: failed
[runner] J1/er-intake/create-branch: failed
[runner] J1/er-intake/create-contact: failed
[runner] J1/er-intake/create-enquiry: failed
[runner] J1/er-manager/create-firm: failed
[runner] J1/er-manager/create-branch: failed
[runner] J1/er-manager/create-contact: failed
[runner] J1/er-manager/create-enquiry: failed
[runner] failed steps: ['J1/administrator/create-contact', 'J1/administrator/create-enquiry', 'J1/er-staff/create-firm', 'J1/er-staff/create-branch', 'J1/er-staff/create-contact', 'J1/er-staff/create-enquiry', 'J1/er-int
[browser-assurance] FAILED: runner reported a failed step or error (exit 1)
```

## full-run: output (end)
```
[runner] J2/er-manager/edit-firm: passed
[runner] J2/er-manager/edit-contact: passed
[runner] J2/er-manager/edit-enquiry: passed
[runner] J3/er-manager/search-firm: passed
[runner] J3/er-manager/search-contact: passed
[runner] J3/er-manager/search-enquiry: passed
[runner] J4/er-manager/set-branch-parent: passed
[runner] J4/er-manager/change-branch-parent: passed
[runner] J4/er-manager/link-second-firm: passed
[runner] J4/er-manager/switch-primary-firm: failed
[runner] J4/er-manager/change-enquiry-firm: passed
[runner] J4/er-manager/related-panels: failed
[runner] J5/er-manager/delete-firm-record: passed
[runner] J5/er-manager/delete-contact-record: passed
[runner] J5/er-manager/delete-firm-list: failed
[runner] J5/er-manager/delete-contact-list: failed
[runner] J5/er-manager/delete-branch-related: failed
[runner] J5/er-manager/delete-contact-related: failed
[runner] J5/er-manager/merge-firm: failed
[runner] J5/er-manager/merge-contact: failed
[runner] J5/er-manager/merge-enquiry: failed
[runner] J5/er-manager/unlink-primary-firm: failed
[runner] J5/er-manager/audit-immutable: passed
[runner] J6/er-manager/administration-area: failed
[runner] J6/er-manager/import-area: passed
[runner] J6/er-manager/user-create-screen: passed
[runner] J6/er-manager/api-create-user: failed
[runner] J6/er-manager/api-edit-user: failed
[runner] failed steps: ['J1/administrator/create-enquiry', 'J1/er-staff/create-enquiry', 'J1/er-intake/create-enquiry', 'J1/er-manager/create-enquiry', 'J4/administrator/switch-primary-firm', 'J4/administrator/related-pa
[browser-assurance] FAILED: runner reported a failed step or error (exit 1)
```

## verify-genuine: output (end)
```
[browser-assurance] REJECTED: step record not passed: J6/er-manager/administration-area.json
[browser-assurance] REJECTED: step not passed: J6/administrator/import-area
[browser-assurance] REJECTED: step record not passed: J6/administrator/import-area.json
[browser-assurance] REJECTED: step not passed: J6/er-staff/api-create-user
[browser-assurance] REJECTED: step record not passed: J6/er-staff/api-create-user.json
[browser-assurance] REJECTED: step not passed: J6/er-intake/api-create-user
[browser-assurance] REJECTED: step record not passed: J6/er-intake/api-create-user.json
[browser-assurance] REJECTED: step not passed: J6/er-manager/api-create-user
[browser-assurance] REJECTED: step record not passed: J6/er-manager/api-create-user.json
[browser-assurance] REJECTED: step not passed: J6/er-staff/api-edit-user
[browser-assurance] REJECTED: step record not passed: J6/er-staff/api-edit-user.json
[browser-assurance] REJECTED: step not passed: J6/er-intake/api-edit-user
[browser-assurance] REJECTED: step record not passed: J6/er-intake/api-edit-user.json
[browser-assurance] REJECTED: step not passed: J6/er-manager/api-edit-user
[browser-assurance] REJECTED: step record not passed: J6/er-manager/api-edit-user.json
```

## Orchestrator notes
This is the last Engineer execution and no further runtime gate precedes the commit. Everything below was seen at runtime: the gate run, then five short probes in a throwaway copy (the runner's journey call replaced by probes, same confinement, not part of the work). Full run: 71 of 128 steps passed, about 15 minutes, mostly step timeouts. J2 and J3 pass completely.

## A. Stage results that need a correct reading
- **"secret scan reported findings" is not a leak.** All 16 findings are the SHA-256 values of evidence files in `manifest.json` whose names contain `api-` (J6 `api-create-user`, `api-edit-user`); each equals the file's hash. The standard scan must be clean: renaming those step ids (tried: `request-create-user`, `request-edit-user`) made gitleaks 8.30.1 report nothing on that manifest. The same applies to any step id or evidence file name containing api, key, token, secret, auth, access, credential or password beside a hash, including steps you add.
- `verify-genuine` failed only because steps failed; the other-commit, changed, removed, added and substituted cases were all rejected.
- Faults act at step level: `broken-screen` fails J1 steps that pass normally; `wrong-expectation` fails administrator `create-firm` only for the altered expectation; `killed-app` passes two steps, then fails. Both interrupts left nothing. Unit suite 769 OK.

## B. Defects in the journeys and runner
1. **Refusal message:** the element is `#notification.alert-danger` itself. The selector `#notification .alert-danger` never matches (record delete "timeout").
2. **Screen readiness:** hash navigation keeps the previous screen, so bare `#main` is satisfied before the new route renders: J6 administration area read "performed" for accounts that get access denied. Wait for the target's own marker (`#main .admin-content`, `.import-container`) or the denied text; check other generic ready selectors for the same stale match. In a probe, navigation stopped taking effect after the enquiry create form had been filled and left (cause not inspected); reloading between steps avoided it. Start each step from a clean page so one failure cannot cascade.
3. **Admin page external request:** the administration page loads a frame from the vendor site (`views/admin/index`, config `adminPanelIframeUrl`); with no external route it fails and lands in the next step ("requestfailed GET /", administrator `import-area`). No filter is permitted: set `adminPanelIframeDisabled` to true in this run's own stack (the admin template then renders no frame; read in the reference, not tried at runtime), and document it. Do not rely on an empty `adminPanelIframeUrl`: it falls back to the vendor address.
4. **Lists:** the text filter is starts-with: `tag+slug` returns no rows. Search `%<tag><slug>` (matches only that kind's own fixtures; used successfully for merge pairs) or the full record name as J3 does, and wait for the row by id; do not search a shared prefix such as `BR `, which matches other kinds' records. Wait for the list (or the select dialog) to render before typing: typing early cancels the screen's own first request (`net::ERR_ABORTED`), which is then an undeclared failed request. Record the failure reason. Mass-action entries also exist hidden: use `:visible`.
5. **Related panels:** the firm page has tabs Stream, Account, Support (`button[data-tab]`); contacts and enquiries are on Account. Use `tr[data-id=...]` (bare `[data-id]` also matches hidden menu items), then the row `.dropdown-toggle` and `[data-action=removeRelated|unlinkRelated]:visible`. Contacts panel: administrator is offered Remove and Unlink, the three ER kinds only Unlink.
6. **Select dialog:** confirm is `button[data-name=select]`. With that, linking a contact to an enquiry assigned to the user worked for all four kinds, and `contactsIds` reads back by API.
7. **ER Staff enquiry:** the create screen leaves Assigned User empty, so ER Staff cannot edit the enquiry just created (no Select). Set Assigned User to the signed-in user on the create screen (autocomplete worked for the three ER kinds). Mention this behaviour in the delivery record.
8. **Switch primary firm:** there is no `account` field. On contact edit: `.field[data-name=accounts] .list-group-item[data-id=<firm>]`, its `.dropdown-toggle`, `[data-action=setPrimary]`, save (verified administrator and ER Staff).

## C. Declarations: exact observed events
Each server refusal logs `Failed to load resource: the server responded with a status of 403 (Forbidden)` AND `Server side error 403: <message>`. The data stayed unchanged where read back.

| Action | Request | message | page error |
|---|---|---|---|
| record delete (firm, contact) | DELETE Account/{id}, Contact/{id} | `Identity records (firms, contacts and their audit history) are never deleted. Retire a firm or contact, or supersede it with a successor.` | `i` |
| contacts panel Remove | DELETE Contact/{id} | same | none seen (one observation) |
| contacts panel Unlink of primary | DELETE Account/{id}/contacts | `This firm is the contact's primary firm. Set another linked firm as primary, or clear the primary firm, before removing the link.` | `i` |
| list Remove (administrator) | POST MassAction | `Mass action 'delete' is disabled for 'Account'.` / `'Contact'.` | `i` |
| merge (`button[data-action=merge]`) | POST Action | `Action 'merge' is disabled for 'Account'.` / `'Contact'.` / `'Opportunity'.` | `i` |
| audit record Remove | DELETE IdentityAudit/{id} | the "never deleted" message above | `i` |
| audit record Edit, Save | PUT IdentityAudit/{id} | `Identity audit records cannot be changed.` | `error` |
| signed-in request, create user | POST User | `No create access.` | none |
| signed-in request, edit user | PUT User/{id} | `No edit access.` | none |

Client access denied logs `Espo.Exceptions.AccessDenied`, as already declared.

## D. What the base application does (expectations must say this; do not change application files; do not present these as met)
Section 3.3: "A combination the platform or role does not permit at the base is declared as such, not omitted."

Observed for the ER kinds, matching their declared J5 values: record delete not offered; lists offer no Remove or Merge on firms and contacts (Manager has Mass Update); enquiry list offers merge to Manager only (refused, message in the table) and not to Intake; Unlink of the primary firm offered and refused for all three; contacts-panel Remove not offered; audit record offers neither Edit nor Remove. ER Staff's contact and enquiry list menus were not looked at.

9. **Unlink primary firm:** declare the contacts-panel Unlink route (refused, verified for all four kinds), with the step itself setting which firm is primary (J4 changes it). On the contact **edit form**, removing the primary firm is accepted: the platform sets the other linked firm as primary in the same save, which the identity rule permits. Say so in the delivery record.
10. **List delete:** the administrator IS offered Remove on the firm and contact lists and the server refuses (section 3 of the order says delete is still offered). The declared "not offered" is wrong for the administrator. The ER kinds' declared values stand.
11. **No branches panel:** the firm page shows no branches related panel on any tab (seen as administrator and ER Staff), although a branch existed. The platform's `Crm/.../layouts/Account/bottomPanelsDetail.json` lists stream, contacts, opportunities, documents, cases; the repository supplies only `relationships.json`. J4 "see them on the related panels" cannot be met for a branch, nor J5 removal of a branch from a related panel. Declare it as its own step with a positive check (Account tab loaded, no branches panel, "not offered" for every kind), keep contact and enquiry panel checks, check the branch's parent on its screen and by API, and record it as an unmet base behaviour.
12. **Identity audit:** the administrator IS offered Edit and Remove; the server refuses both and the record is unchanged. The ER kinds are offered neither. The order's "identity audit records offer no edit or delete" is therefore not true at the base for the administrator: declare what happens (attempted, refused with a message, record unchanged, page usable), do not label it "not offered", and record it as a gap against that sentence for the Product Owner.

Items 9 to 12 go to the Product Owner. None justifies weakening a check.

## Binding approval terms (section 1b of the Orchestrator's approval record; they govern the Work Order text below)


> CRM-BROWSER-001 v1.1 — APPROVED
>
> Budget: at most three executions per role, subject to the approved cumulative limits.
>
> All five decisions in section 11 are approved, including the bundled Chromium, staged execution, verification assignments, narrowly defined error declarations and isolated provisioning.
>
> Proceed following successful integration and entry gates.
>
> Routine engineering decisions remain delegated.
>
> No further IDINT work, no beta deployment and no infrastructure expansion.


Draft or approval-pending wording in the Work Order file predates this approval and is superseded; it is not a finding. Budget: at most 3 executions per role; this is execution 3. Boundary, platform-fidelity paragraph (WO section 6) and host-safety rule (WO section 3.2 item 5) are binding and appear in the Work Order below.

## Test environment
- Unit suite from the worktree: CRM_PLATFORM_REFERENCE=/srv/CRM/wo/CRM-BROWSER-001/reference/espocrm PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests/unit  (set inline). PHP at /usr/bin/php. Current: 769 tests OK. Any skip fails the gate.
- The platform reference (/srv/CRM/wo/CRM-BROWSER-001/reference/espocrm: application/, vendor/, client/) is read-only GPL source. Never copy it into the worktree; never modify it.
- No network, Docker, browser or EspoCRM runtime for you. Do not install anything. State plainly what was not executed. For mutation checks, you may edit a file, run the tests, and restore it (e.g. with a copy kept in your allowed worktree area and removed afterwards); leave no scratch file.
- Leave no bytecode, cache or scratch file in the worktree. Repository is public: no credential, host address, personal, customer or firm data. No IP literals in new test files.
- A needed change outside WO section 4: report BLOCKED.

## Final report format
First line `STATUS: completed|blocked|failed`, then `UNFINISHED:` list (empty if none), host-executing files, test command and counts before/after, platform files relied on (by path), every changed existing test line, what was not executed.

## The Work Order (verbatim, governed by the approval terms above)

WO: CRM-BROWSER-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: abd1b04dd7d91f809ca3bf29fb29c15cf19c449a
KNOWN_COMMIT: abd1b04dd7d91f809ca3bf29fb29c15cf19c449a
BROWSER: yes

# CRM-BROWSER-001: repeatable real-browser assurance

## 1. Identity, purpose and authority

| Item | Value |
|---|---|
| Version | v1.1, 2026-11-27, for exact-version approval. Replaces v1.0 (never approved) and prepared text v0.3 (pull request 96) |
| Issue | https://github.com/infosec-estateresearch/CRM/issues/102 |
| Priority and parent item | P0. CRM-PBI-034, ERm journeys |
| Product outcome | A reliable, repeatable real-browser acceptance run on the pinned platform, covering creation, editing, search, relationships, identity integrity and permission enforcement, reusable for every later release |
| Direction | Architect delivery mission of 2026-11-27, outcome "browser assurance", relayed by the Product Owner; Issue #91; CRM-D045 |
| Governing FOUNDRY | `maff0000/foundry@39cc45c25aa5305b60f4c4af1557bee8cec0bf20`: `standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md` |
| Engine | ForgeV2 plugin 0.3.0, `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, at `/srv/forgev2`, unmodified |
| Assignment | The Orchestrator (Rogue) dispatches one Project Lead (`forgev2-pl`). Roles: Engineer, Auditor, Tester, DevSecOps |
| Delivery autonomy | This order fixes outcomes, the command contract, boundaries and budget. Design and routine corrections belong to the Project Lead and specialists |

## 2. Repository and workspace

| Item | Value |
|---|---|
| Base | the commit above: the candidate of CRM-IDINT-001R2. After the identity integration is merged, GitHub `main` differs from it only in documents, work orders and root product records, with no difference under `config/`, `custom/`, `client/`, `scripts/`, `tests/`, `load/` or `deploy/` |
| Branch and worktree | `forge/CRM-BROWSER-001`, `/srv/CRM/worktrees/CRM-BROWSER-001`, created by the engine |
| Platform reference | `/srv/CRM/wo/CRM-BROWSER-001/reference/espocrm/`, read-only, outside the repository, never committed; extracted from `/var/www/html` of the pinned application image. SHA-256 of the sorted file-hash list: `application/` `c06e7a4650db42d81f90ae2f02e8b5b75aea5631ef4a1fd51088ca9a21e1d187`; `vendor/` `8be4d761df69aa5e2ff408426906a72c08960301ff625c9c10f35876de3b28bb`; `client/` `63f1a941832f42663448645fb18375b2d1856b01d6899303327e8840f900b2de` (templates and, under `lib/`, bundles with source maps). **It is the authority for every platform name, route, setting and screen** |
| Earlier design | commit `895bbcd1003de71dbcb894f2195c1ae9f093a1f5`, `tests/browser/` (not merged). Its hash-locked offline install in a hardened container and its evidence checksums may be reused. Its verifier and isolation probe are tied to a removed release canary and old lab targets: do not port them |
| Protected | ForgeV2 and FOUNDRY installations; every existing ledger, branch, candidate and pull request; live runtimes |

## 3. Outcome and required behaviour

### 3.1 Command contract (binding, so the operator gate can run it)

| Command | Behaviour |
|---|---|
| `python3 scripts/browser_assurance.py run --out DIR [--journey ID]... [--fault NAME]` | `DIR` is absent or empty. Builds a disposable stack from the checkout the script is in, runs the journeys, writes evidence to `DIR`, removes everything it created. Exit 0 only if every step of every selected journey passed and nothing of the run remains |
| `python3 scripts/browser_assurance.py verify DIR --commit SHA` | Exit 0 only if the evidence is intact, complete for the full journey set, all passed, and made from commit `SHA` |

`NAME` is `broken-screen`, `wrong-expectation` or `killed-app`. The host needs only Docker with Compose and the Python 3.12 standard library; runner packages are fetched hash-checked and installed inside containers. If the checkout has uncommitted changes or no Git metadata, `run` still works, records the evidence as uncommitted, and `verify --commit` rejects it. A full run finishes within 40 minutes.

### 3.2 Stack and isolation

1. Own Compose project and names, unique per run (prefix `crm-browser-`); application and database images as pinned in `deploy/compose.json`; a network with no external route; no published host port is required. It never uses a name, network, volume, path or environment file of `crm-dev` or `crm-beta`.
2. The command accepts no target address. Before any journey the browser container proves that the application it reached is the stack this run created.
3. Containers, volumes, networks and runtime files of the run are removed after success, failure, `SIGINT` and `SIGTERM`.
4. The stack carries the repository's own `custom/` and `client/custom/`, the roles, teams and settings of `config/`, and the release settings. Synthetic data only. No product file changes.
5. **Host safety (binding).** The runner creates, changes and removes only resources carrying its own run's Compose project label, and its own run and output directories, identified by a marker it wrote. It never prunes, never removes by name pattern or image, and never touches another container, volume, network, image or path. It mounts no Docker socket, uses no privileged container or host network, and mounts no host path other than the repository (read-only) and its own run and output directories.

### 3.3 Journeys (minimum set, each as administrator, ER Staff, ER Intake and ER Manager)

| ID | Journey, through the screens |
|---|---|
| J1 create | a firm; a branch firm under a firm; a contact linked to a firm; an enquiry linked to a firm and a contact |
| J2 edit | one ordinary field on each, saved and read back |
| J3 search | find each by name from its list and open it |
| J4 relationships | set and change a branch's parent; link a second firm to a contact; switch the primary firm; change an enquiry's firm; see them on the related panels |
| J5 identity integrity | delete a firm and a contact (record, list mass action, related panel); merge firms, contacts and enquiries; unlink a contact's primary firm: each not offered or refused with a message, data unchanged, page usable. Identity audit records offer no edit or delete |
| J6 permissions | accounts that are not administrators cannot reach the administration area or import, or create or change another user, by menu, by direct address or by a direct API request from the signed-in session; the administrator can |

Account kinds and the expected result of each step per kind (`performed`, `not offered`, `refused`) are versioned data in `tests/browser/`, declared before a run; the runner never derives an expectation from what it observes. A later order must be able to change account kinds and expectations by editing that data. A combination the platform or role does not permit at the base is declared as such, not omitted.

### 3.4 Verdicts

A step passes only if the observed result equals the declared one, the stored data read back by API agrees, and no undeclared script error (uncaught error, unhandled rejection, console error) and no undeclared failed request (status 400 or higher) occurred. Only two things may be declared, per step and exactly:

1. **Refused by the server:** method and status of the refused request, with the platform's own rejection and console lines for that request. The step also proves the data unchanged and the page usable afterwards.
2. **Refused by the browser client:** the platform's access-denied log line when an account opens an area it may not open.

There is no global or pattern-wide error filter. A skipped, timed-out or unavailable step is not passed.

### 3.5 Evidence

A manifest records the commit (or uncommitted), image digests, package hashes, browser version, the journey list, per-step verdicts and the SHA-256 of every evidence file, with screenshots and the errors and requests of each step. No password, token, cookie, authorisation header or data other than synthetic fixtures. `verify` rejects a removed, changed, added or substituted file, another commit, a missing journey, step or account kind, and any step not passed.

### 3.6 Faults and documentation

Each fault makes `run` exit non-zero, naming the step that failed: `broken-screen` breaks a screen with client code placed only in the run's own stack; `wrong-expectation` alters one expectation for that run; `killed-app` stops the application during the journeys. None changes the repository. `docs/BUILD.md` says how to run, add a journey and declare an expectation.

## 3C. Platform facts (observed by the Orchestrator on the pinned image; verify against the reference)

- `deploy/apache/crm-access.conf` allows loopback and `CRM_ALLOWED_SOURCES` only: the run's network subnet must be listed or every request answers 403. Do not rely on the host reaching a container on an internal network: run setup and journeys from inside it.
- `scripts/provision_access.py`, `provision_users.py` and `seed_synthetic.py` refuse, as commands, any target but their fixed `dev` or `beta` addresses. This order permits the runner to import and call their functions against its own stack; the scripts and their command-line guards do not change.
- `scripts/deploy_custom.sh` copies `custom/Espo/Custom` and `client/custom/src` into the runtime and runs `php bin/command clear-cache` and `rebuild` as `www-data`; `scripts/deploy_release.sh` applies `config/release-settings.json` with `php bin/command config:set`.
- Entities: firm `Account`, contact `Contact`, enquiry `Opportunity`, identity audit `IdentityAudit`. Roles and teams: ER Staff / Enquiries, ER Intake / Ancillary intake, ER Manager / Firm management. An enquiry needs close date, amount and currency.
- Sign-in: `#field-userName`, `#field-password`, Enter; signed in when `#field-userName` has gone. Routes: `#<Entity>`, `#<Entity>/create`, `#<Entity>/view/<id>`, `#<Entity>/edit/<id>`.
- Record screen: ready at `.detail-button-container`; its `.dropdown-toggle`, then `[data-action=delete]`; confirm `.modal [data-name=confirm]`; save `button[data-action=save]`; fields `.field[data-name=<field>]`; link field input `input[data-name=<link>Name]`, choose from `.autocomplete-suggestion`.
- List: rows `tr[data-id]`; search `input[data-name=textFilter]` and Enter; select `input.record-checkbox`; `.actions-button`, then `a[data-action=remove|merge|massUpdate]`; merge screen `button[data-action=merge]`.
- Related panel: `.panel[data-name=<link>] [data-id='<id>'] .list-row-buttons .dropdown-toggle`, then `a[data-action=removeRelated|unlinkRelated]`; a panel may sit behind a tab. Messages appear in `.alert`, `#notification`, `.field.has-error`, `.modal-body`. Some selects are custom widgets: open them to read their options.
- A request the server refuses raises an unhandled rejection from the platform's request object (it carries the status), logs `Failed to load resource` and, where a reason is sent, `Server side error <status>: <reason>`. The stock platform does the same. Opening an area without access shows "You don't have access to this area" and logs `Espo.Exceptions.AccessDenied`.
- At the base the administrator is still offered delete and merge on firm and contact screens, and administrator and manager are offered enquiry merge; the server refuses them. CRM-ACC-001 is expected to hide them.

## 4. Delivery boundary

| | |
|---|---|
| In scope | `tests/browser/`, new files `scripts/browser_assurance*`, `tests/unit/`, `docs/BUILD.md`, `security/EXTERNAL_CODE_REGISTER.yaml` |
| Must not change | `custom/`, `client/`, `config/`, `deploy/`, `load/`, existing scripts, `.forge/` of other orders, `work-orders/`, root product records, EspoCRM core |
| Excluded | any product behaviour change; any WIP journey; the release canary of the earlier design; continuous integration set-up |
| Dependencies | runner image `mcr.microsoft.com/playwright/python` v1.65.1-noble, linux/amd64 manifest `sha256:ce84a3d75a47e81657d2ec2c0a949e6e0ef790abdc32ce6819220a3df987ff9a`, with its bundled Chromium 158.0.8127.18; packages `playwright==1.65.1` (`sha256:5660e0b050a5bd5672bf8e366ed2580288a3d3640ff9444436ed2d890d3dc442`) and `greenlet==3.5.6` (`sha256:975736b002ed080d124cf81a79cb7e05cb26d6b3f5c7a7b651c0fcce70353aa1`). Registered in the external code register. No other new dependency; no secret in the repository |
| Data and systems | synthetic data only. No beta, production, real data, off-host store or Salesforce access. No deployment or merge |

Existing tests change only where the new image and packages must be added to register expectations. Every changed existing test line is listed; the Auditor checks each. Nothing is removed or weakened.

## 5. Acceptance criteria

All are mandatory.

| AC | Criterion | Evidence |
|---|---|---|
| A1 | The full journey set passes **twice consecutively** on fresh stacks with identical per-step verdicts, each run within 40 minutes | operator report |
| A2 | Each of the three faults makes the run fail, for the intended step | operator report |
| A3 | Every journey J1 to J6 is declared and executed for all four account kinds | evidence manifest, review |
| A4 | An undeclared script error or failed request fails its step; declarations are per step and exact; a skipped or unavailable step is not passed | unit tests |
| A5 | `verify` rejects removed, changed, added and substituted evidence files, another commit and an incomplete set | unit tests, operator report |
| A6 | The command accepts no target, the run has no external route, and the target proof refuses a foreign application | unit tests; operator probe with a positive control |
| A7 | Evidence holds **0** credentials | operator report |
| A8 | After success, each fault and interruption: **0** containers, volumes and networks of the run remain, and no other resource on the host is changed. A unit test shows every container and file-removal command the runner can issue conforms to section 3.2 item 5 | unit tests; operator before-and-after inventory |
| A9 | Unit suite as non-root: **0 failures** (base: 720 tests with PHP and the platform reference, none skipped). New skips only for PHP, listed; the operator runs them with PHP present | delivery record, operator report |
| A10 | Every declared refusal is confirmed against the stock platform: the same refused flow on the pinned image with no ERm code raises the same error type and status, leaves data unchanged and the page usable | operator report |
| A11 | Secret scan: 0 findings; no credential, host address, personal, customer or firm data in the change | scan |
| A12 | On the same unchanged candidate: Auditor **PASS**, DevSecOps **PASS**, Tester **PASS**, or **INCONCLUSIVE solely for browser and live-runtime behaviour** with every sandbox-executable criterion passing | ledger |
| A13 | Operator proof (section 8) passes on that candidate | Orchestrator report |

## 6. Verification by role

| Role | Assigned verification |
|---|---|
| Engineer | implementation; automated tests for everything executable without a runtime; suite counts before and after |
| Auditor | conformance to sections 3 to 5, platform facts relied on checked in the reference, expectations data complete, no weakened assertion |
| Tester | every criterion executable in the sandbox, including mutations showing new tests fail when a control is removed; states what was not executed |
| DevSecOps | isolation, host safety (every command the runner can issue), target proof, teardown, evidence content, secrets, dependencies; no path from the runner to a live stack |

**Platform fidelity (binding).** Every platform interface, class, signature, metadata key, route, setting and screen element relied on is cited by file from the platform reference, and each reviewer checks it there. Test stand-ins declare no platform symbol that is absent from the reference, and match its signatures. Where server code is added or changed, a test loads every custom class against the reference with PHP and `CRM_PLATFORM_REFERENCE` set; the Engineer and Tester run it, and a skip is a blocking finding. A refusal is proven only by the control's own refusal on a route that exists.

The sandbox has no network, Docker, browser or EspoCRM. The Tester reports browser behaviour as inconclusive, never passed; a close **ESCALATED** solely for that is an intermediate result, never acceptance.

## 7. Execution, early feedback and stop conditions

- **Budget:** at most **3** executions each of Engineer, Auditor, Tester and DevSecOps; at most 4 per role including any separately approved corrective successor. A void run counts. Any Engineer change restarts the three reviews. Where the Tester is inconclusive the effective ceiling is two review rounds.
- **Engineer time limit (in every Engineer prompt):** the UTC dispatch time and a deadline 20 minutes later. The Engineer checks `date` between items; at the deadline it stops and reports `STATUS: completed` with an `UNFINISHED:` list, `blocked` only for a real blocker. The report is returned by minute 25.
- **Increment 1** (Engineer execution 1): command contract for `run`, stack, isolation, setup, teardown, target proof, runner container, J1 for all four kinds, evidence manifest.
- **Before each gate** the Orchestrator reads every file that would run on the lab host; a command outside section 3.2 item 5 fails the gate unrun.
- **Gate G1**, on the uncommitted work: the Orchestrator runs it on a disposable lab and returns a report.
- **Increment 2** (Engineer execution 2, before any commit): J2 to J6, faults, `verify`, unit tests, register, documentation, and G1 findings.
- **Gate G2**, on the uncommitted work: one full run, each fault on a journey subset, and `verify`. `PASS` with nothing unfinished: commit and review. Otherwise Engineer execution 3 completes before commit.
- **Waiting:** the Project Lead waits at most 75 minutes for the G1 file and 90 minutes for the G2 file. Engineer executions 2 and 3 are never dispatched before the preceding report exists. If a window passes without a report, the Project Lead stops dispatching Engineers, commits what exists and reviews it. Gate reports go to the Engineer only and replace no review or criterion.
- If execution 3 is used before commit, no Engineer correction remains for review findings: open findings are escalated.
- **BLOCKED and escalated:** an exhausted budget, a failed entry gate, a missing or altered reference, a needed change outside section 4, or a criterion that cannot be met safely.

## 8. Operator proof (no specialist executions)

On a disposable lab host separate from the application host, with the unchanged candidate: the documented command twice; each fault; interruption; the isolation probe with a positive control; `verify` against genuine and tampered evidence; teardown and credential checks; the stock-platform confirmation of A10; the unit suite with PHP; secret scan. The final candidate passes with no diagnostic bypass or patch.

## 9. Entry gates

| Gate | Requirement |
|---|---|
| E0 | CRM-IDINT-001R2 accepted and its integration merged into GitHub `main` |
| E1 | Exact-version approval: path, commit, file SHA-256, base, budget and the decisions of section 11 |
| E2 | Base resolves in the Project Lead repository; `forge-start` accepts it on a scratch copy; unit suite there: 0 failures |
| E3 | Engine and plugin as pinned; no `CRM-BROWSER-001` branch, worktree, ledger or record exists |
| E4 | Runner isolation established immediately before dispatch; a specialist can read the platform reference and cannot write it; digests match |
| E5 | No other open ledger or Project Lead session for this project |
| E6 | The order given to the Project Lead is read-only and byte-identical to the approved file |

## 10. Communications and completion

- **Issue:** #102. Progress is event driven (gates, dispatch, candidate, verdicts, close, blockers). Escalation: Project Lead to Orchestrator; Orchestrator to the Architect and the Product Owner.
- **Logs (writer: Project Lead):** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-BROWSER-001/`, published to `.forge/CRM-BROWSER-001/` on the branch. The repository is public: records carry no exploit detail, address, credential or personal, customer or firm data.
- **Completion report:** outcome, changed paths, base and candidate commits, A1 to A13, verdicts, execution counts, evidence locations, deviations, limitations. Output: candidate branch and draft pull request. Integration to `main` is a separate reviewed step.

## 11. Decisions the approval must state

1. Dispatch of this exact version with this budget.
2. The verification assignment of section 6 and the staged execution of section 7.
3. The dependencies of section 4, including use of the image's bundled Chromium. The superseded CRM-CLIENT-001R2 design excluded the bundled build and fetched a separate browser; this order uses the bundled one: one pinned artifact, test use only, no external route.
4. The two permitted error declarations of section 3.4, confirmed by A10.
5. The runner's use of the provisioning functions against its own stack (section 3C).
