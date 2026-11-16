# Release bundle (CRM-007, PBI-016)

A release is a verified bundle of one accepted commit. crm-beta is installed from it, never from a Git checkout ([BETA.md](BETA.md)).

## Build

```sh
scripts/release.sh <commit> [outdir]       # on the build host, from a checkout of this repository
sha256sum <outdir>/crm-release-<short>.tar.gz
```

- The commit must be reachable from `main`, which means accepted.
- The output is `crm-release-<12-hex>.tar.gz`: the `git archive` of the commit under `crm-release-<short>/`, plus `RELEASE.json`.
- **Excluded:** `.forge/**` (the delivery records; PL decision under CRM-D017). `RELEASE.json` records this as `"excluded": [".forge/"]`, and `verify` refuses a bundle that does not record it or holds anything under `.forge/`. The delivery records stay listed by commit SHA (below).
- `RELEASE.json` holds:
  - the commit;
  - the image digests from the commit's `security/EXTERNAL_CODE_REGISTER.yaml`;
  - the sha256 of every file;
  - the latest commit of each CRM-002 to CRM-006 delivery record (`.forge/<WO>*/REPORT.md`), or `null` where none exists. `"CRM-002": null` is expected: CRM-002 has no ForgeV2 REPORT in `.forge/` (PL decision, CRM-007 r4);
  - `excluded`: `[".forge/"]`.
- The build is reproducible:
  - members are sorted and owned by `0:0`, with the commit time;
  - gzip has no name and mtime 0;
  - two builds of the same commit are identical byte for byte (`cmp`).

## Verify

`python3 scripts/release.py verify <bundle> [--sha256 <hex>]`.

**Anchoring.** `RELEASE.json` is inside the bundle and unsigned: anyone who changes a file and re-computes `RELEASE.json` gets a bundle that is internally consistent. Only the bundle's sha256 from the release record (`sha256sum` on the build host) anchors it. Without `--sha256`, `verify` is for inspection only and prints a warning that the bundle is NOT ANCHORED. `--sha256` must be exactly 64 lower-case hex digits; `deploy_release.sh` always requires it.

It refuses:
- trailing or invalid gzip;
- members outside the top directory, links, devices, or setuid or world-writable modes;
- a member set that differs from `RELEASE.json`;
- any file digest mismatch;
- register digests that differ from `RELEASE.json`;
- an image digest in `deploy/compose.json`, `deploy/beta/compose.json` or `deploy/beta/restoretest/compose.json` that is not in the register. The edge entry `haproxy@sha256:…` carries no tag, so for it only the digest is checked;
- a bundle sha256 that differs from `--sha256`;
- `RELEASE.json` without `"excluded": [".forge/"]`, or any member under `.forge/`.

`python3 scripts/release.py verify-tree <dir> <bundle> --sha256 <hex>` re-verifies the anchored bundle and then refuses unless `<dir>` holds exactly its files: every file listed in `RELEASE.json` plus `RELEASE.json` itself, byte for byte, with no extra, missing or changed file, no extra directory and no link or special file. Like `verify` for tar members, it also refuses any file or directory that is setuid, setgid or sticky, or writable by group or others.

## Deploy

`scripts/deploy_release.sh beta <bundle> --sha256 <hex> [--upgrade]`. `--sha256` is mandatory: if it is missing or malformed the script stops before step 1, with no docker call and no deploy directory. It verifies the bundle before anything else, using the `release.py` of the checkout that runs it, not the one inside the bundle:
1. it copies the bundle into a root-only private temp file (directory `0700`, file `0600`);
2. computes the sha256 of that copy and compares it with `--sha256`;
3. verifies that same copy (`release.py verify --sha256`);
4. unpacks from that copy only;
5. re-checks every unpacked file against `RELEASE.json` (`release.py verify-tree`) before moving it into `/srv/CRM/deploy/<short>`.

With `--upgrade` and an existing `/srv/CRM/deploy/<short>`, that directory is checked the same way, and any difference or extra file refuses the deploy. Then it deploys from the unpacked, read-only copy (operator steps in [BETA.md](BETA.md)). Each step is a shell function. `tests/unit/test_beta.py` sources the script, which runs nothing when sourced, and tests the steps with stubbed `docker` and `python3`.

## Client browser code (CRM-CLIENT-001R)

CRM-owned browser code lives only in `client/custom/src/` (AMD modules; no `import`/`export`, no remote URLs, no `eval`, no storage APIs). `client/custom/modules` is EspoCRM's reserved extension path and never exists in Git. The only module today is the **canary** `crm/release-canary.js`, loaded as `custom:crm/release-canary`. It is referenced by no metadata, layout, navbar or translation, so no user sees any change.

- **Release.** A release is the `git archive` of a commit, so a tracked `client/custom/src/` is bundled and checked like every other file: `release.py verify --sha256` lists the canary in `RELEASE.json` with its sha256, and `verify-tree` refuses a file added under `client/custom/src`. `release.py` itself is unchanged.
- **Deploy.** `scripts/deploy_custom.sh dev|beta` deploys `custom/Espo/Custom` and `client/custom/src` with the same stop, secure, stage and rename discipline ([BUILD.md](BUILD.md) §7.2), then runs `up --wait`, `clear-cache`, `rebuild` and `update-app-timestamp` in `crm-app` as `www-data`. Files removed from Git disappear from the runtime.
- **Cache-bust.** Outside developer mode EspoCRM versions client module URLs with `appTimestamp` (`?r=<appTimestamp>`). `clear-cache` does not change it; only `update-app-timestamp` (or an upgrade or a migration) does. The value is in whole seconds, so the script requires a strictly greater value, retries once after 1 s and otherwise fails. Leave at least 2 s between deploys. With the stack stopped, the script prints that the client cache-bust was skipped and how to complete it.
- **Failure after the swap.** The previous trees are kept as `.Custom.old-<stamp>` and `.src.old-<stamp>` until every step has succeeded. On the first failed step the script prints `FAILED STEP: <step>`, never the success line, and exits with a step-specific code, then recovers: it stops `crm-app` and `crm-daemon`, moves the new trees to `.Custom.failed-<stamp>` and `.src.failed-<stamp>` (kept for inspection), puts the previous trees back, starts the stack and runs `clear-cache`, `rebuild` and `update-app-timestamp` again, and prints `RECOVERED: previous customisation restored`. If recovery fails it stops the stack and prints `RECOVERY FAILED: stack left stopped`, leaving both trees in place.

  | Exit code | Meaning |
  |---|---|
  | 20 | a swap step failed (moving a live tree aside, or installing a staged tree, for either tree). **Both** trees are put back, so the previous `custom/Espo/Custom` and `client/custom/src` are live and unchanged. Neither staging directory remains. The stack is left stopped, and no success line is printed |
  | 21, 22, 23, 24 | `up`, `clear-cache`, `rebuild`, `update-app-timestamp` failed, and recovery succeeded |
  | 41, 42 | recovery failed to stop the stack, or to put the previous trees back |
  | 43, 44, 45, 46 | recovery failed at `up`, `clear-cache`, `rebuild`, `update-app-timestamp` |
  | 47 | interrupted by INT, TERM or HUP after the first swap; the same recovery ran and ended `RECOVERED` |
  | 48 | interrupted by INT, TERM or HUP before the first swap; staging was removed, the previous trees are untouched and the stack is left stopped |

  After `RECOVERY FAILED`, inspect `.src.old-*`, `.Custom.old-*` and `.*.failed-*`, then run `restore.sh dev` of the last backup, `scripts/up.sh dev` and the cache-bust below.
- **Interruption.** Once the stack has stopped, the script traps INT, TERM and HUP. The line `INTERRUPTED: <signal>` is printed, and then either exit 48 (before the first swap) or the recovery of the previous bullet (exit 47, or 41 to 46 if recovery fails). If the stack was not running, recovery restores the trees and leaves it stopped. A signal that arrives after every step has succeeded no longer starts a recovery. A `kill -9`, a host reboot or a lost shell cannot be trapped: use the manual recovery of the real-browser procedure below, or `restore.sh dev` of the last backup followed by `scripts/up.sh dev` and the cache-bust.
- **Leftovers.** The names `.Custom.deploy-*`, `.Custom.old-*` and `.Custom.failed-*` (in the runtime `custom/Espo`) and `.src.deploy-*`, `.src.old-*` and `.src.failed-*` (in the runtime `client/custom`) are working trees of a deploy. Each deploy installs exactly the repository tree as the live tree. It never reads from, moves or deletes a leftover of an earlier run, and prints `LEFTOVER: <name>` on stderr for each one it sees. Release bundles are built from Git and never contain them. A stale `.src.*` directory is not loaded by EspoCRM, but it is static content below `client/custom`, so remove it. **Operator removal procedure:** after a successful deploy and a check that `crm-app` serves the expected release, list the names (`ls -A <runtime>/custom/Espo <runtime>/client/custom`), inspect any `.failed-*` tree you still need, then delete each leftover with `rm -rf --one-file-system -- <full path>` as root, one at a time, never through a symlink. Never touch `client/custom/modules`.
- **Backup, restore, rollback.** `backup.sh` and `restore.sh` already cover `client/custom` as a whole. Restoring gives back `client/custom/src` byte for byte, but it does not advance `appTimestamp`, so run the cache-bust after it:

  ```sh
  scripts/restore.sh dev <backup>
  docker compose -p crm-dev -f deploy/compose.json --env-file /srv/CRM/runtime/dev/env exec -T -u www-data -w /var/www/html crm-app php bin/command update-app-timestamp
  ```

  (Use `scripts/up.sh dev` first if the stack is down.) Rolling back is a deploy of the earlier commit: files that exist only in the later commit are removed, and the deploy ends with its own cache-bust.
- **Not PBI-016.** This keeps the deploy-into-runtime model (the CRM-D017 deviation) and extends it to `client/custom/src`. It claims no baked-image or clean-host acceptance and does not implement CRM-PBI-016.

### Real-browser procedure (operator-run, test-only)

`tests/browser/` holds a hardened Playwright runner. **Nothing in it runs on the host, in a runtime or in a release.** This repository change alone proves the offline parts (static policy, the deploy and recovery logic with a fake `docker`, the verifier and the sanitiser). The real-browser run has **not** been made; it is done by the operator and then judged independently (CRM-CLIENT-001R-BA).

- **Components** (register entries `playwright-python-browser-runner`, `chrome-for-testing-stable`, `grype-cl-d5-scanner`, all `test-only, operator-run`):
  - the official Playwright Python image, pinned by digest, used only as the operating-system and dependency base. Its bundled Chromium is never executed;
  - exactly two hash-locked wheels (`tests/browser/requirements.lock`: playwright 1.65.1, greenlet 3.5.6), installed offline into tmpfs inside the container. The version check uses `importlib.metadata`: the wheel has no module version attribute;
  - Chrome for Testing Stable 157.0.8103.78 (the version Playwright 1.65.x was tested against), hash-pinned, mounted read-only, launched with `executable_path`. Before any Playwright driver or browser process starts, the runner checks the binary's sha256 and that neither the binary nor the bundled Node driver has a missing library (`libatomic.so.1` included), and records the result; any failure stops the run with nothing launched. A compatibility probe must then pass before any journey.
- **Hardening and isolation.** The container runs as uid 65534 with a read-only root, all capabilities dropped, `no-new-privileges`, no Docker socket and no host network. It sits alone on a per-run internal network with `crm-app` and no host-side address. `probe_isolation.py` runs first and is a hard gate: no default route, `crm-app` reachable, and the database, the other `crm-app` address, the host, loopback, beta, a public address and public DNS all unreachable. This isolation covers direct network paths only: anything the synthetic test user can do through `crm-app` remains possible, which is acceptable only because crm-dev holds synthetic data.
- **Run.** The operator takes a backup and a baseline snapshot (D0), then drives the steps with the control files described at the top of `journeys.py` (`ready-<step>` from the runner, `go-<step>` with the `appTimestamp` read in `crm-app` from the operator): D1 deploys the candidate, D2 a transition tree whose only change is the v2 canary (`tests/browser/fixtures/canary-transition/v2`), D3 the candidate again (rollback), D4 a deploy made to fail at `update-app-timestamp` (recovery expected), D5 `restore.sh dev` of the D0 backup followed by the cache-bust. One browser context lives through all steps. J1 to J4 must load contract 1, 2, 1, 1 with a new network fetch and a strictly greater `r` each time; J5 must find the canary absent and the regression screens (login, Account and Enquiry list and detail, Stream) equal to J1, which is the D0 appearance because the canary is unreferenced. No journey may produce a CSP violation or a console error outside the J5 probe.
- **Evidence and public summary.** The raw package (annex B6 layout) stays in the restricted evidence store and never enters Git. `python3 tests/browser/verify_evidence.py <package> --candidate-root <candidate> --expect-candidate <sha>` recomputes every verdict from the raw files (it ignores the runner's own `result.json` verdicts) and does no network I/O. `--public-summary <dir>` writes `public-summary.json` and `EVIDENCE.md` with only public-safe fields (hashes, versions, verdicts, counts, relative paths) and **refuses**, naming the item class, if any address, host name, URL, port, container or network id, env name or value, non-`example.test` e-mail, outside path, free text or the run's browser credential (given to it through the environment only) would be emitted. Only that summary may be committed.
- **Cleanup (always run; a failure is a FAIL).** Remove the browser container; disconnect `crm-app` from the test network and remove the network; restore the crm-dev env file from its byte copy and compare it (`cmp` and sha256); restore the crm-dev state if a deploy left it changed and recreate `crm-app` with `scripts/up.sh dev`; remove the PATH wrapper, the credential file and the temporary directories; write `cleanup.json`. The package must show: env file identical; no `crm-client001r-*` container or network; `crm-app` on the dev network only and healthy; the beta directory metadata, file hashes and container ids unchanged.
- **Manual recovery of an interrupted run** (host reboot, killed shell), from the operator's `state.log` alone: `docker rm -f` the browser container; `docker network disconnect -f` the test network from `crm-app`, then `docker network rm` it; copy the saved env file back over the crm-dev env file with `cp --preserve=mode,ownership`, then `cmp` and sha256; if any deploy was made or `.Custom.old-*`, `.src.old-*` or `.*.failed-*` trees exist, stop `crm-app` and `crm-daemon`, run `restore.sh dev` of the recorded backup, then `up.sh dev` and the cache-bust above; run every cleanup check and record `manual-recovery.json`. An interrupted run is never evidence: a new run id is needed.
