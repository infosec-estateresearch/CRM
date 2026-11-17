WO: WIP-API-001
REPO: infosec-estateresearch/WIP
HOST: DOCKER1
ROOT: /srv/WIP/main
WORKTREES: /srv/WIP/worktrees
BASE: main
KNOWN_COMMIT: 91b2af19877b498ed307ee9f1218b3243b2b60ba

# WIP-API-001: authenticated read-only account endpoint on the existing WIP application

- **Version:** v1.0 **DRAFT**, 2026-11-17. **Not approved. No dispatch.** Dispatch needs a CGPT exact-version approval naming this path and the commit that contains it, relayed through Matt and recorded on the Issue. The approval is recorded outside this text, so this text cannot show it; the Orchestrator's dispatch record (`APPROVAL.md` in the WO directory) carries it and the gate evidence.
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/76. Parent record: https://github.com/infosec-estateresearch/CRM/issues/71.
- **Where this WO lives.** In the CRM repository, which coordinates the integration and where CGPT's approvals are recorded. The delivery target is the WIP repository above. The Orchestrator's GitHub identity has read-only rights on the WIP repository, so it cannot create a branch, a PR or an Issue there. This is a stated deviation from "the WO lives in the product repository" and is for CGPT to accept or refuse when approving.
- **Parent outcome (CRM-WIP integration, #71):** "Open a synthetic Account in EspoCRM and see its WIP cases retrieved from the existing WIP system." This WO delivers the WIP side only (**Part W**). The CRM side (Part B) is delivered separately (`CRM-WIP-INT-001R2`, candidate `167f2a9acf543f171f1db45ab1f3e83d1031fe38`, draft PR #75).
- **Authority:** (1) the Product Owner's direction of 2026-11-17: take over the existing WIP application under Foundry and ForgeV2, with the Orchestrator responsible; do not rewrite WIP or add features. (2) CGPT's approval of the integration amendment `docs/architecture/crm-wip-integration-amendment.md` (CRM commit `194f0e2b94041b2a7922cfd6cfae8cf595357a42`, SHA-256 `7838cf44bf3330e50d42dfe958f26ff84088c50db5a508579f44338da8f15734`, gate G1). (3) CGPT's approval of the Part W contract: section 3 of `CRM-WIP-INT-001` v1.1 (SHA-256 of that section `f627fc2ea5f96df5b7288920b3eebc881b7258c021018c2bfb11d2b9517c725b`), approved as part of `CRM-WIP-INT-001` v1.1, `CRM-WIP-INT-001R` v1.0 and `CRM-WIP-INT-001R2` v1.0. (4) CGPT's instruction that the WIP Work Order uses the approved Part W contract with "no additional WIP functionality".
- **Supersedes** `CRM-WIP-INT-001-W` v1.0 (CRM commit `9ca8ed6f79ae53883c70347ec511453e9fe34de7`, SHA-256 `acb7d51f5d05b5cbe10e02435860de4171088204697b93c9fc4bfbdef13159f3`), which assigned the same contract to a separate Helm lane. That lane never started. Only the delivery route changes; the contract does not.
- **Governing FOUNDRY revision:** `maff0000/foundry` main `84fedf0a74017237aa1bd650d8560350c91c7f0e`; applicable: `standards/work-order-contract.md`, `standards/secure-engineering.md`, `skills/security-by-design.md`, `ROGUE.md` sections A2 and A3.
- **Engine:** ForgeV2 `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82` (plugin 0.3.0), unmodified.
- **Product records for WIP:** the FOUNDRY route is **EXISTING**. No WIP Vision, Backlog or PIM is recorded in the repository. That is a **gap, stated as UNKNOWN**, not invented. Authority for this WO is the Product Owner's direction and the approved integration records above. Inspection alone does not authorise implementation.

## 1. Outcome

The existing WIP application gets one new, read-only, authenticated JSON route that returns the current cases of one firm, identified by its Salesforce Account id, from WIP's own SQL contract views. The route is the WIP half of the CRM Account panel. It is **not started as a service by this WO**.

## 2. Repository, workspace and what must stay untouched

| Item | Verified value (2026-11-17) |
|---|---|
| Repository | `infosec-estateresearch/WIP`, public, default branch `main`, `main` = `91b2af19877b498ed307ee9f1218b3243b2b60ba` (no open Issues or PRs) |
| Execution host and paths | `DOCKER1:/srv/WIP/main` (the PL's own checkout, owned by `forgev2-pl`, clean, at the base, canonical `https://github.com/infosec-estateresearch/WIP.git` origin) and `/srv/WIP/worktrees`. The engine's own `check_repo` and `validate_project_target` accepted both, run read-only as `forgev2-pl` |
| Branch | `forge/WIP-API-001` in its own worktree under `/srv/WIP/worktrees`. Nothing else is created |
| **Live application (not touched)** | The live checkout `/home/WIP` (same `main`, clean), its MariaDB database, its three systemd timers (`wip-mastercopy-import`, `wip-salesforce-sync`, `wip-salesforce-full-sync`, enabled and active) and its environment file. The GUI service `wip-web` is disabled and inactive. **No part of this WO reads, writes, restarts or connects to any of them** |
| Protected | `/srv/forgev2`, `/srv/src/foundry` (never a root, worktree or scratch location), every earlier CRM ledger and evidence store |
| Specialist limits | The specialists run in a sandbox with **no network**, no database and no environment file. The live environment file is mode 0600 and unreadable by `forgev2-pl` (verified) |

**Reference material (read-only).** At dispatch the operator provides `/srv/WIP/wo/WIP-API-001/reference/crm-wip-integration-amendment.md`, a byte-identical copy of the approved amendment (SHA-256 `7838cf44bf3330e50d42dfe958f26ff84088c50db5a508579f44338da8f15734`), whose section 5 defines the exact response and error keys that section 3 refers to. Its hash is recorded in the dispatch record. The WIP migrations needed to read the two contract views are already in the PL's checkout under `migrations/`. No environment file and no WIP data is provided.

## 3. Part W: WIP read-only endpoint (normative spec)

Files (all new except the last):

- `src/wip_web/routes/api_account_wip.py` (about 70 lines)
- `src/wip_web/api_app.py` (about 12 lines): a FastAPI app that includes only that router, with `docs_url`, `redoc_url` and `openapi_url` set to `None`. The existing GUI app is neither imported nor changed
- `tests/unit/test_api_account_wip.py` (about 90 lines)
- `.env.example`: add the names `WIP_API_TOKEN`, `WIP_API_DB_USER`, `WIP_API_DB_PASSWORD` (names only)

Behaviour:

1. One route, `GET /api/v1/accounts/{sfId}/wip`. No other method, no other route, no health route, no CORS. Responses carry `Cache-Control: no-store`.
2. **Order:** authenticate (constant-time compare, `hmac.compare_digest`) → validate `^[A-Za-z0-9]{18}$` → query. A caller without the token learns nothing. If `WIP_API_TOKEN` is unset or empty the app **refuses to start**.
3. **Database:** host, port and database name reuse the existing WIP settings. The user and password come **only** from `WIP_API_DB_USER` and `WIP_API_DB_PASSWORD`. The API never connects as `wip_app`. `connect_timeout` 2 s, `read_timeout` 3 s, a read-only session.
4. **Queries (the only SQL, parameterised, the contract views only):**
   - `SELECT salesforce_account_id, company_name FROM v_eric_wip_company_summary WHERE salesforce_account_id = %s`
   - `SELECT wip_case_id, case_reference, case_name, case_type, status, opened_at, current_wip_value, current_fees_invoiced, current_actual_yield, current_estimated_yield, financial_as_of FROM v_eric_wip_current_cases WHERE salesforce_account_id = %s ORDER BY current_wip_value DESC, wip_case_id LIMIT 51`
   - `SELECT COUNT(*) AS n, COUNT(DISTINCT wip_case_id) AS d FROM v_eric_wip_current_cases WHERE salesforce_account_id = %s` (the integrity check in item 5)
   - The 51st row only sets `truncated` and is dropped. `wip_case_id` is used internally and is **never returned**. No totals, no arithmetic, no float.
5. **Ambiguity is rejected (C2).** The view can return more than one row for a case when two of its financial observations share the latest `as_of_date`. If `n` differs from `d`, or the fetched rows repeat a `wip_case_id`, the API answers **409** with the generic body `{"error":"conflict"}` for the **whole request**: no cases, no amounts. It does not duplicate the case, drop a row, or pick between observations (no selection rule is invented). It logs one warning naming only the affected `wip_case_id` values (at most 10). No schema, view or business-logic change.
6. **Response:** exactly the keys in the amendment §5. Amounts are `format(Decimal, "f")` strings, `null` stays `null`, dates are ISO. **Errors** are exactly 401, 422, 404 (firm absent from the company view; zero cases is a 200), 409 (item 5) and 503 (any database error; the body is generic). The amendment §5 lists the first four of these. The CRM maps any other failure to "WIP unavailable" (amendment §5), so 409 needs no new panel status. No exception text, SQL or token is ever returned or logged.
7. **Unit tests** (existing `TestClient` and fake-connection pattern): missing, wrong and malformed tokens; the order (a bad id with no token gives 401); 422; 404; 200 with zero cases; 200 with mixed null and non-null amounts as strings; truncation at 51; **one negative test (C2): a firm whose view returns two rows for the same `wip_case_id` gets 409 with exactly `{"error":"conflict"}`, no case data, and no `wip_case_id` in the body;** 503 on a database error; no extra keys; the token never appears in any response or captured log; the documentation and schema routes give 404; POST gives 405; the connection never uses the `wip_app` settings. **The unit tests cannot prove "latest observation per case" or that the real view returns one row per case. The proof does (P3).**

## 3A. Clarifications (they add no functionality and change no line of section 3)

Section 3 above is the approved text, byte for byte. These points state how it is to be read in this repository, because the existing code would otherwise be used in a way that defeats its purpose.

- **C-W1 (settings reuse, item 3).** The existing `src/wip_app/config.py` function `wip_db_settings()` calls `load_env()`, which loads **every** key of the live WIP environment file and of ERic's environment file into the process environment. That includes the full-DML `wip_app` credentials and the Salesforce secrets. An API that reused that function would carry them in memory. So **"reuse the existing WIP settings" means the same variable names** `NIF_WIP_DB_HOST`, `NIF_WIP_DB_PORT` and `NIF_WIP_DB_NAME`, **read directly from the process environment**. The new modules **must not import** `src.wip_app.config`, `src.wip_app.db` or `src.wip_web.app`, and must not call `load_env()`. The user and password come only from `WIP_API_DB_USER` and `WIP_API_DB_PASSWORD`. A missing variable is a startup or request failure with the generic 503 and no detail.
- **C-W2 (test environment).** The tests run with `python3.9 -m pytest -p no:cacheprovider`, because `fastapi`, `starlette`, `httpx`, `pymysql` and `pytest` are installed for that interpreter and not for the default `python3`. **Jinja2 is not installed**, and `src/wip_web/app.py` builds its templates at import, so any test that imports the GUI app fails at collection. The new modules must import without it. The package `__init__` files are empty, so this holds if the new modules follow C-W1.
- **C-W3 (names only).** `.env.example` gets the three variable names with empty values and, at most, one comment line each. No default, no example secret.
- **C-W4 (no dependency change).** `pyproject.toml` is not edited. A dependency that is genuinely missing for the new tests is a stop (section 9), not a reason to add one.
- **C-W5 (existing boundary).** The ERic integration boundary (`docs/ERIC_INTEGRATION_BOUNDARY.md`) concerns ERic's reads of the `v_eric_*` views and says ERic does not call WIP's UI or API. This WO adds a route for a different consumer and **does not change the views, the boundary document, ERic or any grant**.

## 4. Exclusions and protected items

Anything not listed in section 3 as a file is out of scope. In particular: no change to any existing route, template, static file, migration, view, grant, systemd unit, `pyproject.toml`, `README.md`, document or test; no new user, grant or database object (creating the SELECT-only principal is a WIP-owner operation and not part of this WO); no service, timer or process is started, stopped or enabled; no network call; no read of any environment file; no Salesforce access; no customer or real firm data in code, tests, fixtures, commit messages or reports (use obviously fake 18-character ids and names); no float arithmetic; no totals; no new feature; no refactoring of existing code; no change to the engine, Foundry, the Gateway or the live host.

## 5. Verification

**Commands (run in the worktree, as the unprivileged specialist account, by explicit path; never the whole suite):**

- New tests: `python3.9 -m pytest -p no:cacheprovider tests/unit/test_api_account_wip.py`.
- Regression, existing database-free tests only. The Orchestrator verified these 14 files by running each alone in a fresh clone at the base as an unprivileged user with no network, the live checkout hidden and a scrubbed environment: `test_audit.py` 8, `test_canonical_resolver.py` 6, `test_duplicate_detector.py` 5, `test_firm_matcher.py` 8, `test_group_apply.py` 11, `test_group_fold_in.py` 10, `test_group_seed.py` 9, `test_mastercopy_parser.py` 32, `test_mastercopy_runner.py` 8, `test_normaliser.py` 11, `test_reject_queue.py` 6, `test_run_migration.py` 8, `test_sync_runner.py` 7, `test_wo22_import_freshness.py` 6 (**135 tests, all pass at the base**).
- **Do not run:** `test_wo20_pages.py`, `test_wo21_wizard.py`, `test_wo23_pagination.py`, `test_wo23_selective_group.py`, `test_wo26_same_canonical_approve.py` and `test_wo27_wip_entry.py` (they load the environment file), `test_wip_web.py` (cannot be collected: Jinja2), `test_sync_health.py` (reads the live checkout by absolute path).
- Static checks required in the report: the diff touches exactly the four paths in section 3; the new modules contain none of the imports banned in C-W1; `git diff` of `.env.example` shows names only; gitleaks on the diff shows 0 findings.

**Independent assurance (ForgeV2, on the exact committed candidate, in the engine's sequence):**

- **Auditor:** conformance to section 3 and 3A, no extra functionality, the SQL being exactly the three statements on the two contract views, parameterised, nothing returned or logged that section 3 forbids, the banned imports absent.
- **Tester:** functional verification through the test client: every behaviour of section 3 and every status, the order of checks, the 409 case with its exact body, decimal strings, truncation, the closed documentation routes. **A real-browser check is not applicable**: the route returns JSON only and has no page. CGPT is asked to accept that rationale with this approval (the contract requires approval of an inapplicable assessment). The proof P3 of `CRM-WIP-INT-001` (real view, disposable database) is outside this WO and still required later.
- **DevSecOps:** the constant-time token comparison, authenticate-before-validate, SQL injection resistance, secrets and token handling in code, logs and responses, the database principal never being `wip_app`, and the secure-engineering standard.
- **Orchestrator (after delivery, not part of the PL's run):** a re-run from a fresh checkout of the candidate and a **mutation check**: revert each guard in turn (token compare, authenticate-before-validate order, id validation, the `n` versus `d` ambiguity check, the ban on `wip_app`, decimal strings, `no-store`, the 409 body, the closed documentation routes, the 51st-row truncation, the startup refusal) and show that a test fails each time. Then CGPT's acceptance review.

## 6. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| WA1 | The diff against the base is exactly the four paths of section 3; `.env.example` changes are names only | `git diff --stat`, Auditor |
| WA2 | Each behaviour 1 to 7 of section 3 is implemented and tested, including the one 409 negative test (exactly `{"error":"conflict"}`, no case data, no `wip_case_id`) | test list mapped to section 3 |
| WA3 | The new tests pass; the 14 listed regression files still pass with their counts; no other test was run; counts before and after are reported | PL record, Tester |
| WA4 | The new modules do not import `src.wip_app.config`, `src.wip_app.db` or `src.wip_web.app` and never call `load_env()` | Auditor, static check |
| WA5 | Auditor, Tester and DevSecOps each return PASS on the **same unchanged candidate SHA** | ledger, delivery record |
| WA6 | gitleaks shows 0 findings on the diff | scan |
| WA7 | The live application is untouched: live checkout `main` and tree unchanged, timers and service states unchanged, no database connection, no environment-file read | Orchestrator before and after record |
| WA8 | The candidate branch is pushed; the Orchestrator opens a **draft** PR that is **not merged** | PR state |
| WA9 | The Orchestrator's independent re-run and mutation check show a failing test for every listed guard | Orchestrator report |

## 7. Entry gates

| Gate | Requirement | State |
|---|---|---|
| G1 | CGPT exact-version approval of this WO, including the clarifications in 3A, the Tester browser-inapplicability rationale, and the stated placement of this WO in the CRM repository | open |
| G2 | Product direction recorded (Product Owner, 2026-11-17) | recorded on #71 and #76 |
| G3 | PL checkout and paths: `DOCKER1:/srv/WIP/main` at `KNOWN_COMMIT`, clean, PL-owned, canonical origin; the engine's `check_repo` and `validate_project_target` pass | **verified** (read-only, as `forgev2-pl`) |
| G4 | **PL push route:** a per-repository SSH deploy key with write access, registered **by the WIP repository owner** (the Orchestrator's identity has no admin rights on that repository), the matching repository-local push settings in the PL checkout (a push URL and an SSH key selection that leave `origin` canonical), and a non-writing push preflight by the PL. The PL's key pair is generated; its public half is in the commissioning record | **OPEN: owner action required** |
| G5 | Exact base: GitHub `main` of the WIP repository equals `KNOWN_COMMIT` and equals the PL's local `main` at dispatch; any difference is a stop | checked at dispatch |
| G6 | The WO file given to the PL is byte-identical to the blob of this path at the approved commit; the reference material is readable from the specialists' sandbox (read test as the PL account, without using an execution) | checked at dispatch |
| G7 | Live-state record taken before dispatch (live checkout `main` and status, timers and service states) for WA7 | taken at dispatch |
| G8 | No other WO is in flight for this repository; no earlier ledger is reused | checked at dispatch |

If G4 is not met the result is **BLOCKED: PL_GIT_WRITE**, never a workaround.

## 8. Execution limits

The engine allows four executions per specialist for a WO. **The Orchestrator proposes a binding cap of two Engineer executions for this WO** (the route is small), held by the dispatch record because the engine's limit cannot be lowered, with no automatic recovery WO if the delivery fails. CGPT may set a different cap with the approval.

## 9. Stop conditions

Any behaviour not in section 3. Any change outside the four paths. A need to read an environment file, connect to a database, start a service or touch the live application. A conflict or ambiguity in section 3 or 3A. A dependency missing from the existing test environment. A banned import. Any finding that cannot be reported safely (BLOCKED, never PASS). A failed entry gate. No firewall rules. No change to ForgeV2, Foundry or the host.

## 10. Communications, logs and completion report

- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/76 (status, evidence references, escalation). It grants no scope.
- **PL record (written by the PL, read by the Orchestrator):** `/home/forgev2-pl/.local/state/forgev2/records/556121f4b765166c/WIP-API-001/` and, on the candidate branch, `.forge/WIP-API-001/`. The ledger is in the PL's private state directory.
- **Specialist logs:** each specialist's output is recorded by the PL under `dispatch/` in the delivery record.
- **Escalation route:** PL to Orchestrator (final status); Orchestrator to CGPT (architecture) and Matt (product, permission or material risk).
- **Completion report (PL):** outcome, changed paths, starting and final commit identities, the acceptance criteria with results, the Auditor, Tester and DevSecOps verdicts and the candidate they assessed, evidence locations, deviations, limitations and remaining risks.
