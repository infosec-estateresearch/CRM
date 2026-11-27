# Engineer prompt, execution 1 of 2 (CRM-IDINT-001R2)

Worktree (the only path you may change; never touch any other path): /srv/CRM/worktrees/CRM-IDINT-001R2
Expected HEAD: 4cb4beca2b8940d63e0706c2d3a50f81cfaee1df (base). Branch forge/CRM-IDINT-001R2. Do not commit; leave changes uncommitted.
Platform reference (read-only, never copy into the worktree): /srv/CRM/wo/CRM-IDINT-001R2/reference/espocrm
Unit suite: CRM_PLATFORM_REFERENCE=/srv/CRM/wo/CRM-IDINT-001R2/reference/espocrm PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests/unit   (set the variable inline; baseline 716 tests OK). A16 test (test_platform_reference.py) must be shown as run with counts. Leave no bytecode, cache or scratch file in the worktree.

## TIME LIMIT (binding)
Dispatch time (UTC): 12:01:31. Deadline: 12:21:31 UTC. Check `date -u` between work items. Work W1 to W5 in order. At the deadline stop changing code and report `STATUS: completed` with an `UNFINISHED:` list (empty if none). Report `blocked` only for a real blocker, never for time. Your report must be returned by 12:26:31 UTC. The engine kills runs at 30 minutes and keeps no report.
Product behaviour (W1, W2) comes first. Final report: STATUS line, files changed, unit counts before/after, A16 counts, platform citations for each interface relied on, the exact S3 reset-removal change and the failing test output, and UNFINISHED list.

## Orchestrator terms, binding, governing the Work Order text (section 1b, verbatim)

> CRM-IDINT-001R2 v1.0 receives EXACT-VERSION ARCHITECT APPROVAL, conditional upon explicit Product Owner recovery exception approval and all entry gates passing.
>
> Rulings R1–R5: ACCEPTED.
> Approach S1–S6: ACCEPTED.
> Consequences C1–C3: ACCEPTED.
>
> The administrator scripting restriction is acceptable. Preserve normal CRM functionality.
>
> All A1–A21 criteria remain mandatory.
>
> The proposed exceptional budget is two additional executions per role, resulting in cumulative ceilings of: Engineer: 6, Auditor: 5, Tester: 5, DevSecOps: 5. This budget requires explicit Product Owner approval.
>
> Ensure the early real-runtime gate is operational before dispatch. Do not consume the second Engineer execution before receiving its findings.
>
> An unfinished report is a checkpoint, not evidence of completed implementation. If the early gate times out, do not waste the remaining correction capacity proceeding blindly.
>
> The unproven audit-memory rollback behaviour must receive meaningful negative testing and independent review.
>
> No further successor, no weakened acceptance, no infrastructure work and no unrelated changes.
>
> Following E0–E7, proceed autonomously and return the completed delivery outcome.
>
> PR #99 remains rejected.

Draft or approval-pending wording in the Work Order file predates these approvals and is superseded; it is not a finding.

## Audit-memory rule (S3), your role (binding)

W3 step 6 must include a negative test of the rule that no in-request memory of an audit record survives a rolled-back change. The test must exercise a failed identity change followed by a further change in the same request, for both the save path and the relation path, and **must fail when the reset is removed**. Report the exact change made to remove it and the failing test output. A missing, skipped or ineffective S3 test is a blocking failure of the work; listing it as unfinished does not satisfy anything.

## Other binding reminders
- Boundary is Work Order section 4; a needed change outside it is a blocker. No change to EspoCRM core. Repository is public: no credential, host address or personal data in anything you write. Do not install anything; no network.
- Do not leave tests failing; if your own report shows failures, say so plainly.

## Work Order (verbatim)

WO: CRM-IDINT-001R2
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: 4cb4beca2b8940d63e0706c2d3a50f81cfaee1df
KNOWN_COMMIT: 4cb4beca2b8940d63e0706c2d3a50f81cfaee1df
BROWSER: yes

# CRM-IDINT-001R2: identity integrity, recovery

## 1. Identity, purpose and authority

| Item | Value |
|---|---|
| Version | v1.0, prepared for approval. **Not in force and not to be dispatched** without both approvals of section 9, gates E1 and E7, on the Issue below |
| Issue (status, evidence, approval, escalation) | https://github.com/infosec-estateresearch/CRM/issues/92 |
| Priority and parent item | P0. CRM-PBI-035 |
| Why | CRM-IDINT-001R closed ESCALATED and its candidate was **not accepted**. That candidate is the base here and must not be merged as it stands |
| Governing FOUNDRY | `maff0000/foundry@39cc45c25aa5305b60f4c4af1557bee8cec0bf20`: `standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md` |
| Engine | ForgeV2 plugin 0.3.0, `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, installed at `/srv/forgev2`, unmodified. It stops any specialist run after **1800 seconds** and keeps no report from a stopped run |
| Assignment | The Orchestrator (Rogue) dispatches one Project Lead (`forgev2-pl` on DOCKER1). Roles: Engineer, Auditor, Tester, DevSecOps |
| Sole objective | Finish identity integrity. No new functionality |

### 1.1 Recovery exception (execution limit)

FOUNDRY permits at most **four** executions per specialist including the first, and states that a replacement Work Order cannot be created to bypass an exhausted limit (`work-order-contract.md`, "Execution and stop boundaries"; FND-036, FND-042). The identity delivery has used:

| | Engineer | Auditor | Tester | DevSecOps |
|---|---|---|---|---|
| CRM-IDINT-001 | 2 | 2 | 2 | 2 |
| CRM-IDINT-001R (one void Engineer run counted) | 2 | 1 | 1 | 1 |
| Used | **4** | 3 | 3 | 3 |
| This order, at most | +2 | +2 | +2 | +2 |
| Cumulative ceiling | **6** | **5** | **5** | **5** |

This order therefore exceeds the limit for every role and exists only under a **one-run recovery exception**, approved explicitly by the Product Owner and recorded on the Issue (gate E7). The exception covers this order only. It changes no FOUNDRY or ForgeV2 rule, resets no earlier counter, and authorises no further successor. The engine's own counter for this order starts at zero; that is not authority to use more than two.

## 2. Repository and workspace

| Item | Value |
|---|---|
| Base | the commit above: the final candidate of CRM-IDINT-001R. Keep what is sound; change only what this order requires |
| Branch and worktree | `forge/CRM-IDINT-001R2`, `/srv/CRM/worktrees/CRM-IDINT-001R2`, created by the engine |
| Platform reference | `/srv/CRM/wo/CRM-IDINT-001R2/reference/espocrm/` (`application/`, `vendor/`): EspoCRM sources from the pinned image, read-only, outside the repository, never committed. SHA-256 of the sorted file-hash list of `application/`: `c06e7a4650db42d81f90ae2f02e8b5b75aea5631ef4a1fd51088ca9a21e1d187`. **It is the authority for every platform name, signature, route and setting** |
| Protected | ForgeV2 and FOUNDRY installations; every existing ledger, branch, candidate and pull request; live runtimes |

## 3. Outcome and rulings

No identity relationship or identifier in ERm can be changed, removed or lost without authorisation and a durable audit record, by any user or service account, including administrators, through any application route. Legitimate changes remain available and audited.

**Identifiers:** FirmID = `Account.id`; ContactID = `Contact.id`. **Identity relationships:** a firm's parent firm; a contact's primary firm; a contact's other firm links; an enquiry's firm; a successor link.

The behaviour required by CRM-IDINT-001R sections 3.0 to 3.9, already built in the base, **stays required**: every route and account kind is refused unchanged or performed with its audit record; audit or fail; audit records protected; the primary firm is always a linked firm; firms and contacts are never deleted or merged; retire and supersede through the audited workflow; release settings (deleted-record cleanup off, audit cleanup off, user action history 6 months, sign-in records 13 months); identifiers issued only by ERm and CSV import refused for firms, contacts and enquiries; over-length input refused cleanly; the WIP item unchanged.

### Rulings

| | Ruling |
|---|---|
| R1 | **Enquiry merge is disabled** for every account. Ordinary enquiry work (create, read, edit, move to another firm, and deletion exactly as each account kind can do it at the base) is unchanged. Controlled soft-deletion and its audit coverage belong to CRM-AUDIT-001 and are not added here |
| R2 | **No committed unaudited identity relationship**, including when audit storage fails and every compensating operation fails |
| R3 | A browser script error raised by stock EspoCRM is excluded from ERm regression acceptance only where its **equivalence and harmlessness are demonstrated** (criterion A14). There is no general waiver |
| R4 | The release applies and reads back **all** required settings through its own scripts |
| R5 | **Administrators do not bypass identity integrity**, the script route included. Legitimate administration is preserved. EspoCRM core is not modified |

## 3A. Findings on the base (all blocking)

| # | Finding | Required correction |
|---|---|---|
| F-1 | Release settings: the release applies only the first of the four settings and still reports success. A command inside the read loop consumes the loop's input; the unit stand-in for that command does not read its input, so unit tests pass | S6, W1 |
| F-2 | `putback-swallowed` and `relation-after-hook-window`: relation changes and record creations are written before they are audited and are undone by compensating writes whose failure is ignored. Confirmed on a disposable runtime across link, unlink, link-list save and create routes | R2: S1, S2, S3 |
| F-3 | Enquiry merge is available (`enquiry-merge-scope`) | R1: S5 |
| F-4 | Live suite: the CSV import cells do not pass. The suite judges the import from a count the platform's import response does not return (`Tools/Import/Result`) | With S4 the platform refuses the import outright with a refusal status and the cells pass unchanged. W4: remove the count-based branch, so that only a refusal status proves a refusal |
| F-5 | Live suite: the enquiry merge route is sent a firm identifier as the enquiry identifier | With S5 the disabled action refuses before it looks the record up, so the cells pass unchanged. W4: send an enquiry identifier |
| F-6 | The changed existing test lines of CRM-IDINT-001R were not listed | W5 |
| F-7 | `script-route-identity-write`: the identity controls of the base do not cover the administrator script route. Found while preparing this order; neither earlier delivery nor its reviews covered it | R5: S4 |

**Correction to the earlier record:** the repair of `tests/unit/test_wip_link.py` (CRM-IDINT-001R 3.9) is present in the history of this base, with its out-of-scope detection test. It was reported as not delivered; that report was wrong. Keep the file as it is.

## 3B. Required approach

Established on an operator prototype of the base (section 11). The prototype is not a candidate, is not given to specialists and was never pushed. The approach below is required; if one part cannot be met safely, report it and stop that part.

| | Requirement |
|---|---|
| S1 | A save of a firm, contact or enquiry runs in **one database transaction**, through the platform's transactional-save setting in each entity definition |
| S2 | The three entities declare an ERm repository class in their entity definitions. Its relation object runs **each relate, unrelate and mass relate, with every hook and the audit, in one transaction** |
| S3 | **Compensating writes are removed.** No refusal depends on a later write. A refusal by an identity hook is still raised on every route that raises it at the base. No in-request memory of an audit record survives a rolled-back change. The minimum mechanism: the repository's save and the relation operations forget that memory when their transaction fails. A product path that rolls back an outer transaction after a successful identity write and then continues in the same request would be a finding |
| S4 | The platform's **system-write restriction** is declared for firm, contact, enquiry and the contact-to-firm link entity, so that script functions cannot create, edit, delete or link them. Link lists that only the link routes may change are refused inside a record save too, so a script cannot change them on the record it runs against |
| S5 | Enquiry merge is disabled in the enquiry's record definition |
| S6 | No command inside the release settings loop reads the loop's input |

### Consequences of the approach, for approval

| | Consequence |
|---|---|
| C1 | Administrator scripts, run directly or configured on a record type, **can no longer write firms, contacts, enquiries or the link record through the record functions, or set their fields**, identity fields or not. They still read them, compute, and write other records; the syntax check is unchanged. An in-memory addition to a contact's firm list on the record a script runs against stays possible and is audited. The release contains no configured script. The deployed custom metadata is read-only, so configuring one fails in this deployment: restriction of configured scripts rests on the reference (the same functions) and is not exercised live |
| C2 | CSV import of the three kinds is refused by the platform's own import check, before ERm's save check |
| C3 | Code or an extension that an administrator installs changes the application itself and is outside these controls. Documented as a limitation |

## 3C. Platform facts (verify each in the reference)

- `entityDefs.<Entity>.transactionalSave` makes a save, including link lists and after-save hooks, one transaction (`Core/Repositories/Database.php`, `ORM/Repository/RDBRepository.php`, `ORM/TransactionManager.php`; nested transactions use savepoints).
- `entityDefs.<Entity>.repositoryClassName` selects the repository (`Core/ORM/ClassNameProvider.php`), so the class can live under `Classes/`. The platform defines no repository of its own for firm, contact or enquiry.
- Every ORM relate, unrelate and mass relate goes through the relation object from the repository's `getRelation` (`ORM/Repository/RDBRelation.php`; the class is not final).
- `entityAcl.<Entity>.systemWriteForbidden` is read by `Core/Acl/SystemRestriction.php`, used by the script record and entity write functions (`Core/Formula/Utils/EntityUtil.php`, `Core/Formula/Functions/`) and by `Tools/Import/Import.php`. It does not restrict the record API.
- A script addition to a link list of the record in hand is checked per field, not per entity, and is persisted by that record's save (`Core/FieldProcessing/Relation/LinkMultipleSaver.php`).
- `recordDefs.<Entity>.actions.merge.disabled` is enforced by `Core/Action/ActionFactory.php`.

## 4. Delivery boundary

| | |
|---|---|
| In scope | `custom/Espo/Custom/`, `scripts/deploy_release.sh`, `tests/`, `docs/` |
| Must not change | `deploy/`, `load/`, `client/`, `config/`, `.forge/` of other orders, `work-orders/`, root product records, EspoCRM core, `tests/unit/test_wip_link.py` |
| Excluded | enquiry deletion audit (CRM-AUDIT-001); FirmGroup; user types, menus and sign-in security; any WIP change; HTTPS and infrastructure; refactoring; any other finding or improvement |
| Dependencies | no new package, image, extension or vendored file; no secret in the repository |
| Data and systems | synthetic data only. No beta, production, real data, NAS or Salesforce. No deployment or merge |

Existing tests change only where they contradict this order, and then are replaced with equally strict ones. Nothing else is removed or weakened.

## 5. Work items, in this order

| | Item | Done when |
|---|---|---|
| W1 | S6 and the unit stand-in: the stand-in for the platform command reads its standard input as the real command does | the new stand-in fails the base script and passes the candidate |
| W2 | S1 to S5 | `docs/IDENTITY-INTEGRITY.md` describes the new behaviour and C1 to C3, and no longer the compensation residual |
| W3 | Unit tests (detail below) | A12 |
| W4 | F-4 and F-5: corrections to two tests, not to the product. An import that answers success is never a refusal (the unit assertion that allowed it is reversed, which is stricter); the enquiry merge route targets an enquiry | live cells and unit tests pass; no assertion weakened |
| W5 | F-6: `docs/IDENTITY-TEST-CHANGES.md`, generated by command from `git diff -U0 65eab11d68583555b378dd2bff36a1d237db3d1a` over the existing test files changed since that commit (this order's changes and CRM-IDINT-001R's), one reason per file naming the finding or ruling | the Auditor checks each changed line |

**W3 detail** (measured by an operator rehearsal on the prototype):

1. With S1 to S5 in place and the base tests unchanged, **30 unit checks fail**, all in `tests/unit/test_identity.py`: the PHP stand-ins have no transaction.
2. Give the stand-ins a transaction that restores all rows on any failure, the transaction manager and the relation base class, within the rules of `test_platform_reference.py`. The fake platform takes transactional save and the repository class from the entity definitions, and its relate, unrelate and mass relate go through the product's relation class when that repository is declared, so removing either is detected.
3. Expected output changes only where a failed change is now rolled back completely, partial audit rows included (five lines in the rehearsal). The two test methods that assert the old residual assert that nothing remains.
4. Replace the three mutations that remove compensating writes with mutations that remove the transaction (save) and the atomic relation (relate, mass relate).
5. After steps 2 to 4, **one check still failed**: the mutation `relation hook runs after the platform's own` is no longer noticed. Add a scenario that detects the hook order, or show from the reference that the order no longer matters and replace it with an equally strict mutation.
6. Add tests that fail without each of: S3's rule on in-request memory, S4 (both parts) and S5.

A route found that these items do not cover is reported, not ignored.

## 6. Acceptance criteria

A1 to A5, A7 to A12, A15, A16 and A18 of CRM-IDINT-001R apply unchanged except where restated here. All are mandatory.

| AC | Criterion | Evidence |
|---|---|---|
| A1 | The live matrix covers every route, relationship and account kind; each cell is refused unchanged or performed and audited | matrix report: 100 % pass |
| A2 | Every human role allowed to edit a relationship at the base can still change it, audited | suite |
| A3 | With audit storage unwritable, 0 identity relationship changes succeed on any route | suite, operator proof |
| A4 | Identity audit records cannot be edited or deleted by any account | suite |
| A5 | 0 new contacts break the primary-firm rule; the exceptions report changes nothing | suite |
| A6 | Delete, mass delete and merge of firms and contacts are refused for every account, and **enquiry merge likewise** | suite, operator proof |
| A7 | On a stack configured **only by the release scripts**, all four settings read back correctly and the cleanup job removes 0 identity records, audit records and audit-history entries | operator proof, suite, unit tests |
| A8 | Supplied identifiers are never used; CSV import is refused | suite |
| A9 | Over-length input returns a validation error and changes nothing | suite |
| A10 | Every identifier resolves; invalid successors are refused | suite |
| A11 | Synthetic seed and loader: no new refusal, totals equal to the base run, second load writes nothing | operator report |
| A12 | Unit suite as non-root with PHP present: 0 failures, none skipped for lack of PHP (base: 716 tests, 0 failures) | operator report |
| A13 | On the same unchanged candidate: Auditor **PASS**, DevSecOps **PASS**, Tester **PASS**, or **INCONCLUSIVE solely for browser and live-runtime behaviour** with every sandbox-executable criterion passing | ledger |
| A14 | Operator runtime and browser proof (section 8) passes on that candidate. A browser script error is excluded only if the same flow on the pinned **stock** image with no ERm code, refused by the server, raises the same error (type and status), the data is unchanged and the page stays usable on both, and the error originates in platform code. Each excluded error is listed with both observations. Any other script error fails | operator report |
| A15 | Secret scan: 0 findings; no host address or credential in the change | scan |
| A16 | The platform-reference test runs with `CRM_PLATFORM_REFERENCE` and PHP, not skipped | delivery record, operator report |
| A17 | Unit suite on the candidate merged with `main` at `4183e25aad8343a5bcd7e320d0d1e032f6871ec9`: 0 failures (`tests/unit/test_wip_link.py` resolves to the candidate's file). **Operator evidence**: that commit is not in the specialists' object store, and no specialist verdict depends on it | operator report |
| A18 | Every refused cell asserts the control's own refusal and shows the route exists | suite |
| A19 | With audit storage unwritable **and** the database refusing every compensating write, on link, unlink, firm and contact link-list edit, successor change, record edit and record create routes: the request does not succeed and relationships and record counts are exactly as before; the same operations without faults succeed and are audited. For A19, A7 and A21 the operator proof is the evidence that counts: the live suite does not exercise these conditions | operator proof |
| A20 | Enquiry merge refused for every account kind; ordinary enquiry work as R1 | operator proof, suite |
| A21 | Through the administrator script route: no firm, contact, enquiry or link is created, deleted, marked deleted, linked or changed except by an audited change that leaves nothing when the audit fails; no supplied identifier is used. The script syntax check, computing scripts, reading identity records and writing other records still work | operator proof, unit tests |

## 7. Execution, early feedback and stop conditions

- **Budget:** at most **2** executions each of Engineer, Auditor, Tester and DevSecOps. A void run counts. Any Engineer change restarts the three reviews. The engine would allow more; they are not available.
- **Engineer time limit (binding in every Engineer prompt):** the prompt states the UTC dispatch time and a deadline 20 minutes later. The Engineer works W1 to W5 in order and checks `date` between items. At the deadline it stops changing code and reports `STATUS: completed` with an `UNFINISHED:` list; it reports `blocked` only for a real blocker, never for time. The report is returned by minute 25.
- **Early feedback before the last Engineer execution:** after Engineer execution 1 returns and **before** the first commit, the Orchestrator runs the operator gate on that uncommitted work: release scripts over the release beta runs today, settings read back, data preserved, A19, A20, A21, then the candidate's live suite (about 40 minutes in rehearsal). The Project Lead waits for the gate file for at most 75 minutes. `FAIL`: Engineer execution 2 is dispatched with the report, before any commit. `PASS` with an empty `UNFINISHED:` list: commit and review. `PASS` with unfinished items: Engineer execution 2 completes them before commit. **Engineer execution 2 is never dispatched before the gate report exists**; if the window passes without one, the Project Lead commits and reviews, and includes the report later with any review findings. The report goes to the Engineer only, never to a reviewer, and replaces no review or criterion.
- The early gate cannot judge S3's rule on in-request memory (every lab request starts clean). Its only evidence is the unit test of W3 step 6 and review.
- A gate report that arrives after Engineer execution 2 is information only. Before accepting, the operator proof runs again on the unchanged final candidate.
- **BLOCKED and escalated:** exhausted budget, a failed gate of section 9, a missing or altered reference, a needed change outside section 4, or a criterion that cannot be met safely. Open findings at the limit are escalated. **No further successor.**

## 8. Verification

| Role | Assigned verification |
|---|---|
| Engineer | W1 to W5; A16 with the reference; platform citations for every interface relied on; unit counts before and after |
| Auditor | conformance to sections 3 to 6, every platform claim checked in the reference, W5 complete with each changed test line checked, no weakened assertion |
| Tester | every criterion executable in the sandbox, including mutations showing new tests fail without the control; states what was not executed. A11, A14, A17, A19 and the live parts of other criteria, A20 and A21 included, are operator evidence |
| DevSecOps | authorisation and bypass review of every server change; R2 on every relation write path in the reference that the product exposes; R5 on every administrator write path the product exposes; no secret, host or new dependency |

Specialists have no network, Docker, browser or EspoCRM runtime. The browser gate of the engine applies as before: a `DELIVERED` close is not expected on this host, an `ESCALATED` close solely for browser and live behaviour is intermediate, and only section 6 accepts.

**Operator proof (no specialist executions),** on a disposable runtime of the pinned images with synthetic data, on a host where the release scripts' fixed project names cannot collide with a live stack: clean deployment of the current release, upgrade to the unchanged candidate with the real release scripts, **no application setting applied by any test step except the candidate's own provisioning, which sets none of the retention settings**; settings read from the running platform; the live suites; A19; A20; A21; A11; A12; A16; A17; A15; PHP syntax; the browser check per human account kind and the stock-platform control of A14. Evidence holds no credential.

## 9. Entry gates

| Gate | Requirement |
|---|---|
| E0 | The findings of section 3A reproduced on the base by the operator gate (recorded on the Issue) |
| E1 | Architect exact-version approval: path, commit, file SHA-256, base, budget, rulings R1 to R5, approach S1 to S6 and consequences C1 to C3 |
| E2 | `BASE` and `KNOWN_COMMIT` resolve in the Project Lead repository; `forge-start` accepts the base on a scratch copy; unit suite there: 0 failures |
| E3 | Engine and plugin as pinned and unmodified; no `CRM-IDINT-001R2` branch, worktree, ledger or record exists |
| E4 | Runner isolation established immediately before dispatch; a specialist can read the reference and cannot write it; digest matches section 2 |
| E5 | No other open ledger or Project Lead session for this project |
| E6 | The order given to the Project Lead is read-only and byte-identical to the approved file |
| E7 | **Product Owner approval of the one-run recovery exception of 1.1**, recorded on the Issue, naming this order, commit and the cumulative ceiling |

## 10. Communications and completion

- **Issue:** #92. Progress is event driven (gates, dispatch, candidate, verdicts, close, blockers). Escalation: Project Lead to Orchestrator; Orchestrator to the Architect and the Product Owner.
- **Logs (writer: Project Lead):** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-IDINT-001R2/`, published to `.forge/CRM-IDINT-001R2/` on the branch. The repository is public: records name findings by safe identifiers and carry no exploit detail, address, credential or personal, customer or firm data.
- **Completion report:** outcome, changed paths, base and candidate commits, A1 to A21, verdicts and the candidate each assessed, execution counts, evidence locations, deviations, limitations. Output: candidate branch and draft pull request. Integration to `main` is a separate reviewed step.

## 11. Basis for approval

Operator measurements, disposable lab, synthetic data, release deployed only by its own release scripts. The prototype is the base with S1 to S6, except S3's rule on in-request memory (12 files, 111 lines added, 158 removed). That rule's minimum mechanism was added afterwards on a copy: with the rehearsed test changes the unit result was unchanged, and the settings, preservation, fault, script and enquiry checks passed; the live suite, loader and browser were not repeated on that copy, and no test yet exercises the rule.

| Check | Base | Prototype |
|---|---|---|
| Upgrade; existing data preserved | pass | pass |
| Settings read back (A7, settings part) | fail: one of four applied | pass |
| Database faults (A19) | fail: 15 of 61 checks | pass: 57 checks, 0 failures |
| Script route (A21) | fail: 15 of 48 checks | pass: 48 checks, 0 failures |
| Enquiry merge refused; ordinary work (A20) | fail: merge accepted for administrator and manager | pass |
| Live identity suite (A1 to A5, A7 to A10, A18) | fail: 21 failures | pass: 10 of 10, all 400 matrix cells, **suite unchanged** (1865 s) |
| Seed and loader (A11) | | no failed write; second load writes nothing; totals equal to the earlier run except one record that an access suite not run here creates |
| Browser, five refused flows against stock (A14) | | same errors as stock (delete, panel unlink, mass delete, merge); none on panel removal; data unchanged and page usable on both |
| Unit suite, base tests | 716 pass | 30 fail (W3, step 1) |
| Unit suite, rehearsed test changes (W3 steps 2 to 4 and the W1 stand-in) | | 716 run, 715 pass, 1 fails (W3, step 5) |

Reading the figures: of the base's 15 script-route failures, three leave only a soft-deleted link row behind a refused request, not a live unaudited link. The fault checks number 61 on the base and 57 on the prototype because a script case refused outright needs no fault sub-checks.

### Fit within the 30-minute limit

| Item | Measured size in the prototype or rehearsal |
|---|---|
| W1 | three redirections; one line in the stand-in, which fails the base script (7 checks) and passes the corrected one |
| W2 | 11 files, mostly small metadata and two short classes; the largest edit removes compensation code. S3's memory mechanism adds about 30 lines |
| W3 | 4 test files, about 140 lines added and 30 removed, plus steps 5 and 6, which were **not** rehearsed. Steps 2 to 4 and the W1 stand-in took about four minutes including unit runs, by an operator who already knew the code |
| W4 | two small test corrections, **not** rehearsed |
| W5 | generated by command plus one reason per file |

Unit suite about 75 seconds. Earlier Engineer runs: 28 min 20 s (the first full build), 2 min 41 s, one stopped at 30 min with a much longer list, 2 min 10 s.

**Judgement: expected to fit with execution 2 held as correction capacity. Not proven:** operator rehearsal time does not measure an Engineer, and the longest comparable run was close to the limit. Protection: product behaviour is ordered first so the early gate can judge it even if tests are unfinished; a deadline at minute 20 with a partial report; the second execution held until the gate has reported. If execution 1 leaves tests unfinished, execution 2 carries both them and any correction.

### Limits of this preparation

The lab is not DOCKER1 (the release scripts' fixed project names would collide with the live stacks). For A11 the lab clients reached the application through an operator relay; application and settings were unchanged. Not run: the access suite, the browser check of legitimate editing per account kind, A16 to the letter on a candidate, A17, the secret scan, TLS. Nothing on DOCKER1, the live beta or any other application was changed.
