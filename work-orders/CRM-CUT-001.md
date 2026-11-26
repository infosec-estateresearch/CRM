WO: CRM-CUT-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: BOUND-AT-ENTRY

# CRM-CUT-001: production target and cutover readiness

## 1. Identity, purpose and authority

| Item | Value |
|---|---|
| Version | v0.1 **PREPARED TEXT**, 2026-11-26. **Not approved. Cannot be dispatched:** the base is unbound. Dispatch needs a later version that names the base and its Issue, approved at that exact path and commit |
| Issue | https://github.com/infosec-estateresearch/CRM/issues/95 (package); this order's own Issue is opened when the base is bound |
| Priority and parent item | P1. CRM-PBI-042 |
| Product outcome | Production ERm can be created from verified beta data with identifiers unchanged, rehearsed and reversible |
| Direction and decisions | Issue https://github.com/infosec-estateresearch/CRM/issues/91; CRM-D046, CRM-D052, CRM-D054, CRM-D016; `PROJECT-INITIATION-MANDATE.md` |
| Governing FOUNDRY | `maff0000/foundry@39cc45c25aa5305b60f4c4af1557bee8cec0bf20`: `standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md` |
| Engine | ForgeV2 plugin 0.3.0, `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, at `/srv/forgev2`, unmodified |
| Assignment | The Orchestrator (Rogue) dispatches one Project Lead (`forgev2-pl` on DOCKER1). Roles: Engineer, Auditor, Tester, DevSecOps |
| Delivery autonomy | This order fixes outcomes, acceptance, boundaries and budget. Design, order of work and routine corrections belong to the Project Lead and specialists |

## 2. Repository and workspace

| Item | Value |
|---|---|
| Base | Unbound. Predecessor: **CRM-LOAD-001; Outlook filing (CRM-PBI-014) before cutover unless the Product Owner defers it**. The base will be a commit held by the Project Lead repository that contains the predecessor's accepted result and differs from GitHub `main` only by documents and delivery records, proved by a compare |
| Branch and worktree | `forge/CRM-CUT-001`, `/srv/CRM/worktrees/CRM-CUT-001`, created by the engine |
| Execution host and route | `DOCKER1:/srv/CRM/main`; the Orchestrator runs on another host and starts the Project Lead on DOCKER1 over its established administrative route |
| Protected | ForgeV2 and Foundry installations; every existing ledger, branch, candidate and pull request; live runtimes; the checkout `ROOT` except as the engine itself writes it |

## 3. Outcome and required behaviour

Release tooling supports a production target, and promotion of a verified beta-derived database into it is rehearsed, reconciled and reversible. **This order does not authorise cutover.**

1. The release tooling gains an explicit production target with its own runtime, secrets, settings and guards; it cannot be mistaken for, or overwrite, beta.
2. Promotion restores a verified beta backup into the prepared production runtime preserving identifiers and relationships and staff changes.
3. After promotion there are no live sessions or carried-over tokens, every credential is replaced, and environment settings are production's.
4. Reconciliation explains every difference. Rollback criteria and steps are rehearsed.
5. The identity start date procedure is defined: consumers already holding beta identifiers are confirmed, test records are dealt with by a recorded decision before that date, and the register starts from it.
6. A cutover checklist states every prerequisite and owner, including e-mail filing, final source delta, backup, monitoring and sign-off.

## 4. Delivery boundary

|  |  |
|---|---|
| In scope | `scripts/`, `deploy/`, `tests/`, `docs/` |
| Must not change | `.forge/` of other orders unless the scope row names them, `work-orders/`, root product records, EspoCRM core, `custom/` behaviour |
| Excluded | performing cutover; creating real production data; DNS, certificate or proxy changes |
| Dependencies and constraints | no new package, image, extension or vendored file; supported EspoCRM extension points only; no secret in the repository |
| Data and systems | synthetic data only. No beta, production, real data, off-host store or Salesforce access. No deployment or merge. No WIP change (on hold) |

### Existing behaviour this order supersedes
Only the following existing expectations change. Another existing assertion may change only where it contradicts a criterion in section 5, and then it is extended or replaced with an equally strict one. Every changed existing test line is listed; the Auditor checks each. Nothing else is removed or weakened:

1. Tooling expectations that only development and beta targets exist are extended to production with equally strict guards.

## 5. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| A1 | Synthetic rehearsal: identity digests equal between source and promoted production | operator report |
| A2 | **0** sessions and carried tokens; every credential differs from the source | suite, operator report |
| A3 | Reconciliation: **0** unexplained differences | operator report |
| A4 | Rollback demonstrated | operator report |
| A5 | Each guard refuses a wrong target, a beta path and an unverified backup | unit tests |
| A6 | Every test suite present at the base, run as a non-root user as documented in the repository: **0 failures**. The only new skips allowed are tests needing PHP, gated like existing ones, each listed; the operator proof runs them with PHP present, none skipped for lack of PHP | delivery record, operator report |
| A7 | On the same unchanged candidate commit: Auditor **PASS**, DevSecOps **PASS**, and Tester **PASS** within the scope of section 6 | ledger |
| A8 | Operator proof (section 8) passes on that unchanged candidate | Orchestrator report |
| A9 | Secret scan: 0 findings; no credential, host address, personal, customer or firm data in the change | scan |

The order is complete only when A1 to A9 hold. A closed ledger alone is not acceptance.

## 6. Verification by role

| Role | Assigned verification and evidence |
|---|---|
| Engineer | implementation; automated tests for every criterion executable without a runtime; scripts for the runtime criteria that the operator proof runs; suite counts before and after; every changed existing test line listed |
| Auditor | conformance to this order and section 4; superseded expectations limited to the list; no weakened assertion. PASS or FINDINGS with the candidate commit |
| Tester | every criterion executable in the sandbox, including mutations showing new tests fail when a control is removed; states what was **not** executed. PASS or FINDINGS; live-runtime behaviour is assigned to section 8 and is not claimed |
| DevSecOps | authorisation and bypass review of every server change; secrets, dependencies and secret scan. PASS or FINDINGS |

**Runtime.** The sandbox has no network, Docker, browser or EspoCRM, and PHP is not assumed. This order assigns live-runtime behaviour to the operator proof of section 8, which is mandatory. Approval of this order approves this assignment.

## 7. Budget and stop conditions

- At most **3** executions each for Engineer, Auditor, Tester and DevSecOps. Any Engineer change restarts the three reviews.
- A corrective successor, if later needed, is a separate Work Order whose exact text is approved before dispatch; **at most 4 executions per role across both**.
- **BLOCKED and escalated:** an exhausted budget, a failed gate, a needed change outside section 4, or a criterion that cannot be met safely.

## 8. Operator proof (no specialist executions)

On a disposable runtime of the pinned images (own project name, internal network, synthetic data only), with the unchanged candidate: synthetic rehearsal end to end including rollback. A rehearsal on a restored copy of beta data is a separate operator step needing its own approval. Evidence holds no credential or personal data.

## 9. Entry gates

| Gate | Requirement |
|---|---|
| E0 | Predecessor accepted and its result on GitHub `main` |
| E1 | Exact-version approval: path, commit, file SHA-256, bound base, budget, and the decisions of section 11 |
| E2 | Base resolves in the Project Lead repository and satisfies section 2; `forge-start` accepts it, proved on a scratch copy |
| E3 | Engine and plugin as pinned; no `CRM-CUT-001` branch, worktree, ledger or record exists |
| E4 | Runner isolation established for this engine immediately before dispatch: hardened mount and PID namespace launcher, clean environment, in-context denial of sensitive paths, positive control and process sentinel; execution identity and CLI version recorded. Any adverse result blocks dispatch |
| E5 | No other open ledger or Project Lead session for this project; coordinated with other users of the engine |
| E6 | The order given to the Project Lead is read-only and byte-identical to the approved file |

## 10. Communications and completion

- **Issue:** this order's Issue (named at base binding). Progress is event driven (gates, dispatch, candidate, verdicts, close, blockers). Escalation: Project Lead to Orchestrator; Orchestrator to the Architect (architecture, scope) and the Product Owner (product, permission, material risk).
- **Logs (writer: Project Lead; readers: Orchestrator, Architect):** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-CUT-001/` with `prompts/` and per-role `dispatch/` output; published to `.forge/CRM-CUT-001/` on the branch.
- **Completion report:** outcome, changed paths, base and candidate commits, acceptance results, the three verdicts and the candidate each assessed, execution counts, evidence locations, deviations, limitations and residual risks. The output is a candidate branch and draft pull request.

## 11. Decisions the approval must state

1. Dispatch of the exact bound version, with this budget.
2. The superseded expectations of section 4 and the verification assignment of section 6.
3. How test records are treated before identity genesis (retire, or remove before genesis).
4. Whether e-mail filing is deferred (Product Owner).
