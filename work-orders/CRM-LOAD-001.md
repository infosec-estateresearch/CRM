WO: CRM-LOAD-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: BOUND-AT-ENTRY
BROWSER: yes

# CRM-LOAD-001: non-destructive source delta, rejected records, Notes and Salesforce Sync

## 1. Identity, purpose and authority

| Item | Value |
|---|---|
| Version | v0.1 **PREPARED TEXT**, 2026-11-26. **Not approved. Cannot be dispatched:** the base is unbound. Dispatch needs a later version that names the base and its Issue, approved at that exact path and commit |
| Issue | https://github.com/infosec-estateresearch/CRM/issues/95 (package); this order's own Issue is opened when the base is bound |
| Priority and parent item | P1. CRM-PBI-041, CRM-PBI-043 |
| Product outcome | Salesforce changes reach ERm until phase-out without losing identifiers or staff work |
| Direction and decisions | Issue https://github.com/infosec-estateresearch/CRM/issues/91; CRM-D050, CRM-D054; `PROJECT-INITIATION-MANDATE.md` |
| Governing FOUNDRY | `maff0000/foundry@39cc45c25aa5305b60f4c4af1557bee8cec0bf20`: `standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md` |
| Engine | ForgeV2 plugin 0.3.0, `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, at `/srv/forgev2`, unmodified |
| Assignment | The Orchestrator (Rogue) dispatches one Project Lead (`forgev2-pl` on DOCKER1). Roles: Engineer, Auditor, Tester, DevSecOps |
| Delivery autonomy | This order fixes outcomes, acceptance, boundaries and budget. Design, order of work and routine corrections belong to the Project Lead and specialists |

## 2. Repository and workspace

| Item | Value |
|---|---|
| Base | Unbound. Predecessor: **CRM-002-INT; technically also CRM-ACC-001 and CRM-AUDIT-001**. The base will be a commit held by the Project Lead repository that contains the predecessor's accepted result and differs from GitHub `main` only by documents and delivery records, proved by a compare |
| Branch and worktree | `forge/CRM-LOAD-001`, `/srv/CRM/worktrees/CRM-LOAD-001`, created by the engine |
| Execution host and route | `DOCKER1:/srv/CRM/main`; the Orchestrator runs on another host and starts the Project Lead on DOCKER1 over its established administrative route |
| Protected | ForgeV2 and Foundry installations; every existing ledger, branch, candidate and pull request; live runtimes; the checkout `ROOT` except as the engine itself writes it |

## 3. Outcome and required behaviour

Source changes apply to ERm on the existing extractor and loader without regenerating identifiers or silently overwriting staff changes, with preview, approval, reconciliation and audit, optionally driven from an administrator-only **Salesforce Sync** entry.

1. Changes are computed against the previous accepted source: a value changed in ERm since then is never overwritten silently; conflicts are listed for a decision and never resolved automatically.
2. Every source record is classified (create, update, unchanged, conflict, rejected, ignored) and totals reconcile to the source. Nothing is deleted because it is absent from the source. A second run writes nothing.
3. Rejected records keep their original values and a field-level reason; known reject shapes load or are listed. Historical Salesforce Notes are brought into the mapping and loaded with their original dates and authors where available.
4. ERm identifiers and ERm relationships are preserved; matching is by the legacy key; identity changes obey the rules of earlier orders and are audited.
5. A batch is identified; applying it requires approval of that batch; a preview whose source or target has changed is refused; only one run at a time; unusual volume of change needs a further explicit confirmation; rollback is rehearsed.
6. **Salesforce Sync** (Admin section, administrators only): retrieve, validate and compare, preview additions, updates, conflicts and rejects, approve, apply, review reconciliation and audit. It drives the same engine; there is no second one and no schedule.
7. Credentials stay server-side outside Git; the web application never holds or sees a Salesforce credential. Retrieval stays **disabled** until an authorised read-only source is configured. Nothing is ever written to Salesforce.
8. The entry and its worker can be switched off and removed cleanly after phase-out. The data-handling document is updated.

## 4. Delivery boundary

|  |  |
|---|---|
| In scope | `load/`, `migrate/` (interfaces only), `custom/Espo/Custom/`, `client/custom/`, `config/`, `scripts/`, `deploy/` (definitions for the worker), `tests/`, `docs/` |
| Must not change | `.forge/` of other orders unless the scope row names them, `work-orders/`, root product records, EspoCRM core |
| Excluded | live Salesforce access; a new extraction or load engine; scheduled sync; writing to Salesforce |
| Dependencies and constraints | no new package, image, extension or vendored file; supported EspoCRM extension points only; no secret in the repository |
| Data and systems | synthetic data only. No beta, production, real data, off-host store or Salesforce access. No deployment or merge. No WIP change (on hold) |

### Existing behaviour this order supersedes
Only the following existing expectations change. Another existing assertion may change only where it contradicts a criterion in section 5, and then it is extended or replaced with an equally strict one. Every changed existing test line is listed; the Auditor checks each. Nothing else is removed or weakened:

1. Loader behaviour that updates a staff-changed value is replaced by conflict listing, with its tests.
2. The Admin section gains the second entry for administrators; the one-entry assertion of CRM-ACC-001 is extended.

## 5. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| A1 | Synthetic scenarios: **0** staff-edited values overwritten; every conflict listed | suite |
| A2 | Classification totals equal source totals in every scenario; second run **0** writes | suite |
| A3 | Absent source records are never deleted; identifiers unchanged | suite, digests |
| A4 | Every known reject shape and Notes cases load or are listed with originals preserved | suite |
| A5 | Stale preview, concurrent run, unapproved batch and unusual volume are each refused | suite |
| A6 | Standard users and other accounts are refused the screen and its API; no credential reaches the web application, logs or the database | suite, browser run |
| A7 | Rollback restores the pre-batch state | operator report |
| A8 | Every test suite present at the base, run as a non-root user as documented in the repository: **0 failures**. The only new skips allowed are tests needing PHP, gated like existing ones, each listed; the operator proof runs them with PHP present, none skipped for lack of PHP | delivery record, operator report |
| A9 | On the same unchanged candidate commit: Auditor **PASS**, DevSecOps **PASS**, and Tester **PASS**, or **INCONCLUSIVE solely for browser and live-runtime behaviour** with every sandbox-executable criterion passing | ledger |
| A10 | Operator proof (section 8) passes on that unchanged candidate | Orchestrator report |
| A11 | Secret scan: 0 findings; no credential, host address, personal, customer or firm data in the change | scan |

The order is complete only when A1 to A11 hold. A closed ledger alone is not acceptance.

## 6. Verification by role

| Role | Assigned verification and evidence |
|---|---|
| Engineer | implementation; automated tests for every criterion executable without a runtime; scripts for the runtime criteria that the operator proof runs; suite counts before and after; every changed existing test line listed |
| Auditor | conformance to this order and section 4; superseded expectations limited to the list; no weakened assertion. PASS or FINDINGS with the candidate commit |
| Tester | every criterion executable in the sandbox, including mutations showing new tests fail when a control is removed; states what was **not** executed. PASS, FINDINGS, or INCONCLUSIVE solely for browser and live-runtime behaviour |
| DevSecOps | credential isolation, injection through source data, authorisation of every sync operation, and write-protection of the source; secrets, dependencies and secret scan. PASS or FINDINGS |

**Browser gate.** The sandbox has no network, Docker, browser or EspoCRM, and PHP is not assumed. Under the engine's browser gate the Tester reports browser behaviour `inconclusive`, never as passed, and, when everything else passes, the Project Lead closes the ledger **ESCALATED** with that reason without a further Tester execution. Under CRM-D013 this is an acceptable intermediate result and **never final acceptance**: that needs section 8. Approval of this order approves this assignment.

## 7. Budget and stop conditions

- At most **3** executions each for Engineer, Auditor, Tester and DevSecOps. Any Engineer change restarts the three reviews. **Effective ceiling: two review rounds**, because the engine closes a ledger when one reviewer is inconclusive twice in a row, so a second round can end ESCALATED with findings open.
- A corrective successor, if later needed, is a separate Work Order whose exact text is approved before dispatch; **at most 4 executions per role across both**.
- **BLOCKED and escalated:** an exhausted budget, a failed gate, a needed change outside section 4, or a criterion that cannot be met safely.

## 8. Operator proof (no specialist executions)

On a disposable runtime of the pinned images (own project name, internal network, synthetic data only), with the unchanged candidate: synthetic source through extractor, preview, approval, apply, rerun and rollback; browser run of the administrator screen; refusal for other accounts. Evidence holds no credential or personal data.

## 9. Entry gates

| Gate | Requirement |
|---|---|
| E0 | Predecessor accepted and its result on GitHub `main` |
| E1 | Exact-version approval: path, commit, file SHA-256, bound base, budget, and the decisions of section 11 |
| E2 | Base resolves in the Project Lead repository and satisfies section 2; `forge-start` accepts it, proved on a scratch copy |
| E3 | Engine and plugin as pinned; no `CRM-LOAD-001` branch, worktree, ledger or record exists |
| E4 | Runner isolation established for this engine immediately before dispatch: hardened mount and PID namespace launcher, clean environment, in-context denial of sensitive paths, positive control and process sentinel; execution identity and CLI version recorded. Any adverse result blocks dispatch |
| E5 | No other open ledger or Project Lead session for this project; coordinated with other users of the engine |
| E6 | The order given to the Project Lead is read-only and byte-identical to the approved file |
| E7 | Size check: if the Project Lead judges the outcome cannot fit the budget, it stops before Engineer dispatch and proposes the split |

## 10. Communications and completion

- **Issue:** this order's Issue (named at base binding). Progress is event driven (gates, dispatch, candidate, verdicts, close, blockers). Escalation: Project Lead to Orchestrator; Orchestrator to the Architect (architecture, scope) and the Product Owner (product, permission, material risk).
- **Logs (writer: Project Lead; readers: Orchestrator, Architect):** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-LOAD-001/` with `prompts/` and per-role `dispatch/` output; published to `.forge/CRM-LOAD-001/` on the branch.
- **Completion report:** outcome, changed paths, base and candidate commits, acceptance results, the three verdicts and the candidate each assessed, execution counts, evidence locations, deviations, limitations and residual risks. The output is a candidate branch and draft pull request.

## 11. Decisions the approval must state

1. Dispatch of the exact bound version, with this budget.
2. The superseded expectations of section 4 and the verification assignment of section 6.
3. The unusual-volume threshold.
4. Split into two orders (engine first, screen second) if the Architect prefers: this is the largest order and may not fit the budget.
