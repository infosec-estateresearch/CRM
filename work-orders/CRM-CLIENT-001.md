WO: CRM-CLIENT-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main
BROWSER: yes (orchestrator-run real-browser journeys against the synthetic crm-dev stack; see §9 and open decision CL-D2)

# CRM-CLIENT-001: version-controlled delivery of CRM-owned browser customisations (`client/custom/`)

- **Version:** v1.0 DRAFT, 2026-11-13. Not approved. This version is identified only by the commit that adds it; an approval must name that commit and this path.
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/59
- **Prepared by:** Rogue (Orchestrator), under the CGPT Architect *Extended Autonomous Delivery Run*, Phase B (preparation only, **no dispatch**).
- **Approval:** none. Dispatch needs a CGPT approval comment on Issue #59 that names this path and the immutable commit (FOUNDRY `standards/work-order-contract.md`, *Approval provenance*).
- **Sandbox entry gate:** not yet accepted for this WO (§11). Without a CRM-CLIENT-001-specific acceptance the WO is **BLOCKED** before dispatch.

## 1. Authority and governing records

| Item | Value |
|---|---|
| Governing FOUNDRY | `5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0` (`maff0000/foundry`) |
| WO standard | `standards/work-order-contract.md` at that revision, sha256 `cbb6eb3ae62bf7877ae470abf2297a5af5ffb23ca617581a9a85077dd9a8ebcc` |
| Product authority | Matt's PO approval of Vision, Backlog (PBI-018..029) and CRM-D020..D032 at `dc6fb4ced68d9139c2332af973084239492104b3` (Issue #54, 2026-11-13T12:04:29Z) |
| Parent PBI | **CRM-PBI-016** (container release packaging). Enabler for CRM-PBI-018 (FirmGroup UI, CRM-FG-001) and CRM-PBI-020 (WIP/Revenue tab) |
| Related decisions | CRM-D017 (release bundle; production image bakes customisations), CRM-D021 (WIP is a CRM module), CRM-D032 (bounded, exact-approved WOs) |
| Starting `main` | **`6e1766980e24d781d498727d4fe5db43cdeadbb7`** (merge of PR #58, CRM-TEST-001). Local checkout, `origin/main` and `ls-remote` agree (2026-11-13) |
| Pinned EspoCRM | `espocrm/espocrm:10.0.12@sha256:b50245d1e291b2636116b0396ce0d06018ffcded6a6c61c7af2420443a20f3ec` (`security/EXTERNAL_CODE_REGISTER.yaml`) |
| Unit baseline | `main` unit suite 564 OK, 1 skip, run as `nobody` from a `git archive` copy after the PR #58 merge (Issue #56 comment 6858541012) |

## 2. Problem and verified facts (PL preflight, 2026-11-13, read-only)

The CRM can deliver server-side customisations (`custom/Espo/Custom/`) from Git, but it has **no** path for CRM-owned browser code. The FirmGroup *Group Members* tab (FG-06, other members of the group, which is not a plain relationship panel) and the WIP/Revenue tab both need client-side views. Copying JavaScript into a runtime by hand is forbidden. This WO provides the delivery mechanism only, with no product UI.

Facts verified by the PL. The image was inspected with `docker create` and `docker export`; no container was started. Each fact names the upstream file and its sha256 inside the pinned image.

| # | Fact | Evidence |
|---|---|---|
| F1 | The image's entrypoint chowns `./data`, `./custom` and `./client/custom` to www-data on every start. It recopies `client/` from `/usr/src/espocrm/client/` only when `/var/www/html/client` itself is a mount, which it is not here, and it never touches `client/custom`. | `/usr/local/bin/docker-entrypoint.sh` sha256 `9f0b70326ec5065e1358b782c39eb264e08cf14df01dfb8c41085fbec32020e2` (`CUSTOM_RESOURCE_LIST`, `copyClientFiles`) |
| F2 | `client/custom/modules` is a **reserved** EspoCRM path: extensions install there. `client/custom` is writable by EspoCRM, recursively. | `Espo/Core/Utils/File/Manager.php` (`RESERVED_CUSTOM_PATH_LIST`); `Espo/Core/Utils/File/Permission.php` sha256 `687e8d73f3b4258ae66f69b91ef741eedad8c2335ad43250675558a4b847e161` |
| F3 | **Cache invalidation.** Outside developer mode, the client loader versions module URLs, scripts and CSS with **`appTimestamp`** (`?r=<appTimestamp>`). `clear-cache` updates only `cacheTimestamp`. `appTimestamp` changes only through `bin/command update-app-timestamp`, an upgrade or a migration. **The current `deploy_custom.sh`, which runs `clear-cache` and `rebuild`, would therefore leave browsers on cached client code after a client change.** | `Espo/Core/Utils/ClientManager.php` sha256 `725121562a41876d79db16f6ace4d961bb1aae9cb30123b7bfafbee98ab62f40` (lines 201–239); `Espo/Core/DataManager.php` sha256 `a701fe39d936072b63c3454ef7299df18101e600ecd6860cc8bb0062f1ccad0f` (`clearCache`, `updateAppTimestamp`); `Espo/Core/Console/Commands/UpdateAppTimestamp.php` sha256 `15d82eae42aa72ccc8ebf541d2935fc68ad24819d89868143370493e38cd098b`; `consoleCommands.json` `updateAppTimestamp` |
| F4 | The CSP is `script-src 'self' 'nonce-…' 'unsafe-eval'`, so client code must be same-origin. No CDN code is permitted (also boundary doc, *Failure containment*). | `ClientManager.php` line 116 |
| F5 | The repository has no `client/` tree. `scripts/deploy_custom.sh` (sha256 `d1aaa430…d67b`) deploys only `custom/Espo/Custom`, by a secured stop, stage and rename swap. | `main` @ `6e176698` |
| F6 | The persistence layer already treats `client/custom` as runtime state: `CRM_PERSISTENT_DIRS=(data custom client/custom)`, `client-custom.tar.gz` in backups, restore, mount checks for both dev and beta compose files, and `make_runtime` creates `client/custom` (0700). | `scripts/lib/common.sh` sha256 `34f62239…fff1`; `scripts/backup.sh` `ba67fa26…0fc3`; `scripts/restore.sh` `c1e92f0d…e30c`; `scripts/deploy_release.sh` `54aaedb3…24d7` |
| F7 | A release bundle is `git archive` of the commit minus `.forge/`. A new tracked `client/custom/src/` is therefore bundled, hashed in `RELEASE.json` and checked by `verify-tree` with no change to `release.py` (sha256 `0560e352…8f06`). `deploy_release.sh` runs `deploy_custom.sh beta` from the unpacked release, so a change to `deploy_custom.sh` reaches beta **only** through a future, separately authorised release deployment. | `scripts/release.py` (`EXCLUDED = (".forge/",)`), `deploy_release.sh` `start_stack` |
| F8 | `custom:` view and module names resolve to `client/custom/src/…` (EspoCRM convention). **This is a PL expectation, not yet verified in a running 10.0.12.** AC6 proves it in a real browser. | to be verified (AC6) |
| F9 | No browser automation is installed or approved on DOCKER1 (no Chromium, Firefox, Node or Playwright). No earlier CRM WO produced in-cycle real-browser evidence: CRM-003 was *ESCALATED (browser and live checks only)*. | host check, 2026-11-13; `.forge/CRM-003/REPORT.md` |

**PBI-016/017 deviation (recorded, not resolved).** Beta runs the pinned upstream image with customisations deployed into the runtime, not a baked `crm-espocrm` image (CRM-D017). This WO **keeps** that model and extends it to `client/custom/src`. It does **not** claim baked-image or clean-host (PBI-017) acceptance. Baking `client/custom` into an image remains PBI-016 work.

## 3. Intended outcome

1. A tracked, CRM-owned client tree `client/custom/src/` in the repository, which is the only source of CRM browser code.
2. `scripts/deploy_custom.sh dev|beta` deploys **both** `custom/Espo/Custom` and `client/custom/src`:
   - from Git or the verified release only;
   - with the same stop, secure, stage and rename discipline;
   - leaving the reserved `client/custom/modules` and every other runtime path untouched.
3. Each deploy then makes browsers load the new code by running `clear-cache`, then `rebuild`, then **`update-app-timestamp`** (F3). The appTimestamp value is recorded, and the order is tested.
4. Backup, restore and upgrade/rollback cover the client tree, and tests prove it.
5. A **non-user-facing canary module** `custom:crm/release-canary` proves, in a real browser against 10.0.12, the `custom:` path mapping, loading, versioned URLs and the cache-bust after a change. It does this without changing any user view.
6. Every existing customisation and protection keeps working (regression).

## 4. In scope (allowlist, exhaustive)

| Path | Change |
|---|---|
| `client/custom/src/crm/release-canary.js` | **new.** An AMD/ES module, self-contained, with no network, DOM, storage or globals. It exports `{name: "crm-release-canary", contract: 1}` and a pure function. It is **not** referenced by any clientDefs, layout, `app/client.json` or navbar |
| `scripts/deploy_custom.sh` | deploy `client/custom/src` beside `custom/Espo/Custom`; then `update-app-timestamp`; print the before and after appTimestamp values (integers only) |
| `scripts/lib/common.sh` | only if a shared helper for the secured swap is factored out. The existing guards must not be weakened (CRM-TEST-001 M1–M4 must still kill) |
| `tests/unit/test_scripts.py` | new tests (AC2–AC5, AC8); existing tests unchanged except for the expected-call list where the new step is added |
| `tests/unit/test_client_custom.py` | **new.** Static policy for `client/custom/` (AC1, AC7) |
| `tests/browser/` | **new**, only once CL-D2 is decided: journeys and a runner for the orchestrator browser run (§9). They are not imported by the unit suite |
| `docs/RELEASE.md`, `docs/BETA.md`, `docs/BUILD.md` | the client delivery, cache-bust, backup and rollback procedure; the PBI-016 deviation note |
| `security/EXTERNAL_CODE_REGISTER.yaml` | only to record the browser component if CL-D2 approves one (candidate, `approval:` as decided) |

Anything else is out of scope. A need to touch another path is a **stop** (§11).

## 5. Exclusions (no change permitted)

- `custom/Espo/Custom/**` (no server-side behaviour change), `config/access/**`, `deploy/**`, `scripts/release.py`, `scripts/deploy_release.sh`, `scripts/backup.sh`, `scripts/restore.sh`, `scripts/up.sh`.
- Any clientDefs, layout, `app/client.json`, navbar or i18n change that would make the canary or any client code user-visible.
- `client/custom/modules/**`: reserved for EspoCRM extensions (F2). It is never written, removed or swapped.
- The running beta (`/srv/CRM/runtime/beta`, `/srv/CRM/deploy`), Salesforce, the legacy WIP repo and its data, FOUNDRY, ForgeV2 (`/srv/forgev2`, `/srv/foundry`), and other host applications (CRM strict boundary).
- Any CDN, remote script, npm/Node toolchain or bundler. Client code is plain hand-written source, reviewed as text.

## 6. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| AC1 | `client/custom/` in Git holds only `src/**`. Only `.js`, `.css`, `.json`, `.tpl` and `.svg` are allowed, with no symlinks, no executable bits and no file over 256 KiB. There is no `modules/` in Git. Every `.js` file is free of remote URLs, `eval`, `new Function`, `document.write`, `innerHTML` assignment with untrusted input, `fetch` or XHR to absolute URLs, and storage APIs (in the canary) | `test_client_custom.py`, with a broken-fixture test for each rule |
| AC2 | `deploy_custom.sh` replaces the runtime `client/custom/src` as a whole, by stage and rename on the same filesystem, after the containers are stopped and the paths are secured as for `Espo/Custom`. It refuses a symlinked or redirected `client`, `client/custom` or `src`. Files removed from Git disappear from the runtime | `test_scripts.py`, fake docker; symlink, redirect, pre-existing staging and wrong-owner cases each refuse **before** any swap |
| AC3 | The runtime `client/custom/modules` (extension content), and any non-`src` entry in `client/custom`, are byte-for-byte unchanged by a deploy | `test_scripts.py`, with a hash before and after |
| AC4 | After a deploy with a running stack, the commands run in order `clear-cache`, `rebuild`, `update-app-timestamp`, all inside crm-app as www-data. Any failure exits non-zero and leaves no success message. If the stack was not running, the script prints that the cache-bust was skipped and how to complete it | `test_scripts.py`, recorded fake-docker call list and failure injection |
| AC5 | **Backup and rollback.** A deploy of tree B over tree A, followed by `restore.sh` of a backup taken before it, gives A back byte for byte in `client/custom/src`. Redeploying release A over B removes B-only files. Both cases are followed by a cache-bust | `test_scripts.py` (backup → deploy → restore; deploy A → B → A) |
| AC6 | **Real browser (10.0.12, synthetic crm-dev).** (a) After a deploy, `Espo.loader` resolves `custom:crm/release-canary` and returns `contract: 1`. (b) The module URL carries `?r=<appTimestamp>` equal to the deployed value. (c) After a canary change (contract 2) and a redeploy, a **fresh** load in the same profile gets contract 2 with a new `r` value, with no manual cache clear. (d) No CSP violation and no console error from the canary. (e) The login, Account list and detail, Enquiry list and detail, and Stream panels render as before (screenshots before and after) | Orchestrator browser run (§9); the Tester reviews the recorded artifacts |
| AC7 | No user-visible change: the canary is not referenced by any metadata or layout, and the `custom/**` diff is empty | `test_client_custom.py`; `git diff --stat` limited to the §4 allowlist |
| AC8 | **Regression.** The full unit suite passes as non-root from a `git archive` copy, at the starting count or higher. `tests/load` passes. The CRM-TEST-001 M1–M4 mutations still fail their targets. The existing `deploy_custom` and guard tests pass unchanged | Orchestrator host procedure (as CRM-TEST-001 §7); Tester re-run on the PL snapshot (§6b pattern) |
| AC9 | Release integrity: a bundle built from the candidate passes `release.py verify --sha256`. Its `RELEASE.json` lists `client/custom/src/crm/release-canary.js` with the expected sha256. `verify-tree` refuses an extra file injected under `client/custom/src` | `release.sh` plus `verify` / `verify-tree` in a temp directory, as `nobody` |
| AC10 | Docs: RELEASE.md and BETA.md describe the client tree, the cache-bust, the pre-upgrade backup and the rollback steps. They state the PBI-016/017 deviation and make no baked-image or clean-host claim | Auditor review |

A skipped or unrun check is **not PASS**.

## 7. Security and supply-chain controls

- **Source of truth.** Client code reaches a runtime only from a Git commit (dev) or a `--sha256`-anchored, verified release (beta). There is no copy from a workstation, specialist output or runtime.
- **Same-origin only** (F4). There is no third-party JavaScript, no CDN, no npm, no minified or vendored blob. Any future library needs its own register entry and approval.
- **Path safety.** The swap reuses `real_dir`, `owned_private` and `secure_dir`. It never acts recursively through symlinks and never crosses a filesystem (`--one-file-system`). The reserved `modules/` is untouched.
- **No secrets or customer data** in client code, tests, screenshots or logs. Browser runs use the synthetic crm-dev data and the synthetic `@example.test` users only. Screenshots are taken only of synthetic records.
- gitleaks runs on the candidate. DevSecOps reviews AC1 rules, the swap's TOCTOU ordering and the CSP result of AC6(d).

## 8. Roles, skills and evidence paths

| Role | Executes | Independent criterion (PASS only if) |
|---|---|---|
| Engineer | implements §4 in the WO worktree; runs the unit suite in the sandbox | every AC1–AC5, AC7 and AC9 test exists, is mutation-sensitive (one deliberate break per rule fails), and nothing outside §4 changes |
| Auditor | reviews the diff against §4, §5 and AC10; checks the F1–F8 claims against the image facts recorded here | the allowlist holds exactly; docs are truthful; no behavioural change to existing paths beyond §3 |
| Tester | re-runs the unit suite on the PL manifest-verified snapshot (CRM-TEST-001 §6b pattern, no specialist Git); reviews the orchestrator host and browser records | every AC is evidenced on the **same unchanged candidate**; AC6 artifacts show a, b, c, d and e explicitly |
| DevSecOps | §7; AC1 rules; the swap ordering; release integrity (AC9); CSP and console evidence | no path, supply-chain or secret finding at blocking level |

- Engine logs: `/home/forgev2-pl/.local/state/forgev2/records/3b6369e4f8e78d83/CRM-CLIENT-001/` (engine-owned; the records directory holds only `REPORT.md` and `prompts/*.md`).
- PL evidence: `/home/forgev2-pl/crm-evidence/CRM-CLIENT-001/` (host and browser records, manifests), indexed by `CRM-CLIENT-001.sha256`.
- **Limit: four executions per specialist, including the first.** This is a hard maximum. An exhausted limit is FAIL, escalated to CGPT.

## 9. Real-browser execution plan

1. **Target:** the synthetic **crm-dev** stack only, never beta. The PL deploys the candidate into crm-dev with `deploy_custom.sh dev`, under this WO's approval. Before that it takes `backup.sh dev`, and after the run it restores the pre-run `client/custom/src`.
2. **Who runs it:** the orchestrator (root prepares, browser runs as a non-root user). Sandbox specialists have no Docker or LAN access. The Tester independently reviews the recorded artifacts and may request one re-run within its execution limit.
3. **Tool (CL-D2, open):** proposed, a pinned Playwright Python container image referenced **by digest**. It would be recorded in `EXTERNAL_CODE_REGISTER.yaml` as a test-only component, run with `--network` limited to reaching crm-dev's loopback and LAN bind, and with no host mounts except an evidence output directory. The alternative is that CGPT names another approved browser. **Without a decision, AC6 cannot run and the WO is BLOCKED at that step.**
4. **Recorded artifacts:**
   - screenshots before and after each journey;
   - the console log;
   - CSP reports;
   - the network list of `client/custom` requests with `r` values;
   - the appTimestamp before and after;
   - the sha256 manifest.

   No credentials appear in artifacts. Synthetic test users get passwords via env from a root 0600 file, never in argv.
5. **Journeys:**
   - J1: log in, then canary resolution (AC6a/b);
   - J2: change the canary, redeploy, then a fresh load (AC6c);
   - J3: CSP and console (AC6d);
   - J4: regression screens (AC6e).

## 10. Repository and workspace

`/srv/CRM/main` (canonical) → `forge-start --wo CRM-CLIENT-001 --base main --known-commit <approved-docs-merge SHA>`. The worktree is `/srv/CRM/worktrees/CRM-CLIENT-001`, on branch `forge/CRM-CLIENT-001`. The PL and specialists are `forgev2-pl` under the engine sandbox. Engineer code never runs as the PL or as root. The host procedure runs tests as `nobody` from `git archive` copies.

## 11. Entry gates, stop conditions and reporting

| Gate | Requirement | State |
|---|---|---|
| G1 | CGPT exact-version approval of this WO (path and commit) on Issue #59 | open |
| G2 | **Sandbox entry gate for this WO.** Engine identity re-verified 2026-11-13 and unchanged from the CRM-TEST-001 annex §7: ForgeV2 `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`; Claude 2.1.317 sha256 `eb224419…7eb0`; bwrap 0.12.0-1~deb13u1 sha256 `573236e5…985f`; `forgelib.py` sha256 `6a7d587a…dc55`; only ignored entry is the accepted `__pycache__/forgelib.cpython-313.pyc` sha256 `1e456d81…52c1`. CRM-CLIENT-001 adds **no** new sandbox capability (no network, no Docker inside the sandbox); Docker and browser steps are orchestrator-run. CGPT must accept that this applies to CRM-CLIENT-001. | open (evidence ready) |
| G3 | CL-D2 browser component decision | open |
| G4 | Docs merge of this WO; its merge SHA becomes `--known-commit` | open |
| G5 | Preflight at dispatch: main unchanged or compatibly advanced; crm-dev synthetic and backed up; beta metadata snapshot recorded | open |

**Stop immediately** for:

- any need outside §4;
- any change to `client/custom/modules`;
- a failed security or entry gate;
- a candidate that changes after review;
- any contact with beta, Salesforce or real data;
- an exhausted execution limit;
- an unverifiable 10.0.12 behaviour (for example, F8 turns out false).

After four PASS verdicts on the same candidate, the PL returns READY_FOR_CGPT with:

- the exact head;
- the patch sha256;
- the evidence index.

The WO does **not** deploy to beta. A beta release of this mechanism needs its own operator authorisation.

## 12. Open decisions

- **CL-D1 (PL proposal, for CGPT):** CRM-owned client code lives under `client/custom/src/` only, deployed as a whole-tree swap. The reserved `client/custom/modules` is never managed by the CRM. Namespacing as `src/crm/…` keeps future module trees (for example `src/wip/…` for CRM-D021) separable.
- **CL-D2 (CGPT/Matt):** the approved real-browser component and where it runs (§9.3).
- **CL-D3 (CGPT):** confirm that orchestrator-run browser evidence plus independent Tester review satisfies the FOUNDRY "independent real-browser journeys" rule for this WO.
- **CL-D4 (recorded):** baking `client/custom` into a `crm-espocrm` image is deferred to PBI-016. No PBI-016/017 acceptance is claimed.
