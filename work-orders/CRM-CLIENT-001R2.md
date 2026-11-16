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
