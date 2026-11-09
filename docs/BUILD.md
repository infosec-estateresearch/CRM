# Build and deployment boundary

- **Status:** DRAFT. Nothing described here has been installed. The commands below take effect only once their WO is approved and the operator stage is authorised.

## 1. What gets built

The build is the official EspoCRM image, pinned by digest, plus Estate Research's extension in `custom/`. Nothing is built from a fork of the upstream source tree (CRM-D001).

| Path in repo | Contents |
|---|---|
| `deploy/compose.json` | Three services, all with images pinned by digest: `crm-app` (EspoCRM), `crm-daemon` (the same image with entrypoint `docker-daemon.sh`) and `crm-db` (MariaDB). JSON is valid Compose YAML; it was chosen so the policy tests need only the Python standard library. |
| `deploy/env.example` | Names of the variables the stack needs. **No values.** |
| `custom/` | ER metadata and code, mounted into the app as EspoCRM's `custom/` directory |
| `scripts/` | Synthetic data seeder, backup, restore, export |
| `tests/unit/` | Run without a stack or network (in the ForgeV2 loop) |
| `tests/acceptance/` | Need the running dev stack (operator stage) |

Images (see `security/EXTERNAL_CODE_REGISTER.yaml`):
- `espocrm/espocrm:10.0.12@sha256:b50245d1e291b2636116b0396ce0d06018ffcded6a6c61c7af2420443a20f3ec`
- `mariadb:11.4.13@sha256:d1891ede5a559f1086f55053bb8cc1569b0298338c4d72d71725a7f74f6ba620`

**Dev versus release.** CRM-001's dev stack mounts `custom/` from the checkout. The customer release (CRM-PBI-016) bakes the customisations into an ER image built from the pinned upstream digest, and installs from a release bundle with no Git checkout, ForgeV2, Claude or development-host paths (CRM-D017).

## 2. Where it runs

The dev environment lives in `DOCKER1:/srv/CRM/runtime/dev/`, which is root-owned, mode `0700` and outside Git. It contains:
- `env`: generated secrets, mode `0600`;
- `db/` and `data/`: bind mounts;
- `backups/`.

## 3. Isolation boundary (CRM-D012)

- **Naming (CRM-D018):**
  - Services, networks, named volumes and ER images carry the `crm-` prefix.
  - Each environment has its own project name (`crm-dev`, later `crm-beta` and `crm-prod`).
  - No `container_name` is set: Compose generates instance names, e.g. `crm-dev-crm-app-1` and network `crm-dev_crm-net`.
- **Compose project:** `crm-dev`, on its own network `crm-net` with subnet `172.16.10.0/24`. On 2026-11-06 Docker on the host had no 172.16.x network; confirm the subnet is also unused on the LAN.
- **Published ports:** `crm-app` publishes `127.0.0.1:8180` only. The database publishes nothing. Access is through an SSH tunnel until CRM-PBI-008 adds TLS and LAN binding.
- **Nothing shared:** no volumes, networks, databases or credentials with any other application on the host.
- **Firewall:** no firewall rules (standing policy). Exposure is controlled by the bind address.
- **Resources:** about 2–3 GB RAM and 10 GB disk.

## 4. Operator commands (operator stage only, from the exact PR commit)

```sh
cd /srv/CRM/worktrees/CRM-001      # the delivered forge/CRM-001 worktree at the PR head commit
git rev-parse HEAD                  # must equal the PR head SHA recorded on the WO Issue
docker compose -p crm-dev -f deploy/compose.json --env-file /srv/CRM/runtime/dev/env up -d
python3 scripts/seed_synthetic.py --base-url http://127.0.0.1:8180
python3 -m unittest discover -s tests/acceptance -v
scripts/backup.sh dev && scripts/restore.sh dev <backup>
docker compose -p crm-dev -f deploy/compose.json ps; docker network inspect crm-dev_crm-net   # AC9: own resources only
docker compose -p crm-dev -f deploy/compose.json down    # data stays in runtime/dev
```

## 5. How changes are verified

These constraints are established facts about the host, not choices:
- ForgeV2 specialists have **no Docker access** (the PL account is not in the `docker` group).
- Specialist commands have **no network**, loopback included (ForgeV2 `sandbox_settings()`).
- The host has **no browser** (ForgeV2 `plugin/README.md`).

What follows (CRM-D013):

| Stage | Who | What is verified |
|---|---|---|
| Build and review | ForgeV2: Engineer, Auditor, Tester, DevSecOps | Unit tests, Compose policy, metadata validity, gitleaks, register. UI changes come back **ESCALATED (browser only)**, which is acceptable as an intermediate result only. |
| Deployment and functional acceptance | Authorised operator | The live acceptance criteria against the running dev stack, with synthetic data, from the exact PR commit |
| Product acceptance | Matt | Walkthrough of the running application; acceptance; merge |

Defects found at deployment stay open. They are fixed under a follow-up WO and retested before acceptance.

## 6. Project boundary

CRM work is confined to:
- this repository and its approved worktrees;
- the `crm-dev` runtime under `/srv/CRM/runtime/dev`;
- specifically authorised supporting operations.

It never inspects, changes or connects to any other application or service on the host. Non-interference is shown from the project's own side, on every WO:
- the diff touches nothing outside this repository (Auditor);
- the Compose file declares no external networks or volumes (DevSecOps);
- the operator inspects only the `crm-dev` project's own containers and network (AC9).

A genuine shared-host conflict, such as a port or subnet already in use, is reported to Matt, not remediated.
