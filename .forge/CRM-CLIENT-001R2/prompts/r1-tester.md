You are an independent reviewer for Work Order CRM-CLIENT-001R2. Assess independently.

Worktree (read-only for you; the candidate is exactly its committed state): /srv/CRM/worktrees/CRM-CLIENT-001R2
Candidate SHA: 07bfaf1c01c633d6c45aba16d6587733a8c7f6a1
Base SHA: 6e1766980e24d781d498727d4fe5db43cdeadbb7
Scratch directory (your own working space, outside the worktree): /srv/CRM/worktrees/.forge-scratch/CRM-CLIENT-001R2
Do not modify the worktree. Use no Git write commands. If you need to run code or tests, copy the worktree tree (without VCS metadata) into the scratch directory and run there, as a non-root user. Review the change from the base to the candidate against the Work Order below (and its annex B) for your role as defined in WO section 8.

Reporting discipline (binding, WO section 0): refer to the earlier publication failure only as "R1". Never write the name of the download tool removed by R1, the scan rule id, or the annex B3 user option value. Use safe finding identifiers, severities (blocking/advisory) and verdicts; put long technical detail in a scratch note and cite it by path and sha256. A genuine finding that cannot be reported safely: say so explicitly; never suppress it and never claim PASS.

End your final message with exactly one verdict line: PASS, FINDINGS, or INCONCLUSIVE, followed by your findings (key, severity, evidence).

===== WORK ORDER (verbatim) =====
WO: CRM-CLIENT-001R2
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main
KNOWN_COMMIT: 6e1766980e24d781d498727d4fe5db43cdeadbb7

# CRM-CLIENT-001R2: (second recovery: image re-pin) version-controlled delivery of CRM-owned browser customisations (`client/custom/src/`)

- **Version:** v1.5 DRAFT, 2026-11-16, Work Order **CRM-CLIENT-001R2**. **Not approved** until a CGPT exact-version approval names the commit that contains this text (see *Approval*).
- **Relationship (§0).** This WO supersedes `CRM-CLIENT-001R` (v1.4) for delivery. `CRM-CLIENT-001R` was delivered and published, but its S3 operator gate then stopped on a security finding in the pinned runner image. The only substantive change is the pinned image (finding I1 in §13), which changes the candidate in three places (§4). Everything else is carried forward unchanged from v1.4.
  - This version is identified only by the commit that adds it. An approval must name that commit and this path.
  - Annex `work-orders/CRM-CLIENT-001R2-browser-annex.md` (annex B) and the companion assurance WO `work-orders/CRM-CLIENT-001R2-BA.md` are part of this version.
- **History:**
  - v1.0 `972b809a`, v1.1 `0fba12cf` and v1.2 `793f69b0` were drafts of WO `CRM-CLIENT-001`.
  - v1.3 (`323b7a8c90af22a3b0fda7536604201140d01218`, WO `CRM-CLIENT-001`) was approved by CGPT for S1–S2 (relayed through Matt, #59 comment 6916530873) and merged at `9065f80f`. Its candidate `b190377c` passed review but failed publication.
  - v1.4 (`8b42d2fd13e68cb2f44a04c20151a08dfae32640`, WO `CRM-CLIENT-001R`) was approved (relayed, #65 comment 6918958943) and merged at `08758cf0d82371c4fff63e020d5cf3e1aea680a7`. Its candidate `9271b481e013d4ed76338b49d4f25b89ca79b126` was published and passed all three reviews. Its documents stay unchanged as historical evidence.
  - **v1.5** is this file (WO `CRM-CLIENT-001R2`).
  - The source allowlist (§4) paths and the exclusions (§5) are **unchanged** from v1.1.
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/67 (earlier records: #59 and #65)
- **Prepared by:** Rogue (Orchestrator). Preparation only: **no dispatch and no deployment.** The replacement image was pulled and inspected locally in S3 preparation, without running any browser.
- **Approval:** recorded outside this text (FOUNDRY *Approval provenance*), so this text cannot show it. Dispatch needs a CGPT exact-version approval of **v1.5**, naming this path and the commit that contains it. Because CGPT's GitHub connector returns 403, Rogue records that approval on Issue #67, marked as relayed through Matt. Rogue gives the PL an Orchestrator dispatch record (`APPROVAL.md`) that cites it, together with the EB evidence. **That approval also constitutes CGPT's acceptance of the three register entries (gate G3).**

**Header note (engine semantics).** The header deliberately has **no `BROWSER: yes` line**. Under the installed ForgeV2 v0.3.0 `deliver` skill (§3, *Browser gate*), `BROWSER: yes` requires the Tester to drive the page itself. The sandboxed Tester has no network or Docker, so it would report INCONCLUSIVE and the PL would return ESCALATED. This WO changes nothing a user sees (AC7). Real-browser assurance is still mandatory (FOUNDRY WO contract, *Quality*), but it is delivered by the operator-run procedure of annex B and the independent Tester and DevSecOps verdicts of the companion WO `CRM-CLIENT-001R2-BA` (CL-D3, CL-D7).

## 0. Recovery record (v1.5)

| Item | Value |
|---|---|
| Chain | `CRM-CLIENT-001` (v1.3) → `CRM-CLIENT-001R` (v1.4) → **`CRM-CLIENT-001R2`** (v1.5, this WO). Each WO is a new ForgeV2 identity on the same engineering base `6e1766980e24d781d498727d4fe5db43cdeadbb7` |
| First failure | `CRM-CLIENT-001`, candidate `b190377c03df0e2d65b912458f47e065ded40d7c`: reviews PASS, controlled publication refused by the ForgeV2 secret scan on the serialised prompts. Recovered by v1.4 (finding R1). Record: #59 comment 6917491774; preserved at `/srv/CRM/evidence/CRM-CLIENT-001-original/` |
| Second failure | `CRM-CLIENT-001R`, candidate **`9271b481e013d4ed76338b49d4f25b89ca79b126`** (delivery record `33fe42162ff3b57030301d1d1b9633f5904bd9f7`, branch `forge/CRM-CLIENT-001R`): published, 642 unit tests OK, Auditor, Tester and DevSecOps PASS, actual commit and push scans clean. The **S3 operator CL-D5 scan** then found a **KEV-listed High vulnerability in a library that the browser process loads** (the pinned image's `libbrotli1`, via `libfreetype6`). Under annex B8.3 this blocks the run. Record: #65. Preserved at `/srv/CRM/evidence/CRM-CLIENT-001R-S3-abort/<run>/` |
| Status of `9271b481` | Technically reviewed and published, but **not accepted**, and never run at S3. It is not merged. Its branch and records are preserved unchanged, and no part of it is applied by Git to this WO |
| What this WO changes | Only the pinned runner image (finding I1). No operator state of crm-dev, beta or the host had been changed when S3 stopped |
| Reference material | **Read-only, optional:** `/srv/CRM/wo/CRM-CLIENT-001R2/reference/CRM-CLIENT-001R-9271b481.diff` (sha256 recorded in the dispatch record), the previous candidate's source diff from `6e176698`.<br>• The Engineer may read it and reuse its content as a starting point, but every line of the new candidate is written in the worktree by the Engineer and is the Engineer's responsibility.<br>• No Git operation (apply, cherry-pick, fetch) may use the previous branches or bundles.<br>• If the path cannot be read in the sandbox, the Engineer proceeds without it |
| Reporting discipline (binding clarification, CGPT 2026-11-16) | The delivery record publishes every prompt and specialist report as single-line JSON strings, and the engine's secret scan reads them.<br>• Specialists and the PL refer to the earlier publication failure only as **R1**. They never write the name of the download tool removed by R1, the scan rule id, or the annex B3 user option value.<br>• This discipline **must not conceal a genuine security finding.** Reports use safe finding identifiers, severities and verdicts, and put the full technical detail in the restricted evidence (the PL's private records, or a scratch note cited by path and sha256).<br>• A genuine finding that cannot be reported safely is a **BLOCKED** condition, never a reason to suppress evidence or claim PASS |
| Limits | This WO has its own ForgeV2 counters, as any new WO does. It is a genuine recovery after a **gate finding**, not a way round exhausted limits: the previous WO used 2/1/1/1 of 4 executions |

## 1. Authority and governing records

| Item | Value |
|---|---|
| FOUNDRY provenance (v1.0–v1.1) | `5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0`, preserved as the historical framework baseline |
| FOUNDRY for the new v1.2 decisions | **`84fedf0a74017237aa1bd650d8560350c91c7f0e`** (adopted main, per CGPT 2026-11-16). `standards/work-order-contract.md` is byte-identical at both revisions (sha256 `cbb6eb3ae62bf7877ae470abf2297a5af5ffb23ca617581a9a85077dd9a8ebcc`). Also applied: `ROGUE.md` `5d7406a5…6aa5` (§A2/§H: PL Git authority, checkout gate) and `standards/project-scaffolding.md` `b52fdc3d…427c` |
| Engine | ForgeV2 `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, plugin 0.3.0.<br>`skills/deliver/SKILL.md` `6a87998258a5a91e52f492fa35708432460ebc892fd4a103240fc130e370bd73`<br>`ORCHESTRATOR.md` `e0c529e26c33e5bea8ffa67b25dff18a19958bd24f216eb8d6d1e7c434a95c28`<br>`lib/forgelib.py` `6a7d587a79da13de733dc41a97e6f499c163062151175acda74918ca19f6dc55`<br>`bin/forge-start` `fdd23d5712817ebc707a04428fee123999366c96d28e487cd82cacccc96366d3` |
| Product authority | Matt's PO approval of the Vision, the Backlog (PBI-018..029) and CRM-D020..D032 at `dc6fb4ced68d9139c2332af973084239492104b3` (Issue #54, 2026-11-13T12:04:29Z) |
| Architect decisions | CL-D1, CL-D3, **CL-D7** (accepted), **CL-D8** (accepted conditionally, on EB1–EB6) and **CL-D5 as revised** (CGPT, 2026-11-16); see §12 |
| Parent PBI | **CRM-PBI-016** (container release packaging). It enables CRM-PBI-018 (CRM-FG-001) and CRM-PBI-020 |
| **Engineering base (exact)** | **`6e1766980e24d781d498727d4fe5db43cdeadbb7`** (= `KNOWN_COMMIT`). On 2026-11-16 it equals GitHub `main` (API), the PL's local `main` and the local `origin/main`. The PL's checkout is clean, has no URL rewrites and has the canonical SSH origin. See §10 and CL-D8 |
| Pinned EspoCRM | `espocrm/espocrm:10.0.12@sha256:b50245d1e291b2636116b0396ce0d06018ffcded6a6c61c7af2420443a20f3ec` |
| Unit baseline | The `main` unit suite gives 564 OK and 1 skip, run as `nobody` from a `git archive` copy (Issue #56 comment 6858541012) |

## 2. Problem and verified facts (PL preflight, read-only)

The CRM has no path for CRM-owned browser code. The FirmGroup *Group Members* tab and the WIP/Revenue tab both need client views, and copying JavaScript by hand into a runtime is forbidden. This WO delivers the mechanism only, with no product UI.

The image was inspected by `docker create` followed by `docker export`; no container was started. For each upstream file the sha256 is the file inside the pinned image.

| # | Fact | Evidence |
|---|---|---|
| F1 | On every start the entrypoint chowns `./data`, `./custom` and `./client/custom` to www-data. It recopies `client/` only when `/var/www/html/client` is itself a mount (not the case here) and never touches `client/custom` | `/usr/local/bin/docker-entrypoint.sh` `9f0b70326ec5065e1358b782c39eb264e08cf14df01dfb8c41085fbec32020e2` |
| F2 | `client/custom/modules` is a **reserved** EspoCRM path, used for extensions | `Espo/Core/Utils/File/Manager.php` `RESERVED_CUSTOM_PATH_LIST`; `Permission.php` `687e8d73f3b4258ae66f69b91ef741eedad8c2335ad43250675558a4b847e161` |
| F3 | **Cache invalidation.**<br>• Outside developer mode the loader versions module URLs with **`appTimestamp`** (`?r=<appTimestamp>`).<br>• `clear-cache` changes only `cacheTimestamp`.<br>• `appTimestamp` changes only through `bin/command update-app-timestamp`, an upgrade or a migration. Its value is `time()` in whole seconds.<br>• It is stored as a state parameter in `data/state.php` and exposed to the client as a global setting | `ClientManager.php` `725121562a41876d79db16f6ace4d961bb1aae9cb30123b7bfafbee98ab62f40`; `DataManager.php` `a701fe39d936072b63c3454ef7299df18101e600ecd6860cc8bb0062f1ccad0f`; `UpdateAppTimestamp.php` `15d82eae42aa72ccc8ebf541d2935fc68ad24819d89868143370493e38cd098b`; `Config/InternalConfigHelper.php` `8e6c9d99b73373a96ec6270ab71af4bac20ddb7bb04cc7ecaee905c20d8ea2e2` |
| F4 | The CSP is `script-src 'self' 'nonce-…' 'unsafe-eval'`, so client code must be same-origin | `ClientManager.php` line 116 |
| F5 | The repository has no `client/` tree. `scripts/deploy_custom.sh` (`d1aaa430e150e95c8e42c93ba3544afdcfbcd40117e0eed1aa0083c7ef9ed67b`) deploys only `custom/Espo/Custom` and runs `clear-cache` and `rebuild`, with no `update-app-timestamp` | `main` @ `6e176698` |
| F6 | Persistence already covers `client/custom`: `CRM_PERSISTENT_DIRS`, `client-custom.tar.gz` in backup and restore, the compose mount checks and `make_runtime` | `common.sh` `34f622395c169ae2e3cc30229ba72ed2073f29a7e5d5fe23d5511fe955d0fff1`; `backup.sh` `ba67fa26fdb49e70f4a53fb329af6813e56e2fc7ac65a83fc790b33b648c0fc3`; `restore.sh` `c1e92f0d43e730c5b627d2a3f5afc67f27529d216fde891010df42b94d3ac78f`; `deploy_release.sh` `54aaedb320e9a26dfccbc1e5916a72cf021483b75beef14ec9e68ac4640524d7` |
| F7 | A release is the `git archive` of a commit minus `.forge/`. A tracked `client/custom/src/` is therefore bundled and checked by `verify-tree` without any change to `release.py` (`0560e352ba3e5fa79fe08694542550ed33b021fef61dd017e2e7c8c74bd06f8f`). The new deploy behaviour reaches beta **only** through a future, separately authorised `deploy_release.sh` run | `release.py` `EXCLUDED`; `deploy_release.sh` `start_stack` |
| F8 | **The module format is AMD.** In `client/lib/espo.js` (`9c88b9db81ffdb35f99f9c77619a8fb56a338a355672173e670dc88ca9ebd318`):<br>• `custom:<p>` maps to `client/custom/src/<p>.js`;<br>• `define` is AMD, and an anonymous `define` is bound to its module id through the requesting URL;<br>• a factory that returns `undefined` fails;<br>• the URL gets `?r=<appTimestamp>`;<br>• untranspiled `import`/`export` is not supported.<br>**Canary:** `define([], function () { return Object.freeze({name: 'crm-release-canary', contract: N, describe: function () { return 'crm-release-canary/' + N; }}); });`, loaded through `Espo.loader.requirePromise('custom:crm/release-canary')` | upstream `espo.js` (minified) |
| F9 | No browser automation or vulnerability scanner is installed or approved on DOCKER1, and no Playwright image is present (re-checked 2026-11-16). No earlier CRM WO produced in-cycle real-browser evidence: CRM-003 was escalated | host check; `.forge/CRM-003/REPORT.md` |
| **F10 (v1.2)** | **The engine cannot place an operator step inside one WO.**<br>• The PL is one headless run that "returns only when it has reached a final status" (`ORCHESTRATOR.md` §2).<br>• Every final status closes the ledger (`SKILL.md` §4).<br>• After a close, `spawn()` refuses every dispatch (`forgelib.py`: "Work Order … is closed; no further dispatch").<br>• Reviewers may be dispatched one at a time while the decision is `REVIEW` (`needs_review`). However, `SKILL.md` §3 requires the three reviewers to be given in one command, and a WO instruction that conflicts with the procedure is `BLOCKED`.<br>• The documented action on ESCALATED is "issue a new, narrower WO" (`ORCHESTRATOR.md` §4). Suffixed follow-on WOs are established CRM practice (CRM-003-F, CRM-009-F…I).<br>Hence CL-D7 | engine files of §1, read-only |
| **F11 (v1.2)** | **The PL's local `main` cannot be advanced by any supported PL-owned tool.**<br>• `forge-start` resolves `--base` locally with `git rev-parse` and never fetches (`forge-start` line 50).<br>• The PL guard forbids direct mutating Git, and `forge-commit`/`forge-push` cannot update `main`.<br>• The correction, FV2-SYNC-001 (`maff0000/forgev2#7`), is **open and not installed**; its delivery is itself `BLOCKED — CREDENTIAL_ADMIN`.<br>• The CRM `main` fast-forwards of 2026-11-11..13 (reflog) were made by root through `runuser` as `forgev2-pl`. Adopted `ROGUE.md` §A2/§H no longer permits that. Hence CL-D8 | `maff0000/forgev2#7`; reflog of `/srv/CRM/main`, read-only |
| **F13 (v1.3)** | **Browser compatibility.**<br>• Playwright release notes: 1.64.x was tested against **Google Chrome 155**; **1.65.0 and 1.65.1 were tested against Google Chrome 157**.<br>• CfT Stable is **157.0.8103.78** (CfT JSON, 2026-11-15T21:10Z). Its linux64 artefacts were published 2026-11-11, and the zip and binary hashes are in annex B2a.<br>• The 1.65.1 wheel (`5660e0b0…c442`) requires only greenlet, bundles Node 26.13.1, and has no `__version__` | GitHub releases of `microsoft/playwright-python`; CfT JSON; downloads read as data |
| **F12 (v1.2; historical, superseded by F13 for selection)** | `playwright/__init__.py` in the 1.64.1 wheel defines **no** `__version__`. The version is `playwright-1.64.1.dist-info/METADATA`, `Version: 1.64.1`. The wheel's `playwright/driver/package/browsers.json` pins **chromium revision 1248, browserVersion 156.0.8078.4**, and the wheel bundles **Node.js 24.22.1** as `playwright/driver/node` | wheel `577b8d88…7e2`, inspected as data with `zipfile`, nothing executed |

**PBI-016/017 deviation.** This WO keeps the deploy-into-runtime model (CRM-D017 deviation) and extends it to `client/custom/src`. It claims **no** baked-image or clean-host acceptance, and it does not implement PBI-016 (CL-D4).

## 3. Intended outcome

1. A tracked, CRM-owned `client/custom/src/` is the only source of CRM browser code (CL-D1).
2. `scripts/deploy_custom.sh dev|beta` deploys `custom/Espo/Custom` **and** `client/custom/src`, with the same stop, secure, stage and rename discipline. `client/custom/modules` and every other runtime path are left untouched.
3. Each deploy then runs `clear-cache`, `rebuild` and **`update-app-timestamp`**, with a strict check that the timestamp advanced (annex B5).
4. Defined failure semantics after the swap: no false success, the failed step is named, the previous trees are recovered, then either a recovered cache-bust or a controlled shutdown (annex B7).
5. Backup, restore and rollback cover the client tree.
6. A non-user-visible AMD canary, `custom:crm/release-canary`, and a hardened runner, isolation probe, journeys and offline evidence verifier. These let the operator prove loading, versioning, cache-bust, rollback and recovery in a real browser (annex B), and the companion WO `CRM-CLIENT-001R2-BA` has that evidence assessed independently.
7. All existing customisations and protections keep working.

## 4. In scope (allowlist, exhaustive; paths unchanged from v1.1, with content refined for A2 and CL-D5)

| Path | Change |
|---|---|
| `client/custom/src/crm/release-canary.js` | **new.** The AMD canary of F8, **contract 1**. No network, DOM, storage or globals. It is not referenced by any clientDefs, layout, `app/client.json`, navbar or i18n |
| `scripts/deploy_custom.sh` | Deploy `client/custom/src`; keep the previous trees until success; `update-app-timestamp` with an advance check; the annex B7 failure and recovery semantics; integer appTimestamp output only |
| `scripts/lib/common.sh` | Only if a shared swap helper is factored out. No weakened guard, and CRM-TEST-001 M1–M4 must still kill |
| `tests/unit/test_scripts.py` | New tests (AC2–AC5, AC4b, AC4c). Existing tests are unchanged, except expected call lists that gain the new step |
| `tests/unit/test_client_custom.py` | **new.** Static policy for `client/custom/` and `tests/browser/` (AC1, AC7, AC11), and the AC6a tests of `verify_evidence.py` on synthetic packages **generated inside the test** (no committed evidence fixtures) |
| `tests/browser/requirements.lock` | **new.** Exactly the two hash-pinned wheels of annex B2 (v1.3) |
| `tests/browser/entry.sh`, `probe_isolation.py`, `journeys.py`, `verify_evidence.py` | **new.** Container entry point, isolation probe, journeys J1–J5 and the offline verifier (annex B2–B6). They run only inside the hardened container, except `verify_evidence.py`, which only reads files and is run in the specialist sandbox |
| `tests/browser/fixtures/canary-transition/v2/crm/release-canary.js` | **new.** Identical to the canary except **contract 2** (annex B5) |
| `docs/RELEASE.md`, `docs/BETA.md`, `docs/BUILD.md` | The client delivery, cache-bust, failure and recovery, backup and rollback, and browser-run procedure (annex B9 summary), plus the PBI-016 deviation note |
| `security/EXTERNAL_CODE_REGISTER.yaml` | The `playwright-python-browser-runner`, `chrome-for-testing-stable` and `grype-cl-d5-scanner` candidate entries (annex B2, B2a, B8), all `usage: test-only, operator-run` |

**v1.5 (finding I1):** the replacement image digest and config ID appear in the candidate in exactly these allowlisted paths, and the Engineer must update them to annex B1: the `EXTERNAL_CODE_REGISTER.yaml` entry `playwright-python-browser-runner` (`version`, `amd64_manifest`, `config_id`) and the image constants of `tests/browser/verify_evidence.py`, with the tests that reference them. No other path changes for this finding.

Any other path is out of scope, and a need for one is a **stop** (§11).

## 5. Exclusions (unchanged from v1.1)

- `custom/Espo/Custom/**`, `config/access/**`, `deploy/**`, `scripts/release.py`, `scripts/deploy_release.sh`, `scripts/backup.sh`, `scripts/restore.sh`, `scripts/up.sh`.
- Any metadata or layout change that makes client code user-visible.
- `client/custom/modules/**`, which is never written, removed or swapped.
- The running beta (`/srv/CRM/runtime/beta`, `/srv/CRM/deploy`), Salesforce, the legacy WIP repository and its data, FOUNDRY, ForgeV2 and other host applications.
- Any CDN, npm, Node toolchain, bundler or minified or vendored blob in `client/custom`.
- Any persistent Docker network, image or container after WO closure; any firewall rule; any use of host networking or the Docker socket by the browser runner.

## 6. Acceptance criteria

**The assessing WO.** Each AC is assessed in **CRM-CLIENT-001R2** (this WO), offline and in the sandbox, unless it is marked **BA**. A BA criterion is assessed by the Tester and DevSecOps of **CRM-CLIENT-001R2-BA** on the operator's immutable evidence (CL-D7).

| AC | Criterion | Evidence |
|---|---|---|
| AC1 | `client/custom/` in Git holds only `src/**`.<br>• Allowed types are `.js`, `.css`, `.json`, `.tpl` and `.svg`, with no symlinks, no executable bit and no file over 256 KiB.<br>• There is no `modules/`.<br>• Every `.js` file is AMD, with no `import`/`export`.<br>• No remote URLs, `eval`, `new Function`, `document.write`, `innerHTML` assignment, absolute-URL fetch or XHR, or storage APIs.<br>• The v2 fixture differs from the canary only in the contract value | `test_client_custom.py`, with a broken fixture for each rule |
| AC2 | `deploy_custom.sh` replaces the runtime `client/custom/src` as a whole, staged and renamed on the same filesystem, after the stop and with path security as for `Espo/Custom`.<br>• It refuses symlinked or redirected `client`, `client/custom` or `src`.<br>• Files removed from Git disappear from the runtime | `test_scripts.py`; each refusal fails **before** any swap |
| AC3 | `client/custom/modules`, and every non-`src` entry in `client/custom`, are byte-identical across a deploy, a failure and a recovery | `test_scripts.py` hash comparison |
| AC4 | The success path runs `up --wait`, `clear-cache`, `rebuild` and `update-app-timestamp`, in that order, in crm-app as www-data.<br>• The appTimestamp after the update is strictly greater than before; one retry after 1 s, otherwise fail.<br>• With the stack stopped, it prints that the cache-bust was skipped and how to complete it | `test_scripts.py`, recorded fake-docker calls |
| AC4b | **Post-swap failure (annex B7).** For an injected failure at each post-swap step and at each recovery step:<br>• the exit code is non-zero and step-specific;<br>• `FAILED STEP: <step>` is printed, with no success line;<br>• the previous trees are restored byte for byte, and `.failed-<stamp>` is retained;<br>• then either a recovered cache-bust, or a stopped stack with `RECOVERY FAILED` | `test_scripts.py` failure injection (J4 in BA) |
| **AC4c (v1.4)** | **Swap failure, leftovers and interruption (R5).**<br>• **Swap failure (exit 20):** at each swap failure point (moving live aside, installing staging, for each tree), the previous trees are live and byte-identical, **no `.deploy-<stamp>` staging directory remains** for either tree, the stack is left stopped, and no success line is printed.<br>• **Leftovers:** with a leftover `.Custom.deploy-*`, `.Custom.old-*`, `.Custom.failed-*`, `.src.deploy-*`, `.src.old-*` or `.src.failed-*` from an earlier stamp present, the next deploy installs exactly the repository tree as live (byte-identical), never reads from, moves or deletes the leftover, lists every leftover it sees on stderr (`LEFTOVER: <name>`). Release bundles are built from Git and are unaffected. `docs/RELEASE.md` gives the operator removal procedure.<br>• **Interruption:** after the first swap, the script traps INT, TERM and HUP. A signal during any post-swap step, or during the second swap, runs the AC4b recovery (stop, restore the previous trees, cache-bust), prints `INTERRUPTED: <signal>`, and ends `RECOVERED` (exit 47) or `RECOVERY FAILED` with the stack stopped. A signal before the first swap removes staging and leaves the stack stopped, with the previous trees untouched. Each case is tested by sending the real signal to the script under the fake-docker harness | `test_scripts.py` |
| AC5 | **Backup and rollback.**<br>• A backup, a deploy of B over A, then `restore.sh`, gives A back byte for byte in `client/custom/src`.<br>• Redeploying A over B removes the files that exist only in B.<br>• Both are followed by a cache-bust | `test_scripts.py` (J3 and J5 in BA) |
| **AC6a** | **Runner and verifier correctness (offline).**<br>• `verify_evidence.py` recomputes every AC6b verdict from the raw files and ignores `result.json`.<br>• **(v1.5, I1) Image pin:** its image constants equal annex B1 exactly, and a package whose recorded image index, amd64 digest or config id equals the **previous** pin (`7d030ac0…15c0` / `b6862d30…60c0`) is a FAIL naming the cause.<br>• On a generated *good* package it returns PASS. It returns FAIL, naming the cause, for each tampered variant: a missing file; a `SHA256SUMS` mismatch; a non-advancing or equal `r`; a cached or absent fetch of the new URL; a CSP event; a canary console error; an unexpected isolation success; a wrong Playwright distribution version; a wrong browser version or revision; a candidate, image or wheel identity mismatch; a cleanup-failure record.<br>• `journeys.py` writes exactly the annex B6 layout | `test_client_custom.py` |
| **AC6c (v1.3)** | **Public-safe summary.**<br>• `verify_evidence.py --public-summary` deterministically emits `public-summary.json` and `EVIDENCE.md` with only the annex B6 *public-safe* fields.<br>• For a generated package seeded with each forbidden item (IPv4 and IPv6 addresses, hostname, URL, port, container or network id, env name or value, non-`example.test` e-mail address, outside path, free log text, and (v1.4) the run's browser credential value, passed to the sanitiser through the environment only), the sanitiser **refuses** to emit it, with exit non-zero and the item class named.<br>• On the clean package, the output contains none of them | `test_client_custom.py` |
| **AC6b (BA)** | **Real browser** on synthetic crm-dev, with the B1 image pinned by digest, the CL-D5 scan gate passed, B4 isolation proven first, and D0–D5 in order (annex B5):<br>• **J1:** contract 1, URL `r = a1 > a0`;<br>• **J2:** contract 2, `a2 > a1`, and a new network fetch;<br>• **J3:** rollback to contract 1, `a3 > a2`;<br>• **J4:** injected failure, then recovered contract 1 and an advanced `r`;<br>• **J5:** after restore, the canary is absent and the regression screens match D0.<br>For every journey, no CSP violation and no canary console error. The login, Account list and detail, Enquiry list and detail, and Stream panels render | Annex B6 package; the independent Tester verdict in BA |
| AC7 | No user-visible change: the canary is unreferenced in any metadata or layout, and the `custom/**` diff is empty | static test; diff limited to §4 |
| AC8 | **Regression.**<br>• The full unit suite passes as non-root from a `git archive` copy, with at least the starting count.<br>• `tests/load` passes.<br>• CRM-TEST-001 M1–M4 still kill.<br>• The existing `deploy_custom` and guard tests pass unchanged | Orchestrator host procedure (as CRM-TEST-001 §7); Tester re-run on the PL snapshot |
| AC9 | **Release integrity.**<br>• A bundle of the candidate passes `release.py verify --sha256`.<br>• `RELEASE.json` lists the canary with its sha256.<br>• `verify-tree` refuses a file injected under `client/custom/src` | Temporary directory, as `nobody` |
| AC10 | The documentation is truthful. In particular (v1.4), the exit-20 text says that a swap failure restores **both** trees, and `docs/BUILD.md` says the previous tree is kept until every step succeeds: client delivery, cache-bust, failure and recovery, rollback, the browser procedure including cleanup and manual recovery (annex B9), and the PBI-016/017 deviation. No baked-image or clean-host claim | Auditor |
| AC11 | **Runner integrity.**<br>• `requirements.lock` equals annex B2 exactly, with `--hash` lines.<br>• **(v1.5, I1)** The register entry `playwright-python-browser-runner` equals annex B1 exactly (tag `v1.65.1-noble`, amd64 manifest, config id), and a static test asserts that the register, `verify_evidence.py` and annex B1 name the same digest and config id.<br>• `journeys.py` and `probe_isolation.py` contact only `CRM_BROWSER_BASE_URL` and the probe targets passed in as data, with no credentials or addresses as literals.<br>• `verify_evidence.py` does no network I/O.<br>• **The version check uses `importlib.metadata`, not `playwright.__version__`.** Playwright 1.65.1 is launched with `executable_path` set to the pinned CfT binary. The binary and running-browser version checks and the compatibility probe are in place, and the runner never launches anything under `/ms-playwright` (annex B2.3).<br>• **(v1.4, R4) Pre-launch order:** the CfT binary sha256 check and the `ldd` checks of the binary and of the bundled Node driver (including `libatomic.so.1`) complete **before any Playwright driver or browser process starts**. A test with a wrong binary hash, and one with a missing library, each show a non-zero exit, a named cause, and **no** `sync_playwright()` start or launch attempt; a static test asserts the order | `test_client_custom.py`; DevSecOps |
| **AC12 (BA)** | **Operator procedure and cleanup (annex B9).** The package's `cleanup.json` shows all of the following, and any cleanup failure is a FAIL:<br>• the crm-dev env file restored byte-identical (`cmp` and sha256);<br>• no `crm-client001r2-*` container or network remaining;<br>• crm-app back on crm-net only, healthy, and serving `/` with the pre-test config hash;<br>• the beta directory metadata, file hashes and container IDs/StartedAt unchanged | `cleanup.json`, `beta-before.json` and `beta-after.json`; Tester and DevSecOps in BA |

A skipped, unrun or screenshot-only check is **not PASS**.

## 7. Security and supply-chain controls

- **Source of truth:**
  - Git for dev;
  - a `--sha256`-anchored, verified release for beta;
  - the transition tree is only an overlay of the candidate's own blobs (annex B5).
- **Client code:** same-origin, plain hand-written AMD, with no third-party JavaScript.
- **Path safety:** `real_dir`, `owned_private` and `secure_dir` are reused; no recursion through a symlink; `--one-file-system`; the reserved `modules/` is never touched.
- **Browser runner (annex B1–B4):**
  - the image is pinned by digest, with offline hash-locked wheels;
  - uid 65534, read-only rootfs, all capabilities dropped, `no-new-privileges`, default seccomp and AppArmor;
  - no Docker socket and no host network;
  - a per-run internal network with no host-side bridge address, and isolation proven by probe before any journey.
- **Isolation, stated precisely.** The browser has **no intended direct network path** to crm-db, beta, the host or external destinations, and the probe proves that for the listed targets. The **application** (crm-app) keeps its legitimate database connection. The design therefore does **not** prevent application-layer effects reached *through* crm-app, such as any data the synthetic test user can read or change through the CRM API. That is acceptable only because crm-dev holds synthetic data and the test users are synthetic.
- **Vulnerability gate (CL-D5, annex B8).** The pinned image, wheels and CfT tree are scanned by the pinned Grype before first use, and material findings are a gate. The executed browser is the current Stable CfT 157.0.8103.78, hash-pinned and mounted read-only. The image's pre-stable Chromium is never executed (annex B2.3, B8.4).
- **Public evidence (v1.3).** Raw evidence stays only in the restricted store. Git receives only the AC6c public-safe summary, checksums, verdicts and provenance (annex B6).
- **No secrets or customer data:**
  - only synthetic crm-dev data and synthetic `@example.test` users;
  - credentials are passed by env file and never appear in argv or evidence;
  - gitleaks runs on the candidate, the snapshot and every evidence package.

## 8. Roles, independent criteria and evidence paths

| Role (this WO) | PASS only if |
|---|---|
| Engineer | §4 is implemented, and every test for AC1–AC5, AC4b, AC4c, AC6a, AC6c, AC7, AC9 and AC11 exists and is mutation-sensitive. Nothing outside §4 changes |
| Auditor | The diff matches §4 and §5. F1–F12 hold against the recorded upstream facts. The documentation is truthful |
| Tester | AC1–AC5, AC4b, AC4c, AC6a, AC6c and AC7–AC11 are evidenced on the **same unchanged candidate**, and the unit-suite re-run on the PL snapshot passes. AC6b and AC12 are **not** assessed here; they belong to CRM-CLIENT-001R2-BA |
| DevSecOps | §7, AC1 and AC11 hold. The swap and recovery ordering is sound, and the runner hardening in the source is sound. This review happens **before** any root execution of `deploy_custom.sh` (sequence S2) |

- **Engine records:** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-CLIENT-001R2/`, holding only `REPORT.md` and `prompts/*.md`.
- **PL evidence:** `/home/forgev2-pl/crm-evidence/CRM-CLIENT-001R2/`, indexed by `CRM-CLIENT-001R2.sha256`.
- **Specialist-readable scratch:** `/srv/CRM/worktrees/.forge-scratch/CRM-CLIENT-001R2/`, holding `snapshot-<sha12>/` (§6b pattern of CRM-TEST-001) and `diff-<sha12>/`.
- **Operator evidence store** (annex B6), used by the BA WO: `/srv/CRM/evidence/CRM-CLIENT-001R2/<run>/`. It is root-owned, group `forgev2-pl`, directories 0750 and files 0640, and it is created at sequence S3, not now.
- **Execution limit:** four executions per specialist, including the first. Exhaustion is FAIL with escalation to CGPT. CRM-CLIENT-001R2-BA has its own counters but **cannot change any §4 path** (CL-D7), so it is never a bypass.

## 9. Assurance sequence (non-circular; A1)

| Step | Actor | Action | Exit condition |
|---|---|---|---|
| **S1** | Engineer (this WO) | Builds the candidate with unit tests, deploy failure and recovery tests, the runner and the verifier | Engineer `completed`, then `forge-commit` |
| **S2** | Auditor, Tester and DevSecOps (this WO), **independently** and in the engine's single concurrent round on the unchanged candidate | Auditor: diff and facts. Tester: offline ACs. DevSecOps: static security review, including `deploy_custom.sh` **before root ever runs it** | PL `DELIVERED` (all three PASS on the same candidate `C`). Otherwise correction rounds, or ESCALATED |
| **S3** | Operator (Rogue as root, under this approval) | **Pre-root verification gate OP-V** (annex B9.1). Checks: the exact archive of `C` from two sources; the `deploy_custom.sh` blob; the root-execution boundary; a fresh synthetic backup with a restore dry check; the recovery procedure; the CL-D5 scan | Every OP-V item passes, or the run is BLOCKED |
| **S4** | Operator | Controlled synthetic browser run D0–D5 (annex B4–B7), with cleanup always run (B9). The package is sealed in the evidence store | `SHA256SUMS` sealed; `cleanup.json` all-true. Otherwise the run FAILS (no BA dispatch) |
| **S5** | Tester (**CRM-CLIENT-001R2-BA**) | Independently evaluates the immutable package with `verify_evidence.py`, the raw files and the trace (AC6b, AC12). May request one bounded repeat | Tester PASS |
| **S6** | DevSecOps (**BA**) | Reviews the final unchanged candidate against the *actual* security evidence: `identity.json`, `isolation.json`, the CSP log, the scan report and `cleanup.json` | DevSecOps PASS |
| **S7** | PL (BA), then Rogue | BA `DELIVERED`, then Rogue validates the PL JSON and the ledger and returns **READY_FOR_CGPT** | Never before S5 and S6 PASS |

**Engine notes.**
- In both WOs the engine runs Auditor, Tester and DevSecOps concurrently on one candidate. Each reviewer is independent and sees no other reviewer's findings, so the FOUNDRY order Engineer → Auditor → Tester → DevSecOps is met in substance: every browser-dependent verdict (S5, S6) comes after the evidence exists.
- The BA Auditor checks the evidence-record commit (annex `CRM-CLIENT-001R2-BA.md`).
- **Operator testing is not a specialist PASS.** S3 and S4 produce evidence only.

## 10. Repository and workspace (exact base; A3, CL-D8)

- **Start command:** `forge-start --wo CRM-CLIENT-001R2 --repo infosec-estateresearch/CRM --host DOCKER1 --root /srv/CRM/main --worktrees /srv/CRM/worktrees --base main --known-commit 6e1766980e24d781d498727d4fe5db43cdeadbb7`.
- **Exact-base gate EB** (Orchestrator, read-only; any failure means engineering dispatch is **BLOCKED**, with no workaround):
  - **EB1.** This WO's docs PR is merged at an exact merge SHA `M`. GitHub compare `6e176698…M` lists only `work-orders/CRM-CLIENT-001*.md` paths: the three historical v1.3 files, unchanged since `9065f80f`, and the three v1.4 `CRM-CLIENT-001R2*.md` files, with `behind_by = 0`.
  - **EB2.** GitHub `main` equals `M`. If it has advanced further, every commit after `M` is reviewed, and any non-docs change is a stop for CGPT.
  - **EB3.** The PL's local `main` equals `6e176698…`. Its tracked and untracked tree is clean. It is on branch `main`, with the origin `git@github.com:infosec-estateresearch/CRM.git` for fetch and push, no `url.*` rewrites, no `core.hooksPath` and no fsmonitor. Inspection is read-only, with `GIT_OPTIONAL_LOCKS=0`.
  - **EB4.** No `forge/CRM-CLIENT-001R2` branch, worktree, scratch directory or ledger exists, and no other WO is in flight. The preserved `forge/CRM-CLIENT-001` and `forge/CRM-CLIENT-001R` branches, worktrees and **closed** ledgers remain by design (§0). They are not in flight and are never touched.
  - **EB5.** The WO file given to the PL is byte-identical (sha256) to the blob of this path at `M`. It is placed outside the repository, readable by `forgev2-pl`.
  - **EB6.** `forge-start` prints `base_sha = 6e1766980e24d781d498727d4fe5db43cdeadbb7`, and the committed ledger later shows the same value.
- **Why the base is `6e176698` and not `M`.**
  - The approved text can only name a commit that already exists when it is approved (WO contract, *Approval provenance*).
  - The installed engine cannot move the PL's `main` to `M` (F11), and root must not do it on the PL's behalf (`ROGUE.md` §A2/§H).
  - EB1 proves that `M` differs from the base only by this WO's own documents, so the engineering tree is exactly the approved one.
  - The candidate's later PR to `main` touches disjoint paths.
  - FV2-SYNC-001 is the permanent fix. Until it is installed, CL-D8 applies.
- **Worktree:** `/srv/CRM/worktrees/CRM-CLIENT-001R2`, on branch `forge/CRM-CLIENT-001R2`.
- **Specialists:** run as `forgev2-pl` under the engine sandbox and use no Git; the PL provides snapshots.
- **Engineer-authored code** runs only in the sandbox, as `nobody` on the host from `git archive` copies, or as uid 65534 inside the browser container. It never runs as root or as the PL, with one exception: the reviewed `scripts/deploy_custom.sh` is run by root from the verified archive at S3–S4 (G2).

## 11. Entry gates, stop conditions and reporting

| Gate | Requirement | State |
|---|---|---|
| G1 | CGPT exact-version approval of **v1.5** (path and commit), relayed and recorded on Issue #67, covering this WO, annex B, the BA template and the three register entries (G3) | open |
| G2 | Sandbox entry gate; see the assessment below | evidence ready; CGPT acceptance open |
| G3 | **Browser component and vulnerability gate (CL-D5).**<br>• CGPT accepts the register entries (v1.5: by the G1 approval of this version).<br>• The CL-D5 method is approved.<br>• At S3 the CfT acquisition and freshness gate (annex B2a) pass, and the scan runs with no unresolved material finding (annex B8).<br>• The RepoDigest and config ID are verified after the pull | open |
| G4 | Exact-base gate EB1–EB6 (§10) | open (EB3 and EB4 pass today) |
| G5 | **Run preflight:**<br>• crm-dev is synthetic and backed up;<br>• the browser subnet is unused;<br>• beta snapshot `beta-before.json` is taken (at preparation: `0:0 700 1794416166`);<br>• no stale `crm-client001r2-*` objects exist | open (S3) |
| G6 | Pre-root verification gate OP-V (annex B9.1) | open (S3) |
| G7 | Cleanup verification (annex B9.3), which is a FAIL, not a warning | open (S4) |

**G2 assessment for CRM-CLIENT-001R2** (re-verified 2026-11-16):

| Component | Identity |
|---|---|
| ForgeV2 | `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, with a clean tracked tree. The only ignored entry is the accepted `plugin/lib/__pycache__/forgelib.cpython-313.pyc` |
| Claude | 2.1.317, sha256 `eb224419e344575faa4a1f39b290b649425a10cd5ee2ef1d003480cd9ae57eb0` |
| bubblewrap | 0.12.0-1~deb13u1, sha256 `573236e5328ac2ebb08f59ae3a9805b4f8d12bdef14be8af4450d5463294985f` |
| `forgelib.py` | `6a7d587a79da13de733dc41a97e6f499c163062151175acda74918ca19f6dc55` |

- **What carries over.** The 2026-11-09 CRM-001 acceptance (`maff0000/forgev2#5` comment 6746699026) and the CRM-TEST-001 acceptance are **specific to those WOs**. They are not engine certification: ENGINE-SANDBOX-TEST-001 (`forgev2#5`) is still **open**.
- **Applicability:**
  - Specialists need file editing, Python and shell in the sandbox, plus reads of the PL snapshot and (in BA) the operator evidence store.
  - No sandbox network, Docker or Git access is requested.
- **New exposure.** Root runs the Engineer-edited `deploy_custom.sh` against crm-dev. Mitigations:
  - it runs only from the verified archive of `C`;
  - it runs only after the S2 Auditor and DevSecOps PASS and the OP-V gate;
  - it runs only on synthetic crm-dev;
  - AC4/AC4b/AC4c cover it.

  Engineer browser code runs only in the hardened runner as uid 65534.
- **Limitations:**
  - The sandbox's Git read isolation has not been established.
  - Root-owned host files appear as uid 65534 inside the sandbox.

  Both are tolerated because snapshots are used. Any observed Git use by a specialist is a recorded deviation.

**Stop immediately** for any of the following:
- a need outside §4, or any write to `client/custom/modules`;
- a failed security, isolation, scan, entry or cleanup gate, including an unexpected probe success;
- a digest or hash mismatch;
- a candidate change after review;
- any contact with beta, Salesforce or real data;
- an exhausted execution limit;
- unverifiable EspoCRM 10.0.12 behaviour.

**Reporting.**
- This WO's PL `DELIVERED` is **not** READY_FOR_CGPT for acceptance or merge. Rogue reports it to CGPT as *"S2 complete; candidate `C` frozen; proceeding to S3"*.
- The PR of `forge/CRM-CLIENT-001R2` is labelled *do not merge: assurance continues in CRM-CLIENT-001R2-BA*.
- READY_FOR_CGPT for CRM-CLIENT-001R2 is returned only at S7. **No beta deployment.**

## 12. Decisions

| ID | Decision | Status |
|---|---|---|
| CL-D1 | CRM-owned client source lives exclusively under `client/custom/src/`. `client/custom/modules/` is never overwritten or managed. The existing secured deploy and release processes are kept | **Decided** (CGPT, 2026-11-16) |
| CL-D2 | Real-browser component: the official Playwright Python image, pinned per annex B1, with dependencies per B2, hardened per B3 and isolated per B4 | Selected; CGPT acceptance of the register entry open (G3) |
| CL-D3 | Operator-run real-browser tests, followed by independent Tester verification, with the annex B6 package and route. The Tester issues its own verdict and may request one bounded repeat. A screenshot alone is insufficient | **Decided** (CGPT, 2026-11-16) |
| CL-D4 | Baking `client/custom` into an image is PBI-016 work, not this WO | Recorded |
| CL-D5 | **Vulnerability assessment:**<br>• Grype `v0.121.0`, subject to checksum, provenance and scan verification;<br>• the image, the two wheels and the CfT tree are scanned;<br>• the executed browser is **CfT Stable 157.0.8103.78**, not the pre-stable bundled Chromium (annex B2a, B8) | **Decided as revised** (CGPT, 2026-11-16). The v1.3 combination (Playwright 1.65.1 with CfT 157) needs this approval |
| CL-D6 | Canary transition by committed fixtures overlaid from one candidate (annex B5) | PL design |
| **CL-D7** | **Two-WO assurance split.**<br>• CRM-CLIENT-001R2 does S1–S2 (build, plus offline Auditor, Tester and DevSecOps).<br>• **CRM-CLIENT-001R2-BA** does S5–S7. It is based on `forge/CRM-CLIENT-001R2` at the delivered candidate, and its only change is committing the sealed evidence record. Its Tester and DevSecOps assess the real-browser evidence.<br>• BA may not change any §4 path; a code defect found in BA is ESCALATED to CGPT, never corrected in BA.<br>• Its final exact version, which names `C` and the evidence manifest sha256, needs its own CGPT approval at S4 completion.<br>• Reason: F10; no engine change, no invented verdict and no counter reset | **Accepted** (CGPT, 2026-11-16) |
| **CL-D8** | **Exact base until FV2-SYNC-001 is installed:**<br>• the engineering base is the pinned `6e176698…`;<br>• the docs merge `M` must be proven docs-only (EB1–EB6);<br>• no root, `runuser` or other Git mutation of the PL checkout.<br>If CGPT requires the base to be `M` itself, engineering dispatch is **BLOCKED on FV2-SYNC-001** | **Accepted conditionally** (CGPT, 2026-11-16): EB1–EB6 must pass, and every intervening `main` change must be documentation-only |

## 13. Findings and corrections (v1.1 → v1.4)

| Finding | Source | Correction |
|---|---|---|
| A1: circular sequencing (four PASS before browser, while Tester PASS needs browser evidence) | CGPT | §9 S1–S7; F10; CL-D7; companion WO `CRM-CLIENT-001R2-BA.md`; AC6 split into AC6a (offline, this WO) and AC6b (BA) |
| A2: `playwright.__version__` does not exist | CGPT, confirmed by F12 | AC11 and annex B2.3: `importlib.metadata.version("playwright") == "1.64.1"`, a single distribution located under `/tmp/pydeps`, and independent browser version and revision checks |
| A3: exact base and stale PL `main` | CGPT, F11 | §10 EB1–EB6; CL-D8; header `KNOWN_COMMIT`. The v1.1 G4 ("docs-merge SHA becomes `--known-commit`") is removed |
| A4: CL-D5 | CGPT | Annex B8 (scanner, provenance, data source, method, triage, Chromium residual); G3 |
| A5: cleanup and recovery | CGPT | Annex B9 (always-run cleanup, verification, closure image removal, manual recovery); AC12; G7; §7 precise isolation wording |
| P1: `BROWSER: yes (...)` header would force a Tester-driven browser, giving INCONCLUSIVE then ESCALATED | PL, against `SKILL.md` §3 | Header line removed; header note added |
| P2: the finding key `browser-rerun:<journey>:<reason>` is invalid (the ledger's `KEY[:severity]` syntax and `SLUG_RE` forbid `:`) | PL, against `forgelib.py` | Annex B6.4: key `browser-rerun-<journey>`, with the reason in `--note` |
| P3: evidence route into `.forge-scratch/CRM-CLIENT-001R2/` cannot serve a later WO, and a WO's scratch must not exist before its `forge-start` | PL, against `forge-start` | Annex B6: root-owned, read-only operator evidence store `/srv/CRM/evidence/CRM-CLIENT-001R2/<run>/` |
| P4: "four independent PASS verdicts" miscounts (there are three reviewers) | PL | G2 text corrected |
| **D1 (v1.3)** | CGPT CL-D5 revision: do not rely on the pre-stable Chromium | Annex B1, B2a and B8.4: CfT Stable 157.0.8103.78, hash-pinned and mounted read-only, never installed on the host. The image's Chromium is proven not executed (B2.3) |
| **D2 (v1.3)** | Verify compatibility with Playwright 1.64.1 before selecting | F13: 1.64.1 was tested only against Chrome 155. **Playwright 1.65.1 (tested against Chrome 157) is selected**; the lock is reduced to two wheels (annex B2). A runtime compatibility probe is a gate, with a same-version headless-shell fallback (B2.3) |
| **D3 (v1.3)** | Public repository must not receive raw evidence | Annex B6 *public-safe publication*; AC6c sanitiser; `CRM-CLIENT-001R2-BA.md` §2 commits only the public summary; reviewers cite by path and hash only; Tester and DevSecOps inspect the raw store directly |
| **D4 (v1.3)** | Decisions accepted | §12: CL-D7 accepted, CL-D8 accepted conditionally, CL-D5 decided as revised |
| **R1 (v1.4)** | CGPT recovery §2.1: the download wording triggered the false positive | Annex B2 step 1 no longer names the download tool ("over HTTPS"). The annex B3 container user is unchanged. No v1.4 document names that tool or the rule id (§0 *Reporting discipline*). §14 gives the scan proof |
| **R2 (v1.4)** | §2.2: stale v1.2 references | Header *Approval* and §11 G1 now name v1.4; BA §1 names the v1.4 acceptance contract |
| **R3 (v1.4)** | §2.3: WO identity | `CRM-CLIENT-001R2` throughout: header, branch, worktree, scratch, ledger, evidence store (`/srv/CRM/evidence/CRM-CLIENT-001R2/`), Docker object names (`crm-client001r2-*`) and the companion `CRM-CLIENT-001R2-BA`. History and the §0 recovery record keep the original names |
| **R4 (v1.4)** | §2.4 and advisory `identity-check-after-launch` | Annex B2.3 *Pre-launch*; AC11; annex B9.1 item 7 (the `libatomic1` check in the pinned image) |
| **R5 (v1.4)** | §5: the advisories `doc-swap-exit20`, `doc-stale-delete`, `staging-leftover-on-swap-fail`/`swap-fail-leaks-staging` and `no-signal-trap-post-swap` | AC4c, AC10; corrected in this WO's implementation (§15) |
| **R6 (v1.4)** | §5: `beta-arg-accepted`, `trace-plaintext-credential` | Annex B9.1 item 3 (hard operator dev-only boundary) and annex B6 (credential handling); §15 |
| **R7 (v1.4)** | §4: reuse the completed work safely | §0 *Reference material* |

## 14. Publication-scan proof (v1.4)

Rogue reproduces, before approval, the exact ForgeV2 scan: `forgelib.gitleaks_scan`, which is `gitleaks git --no-banner --redact --ignore-gitleaks-allow --config /srv/forgev2/plugin/lib/gitleaks.toml --gitleaks-ignore-path <empty> --pre-commit --staged`. It runs on a staged Git index with the expected delivery-record structure:
- `.forge/CRM-CLIENT-001R2/{ledger.json,REPORT.md,prompts/*.md,dispatch/*.json}`, regenerated from the original record with the v1.4 texts and identity substituted and the engine's JSON serialisation preserved;
- the v1.4 documents, the `APPROVAL.md` dispatch record, and the original candidate tree.

**Positive control:** the same harness with the v1.3 texts must reproduce the 8 original findings of that rule. The results are recorded on #65 with the PR head.

## 15. Advisory reassessment (v1.4)

| Advisory | Synthetic root-operated run (S3–S4) | Eventual production release | Disposition |
|---|---|---|---|
| `identity-check-after-launch` | **Material.** An unverified binary would be executed before its hash is checked | Not applicable (test-only runner) | **Fixed**: R4 and AC11 |
| `staging-leftover-on-swap-fail` / `swap-fail-leaks-staging` | After exit 20 the previous trees are live and the stack is stopped, so the active deployment is safe. A stale `.src.deploy-*` under `client/custom` is not loaded by EspoCRM, but it is web-reachable static content | The same, on customer hosts | **Fixed**: staging removed on swap failure; leftovers listed and never used (AC4c) |
| `no-signal-trap-post-swap` | **Material.** An interrupted deploy could leave new trees live without a cache-bust or a recovery record; B9.5 was a manual procedure only | The same | **Fixed**: post-swap INT/TERM/HUP recovery, tested with real signals (AC4c) |
| `doc-swap-exit20`, `doc-stale-delete` | Misleading recovery documentation | The same | **Fixed**: AC10 |
| `beta-arg-accepted` | `deploy_custom.sh beta` is the existing release path for beta (present at `6e176698`) and is out of §4 scope. The S3–S4 boundary is the operator's, and it is now **hard**: annex B9.1 item 3 | The release path is unchanged. A beta deploy remains a separately approved release action | **Controlled**: operator allowlist, runtime-path check and beta before/after equality (G7) |
| `trace-plaintext-credential` | Traces may contain the synthetic crm-dev credential. They stay only in the restricted store (root:forgev2-pl, 0750/0640), are never committed, and are excluded from the public summary (AC6c) | Not applicable | **Controlled**: annex B6 credential handling. The credential is never a beta or UAT credential |
| `existing-test-edit` | The `scripts=` option and the extended chown list in existing tests. The tests still pass unchanged in intent (AC8) | None | **Accepted**: the Auditor confirms intent is preserved |
| **I1 (v1.5)** | **S3 finding on `CRM-CLIENT-001R`:** the pinned image `v1.64.1-noble` (amd64 `7d030ac0…15c0`, config `b6862d30…60c0`) has `libbrotli1` 1.1.0-2build2, which matches a KEV-listed High vulnerability (Ubuntu fix 1.1.0-2ubuntu0.1, advisory 2026-10-26). The library is loaded by the browser process through `libfreetype6`. Annex B8.3 makes this material and a gate | **Re-pin** to `playwright/python:v1.65.1-noble` (annex B1). The replacement has `libbrotli1` 1.1.0-2ubuntu0.1, no KEV match, no Critical, and 8 High findings that are all in packages that are present but never executed (Firefox, GStreamer plugins). It is the image of the same Playwright line as the wheel, whose notes say it carries `libatomic1` for the Node 26 driver. The library gate (`ldd` of the CfT binary and the Node driver, `libatomic.so.1`) passed in the replacement image, with no browser started. No acceptance of a residual risk is requested |
| **I2 (v1.5)** | DevSecOps advisory `doc-register-approval-open`: register entries carried `approval: none` | G1 now states that CGPT's exact-version approval of this version is the acceptance of the three register entries (G3); the dispatch record cites it. The `approval:` text in the register points to the WO, so the candidate needs no later edit |
| **I3 (v1.5)** | CGPT clarification: the reporting discipline must not conceal security findings | §0 *Reporting discipline* |


===== ANNEX B (verbatim) =====
# CRM-CLIENT-001R2 annex B: real-browser runner, isolation, vulnerability gate, evidence and cleanup (v1.3)

- **Status:** part of the CRM-CLIENT-001R2 **v1.5** DRAFT (second recovery: image re-pin; WO §0). It is approved only together with the WO, by commit. History: v1.1 is in commit `0fba12cf5395800d02db5801e4772506c849cb1a`. v1.2 is commit `793f69b04d860e3f82bbd39cbe08404f289ccbef`. v1.2 changes were B2.3, B3, B4, B6, B8 and B9.
- **v1.5 changes** (finding I1; CGPT recovery authorisation of 2026-11-16 and the S3 gate): the runner image is re-pinned to `mcr.microsoft.com/playwright/python:v1.65.1-noble` (B1, B3, B8.2 step 4); B8.5 records the S3 result that required it. Nothing else in this annex changes.
- v1.4 changes (CGPT *CRM-CLIENT-001R2 Recovery Authorisation*, 2026-11-16):
  - B2 step 1 wording (R1);
  - B2.3 *Pre-launch* order and the Node-driver library check (R4);
  - B6 credential handling and B9.1 items 3 and 7 (R6, R4);
  - the identity is `CRM-CLIENT-001R2` (R3).
- v1.3 changes (CGPT *CRM/WIP Delivery Mission*, 2026-11-16): the browser executable is now **Chrome for Testing Stable 157.0.8103.78** (B1, B2a, B3); the lock is **Playwright 1.65.1** (B2, B2.3); the scan covers the new browser (B8.4); evidence is published in **public-safe** form only (B6). WO §13 maps them.
- **Preparation constraints.** During preparation nothing was pulled, installed, scanned or run, and no Docker network was changed. The Chrome for Testing archives and the 1.65.1 wheel were downloaded only to compute hashes and were read as inert data.
  - Every value comes from public registry, PyPI, GitHub or OSV **metadata**, from read-only host inspection, or from reading the playwright wheel as inert data with `zipfile` (no code executed).
  - Each **VERIFY** item is re-checked by the operator at execution, and a mismatch is a stop.
- **Framework.** FOUNDRY `84fedf0a…` for the v1.2 decisions; `5f5e4a51…` is the provenance of v1.0–v1.1.

## B1. Component selection

| Item | Value | Provenance |
|---|---|---|
| Image | `mcr.microsoft.com/playwright/python:v1.65.1-noble` (official Microsoft Playwright for Python image, Ubuntu 24.04) | MCR tag list, 2026-11-16 |
| Multi-arch index digest | `sha256:0ab41a37431309d72b7a26f40ef1fdb464a62740196b2143965a2f59dc090409` | `Docker-Content-Digest` header; equals the sha256 of the fetched body |
| linux/amd64 manifest (DOCKER1 is x86_64) | **`sha256:ce84a3d75a47e81657d2ec2c0a949e6e0ef790abdc32ce6819220a3df987ff9a`** | index entry; the local pull's RepoDigest equals it |
| linux/arm64 manifest (not used) | `sha256:3eab9095f611a5923d8251fbcdf4c3e0d1527eee9334fe3aec6bb84198cf8c56` | index entry |
| amd64 config blob | `sha256:eccd588fcb91db7fbc8db45ba5e8aa3afb31a13a57d445c3f65be10f0b692261`; created 2026-11-12T00:51:26Z; 4 layers, 1,061,450,770 bytes compressed | manifest fetched; the local `docker image inspect` Id equals it |
| Image defaults | `User` unset (root); `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`; `CMD ["/bin/bash"]`; user `pwuser` created; `/ms-playwright` is `chmod -R 777` | config history |
| Python | Ubuntu noble `python3` 3.12; `pip` from `get-pip.py` at build time | config history |
| Playwright Python package | **Not present in the final image.** It was installed only in a temporary venv that the build deleted | config history, last RUN step |
| **Image role (v1.3)** | **Operating-system and dependency base only.** The image's bundled Chromium 158.0.8127.18 (`chromium-1254`) under `/ms-playwright` is **never executed**. `entry.sh` launches only the pinned Chrome for Testing binary (B2a), and the run records the launched executable path and the running process list | — |
| **Browser executed (v1.3)** | **Google Chrome for Testing, Stable channel, `157.0.8103.78`**, linux64 `chrome`, mounted read-only from the host verified copy (B2a) | CfT last-known-good JSON (timestamp 2026-11-15T21:10:21Z): Stable = 157.0.8103.78, revision 1717349 |

**Why Playwright 1.65.1 with Chrome 157 (v1.3).**
- Playwright's release notes give the stable Chrome channel each version was tested against.
  - **1.64.0 and 1.64.1: Google Chrome 155.** Chrome 157 is untested with 1.64.1, so 1.64.1 is **not selected**.
  - **1.65.0 and 1.65.1: Google Chrome 157.** This is the documented compatible line.
  - 1.65.2 moved its bundled Chromium to 159 and is not needed.
- **1.65.1** (PyPI 2026-11-11) is the latest patch of the line tested with Chrome 157.
- The earlier preference for packages at least two weeks old gives way to documented compatibility. The compensating controls are the hash pin, OSV and Grype scans, and the compatibility probe of B2.3.
- **Fallback.** If the compatibility probe fails, the same-version **CfT `chrome-headless-shell` 157.0.8103.78** (B2a), which is the launch target Playwright prefers in headless mode, is used through the same mechanism. Any other version needs a new WO version.

## B2. Python dependency lock (no unpinned installation)

`tests/browser/requirements.lock` holds exactly (v1.3; Playwright 1.65.1 requires only `greenlet>=3.1.1,<4`, so pyee and typing-extensions are no longer needed):

| Distribution | File | sha256 (PyPI) | Published |
|---|---|---|---|
| playwright 1.65.1 | `playwright-1.65.1-py3-none-manylinux1_x86_64.whl` | `5660e0b050a5bd5672bf8e366ed2580288a3d3640ff9444436ed2d890d3dc442` (verified by download, 2026-11-16) | 2026-11-11 |
| greenlet 3.5.6 | `greenlet-3.5.6-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl` | `975736b002ed080d124cf81a79cb7e05cb26d6b3f5c7a7b651c0fcce70353aa1` | 2026-09-14 |

The 1.65.1 wheel (inspected as data) has **no** `playwright.__version__`. It carries `playwright-1.65.1.dist-info`, bundles **Node.js 26.13.1** as `playwright/driver/node`, and pins its own Chromium as revision 1254 / 158.0.8127.18. That Chromium is not installed and not used.

**Install method (VERIFY at the first run).**

1. **Download.** The operator, as root, fetches the two wheels over HTTPS from the `files.pythonhosted.org` URLs listed by PyPI JSON. They go into a fresh root-owned directory and are checked against the lock; any mismatch stops the run. Nothing from the wheels is executed on the host.
2. **Install inside the container, offline:**
   `python3 -m pip install --no-index --find-links /wheels --require-hashes --only-binary=:all: --no-deps --target /tmp/pydeps -r /work/tests/browser/requirements.lock`
   - It installs to tmpfs, so nothing persists.
   - The container has no route to PyPI (B4).
3. **Pre-launch checks (v1.4, R4).** These run in `entry.sh` (or a stdlib-only Python step) **before any Playwright driver (Node) or browser process is started**. Any failure exits non-zero with a named cause, launches nothing, and the run is **BLOCKED**:
   - **Binary hash:** the sha256 of the selected CfT binary (below) equals the pinned value.
   - **Libraries:**
     - `ldd` of the CfT binary reports no `not found`;
     - `ldd` of the bundled Node driver `/tmp/pydeps/playwright/driver/node` reports no `not found`;
     - `libatomic.so.1` resolves explicitly. Playwright 1.65.1 bundles Node 26.13.1, whose image added `libatomic1` (CGPT finding).
   - **Record:** all of these are written to `identity.json` before launch.

   **Version and compatibility checks (v1.3).** `entry.sh` runs Python as `PYTHONPATH=/tmp/pydeps python3 -s -B …`. It must not use `-I` or `-E`, which ignore `PYTHONPATH`. It asserts and records the following in `identity.json`:
   - **Distribution.**
     - `importlib.metadata.version("playwright") == "1.65.1"`;
     - exactly **one** `playwright` distribution is visible, and its `locate_file("")` and `playwright.__file__` resolve under `/tmp/pydeps`;
     - `greenlet` is 3.5.6.
   - **Browser binary.**
     - The sha256 of `/opt/cft/chrome-linux64/chrome` equals `f60cb86024464df9740504a1584b605c2b3cf107625ff11e1da22c875c1627e8`, or for the fallback, `/opt/cft/chrome-headless-shell-linux64/chrome-headless-shell` equals `8e4c5db8c070059cb570a05c171dfcaec022d46334722ec3a16376614d687a96`.
     - `ldd` of that binary reports no `not found` library. The image supplies the dependencies. **Both checks are part of the pre-launch step above and complete before the launch.**
   - **Launch.** `p.chromium.launch(executable_path=<that binary>, headless=True)`.
     - The **running browser's** `browser.version` equals `157.0.8103.78`.
     - The launched process's `/proc/<pid>/exe` resolves to the pinned path.
     - No process from `/ms-playwright` exists at any time during the run.
   - **Compatibility probe** (before the isolation-gated journeys, against crm-app only), exercising every Playwright feature the journeys use:
     - new context and page;
     - navigation to the login page;
     - request/response events with the `from-cache` flag and response bodies;
     - console and page-error events;
     - a `securitypolicyviolation` listener;
     - tracing start and stop, with the trace written to `/evidence`;
     - a screenshot.

     Any failure means the run is **BLOCKED** (then the B1 fallback, once).

   `verify_evidence.py` recomputes each of these from `identity.json`, and any mismatch is a FAIL.

**External code register (§4 allowlist).** The register gains three test-only, operator-run entries:
- **`playwright-python-browser-runner`.** It records:
  - the image tag and digests, with the role *OS and dependency base; bundled Chromium not executed*;
  - the two wheels and their hashes, and the bundled Node 26.13.1;
  - licences: Apache-2.0 (Playwright), MIT (greenlet), and the Ubuntu licences;
  - `usage: test-only, operator-run, never in any release bundle or runtime`.
- **`chrome-for-testing-stable`.** It records:
  - version 157.0.8103.78 and the URL;
  - the zip sha256, GCS md5 and binary sha256 of B2a;
  - the fallback headless shell;
  - licence: Chromium and Google Chrome for Testing terms;
  - usage: test-only, mounted read-only into the runner and never installed on the host.
- **`grype-cl-d5-scanner`** (B8).

Each entry carries `approval:` as recorded by CGPT. `release.py verify` checks image digests only for the compose files, so release bundles are unaffected.

## B2a. Chrome for Testing acquisition (v1.3)

| Item | `chrome` (primary) | `chrome-headless-shell` (fallback) |
|---|---|---|
| URL | `https://storage.googleapis.com/chrome-for-testing-public/157.0.8103.78/linux64/chrome-linux64.zip` | `…/157.0.8103.78/linux64/chrome-headless-shell-linux64.zip` |
| Zip sha256 | `9223832977a13db3646201b1341c1f9cf08afa3ceae92540116d7b0c062364fb` | `f90329720fb61e5a76da9b6b509b6ad12a484c9c5df0359403e935177c6d153a` |
| Size; GCS object md5 (`x-goog-hash`) | 203,266,906; `n3ml73xVw0ZMdH0ruvsZVg==` (matches the download) | 127,965,683; `+V2ivCON/pkNQRVG64AOKA==` (matches) |
| Published (`last-modified`) | 2026-11-11T01:28:48Z | 2026-11-11T01:29:14Z |
| Binary sha256 | `chrome-linux64/chrome` `f60cb86024464df9740504a1584b605c2b3cf107625ff11e1da22c875c1627e8` | `chrome-headless-shell-linux64/chrome-headless-shell` `8e4c5db8c070059cb570a05c171dfcaec022d46334722ec3a16376614d687a96` |
| Embedded version string | `157.0.8103.78` | `157.0.8103.78` |

- **Procedure (S3, operator).**
  1. Download into a fresh root-owned 0700 directory. Verify the zip sha256 and the `x-goog-hash` md5, and re-read the CfT JSON to confirm that the version and URL are unchanged.
  2. Unzip with `--no-same-owner`. Drop every setuid or setgid bit. The archive's `chrome_sandbox` has mode 0755, not setuid, and it is never used, because Chrome runs `--no-sandbox` under Playwright with all capabilities dropped (B3).
  3. Make the tree root-owned and read-only (0555 directories, 0444/0555 files). Verify the binary sha256.
  4. Mount it read-only at `/opt/cft`.
- **No installation on the host.** The tree lives only under the run's operator directory and is deleted at WO closure (B9.4). Nothing from it is executed on the host.
- **Freshness gate.** At S3 the operator re-reads the CfT JSON and the Chrome Releases blog.
  - If Stable has moved past 157.0.8103.78 with **security fixes**, the run pauses and Rogue proposes a re-pin to CGPT: a new WO version with only the B2a constants changed.
  - If Stable has moved for non-security reasons, the run proceeds with `.78`.

## B3. Container hardening (exact invocation template)

Root prepares the container. The processes inside run as uid/gid 65534.

```
docker run --rm --pull never \
  --name crm-client001r2-browser-<run> \
  --user 65534:65534 \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=1g \
  --cap-drop ALL --security-opt no-new-privileges=true \
  --pids-limit 512 --memory 2g --shm-size 1g \
  --network crm-client001r2-browser-<run> --ip <browser-ip> \
  --env HOME=/tmp --env PYTHONDONTWRITEBYTECODE=1 \
  --env CRM_BROWSER_BASE_URL=http://<app-ip> \
  --env-file <root-0600-tmp-file> \
  --mount type=bind,src=<archive-copy-of-candidate>,dst=/work,readonly \
  --mount type=bind,src=<verified-wheelhouse>,dst=/wheels,readonly \
  --mount type=bind,src=<verified-cft-tree>,dst=/opt/cft,readonly \
  --mount type=bind,src=<evidence-out>,dst=/evidence \
  mcr.microsoft.com/playwright/python@sha256:ce84a3d75a47e81657d2ec2c0a949e6e0ef790abdc32ce6819220a3df987ff9a \
  /bin/bash /work/tests/browser/entry.sh
```

- **`<root-0600-tmp-file>`** holds only the synthetic `@example.test` test-user credentials. It is created for the run and deleted in cleanup (B9), and is never in argv or evidence.
- **Restrictions.**
  - No Docker socket, no host networking, no privileged mode, no added capabilities and no device mounts.
  - The only writable paths are `/tmp` (tmpfs) and `/evidence`.
  - The default seccomp and AppArmor profiles apply.
- **Browser sandbox.** Playwright launches Chrome without its own sandbox (`chromiumSandbox: false`, so `--no-sandbox`). Under `--cap-drop ALL` the namespace sandbox is unavailable anyway, so the boundary is the container plus B4. Running a **patched stable** browser (B2a) is what makes this acceptable (B8.4).
- **Image acquisition (S3 operator gate).**
  1. Pull by digest: `docker pull mcr.microsoft.com/playwright/python@sha256:ce84a3d7…ff9a`.
  2. `docker image inspect` must show that RepoDigest and config ID `sha256:eccd588f…2261`.
  3. Acquire Chrome for Testing (B2a), then run the B8 scan over the image, the wheels and the CfT tree.
  4. Use `--pull never` thereafter.
- **Image removal.** The image is removed at **WO closure** (B9.4), not after each run, so that a bounded repeat (B6.4) uses the same bytes.
- **`<evidence-out>`** is a fresh root-created `/tmp/crm-client001r2-browser-<run>/out`, owned by 65534 with mode 0700.
- **`<archive-copy-of-candidate>`** is the verified `git archive` of `C` (or of the B5 transition tree `T`), root-owned and read-only. Engineer-authored code runs **only** inside this container as uid 65534, and never as root, as the PL or on the host. The one exception is the reviewed `deploy_custom.sh` (WO G2).

## B4. Network isolation

**Verified host facts (read-only, 2026-11-16):**
- `crm-dev_crm-net` is a non-internal bridge on `172.16.10.0/24`. crm-db is on it, so the browser never joins it.
- crm-beta uses its own `crm-beta_crm-beta-net`. Its app is published on `127.0.0.1:8280`, and the edge uses host networking.
- crm-dev Apache admits only loopback and `CRM_ALLOWED_SOURCES` (`deploy/apache/crm-access.conf`).
- `check_access.py dev` accepts RFC 1918 sources of /16 or longer that do not overlap crm-net.
- Docker Engine is 24.0.5, and its binary contains `com.docker.network.bridge.inhibit_ipv4` (**VERIFY** effectiveness via the probe below).

**Design (per run, test-only).**

1. **Create the network.**
   `docker network create --driver bridge --internal --subnet 172.31.250.0/29 -o com.docker.network.bridge.inhibit_ipv4=true -o com.docker.network.bridge.enable_ip_masquerade=false crm-client001r2-browser-<run>`
   - `--internal` means no default route and no NAT.
   - `inhibit_ipv4` gives the host-side bridge no IPv4 address.
   - The subnet is first checked as unused against `docker network ls` and `ip route`.
2. **Admit the browser.** Its single address, `172.31.250.2/32`, is appended **temporarily** to `CRM_ALLOWED_SOURCES` in `/srv/CRM/runtime/dev/env`.
   - Before the change: a byte copy and the sha256 of the env file are saved (B9.1).
   - `check_access.py dev` must pass.
   - The existing bind-only entry is handled per the recorded crm-dev procedure.
   - crm-app is then recreated with `scripts/up.sh dev`.
3. **Attach crm-app.** `docker network connect --ip 172.31.250.3 crm-client001r2-browser-<run> crm-dev-crm-app-1`.
   - crm-db and crm-daemon are **not** attached.
   - **VERIFY:** `/proc/sys/net/ipv4/ip_forward` inside crm-app is 0.
4. **Prove isolation before any journey.** `probe_isolation.py` runs as a separate step. Every item is a hard gate:
   - the route table (`/proc/net/route`) shows only `172.31.250.0/29`, with no default route;
   - TCP to `172.31.250.3:80` succeeds;
   - each of the following **fails** within 3 s:
     - crm-db `<addr>:3306`, its address supplied as data from `docker inspect`;
     - crm-app on crm-net `172.16.10.3:80`;
     - the host LAN `<dev bind IP>:8180` and `:8290`;
     - `127.0.0.1:8280`;
     - the crm-beta network gateway and its app address;
     - a public address on 443;
     - DNS resolution of a public name.

   Any unexpected success stops the run before the journeys. The run then reports BLOCKED, and there is no fallback to a wider network.

**What isolation does and does not mean (A5).**
- The browser has **no intended direct network path** to crm-db, beta, the host or external destinations, and the probe demonstrates this for the listed targets only.
- crm-app keeps its legitimate connection to crm-db. Anything the synthetic test user can do through the CRM application, the browser can do.
- The design does not prevent application-layer access through crm-app and does not claim to. It is acceptable only because crm-dev is synthetic.
- Steps 2 and 3 briefly change crm-dev's runtime configuration and recreate crm-app, under this WO's approval. B9 restores and verifies them.

Teardown is defined in **B9** and always runs. No firewall rule is created or changed at any point.

## B5. Immutable canary versions and the cache-bust transition

- **Committed fixtures** keep every deployed byte inside **one** reviewed candidate `C`:
  - `client/custom/src/crm/release-canary.js` declares contract **1**;
  - `tests/browser/fixtures/canary-transition/v2/crm/release-canary.js` is identical except for contract **2** (AC1).
- **Transition tree `T`.** The operator builds it from the verified archive of `C`:
  - only `client/custom/src/crm/release-canary.js` is replaced, with the v2 fixture blob;
  - the manifest of `T` is written;
  - every other file is verified equal to its `C` blob.

  `T` is never committed, and it is deployed with its own (= `C`'s) `scripts/deploy_custom.sh`.
- **Deployment order and assertions.** One browser profile is kept across D1–D3. A "fresh load" is a new navigation, with no manual cache clear.

  | Step | Deploy | Expected |
  |---|---|---|
  | D0 | `backup.sh dev`; record appTimestamp `a0` | — |
  | D1 | `C` | J1: contract 1; `…/release-canary.js?r=a1`, `a1 > a0`; `a1` equals the crm-app value |
  | D2 | `T` (≥2 s after D1) | J2: contract 2; `r=a2 > a1`; a new network fetch, not cached |
  | D3 | `C` again (rollback, ≥2 s) | J3: contract 1; `r=a3 > a2` |
  | D4 | failure injection (B7) | J4 per B7 |
  | D5 | `restore.sh dev` of the D0 backup, then a cache-bust | J5: canary absent (clean resolution failure, no console error outside the probe); `a5 > a4`; regression screens match D0 |

- **appTimestamp resolution.** The value is in whole seconds.
  - `deploy_custom.sh` re-reads after `update-app-timestamp`. If the value has not advanced, it waits 1 s and runs the update once more, and otherwise fails with `FAILED STEP: update-app-timestamp (not advanced)`.
  - The operator also waits at least 2 s between deploys.
  - The browser treats equality as a FAIL.

## B6. Evidence package, store and route to the Tester

**Contents for each run `<run>`.** The container writes to `/evidence`, except files marked *operator*.

| File | Content |
|---|---|
| `invocation.txt` | *operator*: the exact docker, network, deploy and cleanup commands, with digests. Credentials appear only as file references |
| `identity.json` | `C`, the sha256 of the `T` manifest, the snapshot manifest, the image RepoDigest and config ID, the wheel hashes, the B2.3 version checks, the Docker version, and a `docker inspect` subset of the browser container (Mounts, NetworkSettings, CapDrop, SecurityOpt, ReadonlyRootfs, User, Privileged; no Env). The operator writes its parts |
| `scan/` | *operator*: the B8 reports and the scanner and DB identity |
| `isolation.json` | each probe target, expected and actual result, and the route table |
| `timestamps.json` | `a0`..`a5` read in crm-app, and the `r` values the browser observed |
| `journeys/<J>/result.json` | per assertion: id, AC, expected, observed, pass/fail |
| `journeys/<J>/requests.jsonl` | every request: URL, method, status, from-cache flag, and the response sha256 for `client/custom` resources |
| `journeys/<J>/console.jsonl`, `csp.jsonl` | console messages, page errors and `securitypolicyviolation` events |
| `journeys/<J>/trace.zip`, `*.png` | the Playwright trace (offline-viewable) and screenshots of synthetic records. **May contain the synthetic crm-dev credential (v1.4):** restricted store only, never committed, never quoted by reviewers, never in the public summary. The credential is the crm-dev synthetic login, supplied only through the root 0600 env file, and is **never** a beta or UAT credential (checked at OP-V) |
| `beta-before.json`, `beta-after.json`, `crmdev-before.json`, `cleanup.json` | *operator*: B9 |
| `SHA256SUMS` | *operator*: covers every file above |

**Public-safe publication (v1.3, CGPT finding).** The CRM repository is public.
- The **raw package never enters Git.** It contains internal URLs, addresses, container and network details, and operational metadata, and it stays only in the restricted store (step 1).
- **What may be committed** is the *public summary* `public-summary.json` and `EVIDENCE.md`, produced deterministically by `verify_evidence.py --public-summary` (AC6c). It contains only:
  - the run id;
  - `C`;
  - the image index and amd64 digests, the wheel hashes, and the CfT version and binary sha256;
  - the Grype version, the DB build time and checksum, and finding counts by severity and triage class;
  - the per-journey and per-AC verdicts with assertion ids;
  - the sha256 of each raw file **by relative path**, and the sha256 of `SHA256SUMS`;
  - `cleanup.json` booleans, with labels only.
- **Forbidden in the public summary:** IPv4 and IPv6 addresses, hostnames, URLs, ports, container, network or volume ids and names, env names and values, usernames and e-mail addresses (other than the literal `@example.test` domain), file-system paths outside the package, and free text from logs.
  - AC6c's sanitiser test fails on each of these.
  - The BA Auditor and DevSecOps check the committed summary against them.
- **Reviewer outputs are public too.** Specialist final messages and PL prompts are committed to `.forge/<WO>/` on the branch. BA prompts therefore instruct every reviewer to cite raw evidence only by **relative path, line number and sha256**, and never to quote addresses, URLs or log content.

**Store and route (no Docker, network or Git for specialists).**

1. **Seal.** After S4 (including cleanup), root copies the package to `/srv/CRM/evidence/CRM-CLIENT-001R2/<run>/`, root-owned with group `forgev2-pl`, directories 0750 and files 0640. `SHA256SUMS` is written last and its own sha256 is recorded.
   - gitleaks (`dir --redact`) must report the package clean.
   - The package is never edited afterwards. A repeat gets a new `<run>`.
2. **BA final WO version.** It names the raw package by `<run>` and the sha256 of `SHA256SUMS` only. The sha256 of `SHA256SUMS` and `<run>` go into the final exact version of `CRM-CLIENT-001R2-BA.md`, which CGPT approves before dispatch. The sandboxed specialists of that WO can read the store (it is not a private path of the engine) but cannot write it.
3. **Independent assessment.**
   - The BA Tester and DevSecOps **inspect the raw package directly in the restricted store** (read-only). The Tester verifies `SHA256SUMS` first.
   - It runs `verify_evidence.py` **from the candidate** on a copy in its scratch. The verifier recomputes every AC6b and AC12 verdict from the raw files and never trusts `result.json`.
   - It may unpack and inspect `trace.zip` and the screenshots.
   - It issues its own PASS or FAIL per journey.
4. **Challenge and bounded repeat.**
   - The Tester may record a blocking finding with the key **`browser-rerun-<journey>`** (the ledger's `KEY[:severity]` syntax forbids `:` inside keys), with the reason in `--note`.
   - BA then cannot deliver. The PL returns ESCALATED, because the Engineer cannot produce operator evidence.
   - The Orchestrator performs **one** bounded repeat (same `C`, same procedure, new `<run>`).
   - The repeat is assessed in **one** follow-on WO `CRM-CLIENT-001R2-BA2`, which is identical except for the run id and manifest and needs its own CGPT exact-version approval. No further repeat is permitted without a new CGPT decision.
   - The PL can never overrule a Tester FAIL.

A screenshot alone is never accepted as proof.

## B7. Failure after a successful swap

1. **Swap.** `custom/Espo/Custom` and `client/custom/src` are both staged, then swapped. The previous trees are kept as `.Custom.old-<stamp>` and `.src.old-<stamp>` until every later step succeeds. If the second swap fails, the first is swapped back before exit.
2. **Post-swap steps** run in order: `up --wait`, `clear-cache`, `rebuild`, then `update-app-timestamp` with the advance check. On the first failure the script:
   - prints `FAILED STEP: <step>`;
   - never prints the success line;
   - exits with a step-specific code;
   - **recovers**:
     1. stops crm-app and crm-daemon;
     2. moves the new trees to `.failed-<stamp>` and swaps the previous trees back;
     3. starts the stack and runs `clear-cache`, `rebuild` and `update-app-timestamp`;
     4. prints `RECOVERED: previous customisation restored`.

   If recovery fails: a controlled stop of crm-app and crm-daemon, `RECOVERY FAILED: stack left stopped`, and both trees retained.
3. **Unit tests (AC4b).** A failure is injected at every step and every recovery step. Each test asserts the exit code, the markers, byte equality with the previous tree, retention of `.failed-*`, and the docker call order.
4. **On crm-dev (J4).**
   - The operator prepends a test-only `docker` wrapper to `PATH`. It is recorded in `invocation.txt` and is not part of the candidate. It makes `exec … bin/command update-app-timestamp` fail once.
   - The operator then deploys `T` over `C`.
   - Expected: non-zero exit with `FAILED STEP: update-app-timestamp` and `RECOVERED`; the browser loads contract **1**; `r` has advanced; no console errors.
   - Beta is never touched.

## B8. CL-D5: vulnerability assessment (decided as revised, v1.3)

**B8.1 Scanner selection.**

| Item | Value | Provenance (read-only, 2026-11-16) |
|---|---|---|
| Scanner | **Grype `v0.121.0`** (Anchore), published 2026-10-19, more than two weeks old | GitHub release API: `immutable: true`, author `github-actions[bot]` |
| Artefact | `grype_0.121.0_linux_amd64.tar.gz`, 32,504,199 bytes, **sha256 `64e07133d3486115de647a66581461dccf5c732748a0a3119077395565f15519`** | GitHub asset digest; equals the line in `grype_0.121.0_checksums.txt` |
| Checksums file | sha256 `938761709760ee0e94ebca564a757b6658ab4efddc0d19ecc6ede12f22d2fdd0`, with sigstore bundle `grype_0.121.0_checksums.txt.sigstore.json` (sha256 `76e0fda1979bdc991dcab685fd10ed59c704edcab083667684412527e35af0e9`) | downloaded and hashed (text only; no binary fetched) |
| Signature verification | `gh release verify-asset v0.121.0 <file> -R anchore/grype`, using the **already installed** `gh` 2.103.3 (GitHub release attestation). No cosign installation is needed | `gh release verify-asset --help` |
| Vulnerability data | The Grype DB (Anchore-built, from NVD, GitHub Advisory Database, Ubuntu OVAL/USN and other vendor feeds), downloaded at scan time. Its schema, build timestamp and checksum are recorded from `grype db status -o json`, so the data source of the verdict is identified | at S3 |
| Why not Trivy | Trivy's release pipeline was compromised in March 2026: malicious v0.69.4 and rewritten trivy-action tags (GHSA-69fq-xp46-6x23, CVE-2026-33634). Trivy v0.76.x is also an immutable, signed release, but this preparation prefers the scanner with no such incident. No Grype release compromise was found in this preparation's searches (searched, not exhaustively verified) | Aqua advisory; OSV |

**B8.2 Method (S3, operator).** It is temporary, non-root, has no Docker socket and leaves no service behind.

1. **Fetch and verify.** Root downloads the tarball and the checksums into a fresh root-owned directory, checks the sha256 and `gh release verify-asset`, and extracts only the `grype` binary. Any mismatch stops the run.
2. **Run unprivileged.** The scanner runs as uid/gid 65534:
   `setpriv --reuid=65534 --regid=65534 --clear-groups --no-new-privs env -i HOME=<tmp> TMPDIR=<tmp> GRYPE_DB_CACHE_DIR=<tmp>/db PATH=/usr/bin:/bin <tmp>/grype …`
   - `<tmp>` is fresh, 0700 and owned by 65534.
   - The scanner never receives the Docker socket. Its only network use is the DB download and the registry pull.
   - No firewall change is made.
3. **Database.** `grype db update`, then `grype db status -o json` goes to `scan/db-status.json`.
4. **Image scan.** `grype registry:mcr.microsoft.com/playwright/python@sha256:ce84a3d7…ff9a --platform linux/amd64 -o json` goes to `scan/image.json`, with a table copy in `scan/image.txt`. The `registry:` source fetches layers directly, with no daemon.
5. **Wheel and browser scan.**
   - The two verified wheels are unzipped as data into a fresh directory, and `grype dir:<that dir> -o json` goes to `scan/wheels.json`. This covers the dist-info and the bundled Node 26.13.1.
   - `grype dir:<verified-cft-tree> -o json` goes to `scan/cft.json`.
6. **OSV cross-check.** An OSV API query for the two `PyPI` versions goes to `scan/osv.json`. At preparation it returned **0 known vulnerabilities** for playwright 1.65.1 (queried 2026-11-16 ~11:55 UTC) and greenlet 3.5.6 (11:20 UTC).
7. **Cleanup.** Remove the binary, DB cache and extracted files. Record the hashes of the reports in `SHA256SUMS`.

**B8.3 Triage rules (recorded per finding in `scan/triage.json`).**
- **Material, and a gate.** Any finding, whatever its fix state, in a component that *executes during the run* and that is reached by page content or network input:
  - the Chrome for Testing binary;
  - the bundled Node driver and its OpenSSL or undici;
  - playwright or greenlet;
  - python3 or the libc, TLS and font libraries loaded by Chromium.

  It must be at least High, or be KEV-listed, or have a known exploit. Such a finding blocks the run until one of three things happens:
  - a re-pin through a register change and a new WO version;
  - a documented mitigation that removes reachability;
  - explicit acceptance (CGPT, and Matt where the risk is material).
- **Not material in this environment** (recorded, with the reason):
  - packages present but not executed: the image's bundled Chromium 158 and headless shell under `/ms-playwright` (proven not executed, B2.3), and the Firefox and WebKit binaries, `apt` and `dpkg` tooling, `perl`, `openssh-client`, X11 or GUI libraries used only in headful mode, and ffmpeg;
  - CVEs that need a listening network service, local privileged users, or a route to destinations that B4 proves unreachable;
  - kernel CVEs, which are reported to DevSecOps but belong to the host.
- **Unscannable components** are listed explicitly and never counted as clean. Chrome for Testing is not package-managed, so it is assessed by version against the Chrome Releases blog (B8.4).

**B8.4 Browser vulnerability position (v1.3).** The v1.2 residual is **removed**: no pre-stable Chromium is executed (the image's bundled Chromium is present but never run). The executed browser is the current **Stable** Chrome for Testing, 157.0.8103.78.
- The latest desktop Stable release notes found during preparation are 157.0.8103.50, from 2026-11-09. The `.78` artefacts were published by the CfT Stable channel on 2026-11-11, so they are later.
- At S3 the B2a freshness gate re-confirms that no later Stable security release exists.
- A Chrome CVE published after `.78` and fixed in a later Stable is a **material** finding under B8.3, and it triggers the re-pin route.
- The unexecuted bundled Chromium 158 files remain in the image's filesystem. They are classified *present, not executed*, and the process check proves it at runtime.

**B8.5 S3 record and the executed-package rule (v1.5).**
- **Previous pin (failed).** At the S3 gate of `CRM-CLIENT-001R` (2026-11-16, Grype 0.121.0, DB built 2026-11-16T06:30:54Z, schema v6.1.10), the previous image (`v1.64.1-noble`, amd64 `7d030ac0…15c0`) matched 2,719 findings: 28 Critical and 151 High, and 1 KEV. Of the 179 High or Critical findings, 178 were in packages that are present but not executed (170 in `firefox`; the rest in `virtualenv`, `apt`, GStreamer plugins and `filelock`). **One was in an executed package: `libbrotli1` (KEV-listed, fix available).** That is material under B8.3, and it blocked the run.
- **Executed-package set.** The operator derives it per image: the packages that own every shared library that `ldd` resolves for the pinned CfT binary, the Node driver and `python3`, plus `python3` and `bash` themselves. The previous image had 77 such packages. The result is recorded in `scan/executed-packages.txt`.
- **This pin.** The S3 preparation scan of `v1.65.1-noble` (same scanner and DB) matched 2,405 findings: 0 Critical, 8 High and 0 KEV. All 8 High are in packages that are not executed (`firefox`, `gstreamer1.0-plugins-bad`, `libgstreamer-plugins-bad1.0-0`), and `libbrotli1` is 1.1.0-2ubuntu0.1. The operator **re-runs** the whole B8.2 method at S3 for this exact digest, and the triage is recorded again. The result of the re-run, not this preparation scan, is the gate.

**Register entry `grype-cl-d5-scanner`:**
- the release, artefact digest, checksums sha256 and sigstore bundle sha256;
- the verification command;
- `usage: operator-run, temporary, removed after scan`;
- licence Apache-2.0.

## B9. Operator procedure: pre-root verification, cleanup, verification and manual recovery (v1.2)

The operator script is root-owned and operator-authored, not part of the candidate. Its text and sha256 are recorded in `invocation.txt` before execution. It runs `set -Eeuo pipefail` and installs **`trap cleanup EXIT INT TERM HUP`** before the first state-changing step, so cleanup runs after a test failure, a deploy failure or an interruption. Every state change is journalled to `state.log` *before* it is made, which drives both automatic and manual recovery.

**B9.1 Pre-root verification gate OP-V (S3; any failure means BLOCKED, with no state change made).**
1. **Candidate.**
   - `C` is the PL's delivered candidate: the PL JSON passes the `ORCHESTRATOR.md` §3 checks, and the committed ledger shows `DELIVERED` with `candidate = C`.
   - The GitHub `forge/CRM-CLIENT-001R2` branch contains `C`.
   - The archive tree manifest from GitHub (`tarball/<C>`) equals the manifest from a read-only `git archive C` of the canonical repository (`safe.directory` scoped, `GIT_OPTIONAL_LOCKS=0`).
   - Both equal the PL snapshot manifest.
2. **Deploy script.** `scripts/deploy_custom.sh` in the archive equals the blob of `C` that the S2 DevSecOps reviewed (its sha256 is recorded). It is run only from the root-owned 0700 archive directory under `/srv/CRM/releases`.
3. **Root-execution boundary (hard dev-only, v1.4).**
   - Only `deploy_custom.sh dev`, `backup.sh dev`, `restore.sh dev`, `up.sh dev`, `check_access.py dev` and the docker commands of B3, B4 and B8 run as root, and Engineer browser code runs only in the container.
   - The **operator script** runs each candidate script through one wrapper. The wrapper refuses, before executing, any argv that is not in that fixed list with the literal target `dev`; any argument equal to or containing `beta`; and an environment whose resolved `CRM_RUNTIME_DIR`, compose project or env file is not crm-dev's.
   - `deploy_custom.sh` itself still accepts `beta` for the separately approved release path, which is outside §4.
   - The wrapper's refusals are exercised once at OP-V with a dry `beta` argv, which must be refused with no candidate script executed, and are recorded in `invocation.txt`.
   - The browser credential is checked to differ from every beta and UAT credential, by comparing hashes only and never displaying either.
   - `beta-after.json` must equal `beta-before.json` (G7).
4. **Synthetic backup.** `backup.sh dev` creates a fresh backup. Its manifest and sha256 are recorded, and a restore dry check confirms that the archive members are readable and include `client-custom.tar.gz`.
5. **Snapshots before any change:**
   - `crmdev-before.json`: the env file sha256 and a byte copy (root 0600); the crm-app, crm-db and crm-daemon container IDs, images, networks, health and StartedAt; the HTTP status and body hash of `/` from loopback; the appTimestamp; the `client/custom` tree manifest;
   - `beta-before.json`: **metadata only**, with no file content read (and never the beta env file): `stat` of `/srv/CRM/runtime/beta` and `/srv/CRM/deploy`; the `find -printf '%p %u:%g %m %s %T@'` listing of both to depth 2; the crm-beta container IDs, images, StartedAt, RestartCount and health.
6. **Absence of stale objects.** No `crm-client001r2-*` container or network, and the subnet is unused.
7. **Gate.** The CfT acquisition and freshness gate (B2a) and the CL-D5 scan (B8) pass under the triage rules. **Library gate (v1.4, CGPT finding; v1.5: passed in preparation for this pin with no missing library and `libatomic.so.1` resolved, and repeated at S3):** inside the exact pinned image, as uid 65534 with no network, `ldd` of the verified CfT binary and of the 1.65.1 wheel's bundled `playwright/driver/node`, run as data with no browser started, shows no `not found` library, including `libatomic.so.1`. **If any library is missing, STOP browser execution** and propose the smallest image re-pin to CGPT. Host libraries are never installed and the approved runtime is never changed.

**B9.2 Cleanup (always run, in this order, each step idempotent and logged).**
1. Stop and remove the `crm-client001r2-browser-<run>` container if present (`docker rm -f`).
2. Disconnect crm-app from the test network, if attached.
3. Remove the test network.
4. Restore the env file from the byte copy, then run `cmp` and compare its sha256 with `crmdev-before.json`.
5. If a deploy left the stack in a non-baseline state, run `restore.sh dev` of the B9.1 backup, and the cache-bust (D5 does this in the success path).
6. Recreate crm-app with `scripts/up.sh dev` and wait until it is healthy.
7. Remove the PATH wrapper directory, the env-file of test credentials and the temporary wheelhouse and output directories, after the evidence is copied.
8. Write `cleanup.json`.

**B9.3 Cleanup verification (G7). Each item is a boolean, and any false is a FAILED run, even if every journey passed.**
- The env file is byte-identical to `crmdev-before.json`.
- `docker ps -a` and `docker network ls` show no `crm-client001r2-*` object.
- crm-app is attached to `crm-dev_crm-net` only.
- crm-app, crm-db and crm-daemon are running, healthy where a healthcheck exists, and on the same images.
- `/` returns the pre-test status.
- The `client/custom` tree equals the D0 manifest after D5.
- `beta-after.json` equals `beta-before.json` in every field.

Cleanup failures are reported as `CLEANUP FAILED: <item>`, and a BA WO is not proposed.

**B9.4 WO closure.**
- After CGPT acceptance or a final ESCALATED, run `docker image rm` of the Playwright image by digest.
- Record that `docker images --digests` no longer lists it.
- Confirm that the Grype artefacts are absent.
- Keep the evidence store (`/srv/CRM/evidence/CRM-CLIENT-001R2/`) as the delivery record until CGPT authorises archival.

**B9.5 Manual recovery (interrupted procedure, e.g. host reboot or killed shell).** This is documented in `docs/RELEASE.md` (AC10) and works from `state.log` alone:
1. `docker rm -f crm-client001r2-browser-<run>`.
2. `docker network disconnect -f crm-client001r2-browser-<run> crm-dev-crm-app-1`, then `docker network rm crm-client001r2-browser-<run>`.
3. `cp --preserve=mode,ownership <saved env copy> /srv/CRM/runtime/dev/env`, then `cmp` and sha256.
4. If `state.log` records any deploy, or the runtime trees show `.Custom.old-*`, `.src.old-*` or `.failed-*`: stop crm-app and crm-daemon, run `restore.sh dev` of the recorded backup, then `up.sh dev`, `clear-cache`, `rebuild` and `update-app-timestamp`.
5. Run every B9.3 check and record the result as `manual-recovery.json` in the run's evidence.
6. An interrupted run is **never** evidence for BA. A new run id is required.

===== YOUR ROLE: TESTER (WO section 8) =====
