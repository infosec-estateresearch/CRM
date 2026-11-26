# auditor review: CRM-IDINT-001 (round 2)

Worktree (read-only to you): /srv/CRM/worktrees/CRM-IDINT-001
Candidate SHA: 65eab11d68583555b378dd2bff36a1d237db3d1a
Base SHA: 5c56fcd8c1fe7b6257e11aae2276ce0878f9be20
Scratch directory: /srv/CRM/worktrees/.forge-scratch/CRM-IDINT-001
Assess the candidate independently against the Work Order below. Do not modify the worktree; leave no bytecode or cache file in it (use PYTHONDONTWRITEBYTECODE=1 python3 -B; write temporary material only where permitted). State plainly what you did not execute. Use safe finding keys; keep exploit detail of anything that might remain on a running system out of public-safe wording.

Your assigned verification (WO section 6): conformance to this order and section 4; each superseded expectation is limited to the list; matrix completeness; no weakened assertion. PASS or FINDINGS with the candidate commit.
End your final message with exactly one verdict line: VERDICT: PASS, VERDICT: FINDINGS, or VERDICT: INCONCLUSIVE, followed by the candidate commit and, for each finding, a short key, severity (blocking/advisory), and evidence.

## GOVERNING RULINGS (binding; these govern the Work Order text below wherever it differs)

- **Approved artifact:** PR #93, commit `1717537ec7e1ad716273f6d5ca60f86c62000469`, `work-orders/CRM-IDINT-001.md`, SHA-256 `a7899d276c781736eb53d482731320a272262836470dd305d2421df0d0680f93`.
- **Base and known commit:** `5c56fcd8c1fe7b6257e11aae2276ce0878f9be20`.
- **Rulings:**
  1. Dispatch of this exact version: yes, once E0 to E6 pass.
  2. At most **three** executions per role for this ledger.
  3. One corrective successor within a cumulative maximum of four executions per role: yes in principle. **Its exact artifact needs separate approval.** The correction comment on Issue #92 governs the contradictory wording in section 7: there is **no standing authority**. You do not write, start or dispatch a successor.
  4. Operator runtime and browser proof: yes. A browser-only ESCALATED close is intermediate, never acceptance.
  5. The superseded expectations of section 4: accepted.
  6. Section 3.5: **option (a)**. Roles with permission to edit the record may retire or supersede it through the controlled and audited workflow.
- The draft labels in the Work Order file ("DRAFT", "Not approved. No dispatch", "No ruling has decided it", and the approval choices it leaves open) predate this approval and are superseded by this section. They are not a contradiction in acceptance criteria.

### PASS rule and what closes the Work Order (verbatim)
- Criterion A13 needs, on the same unchanged candidate: Auditor **PASS**, DevSecOps **PASS**, and Tester **PASS**, or **INCONCLUSIVE solely for browser and live-runtime behaviour** with every sandbox-executable criterion passing.
- A reviewer verdict `FINDINGS` is not a PASS. Do not record the findings of a FINDINGS verdict as advisory or rejected to reach DELIVER, unless you disprove one with evidence, which you record. Observations stated under a PASS may be advisory.
- Browser gate (WO section 6): when everything else passes and the Tester is inconclusive solely for browser and live-runtime behaviour, close **ESCALATED** with that reason **without a further Tester execution to retry it**. That is the expected successful result on this host.
- A Tester that is inconclusive for any other reason, or any other inconclusive reviewer, is handled by the engine rules inside the budget of section 2.

### Test environment and binding reminders (verbatim)
- Unit suite: `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests/unit`, from the worktree. Baseline at the base: 624, OK. The Work Order records 11 PHP skips where PHP is absent.
- The specialists have no network, Docker, browser or EspoCRM runtime. Do not install anything. State plainly what was not executed. The Orchestrator performs the runtime and browser proof of WO section 8; do not claim it.
- Leave no bytecode, cache or scratch file in the worktree or the repository.
- Boundary: WO section 4. A needed change outside it is a stop condition: report BLOCKED, never work around it. WIP is on hold: the "Open WIP / Revenue" item and its handler stay unchanged; the only related change is the scope-guard repair of WO section 3.9.
- **The repository is public.** Anything you commit or push (including `.forge/` records) carries no credential, host address, personal, customer or firm data. In published records name findings by safe identifiers and keep exploit detail of anything still present on a running system in your private records. A genuine finding that cannot be reported safely is BLOCKED, never PASS.
- Pre-existing root-owned entries in the repository's Git directory, and a root-owned bytecode directory under `load/`, are preserved state. Do not repair, re-own, reset or clean them. If a Git operation fails for an ownership reason, report BLOCKED with the exact error.

Execution budget: at most 3 executions per role for this ledger. A missing standing successor authority or the three-execution limit is NOT a finding.

## WORK ORDER (verbatim)

WO: CRM-IDINT-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: 5c56fcd8c1fe7b6257e11aae2276ce0878f9be20
KNOWN_COMMIT: 5c56fcd8c1fe7b6257e11aae2276ce0878f9be20
BROWSER: yes

# CRM-IDINT-001: identity integrity

## 1. Identity, purpose and authority

| Item | Value |
|---|---|
| Version | v1.1 **DRAFT**, 2026-11-26. Replaces v1.0 (commit `1f0ba1762e66d8589d6cb0f1d0f8ebbb887103c0`), published the same day and never approved: the review ceiling, retire permission and two verification rows are corrected. **Not approved. No dispatch.** Approval must name this path and the commit that contains it, on the Issue below |
| Issue (status, evidence, approval, escalation) | https://github.com/infosec-estateresearch/CRM/issues/92 |
| Priority and parent item | P0. CRM-PBI-035 (identity integrity), proposed in the records change of 2026-11-26 |
| Product outcome | ERm can be the authoritative source of FirmID and ContactID for Estate Research's applications |
| Direction and decisions | Issue https://github.com/infosec-estateresearch/CRM/issues/91 (C-1, C-2, C-3; auditing decision); CRM-D036; `PROJECT-INITIATION-MANDATE.md` |
| Governing FOUNDRY | `maff0000/foundry@39cc45c25aa5305b60f4c4af1557bee8cec0bf20`: `standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md`. The requirements needed here are stated here |
| Engine | ForgeV2 plugin 0.3.0, `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, installed at `/srv/forgev2`, unmodified |
| Assignment | The Orchestrator (Rogue) dispatches one Project Lead (`forgev2-pl` on DOCKER1). Roles: Engineer, Auditor, Tester, DevSecOps |
| Delivery autonomy | This order fixes outcomes, acceptance, boundaries and budget. Design, order of work and routine corrections belong to the Project Lead and specialists |

## 2. Repository and workspace

| Item | Value |
|---|---|
| Base | the commit above: held by the Project Lead repository and differing from GitHub `main` (`862c6302b4e919b1aa734e37078b4fd4c17f0115` at preparation) **only by Markdown documents** |
| Branch and worktree | `forge/CRM-IDINT-001`, `/srv/CRM/worktrees/CRM-IDINT-001`, created by the engine |
| Execution host and route | `DOCKER1:/srv/CRM/main`; the Orchestrator runs on another host and starts the Project Lead on DOCKER1 over its established administrative route |
| Protected | ForgeV2 and Foundry installations; every existing ledger, branch, candidate and pull request; live runtimes; the checkout `ROOT` except as the engine itself writes it |

## 3. Outcome

No identity relationship or identifier in ERm can be changed, removed or lost without authorisation and a durable audit record, by any user or service account, including administrators, through any application route. Legitimate changes remain available and audited.

**Identifiers:** FirmID = `Account.id`; ContactID = `Contact.id`; `sfId` is a legacy cross-reference. **Identity relationships:** a firm's parent firm; a contact's primary firm; a contact's other firm links; an enquiry's firm; a successor link (3.5).

### 3.0 Route matrix (the unit of acceptance)

For **each relationship**, **each route** that can reach it and **each account kind**, the result is either *refused, with nothing changed* or *performed, with its identity audit record*.

| Axis | Members |
|---|---|
| Routes | record create; record edit; link and unlink from either side, including panel selection and bulk linking; mass update; delete and mass delete; record merge; CSV import; creation with a supplied identifier; retire and supersede; the scheduled cleanup job |
| Account kinds | administrator; every human role present at the base; the import service account |

A route the product exposes and this list omits is added, not ignored.

### 3.1 Audit or fail
An identity relationship change does not succeed unless its audit record is durably stored. The record names actor, UTC time, the record changed, and previous and new identifiers (empty where none). If it cannot be stored, the change is refused and nothing changes.

### 3.2 Audit protection
No role, including administrator, can edit or delete identity audit records through the application. Host-level and database-level tampering remains possible and is documented as a residual risk.

### 3.3 Primary firm
A contact's primary firm is always one of its linked firms. Removing that link is refused unless the same change sets another linked firm as primary or deliberately clears the primary. Existing exceptions are **not repaired and no primary firm is invented**: a read-only report lists them (counts and identifiers).

### 3.4 No loss of identity records
Deleting and merging firms and contacts is refused for every account. Automatic removal of deleted records and of audit history is off.

### 3.5 Retire and supersede
Every issued firm and contact identifier resolves to `active`, `retired`, or `superseded` with a successor. Who may do so is decided by the approval, which states one of: **(a)** any role that may edit the record (proposed); **(b)** administrators only. No ruling has decided it. A successor is an existing record of the same kind, never itself, and cycles are refused; resolution follows the chain to its end. Retired and superseded records stay readable. State changes are audited under 3.1. **Interim rule:** a mistaken or test record is retired or superseded, never deleted; removal of test records before identity genesis is decided in CRM-CUT-001.

### 3.6 Settings travel with the release
The release applies and reads back: deleted-record cleanup off, audit cleanup off, user action history 6 months, sign-in records 13 months. A deployment fails if they are not in force. `bin/command config:set` is the setting mechanism the release already uses.

### 3.7 Identifiers are issued only by ERm
No create route accepts a supplied identifier; CSV import is unavailable for firms, contacts and enquiries.

### 3.8 Clean refusal
Input longer than a stored field allows (contact job title is the known case) is refused as a validation error and creates or changes nothing.

### 3.9 Preserved behaviour and the scope guard
The loader and synthetic seed work as before. The Account "Open WIP / Revenue" item and its handler are unchanged (WIP is on hold). `tests/unit/test_wip_link.py` measures changed paths from an earlier Work Order's base, so it fails on any later change outside that order's list (it fails on `main` today): bind it to the delivery it was written to protect, keeping that protection, with a test showing it still detects an out-of-scope change.

Configuration-only controls may be built first and server controls added after. There is no partial acceptance.

## 4. Delivery boundary

| | |
|---|---|
| In scope | `custom/Espo/Custom/`, `config/`, `scripts/`, `tests/`, existing and new files under `docs/` |
| Must not change | `deploy/`, `load/`, `client/custom/`, `.forge/` of other orders, `work-orders/`, root product records, EspoCRM core. Do **not** create `docs/IDENTITY.md` or `docs/LOGGING.md`: the records change adds them on `main` |
| Excluded | FirmGroup (CRM-FG-001); the independent identity register and restore reconciliation (CRM-OPS-001); user types, sign-in security and menus (CRM-ACC-001) beyond what refusal above needs; any WIP change |
| Dependencies and constraints | no new package, image, extension or vendored file; supported EspoCRM metadata and server extension points only; no secret in the repository |
| Data and systems | synthetic data only. No beta, production, real data, NAS or Salesforce. No deployment or merge |

### Behaviour this order supersedes
These existing expectations change with the new behaviour. Another existing assertion may change only where it contradicts a criterion in section 5, and then it is extended or replaced with an equally strict one. Every changed existing test line is listed; the Auditor checks each. Nothing else is removed or weakened:

1. The acceptance suites under `tests/acceptance/`: deleting a firm or contact, including by an administrator after an enquiry is removed, becomes a refusal; setup and teardown no longer delete firms or contacts.
2. Removal of an accepted near-duplicate in those suites uses retirement.
3. Unit tests that assert the exact set or location of server hooks (`tests/unit/test_metadata.py` allowed hook folders; `tests/unit/test_access_policy.py` hook list) may be extended to include what this order adds, keeping their other assertions.
4. The guard that refuses deleting a firm with enquiries may be replaced by the general refusal, with its unit tests rewritten to prove that refusal.
5. `docs/BETA.md` and `docs/ACCESS.md` statements about deleting or removing records are updated. `scripts/uat_records.py` is read-only and keeps working.
6. `ER Manager` may delete contacts at the base (`config/access/roles.json`). That level may become `no`, with the matching expectation in `tests/unit/access_policy.py`, its fixtures and the `docs/ACCESS.md` table. No other role level changes.

Synthetic tests do not clean up by deleting firms or contacts: they use unique names and a disposable stack that is torn down.

## 5. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| A1 | A suite under `tests/acceptance/` covers every cell of 3.0 and asserts refused-and-unchanged or performed-and-audited; a unit test fails if a required cell is missing | matrix report: **100 % pass** |
| A2 | For each relationship, every human role allowed to edit it at the base can still change it by at least one supported route, with the audit record | suite |
| A3 | With audit storage made unwritable, **0** identity relationship changes succeed on any route | suite |
| A4 | Edit and delete of identity audit records are refused for every account | suite |
| A5 | After the matrix run there are **0 new** contacts breaking 3.3; the report lists exactly the seeded exceptions and changes nothing | suite, before and after digests |
| A6 | Delete, mass delete and merge of firms and contacts are refused for every account | suite |
| A7 | The cleanup job run on data aged past every period removes **0** firm or contact records and **0** audit records; the release fails when any setting of 3.6 is wrong | suite, unit tests |
| A8 | Supplied identifiers are never used; CSV import is refused for firms, contacts and enquiries | suite |
| A9 | Over-length input returns a validation error; record counts unchanged | suite |
| A10 | Every identifier created in the run resolves per 3.5; self, cycle, wrong-kind and missing successor are refused | suite |
| A11 | Synthetic seed and loader on the candidate: no new refusal, relationship totals equal to the base run, second load writes nothing | operator report |
| A12 | `python3 -m unittest discover -s tests/unit` as a non-root user: **0 failures**. The only new skips allowed are tests that need PHP, gated like the existing ones, and each is listed. The operator proof runs the suite **with PHP present: 0 failures, none skipped for lack of PHP**. Baseline 2026-11-26 without PHP: base 624 tests, 0 failures, 11 skipped; GitHub `main` has 1 failure, the guard of 3.9 | delivery record, operator report |
| A13 | On the same unchanged candidate commit: Auditor **PASS**, DevSecOps **PASS**, and Tester **PASS**, or **INCONCLUSIVE solely for browser and live-runtime behaviour** with every sandbox-executable criterion passing (section 6) | ledger |
| A14 | Operator runtime and browser proof (section 8) passes on that unchanged candidate | Orchestrator report |
| A15 | Secret scan: 0 findings; no host address or credential in the change | scan |

The order is complete only when A1 to A15 hold. A closed ledger alone is not acceptance.

## 6. Verification by role

| Role | Assigned verification and evidence |
|---|---|
| Engineer | implementation; the suites of A1 to A10; unit counts before and after; every changed existing test line listed |
| Auditor | conformance to this order and section 4; each superseded expectation is limited to the list; matrix completeness; no weakened assertion. PASS or FINDINGS with the candidate commit |
| Tester | every criterion executable in the sandbox, including mutations showing the new unit tests fail when a control is removed. States plainly that PHP, EspoCRM and a browser were **not** executed. PASS, FINDINGS, or INCONCLUSIVE solely for browser and live-runtime behaviour |
| DevSecOps | authorisation and bypass review of every server change; no secret, host or new dependency; secret scan. PASS or FINDINGS |

**Browser gate.** The sandbox has no network, Docker, browser or EspoCRM, and PHP is not assumed. Browser behaviour is material, so under the engine's browser gate the Tester reports it `inconclusive`, never as passed, and, when everything else passes, the Project Lead closes the ledger **ESCALATED** with that reason, **without a further Tester execution to retry it**. Under CRM-D013 this is an acceptable intermediate result when everything else passes, and **never final acceptance**: that needs section 8, which is mandatory. A `DELIVERED` close is therefore not expected on this host. Approval of this order approves this assignment of browser and live-runtime verification to the operator.

## 7. Budget, correction and stop conditions

- **This ledger:** at most **3** executions each for Engineer, Auditor, Tester and DevSecOps. Any Engineer change restarts the three reviews. **Effective ceiling: two review rounds.** The engine closes a ledger when one reviewer is inconclusive twice in a row, before it routes any further correction, and the browser gate makes the Tester inconclusive on each otherwise passing round. A second round can therefore end **ESCALATED with findings still open**.
- **Standing correction authority (requested; applies only if the approval grants it):** one corrective successor `CRM-IDINT-001-C` may be dispatched **without further approval** from the last candidate, with the same outcome, boundaries and acceptance, when (i) this ledger closes ESCALATED under the rule above with open findings, or (ii) the operator proof finds a defect. It carries those findings. **Total across both: at most 4 per role**, recorded cumulatively; it adds no execution beyond that limit and no further successor exists. Without the grant, either case is escalated.
- **BLOCKED and escalated:** an exhausted budget, a failed gate, a needed change outside section 4, or a criterion that cannot be met safely.

## 8. Operator runtime and browser proof (no specialist executions)

On a disposable runtime of the pinned images (own project name, internal network, synthetic data only), with the unchanged candidate: PHP syntax check; deployment with the real release scripts; the suites of A1 to A11; the unit suite with PHP present (A12); and a real-browser check of firm, contact and enquiry screens for each human account kind (legitimate edits work; refused actions are absent or fail with a clear message; no script error). Evidence holds no credential.

## 9. Entry gates

| Gate | Requirement |
|---|---|
| E0 | **First entry activity:** the defect this order addresses is reproduced on synthetic `crm-dev` and recorded (private evidence; counts and outcome on the Issue). If it cannot be reproduced, stop and report |
| E1 | Exact-version approval: path, commit, file SHA-256, base, budget, whether the correction authority of section 7 is granted, and the section 3.5 choice |
| E2 | `BASE` and `KNOWN_COMMIT` resolve in the Project Lead repository; GitHub `main` differs from the base only by Markdown documents; `forge-start` accepts the base, proved on a scratch copy |
| E3 | Engine and plugin as pinned and unmodified; no `CRM-IDINT-001` branch, worktree, ledger or record exists |
| E4 | Runner isolation established for this engine immediately before dispatch: hardened mount and PID namespace launcher, clean environment, in-context denial of sensitive paths, positive control and process sentinel; execution identity and CLI version recorded. Any adverse result blocks dispatch |
| E5 | No other open ledger or Project Lead session for this project; coordinated with other users of the engine |
| E6 | The order given to the Project Lead is read-only and byte-identical to the approved file |

## 10. Communications and completion

- **Issue:** #92. Progress is event driven (gates, dispatch, candidate, verdicts, close, blockers). Escalation: Project Lead to Orchestrator; Orchestrator to the Architect (architecture, scope) and the Product Owner (product, permission, material risk).
- **Logs (writer: Project Lead; readers: Orchestrator, Architect):** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-IDINT-001/` with `prompts/` and per-role `dispatch/` output; published to `.forge/CRM-IDINT-001/` on the branch.
- **Completion report:** outcome, changed paths, base and candidate commits, results for A1 to A15, the three verdicts and the candidate each assessed, execution counts, evidence locations, deviations, limitations and residual risks. The output is a candidate branch and draft pull request (also on an ESCALATED close). Integration to `main` is a separate reviewed step, because the base precedes `main` by document-only differences.
