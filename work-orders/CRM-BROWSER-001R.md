WO: CRM-BROWSER-001R
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: f7dd4d2eb79b3bc82308efb0190f377988e81c46
KNOWN_COMMIT: f7dd4d2eb79b3bc82308efb0190f377988e81c46
BROWSER: yes

# CRM-BROWSER-001R: browser assurance, one correction round

## 1. Identity, purpose and authority

| Item | Value |
|---|---|
| Version | v1.0, 2026-11-27, prepared for exact-version approval. **Not in force and not to be dispatched** without it |
| Issue | https://github.com/infosec-estateresearch/CRM/issues/102 |
| Priority and parent item | P0. CRM-PBI-034, ERm journeys |
| Why | CRM-BROWSER-001 closed **ESCALATED**: two blocking review findings, Engineer budget used. Its candidate is the base here and is not accepted |
| Parent order | CRM-BROWSER-001 v1.1, commit `8ea549a95e0cdbe45ff936022afa79c6cb4648c4`, file SHA-256 `b74579d87d456f33e721d096cc0175d96a1a72372d274d1ba73295dad8b0f445`. Given to the Project Lead and specialists as a read-only copy at `/srv/CRM/wo/CRM-BROWSER-001R/reference/parent-order.md` |
| Governing FOUNDRY | `maff0000/foundry@39cc45c25aa5305b60f4c4af1557bee8cec0bf20`: `standards/work-order-contract.md`, `standards/secure-engineering.md`, `standards/product-records.md` |
| Engine | ForgeV2 plugin 0.3.0, `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, at `/srv/forgev2`, unmodified. It stops any specialist run after 1800 seconds and keeps no report from a stopped run |
| Assignment | The Orchestrator (Rogue) dispatches one Project Lead (`forgev2-pl`). Roles: Engineer, Auditor, Tester, DevSecOps |
| Sole objective | Finish the browser assurance runner. No new journey area, no product change |

### 1.1 Execution budget (the approval states option A or option B)

| | Engineer | Auditor | Tester | DevSecOps |
|---|---|---|---|---|
| Used by CRM-BROWSER-001 | 3 | 1 | 1 | 1 |
| **Option A**: this order, at most | 1 | 2 | 2 | 2 |
| Option A cumulative | **4** | 3 | 3 | 3 |
| **Option B**: this order, at most | 2 | 2 | 2 | 2 |
| Option B cumulative | **5** | 3 | 3 | 3 |

A reviewer's second execution only replaces a void run. There is one review round in both options.

**Option A** stays inside the four executions per specialist that FOUNDRY permits and the parent order's "at most 4 per role including any separately approved corrective successor". It leaves one Engineer execution and **no operator gate**, because nothing could act on its report: a runtime defect found afterwards cannot be corrected under this order.

**Option B** exceeds that limit by one Engineer execution. FOUNDRY states that a replacement Work Order cannot be created to bypass an exhausted limit (`work-order-contract.md`, "Execution and stop boundaries"), so option B exists only as a **one-run recovery exception**, approved explicitly by the Product Owner and recorded on the Issue (gate E7). It adds an operator gate between the two Engineer executions. It changes no FOUNDRY or ForgeV2 rule, resets no counter and authorises no further successor.

The engine's own counter for this order starts at zero; that is not authority to exceed the approved option.

## 2. Repository and workspace

| Item | Value |
|---|---|
| Base | the commit above: the final candidate of CRM-BROWSER-001. Keep what is sound; change only what this order requires |
| Branch and worktree | `forge/CRM-BROWSER-001R`, `/srv/CRM/worktrees/CRM-BROWSER-001R`, created by the engine |
| Platform reference | `/srv/CRM/wo/CRM-BROWSER-001R/reference/espocrm/`, read-only, outside the repository, never committed. Same content and digests as the parent order, section 2. **It is the authority for every platform name, route, setting and screen** |
| Protected | ForgeV2 and FOUNDRY installations; every existing ledger, branch, candidate and pull request; live runtimes |

## 3. Outcome

The parent order's sections 3, 3C, 4, 5 and 6 **stay required**, as amended in section 3A, together with the corrections of sections 3B and 3C. Where section 3B, 3C or 3D states a platform fact that differs from the parent's section 3C, this order's statement applies.

## 3A. Amendments to the parent order (need the Product Owner's approval)

The base product does not do two things the parent's section 3.3 expects, and the delivery boundary excludes product changes. The base candidate already declares them as they are; approval of this order accepts that. The third row defines the comparison for criterion A10 where the parent's wording cannot be applied to a refusal that only ERm makes.

| Parent text | At the base | Required declaration | Carried to |
|---|---|---|---|
| J4 "see them on the related panels" | the firm screen has **no branches related panel** | contacts and enquiries are shown on the firm's Account tab; the branches panel is a step declared `not offered` for every kind, checked after that tab's other panels are drawn; the branch's parent is checked on the branch's screen and by API | a separate firm-screen order |
| J5 "Identity audit records offer no edit or delete" | the administrator **is offered both**; the server refuses both | administrator: `refused` (attempted, refused with a message, record unchanged, page usable); other kinds: `not offered` | CRM-ACC-001 (hide) |
| A10 "the same refused flow on the pinned image with no ERm code" | where ERm's own control makes the refusal, the stock image has nothing that refuses that flow | the comparison is a refusal by the platform's own permission rules with the same method, kind of route and status: same error type and message handling, data unchanged, page usable (**not yet executed**) | operator report |

Also recorded, with no change to the parent text: the create screen leaves an enquiry's Assigned User empty and an ER Staff account cannot then edit the enquiry it created, so the J1 step of each non-administrator kind assigns the signed-in user on that screen; removing a contact's primary firm on the contact **edit form** is accepted because the platform sets another linked firm as primary in the same save, which the identity rule permits (J5 unlink uses the firm's contacts panel); and the administration page's vendor frame is switched off in the run's own stack only.

## 3B. Review findings on the base (all required, whatever severity they were given)

| # | Finding | Required behaviour |
|---|---|---|
| F-1 | `policy-run-allowlist-gaps`: the Docker command guard is a list of forbidden flags | `docker run` is admitted only from an **allow-list** of the flags the runner uses. It requires an explicitly named network of this run (the package-fetch network or the stack network), `--cap-drop ALL`, `--security-opt no-new-privileges` and `--read-only`; `--user` only as the invoking user's own user and group. The only mount sources are the repository root (read-only), the run's output directory, and the run's own run directory or what the runner made inside it. Everything else is refused in both spellings, including `--volume`, a mount of a repository subdirectory, any other security option, another user, an entrypoint, a process-limit change and a missing network. A test covers each refusal and shows every command the runner issues is admitted |
| F-2 | `fault-subset-silent-pass`: a fault can have no effect on a journey subset and the run passes | every fault takes effect in whatever journeys are selected, or the combination is refused before anything is created. A fault run whose fault was never applied exits non-zero. Tests cover a subset without J1 for each fault |
| F-3 | `partial-failure-unnamed` | a run that stops midway names the failing step and records it as failed in the results and the manifest (parent 3.6) |
| F-4 | `late-events-dropped` | a step is judged only after the page is idle (item S-1); an error or failed request that arrives afterwards fails that step; none is discarded (parent 3.4) |
| F-5 | `weak-tests-surviving-mutants` | tests fail when the step-record check of `verify` or the Docker socket check is removed |
| F-6 | `subnet-host-route` | the run's subnet overlaps no route in the host's route table other than a default route (read from the host, without inspecting other Docker resources); if no free subnet is found the run fails saying so; Docker's refusal of an overlapping network is still retried; the range is documented |
| F-7 | `verify-symlinked-dir` | `verify` rejects any link in the evidence and any entry that is neither a directory nor a regular file, and requires the target proof recorded as matched |

## 3C. Runtime findings on the base (operator observation, synthetic data, disposable lab; all required)

On a tree identical to the base, 129 of 136 steps passed. The unit suite passed (779).

| # | Observed | Required behaviour |
|---|---|---|
| R-1 | `J1/create-enquiry`: after one link field has been chosen on a screen, its suggestion list stays in the page, hidden; the next choice clicks that hidden list | choose the **visible** suggestion that carries the wanted name |
| R-2 | `J4/branch-parent-screen`: a link field on a record screen is rendered as an anchor with an address and **no** `data-id` (`client/res/templates/fields/link/detail.tpl`) | identify the parent by its record address |
| R-3 | `J5/audit-edit`: the audit edit form has no name field. Edit, then Save with nothing changed, sends the update, which the server refuses with the declared events; the screen stays in edit mode | no field is filled; the record screen's own buttons are shown usable after Cancel; the stored record is compared before and after |
| S-1 | Screens change without a new document, so a page load state proves nothing after the first load. Ticking list rows before the search result was drawn lost the selection (an intermittent failure) | before acting on a drawn or re-drawn screen (first render, search, tab, dialog) the runner waits until **no request has been in flight** for a short quiet period; after a search it also waits for the search's own response |
| S-2 | Two of thirteen starts in the operator's last series of full-command runs failed: the application container exited during start. The cause was not captured; fifteen further start-only repetitions succeeded | on a failed start the runner prints the end of this run's application and database logs, with the run's own secrets replaced, before removing the stack. The run still fails: there is no automatic retry |
| V-1 | "Not offered" is concluded at once after a click, so a menu not yet drawn would read the same | `not offered` is concluded only after the holding menu or screen is shown with an entry that account does have (record menu, list actions menu, panel row menu, audit record menu) |
| V-2 | A refused list or merge step does not prove the other records unchanged, or the page usable | every refused step proves **every** record involved unchanged and the page usable afterwards (parent 3.4) |

A throwaway operator copy of the base containing **only** R-1 to R-3, S-1, V-1 and V-2 (none of F-1 to F-7 or S-2) gave this result: the full command passed all 136 steps in two consecutive runs with identical per-step verdicts (journeys about 6.5 minutes each) and a clean secret scan of both evidence sets. On the same copy each fault made the run exit non-zero naming failed steps, an interruption (`SIGINT`) exited non-zero, and no resource of any run remained. That copy is not a candidate, is not given to specialists and was never pushed.

## 3D. Mechanisms observed to work (that copy; verify against the reference)

| Item | Mechanism |
|---|---|
| R-1 | among `.autocomplete-suggestion:visible`, the first that contains the wanted name |
| R-2 | `.field[data-name=parent] a[href$='#Account/view/<id>']` |
| R-3 | Edit, then `button[data-action=save]` with no field filled; after the refusal `[data-action=cancelEdit]`, after which `.detail-button-container [data-action=edit]` is visible |
| S-1 | per page, count requests from the `request`, `requestfinished` and `requestfailed` events; idle is 600 ms with none in flight, bounded by the step time limit. Applied after every screen opens, after a tab or dialog opens, and before a step is judged. A page load state does not serve. A search additionally waits for the `GET` response whose address contains `textFilter` |
| V-1, record menu and audit record menu | open the visible `.detail-button-container .dropdown-toggle`; wait for `[data-action=viewUserAccess]`; on the audit record, Escape closes the menu before Edit is chosen |
| V-1, list actions menu | `.actions-button`; wait for `a[data-action=follow]` |
| V-1, panel row menu | the row's `.dropdown-toggle`; wait for its `[data-action=quickEdit]` |
| V-1, branches panel | wait for the `contacts`, `opportunities` and `documents` panels |
| V-2, stored data | read every involved record by API before the action and compare the whole answer afterwards, lists in a fixed order; for firms also the list of linked contacts |
| V-2, page usable | in the same application instance open the entity's list (`tr[data-id]`), then the record; no `.modal` may remain visible |
| F-4 | the browser library delivers page events only during a browser call: after judging, make one that gives the page a window (leave the page, wait 300 ms), then compare the event count; a new event fails the judged step. Two earlier operator runs that watched this way, before V-2 was complete, saw none |

The base already opens a blank page before every step.

## 4. Delivery boundary

As the parent order, section 4, measured from this order's base: `tests/browser/`, files `scripts/browser_assurance*`, `tests/unit/`, `docs/BUILD.md`, `security/EXTERNAL_CODE_REGISTER.yaml`. Nothing under `custom/`, `client/`, `config/`, `deploy/` or `load/`; no existing script outside the runner; no new dependency or image; synthetic data only; no beta, production, real data, off-host store or Salesforce access; no deployment or merge.

An existing assertion changes only where a requirement of this order changes the behaviour it asserts, and is then replaced by one at least as strict. Every changed existing test line is listed; the Auditor checks each.

## 5. Acceptance criteria

All are mandatory, on the new candidate.

| AC | Criterion | Evidence |
|---|---|---|
| A1 to A13 | As the parent order, section 5, with the journeys as amended in section 3A | as there |
| A14 | Every item of sections 3B and 3C holds. Each has a test that fails without it where such a test can run without a browser or a live runtime; otherwise, and always for R-1 to R-3, S-1, S-2, V-1 and V-2, a stated operator check | delivery record naming the test or check per item; review; operator report |
| A15 | On a disposable runtime: each fault with a journey subset that excludes J1 exits non-zero naming a step, or is refused before creating anything; and the secret scan is shown to detect a planted secret in a copy of the evidence | operator report |

A review finding is **blocking** only when it names the mandatory criterion or required item it shows unmet; any other finding is advisory and is recorded.

## 6. Verification by role

As the parent order, section 6, including platform fidelity. The Auditor and Tester also check each item of sections 3B and 3C. DevSecOps also checks the allow-list of F-1 and the log output of S-2 for secrets. The sandbox has no network, Docker, browser or EspoCRM; the Tester reports browser behaviour as inconclusive, never passed.

## 7. Execution and stop conditions

- **Budget:** the approved option of section 1.1. A void run counts. There is no correction round after review.
- **Engineer time limit (in every Engineer prompt):** the UTC dispatch time and a deadline 20 minutes later. The Engineer checks `date` between items, takes the items in the order F-1, F-2, R-1 to R-3, S-1, V-1, V-2, F-3, F-4, F-7, F-5, F-6, S-2, and runs the unit suite before reporting. At the deadline it stops and reports `STATUS: completed` with an `UNFINISHED:` list, `blocked` only for a real blocker. The report is returned by minute 25.
- **Option A:** one Engineer execution, then commit and review.
- **Option B:** Engineer execution 1; **gate G1** on the uncommitted work (the Orchestrator reads every file that would run, then runs the unit suite, the full command, each fault and an interruption on a disposable lab and returns a report); Engineer execution 2 before any commit, for the G1 findings and anything unfinished; then commit and review. If G1 is PASS with nothing unfinished, execution 2 is not used. The Project Lead waits at most 90 minutes for the G1 file and never dispatches execution 2 before it exists; if the window passes, it commits what exists and reviews it. Gate reports go to the Engineer only and replace no review or criterion.
- **BLOCKED or escalated:** an exhausted budget, a failed entry gate, a missing or altered reference, a needed change outside section 4, or a criterion that cannot be met safely.

## 8. Operator proof (no specialist executions)

As the parent order, section 8, plus A15, on the unchanged candidate: the documented command twice with identical verdicts; each fault; interruption; the isolation probe with a positive control; `verify` against genuine and tampered evidence; teardown and credential checks; the stock-platform confirmation; the unit suite with PHP; secret scan. No diagnostic bypass or patch. **Start failures:** a run of this proof, or of gate G1, that fails because the stack did not start, before any journey ran, is **no result**: neither a pass nor a detected fault. The Orchestrator records the output and repeats that check once (for A1, both consecutive runs); a second start failure of the same check fails it. A failure of this proof is reported to the Product Owner; no execution under this order remains to correct it.

## 9. Entry gates

| Gate | Requirement |
|---|---|
| E0 | CRM-BROWSER-001 is closed ESCALATED; its ledger, branch and draft pull request are unchanged |
| E1 | Exact-version approval: path, commit, file SHA-256, base, budget and the decisions of section 11 |
| E2 | Base resolves in the Project Lead repository; `forge-start` accepts it on a scratch copy; unit suite there: 0 failures |
| E3 | Engine and plugin as pinned; no `forge/CRM-BROWSER-001R` branch, worktree, ledger or record exists |
| E4 | Runner isolation established immediately before dispatch; a specialist can read the platform reference and the parent order and cannot write them; digests match |
| E5 | No other open ledger or Project Lead session for this project |
| E6 | The order given to the Project Lead is read-only and byte-identical to the approved file |
| E7 | Option B only: the recovery exception of section 1.1 is recorded on the Issue before dispatch |
| E8 | The three operator checks not yet run on the base pass on it before dispatch: the foreign-target probe with its positive control (A6), the credential check of the evidence (A7) and the A10 comparison of section 3A. If one fails, nothing is dispatched and the order returns to the Product Owner |

## 10. Communications and completion

As the parent order, section 10, with records under this order's identifier. The repository is public: records carry no exploit detail, address, credential or personal, customer or firm data. Output: candidate branch and draft pull request. Integration to `main` is a separate reviewed step.

## 11. Decisions the approval must state

1. Dispatch of this exact version, and **budget option A or option B** of section 1.1; B is also the explicit recovery exception.
2. The amendments of section 3A (J4 branches panel, J5 audit records, the A10 comparison) and the recorded base behaviours.
3. The definition of a blocking finding in section 5.
4. The start-failure rule of section 8.
