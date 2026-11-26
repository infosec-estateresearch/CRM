WO: CRM-ERIC-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: BOUND-AT-ENTRY

# CRM-ERIC-001: read-only identity access for consumers

## 1. Identity, purpose and authority

| Item | Value |
|---|---|
| Version | v0.1 **PREPARED TEXT**, 2026-11-26. **Not approved. Cannot be dispatched:** the base is unbound. Dispatch needs a later version that names the base and its Issue, approved at that exact path and commit |
| Issue | https://github.com/infosec-estateresearch/CRM/issues/95 (package); this order's own Issue is opened when the base is bound |
| Priority and parent item | P2. CRM-PBI-007 |
| Product outcome | A consuming system resolves FirmID, GroupID and ContactID without any write access |
| Direction and decisions | Issue https://github.com/infosec-estateresearch/CRM/issues/91; CRM-D046; `docs/IDENTITY.md` (integration); `PROJECT-INITIATION-MANDATE.md` |
| Governing FOUNDRY | `maff0000/foundry@39cc45c25aa5305b60f4c4af1557bee8cec0bf20`: `standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md` |
| Engine | ForgeV2 plugin 0.3.0, `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, at `/srv/forgev2`, unmodified |
| Assignment | The Orchestrator (Rogue) dispatches one Project Lead (`forgev2-pl` on DOCKER1). Roles: Engineer, Auditor, Tester, DevSecOps |
| Delivery autonomy | This order fixes outcomes, acceptance, boundaries and budget. Design, order of work and routine corrections belong to the Project Lead and specialists |

## 2. Repository and workspace

| Item | Value |
|---|---|
| Base | Unbound. Predecessor: **CRM-FG-001 for synthetic delivery; **use of real identifiers waits for identity genesis** (CRM-CUT-001)**. The base will be a commit held by the Project Lead repository that contains the predecessor's accepted result and differs from GitHub `main` only by documents and delivery records, proved by a compare |
| Branch and worktree | `forge/CRM-ERIC-001`, `/srv/CRM/worktrees/CRM-ERIC-001`, created by the engine |
| Execution host and route | `DOCKER1:/srv/CRM/main`; the Orchestrator runs on another host and starts the Project Lead on DOCKER1 over its established administrative route |
| Protected | ForgeV2 and Foundry installations; every existing ledger, branch, candidate and pull request; live runtimes; the checkout `ROOT` except as the engine itself writes it |

## 3. Outcome and required behaviour

A consumer-specific, revocable, read-only access that exposes the contract resources and supports full reconciliation.

1. One identity per consumer with its own key, a role limited to the contract entities and fields, revocable alone; never a human or administrator account.
2. Firm, group and contact resources carry the fields of `docs/IDENTITY.md`, including state, successor and change time; a contact's group is resolvable through its primary firm.
3. Consumers can pull changes since a point and reconcile the complete identifier set; retired and superseded identifiers resolve.
4. Every write, other entity and other field is refused. Access is audited and limited in rate.
5. A consumer guide with synthetic examples and a conformance check is provided. Changes inside any consuming system belong to its owner.

## 4. Delivery boundary

|  |  |
|---|---|
| In scope | `custom/Espo/Custom/`, `config/`, `scripts/`, `tests/`, `docs/` |
| Must not change | `.forge/` of other orders unless the scope row names them, `work-orders/`, root product records, EspoCRM core |
| Excluded | any change to a consuming system or its database; real consumer keys; use before identity genesis |
| Dependencies and constraints | no new package, image, extension or vendored file; supported EspoCRM extension points only; no secret in the repository |
| Data and systems | synthetic data only. No beta, production, real data, off-host store or Salesforce access. No deployment or merge. No WIP change (on hold) |

### Existing behaviour this order supersedes
Only the following existing expectations change. Another existing assertion may change only where it contradicts a criterion in section 5, and then it is extended or replaced with an equally strict one. Every changed existing test line is listed; the Auditor checks each. Nothing else is removed or weakened:

1. Role and policy tests gain the consumer role.

## 5. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| A1 | Every write attempt and every out-of-contract read by the consumer is refused | route suite |
| A2 | Full and incremental reconciliation match the database on synthetic data, including changes, retirements and successors | suite |
| A3 | Revoking one consumer leaves others working | suite |
| A4 | Access records show consumer, time and resource | suite |
| A5 | The conformance check passes against the disposable runtime and fails on a deliberate contract break | operator report |
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

On a disposable runtime of the pinned images (own project name, internal network, synthetic data only), with the unchanged candidate: synthetic runtime: full route suite, reconciliation and revocation. Evidence holds no credential or personal data.

## 9. Entry gates

| Gate | Requirement |
|---|---|
| E0 | Predecessor accepted and its result on GitHub `main` |
| E1 | Exact-version approval: path, commit, file SHA-256, bound base, budget, and the decisions of section 11 |
| E2 | Base resolves in the Project Lead repository and satisfies section 2; `forge-start` accepts it, proved on a scratch copy |
| E3 | Engine and plugin as pinned; no `CRM-ERIC-001` branch, worktree, ledger or record exists |
| E4 | Runner isolation established for this engine immediately before dispatch: hardened mount and PID namespace launcher, clean environment, in-context denial of sensitive paths, positive control and process sentinel; execution identity and CLI version recorded. Any adverse result blocks dispatch |
| E5 | No other open ledger or Project Lead session for this project; coordinated with other users of the engine |
| E6 | The order given to the Project Lead is read-only and byte-identical to the approved file |

## 10. Communications and completion

- **Issue:** this order's Issue (named at base binding). Progress is event driven (gates, dispatch, candidate, verdicts, close, blockers). Escalation: Project Lead to Orchestrator; Orchestrator to the Architect (architecture, scope) and the Product Owner (product, permission, material risk).
- **Logs (writer: Project Lead; readers: Orchestrator, Architect):** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-ERIC-001/` with `prompts/` and per-role `dispatch/` output; published to `.forge/CRM-ERIC-001/` on the branch.
- **Completion report:** outcome, changed paths, base and candidate commits, acceptance results, the three verdicts and the candidate each assessed, execution counts, evidence locations, deviations, limitations and residual risks. The output is a candidate branch and draft pull request.

## 11. Decisions the approval must state

1. Dispatch of the exact bound version, with this budget.
2. The superseded expectations of section 4 and the verification assignment of section 6.
3. The first consumer to be conformance-tested.
