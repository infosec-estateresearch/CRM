WO: CRM-CLIENT-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main
BROWSER: yes (orchestrator-run real-browser journeys on synthetic crm-dev, with independent Tester verification; CL-D3, annex B)

# CRM-CLIENT-001: version-controlled delivery of CRM-owned browser customisations (`client/custom/src/`)

- **Version:** v1.1 DRAFT, 2026-11-16. Not approved. This version is identified only by the commit that adds it, and an approval must name that commit and this path. Annex `work-orders/CRM-CLIENT-001-browser-annex.md` (annex B) is part of this version.
- **History:**
  - v1.0 was commit `972b809ab36e8befbc6126a0649c6592d24694d3`.
  - v1.1 answers the CGPT directive *Extended autonomous preflight and Work Order finalisation* (2026-11-16), Phase A (items A1–A5), Phase B and Phase C:
    - it records CL-D1 and CL-D3 as decided;
    - it adds the browser runner, the isolation design and the dependency lock (annex B1–B4);
    - it adds immutable canary versions (annex B5), the evidence route (B6) and the post-swap failure semantics (B7);
    - it resolves the module format (§2 F8);
    - it adds the G2 assessment (§11).

    The source allowlist and exclusions of v1.0 are kept. Additions are made only for the browser runner, the fixtures and the evidence (§4, marked **v1.1**).
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/59
- **Prepared by:** Rogue (Orchestrator), under the CGPT Architect directives of 2026-11-13 and 2026-11-16. These authorise preparation only: **no dispatch, no deployment, no pull or run of the browser image.**
- **Approval:** none. Dispatch needs a CGPT approval comment on Issue #59 that names this path and the immutable commit containing v1.1 (FOUNDRY `standards/work-order-contract.md`, *Approval provenance*).

## 1. Authority and governing records

| Item | Value |
|---|---|
| Governing FOUNDRY | `5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0` (`maff0000/foundry`) |
| WO standard | `standards/work-order-contract.md` at that revision, sha256 `cbb6eb3ae62bf7877ae470abf2297a5af5ffb23ca617581a9a85077dd9a8ebcc` |
| Product authority | Matt's PO approval of the Vision, the Backlog (PBI-018..029) and CRM-D020..D032 at `dc6fb4ced68d9139c2332af973084239492104b3` (Issue #54, 2026-11-13T12:04:29Z) |
| Architect decisions | CL-D1 and CL-D3 (CGPT, 2026-11-16); see §12 |
| Parent PBI | **CRM-PBI-016** (container release packaging). It enables CRM-PBI-018 (CRM-FG-001) and CRM-PBI-020 |
| Starting `main` | **`6e1766980e24d781d498727d4fe5db43cdeadbb7`**, re-verified on 2026-11-16 against the GitHub API |
| Pinned EspoCRM | `espocrm/espocrm:10.0.12@sha256:b50245d1e291b2636116b0396ce0d06018ffcded6a6c61c7af2420443a20f3ec` |
| Unit baseline | The `main` unit suite gives 564 OK and 1 skip, run as `nobody` from a `git archive` copy (Issue #56 comment 6858541012) |

## 2. Problem and verified facts (PL preflight, read-only)

The CRM has no path for CRM-owned browser code. The FirmGroup *Group Members* tab and the WIP/Revenue tab both need client views, and copying JavaScript by hand into a runtime is forbidden. This WO delivers the mechanism only, with no product UI.

The image was inspected by `docker create` followed by `docker export`; no container was started. For each upstream file the sha256 is the file inside the pinned image.

| # | Fact | Evidence |
|---|---|---|
| F1 | On every start the entrypoint chowns `./data`, `./custom` and `./client/custom` to www-data. It recopies `client/` only when `/var/www/html/client` is itself a mount, which is not the case here, and it never touches `client/custom` | `/usr/local/bin/docker-entrypoint.sh` `9f0b70326ec5065e1358b782c39eb264e08cf14df01dfb8c41085fbec32020e2` |
| F2 | `client/custom/modules` is a **reserved** EspoCRM path, used for extensions | `Espo/Core/Utils/File/Manager.php` `RESERVED_CUSTOM_PATH_LIST`; `Permission.php` `687e8d73f3b4258ae66f69b91ef741eedad8c2335ad43250675558a4b847e161` |
| F3 | **Cache invalidation.** Outside developer mode the loader versions module URLs with **`appTimestamp`** (`?r=<appTimestamp>`). `clear-cache` changes only `cacheTimestamp`. `appTimestamp` changes only through `bin/command update-app-timestamp`, an upgrade or a migration, and its value is `time()` in whole seconds. It is stored as a state parameter in `data/state.php` and exposed to the client as a global setting | `ClientManager.php` `725121562a41876d79db16f6ace4d961bb1aae9cb30123b7bfafbee98ab62f40`; `DataManager.php` `a701fe39d936072b63c3454ef7299df18101e600ecd6860cc8bb0062f1ccad0f`; `UpdateAppTimestamp.php` `15d82eae42aa72ccc8ebf541d2935fc68ad24819d89868143370493e38cd098b`; `Config/InternalConfigHelper.php` `8e6c9d99b73373a96ec6270ab71af4bac20ddb7bb04cc7ecaee905c20d8ea2e2` (`stateParamList`); `Config.php` (`data/state.php`); `defaults/systemConfig.php` (`globalItems`) |
| F4 | The CSP is `script-src 'self' 'nonce-…' 'unsafe-eval'`, so client code must be same-origin | `ClientManager.php` line 116 |
| F5 | The repository has no `client/` tree. `scripts/deploy_custom.sh` (`d1aaa430e150e95c8e42c93ba3544afdcfbcd40117e0eed1aa0083c7ef9ed67b`) deploys only `custom/Espo/Custom` and runs `clear-cache` and `rebuild`, with no `update-app-timestamp` | `main` @ `6e176698` |
| F6 | Persistence already covers `client/custom`: `CRM_PERSISTENT_DIRS`, `client-custom.tar.gz` in backup and restore, compose mount checks, and `make_runtime` | `common.sh` `34f622395c169ae2e3cc30229ba72ed2073f29a7e5d5fe23d5511fe955d0fff1`; `backup.sh` `ba67fa26fdb49e70f4a53fb329af6813e56e2fc7ac65a83fc790b33b648c0fc3`; `restore.sh` `c1e92f0d43e730c5b627d2a3f5afc67f27529d216fde891010df42b94d3ac78f`; `deploy_release.sh` `54aaedb320e9a26dfccbc1e5916a72cf021483b75beef14ec9e68ac4640524d7` |
| F7 | A release is the `git archive` of a commit minus `.forge/`. A tracked `client/custom/src/` is therefore bundled and checked by `verify-tree` without any change to `release.py` (`0560e352ba3e5fa79fe08694542550ed33b021fef61dd017e2e7c8c74bd06f8f`). The new deploy behaviour reaches beta **only** through a future, separately authorised `deploy_release.sh` run | `release.py` `EXCLUDED`; `deploy_release.sh` `start_stack` |
| **F8 (A5, resolved)** | The **module format is AMD.** In `client/lib/espo.js` (`9c88b9db81ffdb35f99f9c77619a8fb56a338a355672173e670dc88ca9ebd318`):<br>• `_idToPath` maps `custom:<p>` to `client/custom/src/<p>.js`.<br>• The global `define(deps, factory)` is AMD (`define.amd = true`). An anonymous `define` is bound to its module id through the requesting script URL (`_urlIdMap`).<br>• The factory's return value is the module, and `undefined` raises `Could not load '<id>'`.<br>• With a cache timestamp set, the script URL gets `?r=<timestamp>`, and the loader's timestamp outside developer mode is `appTimestamp` (F3).<br>• Untranspiled ES-module syntax (`import`/`export`) is **not** supported in `client/custom/src`: only module ids listed in `_transpiledModuleList` are loaded from `lib/transpiled` paths.<br>**The canary is therefore a plain-ES2015 AMD file:** `define([], function () { return Object.freeze({name: 'crm-release-canary', contract: N, describe: function () { return 'crm-release-canary/' + N; }}); });`. It loads through `Espo.loader.requirePromise('custom:crm/release-canary')` | upstream `espo.js` (minified; behaviour quoted in the PL record) |
| F9 | No browser automation is installed or approved on DOCKER1, and the Playwright image has not been pulled (re-checked 2026-11-16). No earlier CRM WO produced in-cycle real-browser evidence: CRM-003 was escalated | host check; `.forge/CRM-003/REPORT.md` |

**PBI-016/017 deviation.** This WO keeps the deploy-into-runtime model (CRM-D017 deviation) and extends it to `client/custom/src`. It claims **no** baked-image or clean-host acceptance, and it does not implement PBI-016 (CL-D4).

## 3. Intended outcome

1. A tracked, CRM-owned `client/custom/src/` is the only source of CRM browser code (CL-D1).
2. `scripts/deploy_custom.sh dev|beta` deploys `custom/Espo/Custom` **and** `client/custom/src`, using the same stop, secure, stage and rename discipline. `client/custom/modules` and every other runtime path are left untouched.
3. Each deploy then runs `clear-cache`, `rebuild` and **`update-app-timestamp`**, with a strict check that the timestamp advanced (annex B5).
4. Defined failure semantics after the swap: no false success, the failed step is named, the previous trees are recovered, and then either a recovered cache-bust or a controlled shutdown (annex B7).
5. Backup, restore and rollback cover the client tree.
6. A non-user-visible AMD canary, `custom:crm/release-canary`, proves loading, versioning, cache-bust, rollback and recovery in a real browser (annex B5).
7. All existing customisations and protections keep working.

## 4. In scope (allowlist, exhaustive)

| Path | Change |
|---|---|
| `client/custom/src/crm/release-canary.js` | **new.** The AMD canary of F8 with **contract 1**. No network, DOM, storage or globals. It is not referenced by any clientDefs, layout, `app/client.json`, navbar or i18n |
| `scripts/deploy_custom.sh` | Deploy `client/custom/src`; keep the previous trees until success; run `update-app-timestamp` with an advance check; implement the annex B7 failure and recovery semantics; print integer appTimestamp values only |
| `scripts/lib/common.sh` | Only if a shared swap helper is factored out. The existing guards must not be weakened, and CRM-TEST-001 M1–M4 must still kill |
| `tests/unit/test_scripts.py` | New tests (AC2–AC5, AC4b). Existing tests stay unchanged, except the expected call lists that gain the new step |
| `tests/unit/test_client_custom.py` | **new.** Static policy for `client/custom/` and `tests/browser/` (AC1, AC7, AC11) |
| **v1.1** `tests/browser/requirements.lock` | **new.** Exactly the four hash-pinned wheels of annex B2 |
| **v1.1** `tests/browser/entry.sh`, `probe_isolation.py`, `journeys.py`, `verify_evidence.py` | **new.** Container entry point, isolation probe, journeys J1–J5, and the offline evidence verifier (annex B4–B6). They run only inside the hardened container, except `verify_evidence.py`, which only reads files and is run by the Tester in the sandbox |
| **v1.1** `tests/browser/fixtures/canary-transition/v2/crm/release-canary.js` | **new.** Identical to the canary except **contract 2** (annex B5) |
| `docs/RELEASE.md`, `docs/BETA.md`, `docs/BUILD.md` | The client delivery, cache-bust, failure and recovery, backup and rollback, and browser-run procedure, plus the PBI-016 deviation note |
| `security/EXTERNAL_CODE_REGISTER.yaml` | **v1.1:** the `playwright-python-browser-runner` candidate entry (annex B2) |

Any other path is out of scope, and a need for one is a **stop** (§11).

## 5. Exclusions (unchanged from v1.0)

- `custom/Espo/Custom/**`, `config/access/**`, `deploy/**`, `scripts/release.py`, `scripts/deploy_release.sh`, `scripts/backup.sh`, `scripts/restore.sh`, `scripts/up.sh`.
- Any metadata or layout change that makes client code user-visible.
- `client/custom/modules/**`, which is never written, removed or swapped.
- The running beta (`/srv/CRM/runtime/beta`, `/srv/CRM/deploy`), Salesforce, the legacy WIP repository and its data, FOUNDRY, ForgeV2, and other host applications.
- Any CDN, npm, Node toolchain, bundler or minified or vendored blob in `client/custom`.
- **v1.1:**
  - any persistent Docker network, image or container left after the WO;
  - any firewall rule;
  - any use of host networking or the Docker socket by the browser runner.

## 6. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| AC1 | `client/custom/` in Git holds only `src/**`.<br>• Allowed types are `.js`, `.css`, `.json`, `.tpl` and `.svg`, with no symlinks, no executable bit and no file over 256 KiB.<br>• There is no `modules/`.<br>• Every `.js` file is AMD (`define(`), with no `import`/`export` statements.<br>• Banned constructs: remote URLs, `eval`, `new Function`, `document.write`, `innerHTML` assignment, absolute-URL fetch or XHR, and storage APIs.<br>• The v2 fixture differs from the canary only in the contract value. | `test_client_custom.py`, with a broken fixture for each rule |
| AC2 | `deploy_custom.sh` replaces the runtime `client/custom/src` as a whole, staged and renamed on the same filesystem, after the stop and with path security as for `Espo/Custom`.<br>• It refuses symlinked or redirected `client`, `client/custom` or `src`.<br>• Files removed from Git disappear from the runtime. | `test_scripts.py`. Each refusal case fails **before** any swap |
| AC3 | `client/custom/modules`, and every non-`src` entry in `client/custom`, are byte-identical before and after a deploy, a failure and a recovery | `test_scripts.py` hash comparison |
| AC4 | The success path runs `up --wait`, `clear-cache`, `rebuild` and `update-app-timestamp`, in that order, in crm-app as www-data.<br>• The appTimestamp after the update is strictly greater than before. The script retries once after one second, and otherwise fails.<br>• With the stack stopped, it prints that the cache-bust was skipped and how to complete it. | `test_scripts.py`, recorded fake-docker calls |
| **AC4b** | **Post-swap failure (annex B7).** For an injected failure at each post-swap step, and at each recovery step:<br>• the exit code is non-zero and step-specific;<br>• `FAILED STEP: <step>` is printed, and there is no success line;<br>• the previous trees are restored byte for byte, and `.failed-<stamp>` is retained;<br>• after recovery a cache-bust ran, or the stack is stopped and `RECOVERY FAILED` is printed. | `test_scripts.py` failure injection; on crm-dev, J4 |
| AC5 | **Backup and rollback.**<br>• A backup, then a deploy of B over A, then `restore.sh`, gives A back byte for byte in `client/custom/src`.<br>• Redeploying A over B removes the files that exist only in B.<br>• Both are followed by a cache-bust. | `test_scripts.py`; on crm-dev, J3 and J5 |
| **AC6** | **Real browser** on synthetic crm-dev, with the annex B1 image pinned by digest, the B4 isolation proven first, and D0–D5 run in order (annex B5):<br>• **J1:** contract 1, and the URL `r` equals `a1` (with `a1 > a0`);<br>• **J2:** contract 2, `a2 > a1`, and a new network fetch;<br>• **J3:** after rollback, contract 1 and `a3 > a2`;<br>• **J4:** after the injected failure, recovered contract 1 and an advanced `r`;<br>• **J5:** after restore, the canary is absent and the regression screens match D0.<br>For every journey there is no CSP violation and no canary console error. The login, Account list and detail, Enquiry list and detail, and Stream panels render. | Annex B6 evidence package; the Tester's independent verdict (CL-D3) |
| AC7 | No user-visible change: the canary is unreferenced in any metadata or layout, and the `custom/**` diff is empty | static test; diff limited to §4 |
| AC8 | **Regression.**<br>• The full unit suite passes as non-root from a `git archive` copy, with at least the starting count.<br>• `tests/load` passes.<br>• The CRM-TEST-001 M1–M4 mutations still kill.<br>• The existing `deploy_custom` and guard tests pass unchanged. | Orchestrator host procedure (as CRM-TEST-001 §7); Tester re-run on the PL snapshot |
| AC9 | **Release integrity.**<br>• A bundle of the candidate passes `release.py verify --sha256`.<br>• `RELEASE.json` lists the canary with its sha256.<br>• `verify-tree` refuses a file injected under `client/custom/src`. | Temporary directory, run as `nobody` |
| AC10 | The documentation is truthful: client delivery, cache-bust, failure and recovery, rollback, the browser procedure, and the PBI-016/017 deviation. It makes no baked-image or clean-host claim. | Auditor |
| **AC11** | **Browser runner integrity.**<br>• `requirements.lock` equals annex B2 exactly, with `--hash` lines.<br>• `journeys.py` and `probe_isolation.py` contact only `CRM_BROWSER_BASE_URL` and the probe targets passed in as data. They contain no credentials or addresses as literals.<br>• `verify_evidence.py` does no network I/O and recomputes every AC6 verdict from the raw files. | `test_client_custom.py`; DevSecOps |

A skipped, unrun or screenshot-only check is **not PASS**.

## 7. Security and supply-chain controls

- **Source of truth:**
  - Git for dev, and a `--sha256`-anchored, verified release for beta;
  - the transition tree is only an overlay of the candidate's own blobs (annex B5).
- **Client code:**
  - same-origin, plain hand-written AMD;
  - no third-party JavaScript.
- **Path safety:**
  - `real_dir`, `owned_private` and `secure_dir` are reused;
  - no recursion through a symlink;
  - `--one-file-system` throughout;
  - the reserved `modules/` is never touched.
- **Browser runner (annex B1–B4):**
  - the official image is pinned by digest;
  - offline, hash-locked wheels;
  - uid 65534, read-only rootfs, all capabilities dropped, `no-new-privileges`, default seccomp and AppArmor;
  - no Docker socket, no host network;
  - a per-run internal network with no host-side bridge address;
  - isolation is proven by probe before any journey;
  - full teardown afterwards.
- **No secrets or customer data:**
  - only synthetic crm-dev data and synthetic `@example.test` users;
  - credentials are passed by env file and never appear in argv or evidence;
  - gitleaks runs on the candidate, the snapshot and every evidence package.
- **Open item:** vulnerability scanning of the runner image is CL-D5 (annex B8).

## 8. Roles, independent criteria and evidence paths

| Role | PASS only if |
|---|---|
| Engineer | §4 is implemented, and every test for AC1–AC5, AC4b, AC7, AC9 and AC11 exists and is mutation-sensitive. Nothing outside §4 changes. |
| Auditor | The diff matches §4 and §5. The F1–F8 claims hold against the recorded upstream facts. The documentation is truthful. |
| Tester | All ACs are evidenced on the **same unchanged candidate**. The unit-suite re-run on the PL snapshot passes. Its **own** AC6 verdict per journey comes from `verify_evidence.py`, the raw evidence and the trace (annex B6), and it may request one bounded repeat. |
| DevSecOps | §7, AC1 and AC11 hold. The swap and recovery ordering is sound. Runner hardening and isolation evidence are in place (`identity.json`, `isolation.json`). There is no CSP finding and no secret. |

- **Engine records:** `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-CLIENT-001/`. They hold only `REPORT.md` and `prompts/*.md`.
- **PL evidence:** `/home/forgev2-pl/crm-evidence/CRM-CLIENT-001/`, indexed by `CRM-CLIENT-001.sha256`.
- **Specialist-readable scratch:** `/srv/CRM/worktrees/.forge-scratch/CRM-CLIENT-001/`, which holds:
  - `snapshot-<sha12>/` (§6b pattern of CRM-TEST-001);
  - `diff-<sha12>/`;
  - `browser-<sha12>-<run>/`.
- **Execution limit:** four executions per specialist, including the first. This is a hard maximum, and exhaustion is FAIL with escalation to CGPT.

## 9. Real-browser execution plan

This is annex B in full:
- B1: the component;
- B2: the dependency lock and the offline installation;
- B3: the hardened invocation;
- B4: network isolation and teardown;
- B5: the D0–D5 deployment order and assertions;
- B6: the evidence package and the route to the Tester;
- B7: failure injection.

Only the operator acts on Docker, crm-dev or the network, and only after G1–G5. Beta is never a target.

## 10. Repository and workspace

- **Canonical checkout and start:** `/srv/CRM/main`, then `forge-start --wo CRM-CLIENT-001 --base main --known-commit <docs-merge SHA of this approved version>`.
- **Worktree:** `/srv/CRM/worktrees/CRM-CLIENT-001`, on branch `forge/CRM-CLIENT-001`.
- **Specialists:** run as `forgev2-pl` under the engine sandbox and use no Git; the PL provides snapshots.
- **Engineer-authored code runs** only in the sandbox, as `nobody` on the host from `git archive` copies, or as uid 65534 inside the browser container. It never runs as root or as the PL.

## 11. Entry gates, stop conditions and reporting

| Gate | Requirement | State |
|---|---|---|
| G1 | CGPT exact-version approval of v1.1 (path and commit) on Issue #59 | open |
| **G2** | **Sandbox entry gate for CRM-CLIENT-001.** See the assessment below this table. | **evidence ready; CGPT acceptance open** |
| G3 | **Browser component.** Annex B1/B2 records the selection. Open items:<br>• CGPT acceptance of the register entry;<br>• CL-D5 (scanning) decided;<br>• at execution, the operator verifies the RepoDigest and config ID after the pull. | open |
| G4 | Docs merge of v1.1. Its merge SHA becomes `--known-commit`. | open |
| G5 | **Dispatch and run preflight:**<br>• main is unchanged or compatibly advanced;<br>• crm-dev is synthetic and backed up;<br>• the browser network subnet is unused;<br>• the beta metadata snapshot (`0:0 700 1794416166` at preparation) is recorded and re-checked after the run. | open |

**G2 assessment for CRM-CLIENT-001** (re-verified on 2026-11-16, and unchanged since the CRM-TEST-001 annex §7):

| Component | Identity |
|---|---|
| ForgeV2 | `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, with a clean tracked tree. The only ignored entry is the accepted `plugin/lib/__pycache__/forgelib.cpython-313.pyc`, sha256 `1e456d81…52c1`. |
| Claude | 2.1.317, sha256 `eb224419e344575faa4a1f39b290b649425a10cd5ee2ef1d003480cd9ae57eb0` |
| bubblewrap | 0.12.0-1~deb13u1, sha256 `573236e5328ac2ebb08f59ae3a9805b4f8d12bdef14be8af4450d5463294985f` |
| `forgelib.py` | `6a7d587a79da13de733dc41a97e6f499c163062151175acda74918ca19f6dc55` |

**What carries over.** The 2026-11-09 CRM-001 acceptance (`maff0000/forgev2#5` comment 6746699026) and the CRM-TEST-001 acceptance are **specific to those WOs**. They are not engine certification: ENGINE-SANDBOX-TEST-001 (`forgev2#5`) is still **open**.

**Applicability to this WO:**
- Specialists need only file editing, Python and shell in the sandbox, and reads of the PL snapshot and evidence. This is the same capability set CRM-TEST-001 used.
- No sandbox network, Docker or Git access is requested.
- The browser, Docker and crm-dev steps are orchestrator-run outside the sandbox (annex B).

**New exposure compared with CRM-TEST-001:**
- The Engineer edits `scripts/deploy_custom.sh`, which the operator later runs **as root** against crm-dev. This is mitigated as follows:
  - it runs only from a `git archive` copy of the reviewed candidate;
  - it runs only after four independent PASS verdicts on that candidate;
  - it runs only against synthetic crm-dev;
  - the AC4/AC4b tests and the DevSecOps review cover it;
  - this matches the existing practice for `deploy_custom.sh` (CRM-001/007).
- The Engineer also authors browser code. That code runs inside the hardened runner as uid 65534 (annex B3).

**Remaining limitations:**
- The sandbox's Git read isolation has not been established.
- The sandbox maps root-owned host files to uid 65534 (observed).
- Both are tolerated, because specialists are told not to use Git and are given snapshots. Any observed Git use by a specialist is a recorded deviation.

**Stop immediately** for any of the following:
- a need outside §4, or any write to `client/custom/modules`;
- a failed security, isolation or entry gate, including an unexpected probe success;
- a digest or hash mismatch;
- a candidate change after review;
- any contact with beta, Salesforce or real data;
- an exhausted execution limit;
- unverifiable EspoCRM 10.0.12 behaviour.

After four PASS verdicts on the same candidate, the PL returns READY_FOR_CGPT with the head, the patch sha256 and the evidence index. **No beta deployment.**

## 12. Decisions

| ID | Decision | Status |
|---|---|---|
| CL-D1 | CRM-owned client source lives exclusively under `client/custom/src/`. `client/custom/modules/` is never overwritten or managed. The existing secured deploy and release processes are kept. | **Decided** (CGPT, 2026-11-16) |
| CL-D2 | Real-browser component: the official Playwright Python image, pinned per annex B1, with dependencies per B2, hardened per B3 and isolated per B4. | **Selected by the PL** per the CGPT preference. CGPT acceptance of the register entry is open (G3) |
| CL-D3 | Orchestrator-run real-browser tests, followed by independent Tester verification, are accepted for this WO **only** with the annex B6 evidence package and route. The Tester issues its own verdict and may request one bounded repeat. A screenshot alone is insufficient. | **Decided** (CGPT, 2026-11-16), with conditions incorporated |
| CL-D4 | Baking `client/custom` into a `crm-espocrm` image is PBI-016 work and not this WO. No PBI-016/017 acceptance is claimed. | Recorded |
| CL-D5 | Vulnerability scanning of the runner image: approve a pinned scanner, or accept the risk (annex B8). | **Open** (CGPT) |
| CL-D6 | Canary transition uses committed fixtures overlaid from one candidate, not two ordered commits. Reason: execution-limit economy; every deployed byte is still a blob of `F` (annex B5). | PL design under the A3 options |
