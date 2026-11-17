WO: CRM-WIP-INT-001-W
LANE: Helm (the existing WIP development lane; CGPT gate G4, option T2)
REPO: infosec-estateresearch/WIP
BASE: 91b2af19877b498ed307ee9f1218b3243b2b60ba (WIP `main`, 2026-06-08; GitHub `main` equalled it on 2026-11-17)
WIP LANE NUMBER: WO-28 (provisional: the next number after the last merged WO-27; Helm may renumber, which changes only the branch name and commit prefix)

# CRM-WIP-INT-001-W: the WIP read-only account endpoint (Part W of CRM-WIP-INT-001)

- **Version:** v1.0 **DRAFT**, 2026-11-17. **Not approved. Helm must not start.** Work starts only after a CGPT exact-version approval naming this path and the commit that contains it, relayed through Matt and recorded on CRM Issue #71.
- **Prepared by:** Rogue (Orchestrator, DOCKER1), on CGPT's instruction of 2026-11-17 ("prepare the separate, bounded WIP Work Order immediately using T2; use the approved Part W contract, with no additional WIP functionality").
- **Authority:** CGPT G4 decision, T2 (Issue #71, comment 6948227144), and CGPT's approval of `CRM-WIP-INT-001` v1.1 (comment 6948627548). Architecture: the approved amendment `docs/architecture/crm-wip-integration-amendment.md` (commit `194f0e2b94041b2a7922cfd6cfae8cf595357a42`, SHA-256 `7838cf44bf3330e50d42dfe958f26ff84088c50db5a508579f44338da8f15734`).

## 1. The contract (normative, not restated)

The contract is **§3 "Part W: WIP read-only endpoint" of `work-orders/CRM-WIP-INT-001.md`**, as approved: commit `a657f13d40f46a2c52395b91bafb5b03100b20de`, merged at `37aaba1177b59bbb4a9e54013baab4a255131d29`, file SHA-256 `c5861f2d0a8a8ac5d4e64f8eefa931e1e5d4978b64e2878142a4f835ae7d4d86`, together with the response and error contract in the amendment §5. Implement exactly that: seven numbered behaviours, three SQL statements, the 409 rule for ambiguous duplicate cases, and the unit tests listed there.

- **Same text in the recovery WO.** `work-orders/CRM-WIP-INT-001R.md` carries §3 byte-identically (SHA-256 `f627fc2ea5f96df5b7288920b3eebc881b7258c021018c2bfb11d2b9517c725b`, over the bytes from the line `## 3. Part W` up to, not including, the line `## 4. Part B`, in both `CRM-WIP-INT-001` v1.1 and `CRM-WIP-INT-001R`). Either file may be cited; the content is the same.
- **No other WIP functionality.** On any conflict between this WO and §3, §3 prevails. Report the conflict; do not resolve it by choice.
- **Files:** `src/wip_web/routes/api_account_wip.py`, `src/wip_web/api_app.py`, `tests/unit/test_api_account_wip.py` (all new) and the three variable names in `.env.example`. Imports follow the existing `src.` style. **Nothing else changes.** No existing route, template, migration, view, grant, systemd unit, `pyproject.toml` or GUI file is touched.

## 2. Lane rules (what this WO adds to §3)

1. **Do not disturb the live installation.** Its checkout runs the hourly timers. Create the branch `wo/WO-28-account-wip-api` from the base in a **separate worktree or clone**. Never switch branches or edit files in the live checkout. Record `main` and `git status` of the live checkout before and after; both must be unchanged.
2. **No database, no secrets, no services.** Unit tests use fakes only and make no database connection. Never read or print the WIP environment file. Never use the `wip_app` credentials. No migration, grant or user creation. No `systemctl`, start, stop, restart or enable of any service or timer. No permanent API service is created.
3. **Which tests may run.** Some existing tests load the live environment file and touch the live database (for example `tests/unit/test_wo27_wip_entry.py`). **Never run the whole suite.** Run the new test file, plus the existing DB-free tests, chosen by explicit path. Helm lists in the report which existing files were run and why they are DB-free (the fake-connection `tests/unit/test_wip_web.py` is the reference).
4. **Commits.** Identity through the environment only (`GIT_AUTHOR_NAME=Helm`, `GIT_AUTHOR_EMAIL=helm@noust.ai`, and the same for the committer). Never change git config. gitleaks before each commit. No force-push, no `reset --hard`, no `--no-verify`. Commit messages start `WO-28:` and end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
5. **Delivery.** Push the branch and open a **draft** PR whose description ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. **Do not merge.** The PR stays unmerged pending acceptance. No secrets, addresses, customer or real firm data in the PR, the tests or the fixtures (use obviously fake ids).

## 3. Independent tests and review (required by CGPT)

| Step | Who | What |
|---|---|---|
| Implementer run | Helm | New tests and the listed DB-free existing tests pass. Report counts before (at the base) and after |
| **Independent re-run** | Rogue | Fresh scratch clone of the PR head, not Helm's worktree. Run the same explicit test list. **Mutation check:** revert each guard in turn (token compare, authenticate-before-validate order, id validation, the `n` versus `d` ambiguity check, the ban on `wip_app` settings, decimal strings) and show that a test fails each time |
| **Independent review** | Reviewer independent of Helm, **named by CGPT when approving this WO**. Proposed: CGPT, plus a fresh read-only review agent briefed by Rogue with only the diff, §3 and this WO | Checks conformance to §3, **no extra functionality**, the SQL being exactly the three statements on the contract views, no float, nothing returned or logged that §3 forbids, and the lane rules above |

The unit tests **cannot** prove that the real view returns the latest observation per case, one row per case, or that the database principal is SELECT-only. Those are proven in `CRM-WIP-INT-001` proof steps P2 and P3 on a disposable database, outside this WO.

## 4. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| WA1 | The PR diff against the base is exactly the four paths in §1, and every changed line in `.env.example` is a name only | `git diff --stat`, reviewer |
| WA2 | Each §3 behaviour 1 to 7 is implemented and covered by a test, including the **one** negative test for the 409 ambiguity (exactly `{"error":"conflict"}`, no case data, no `wip_case_id` in the body) | test list mapped to §3 |
| WA3 | The new tests and the listed existing DB-free tests pass, with counts reported | Helm's report and Rogue's independent re-run |
| WA4 | The mutation check shows a failing test for every listed guard | Rogue's record |
| WA5 | gitleaks reports 0 findings on the PR diff | scan |
| WA6 | Independent review is complete and has no unresolved finding | reviewer's record |
| WA7 | The live installation is untouched: checkout `main` and tree unchanged, no environment-file read, no database connection, no service change | Helm's before and after record |
| WA8 | The PR is a draft and unmerged | PR state |

## 5. Return and gates

- **Helm returns** (public-safe): branch, PR number, head SHA, SHA-256 of the four files, test counts and the list of tests run, the gitleaks result, and the WA7 record. Rogue records it on Issue #71.
- **Gates:** **WG1** CGPT exact-version approval of this WO (it names the reviewer). **WG2** this WO's base check: WIP `main` equals `91b2af19…` when work starts; if it has moved, report before starting (the diff touches only new files and `.env.example`). Part B does not wait for this WO. End-to-end proof (`CRM-WIP-INT-001` §5) needs the accepted Part W commit.

## 6. Stop conditions

Any behaviour not in §3. Any change to an existing file other than the `.env.example` names. A need to read the environment file, connect to a database, or change a service. A conflict or ambiguity in §3. A dependency missing from the existing test environment (report BLOCKED; do not edit `pyproject.toml`). A finding that cannot be reported safely is BLOCKED, never PASS.
