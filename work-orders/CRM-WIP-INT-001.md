WO: CRM-WIP-INT-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main
KNOWN_COMMIT: 9ea7b725b7d8a8ddfc330a68510de65d184de089

# CRM-WIP-INT-001: one CRM Account displaying WIP data read from the existing WIP application

- **Version:** v1.0 **DRAFT**, 2026-11-17. **Not approved. No dispatch.** Dispatch needs a CGPT exact-version approval naming this path and the commit that contains it, relayed through Matt and recorded on Issue #71.
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/71. Related: #70 (security hygiene, not a dependency).
- **Authority:** the CGPT scope approval of 2026-11-17 ("approved to prepare"), and `docs/architecture/crm-wip-integration-amendment.md` (**must be approved and merged first**, gate G1).
- **Header note.** There is no `BROWSER: yes` line. The sandboxed Tester has no network to crm-dev. The one browser check (P8) is run by the operator or Matt. The CRM-CLIENT-001R2 harness and its D0–D5 sequence are **not used**.
- **Prepared by:** Rogue (Orchestrator). No implementation and no dispatch.

## 1. Outcome

On synthetic crm-dev, an authorised user opens one synthetic Account and sees its current WIP cases. The data comes from a **disposable** database built from the existing WIP application's own migrations, through an authenticated, read-only WIP JSON API. CRM stores nothing from WIP. WIP gains no financial or business logic. The contract is in the amendment §5. It is normative here.

## 2. Two parts, one WO

| Part | Repository | Content |
|---|---|---|
| **W** (WIP side) | `infosec-estateresearch/WIP`, base `91b2af19877b498ed307ee9f1218b3243b2b60ba` | New files only: the read-only endpoint, its own small app, tests, and three variable names. No existing WIP file other than `.env.example` changes |
| **B** (CRM side) | this repository | Read loader, two fields, panel, role scope, optional env pass-through, tests, one operator document |

**Dispatch scope.** ForgeV2 identifies one repository per WO and its PL can push only to this one. **A ForgeV2 dispatch of this WO delivers Part B only.** Part W is specified here and is delivered under gate **G4**. Part B is tested against a stub of the contract, so the two parts can proceed independently. The proof (§5) needs both.

**Reference material (read-only).** At dispatch the operator provides `/srv/CRM/wo/CRM-WIP-INT-001/reference/wip-91b2af19/`: a `git archive` of WIP's `migrations/` and `.env.example` at the pinned base, with its sha256 recorded in the dispatch record. The Engineer writes the synthetic seed from it and edits nothing in it. No other WIP source, no environment file and no WIP data is provided.

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
   - `SELECT case_reference, case_name, case_type, status, opened_at, current_wip_value, current_fees_invoiced, current_actual_yield, current_estimated_yield, financial_as_of FROM v_eric_wip_current_cases WHERE salesforce_account_id = %s ORDER BY current_wip_value DESC, wip_case_id LIMIT 51`
   - The 51st row only sets `truncated` and is dropped. No totals, no arithmetic, no float.
5. **Response:** exactly the keys in the amendment §5. Amounts are `format(Decimal, "f")` strings, `null` stays `null`, dates are ISO. **Errors** are exactly 401, 422, 404 (firm absent from the company view; zero cases is a 200), 503 (any database error; the body is generic). No exception text, SQL or token is ever returned or logged.
6. **Unit tests** (existing `TestClient` and fake-connection pattern): missing, wrong and malformed tokens; the order (a bad id with no token gives 401); 422; 404; 200 with zero cases; 200 with mixed null and non-null amounts as strings; truncation at 51; 503 on a database error; no extra keys; the token never appears in any response or captured log; the documentation and schema routes give 404; POST gives 405; the connection never uses the `wip_app` settings. **The unit tests cannot prove "latest observation per case". The proof does (P3).**

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

1. **No grant, no call.** If the user lacks the `WipSummary` scope, or the Account has no valid `sfId`, the loader sets the fields to nothing and makes **no outbound request**.
2. The URL and token come only from the two env names. A missing or empty value gives "WIP unavailable". The `sfId` is checked against `^[A-Za-z0-9]{18}$` before it goes into the path. Only `http` and `https`. **No redirects.** The body is capped at 256 KiB. Timeouts 2 s and 3 s.
3. The reply must be a valid JSON object with exactly the contract keys and types, with at most 50 cases and bounded string lengths. Anything else is "WIP unavailable". Output is plain text (no HTML).
4. Every failure (timeout, refusal, 401, 404, 422, 5xx, bad JSON, wrong shape) becomes a status. **Nothing is thrown to the page.** A log line may name the failure class and HTTP status only. It never holds the token, the URL, the sfId or the body.
5. Two read-only fields only. No write path, no hook and no stored copy.

**Part B tests (`test_wip_panel.py`, precedent `test_activities.py` and `test_access_policy.py`, PHP run when present):**

- Metadata: valid JSON; the loader is registered; both fields are `readOnly` and `notStorable`; the panel names only existing fields; the scope has the core shape; every role lists `WipSummary` as `false`.
- Loader, using a stub server on loopback and stubs for the EspoCRM classes it touches: each status in the amendment §5 from the matching reply; no outbound request without the scope or without a valid `sfId` (the stub records zero requests); no token in output or logs; no redirect followed; oversize, malformed and wrong-shape replies; a timeout. **Show that the PHP tests actually ran. A skip does not count.**

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
| P7 | **REST checks.** (a) Admin and U1 on S1: status available, the expected cases, latest-period values, decimal strings, B's blanks not zero, no case C or D. (b) S2 gives "No current WIP cases"; S3 "Firm not found in WIP"; S4 "No Salesforce ID". (c) U2 and U3 on S1: HTTP 200, the WIP fields empty, **and the WIP API log shows no request**. (d) Stop the API: Admin on S1 gets HTTP 200, "WIP unavailable", all other fields intact. Restart: recovered. (e) The token is absent from every Account response, `docker logs` and the Apache and EspoCRM logs. (f) No WIP column in `account`; the fields are absent from the list, export and audit. (g) Admin saves S1: it succeeds and sends nothing to WIP | the matrix |
| P8 | **One browser check** (operator or Matt, one session, a real browser): Admin opens S1 and sees the panel and cases; U2 opens S1 and sees no panel; with the API stopped Admin sees the bounded status and the Account page works. Screenshots go to the restricted store | |
| P9 | Regression: the unit suite, the access-policy and compose-policy tests, and the existing acceptance tests | pass counts |
| P10 | **Teardown:** stop the API; remove the scratch database, scratch directory and temporary role and users; delete the synthetic Accounts; restore the crm-dev env file to its recorded hash and recreate crm-app. Confirm no leftovers | before and after state |

**Evidence discipline.** Raw evidence goes to the restricted store at `/srv/CRM/evidence/CRM-WIP-INT-001/<run>/`. It is copied from an **explicit file allowlist**, an env file is never copied, and gitleaks runs **before** any ownership or permission change. `SHA256SUMS` is written last. Only a public-safe summary goes to GitHub. No password, token, address or `sfId` is published. A finding that cannot be reported safely is BLOCKED, not PASS.

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

## 7. Gates

| Gate | Requirement | State |
|---|---|---|
| G1 | CGPT exact-version approval of the amendment; merged | open |
| G2 | CGPT exact-version approval of **this** WO; base re-pinned and EB1–EB6 re-run at approval | open |
| G3 | PO-W1 is **not** a gate. This WO grants no role. Admin only until PO-W1 is decided | noted |
| **G4** | **Delivery of Part W (CGPT decision).** **T1:** a second ForgeV2 identity `CRM-WIP-INT-001-W` with `REPO: infosec-estateresearch/WIP`. It needs a clean WIP clone owned by the PL (not the live installation) and a push credential for that repository, which are new access Matt must grant. **T2 (recommended):** the WIP lane (Helm) implements §3 as a WIP-repo branch and PR at the pinned base, commits with the Helm identity, and does not merge. The Part W tests need `fastapi`, its test client and `pymysql` in the interpreter that runs them | open, needs CGPT |
| G5 | Proof prerequisites: P2 migrations apply on the pinned MariaDB image and P5 the network path works | checked at proof time |

## 8. Stop conditions

Any change outside the allowlists. A role grant before PO-W1. A total, a "revenue" figure or any calculation. Any real data, any beta step, any permanent WIP service, any change to the WIP GUI or its live database. A failing migration, an unresolvable network path or an unreportable finding is **BLOCKED**, not worked around. No firewall rules. No ForgeV2, Foundry or scan changes.
