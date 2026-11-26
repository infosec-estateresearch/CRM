WO: CRM-ACC-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: BOUND-AT-ENTRY
BROWSER: yes

# CRM-ACC-001: two user types, sign-in security and administrator user management

## 1. Identity, purpose and authority

| Item | Value |
|---|---|
| Version | v0.1 **PREPARED TEXT**, 2026-11-26. **Not approved. Cannot be dispatched:** the base is unbound. Dispatch needs a later version that names the base and its Issue, approved at that exact path and commit |
| Issue | https://github.com/infosec-estateresearch/CRM/issues/95 (package); this order's own Issue is opened when the base is bound |
| Priority and parent item | P0. CRM-PBI-036 |
| Product outcome | Staff can be given named access safely, and only administrators administer |
| Direction and decisions | Issue https://github.com/infosec-estateresearch/CRM/issues/91; CRM-D044, CRM-D049; `PROJECT-INITIATION-MANDATE.md` |
| Governing FOUNDRY | `maff0000/foundry@39cc45c25aa5305b60f4c4af1557bee8cec0bf20`: `standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md` |
| Engine | ForgeV2 plugin 0.3.0, `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, at `/srv/forgev2`, unmodified |
| Assignment | The Orchestrator (Rogue) dispatches one Project Lead (`forgev2-pl` on DOCKER1). Roles: Engineer, Auditor, Tester, DevSecOps |
| Delivery autonomy | This order fixes outcomes, acceptance, boundaries and budget. Design, order of work and routine corrections belong to the Project Lead and specialists |

## 2. Repository and workspace

| Item | Value |
|---|---|
| Base | Unbound. Predecessor: **CRM-BROWSER-001**. The base will be a commit held by the Project Lead repository that contains the predecessor's accepted result and differs from GitHub `main` only by documents and delivery records, proved by a compare |
| Branch and worktree | `forge/CRM-ACC-001`, `/srv/CRM/worktrees/CRM-ACC-001`, created by the engine |
| Execution host and route | `DOCKER1:/srv/CRM/main`; the Orchestrator runs on another host and starts the Project Lead on DOCKER1 over its established administrative route |
| Protected | ForgeV2 and Foundry installations; every existing ledger, branch, candidate and pull request; live runtimes; the checkout `ROOT` except as the engine itself writes it |

## 3. Outcome and required behaviour

Two human user types with equal ordinary business access; only administrators administer; sign-in meets the security baseline; administrators manage users and passwords with native screens.

1. Human accounts are native **Administrator** or one standard role, `ER User`, which replaces `ER Staff`, `ER Intake` and `ER Manager`. Service accounts stay separate, named and restricted; the import role is unchanged.
2. `ER User`: create, read and edit firms, contacts, enquiries and activities; no deletion of identity records; enquiries and activities soft-deleted with history; mass update excludes protected identity fields and relationships; **bulk export off** until CRM-AUDIT-001 proves export auditing; no user, role, configuration or reference-data administration.
3. An **Admin** section in the left navigation, visible only to native administrators, with exactly one entry, **Users**, with a user-management icon, navigating to `#Admin/users` as a relative route. Native extension mechanisms and styling; the existing navigation is unaffected. A standard user sees neither and is refused the route and the API.
4. Administrators create users and reset passwords in the native screens, using the native **Generate** control to obtain a strong temporary password they can view and copy. No stored password can be retrieved.
5. **Change required at next sign-in** after creation or reset. EspoCRM 10.0.12 has no native setting for this, so a supported extension enforces it **on the server**: until the user sets a new password, every request other than changing it and signing out is refused. Only the user's own successful change clears it.
6. A reset ends the user's earlier sessions (verify the native password-version behaviour and close any gap). Each administrator creation and reset is audited with actor, target and time, **never the password**.
7. Minimum password length 14, with the native strength settings applied.
8. A second factor is **enforced** for every human account including administrators, on every sign-in route: web sign-in, password and token use of the API, password recovery and access links. Enrolment alone does not count. Account recovery is documented and tested.
9. Tooling that signs in as a human administrator (provisioning, release and acceptance scripts) moves to a restricted service account with its own key, held outside Git.
10. Clients behind the proxy are seen with their own addresses, so one client cannot lock out another; only the trusted front end may state a client address.
11. Extension upload and impersonation are off. A configuration check fails when any setting of this order is changed.

## 4. Delivery boundary

|  |  |
|---|---|
| In scope | `custom/Espo/Custom/`, `client/custom/`, `config/`, `scripts/`, `deploy/beta/apache/`, `deploy/beta/edge/`, `tests/`, `docs/` |
| Must not change | `.forge/` of other orders unless the scope row names them, `work-orders/`, root product records, EspoCRM core |
| Excluded | FirmGroup permissions beyond reserving them for both user types; logging beyond the audit named here; e-mail delivery of passwords (the native generate-and-send route needs a mail server and is not used); any change to a running environment |
| Dependencies and constraints | no new package, image, extension or vendored file; supported EspoCRM extension points only; no secret in the repository |
| Data and systems | synthetic data only. No beta, production, real data, off-host store or Salesforce access. No deployment or merge. No WIP change (on hold) |

### Existing behaviour this order supersedes
Only the following existing expectations change. Another existing assertion may change only where it contradicts a criterion in section 5, and then it is extended or replaced with an equally strict one. Every changed existing test line is listed; the Auditor checks each. Nothing else is removed or weakened:

1. The three business roles and their expected levels (`config/access/roles.json`, `tests/unit/access_policy.py`, fixtures, `docs/ACCESS.md`) are replaced by `ER User`.
2. The shared temporary password option (`provision_users.py --common-password-file`) and its documentation are removed.
3. Acceptance suites and scripts that sign in with a human administrator password use the service account; staff journeys include the second factor and the forced change.

## 5. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| A1 | Permission matrix for both types, by API and browser: **100 %** as specified; every escalation attempt refused | suite, operator browser run |
| A2 | Standard user: Admin section absent; `#Admin/users` and the user administration API refused; administrator: entry works after refresh and under a different host name | operator browser run |
| A3 | After creation or reset the user can do nothing but change the password or sign out, through every route; after the change the restriction is gone | suite |
| A4 | Earlier sessions are refused after a reset | suite |
| A5 | A generated password appears **0** times in logs, audit records and database text | suite check on the disposable runtime |
| A6 | Each sign-in route without the second factor is refused for each human account kind | route suite |
| A7 | Passwords under 14 characters refused on every setting route | suite |
| A8 | Two client addresses behind the proxy are recorded as different, a forged address header from another source is ignored, and lock-out of one leaves the other working | operator report |
| A9 | The configuration check fails on each deliberate change | unit tests, operator report |
| A10 | Every test suite present at the base, run as a non-root user as documented in the repository: **0 failures**. The only new skips allowed are tests needing PHP, gated like existing ones, each listed; the operator proof runs them with PHP present, none skipped for lack of PHP | delivery record, operator report |
| A11 | On the same unchanged candidate commit: Auditor **PASS**, DevSecOps **PASS**, and Tester **PASS**, or **INCONCLUSIVE solely for browser and live-runtime behaviour** with every sandbox-executable criterion passing | ledger |
| A12 | Operator proof (section 8) passes on that unchanged candidate | Orchestrator report |
| A13 | Secret scan: 0 findings; no credential, host address, personal, customer or firm data in the change | scan |

The order is complete only when A1 to A13 hold. A closed ledger alone is not acceptance.

## 6. Verification by role

| Role | Assigned verification and evidence |
|---|---|
| Engineer | implementation; automated tests for every criterion executable without a runtime; scripts for the runtime criteria that the operator proof runs; suite counts before and after; every changed existing test line listed |
| Auditor | conformance to this order and section 4; superseded expectations limited to the list; no weakened assertion. PASS or FINDINGS with the candidate commit |
| Tester | every criterion executable in the sandbox, including mutations showing new tests fail when a control is removed; states what was **not** executed. PASS, FINDINGS, or INCONCLUSIVE solely for browser and live-runtime behaviour |
| DevSecOps | authentication and authorisation bypass review of every route, including the forced-change extension and the service account; secrets, dependencies and secret scan. PASS or FINDINGS |

**Browser gate.** The sandbox has no network, Docker, browser or EspoCRM, and PHP is not assumed. Under the engine's browser gate the Tester reports browser behaviour `inconclusive`, never as passed, and, when everything else passes, the Project Lead closes the ledger **ESCALATED** with that reason without a further Tester execution. Under CRM-D013 this is an acceptable intermediate result and **never final acceptance**: that needs section 8. Approval of this order approves this assignment.

## 7. Budget and stop conditions

- At most **3** executions each for Engineer, Auditor, Tester and DevSecOps. Any Engineer change restarts the three reviews. **Effective ceiling: two review rounds**, because the engine closes a ledger when one reviewer is inconclusive twice in a row, so a second round can end ESCALATED with findings open.
- A corrective successor, if later needed, is a separate Work Order whose exact text is approved before dispatch; **at most 4 executions per role across both**.
- **BLOCKED and escalated:** an exhausted budget, a failed gate, a needed change outside section 4, or a criterion that cannot be met safely.

## 8. Operator proof (no specialist executions)

On a disposable runtime of the pinned images (own project name, internal network, synthetic data only), with the unchanged candidate: deploy with the real release scripts; run the suites; run the browser journeys for both user types, including creation, copy of a generated password, forced change, reset and second factor. Evidence holds no credential or personal data.

## 9. Entry gates

| Gate | Requirement |
|---|---|
| E0 | Predecessor accepted and its result on GitHub `main` |
| E1 | Exact-version approval: path, commit, file SHA-256, bound base, budget, and the decisions of section 11 |
| E2 | Base resolves in the Project Lead repository and satisfies section 2; `forge-start` accepts it, proved on a scratch copy |
| E3 | Engine and plugin as pinned; no `CRM-ACC-001` branch, worktree, ledger or record exists |
| E4 | Runner isolation established for this engine immediately before dispatch: hardened mount and PID namespace launcher, clean environment, in-context denial of sensitive paths, positive control and process sentinel; execution identity and CLI version recorded. Any adverse result blocks dispatch |
| E5 | No other open ledger or Project Lead session for this project; coordinated with other users of the engine |
| E6 | The order given to the Project Lead is read-only and byte-identical to the approved file |
| E7 | Size check: if the Project Lead judges the outcome cannot fit the budget, it stops before Engineer dispatch and proposes a split |

## 10. Communications and completion

- **Issue:** this order's Issue (named at base binding). Progress is event driven (gates, dispatch, candidate, verdicts, close, blockers). Escalation: Project Lead to Orchestrator; Orchestrator to the Architect (architecture, scope) and the Product Owner (product, permission, material risk).
- **Logs (writer: Project Lead; readers: Orchestrator, Architect):** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-ACC-001/` with `prompts/` and per-role `dispatch/` output; published to `.forge/CRM-ACC-001/` on the branch.
- **Completion report:** outcome, changed paths, base and candidate commits, acceptance results, the three verdicts and the candidate each assessed, execution counts, evidence locations, deviations, limitations and residual risks. The output is a candidate branch and draft pull request.

## 11. Decisions the approval must state

1. Dispatch of the exact bound version, with this budget.
2. The superseded expectations of section 4 and the verification assignment of section 6.
3. The three business roles become one.
4. A supported server extension for the forced password change.
5. Which second factor method staff use (native authenticator app proposed).
6. A restricted service account for release and provisioning tooling.
