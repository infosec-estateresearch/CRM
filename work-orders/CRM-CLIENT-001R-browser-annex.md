# CRM-CLIENT-001R annex B: real-browser runner, isolation, vulnerability gate, evidence and cleanup (v1.3)

- **Status:** part of the CRM-CLIENT-001R **v1.4** DRAFT (recovery of CRM-CLIENT-001; WO §0). It is approved only together with the WO, by commit. History: v1.1 is in commit `0fba12cf5395800d02db5801e4772506c849cb1a`. v1.2 is commit `793f69b04d860e3f82bbd39cbe08404f289ccbef`. v1.2 changes were B2.3, B3, B4, B6, B8 and B9.
- **v1.4 changes** (CGPT *CRM-CLIENT-001R Recovery Authorisation*, 2026-11-16):
  - B2 step 1 wording (R1);
  - B2.3 *Pre-launch* order and the Node-driver library check (R4);
  - B6 credential handling and B9.1 items 3 and 7 (R6, R4);
  - the identity is `CRM-CLIENT-001R` (R3).
- v1.3 changes (CGPT *CRM/WIP Delivery Mission*, 2026-11-16): the browser executable is now **Chrome for Testing Stable 157.0.8103.78** (B1, B2a, B3); the lock is **Playwright 1.65.1** (B2, B2.3); the scan covers the new browser (B8.4); evidence is published in **public-safe** form only (B6). WO §13 maps them.
- **Preparation constraints.** During preparation nothing was pulled, installed, scanned or run, and no Docker network was changed. The Chrome for Testing archives and the 1.65.1 wheel were downloaded only to compute hashes and were read as inert data.
  - Every value comes from public registry, PyPI, GitHub or OSV **metadata**, from read-only host inspection, or from reading the playwright wheel as inert data with `zipfile` (no code executed).
  - Each **VERIFY** item is re-checked by the operator at execution, and a mismatch is a stop.
- **Framework.** FOUNDRY `84fedf0a…` for the v1.2 decisions; `5f5e4a51…` is the provenance of v1.0–v1.1.

## B1. Component selection

| Item | Value | Provenance |
|---|---|---|
| Image | `mcr.microsoft.com/playwright/python:v1.64.1-noble` (official Microsoft Playwright for Python image, Ubuntu 24.04) | MCR tag list, 2026-11-16 |
| Multi-arch index digest | `sha256:330d401ae23c905896a0c26c66c36fc971b621519e7b11b435a8328d7bf6e031` | `Docker-Content-Digest` header; equals the sha256 of the fetched body |
| linux/amd64 manifest (DOCKER1 is x86_64) | **`sha256:7d030ac0638b279ecc72493f8b6706fecef80a893679a23b02f912905c4915c0`** | index entry; equals the sha256 of the fetched body |
| linux/arm64 manifest (not used) | `sha256:e731c79aba1c9d777b77ed85f0c0111531cbaa24ecba90fe65ad7b7438e89c40` | index entry |
| amd64 config blob | `sha256:b6862d3036a770b5c0e8a0987e9546dc1844f10ba70925f746e7a44ca84660c0`; created 2026-10-22T17:51:03Z; 4 layers, 1,032,349,420 bytes compressed | blob fetched, sha256 verified |
| Image defaults | `User` unset (root); `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`; `CMD ["/bin/bash"]`; user `pwuser` created; `/ms-playwright` is `chmod -R 777` | config history |
| Python | Ubuntu noble `python3` 3.12; `pip` from `get-pip.py` at build time | config history |
| Playwright Python package | **Not present in the final image.** It was installed only in a temporary venv that the build deleted | config history, last RUN step |
| **Image role (v1.3)** | **Operating-system and dependency base only.** The image's bundled Chromium 156.0.8078.4 (revision 1248, pre-stable) under `/ms-playwright` is **never executed**. `entry.sh` launches only the pinned Chrome for Testing binary (B2a), and the run records the launched executable path and the running process list | — |
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
  --name crm-client001r-browser-<run> \
  --user 65534:65534 \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=1g \
  --cap-drop ALL --security-opt no-new-privileges=true \
  --pids-limit 512 --memory 2g --shm-size 1g \
  --network crm-client001r-browser-<run> --ip <browser-ip> \
  --env HOME=/tmp --env PYTHONDONTWRITEBYTECODE=1 \
  --env CRM_BROWSER_BASE_URL=http://<app-ip> \
  --env-file <root-0600-tmp-file> \
  --mount type=bind,src=<archive-copy-of-candidate>,dst=/work,readonly \
  --mount type=bind,src=<verified-wheelhouse>,dst=/wheels,readonly \
  --mount type=bind,src=<verified-cft-tree>,dst=/opt/cft,readonly \
  --mount type=bind,src=<evidence-out>,dst=/evidence \
  mcr.microsoft.com/playwright/python@sha256:7d030ac0638b279ecc72493f8b6706fecef80a893679a23b02f912905c4915c0 \
  /bin/bash /work/tests/browser/entry.sh
```

- **`<root-0600-tmp-file>`** holds only the synthetic `@example.test` test-user credentials. It is created for the run and deleted in cleanup (B9), and is never in argv or evidence.
- **Restrictions.**
  - No Docker socket, no host networking, no privileged mode, no added capabilities and no device mounts.
  - The only writable paths are `/tmp` (tmpfs) and `/evidence`.
  - The default seccomp and AppArmor profiles apply.
- **Browser sandbox.** Playwright launches Chrome without its own sandbox (`chromiumSandbox: false`, so `--no-sandbox`). Under `--cap-drop ALL` the namespace sandbox is unavailable anyway, so the boundary is the container plus B4. Running a **patched stable** browser (B2a) is what makes this acceptable (B8.4).
- **Image acquisition (S3 operator gate).**
  1. Pull by digest: `docker pull mcr.microsoft.com/playwright/python@sha256:7d030ac0…15c0`.
  2. `docker image inspect` must show that RepoDigest and config ID `sha256:b6862d30…60c0`.
  3. Acquire Chrome for Testing (B2a), then run the B8 scan over the image, the wheels and the CfT tree.
  4. Use `--pull never` thereafter.
- **Image removal.** The image is removed at **WO closure** (B9.4), not after each run, so that a bounded repeat (B6.4) uses the same bytes.
- **`<evidence-out>`** is a fresh root-created `/tmp/crm-client001r-browser-<run>/out`, owned by 65534 with mode 0700.
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
   `docker network create --driver bridge --internal --subnet 172.31.250.0/29 -o com.docker.network.bridge.inhibit_ipv4=true -o com.docker.network.bridge.enable_ip_masquerade=false crm-client001r-browser-<run>`
   - `--internal` means no default route and no NAT.
   - `inhibit_ipv4` gives the host-side bridge no IPv4 address.
   - The subnet is first checked as unused against `docker network ls` and `ip route`.
2. **Admit the browser.** Its single address, `172.31.250.2/32`, is appended **temporarily** to `CRM_ALLOWED_SOURCES` in `/srv/CRM/runtime/dev/env`.
   - Before the change: a byte copy and the sha256 of the env file are saved (B9.1).
   - `check_access.py dev` must pass.
   - The existing bind-only entry is handled per the recorded crm-dev procedure.
   - crm-app is then recreated with `scripts/up.sh dev`.
3. **Attach crm-app.** `docker network connect --ip 172.31.250.3 crm-client001r-browser-<run> crm-dev-crm-app-1`.
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

1. **Seal.** After S4 (including cleanup), root copies the package to `/srv/CRM/evidence/CRM-CLIENT-001R/<run>/`, root-owned with group `forgev2-pl`, directories 0750 and files 0640. `SHA256SUMS` is written last and its own sha256 is recorded.
   - gitleaks (`dir --redact`) must report the package clean.
   - The package is never edited afterwards. A repeat gets a new `<run>`.
2. **BA final WO version.** It names the raw package by `<run>` and the sha256 of `SHA256SUMS` only. The sha256 of `SHA256SUMS` and `<run>` go into the final exact version of `CRM-CLIENT-001R-BA.md`, which CGPT approves before dispatch. The sandboxed specialists of that WO can read the store (it is not a private path of the engine) but cannot write it.
3. **Independent assessment.**
   - The BA Tester and DevSecOps **inspect the raw package directly in the restricted store** (read-only). The Tester verifies `SHA256SUMS` first.
   - It runs `verify_evidence.py` **from the candidate** on a copy in its scratch. The verifier recomputes every AC6b and AC12 verdict from the raw files and never trusts `result.json`.
   - It may unpack and inspect `trace.zip` and the screenshots.
   - It issues its own PASS or FAIL per journey.
4. **Challenge and bounded repeat.**
   - The Tester may record a blocking finding with the key **`browser-rerun-<journey>`** (the ledger's `KEY[:severity]` syntax forbids `:` inside keys), with the reason in `--note`.
   - BA then cannot deliver. The PL returns ESCALATED, because the Engineer cannot produce operator evidence.
   - The Orchestrator performs **one** bounded repeat (same `C`, same procedure, new `<run>`).
   - The repeat is assessed in **one** follow-on WO `CRM-CLIENT-001R-BA2`, which is identical except for the run id and manifest and needs its own CGPT exact-version approval. No further repeat is permitted without a new CGPT decision.
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
4. **Image scan.** `grype registry:mcr.microsoft.com/playwright/python@sha256:7d030ac0…15c0 --platform linux/amd64 -o json` goes to `scan/image.json`, with a table copy in `scan/image.txt`. The `registry:` source fetches layers directly, with no daemon.
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
  - packages present but not executed: the image's bundled Chromium 156 and headless shell under `/ms-playwright` (proven not executed, B2.3), and the Firefox and WebKit binaries, `apt` and `dpkg` tooling, `perl`, `openssh-client`, X11 or GUI libraries used only in headful mode, and ffmpeg;
  - CVEs that need a listening network service, local privileged users, or a route to destinations that B4 proves unreachable;
  - kernel CVEs, which are reported to DevSecOps but belong to the host.
- **Unscannable components** are listed explicitly and never counted as clean. Chrome for Testing is not package-managed, so it is assessed by version against the Chrome Releases blog (B8.4).

**B8.4 Browser vulnerability position (v1.3).** The v1.2 residual is **removed**: the pre-stable Chromium 156.0.8078.4 is no longer executed. The executed browser is the current **Stable** Chrome for Testing, 157.0.8103.78.
- The latest desktop Stable release notes found during preparation are 157.0.8103.50, from 2026-11-09. The `.78` artefacts were published by the CfT Stable channel on 2026-11-11, so they are later.
- At S3 the B2a freshness gate re-confirms that no later Stable security release exists.
- A Chrome CVE published after `.78` and fixed in a later Stable is a **material** finding under B8.3, and it triggers the re-pin route.
- The unexecuted Chromium 156 files remain in the image's filesystem. They are classified *present, not executed*, and the process check proves it at runtime.

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
   - The GitHub `forge/CRM-CLIENT-001R` branch contains `C`.
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
6. **Absence of stale objects.** No `crm-client001r-*` container or network, and the subnet is unused.
7. **Gate.** The CfT acquisition and freshness gate (B2a) and the CL-D5 scan (B8) pass under the triage rules. **Library gate (v1.4, CGPT finding):** inside the exact pinned image, as uid 65534 with no network, `ldd` of the verified CfT binary and of the 1.65.1 wheel's bundled `playwright/driver/node`, run as data with no browser started, shows no `not found` library, including `libatomic.so.1`. **If any library is missing, STOP browser execution** and propose the smallest image re-pin to CGPT. Host libraries are never installed and the approved runtime is never changed.

**B9.2 Cleanup (always run, in this order, each step idempotent and logged).**
1. Stop and remove the `crm-client001r-browser-<run>` container if present (`docker rm -f`).
2. Disconnect crm-app from the test network, if attached.
3. Remove the test network.
4. Restore the env file from the byte copy, then run `cmp` and compare its sha256 with `crmdev-before.json`.
5. If a deploy left the stack in a non-baseline state, run `restore.sh dev` of the B9.1 backup, and the cache-bust (D5 does this in the success path).
6. Recreate crm-app with `scripts/up.sh dev` and wait until it is healthy.
7. Remove the PATH wrapper directory, the env-file of test credentials and the temporary wheelhouse and output directories, after the evidence is copied.
8. Write `cleanup.json`.

**B9.3 Cleanup verification (G7). Each item is a boolean, and any false is a FAILED run, even if every journey passed.**
- The env file is byte-identical to `crmdev-before.json`.
- `docker ps -a` and `docker network ls` show no `crm-client001r-*` object.
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
- Keep the evidence store (`/srv/CRM/evidence/CRM-CLIENT-001R/`) as the delivery record until CGPT authorises archival.

**B9.5 Manual recovery (interrupted procedure, e.g. host reboot or killed shell).** This is documented in `docs/RELEASE.md` (AC10) and works from `state.log` alone:
1. `docker rm -f crm-client001r-browser-<run>`.
2. `docker network disconnect -f crm-client001r-browser-<run> crm-dev-crm-app-1`, then `docker network rm crm-client001r-browser-<run>`.
3. `cp --preserve=mode,ownership <saved env copy> /srv/CRM/runtime/dev/env`, then `cmp` and sha256.
4. If `state.log` records any deploy, or the runtime trees show `.Custom.old-*`, `.src.old-*` or `.failed-*`: stop crm-app and crm-daemon, run `restore.sh dev` of the recorded backup, then `up.sh dev`, `clear-cache`, `rebuild` and `update-app-timestamp`.
5. Run every B9.3 check and record the result as `manual-recovery.json` in the run's evidence.
6. An interrupted run is **never** evidence for BA. A new run id is required.
