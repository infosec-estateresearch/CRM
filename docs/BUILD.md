# Build and deployment boundary

- **Status:** DRAFT. Nothing described here has been installed. The commands below take effect only once their WO is approved and the operator stage is authorised.

## 1. What gets built

The build is the official EspoCRM image, pinned by digest, plus Estate Research's extension in `custom/`. Nothing is built from a fork of the upstream source tree (CRM-D001).

| Path in repo | Contents |
|---|---|
| `deploy/compose.json` | Three services, all with images pinned by digest: `crm-app` (EspoCRM), `crm-daemon` (the same image with entrypoint `docker-daemon.sh`) and `crm-db` (MariaDB). JSON is valid Compose YAML; it was chosen so the policy tests need only the Python standard library. |
| `deploy/env.example` | Names of the variables the stack needs. **No values.** |
| `custom/` | ER metadata and code. `scripts/deploy_custom.sh` deploys `custom/Espo/Custom/` into the runtime directory that the app mounts as EspoCRM's `custom/` (§7.2) |
| `scripts/` | Synthetic data seeder, customisation deploy, backup, restore, export |
| `tests/unit/` | Run without a stack or network (in the ForgeV2 loop) |
| `tests/acceptance/` | Need the running dev stack (operator stage) |

Images (see `security/EXTERNAL_CODE_REGISTER.yaml`):
- `espocrm/espocrm:10.0.12@sha256:b50245d1e291b2636116b0396ce0d06018ffcded6a6c61c7af2420443a20f3ec`
- `mariadb:11.4.13@sha256:d1891ede5a559f1086f55053bb8cc1569b0298338c4d72d71725a7f74f6ba620`

**Dev versus release.** CRM-001's dev stack deploys `custom/` from the checkout into its runtime directory. The customer release (CRM-PBI-016) bakes the customisations into an ER image built from the pinned upstream digest, and installs from a release bundle with no Git checkout, ForgeV2, Claude or development-host paths (CRM-D017).

## 2. Where it runs

The dev environment lives in `DOCKER1:/srv/CRM/runtime/dev/`, which is root-owned, mode `0700` and outside Git. It contains:
- `env`: generated secrets, mode `0600`;
- `db/`, `data/`, `custom/` and `client/custom/`: bind mounts;
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
scripts/deploy_custom.sh dev        # before the first up (§7.2)
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

## 7. Usage (CRM-001 dev stack)

Everything below is for the operator stage. Run it as the authorised operator, from the delivered worktree at the PR head commit (§4). Nothing in it has been run inside the ForgeV2 loop.

### 7.1 One-time runtime preparation

1. Create `/srv/CRM/runtime/dev/` (root-owned, mode `0700`) with the subdirectories `db/`, `data/`, `custom/`, `client/custom/` and `backups/`. All of them start empty.
2. Copy `deploy/env.example` to `/srv/CRM/runtime/dev/env` (mode `0600`) and fill in every name. Generate the secrets on the host and never commit them. Use these values:
   - `CRM_DB_DIR=/srv/CRM/runtime/dev/db`
   - `CRM_DATA_DIR=/srv/CRM/runtime/dev/data`
   - `CRM_CUSTOM_DIR=/srv/CRM/runtime/dev/custom`
   - `CRM_CLIENT_CUSTOM_DIR=/srv/CRM/runtime/dev/client/custom`
   - `CRM_SITE_URL=http://127.0.0.1:8180`

   Compose refuses to start if any variable is unset. `deploy_custom.sh`, `backup.sh` and `restore.sh` read `CRM_DATA_DIR`, `CRM_CUSTOM_DIR` and `CRM_CLIENT_CUSTOM_DIR` from the env file as text (it is never sourced). They refuse to run unless each one is a single, absolute, plain `NAME=<path>` line whose canonical path is exactly `/srv/CRM/runtime/dev/{data,custom,client/custom}`, and unless `/srv/CRM/runtime/dev` itself contains no symlink.
3. Confirm that `172.16.10.0/24` and `127.0.0.1:8180` are free. A conflict is reported to Matt, not remediated (§6).

### 7.2 Layout of the stack

- `crm-app` serves EspoCRM on `127.0.0.1:8180`. Reach it from a workstation over an SSH tunnel.
- `crm-daemon` runs the job daemon (`docker-daemon.sh`).
- `crm-db` is MariaDB and publishes no port. It bind-mounts `CRM_DB_DIR` at `/var/lib/mysql`.
- `crm-app` and `crm-daemon` each have exactly three bind mounts, which are the same three on both services and are all read-write:

  | Runtime directory (env variable) | Mounted at |
  |---|---|
  | `data/` (`CRM_DATA_DIR`) | `/var/www/html/data`: config, uploads, logs, cache |
  | `custom/` (`CRM_CUSTOM_DIR`) | `/var/www/html/custom` |
  | `client/custom/` (`CRM_CLIENT_CUSTOM_DIR`) | `/var/www/html/client/custom` |

  No service mounts `/var/www/html` itself. The application code is the image's own, so an image upgrade really upgrades it. This is the EspoCRM 10 layout ("Migration to EspoCRM 10", https://docs.espocrm.com/administration/docker/installation/). If the entrypoint finds `/var/www/html` mounted, it takes the legacy path: no further upgrades, and `exit 1` when the mount is empty, which was the first-start risk in the earlier layout. The Compose policy tests enforce the layout (`no_docroot_mount`, `espocrm_mounts`, `espocrm_mounts_writable`).

#### Customisation: Git is authoritative, the runtime copy is read-write

**Decision.** The runtime `custom/` and `client/custom/` are mounted read-write. The repository's `custom/` is not mounted into the containers at all. `scripts/deploy_custom.sh dev` copies `custom/Espo/Custom/` into the runtime `custom/Espo/Custom/`.

**Why not read-only.** The image entrypoint runs `setPermissions`, which is `chown -R www-data:www-data ./data ./custom ./client/custom`, on every start, under `set -euo pipefail`. That covers both installation and migration. A chown on a read-only mount fails, so the entrypoint would abort the first installation and every later restart. The image entrypoint is not overridden.

**How the deploy works.** It is deterministic:
- It stops `crm-app` and `crm-daemon` before it checks the paths and swaps the tree (see "Path safety" below).
- It builds a fresh copy beside the live tree, swaps it in by rename, and deletes the previous tree. Files removed from Git are therefore removed from the runtime too, and two deploys of the same commit give identical trees.
- Files are written world-readable (umask `022`), whatever the operator's umask.
- It only manages `custom/Espo/Custom/`. The rest of the runtime `custom/` and all of `client/custom/` are left alone. The repository has no `client/custom/` content at present.
- It never replaces the runtime `custom/` directory itself, because that directory is the bind-mount source.
- If `crm-app` was running when the deploy started, it starts `crm-app` and `crm-daemon` again (`up -d --wait`), then runs `bin/command clear-cache` and `bin/command rebuild` inside `crm-app` as `www-data`. If `crm-app` was not running, both stay stopped and the script says the rebuild was skipped.
- It takes the `dev` guard like the other scripts.

**Path safety.** The deploy runs as root. The image entrypoint chowns the runtime `custom/` to the container's `www-data` on every start, so code running as `www-data` in `crm-app` or `crm-daemon` could otherwise plant a symlink in that tree and redirect a root write or delete elsewhere on the host. The script therefore fails closed, as follows:
- It checks the paths once before touching the stack, so a bad layout is refused while the stack keeps running.
- It then records whether `crm-app` is running and stops `crm-daemon` and `crm-app`. It checks the paths again, and this is the authoritative check: with the containers stopped, nothing in them can change the tree between check and use.
- Every component it works on must be a real directory, not a symlink, and its canonical path must equal its lexical path under the canonical runtime. That covers `/srv/CRM/runtime/dev`, `custom/`, `custom/Espo` and `custom/Espo/Custom`. A missing `custom/Espo` is created as a plain directory.
- `/srv/CRM/runtime/dev` must be owned by the invoking user (root) and must not be group- or world-writable.
- The staging name `.Custom.deploy-<UTC>` and the old-tree name `.Custom.old-<UTC>` must not exist, not even as a dangling symlink.
- Renames use `mv -T`, so they never move a tree into a directory.
- Removal of the staging or old tree refuses a symlink and stays on one filesystem (`rm --one-file-system`).
- If any check fails after the stop, the script exits non-zero and leaves `crm-app` and `crm-daemon` stopped. Investigate the runtime tree before starting them again.

**Consequences:**
- **Installation (first start).** Run the first deploy **before** the first `up`. Bind mounts start empty, and they hide the image's own `custom/` and `client/custom/`. On its first start the entrypoint runs `actionInstall`, which includes `bin/command rebuild`. With the customisation already in place, that rebuild creates the ER fields, links and database columns. The metadata cache and schema are then right from the first start, with no second rebuild. Deploying after the first `up` also works, but only once the deploy's own rebuild has run. The script refuses to run if the runtime `custom/` directory does not exist (§7.1).
- **Rebuild (changing the customisation).** Change `custom/` in Git, check out the commit, and run `scripts/deploy_custom.sh dev` with the stack up. The script stops `crm-app` and `crm-daemon`, swaps the tree, starts them again, then clears the cache and rebuilds. Expect a short outage of the app while it runs. If the stack is down, run the script again after `up`. A restart alone runs `clear-cache` and `migrate` (`actionMigrate`), not a guaranteed `rebuild`.
- **Restart.** The entrypoint re-chowns the three runtime directories to `www-data` (container uid) on every start. The files deployed from Git stay as they are, only their owner changes. A later deploy, run as root, replaces them again.
- **Admin-UI changes.** A deploy run as root leaves the deployed `custom/Espo/Custom/` tree **root-owned until the next container start**, when the entrypoint chowns it to `www-data`. Until then, Entity Manager and Layout Manager cannot write to it. When the deploy restarts the app itself (the app was running), that start is part of the deploy and they can write again once the deploy has finished. After a deploy before the first `up`, they can write once the stack has started. Any change they make is **overwritten by the next deploy**. To keep a change, make it in Git. Git remains authoritative, and the runtime copy is only a deployment of it.
- **Backup and restore** cover the runtime `custom/` and `client/custom/` as well as `data/` and the database (§7.3). After a restore, the runtime holds the customisation as it was at backup time. Run `scripts/deploy_custom.sh dev` to return to the checked-out commit.

The entrypoint and image behaviour above comes from the upstream `espocrm-docker` source (`latest/apache/`, `ESPOCRM_VERSION 10.0.12`), not from the pinned digest. It is to be confirmed at the operator stage.

### 7.3 Commands

All commands run from the repository root.

```sh
ENVF=/srv/CRM/runtime/dev/env
scripts/deploy_custom.sh dev               # first deploy BEFORE the first up (crm-app not running: no rebuild yet)
docker compose -p crm-dev -f deploy/compose.json --env-file "$ENVF" up -d --wait   # installs, incl. rebuild

# Later customisation changes, with the stack up: stop app+daemon, deploy, start them, clear-cache + rebuild
scripts/deploy_custom.sh dev

# Credentials are read from the environment only; they are never written to disk.
export CRM_BASE_URL=http://127.0.0.1:8180 CRM_ADMIN_USERNAME=... CRM_ADMIN_PASSWORD=...
python3 scripts/seed_synthetic.py --dry-run                # dataset summary, no HTTP
python3 scripts/seed_synthetic.py --base-url "$CRM_BASE_URL" --seed 1

scripts/backup.sh dev                      # -> /srv/CRM/runtime/dev/backups/crm-dev-<UTC>/
scripts/export.sh dev                      # -> /srv/CRM/runtime/dev/backups/export-<UTC>/{accounts,contacts}.csv
scripts/restore.sh dev crm-dev-<UTC>       # prints "restore completed ... in <N>s" (record it for AC8)

CRM_SEED=1 CRM_EXPORT_DIR=/srv/CRM/runtime/dev/backups/export-<UTC> \
    python3 -m unittest discover -s tests/acceptance -v
```

Script behaviour:
- **The dev guard.** `deploy_custom.sh`, `backup.sh`, `restore.sh` and `export.sh` take the target environment as their first argument. They refuse, with exit 2, unless it is exactly `dev` and the runtime directory is named `dev`.
- **Env-file paths.** `deploy_custom.sh`, `backup.sh` and `restore.sh` refuse to run (exit 1, nothing written, no `docker` call) if the env file's `CRM_DATA_DIR`, `CRM_CUSTOM_DIR` or `CRM_CLIENT_CUSTOM_DIR` is missing, duplicated, relative, or does not resolve to exactly `$CRM_RUNTIME_DIR/{data,custom,client/custom}` (§7.1).
- **`deploy_custom.sh`** is described in §7.2.
- **`backup.sh`** runs `mariadb-dump` inside `crm-db`, using the container's own credentials, so no secret appears on the host command line. It also writes one archive per mounted runtime directory: `data.tar.gz` (`data/`), `custom.tar.gz` (`custom/`) and `client-custom.tar.gz` (`client/custom/`). Each archive stores its runtime-relative path. It then writes `SHA256SUMS` over all four files. A failed backup leaves no partial directory.
- **`restore.sh`** checks the checksums. It also refuses a backup that lacks any of the four checksummed files, which includes backups made with the earlier, whole-document-root layout. Then it stops `crm-app` and `crm-daemon`. It moves each current directory aside, to `data.replaced-<UTC>`, `custom.replaced-<UTC>` and `client/custom.replaced-<UTC>` (nothing is deleted), and extracts each archive back into its own place. It imports the dump, starts the stack and prints the elapsed time. Remove the `*.replaced-*` directories by hand once the restore has been accepted.
- **`export.sh`** pages through the API, ordered by id, and fails if the number of rows does not match the API total. Values are written verbatim, so open the CSV files as data, not as spreadsheets with formulas.

### 7.4 The synthetic dataset (seed 1)

The dataset contains:
- 219 firms: 1 parent with 34 branches; 24 parents with 1–8 branches each; 40 stand-alone firms. Two of the branches share one name and have different postcodes.
- 600 contacts at `@example.test`.
- 5 held-back near-duplicates (3 firms, 2 contacts). They are not created by the seeder; AC7 creates them.
- 10 search probes.

All values are synthetic:
- names are built from invented syllables;
- postcodes are in the non-geographic `ZZ` area;
- phone numbers come from Ofcom's drama ranges.

`--dry-run` prints the exact counts for any seed. The acceptance tests recompute every expected value from the seed, and assume that the stack holds only the seeded data.

### 7.5 In-loop checks (no stack, no network)

```sh
python3 -m unittest discover -s tests/unit -v
for f in scripts/*.sh scripts/lib/*.sh; do bash -n "$f"; done
# Show that a policy test fails when its rule is broken (any compose_bad_*.json):
CRM_COMPOSE_UNDER_TEST=tests/unit/fixtures/compose_bad_mount_read_only.json \
    python3 -m unittest discover -s tests/unit -p test_compose_policy.py
```
