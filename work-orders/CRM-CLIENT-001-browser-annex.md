# CRM-CLIENT-001 annex B: real-browser runner, isolation and evidence (v1.1)

- **Status:** part of the CRM-CLIENT-001 v1.1 DRAFT. It is approved only together with the WO, by commit.
- **Preparation constraints (CGPT, 2026-11-16).** During preparation nothing was pulled, installed or run, and no Docker network was changed. Every value below comes from public registry or PyPI **metadata**, or from read-only host inspection.
- **Values verified at execution.** Each item marked **VERIFY** must be re-checked by the operator at execution time. A mismatch is a stop.

## B1. Component selection

| Item | Value | Provenance |
|---|---|---|
| Image | `mcr.microsoft.com/playwright/python:v1.64.1-noble` (official Microsoft Playwright for Python image, Ubuntu 24.04) | MCR tag list, 2026-11-16 |
| Multi-arch index digest | `sha256:330d401ae23c905896a0c26c66c36fc971b621519e7b11b435a8328d7bf6e031` (OCI image index) | `Docker-Content-Digest` header; equals sha256 of the fetched index body |
| linux/amd64 manifest digest (DOCKER1 is x86_64) | **`sha256:7d030ac0638b279ecc72493f8b6706fecef80a893679a23b02f912905c4915c0`** (also tag `v1.64.1-noble-amd64`) | index entry; equals sha256 of the fetched manifest body |
| linux/arm64 manifest digest (not used) | `sha256:e731c79aba1c9d777b77ed85f0c0111531cbaa24ecba90fe65ad7b7438e89c40` | index entry |
| amd64 config blob | `sha256:b6862d3036a770b5c0e8a0987e9546dc1844f10ba70925f746e7a44ca84660c0`; created 2026-10-22T17:51:03Z; 4 layers, 1,032,349,420 bytes compressed | blob fetched, sha256 verified |
| Image defaults | `User` unset (root); `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`; `CMD ["/bin/bash"]`; no entrypoint; the build creates the user `pwuser`; `/ms-playwright` is `chmod -R 777` | config history |
| Python | Ubuntu noble `python3` 3.12 (the history removes `/usr/lib/python3.12/EXTERNALLY-MANAGED`); `pip` from `get-pip.py` at build time | config history |
| **Playwright Python package** | **Not present in the final image.** The build installs the wheel only in a temporary venv (`/ms-playwright-agent/venv`), uses it to run `playwright install --with-deps`, then deletes that directory. This confirms the CGPT statement | config history, last RUN step |
| Browser builds | Installed by Playwright 1.64.1 into `/ms-playwright`. They therefore match the 1.64.1 driver below | same step |

**Why v1.64.1 and not v1.65.x.** 1.64.1 was published on 2026-10-22, more than three weeks before preparation. 1.65.0, 1.65.1 and 1.65.2 are less than a week old. The older release with no open regressions is chosen. Upgrading needs a register change.

## B2. Python dependency lock (no unpinned installation)

The file `tests/browser/requirements.lock` (new, in the §4 allowlist) holds exactly the following entries:

| Distribution | File | sha256 (PyPI) | Published |
|---|---|---|---|
| playwright 1.64.1 | `playwright-1.64.1-py3-none-manylinux1_x86_64.whl` | `577b8d88778c245cfbd145ae17cf53044f084b1b46c55c69081d4069d56057e2` | 2026-10-22 |
| pyee 13.0.0 (playwright requires `pyee>=13,<15`) | `pyee-13.0.0-py3-none-any.whl` | `48195a3cddb3b1515ce0695ed76036b5ccc2ef3a9f963ff9f77aec0139845498` | 2025-03-17 |
| greenlet 3.5.6 (requires `greenlet>=3.1.1,<4`) | `greenlet-3.5.6-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl` | `975736b002ed080d124cf81a79cb7e05cb26d6b3f5c7a7b651c0fcce70353aa1` | 2026-09-14 |
| typing-extensions 4.16.0 (required by pyee) | `typing_extensions-4.16.0-py3-none-any.whl` | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` | 2026-07-02 |

**Install method (VERIFY at first run).**

1. **Download (operator, as root, on the host).** The four wheels are fetched with `curl` from the `files.pythonhosted.org` URLs that the PyPI JSON lists for these files. The PyPI JSON and wheel URLs are recorded in the evidence. The wheels go into a fresh root-owned directory, and each file's sha256 is checked against the lock. Any mismatch stops the run. Nothing from the wheels is executed on the host.
2. **Install (inside the container, offline).** The command is `python3 -m pip install --no-index --find-links /wheels --require-hashes --only-binary=:all: --no-deps --target /tmp/pydeps -r /work/tests/browser/requirements.lock`, followed by `PYTHONPATH=/tmp/pydeps`. The installation goes to a tmpfs, so nothing persists.
   - `--no-deps` together with the complete lock means that nothing outside the lock is resolved.
   - The container has no route to PyPI (B4), so any attempt to fetch from the network fails closed.
3. **Driver and browser check.** The run asserts the following and records them:
   - `playwright.__version__ == "1.64.1"`;
   - the Chromium executable under `/ms-playwright` exists;
   - the browser version reported by Playwright.

**External code register (§4 allowlist).** The run adds one candidate entry to `security/EXTERNAL_CODE_REGISTER.yaml`, `playwright-python-browser-runner`. It records:
- the image tag, the index digest and the amd64 digest;
- the four wheels with their hashes;
- licences: Apache-2.0 (Playwright), MIT (pyee, greenlet), PSF-2.0 (typing-extensions), plus the Ubuntu, Chromium and Firefox licences inside the image;
- `usage: test-only, orchestrator-run, never in any release bundle or runtime`;
- `approval:` set to whatever CGPT records.

`release.py verify` already refuses image digests that are not in the register only for the three compose files. The browser image appears in no compose file, so release bundles are unaffected.

## B3. Container hardening (exact invocation template)

The orchestrator runs the container. Root prepares it; the processes inside run as uid/gid 65534.

```
docker run --rm --pull never \
  --name crm-client001-browser-<run> \
  --user 65534:65534 \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=1g \
  --cap-drop ALL --security-opt no-new-privileges=true \
  --pids-limit 512 --memory 2g --shm-size 1g \
  --network crm-client001-browser-<run> --ip <browser-ip> \
  --env HOME=/tmp --env PYTHONDONTWRITEBYTECODE=1 \
  --env CRM_BROWSER_BASE_URL=http://<app-ip> \
  --env-file <root-0600-tmp-file> \
  --mount type=bind,src=<archive-copy-of-candidate>,dst=/work,readonly \
  --mount type=bind,src=<verified-wheelhouse>,dst=/wheels,readonly \
  --mount type=bind,src=<evidence-out>,dst=/evidence \
  mcr.microsoft.com/playwright/python@sha256:7d030ac0638b279ecc72493f8b6706fecef80a893679a23b02f912905c4915c0 \
  /bin/bash /work/tests/browser/entry.sh
```

- `<root-0600-tmp-file>` holds only the synthetic `@example.test` test-user credentials; it is created for the run and deleted afterwards, and is never in argv or evidence.
- **No Docker socket, no host networking, no privileged mode, no added capabilities, no device mounts.** The only writable paths are `/tmp` (tmpfs) and `/evidence`. The default seccomp and AppArmor profiles apply (both are listed in `docker info`).
- **Chromium sandbox.** Playwright launches Chromium with `chromiumSandbox: false` by default. Under `--cap-drop ALL` and the default seccomp profile, Chromium's own namespace sandbox is unavailable. The isolation boundary is therefore the container plus the network design in B4. The page under test is only the synthetic crm-dev application. This limitation is recorded for DevSecOps.
- **Image acquisition (operator gate, not preparation).**
  1. `docker pull mcr.microsoft.com/playwright/python@sha256:7d030ac0…15c0`.
  2. `docker image inspect` must show that RepoDigest and the expected config ID `sha256:b6862d30…60c0`.
  3. `--pull never` thereafter.
  4. The image is removed when the WO closes. No permanent infrastructure is left.
- **`<evidence-out>`** is a fresh root-created directory, `/tmp/crm-client001-browser-<run>/out`, owned by 65534 with mode 0700. Root copies it into the PL evidence store after the run (B6).
- **`<archive-copy-of-candidate>`** is the `git archive` copy of the exact candidate (or of a B5 transition tree), root-owned and read-only. Engineer-authored code (`tests/browser/*.py`, `entry.sh`) therefore runs **only** inside this container as uid 65534. It never runs as root, as the PL, or on the host.

## B4. Network isolation (A2)

**Verified host facts (read-only, 2026-11-16).**

- crm-dev runs as Compose project `crm-dev`. `crm-dev_crm-net` is a bridge on `172.16.10.0/24` that is **not** internal. The database `crm-dev-crm-db-1` is on it, so the browser must **not** join it.
- crm-beta runs on a separate network, `crm-beta_crm-beta-net`. Its app is published on `127.0.0.1:8280`, and its edge uses host networking.
- crm-dev's Apache admits only loopback and `CRM_ALLOWED_SOURCES` (`deploy/apache/crm-access.conf`). A browser on any new network gets **403** unless its exact address is admitted.
- `check_access.py dev` accepts sources that are RFC 1918, /16 or longer, and do not overlap crm-net.
- The Docker Engine is 24.0.5. Its binary contains the bridge driver option `com.docker.network.bridge.inhibit_ipv4` (VERIFY that it is effective).

**Design: a per-run, test-only internal network.**

1. **Create the network.** The command is `docker network create --driver bridge --internal --subnet 172.31.250.0/29 -o com.docker.network.bridge.inhibit_ipv4=true -o com.docker.network.bridge.enable_ip_masquerade=false crm-client001-browser-<run>`.
   - `--internal`: no default route, no NAT and no published ports.
   - `inhibit_ipv4`: the host-side bridge gets **no** IPv4 address, so the container cannot reach any host listener, including the beta port on 127.0.0.1 (which is the container's own loopback anyway) or the LAN address.
   - The subnet is checked first against `docker network ls` and `ip route` to confirm it is unused.
2. **Admit the browser.** The browser's single address, `172.31.250.2/32`, is appended **temporarily** to crm-dev's `CRM_ALLOWED_SOURCES` in `/srv/CRM/runtime/dev/env`. The operator first saves a byte copy of the env file. `check_access.py dev` must pass; Matt's existing bind-only `172.16.10.1/32` entry is handled exactly as the recorded crm-dev procedure requires. crm-app is then recreated through `scripts/up.sh dev`.
3. **Attach crm-app.** The command is `docker network connect --ip 172.31.250.3 crm-client001-browser-<run> crm-dev-crm-app-1`, so crm-app is temporarily on this network in addition to crm-net. crm-db and crm-daemon are **not** attached. crm-app does not forward IP traffic between its interfaces (VERIFY: `/proc/sys/net/ipv4/ip_forward` inside crm-app is 0).
4. **Prove isolation before any journey.** `tests/browser/probe_isolation.py` runs in the same container, but it is a separate step from the journeys. The run must record the following, and each is a hard gate:
   - `ip route` and `/etc/resolv.conf` (via Python `/proc/net/route`) show only `172.31.250.0/29`, with no default route;
   - TCP to `172.31.250.3:80` succeeds;
   - each of the following **fails** (connect error or timeout within 3 s):
     - crm-dev db `172.16.10.x:3306` (its address is read from `docker inspect` by the operator and passed in as data);
     - crm-dev app on crm-net `172.16.10.3:80`;
     - host LAN `<dev bind IP>:8180` and `:8290` (beta);
     - `127.0.0.1:8280` (beta, inside the container namespace);
     - the crm-beta network gateway and its app container address;
     - a public address on 443;
     - DNS resolution of a public name.

   **Any unexpected success stops the run before the journeys, and the WO reports BLOCKED. Host networking or a wider network is never used as a fallback.**
5. **Teardown, always run, including on failure.**
   1. Disconnect crm-app from the network.
   2. Remove the network.
   3. Restore the saved env file byte for byte, comparing with `cmp`.
   4. Recreate crm-app through `up.sh dev`.
   5. Record `docker network ls`, which must show no leftover network.

   No firewall rule is created or changed at any point (standing rule: no iptables, ufw or nftables).

**Residual limitation (for DevSecOps and CGPT).** Steps 2 and 5 briefly change crm-dev's runtime configuration and recreate crm-app, which is a synthetic-only stack. This is an operator action under the WO's approval. It is not a change to the repository or to beta.

## B5. Immutable canary versions and the cache-bust transition (A3)

- **Approach: committed synthetic fixtures** (not two ordered engineering commits). Ordered commits would cost an extra Engineer execution per fix round against the four-execution maximum. Fixtures keep every deployed byte inside **one** reviewed candidate `F`.
  - `client/custom/src/crm/release-canary.js` in `F` declares **contract 1**.
  - `tests/browser/fixtures/canary-transition/v2/crm/release-canary.js` in `F` is identical except that it declares **contract 2**. AC1 checks that the two files differ only in that value.
- **Transition tree `T`.** The operator takes `git archive F` and replaces only `client/custom/src/crm/release-canary.js` with the v2 fixture blob, then:
  - writes the manifest of `T`;
  - verifies that every file in `T` equals the blob of `F` at the same path, except that the one replaced path equals the blob `F:tests/browser/fixtures/canary-transition/v2/crm/release-canary.js`.

  `T` is never committed, and `deploy_custom.sh` gains no seam: `T` is deployed with `T`'s own `scripts/deploy_custom.sh`, which is `F`'s blob.
- **Deployment order and assertions** (one browser profile is kept across D1 to D3; a "fresh load" means a new page navigation, with no manual cache clear):

  | Step | Deploy | Expected browser result |
  |---|---|---|
  | D0 | backup `backup.sh dev`; record the appTimestamp `a0` | none |
  | D1 | `F` | J1: contract 1; resource URL `…/client/custom/src/crm/release-canary.js?r=a1` with `a1 > a0`; `a1` equals the appTimestamp read in crm-app |
  | D2 | `T` (≥2 s after D1) | J2: contract 2; `r=a2`, `a2 > a1`; the browser fetched the new URL (network log), not a cached copy |
  | D3 | `F` again (rollback, ≥2 s after D2) | J3: contract 1; `r=a3`, `a3 > a2` |
  | D4 | failure injection (B7) | J4: as specified in B7 |
  | D5 | `restore.sh dev` of the D0 backup; cache-bust | J5: the canary is absent (resolution fails cleanly with no console error outside the probe); `a5 > a4`; regression screens match D0 |

- **appTimestamp resolution.** `appTimestamp` is `time()`, in whole seconds (`DataManager::updateAppTimestamp`).
  - `deploy_custom.sh` reads the value before and after `update-app-timestamp`. If the after value is not strictly greater, it waits one second and runs `update-app-timestamp` once more. If the value is still not greater, it fails with `FAILED STEP: update-app-timestamp (not advanced)`.
  - The operator also waits at least 2 s between deploys.
  - The browser asserts strict increase from the network URLs. Equality is a FAIL.

## B6. Evidence package and its route to the Tester (CL-D3, Phase B)

**Contents of the evidence for each run `<run>`.** Everything is written by the container to `/evidence`, except where marked *operator*.

| File | Content |
|---|---|
| `invocation.txt` | *operator*: the exact docker, network and deploy commands, with digests. Credentials are referenced only by file descriptor and never included |
| `identity.json` | *operator*: candidate SHA; the `T` manifest sha256; the snapshot manifest sha256; the image RepoDigest and config ID; the wheel hashes; the Docker version; `docker inspect` of the browser container, restricted to Mounts, NetworkSettings, HostConfig.CapDrop, SecurityOpt, ReadonlyRootfs, User and Privileged (no Env) |
| `isolation.json` | each probe target, the expected and actual results, and the route table |
| `timestamps.json` | `a0`..`a5` as read by the operator in crm-app, and the `r` values observed by the browser |
| `journeys/<J>/result.json` | for each assertion: id, AC, expected, observed, pass/fail |
| `journeys/<J>/requests.jsonl` | every request (URL, method, status, from-cache flag, response sha256 for `client/custom` resources) |
| `journeys/<J>/console.jsonl`, `csp.jsonl` | every console message, page error and `securitypolicyviolation` event |
| `journeys/<J>/trace.zip` | the Playwright trace (DOM snapshots, network, console). It can be opened offline |
| `journeys/<J>/*.png` | screenshots of synthetic records only |
| `SHA256SUMS` | *operator*: covers every file above |

**Route to the Tester (no Docker, network or Git for specialists).**

1. Root copies `<evidence-out>` into `/srv/CRM/worktrees/.forge-scratch/CRM-CLIENT-001/browser-<sha12>-<run>/`, which is the WO's permitted scratch location, the same mechanism as the CRM-TEST-001 §6b snapshot. It sets ownership to `forgev2-pl`, read-only. gitleaks (`dir --redact`) must report it clean before it is used.
2. The sha256 of `SHA256SUMS` and the run id are written into the Tester prompt. The Tester checks them first.
3. The Tester runs the candidate's `tests/browser/verify_evidence.py` **in the sandbox, from its own copy of the PL snapshot**. This offline verifier only reads files. It recomputes every AC6 verdict independently from the raw `requests.jsonl`, `console.jsonl`, `csp.jsonl`, `timestamps.json` and `isolation.json`, and does not trust `result.json`. The Tester may also unpack and inspect `trace.zip` and the screenshots.
4. The Tester issues its own PASS or FAIL for each journey. It can **challenge** the evidence by recording a finding `browser-rerun:<journey>:<reason>`. The PL then performs **one** bounded repeat under a new run id (same candidate, same procedure), and that repeat goes to the Tester's next execution, which counts toward the four-execution maximum. The PL cannot overrule a Tester FAIL.

A screenshot alone is never accepted as proof of any assertion.

## B7. Failure after a successful swap (A4)

`deploy_custom.sh` behaviour (tested in the unit suite with fake docker; on crm-dev with the operator wrapper below):

1. **Swap.** `custom/Espo/Custom` and `client/custom/src` are both staged, then swapped. The previous trees are kept as `.Custom.old-<stamp>` and `.src.old-<stamp>` until every later step succeeds. If the second swap fails, the first is swapped back before exit.
2. **Post-swap steps** run in this order: `up --wait`, `clear-cache`, `rebuild`, `update-app-timestamp` (with the advance check). On the first failure the script:
   - prints `FAILED STEP: <step>` to stderr;
   - never prints the success line;
   - exits with a code specific to the step (documented);
   - **recovers**:
     1. stops crm-app and crm-daemon;
     2. moves the new trees aside as `.failed-<stamp>` and swaps the previous trees back;
     3. starts the stack and runs `clear-cache`, `rebuild` and `update-app-timestamp`, so browsers move to a new `r` and reload the previous code;
     4. prints `RECOVERED: previous customisation restored`.
   - If recovery itself fails, it stops crm-app and crm-daemon (controlled shutdown), prints `RECOVERY FAILED: stack left stopped`, and keeps both the previous and the failed trees for the operator.
3. **Unit tests (AC4b).**
   - A failure is injected at each of the four steps and at each recovery step.
   - Each test asserts the exit code, the stderr markers and the absence of the success line.
   - Each test checks the runtime tree contents byte for byte against the previous tree, and that the `.failed-*` tree is retained.
   - Each test checks the recorded docker call order.
4. **On crm-dev (J4).**
   - The operator prepends a test-only `docker` wrapper to `PATH`. The wrapper is written by the operator, recorded in `invocation.txt` and not part of the candidate. It passes every call to the real docker except `exec … bin/command update-app-timestamp`, which it makes fail once.
   - It then deploys `T` over `F`.
   - Expected results:
     - the script exits non-zero with `FAILED STEP: update-app-timestamp` and `RECOVERED`;
     - the browser loads contract **1** (the previous code);
     - `r` has advanced past the last value;
     - there are no console errors.
   - beta is never touched.

## B8. Tool decisions still needed

- **CL-D5 (vulnerability scanning).** No image or dependency vulnerability scanner is installed or approved on DOCKER1 (no trivy, grype, syft or docker scout). The proposal is that CGPT either approves a scanner pinned by checksum to run on the pulled image before first use, or records an accepted risk. The case for accepting the risk:
  - the runner is ephemeral and test-only, with no route anywhere except synthetic crm-dev (B4);
  - it is read-only and runs with no capabilities;
  - it handles no customer data.

  Secret scanning is covered: gitleaks runs on the candidate, on every evidence directory, and on the exported `/work` copy.
