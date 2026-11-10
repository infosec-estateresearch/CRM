# Build and deployment boundary

- **Status:** DRAFT. Nothing described here has been installed. The commands below take effect only once their WO is approved and the operator stage is authorised.

## 1. What gets built

The build is the official EspoCRM image, pinned by digest, plus Estate Research's extension in `custom/`. Nothing is built from a fork of the upstream source tree (CRM-D001).

| Path in repo | Contents |
|---|---|
| `deploy/compose.json` | Three services, all with images pinned by digest: `crm-app` (EspoCRM), `crm-daemon` (the same image with entrypoint `docker-daemon.sh`) and `crm-db` (MariaDB). JSON is valid Compose YAML; it was chosen so the policy tests need only the Python standard library. |
| `deploy/env.example` | Names of the variables the stack needs. **No values.** |
| `deploy/apache/crm-access.conf` | Apache source-address restriction for `crm-app`, mounted read-only (§7.6, CRM-D019) |
| `custom/` | ER metadata and code. `scripts/deploy_custom.sh` deploys `custom/Espo/Custom/` into the runtime directory that the app mounts as EspoCRM's `custom/` (§7.2) |
| `scripts/` | Synthetic data seeder, customisation deploy, backup, restore, export, LAN access check (`check_access.py`) |
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
- **Published ports:** `crm-app` publishes port 8180 on one host LAN address only, `${CRM_BIND_IP}` from the runtime env file. It never uses `0.0.0.0` or a mapping without a host IP, and it no longer publishes on `127.0.0.1`. The database and the daemon publish nothing. The address is never written in Git (§7.6, CRM-D019).
- **Source restriction:** Apache inside `crm-app` admits only loopback and the networks in `${CRM_ALLOWED_SOURCES}` (§7.6). TLS is still missing and is mandatory before real data (CRM-PBI-008).
- **Nothing shared:** no volumes, networks, databases or credentials with any other application on the host.
- **Firewall:** no firewall rules (standing policy: no iptables, ufw or nftables, and so no `DOCKER-USER` rules either). Exposure is controlled by the bind address plus the Apache source restriction.
- **Resources:** about 2–3 GB RAM and 10 GB disk.

## 4. Operator commands (operator stage only, from the exact PR commit)

```sh
cd /srv/CRM/worktrees/CRM-001      # the delivered forge/CRM-001 worktree at the PR head commit
git rev-parse HEAD                  # must equal the PR head SHA recorded on the WO Issue
scripts/deploy_custom.sh dev        # before the first up (§7.2)
scripts/up.sh dev                   # every start: checks paths and LAN access, then up -d --wait (§7.6)
python3 scripts/seed_synthetic.py --base-url "http://<CRM_BIND_IP>:8180"
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
   - `CRM_BIND_IP=<the host's LAN address>`
   - `CRM_ALLOWED_SOURCES=<authorised subnet A> <authorised subnet B>`
   - `CRM_SITE_URL=http://<CRM_BIND_IP>:8180`

   `python3 scripts/check_access.py dev` checks the last three (§7.6). `scripts/up.sh dev`, `deploy_custom.sh` and `restore.sh` run that check themselves before they start anything.

   Compose refuses to start if any variable is unset. `deploy_custom.sh`, `backup.sh` and `restore.sh` read `CRM_DATA_DIR`, `CRM_CUSTOM_DIR` and `CRM_CLIENT_CUSTOM_DIR` from the env file as text (it is never sourced). They refuse to run unless each one is a single, absolute, plain `NAME=<path>` line whose canonical path is exactly `/srv/CRM/runtime/dev/{data,custom,client/custom}`, and unless `/srv/CRM/runtime/dev` itself contains no symlink. Every line that could assign the name in a form Compose accepts counts towards "single": `NAME=`, `NAME: value`, `export NAME`, leading blanks, a bare `NAME`. Compose's own parser takes the last such line. Do not export any variable named in `deploy/env.example` in the shell. Compose prefers the process environment to the env file, so `deploy_custom.sh`, `backup.sh`, `restore.sh` and `up.sh` refuse to run if any of them is set. The list of names is read from `deploy/env.example` itself, so it cannot drift from the file.
3. Confirm that `172.16.10.0/24` and `<CRM_BIND_IP>:8180` are free. A conflict is reported to Matt, not remediated (§6).

### 7.2 Layout of the stack

- `crm-app` serves EspoCRM on `<CRM_BIND_IP>:8180`, to the authorised subnets only (§7.6).
- `crm-daemon` runs the job daemon (`docker-daemon.sh`).
- `crm-db` is MariaDB and publishes no port. It bind-mounts `CRM_DB_DIR` at `/var/lib/mysql`.
- `crm-app` and `crm-daemon` each have exactly three bind mounts, which are the same three on both services and are all read-write:

  | Runtime directory (env variable) | Mounted at |
  |---|---|
  | `data/` (`CRM_DATA_DIR`) | `/var/www/html/data`: config, uploads, logs, cache |
  | `custom/` (`CRM_CUSTOM_DIR`) | `/var/www/html/custom` |
  | `client/custom/` (`CRM_CLIENT_CUSTOM_DIR`) | `/var/www/html/client/custom` |

  `crm-app` also mounts the Git-controlled `deploy/apache/crm-access.conf` **read-only** at `/etc/apache2/conf-enabled/crm-access.conf` (§7.6). That is its only other mount. No service mounts `/var/www/html` itself. The application code is the image's own, so an image upgrade really upgrades it. This is the EspoCRM 10 layout ("Migration to EspoCRM 10", https://docs.espocrm.com/administration/docker/installation/). If the entrypoint finds `/var/www/html` mounted, it takes the legacy path: no further upgrades, and `exit 1` when the mount is empty, which was the first-start risk in the earlier layout. The Compose policy tests enforce the layout (`no_docroot_mount`, `espocrm_mounts`, `espocrm_mounts_writable`).

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
- After the stop and before the authoritative check, the script takes `custom/` and then `custom/Espo` back from the container uid. This closes the remaining race from a **host** process that runs with the container's uid (33), which stopping the containers does not stop. For each directory in turn, it first confirms that the path is a real directory. It then runs `chown -h <invoking uid>` and `chmod go-w` on that one directory only, never recursively. Finally it confirms again that the path is a real directory, owned by the invoking user, and not group- or world-writable. `custom/` is done first, because its parent, the runtime directory, is already private. Once `custom/` is private, no other uid can swap `custom/Espo` while it is being secured. The authoritative path check then verifies the owner and mode of both directories again. On the next start, the entrypoint's `setPermissions` re-owns them to `www-data`, which is expected. The unit tests run unprivileged, so they cannot create a directory owned by another uid. They check the mode part fully. For the owner part they check the `chown -h` invocation and the resulting owner. The owner refusal itself is not exercised.
- The staging name `.Custom.deploy-<UTC>` and the old-tree name `.Custom.old-<UTC>` must not exist, not even as a dangling symlink.
- Renames use `mv -T`, so they never move a tree into a directory.
- Removal of the staging or old tree refuses a symlink and stays on one filesystem (`rm --one-file-system`). The unit tests cannot create a mount point without privileges, so they check that the flag is passed to `rm`.
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
scripts/deploy_custom.sh dev               # first deploy BEFORE the first up (crm-app not running: no rebuild yet)
scripts/up.sh dev                          # checks, then up -d --wait: installs, incl. rebuild

# Later customisation changes, with the stack up: stop app+daemon, deploy, start them, clear-cache + rebuild
scripts/deploy_custom.sh dev

# Credentials are read from the environment only; they are never written to disk.
# CRM_ADMIN_USERNAME and CRM_ADMIN_PASSWORD are env-file names, and backup.sh,
# restore.sh, deploy_custom.sh and up.sh refuse to run while any env-file name
# is set in their environment. So the credentials are exported only inside the
# ( ... ) subshells, never in the shell that runs those scripts.
( export CRM_BASE_URL=http://<CRM_BIND_IP>:8180 CRM_ADMIN_USERNAME=... CRM_ADMIN_PASSWORD=...
  python3 scripts/seed_synthetic.py --dry-run               # dataset summary, no HTTP
  python3 scripts/seed_synthetic.py --base-url "$CRM_BASE_URL" --seed 1 )

scripts/backup.sh dev                      # -> /srv/CRM/runtime/dev/backups/crm-dev-<UTC>/
( export CRM_BASE_URL=http://<CRM_BIND_IP>:8180 CRM_ADMIN_USERNAME=... CRM_ADMIN_PASSWORD=...
  scripts/export.sh dev )                  # -> /srv/CRM/runtime/dev/backups/export-<UTC>/{accounts,contacts}.csv
scripts/restore.sh dev crm-dev-<UTC>       # prints "restore completed ... in <N>s" (record it for AC8)

( export CRM_BASE_URL=http://<CRM_BIND_IP>:8180 CRM_ADMIN_USERNAME=... CRM_ADMIN_PASSWORD=...
  CRM_SEED=1 CRM_EXPORT_DIR=/srv/CRM/runtime/dev/backups/export-<UTC> CRM_EXPECTED_BIND_IP=<CRM_BIND_IP> \
      python3 -m unittest discover -s tests/acceptance -v )
```

Script behaviour:
- **The dev guard.** `deploy_custom.sh`, `backup.sh`, `restore.sh`, `export.sh` and `up.sh` take the target environment as their first argument. They refuse, with exit 2, unless it is exactly `dev` and the runtime directory is named `dev`.
- **Env-file paths.** `deploy_custom.sh`, `backup.sh`, `restore.sh` and `up.sh` refuse to run (exit 1, nothing written, no `docker` call) in these cases (§7.1):
  - `CRM_ENV_FILE` names any file other than `$CRM_RUNTIME_DIR/env`;
  - any variable named in `deploy/env.example` is set in their environment (the bind-mount paths, the database and administrator settings, `CRM_SITE_URL`, `CRM_BIND_IP` and `CRM_ALLOWED_SOURCES`), or no names can be read from that file;
  - the env file's `CRM_DATA_DIR`, `CRM_CUSTOM_DIR` or `CRM_CLIENT_CUSTOM_DIR` is missing, assigned more than once in any form, not in the plain `NAME=` form, or relative;
  - one of those values does not resolve to exactly `$CRM_RUNTIME_DIR/{data,custom,client/custom}`.
- **Compose-resolved mounts.** After that static check, the same scripts run `docker compose ... config --format json`, which is authoritative, and parse it with `python3 -I` (standard library only). The bind sources for `/var/www/html/data`, `/var/www/html/custom` and `/var/www/html/client/custom` on both `crm-app` and `crm-daemon` must each be exactly one bind mount whose source is `$CRM_RUNTIME_DIR/{data,custom,client/custom}`. A source containing `..` is refused. The scripts refuse (exit 1, before any other `docker` call) on a mismatch, a missing mount, or a failure of `compose config`. The resolved config contains the secrets. It is piped straight into the parser, never printed or stored. The parser reports only service, mount target and source. As defence in depth, every `docker compose` call the scripts make runs with every variable named in `deploy/env.example` removed from its environment (`env -u`), so only the checked env file can supply them.
- **LAN access check.** Every script that can start or recreate a service (`up.sh`, `deploy_custom.sh` and `restore.sh`) then runs `scripts/check_access.py dev` (§7.6) on the same env file. If it refuses, the script exits 1 before it touches the stack: nothing is stopped, moved or started.
- **`up.sh`** is the only supported way to start or recreate the stack. It runs the dev guard, the env-file and path checks and the access check, and then `docker compose ... up -d --wait`, with any further arguments appended (for example `scripts/up.sh dev --force-recreate crm-app`).
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
# The same for the Apache access file (any apache_bad_*.conf):
CRM_ACCESS_CONF_UNDER_TEST=tests/unit/fixtures/apache_bad_remoteip.conf \
    python3 -m unittest discover -s tests/unit -p test_compose_policy.py
```

### 7.6 LAN access (CRM-D019)

Matt has authorised direct access to the dev CRM from the two internal networks, on port 8180 of the host's LAN address. For the dev environment, this replaces the loopback-only binding and the SSH tunnel. The real addresses exist only in the runtime env file. Git holds variable names, loopback and logic only. Below, `<CRM_BIND_IP>` stands for the env file's value.

#### How access is controlled

1. **Bind.** Docker publishes `crm-app` port 80 as `${CRM_BIND_IP}:8180` only. No other host address answers, `127.0.0.1` included. `crm-db` and `crm-daemon` publish nothing, so MariaDB stays off the host network.
2. **Source restriction, in Apache.** The host firewall is not available (standing rule: no iptables, ufw or nftables, so no `DOCKER-USER` chain either). The restriction is therefore enforced inside the stack. `deploy/apache/crm-access.conf` is mounted read-only into `crm-app` at `/etc/apache2/conf-enabled/crm-access.conf`, which `apache2.conf` includes server-wide. It holds:

   ```apache
   <Location "/">
       AuthMerging And
       Require ip 127.0.0.1 ::1 ${CRM_ALLOWED_SOURCES}
   </Location>
   ```

   - `<Location "/">` covers every URL path. Location sections are merged after `<Directory>` sections and `.htaccess`. With `AuthMerging And`, this `Require` is combined with the authorization that already applies there, which is the `Require all granted` that `apache2.conf` gives `/var/www/`. A request must pass both. The block can therefore only narrow access, and any authorization deny the image applies elsewhere still holds. The image's `.htaccess` has no access directives.
   - The image also denies `data/`, `application/`, `custom/` and `vendor/` with mod_rewrite `[F]` (checked by the PL in the running image). Those denies are not authorization, so authz merging does not affect them either way. They stay in force.
   - Any other source gets `403 Forbidden`.
   - `Require ip` tests the TCP peer address. `mod_remoteip` is not loaded and no header (`X-Forwarded-For` or any other) is trusted.
   - Loopback stays allowed for the container's own healthcheck (`curl http://127.0.0.1/`).
   - Compose passes `CRM_ALLOWED_SOURCES` to `crm-app` as a required variable. Apache expands `${CRM_ALLOWED_SOURCES}` from its process environment when it parses the configuration.
3. **Fail closed.** No layer opens access when the variable is wrong or missing:

   | Condition | Result |
   |---|---|
   | Bad bind, sources or site URL in the env file | `check_access.py dev` refuses (exit 1), and so do `up.sh`, `deploy_custom.sh` and `restore.sh`, before any `up` |
   | `CRM_BIND_IP`, `CRM_ALLOWED_SOURCES`, `CRM_SITE_URL` or any other env-file name exported in the shell | `up.sh`, `deploy_custom.sh`, `restore.sh` and `backup.sh` refuse (exit 1). Every `docker compose` call they make also runs without those names in its environment. |
   | `CRM_BIND_IP` or `CRM_ALLOWED_SOURCES` unset or empty in the env file | Compose refuses to create the stack (`${VAR:?}`) |
   | Variable undefined inside the container | Apache warns that it is not defined and leaves `${CRM_ALLOWED_SOURCES}` unexpanded. `mod_authz_host` rejects that as an invalid address, so the configuration does not parse and **Apache does not start**. The healthcheck then fails. |
   | Variable empty inside the container | The line reduces to `Require ip 127.0.0.1 ::1`, so **every remote client is denied**. The healthcheck still passes. |
   | Docker relays a connection instead of NAT-ing it (userland proxy) | Apache sees the `crm-net` gateway as the source. `check_access.py` refuses any source that overlaps `crm-net`, so the request is denied. |

4. **Policy tests (in the loop).** `tests/unit/test_compose_policy.py` covers the following, each with a broken fixture:
   - the single env-sourced bind (`app_single_env_bind`);
   - no mapping without a host IP and no `0.0.0.0` (`ports_host_ip`);
   - no literal non-loopback address in the Compose file (`no_literal_ip`), and none anywhere in `deploy/`, `scripts/` or `tests/` (`TestLiteralAddresses`);
   - the read-only, `crm-app`-only access-file mount (`access_conf_mount`) and the required `CRM_ALLOWED_SOURCES` (`access_sources_env`);
   - the conf file itself (`conf_deny_by_default`, `conf_authmerging_and`, `conf_no_grant`, `conf_no_remoteip`, `conf_no_indirection`). `conf_authmerging_and` requires the block to be exactly `AuthMerging And` plus the `Require` line. `conf_no_indirection` refuses `Define`, `UnDefine`, `Include`, `IncludeOptional`, `<Macro>` and `Use`, and any directive other than the `Require` line that names `CRM_ALLOWED_SOURCES` (`SetEnv`, `SetEnvIf`, `PassEnv`, `UnsetEnv`, a rewrite `[E=]`). A `Define` would take precedence over the environment when Apache expands `${CRM_ALLOWED_SOURCES}`.

   **Procedural check versus enforced controls.** `scripts/up.sh dev` (and `deploy_custom.sh` and `restore.sh`) run the access check before Compose. A raw `docker compose ... up` skips that procedural check entirely. Then only two controls remain in force: Compose's `${VAR:?}`, which refuses an unset or empty variable but not a wrong value, and the Apache restriction in `crm-access.conf`. Always start the stack with `scripts/up.sh dev`.

**To confirm at the operator stage.** None of the following could be run in the ForgeV2 loop, which has no Docker and no network:
- the Apache merge behaviour, and the fail-closed results for an undefined and an empty variable;
- that Apache in the pinned image sees the container's environment;
- that the container sees the real client source address for LAN traffic. Docker on the host runs with default settings: iptables NAT and the userland proxy.

The steps below confirm each of these.

#### The check: `scripts/check_access.py dev`

It uses the Python standard library only and takes the same `dev` guard as the shell scripts: exit 2 unless the argument is exactly `dev` and the runtime directory is named `dev`. It reads the env file as text and never sources it. It refuses (exit 1) unless all of the following hold:
- `CRM_BIND_IP` is exactly one IPv4 unicast address in dotted-quad form, inside RFC 1918 and inside one of the `CRM_ALLOWED_SOURCES` networks. It is not `0.0.0.0` (nor in `0.0.0.0/8`), not loopback, not multicast, reserved, broadcast or link-local, and not a public address.
- `CRM_ALLOWED_SOURCES` is one or more space-separated IPv4 CIDRs, each of the form `a.b.c.d/nn`, with no host bits set. Each one:
  - lies inside RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`);
  - is `/16` or longer;
  - does not overlap the `crm-net` subnet, which is read from `deploy/compose.json`.

  `0.0.0.0/0` is therefore always refused.
- `CRM_SITE_URL` is `http://<CRM_BIND_IP>:8180`, with the port explicit, no path other than `/`, no query and no user information. It is `http` because TLS is not implemented yet.
- Each of the three names is assigned exactly once, in the plain `NAME=value` form, and none of them is set in the process environment, because Compose would prefer the process environment to the env file. Do not export `CRM_BIND_IP`. The acceptance tests use `CRM_EXPECTED_BIND_IP` instead.
- The env file is `$CRM_RUNTIME_DIR/env`. If `CRM_ENV_FILE` names any other file, the check refuses, so the file it checks is the one the scripts give Compose.

It prints no value from the env file. Problems are reported by variable name and entry number only.

#### Operator steps: changing the existing install

These steps keep the database, `data/`, `custom/`, `client/custom/` and the backups. They are all bind mounts under `/srv/CRM/runtime/dev` that `up -d` does not touch. Run them from the delivered worktree at the PR head commit (§4). Do not run `down -v`, and do not delete anything under the runtime.

```sh
ENVF=/srv/CRM/runtime/dev/env
DC="docker compose -p crm-dev -f deploy/compose.json --env-file $ENVF"

scripts/backup.sh dev                        # 1. a fresh backup before the change
# 2. edit $ENVF (root, mode 0600): add CRM_BIND_IP and CRM_ALLOWED_SOURCES, and set
#    CRM_SITE_URL=http://<CRM_BIND_IP>:8180. Nothing else changes.
python3 scripts/check_access.py dev          # 3. must print "access settings OK"
$DC config --quiet                           # 4. Compose accepts the file (prints nothing)
ss -ltn 'sport = :8180'                      # 5. <CRM_BIND_IP>:8180 must be free (§6)
scripts/up.sh dev                            # 6. checks again, then recreates crm-app with the new
                                             #    port, env and access file; the data is in the bind mounts
# 7. The entrypoint sets siteUrl only at installation, so set it on the existing install:
$DC exec -T -u www-data -w /var/www/html crm-app php bin/command config:set siteUrl "http://<CRM_BIND_IP>:8180"
$DC exec -T -u www-data -w /var/www/html crm-app php bin/command clear-cache
```

8. **Check Apache.**
   - Run `$DC exec -T crm-app apache2ctl -t`. Expect `Syntax OK`.
   - Run `$DC exec -T crm-app env -u CRM_ALLOWED_SOURCES apache2ctl -t`. Expect a syntax error about an invalid IP address, which shows that an undefined variable stops Apache.
   - Run `$DC exec -T crm-app env CRM_ALLOWED_SOURCES= apache2ctl -t`. Expect `Syntax OK`, which means loopback only.

   None of these restarts the running server.
9. **Run AC9.** Run `CRM_EXPECTED_BIND_IP=<CRM_BIND_IP> python3 -m unittest discover -s tests/acceptance -k ac9 -v`. It checks the following:
   - `crm-app` is published on `<CRM_BIND_IP>:8180` only;
   - nothing answers on `127.0.0.1:8180`;
   - `crm-db` and `crm-daemon` publish nothing;
   - a request from `crm-daemon`, an unlisted source, gets `403`;
   - `crm-app` is still healthy over loopback.

   Then run the full acceptance suite with `CRM_BASE_URL=http://<CRM_BIND_IP>:8180`. Those requests come from the host itself. They are admitted because `check_access.py` requires `CRM_BIND_IP`, the host's own address, to be inside `CRM_ALLOWED_SOURCES`.
10. **Check from each authorised subnet.** From one workstation in each authorised subnet, open `http://<CRM_BIND_IP>:8180/`, log in, and follow a few links. They must stay on the LAN URL. This verifies routing and the return path for both subnets. On the host, `docker compose ... logs crm-app` shows each request's client address. It must be the workstation's own address, not a `crm-net` address, which confirms that Docker preserves the source address.
11. **Unauthorised source.** Request the CRM from a source outside both subnets and expect `403`, or no route. Use `curl -s -o /dev/null -w '%{http_code}\n' http://<CRM_BIND_IP>:8180/`.
    - The in-stack check in step 9 always applies.
    - If a LAN host outside both subnets is available, use it as well.
    - Never widen `CRM_ALLOWED_SOURCES` to run a test.
12. **Record the evidence** on the WO Issue, sanitised: no addresses. The CRM-001 evidence already recorded stays as it is.

To roll back, run `$DC up -d --wait` from a checkout of the PR #5 head commit, with the previous env file restored. That brings back the `127.0.0.1` binding. Then set `siteUrl` back the same way. This is the one raw `up` in this document: the PR #5 commit has no `scripts/up.sh` and no LAN access to check. This commit's Compose file cannot be used without `CRM_BIND_IP`.

**Changing the allowed sources or the access file later.** Edit the env file, or check out the new commit, then run `scripts/up.sh dev --force-recreate crm-app`. It runs the access check first. The access file is bind-mounted by inode, so a checkout that replaces the file reaches the container only when the container is recreated. The checkout must stay in place while the stack runs.

#### HTTPS for LAN access (assessment)

**Options assessed** (PL, 2026-11-10):
- **(A) TLS in `crm-app`'s own Apache.** `mod_ssl` is already loaded in the pinned image. A Git-controlled vhost conf for `:443` is mounted read-only. The certificate and key come from the runtime (root, `0600`, never in Git). `${CRM_BIND_IP}:8443:443` is published, and 8180 either redirects to HTTPS or is retired. This needs no new image and no new external code.
- **(B) A reverse-proxy container in `crm-dev`**, for example Caddy with `tls internal`, or Traefik. This adds a new external image, which needs a register entry and review. Caddy's internal CA root must then be installed on staff devices.
- **(C) A host-level proxy.** Rejected: the host is shared, and this is outside the CRM boundary.

**Certificate source.** ACME HTTP-01 is not possible on a LAN-only address. The candidates are:
- an organisation internal CA (preferred, if one exists);
- ACME DNS-01 for an internal hostname under the company domain. This needs DNS API credentials held on the host;
- self-signed. Browsers show warnings, so this is for dev only.

**Recommendation:** (A), with a hostname (not an IP) and a certificate from an internal CA or DNS-01. The PO must decide the hostname and the issuer. TLS is mandatory before real data (CRM-D019).

#### Residual risks

- **Plain HTTP.** Passwords and session cookies cross the LAN unencrypted. **TLS is mandatory before any real data** (CRM-PBI-008), and HTTPS is preferred for any authenticated use before then.
- **Admin interface.** Every host in the authorised subnets reaches the login page, and with it the administrator login. EspoCRM authentication is the only control inside those subnets.
- **Address-based trust.** A compromised or spoofing host inside an authorised subnet is admitted. The TCP handshake limits blind spoofing.
- **The host itself.** Processes on the host that connect to `<CRM_BIND_IP>` carry the host's own address. `check_access.py` requires that address to be inside an authorised subnet, so they are admitted, much as loopback access was before. Containers of other projects that are relayed through the `crm-net` gateway are refused. To confirm at the operator stage.
- **Docker networking changes.** If Docker's NAT mode changed, for example to `--iptables=false`, sources would appear differently. The overlap rule makes that fail closed for relayed traffic. Re-run step 9 after any Docker upgrade.
- **IPv6.** Only an IPv4 address is published. No IPv6 access exists or is checked.
