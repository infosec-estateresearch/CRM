WO: CRM-BROWSER-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: BOUND-AT-ENTRY
BROWSER: yes

# CRM-BROWSER-001: repeatable real-browser assurance

## 1. Identity, purpose and authority

| Item | Value |
|---|---|
| Version | v0.1 **PREPARED TEXT**, 2026-11-26. **Not approved. Cannot be dispatched:** the base is unbound. Dispatch needs a later version that names the base and its Issue, approved at that exact path and commit |
| Issue | https://github.com/infosec-estateresearch/CRM/issues/95 (package); this order's own Issue is opened when the base is bound |
| Priority and parent item | P0. CRM-PBI-034, re-scoped to ERm journeys |
| Product outcome | Any later order can obtain repeatable real-browser evidence against synthetic data |
| Direction and decisions | Issue https://github.com/infosec-estateresearch/CRM/issues/91; CRM-D045; C-4 (CRM-CLIENT-001R2 superseded as a lane, its runner design reused); `PROJECT-INITIATION-MANDATE.md` |
| Governing FOUNDRY | `maff0000/foundry@39cc45c25aa5305b60f4c4af1557bee8cec0bf20`: `standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md` |
| Engine | ForgeV2 plugin 0.3.0, `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, at `/srv/forgev2`, unmodified |
| Assignment | The Orchestrator (Rogue) dispatches one Project Lead (`forgev2-pl` on DOCKER1). Roles: Engineer, Auditor, Tester, DevSecOps |
| Delivery autonomy | This order fixes outcomes, acceptance, boundaries and budget. Design, order of work and routine corrections belong to the Project Lead and specialists |

## 2. Repository and workspace

| Item | Value |
|---|---|
| Base | Unbound. Predecessor: **CRM-IDINT-001 (its scope-guard repair and identity screens)**. The base will be a commit held by the Project Lead repository that contains the predecessor's accepted result and differs from GitHub `main` only by documents and delivery records, proved by a compare |
| Branch and worktree | `forge/CRM-BROWSER-001`, `/srv/CRM/worktrees/CRM-BROWSER-001`, created by the engine |
| Execution host and route | `DOCKER1:/srv/CRM/main`; the Orchestrator runs on another host and starts the Project Lead on DOCKER1 over its established administrative route |
| Protected | ForgeV2 and Foundry installations; every existing ledger, branch, candidate and pull request; live runtimes; the checkout `ROOT` except as the engine itself writes it |

## 3. Outcome and required behaviour

A published, repeatable way to run real-browser journeys against a disposable synthetic ERm, whose evidence can be trusted and checked by someone who did not run it.

1. One documented command starts a disposable synthetic stack, runs the journeys in a pinned browser image, collects evidence and removes everything it created.
2. Journeys sign in as each human account kind present at the base and exercise firm, contact and enquiry screens, including the identity behaviour delivered by CRM-IDINT-001.
3. The runner has no route to the internet, to beta or to production, and refuses any target that is not its own disposable stack.
4. The evidence package records candidate commit, image digests, journey list, per-step verdicts and checksums; a separate verifier rejects missing, altered or foreign evidence.
5. Evidence holds no password, token, cookie or record data other than synthetic fixtures.
6. A failed, skipped or unavailable step is reported as not passed.
7. The design of `tests/browser/` on the CRM-CLIENT-001R2 candidate (`895bbcd1003de71dbcb894f2195c1ae9f093a1f5`, pull request 69) is reused where it fits; that candidate is not merged.

## 4. Delivery boundary

|  |  |
|---|---|
| In scope | `tests/browser/`, runner scripts under `scripts/`, `tests/unit/`, `docs/BUILD.md`, `security/EXTERNAL_CODE_REGISTER.yaml` |
| Must not change | `.forge/` of other orders unless the scope row names them, `work-orders/`, root product records, EspoCRM core, `custom/`, `client/custom/`, `deploy/` release content |
| Excluded | client asset delivery (already on `main`); the release canary of the superseded candidate; any product behaviour change; any WIP journey |
| Dependencies and constraints | one pinned browser runner image (by digest) and a hash-locked set of runner packages, both registered in the external code register and named at base binding. No other new dependency; no secret in the repository |
| Data and systems | synthetic data only. No beta, production, real data, off-host store or Salesforce access. No deployment or merge. No WIP change (on hold) |

### Existing behaviour this order supersedes
Only the following existing expectations change. Another existing assertion may change only where it contradicts a criterion in section 5, and then it is extended or replaced with an equally strict one. Every changed existing test line is listed; the Auditor checks each. Nothing else is removed or weakened:

1. The repository gains a registered runner image and runner packages; register expectations in unit tests are extended to include them.

## 5. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| A1 | One published journey set passes **twice consecutively** on a fresh stack with identical verdicts | operator report |
| A2 | Each of: a deliberately broken screen, a wrong expected value and a killed application makes the run **fail** | operator report; unit tests for the verifier |
| A3 | The verifier rejects removed, changed and substituted evidence files | unit tests |
| A4 | The runner refuses a non-disposable target and has no external route | unit tests; operator probe with a positive control |
| A5 | Pattern and secret check over the evidence finds **0** credentials | operator report |
| A6 | After success, failure and interruption: **0** containers, volumes and networks of the run remain | operator report |
| A7 | Every test suite present at the base, run as a non-root user as documented in the repository: **0 failures**. The only new skips allowed are tests needing PHP, gated like existing ones, each listed; the operator proof runs them with PHP present, none skipped for lack of PHP | delivery record, operator report |
| A8 | On the same unchanged candidate commit: Auditor **PASS**, DevSecOps **PASS**, and Tester **PASS**, or **INCONCLUSIVE solely for browser and live-runtime behaviour** with every sandbox-executable criterion passing | ledger |
| A9 | Operator proof (section 8) passes on that unchanged candidate | Orchestrator report |
| A10 | Secret scan: 0 findings; no credential, host address, personal, customer or firm data in the change | scan |

The order is complete only when A1 to A10 hold. A closed ledger alone is not acceptance.

## 6. Verification by role

| Role | Assigned verification and evidence |
|---|---|
| Engineer | implementation; automated tests for every criterion executable without a runtime; scripts for the runtime criteria that the operator proof runs; suite counts before and after; every changed existing test line listed |
| Auditor | conformance to this order and section 4; superseded expectations limited to the list; no weakened assertion. PASS or FINDINGS with the candidate commit |
| Tester | every criterion executable in the sandbox, including mutations showing new tests fail when a control is removed; states what was **not** executed. PASS, FINDINGS, or INCONCLUSIVE solely for browser and live-runtime behaviour |
| DevSecOps | authorisation and bypass review of every server change; secrets, dependencies and secret scan. PASS or FINDINGS |

**Browser gate.** The sandbox has no network, Docker, browser or EspoCRM, and PHP is not assumed. Under the engine's browser gate the Tester reports browser behaviour `inconclusive`, never as passed, and, when everything else passes, the Project Lead closes the ledger **ESCALATED** with that reason without a further Tester execution. Under CRM-D013 this is an acceptable intermediate result and **never final acceptance**: that needs section 8. Approval of this order approves this assignment.

## 7. Budget and stop conditions

- At most **3** executions each for Engineer, Auditor, Tester and DevSecOps. Any Engineer change restarts the three reviews. **Effective ceiling: two review rounds**, because the engine closes a ledger when one reviewer is inconclusive twice in a row, so a second round can end ESCALATED with findings open.
- A corrective successor, if later needed, is a separate Work Order whose exact text is approved before dispatch; **at most 4 executions per role across both**.
- **BLOCKED and escalated:** an exhausted budget, a failed gate, a needed change outside section 4, or a criterion that cannot be met safely.

## 8. Operator proof (no specialist executions)

On a disposable runtime of the pinned images (own project name, internal network, synthetic data only), with the unchanged candidate: run the documented command twice, then each fault case, the isolation probe, the evidence checks and the teardown checks. Evidence holds no credential or personal data.

## 9. Entry gates

| Gate | Requirement |
|---|---|
| E0 | Predecessor accepted and its result on GitHub `main` |
| E1 | Exact-version approval: path, commit, file SHA-256, bound base, budget, and the decisions of section 11 |
| E2 | Base resolves in the Project Lead repository and satisfies section 2; `forge-start` accepts it, proved on a scratch copy |
| E3 | Engine and plugin as pinned; no `CRM-BROWSER-001` branch, worktree, ledger or record exists |
| E4 | Runner isolation established for this engine immediately before dispatch: hardened mount and PID namespace launcher, clean environment, in-context denial of sensitive paths, positive control and process sentinel; execution identity and CLI version recorded. Any adverse result blocks dispatch |
| E5 | No other open ledger or Project Lead session for this project; coordinated with other users of the engine |
| E6 | The order given to the Project Lead is read-only and byte-identical to the approved file |

## 10. Communications and completion

- **Issue:** this order's Issue (named at base binding). Progress is event driven (gates, dispatch, candidate, verdicts, close, blockers). Escalation: Project Lead to Orchestrator; Orchestrator to the Architect (architecture, scope) and the Product Owner (product, permission, material risk).
- **Logs (writer: Project Lead; readers: Orchestrator, Architect):** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-BROWSER-001/` with `prompts/` and per-role `dispatch/` output; published to `.forge/CRM-BROWSER-001/` on the branch.
- **Completion report:** outcome, changed paths, base and candidate commits, acceptance results, the three verdicts and the candidate each assessed, execution counts, evidence locations, deviations, limitations and residual risks. The output is a candidate branch and draft pull request.

## 11. Decisions the approval must state

1. Dispatch of the exact bound version, with this budget.
2. The superseded expectations of section 4 and the verification assignment of section 6.
3. The runner image digest and package lock as approved dependencies (named in the bound version).
