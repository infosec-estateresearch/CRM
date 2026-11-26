WO: CRM-OPS-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: BOUND-AT-ENTRY

# CRM-OPS-001: backup tooling, identity register and failure alerting

## 1. Identity, purpose and authority

| Item | Value |
|---|---|
| Version | v0.3 **PREPARED TEXT**, 2026-11-26. **Not approved. Cannot be dispatched:** the base is unbound. Dispatch needs a later version that names the base and its Issue, approved at that exact path and commit |
| Issue | https://github.com/infosec-estateresearch/CRM/issues/95 (package); this order's own Issue is opened when the base is bound |
| Priority and parent item | P0. CRM-PBI-039 |
| Product outcome | Recovery is proven and monitored, and no issued identifier disappears unnoticed after a restore |
| Direction and decisions | Issue https://github.com/infosec-estateresearch/CRM/issues/91; CRM-D046; `docs/IDENTITY.md` (identity register); `PROJECT-INITIATION-MANDATE.md`. Decisions CRM-D044 to D054, `docs/IDENTITY.md` and `docs/LOGGING.md` are on pull request 94 until merged |
| Governing FOUNDRY | `maff0000/foundry@39cc45c25aa5305b60f4c4af1557bee8cec0bf20`: `standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md` |
| Engine | ForgeV2 plugin 0.3.0, `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, at `/srv/forgev2`, unmodified |
| Assignment | The Orchestrator (Rogue) dispatches one Project Lead (`forgev2-pl` on DOCKER1). Roles: Engineer, Auditor, Tester, DevSecOps |
| Delivery autonomy | This order fixes outcomes, acceptance, boundaries and budget. Design, order of work and routine corrections belong to the Project Lead and specialists |

## 2. Repository and workspace

| Item | Value |
|---|---|
| Base | Unbound. Predecessor: **CRM-AUDIT-001**. The base will be a commit held by the Project Lead repository that contains the predecessor's accepted result and differs from GitHub `main` only by documents and delivery records, proved by a compare |
| Branch and worktree | `forge/CRM-OPS-001`, `/srv/CRM/worktrees/CRM-OPS-001`, created by the engine |
| Execution host and route | `DOCKER1:/srv/CRM/main`; the Orchestrator runs on another host and starts the Project Lead on DOCKER1 over its established administrative route |
| Platform reference | `/srv/CRM/wo/CRM-OPS-001/reference/espocrm/`: `application/` and `vendor/`, and `client/` where the order changes browser code, extracted from the image pinned at the bound base. Read-only, outside the repository, never committed; digests are recorded in the bound version. **It is the authority for every platform name, signature, route and setting** |
| Protected | ForgeV2 and Foundry installations; every existing ledger, branch, candidate and pull request; live runtimes; the checkout `ROOT` except as the engine itself writes it |

## 3. Outcome and required behaviour

The nightly backup already operated by hand-installed scripts becomes tested product tooling, with an independent identity register and an alert that reaches a named person.

1. Backup, encryption to a public key, off-host copy, read-back check and retention (7 daily, 4 weekly, 3 monthly, one copy serving several) are product scripts with tests; pinned copies are never removed; retention starts report-only and is enabled only by explicit operator setting.
2. One scheduling mechanism. The unavailable or wrong off-host target is refused with nothing written in its place; a local backup is still made.
3. The job follows the deployed release without a hand-edited pin, and refuses a mismatch.
4. A failed, missed or stale backup reaches a named person within **26 hours** by a channel the Product Owner names.
5. An **identity register**, outside the application database and carried with the off-host copies, records every firm and contact identifier (and every group identifier where groups exist at the base) with state and successor, and no names or other personal data. It is append-only in effect: an entry is never removed.
6. After a restore to an earlier state, reconciliation lists every registered identifier missing from the database, every state or successor mismatch and every successor cycle, and nothing disappears unnoticed. Reissue of a registered identifier is detected.
7. A restore runbook and an isolated restore proof of the whole application are part of the product.

## 4. Delivery boundary

|  |  |
|---|---|
| In scope | `scripts/`, `deploy/beta/systemd/`, `custom/Espo/Custom/` (register export only), `tests/`, `docs/` |
| Must not change | `.forge/` of other orders unless the scope row names them, `work-orders/`, root product records, EspoCRM core |
| Excluded | the private decryption key on the application host or the off-host store; changes to other applications' backups or the storage service |
| Dependencies and constraints | no new package, image, third-party or installable extension, or vendored file; custom code at supported EspoCRM extension points only; no secret in the repository |
| Data and systems | synthetic data only. No beta, production, real data, off-host store or Salesforce access. No deployment or merge. No WIP change (on hold) |

### Existing behaviour this order supersedes
Only the following existing expectations change. Another existing assertion may change only where it contradicts a criterion in section 5, and then it is extended or replaced with an equally strict one. Every changed existing test line is listed; the Auditor checks each. Nothing else is removed or weakened:

1. The release backup timer template is replaced by the single mechanism, with its documentation and unit expectations.

## 5. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| A1 | Retention proof on synthetic dated copies: pinned, partial, foreign, linked and altered folders untouched; only planned copies removed | unit tests |
| A2 | Wrong or absent target: refused, **0** files written there, local backup present, failure visible | unit tests, operator report |
| A3 | Restore from an encrypted copy into an isolated stack: identity digests equal, sign-in and record reads work | operator report |
| A4 | Register: restore to an earlier synthetic state lists exactly the identifiers issued later; successor resolution correct; cycle and reissue detected; register holds no personal data | suite |
| A5 | An induced failure and an induced missed run (simulated clock) each raise an alert that arrives on the named channel; detection fires no later than 26 hours after the missed time | operator report, test-marked alerts |
| A6 | Every test suite present at the base, run as a non-root user as documented in the repository: **0 failures**. The only new skips allowed are tests needing PHP, gated like existing ones, each listed; the operator proof runs them with PHP present, none skipped for lack of PHP | delivery record, operator report |
| A7 | On the same unchanged candidate commit: Auditor **PASS**, DevSecOps **PASS**, and Tester **PASS**, or **INCONCLUSIVE solely for live-runtime behaviour** with every sandbox-executable criterion passing | ledger |
| A8 | Operator proof (section 8) passes on that unchanged candidate | Orchestrator report |
| A9 | Secret scan: 0 findings; no credential, host address, personal, customer or firm data in the change | scan |

The order is complete only when A1 to A9 hold. A closed ledger alone is not acceptance.

## 6. Verification by role

| Role | Assigned verification and evidence |
|---|---|
| Engineer | implementation; automated tests for every criterion executable without a runtime; scripts for the runtime criteria that the operator proof runs; suite counts before and after; every changed existing test line listed |
| Auditor | conformance to this order and section 4; superseded expectations limited to the list; no weakened assertion. PASS or FINDINGS with the candidate commit |
| Tester | every criterion executable in the sandbox, including mutations showing new tests fail when a control is removed; states what was **not** executed. PASS, FINDINGS, or INCONCLUSIVE solely for live-runtime behaviour |
| DevSecOps | authorisation and bypass review of every server change; secrets, dependencies and secret scan. PASS or FINDINGS |

**Runtime.** The sandbox has no network, Docker or EspoCRM, and PHP is not assumed. Criteria that need a runtime are assigned to the operator proof of section 8. Where the Tester cannot execute one it reports it `inconclusive`, never passed, and, when everything else passes, the Project Lead closes the ledger **ESCALATED** with that reason. This is an acceptable intermediate result and **never final acceptance**: that needs section 8. Approval of this order approves this assignment.

**Platform fidelity (binding).** Every platform interface, class, signature, metadata key, route and setting relied on is cited by file from the platform reference, and each reviewer checks it there. Unit-test stand-ins declare no platform symbol that is absent from the reference, and match its signatures. Where the order adds or changes server code, a test loads every custom class against the reference with PHP and `CRM_PLATFORM_REFERENCE` set; the Engineer and Tester run it, and a skip is a blocking finding. A refusal is proven only by the control's own refusal on a route that exists.

## 7. Budget and stop conditions

- At most **3** executions each for Engineer, Auditor, Tester and DevSecOps. Any Engineer change restarts the three reviews. **Where the Tester reports inconclusive, the effective ceiling is two review rounds**, because the engine closes a ledger when one reviewer is inconclusive twice in a row, so a second round can end ESCALATED with findings open.
- A corrective successor, if later needed, is a separate Work Order whose exact text is approved before dispatch; **at most 4 executions per role across both**.
- **BLOCKED and escalated:** an exhausted budget, a failed gate, a needed change outside section 4, or a criterion that cannot be met safely.

## 8. Operator proof (no specialist executions)

On a disposable runtime of the pinned images (own project name, internal network, synthetic data only), with the unchanged candidate: exercise the scripts against a stand-in target; full restore proof; register reconciliation; failure and missed-run alerts sent from the operator host. After acceptance, installation on the target host is a separate operator step with its own approval; **3 consecutive** scheduled successes there close the product item, not this order. Evidence holds no credential or personal data.

**Early runtime check.** Before the first candidate commit, the Orchestrator runs the first Engineer round on a disposable runtime of the pinned image; a failure goes to the second Engineer execution. The final candidate passes on that runtime with no diagnostic bypass or patch.

## 9. Entry gates

| Gate | Requirement |
|---|---|
| E0 | Predecessor accepted and its result on GitHub `main`, together with the decision, identity and logging records of pull request 94 |
| E1 | Exact-version approval: path, commit, file SHA-256, bound base, budget, and the decisions of section 11 |
| E2 | Base resolves in the Project Lead repository and satisfies section 2; `forge-start` accepts it, proved on a scratch copy |
| E3 | Engine and plugin as pinned; no `CRM-OPS-001` branch, worktree, ledger or record exists |
| E4 | Runner isolation established for this engine immediately before dispatch: hardened mount and PID namespace launcher, clean environment, in-context denial of sensitive paths, positive control and process sentinel; execution identity and CLI version recorded. Any adverse result blocks dispatch; a specialist can read the platform reference and cannot write it, and its digests match |
| E5 | No other open ledger or Project Lead session for this project; coordinated with other users of the engine |
| E6 | The order given to the Project Lead is read-only and byte-identical to the approved file |

## 10. Communications and completion

- **Issue:** this order's Issue (named at base binding). Progress is event driven (gates, dispatch, candidate, verdicts, close, blockers). Escalation: Project Lead to Orchestrator; Orchestrator to the Architect (architecture, scope) and the Product Owner (product, permission, material risk).
- **Logs (writer: Project Lead; readers: Orchestrator, Architect):** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-OPS-001/` with `prompts/` and per-role `dispatch/` output; published to `.forge/CRM-OPS-001/` on the branch.
- **Completion report:** outcome, changed paths, base and candidate commits, acceptance results, the three verdicts and the candidate each assessed, execution counts, evidence locations, deviations, limitations and residual risks. The output is a candidate branch and draft pull request.

## 11. Decisions the approval must state

1. Dispatch, with this budget, of the later version that binds the base. This item cannot be given to this prepared text.
2. The superseded expectations of section 4 and the verification assignment of section 6.
3. The alert channel and named recipient (Product Owner input).
4. Where the identity register is held.
