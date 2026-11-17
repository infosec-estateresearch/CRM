WO: CRM-WIP-INT-001R
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main
KNOWN_COMMIT: 6e1766980e24d781d498727d4fe5db43cdeadbb7

# CRM-WIP-INT-001R: (recovery of CRM-WIP-INT-001) one CRM Account displaying WIP data read from the existing WIP application

- **Version:** v1.0 **DRAFT** of the recovery WO, 2026-11-17. It is `CRM-WIP-INT-001` v1.1 (commit `a657f13d40f46a2c52395b91bafb5b03100b20de`, SHA-256 `c5861f2d0a8a8ac5d4e64f8eefa931e1e5d4978b64e2878142a4f835ae7d4d86`) with **only** the changes listed in §0. **Not approved. No dispatch.** Dispatch needs a CGPT exact-version approval naming this path and the commit that contains it, relayed through Matt and recorded on Issue #71.
- **Approval evidence.** The approval is recorded outside this text, so this text cannot show it. The Orchestrator's dispatch record, `APPROVAL.md` in the WO directory, carries it and the gate evidence, and the PL reads it with the WO before deciding intake.
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/71. Related: #70 (security hygiene, not a dependency).
- **Authority:** the CGPT scope approval of 2026-11-17 ("approved to prepare"), and `docs/architecture/crm-wip-integration-amendment.md` (**approved by CGPT** at `194f0e2b…`, SHA-256 `7838cf44bf3330e50d42dfe958f26ff84088c50db5a508579f44338da8f15734`, gate G1; it merges with this PR and is unchanged here).
- **Header note (base).** `KNOWN_COMMIT` is the PL's actual local `main`, which is the engineering base (§8). It is **not** the GitHub `main` at the docs merge. The two differ only by documents (§8, EB1).
- **Header note.** There is no `BROWSER: yes` line. The sandboxed Tester has no network to crm-dev. The one browser check (P8) is run by the operator or Matt. The CRM-CLIENT-001R2 harness and its D0–D5 sequence are **not used**.
- **Prepared by:** Rogue (Orchestrator). No implementation and no dispatch.

## 0. Recovery record

| Item | Value |
|---|---|
| Chain | `CRM-WIP-INT-001` (v1.1, approved) → **`CRM-WIP-INT-001R`** (this WO). Same engineering base `6e1766980e24d781d498727d4fe5db43cdeadbb7` |
| What happened | `CRM-WIP-INT-001` was dispatched on 2026-11-17 after EB1–EB7 passed. Attempt 1 (12:57Z) was a no-op: the Orchestrator's command omitted the pointer to the dispatch record, so intake stopped. Attempt 2 (12:59Z) passed intake and **EB6** (`forge-start` printed `base_sha` = `KNOWN_COMMIT`). The Engineer stopped in round 1, before writing any file, on two precondition findings below. The PL closed the WO **BLOCKED**. Executions 1/0/0/0 of 4. No candidate, no push, no PR |
| Finding R1 | The normative contract, `docs/architecture/crm-wip-integration-amendment.md`, was not in the PL's base worktree (the base predates PR #72, as §8 intends) and the PL repository does not hold it. **Orchestrator staging error:** it was not supplied as reference data |
| Finding R2 | The reference `migrations/` directory was staged `root:root 0750`, unreadable by `forgev2-pl` and the Engineer sandbox. **Orchestrator staging error** |
| Why a new identity | A closed ForgeV2 ledger cannot be dispatched again (`forgelib.py`: "closed (BLOCKED); no further dispatch"), and ledgers are never edited by hand. The id `CRM-WIP-INT-001` is spent, as the earlier recovery chains were |
| Preserved, not touched | Branch `forge/CRM-WIP-INT-001` (delivery record commit `c6792462dfe3e94e20f3d290fbc40fd17ce8a36c`, no code), its worktree and its closed ledger. The PL checkout is otherwise unchanged |
| **What this WO changes (only these)** | (1) The identity (`WO:`, title, the branch `forge/CRM-WIP-INT-001R`, the evidence path). (2) §2 *Reference material* now also provides the approved amendment as read-only data. (3) §7 G2 and G4 state the current approvals and the prepared WIP Work Order. (4) §8: EB1 lists the recovery PR's two files, EB4 treats the preserved `CRM-WIP-INT-001` artefacts as closed, and **new EB8** checks that the reference material is readable. (5) This section and the two header lines. **§1, §3, §4 and §9 are unchanged. The only edits in §5 and §6 are the evidence path (§5) and the gate range in A9 (§6, now EB1–EB8).** In particular **§3 (Part W) is byte-identical to `CRM-WIP-INT-001` v1.1. Its SHA-256 is `f627fc2ea5f96df5b7288920b3eebc881b7258c021018c2bfb11d2b9517c725b` in both files, computed over the bytes from the line `## 3. Part W` up to, not including, the line `## 4. Part B`** |
| Limits | A new WO has its own ForgeV2 counters. This is a genuine recovery after precondition findings, not a way round the limits: the previous WO used 1 of 4 Engineer executions and wrote no code |

## 1. Outcome

On synthetic crm-dev, an authorised user opens one synthetic Account and sees its current WIP cases. The data comes from a **disposable** database built from the existing WIP application's own migrations, through an authenticated, read-only WIP JSON API. CRM stores nothing from WIP. WIP gains no financial or business logic. The contract is in the amendment §5. It is normative here.

## 2. Two parts, one WO

| Part | Repository | Content |
|---|---|---|
| **W** (WIP side) | `infosec-estateresearch/WIP`, base `91b2af19877b498ed307ee9f1218b3243b2b60ba` | New files only: the read-only endpoint, its own small app, tests, and three variable names. No existing WIP file other than `.env.example` changes |
| **B** (CRM side) | this repository | Read loader, two fields, panel, role scope, optional env pass-through, tests, one operator document |

**Dispatch scope.** ForgeV2 identifies one repository per WO and its PL can push only to this one. **A ForgeV2 dispatch of this WO delivers Part B only.** Part W is specified here and is delivered by the WIP Helm lane (gate **G4**, T2 selected by CGPT): no new ForgeV2 checkout, credential or access. Part B is tested against a stub of the contract, so the two parts can proceed independently. The proof (§5) needs both.

**Reference material (read-only).** At dispatch the operator provides, under `/srv/CRM/wo/CRM-WIP-INT-001R/reference/`: (a) `wip-91b2af19/`, a `git archive` of WIP's `migrations/` and `.env.example` at the pinned base; (b) `amendment/crm-wip-integration-amendment.md`, a byte-identical copy of the **approved** amendment (SHA-256 `7838cf44bf3330e50d42dfe958f26ff84088c50db5a508579f44338da8f15734`), which is this WO's normative contract and is not in the base worktree. Their sha256 values are recorded in the dispatch record. The Engineer writes the synthetic seed from (a) and the loader from (b), and edits nothing in either. **Both must be readable by `forgev2-pl` before dispatch (EB8).** No other WIP source, no environment file and no WIP data is provided.

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

## 4. Part B: CRM side

**Allowlist (anything else needs a new approved version):**

| Path | Change |
|---|---|
| `custom/Espo/Custom/Classes/FieldProcessing/Account/WipLoader.php` | new, about 90 lines |
| `custom/Espo/Custom/Resources/metadata/recordDefs/Account.json` | add `readLoaderClassNameList` for the loader |
| `custom/Espo/Custom/Resources/metadata/entityDefs/Account.json` | add `wipStatus` (varchar) and `wipCases` (text): `readOnly`, `notStorable`, and excluded from list, filter, export, import, mass-update and audit surfaces using the field flags that 10.0.12 supports (verify them in the running image) |
| `custom/Espo/Custom/Resources/metadata/scopes/WipSummary.json` | new boolean ACL scope, same shape as core's `EmailAccountScope` (`entity` false, `layouts` false, `tab` false, `acl` boolean) |
| `custom/Espo/Custom/Resources/layouts/Account/detail.json` | one new native panel with the two fields, hidden when `wipStatus` is empty (`dynamicLogicVisible`). Existing panels are untouched |
| `custom/Espo/Custom/Resources/i18n/en_US/Account.json`, `Global.json` | labels per amendment §5; the scope name for the role editor |
| `config/access/roles.json` | `WipSummary: false` in **every** role. This WO grants it to no role |
| `tests/unit/access_policy.py` (and `test_access_policy.py` if needed) | add `WipSummary` to the verified boolean scopes, with `false` in the human and import expectations |
| `deploy/compose.json`, `deploy/env.example` | the crm-app service gets `CRM_WIP_API_URL` and `CRM_WIP_API_TOKEN` as **optional** (`${VAR:-}`), so existing environments start unchanged. `deploy/env.example` gets the two names only. **Not** `deploy/beta/*` |
| `tests/unit/compose_policy.py`, `test_compose_policy.py` | only if the policy needs to admit the two optional variables |
| `tests/unit/test_wip_panel.py` | new |
| `tests/fixtures/wip_proof_seed.sql` | new: the synthetic seed for P2 (public-safe, obviously fake) |
| `docs/WIP-INTEGRATION.md` | new, about 40 lines: configuration, statuses, rollback |

**Loader behaviour (all server-side):**

1. **Authorisation first, then the Account (C1).**
   - **No grant:** a user without the `WipSummary` scope (any role that is not Admin and does not grant it) gets **no WIP fields at all**, so the panel stays hidden. The loader makes **no outbound request**, whatever the Account holds.
   - **Granted, no valid `sfId`:** an authorised user (Admin, or a role that grants the scope) who opens an Account whose `sfId` is empty or fails `^[A-Za-z0-9]{18}$` gets `wipStatus` = "No Salesforce ID on this Account" (the amendment §5 wording) and an empty `wipCases`. The loader makes **no outbound request**.
   - Both rules hold on every read path that runs the loader.
2. The URL and token come only from the two env names. A missing or empty value gives "WIP unavailable". Only a valid `sfId` (rule 1) ever reaches the path. Only `http` and `https`. **No redirects.** The body is capped at 256 KiB. Timeouts 2 s and 3 s.
3. The reply must be a valid JSON object with exactly the contract keys and types, with at most 50 cases and bounded string lengths. Anything else is "WIP unavailable". Output is plain text (no HTML).
4. Every outcome other than a valid 200 becomes a status: 404 gives "Firm not found in WIP"; every other failure (timeout, refusal, 401, 409, 422, 5xx, bad JSON, wrong shape) gives "WIP unavailable". **Nothing is thrown to the page.** A log line may name the failure class and HTTP status only. It never holds the token, the URL, the sfId or the body.
5. Two read-only fields only. No write path, no hook and no stored copy.

**Part B tests (`test_wip_panel.py`, precedent `test_activities.py` and `test_access_policy.py`, PHP run when present):**

- Metadata: valid JSON; the loader is registered; both fields are `readOnly` and `notStorable`; the panel names only existing fields; the scope has the core shape; every role lists `WipSummary` as `false`.
- Loader, using a stub server on loopback and stubs for the EspoCRM classes it touches: each status in the amendment §5 from the matching reply: 404 gives "Firm not found in WIP", and **409**, 401, 422 and 5xx give "WIP unavailable"; **C1, both cases: (i) a user without the scope, with a valid `sfId`, with an empty `sfId` and with a malformed `sfId` (15 characters, 19 characters, a non-alphanumeric character), gets no WIP fields and the stub records zero requests; (ii) an authorised user with an empty or malformed `sfId` gets "No Salesforce ID on this Account" and the stub records zero requests;** no token in output or logs; no redirect followed; oversize, malformed and wrong-shape replies; a timeout. **Show that the PHP tests actually ran. A skip does not count.**

## 5. Proof (operator, synthetic, disposable, transient)

No permanent WIP service is started. No beta, production, Salesforce or real data. No ForgeV2, Foundry or Gateway change. The existing WIP installation, its database and its running timers are not touched. Secrets live only in files outside Git (mode 0600) and in the environment, never on a command line.

| Step | Action | Result recorded |
|---|---|---|
| P1 | Check out WIP at the Part W commit into a scratch directory. Start a disposable MariaDB from the project's pinned image, port on loopback only, no persistent volume | image digest; teardown plan |
| P2 | Apply WIP's own migrations in order (the Engineer or operator edits none). Load `wip_proof_seed.sql`: firm S1 with case A (two periods, different values) and case B (null yield amounts), a closed case C, and a case on another firm D. Firm S2 has no cases. A third id is absent | migration result. **If a migration does not apply on this image, stop BLOCKED and name it** |
| P3 | Create the SELECT-only principal on the two views. Prove an `INSERT` and a read of a base table both fail. Query the views and assert one row per case, with case A showing its **latest** period | grants; the assertions |
| P4 | Start the Part W app transiently, bound to the crm-net gateway address (read at run time, never written to Git), with a random token. Prove that no token gives 401 and that the documentation routes give 404 | |
| P5 | Operator adds the two names to the crm-dev env file (record before and after hashes), recreates crm-app with `scripts/up.sh dev`, then runs `scripts/deploy_custom.sh dev` and `scripts/provision_access.py` | the crm-app to WIP network path works, or **BLOCKED** |
| P6 | Create synthetic Accounts: S1, S2, an id absent from WIP (S3), and one with no `sfId` (S4). Create a temporary role with `WipSummary: true` and a user U1 on it. Use existing Admin, an ER Staff user U2 (explicit false) and a user U3 on a role that omits the scope | |
| P7 | **REST checks.** (a) Admin and U1 on S1: status available, the expected cases, latest-period values, decimal strings, B's blanks not zero, no case C or D. (b) S2 gives "No current WIP cases"; S3 "Firm not found in WIP". **(C1)** Admin and U1 on S4 (no `sfId`) get "No Salesforce ID on this Account", **and the WIP API log shows no request for S4**. (c) **(C1)** U2 and U3 on S1 **and on S4**: HTTP 200, no WIP fields, **and the WIP API log shows no request for either**. (d) Stop the API: Admin on S1 gets HTTP 200, "WIP unavailable", all other fields intact. Restart: recovered. (e) The token is absent from every Account response, `docker logs` and the Apache and EspoCRM logs. (f) No WIP column in `account`; the fields are absent from the list, export and audit. (g) Admin saves S1: it succeeds and sends nothing to WIP | the matrix |
| P8 | **One browser check** (operator or Matt, one session, a real browser): Admin opens S1 and sees the panel and cases; U2 opens S1 and sees no panel; with the API stopped Admin sees the bounded status and the Account page works. Screenshots go to the restricted store | |
| P9 | Regression: the unit suite, the access-policy and compose-policy tests, and the existing acceptance tests | pass counts |
| P10 | **Teardown:** stop the API; remove the scratch database, scratch directory and temporary role and users; delete the synthetic Accounts; restore the crm-dev env file to its recorded hash and recreate crm-app. Confirm no leftovers | before and after state |

**Evidence discipline.** Raw evidence goes to the restricted store at `/srv/CRM/evidence/CRM-WIP-INT-001R/<run>/`. It is copied from an **explicit file allowlist**, an env file is never copied, and gitleaks runs **before** any ownership or permission change. `SHA256SUMS` is written last. Only a public-safe summary goes to GitHub. No password, token, address or `sfId` is published. A finding that cannot be reported safely is BLOCKED, not PASS.

## 6. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| A1 | Part B unit tests pass as non-root; the PHP tests ran | ForgeV2 delivery record |
| A2 | The diff stays inside the §4 allowlist; no change to `deploy/beta/*`, ForgeV2, Foundry, any EspoCRM core file, or the earlier CLIENT-001R2 candidate | `git diff --stat`, Auditor |
| A3 | Auditor, Tester and DevSecOps PASS on the exact candidate. DevSecOps looks specifically at the token path, request building (SSRF and redirects), response handling and log content | delivery record |
| A4 | Part W unit tests pass and the Part W diff has only the §3 files | WIP PR or record (G4) |
| A5 | P3: the principal is SELECT-only and the view returns the latest observation per case | proof |
| A6 | P7 (a) to (g) all as stated, and P8 as stated | proof and restricted evidence |
| A7 | P9 regression passes. P10 leaves no leftovers and the crm-dev env file is back to its recorded hash | proof |
| A8 | `gitleaks` shows 0 findings on the candidate, on the Part W diff and on the evidence store | scans |
| A9 | The exact-base gate EB1–EB8 (§8) passed before dispatch, and the committed ledger shows `base_sha` `6e1766980e24d781d498727d4fe5db43cdeadbb7` | dispatch record, ledger |

## 7. Gates

| Gate | Requirement | State |
|---|---|---|
| G1 | CGPT exact-version approval of the amendment; merged | **approved** (CGPT, 2026-11-17, at `194f0e2b…`, file SHA-256 `7838cf44…`); merge with PR #72 |
| G2 | CGPT exact-version approval of **this** WO (`CRM-WIP-INT-001R` v1.0) and the exact-base gate (§8, EB1–EB8). The approval of `CRM-WIP-INT-001` v1.1 (CGPT, 2026-11-17, Issue #71 comment 6948627548) covers the same text apart from §0 | open |
| G3 | PO-W1 is **not** a gate. This WO grants no role. Admin only until PO-W1 is decided | noted |
| **G4** | **Delivery of Part W: T2 selected** (CGPT, 2026-11-17). The WIP Helm lane implements §3 in the WIP repository at base `91b2af19877b498ed307ee9f1218b3243b2b60ba` and does not merge. It needs its own **separately recorded, bounded WIP Work Order and CGPT approval** before any Part W work starts (`work-orders/CRM-WIP-INT-001-W.md`, prepared and awaiting CGPT approval; this WO's §3 is its normative content). Independent tests and review are required (the WIP WO names who does them). The WIP PR stays unmerged pending acceptance. No new ForgeV2 checkout, credential or access. The Part W tests need `fastapi`, its test client and `pymysql` in the interpreter that runs them. **Part B dispatch does not wait for G4; the proof (§5) does** | selected; the WIP WO is open |
| G5 | Proof prerequisites: P2 migrations apply on the pinned MariaDB image and P5 the network path works | checked at proof time |
| G6 | **Exact-base gate EB1–EB8 (§8)** passes before Part B dispatch | open |

## 8. Exact-base gate (C3, CL-D8)

**Facts checked on 2026-11-17 (read-only).** The PL's local `main` is `6e1766980e24d781d498727d4fe5db43cdeadbb7`, clean, and behind GitHub `main` (nine commits at `9ea7b725…`; twelve at the PR #72 merge `37aaba11…`). `forge-start` resolves `--base` locally with `git rev-parse` and **never fetches**, so the worktree base is the PL's local `main`. `check_repo` tests only that `KNOWN_COMMIT` exists as a commit object in the PL repository. It does not compare it with the base. Nobody may advance the PL checkout: the permanent fix, FV2-SYNC-001 (`maff0000/forgev2#7`), is not installed.

Therefore the engineering base is `6e176698…` (the header `KNOWN_COMMIT`), exactly as in CRM-CLIENT-001R2. v1.0 named `9ea7b725…`; that was wrong, and it would have passed `check_repo` only by accident (see the disclosure on Issue #71).

| Gate | Requirement (all read-only, `GIT_OPTIONAL_LOCKS=0`) |
|---|---|
| **EB1** | This WO's recovery docs PR is merged at an exact merge SHA `M`. GitHub compare `6e176698…M` has `behind_by = 0` and lists **only documents**: the nine `work-orders/CRM-CLIENT-001*.md` files (unchanged since their own merges) the six files merged by PR #72 (`work-orders/CRM-WIP-INT-001.md`, `docs/architecture/crm-wip-integration-amendment.md`, `docs/architecture/crm-wip-module-boundary.md`, `docs/requirements/crm-modules-requirements.md`, `DECISIONS.md`, `PRODUCT-BACKLOG.md`) and this recovery PR's two files (`work-orders/CRM-WIP-INT-001R.md`, `work-orders/CRM-WIP-INT-001-W.md`). **No path of the §4 allowlist, and nothing under `custom/`, `config/`, `deploy/`, `scripts/` or `tests/`, appears.** So the Part B tree at `6e176698…` equals the tree at `M` for every file the WO may touch |
| **EB2** | GitHub `main` equals `M`. If it has advanced, every later commit is reviewed, and any non-document change is a stop for CGPT |
| **EB3** | The PL's local `main` equals `6e1766980e24d781d498727d4fe5db43cdeadbb7`, on branch `main`, with a clean tracked and untracked tree, the canonical SSH origin, no `url.*` rewrites, no `core.hooksPath` and no fsmonitor. **This is the gate. The presence of newer objects, or a newer local `origin/main` ref, in the PL repository is not evidence of anything and is never a pass** (the 2026-11-17 root-run `git fetch` is disclosed on #71) |
| **EB4** | No `forge/CRM-WIP-INT-001R` branch, worktree, scratch directory or ledger exists, and no other WO is in flight. The preserved CLIENT-001, 001R, 001R2 and **`CRM-WIP-INT-001`** branches, worktrees and closed ledgers stay by design and are never touched |
| **EB5** | The WO file given to the PL is byte-identical (sha256) to the blob of this path at `M`, and sits outside the repository, readable by `forgev2-pl` |
| **EB6** | `forge-start` prints `base_sha = 6e1766980e24d781d498727d4fe5db43cdeadbb7`, equal to `KNOWN_COMMIT`, and the committed ledger later shows the same value. **Any other value is a stop (BLOCKED), with no retry and no repair** |
| **EB7** | **No one advances the PL checkout.** No root, `runuser`, fetch, pull, checkout, merge, reset, gc or other Git mutation in `/srv/CRM/main` before or during the run. ForgeV2 is not modified. Reads of GitHub use `gh api`. If EB3 or EB6 cannot pass, dispatch is **BLOCKED on FV2-SYNC-001** and goes to CGPT. It is never forced |
| **EB8** | **Staged material is readable.** Every file and directory under the WO directory's `reference/` is readable by `forgev2-pl` (checked with a read test as that account, not by inspecting modes), the amendment copy has SHA-256 `7838cf44…` and the WIP manifest matches the dispatch record. The dispatch command passes the WO directory to the PL (`--add-dir`) and points to `APPROVAL.md` in the prompt. **An unreadable file is a stop before dispatch** |

## 9. Stop conditions

Any change outside the allowlists. A role grant before PO-W1. A total, a "revenue" figure or any calculation. Any real data, any beta step, any permanent WIP service, any change to the WIP GUI or its live database. A failing migration, an unresolvable network path or an unreportable finding is **BLOCKED**, not worked around. No firewall rules. No ForgeV2, Foundry or scan changes.
