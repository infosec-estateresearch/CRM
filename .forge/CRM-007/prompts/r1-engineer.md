# CRM-007, round 1: Engineer (crm-beta, release bundle, clean-host deploy)

- **Worktree:** `/srv/CRM/worktrees/CRM-007`, branch `forge/CRM-007`. The expected HEAD is `e1f9a6899e82ac5862849db0bf1f00dbcae51244`. Confirm it first. Do not modify `.forge/`.
- **Work order:** `work-orders/CRM-007.md` **v1.1**, on main. It is authoritative. Keep strictly to its allowlist. `load/` and `custom/` are excluded; `scripts/load.sh` is owned by CRM-006S, which runs in parallel, so **do not edit it**.
- **Everything happens in-process.** You start no containers, run no Docker commands, write nothing under `/srv/CRM/runtime` and use no network. The operator stage (AC3–AC7) is run later by the PL as root. Your deliverable is the code, unit tests and docs that make it possible.
- **Scratch:** `/srv/CRM/worktrees/.forge-scratch/CRM-007/`.
- **Status reporting.** If the time box ends before you finish, report **`STATUS: completed`** with a precise "Known gaps" list. Use `failed` only if the work cannot be done at all.
- **Time box:** the dispatcher stops you at 30 minutes. Return by about 25 minutes. Work in this order: steps 1 → 2 → 3 → 4 → 6 → 5 → 7. If time runs short, leave the timer template and the polish of `docs/RELEASE.md`.

## Facts verified by the PL on DOCKER1
- `crm-dev` is defined by `deploy/compose.json`, `deploy/env.example` and `deploy/apache/`. The scripts are in `scripts/` and `scripts/lib/common.sh`. The runtime is `/srv/CRM/runtime/dev` (root `0700`), with `env`, `db`, `data`, `custom`, `client` and `backups`. Read those files: they are the pattern to generalise. Keep the dev behaviour **byte-identical** where the target is dev, and prove it with the existing tests.
- **The edge image:** `haproxy:3.2-alpine`, HAProxy 3.2.26 LTS, digest `sha256:1c3568e520453cc8ba98c39501febcf450429c80e6cc27ecad779961d76e597c`. It runs as user `haproxy`.
  - Reference it in compose as `haproxy@sha256:…`, and register it in `security/EXTERNAL_CODE_REGISTER.yaml` alongside the existing espocrm/mariadb entries, in the same format.
  - The edge listens on an unprivileged port, so it needs no added capabilities: `cap_drop: [ALL]`, `read_only: true`, `security_opt: [no-new-privileges:true]`, and a tmpfs only if HAProxy needs one.
- **Host values live only in the root-only runtime env** (`/srv/CRM/runtime/beta/env`): `CRM_BETA_BIND_IP`, `CRM_BETA_PORT`, `CRM_BETA_UPSTREAM_SOURCES`, `CRM_BETA_HOSTNAME` and `CRM_BETA_APP_PORT`.
  - The repo holds only `deploy/beta/env.example`, with RFC 5737 / RFC 2606 placeholders such as `192.0.2.10` and `crm-beta.example.invalid`.
  - **No real IPs, hostnames, staff or firm names** go anywhere in the repo.
- **Rendering the HAProxy config.** The config is rendered from a Git-controlled template by a stdlib Python renderer, which validates fail-closed (`check_access.py beta`):
  - every source is an RFC 1918 /32;
  - there are 1–4 sources;
  - the bind IP is RFC 1918 and is not `0.0.0.0`;
  - the port is an integer between 1024 and 65535;
  - the hostname matches a strict DNS regex;
  - the result is written into `/srv/CRM/runtime/beta/edge/haproxy.cfg` at deploy time.
  - Keep the template minimal: `mode http`; an ACL on `src` that returns 403 for everything else; `http-request set-header X-Forwarded-Proto https` only for trusted sources; and `option forwardfor` only for trusted sources (the upstream HAProxy's X-Forwarded-For is kept when it comes from a trusted source; otherwise it is deleted). Set timeouts.
- **EspoCRM behind a TLS proxy:**
  - set `siteUrl` to `https://<hostname>`;
  - `crm-app` (beta) publishes only `127.0.0.1:${CRM_BETA_APP_PORT}`;
  - the Apache config must trust `X-Forwarded-Proto` only from loopback, where the edge connects from.
- **`phoneNumberInternational=false` on beta** (WO v1.1, step 4). This is the CRM-006S precondition. Deploy sets it and then reads it back. If the read-back value isn't exactly false, deploy fails.
- Beta never gets synthetic seeding. Its acceptance suite in beta-safe mode is read-only.

Run `python3 -m unittest discover -s tests/unit` plus any new suite you add. Report exact counts and give mutation evidence for each guard: the target guard, bind, edge policy, bundle tamper/digest, and non-empty runtime. Finish in the Engineer final message format.
