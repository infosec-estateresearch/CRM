WO: CRM-MAIL-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: BOUND-AT-ENTRY
BROWSER: yes

# CRM-MAIL-001: file a chosen Outlook email to an enquiry

## 1. Identity, purpose and authority

| Item | Value |
|---|---|
| Version | v0.1 **PREPARED TEXT**, 2026-11-26. **Not approved. Cannot be dispatched:** the base is unbound. Dispatch needs a later version that names the base and its Issue, approved at that exact path and commit |
| Issue | https://github.com/infosec-estateresearch/CRM/issues/95 (package); this order's own Issue is opened when the base is bound |
| Priority and parent item | P0 (cutover requirement). CRM-PBI-006 and CRM-PBI-014 |
| Product outcome | Staff can file a chosen email against an enquiry in ERm, so that Salesforce is no longer needed for filing |
| Direction and decisions | Issue https://github.com/infosec-estateresearch/CRM/issues/91; CRM-D005, CRM-D016, CRM-D054, CRM-D061; requirement R10; `PROJECT-INITIATION-MANDATE.md`. Decisions CRM-D044 to D062, `docs/IDENTITY.md` and `docs/LOGGING.md` are on pull request 94 until merged |
| Governing FOUNDRY | `maff0000/foundry@39cc45c25aa5305b60f4c4af1557bee8cec0bf20`: `standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md` |
| Engine | ForgeV2 plugin 0.3.0, `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, at `/srv/forgev2`, unmodified |
| Assignment | The Orchestrator (Rogue) dispatches one Project Lead (`forgev2-pl` on DOCKER1). Roles: Engineer, Auditor, Tester, DevSecOps |
| Delivery autonomy | This order fixes outcomes, acceptance, boundaries and budget. Design, order of work and routine corrections belong to the Project Lead and specialists |

## 2. Repository and workspace

| Item | Value |
|---|---|
| Base | Unbound. Predecessor: **CRM-AUDIT-001 (named users with a second factor, and audit)**. The base will be a commit held by the Project Lead repository that contains the predecessor's accepted result and differs from GitHub `main` only by documents and delivery records, proved by a compare |
| Branch and worktree | `forge/CRM-MAIL-001`, `/srv/CRM/worktrees/CRM-MAIL-001`, created by the engine |
| Execution host and route | `DOCKER1:/srv/CRM/main`; the Orchestrator runs on another host and starts the Project Lead on DOCKER1 over its established administrative route |
| Protected | ForgeV2 and Foundry installations; every existing ledger, branch, candidate and pull request; live runtimes; the checkout `ROOT` except as the engine itself writes it |

## 3. Outcome and required behaviour

A staff member chooses one email in Outlook, chooses an enquiry, and files it: ERm holds it once, as that person's audited action, through an Estate Research owned filing service that does not tie the Outlook side to this CRM's internals.

1. An Outlook task pane lets the signed-in staff member search the enquiries they may see, choose one and file the open message.
2. The message is stored as an archived Email linked to the enquiry, with sender, To and Cc recipients, subject, sent time, message identifier and the plain-text body. Attachment **names** are listed; attachment content is not stored (CRM-D005). Archived history stays read-only as today.
3. De-duplication is by Message-ID: filing an already filed message creates **no second record**; the user is told where it is filed. Moving it to another enquiry is a separate, explicit, permitted and audited action.
4. Unknown senders and recipients are accepted. No firm or contact is created or changed by filing.
5. Filing happens as a named ERm user, with that user's permissions. There is no anonymous access and no shared human credential. Any service credential is held on the server, outside Git, with the least privilege that works.
6. Only the message the user chose is read. No mailbox synchronisation, scanning, sending or automatic filing. Microsoft 365 permissions requested are the minimum and are listed.
7. Each filing and each refusal is audited with actor, time, message identifier and enquiry. Message bodies, addresses beyond what audit needs, tokens and secrets are never logged.
8. Oversized, malformed or hostile content is refused or stored inert; message content is never executed or rendered as active markup. A failure leaves no partial record, is shown to the user and can be retried safely.
9. The task pane and service are used over trusted HTTPS only.

## 4. Delivery boundary

|  |  |
|---|---|
| In scope | `mail/` (new: filing service and task pane), `custom/Espo/Custom/`, `config/`, `deploy/`, `scripts/`, `tests/`, `docs/` |
| Must not change | `.forge/` of other orders unless the scope row names them, `work-orders/`, root product records, EspoCRM core |
| Excluded | sending or receiving e-mail; mailbox synchronisation; attachment content; automatic or bulk filing; import of historic Salesforce e-mail (migration orders); deployment to staff mailboxes or to a running environment |
| Dependencies and constraints | a filing service runtime and the Outlook add-in library are new dependencies: each is named and pinned in the bound version and approved there; no other third-party or installable extension; custom CRM code at supported EspoCRM extension points only; no secret in the repository |
| Data and systems | synthetic data only, including a test mailbox that holds synthetic messages. No beta, production, real data, staff mailbox or Salesforce access. No deployment or merge. No WIP change (on hold) |

### Existing behaviour this order supersedes
Only the following existing expectations change. Another existing assertion may change only where it contradicts a criterion in section 5, and then it is extended or replaced with an equally strict one. Every changed existing test line is listed; the Auditor checks each. Nothing else is removed or weakened:

1. The release image-set and unit expectations are extended to the filing service, with equally strict assertions.
2. The statement that there is no email filing (`docs/ACTIVITIES.md`) is replaced by the filing route; there is still no sending or inbound mail.

## 5. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| A1 | A chosen message is filed to a chosen enquiry with every listed field equal to the source; attachment content stored: **0** | suite with synthetic messages, operator Outlook journey |
| A2 | The same message filed again, also concurrently, yields exactly **1** record and tells the user where it is | suite |
| A3 | Filing and search respect the user's permissions; anonymous, expired, forged and other-user requests are refused | route suite |
| A4 | Unknown addresses are accepted; firm and contact records created or changed by filing: **0** | suite |
| A5 | Requested mailbox permissions equal the approved list; the service reads no message other than the chosen one | manifest check, operator journey |
| A6 | Audit record present for each filing and refusal; body text and secrets in logs and audit: **0** | suite with sentinel content |
| A7 | Oversized, malformed and hostile inputs are refused or stored inert; an induced failure leaves no partial record and a retry succeeds | suite |
| A8 | The service and task pane refuse plain HTTP | suite, operator report |
| A9 | Every test suite present at the base, run as a non-root user as documented in the repository: **0 failures**. The only new skips allowed are tests needing PHP, gated like existing ones, each listed; the operator proof runs them with PHP present, none skipped for lack of PHP | delivery record, operator report |
| A10 | On the same unchanged candidate commit: Auditor **PASS**, DevSecOps **PASS**, and Tester **PASS**, or **INCONCLUSIVE solely for browser and live-runtime behaviour** with every sandbox-executable criterion passing | ledger |
| A11 | Operator proof (section 8) passes on that unchanged candidate | Orchestrator report |
| A12 | Secret scan: 0 findings; no credential, host address, personal, customer or firm data in the change | scan |

The order is complete only when A1 to A12 hold. A closed ledger alone is not acceptance.

## 6. Verification by role

| Role | Assigned verification and evidence |
|---|---|
| Engineer | implementation; automated tests for every criterion executable without a runtime; scripts for the runtime criteria that the operator proof runs; suite counts before and after; every changed existing test line listed |
| Auditor | conformance to this order and section 4; superseded expectations limited to the list; no weakened assertion. PASS or FINDINGS with the candidate commit |
| Tester | every criterion executable in the sandbox, including mutations showing new tests fail when a control is removed; states what was **not** executed. PASS, FINDINGS, or INCONCLUSIVE solely for browser and live-runtime behaviour |
| DevSecOps | authentication of the add-in and service, token handling, content handling and permission scope; network exposure of the new service; secrets, dependencies and secret scan. PASS or FINDINGS |

**Browser gate.** The sandbox has no network, Docker, browser or EspoCRM, and PHP is not assumed. Under the engine's browser gate the Tester reports browser behaviour `inconclusive`, never as passed, and, when everything else passes, the Project Lead closes the ledger **ESCALATED** with that reason without a further Tester execution. Under CRM-D013 this is an acceptable intermediate result and **never final acceptance**: that needs section 8. Approval of this order approves this assignment.

## 7. Budget and stop conditions

- At most **3** executions each for Engineer, Auditor, Tester and DevSecOps. Any Engineer change restarts the three reviews. **Where the Tester reports inconclusive, the effective ceiling is two review rounds**, because the engine closes a ledger when one reviewer is inconclusive twice in a row, so a second round can end ESCALATED with findings open.
- A corrective successor, if later needed, is a separate Work Order whose exact text is approved before dispatch; **at most 4 executions per role across both**.
- **BLOCKED and escalated:** an exhausted budget, a failed gate, a needed change outside section 4, or a criterion that cannot be met safely.

## 8. Operator proof (no specialist executions)

On a disposable runtime of the pinned images (own project name, internal network, synthetic data only), with the unchanged candidate: run the filing service and CRM with synthetic messages through the suites; then, outside that internal network and only as approved under section 11, run the journey in Outlook with the test mailbox against a synthetic runtime over the approved test endpoint, including filing, repeat filing and a refused user. Evidence holds no credential or personal data.

## 9. Entry gates

| Gate | Requirement |
|---|---|
| E0 | Predecessor accepted and its result on GitHub `main`, together with the decision, identity and logging records of pull request 94 |
| E1 | Exact-version approval: path, commit, file SHA-256, bound base, budget, and the decisions of section 11 |
| E2 | Base resolves in the Project Lead repository and satisfies section 2; `forge-start` accepts it, proved on a scratch copy |
| E3 | Engine and plugin as pinned; no `CRM-MAIL-001` branch, worktree, ledger or record exists |
| E4 | Runner isolation established for this engine immediately before dispatch: hardened mount and PID namespace launcher, clean environment, in-context denial of sensitive paths, positive control and process sentinel; execution identity and CLI version recorded. Any adverse result blocks dispatch |
| E5 | No other open ledger or Project Lead session for this project; coordinated with other users of the engine |
| E6 | The order given to the Project Lead is read-only and byte-identical to the approved file |
| E7 | The Product Owner has provided a test mailbox with synthetic content, a Microsoft 365 app registration and a trusted HTTPS test endpoint reachable by that Outlook client |
| E8 | Size check: if the Project Lead judges the outcome cannot fit the budget, it stops before Engineer dispatch and proposes a split (filing service and test-mailbox journey first, production readiness second) |

## 10. Communications and completion

- **Issue:** this order's Issue (named at base binding). Progress is event driven (gates, dispatch, candidate, verdicts, close, blockers). Escalation: Project Lead to Orchestrator; Orchestrator to the Architect (architecture, scope) and the Product Owner (product, permission, material risk).
- **Logs (writer: Project Lead; readers: Orchestrator, Architect):** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-MAIL-001/` with `prompts/` and per-role `dispatch/` output; published to `.forge/CRM-MAIL-001/` on the branch.
- **Completion report:** outcome, changed paths, base and candidate commits, acceptance results, the three verdicts and the candidate each assessed, execution counts, evidence locations, deviations, limitations and residual risks. The output is a candidate branch and draft pull request.

## 11. Decisions the approval must state

1. Dispatch, with this budget, of the later version that binds the base. This item cannot be given to this prepared text.
2. The superseded expectations of section 4 and the verification assignment of section 6.
3. The new runtime image and libraries.
4. How the task pane authenticates a staff member to ERm.
5. The Microsoft 365 permissions requested, the app registration and who consents.
6. The test endpoint used for the Outlook journey.
