# crm-beta (CRM-007)

crm-beta is the first environment that holds customer data. It is installed only from a verified release bundle ([RELEASE.md](RELEASE.md)) by `scripts/deploy_release.sh`, as root, at the operator stage. It is never seeded with synthetic data.

## Architecture

```
PO's HAProxy (TLS for <CRM_BETA_HOSTNAME>)
      │  HTTP, from CRM_BETA_UPSTREAM_SOURCES only
      ▼
crm-beta-edge  (HAProxy, host network, binds CRM_BETA_BIND_IP:CRM_BETA_PORT, 403 for anyone else)
      │  HTTP to 127.0.0.1:CRM_BETA_APP_PORT
      ▼
crm-app  (EspoCRM; publishes only 127.0.0.1:CRM_BETA_APP_PORT)  ── crm-beta-net ──  crm-db, crm-daemon (publish nothing)
```

- **Compose project `crm-beta`** (`deploy/beta/compose.json`) is separate from `crm-dev`:
  - its own network `crm-beta-net`;
  - runtime `/srv/CRM/runtime/beta` (root, `0700`);
  - env file `/srv/CRM/runtime/beta/env` (root, `0600`). The names are in `deploy/beta/env.example`, which has no values.
- **crm-app** publishes only `127.0.0.1:${CRM_BETA_APP_PORT}`. `crm-db` and `crm-daemon` publish nothing.
- **crm-beta-edge** is HAProxy, pinned by digest (`haproxy@sha256:1c3568e5…`, registered in `security/EXTERNAL_CODE_REGISTER.yaml`).
  - It runs with `network_mode: host`, so `src` is the real peer, as user `haproxy`, with `read_only`, `cap_drop: [ALL]` and `no-new-privileges`.
  - It binds only `${CRM_BETA_BIND_IP}:${CRM_BETA_PORT}` and admits only `${CRM_BETA_UPSTREAM_SOURCES}`. Everyone else gets 403.
- **Edge configuration** is rendered from `deploy/beta/edge/haproxy.cfg.tmpl` by `scripts/check_access.py beta --render` into `/srv/CRM/runtime/beta/edge/haproxy.cfg`. Rendering is fail-closed. It refuses unless:
  - the sources are 1–4 RFC 1918 /32s;
  - the bind address is RFC 1918 (never `0.0.0.0`);
  - the ports are 1024–65535 and not 8180;
  - the hostname is a strict DNS name;
  - `CRM_SITE_URL` is exactly `https://<CRM_BETA_HOSTNAME>`;
  - the rendered text passes the edge policy.

### HTTPS and the trust boundary

TLS ends at the PO's HAProxy. EspoCRM must still generate `https://` links, so `deploy/beta/apache/crm-proxy.conf` sets `SetEnv HTTPS on` for **every** request and runs `RequestHeader unset X-Forwarded-Proto`. No client can choose the scheme.

- **The boundary: anything on the host's loopback is trusted.** crm-app publishes only on `127.0.0.1`, and only the edge connects to that port. Any process on the host that can reach `127.0.0.1:${CRM_BETA_APP_PORT}` talks to EspoCRM as if over HTTPS. Do not run anything on the beta host that you would not let do that.
- **Why the peer address is not used.** With Docker's userland proxy, Apache sees the bridge gateway, not loopback, as the peer. A peer-based test cannot tell the edge apart from anything else, so none is used and no subnet is pinned.
- **Modules.** `SetEnv` needs `mod_env` and `RequestHeader` needs `mod_headers`. The conf loads each one only if the image has not already enabled it (`<IfModule !env_module>` / `<IfModule !headers_module>` around `LoadModule`). If a module file is missing, Apache does not start and the deploy fails.
- **Enforcement.** `scripts/check_access.py beta` refuses a `crm-proxy.conf` that makes HTTPS conditional, keeps or sets `X-Forwarded-Proto`, or adds any other directive.
- The edge still sets `X-Forwarded-Proto: https` for trusted sources. Apache discards it.

## HAProxy upstream contract (configured by the PO)

- Terminate TLS for `<CRM_BETA_HOSTNAME>`.
- Forward plain HTTP to `<CRM_BETA_BIND_IP>:<CRM_BETA_PORT>`, from an address listed in `CRM_BETA_UPSTREAM_SOURCES` (each one a `/32`; at most 4).
- Send `X-Forwarded-For`. The edge keeps it only from trusted sources, deletes it from anyone else, and appends the upstream's own address.
- Keep the `Host` header as `<CRM_BETA_HOSTNAME>`.
- Health checks must come from a listed source too. Any other source gets 403.
- **Placeholders (documentation values only; the real values are RFC 1918 and live only in the runtime env file):**

  | Name | Placeholder |
  |---|---|
  | `CRM_BETA_BIND_IP` | `192.0.2.10` |
  | `CRM_BETA_PORT` | `8443` |
  | `CRM_BETA_UPSTREAM_SOURCES` | `192.0.2.20/32` |
  | `CRM_BETA_HOSTNAME` | `crm-beta.example.invalid` |
  | `CRM_SITE_URL` | `https://crm-beta.example.invalid` |
  | `CRM_BETA_APP_PORT` | `8280` |

  (`192.0.2.0/24` is a documentation range and would be refused by the check. That is deliberate.)

## Operator steps (as root)

1. **Prepare a clean runtime.** "Clean" means the runtime holds only the operator's env file, owned by root with mode `0600`. `deploy_release.sh` refuses any other entry unless `--upgrade` is given.
   ```sh
   install -d -m 0700 -o root -g root /srv/CRM/runtime/beta
   install -m 0600 -o root -g root /dev/null /srv/CRM/runtime/beta/env
   # Fill in every name in deploy/beta/env.example. Generate each secret on the host.
   # CRM_DB_DIR etc. are exactly /srv/CRM/runtime/beta/{db,data,custom,client/custom}.
   ```
2. **Get and verify the bundle** ([RELEASE.md](RELEASE.md)). Note its sha256 from the build host.
3. **Deploy.** Credentials are exported only in this subshell. `deploy_release.sh` strips every env-file name before it runs `up.sh` and `deploy_custom.sh`, which refuse to run with one set.
   ```sh
   ( export CRM_ADMIN_USERNAME=... CRM_ADMIN_PASSWORD=...          # the EspoCRM admin; never stored
     export CRM_BASE_URL=http://127.0.0.1:<CRM_BETA_APP_PORT>
     export CRM_PROVISION_KEY_FILE=/root/crm-beta-import-key.env   # must not exist yet
     scripts/deploy_release.sh beta crm-release-<short>.tar.gz --sha256 <hex> )
   ```
   In order, the deploy:
   - verifies the bundle;
   - refuses a non-clean runtime;
   - unpacks to `/srv/CRM/deploy/<short>`, root-owned and read-only;
   - creates `db`, `data`, `custom`, `client/custom` and `backups` (`0700`);
   - renders the edge config;
   - runs `up.sh beta` and `deploy_custom.sh beta`;
   - sets `siteUrl` and `phoneNumberInternational=false`, then reads `phoneNumberInternational` back with `php -r` + `var_export`. Only the PHP boolean `false` passes; the string `'false'` fails;
   - provisions the CRM-003 teams, roles and `ER Import` API user;
   - runs the beta-safe acceptance suite;
   - writes the sanitised `deploy-report-<stamp>.json` (`0600`).

   Without the four variables, provisioning and acceptance are skipped, and the report says so.
4. **Upgrade.** Add `--upgrade`. The `ER Import` user already exists, so no new key file is written. Point the suite at the existing key with `CRM_BETA_SAFE_KEY_FILE=/root/crm-beta-import-key.env`.
5. **Named users** come from `crm-load users` and `scripts/provision_users.py beta` (CRM-003, [ACCESS.md](ACCESS.md)).

### Beta-safe acceptance suite

`tests/acceptance/test_beta_safe.py` makes **GET requests only**. `tests/unit/test_beta.py` enforces this: it runs the suite against a fake, asserts that only GETs are sent, and statically checks the source.

- It reads `CRM_BASE_URL` and an API key from the file named by `CRM_BETA_SAFE_KEY_FILE`:
  - the file must be a regular file, not a symlink, with no group or other permission bits;
  - it holds exactly one `CRM_IMPORT_API_KEY=` or `CRM_LOAD_API_KEY=` line;
  - the key never comes from the command line.
- It checks:
  - the API answers;
  - every role in `config/access/roles.json` exists;
  - `phoneNumberInternational` is JSON `false`;
  - `siteUrl` is `https://…`;
  - no Account name contains the synthetic marker `SENTINEL-7f3a`, reported as a count only.

Run it by hand:
```sh
CRM_BASE_URL=http://127.0.0.1:<CRM_BETA_APP_PORT> CRM_BETA_SAFE_KEY_FILE=/root/crm-beta-import-key.env \
  python3 -B -m unittest discover -s tests/acceptance -p test_beta_safe.py -v
```
`deploy_release.sh` treats a skipped suite as a failure.

## Access control

Named users and roles are provisioned by `scripts/provision_access.py beta` and `scripts/provision_users.py beta` (CRM-003), with the same code and rules as dev. Beta is never seeded: `seed_synthetic.py` refuses https URLs, any port other than 8180, and `CRM_TARGET` set to anything but dev.

## Backup and restore

- **Backup.** `scripts/backup.sh beta` writes `/srv/CRM/runtime/beta/backups/crm-beta-<stamp>/` with umask 077 (directories `0700`, files `0600`). Each backup holds a database dump, `data/`, `custom/`, `client/custom/` and `SHA256SUMS`.
- **Restore.** `scripts/restore.sh beta <name>` restores into crm-beta. The current directories are moved aside to `<dir>.replaced-<stamp>`, not deleted.
- **Restore test.** `scripts/restore.sh beta --restoretest <name>` proves a backup restores without touching crm-beta:
  - **Before anything else** it:
    - verifies `SHA256SUMS` and completeness;
    - refuses unless the throwaway project is `crm-beta-restoretest`, with Compose file `deploy/beta/restoretest/compose.json`;
    - runs the isolation policy `check_access.py restoretest`: one `crm-db`, no published or exposed port, no bind mount, its own project-scoped volume and internal network;
    - requires the runtime to be exactly `/srv/CRM/runtime/beta-restoretest`, and refuses if it already exists.
  - **Then** it:
    - unpacks the file archives into that runtime;
    - loads the dump into the throwaway `crm-db` with a generated root password, kept in a `0600` file there and never printed;
    - prints fingerprints: live row counts for `account`, `contact`, `opportunity`, `call`, `meeting`, `task`, `email`, `user`, `team`, `role`, plus the file counts of `data`, `custom` and `client/custom`.
  - **Teardown.** It always tears down, also on failure: `docker compose -p crm-beta-restoretest … down -v` and removal of `/srv/CRM/runtime/beta-restoretest`. Nothing in it calls the `crm-beta` or `crm-dev` project.
  - **Leftovers.** If a killed run leaves the directory behind, run `docker compose -p crm-beta-restoretest -f deploy/beta/restoretest/compose.json down -v` and remove the directory, then re-run.
  - **Limit.** It restores the database and the files and counts them. It does not boot EspoCRM on the restored data.
- **Retention.** Retention is the PO's decision. Nothing prunes backups automatically; remove old `crm-beta-<stamp>/` directories by hand.

### Backup timer (operator-installed, with PO consent)

`deploy/beta/systemd/crm-beta-backup@.service` and `crm-beta-backup@.timer` are **templates**. Nothing in the repository installs them.

- **Instance name.** It is the 12-hex short commit of the deployed release. The service runs `/srv/CRM/deploy/<short>/scripts/backup.sh beta` as root, with `UMask=0077`, `NoNewPrivileges` and `ProtectSystem=full`, at 02:30 daily (`Persistent=true`, up to 15 minutes of random delay).
- **No environment.** The units set no environment: `backup.sh` refuses to run if an env-file name is set.

```sh
install -m 0644 -o root -g root /srv/CRM/deploy/<short>/deploy/beta/systemd/crm-beta-backup@.service \
    /srv/CRM/deploy/<short>/deploy/beta/systemd/crm-beta-backup@.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now crm-beta-backup@<short>.timer
systemctl list-timers 'crm-beta-backup@*'
# After an upgrade to <new>: disable the old instance, enable the new one.
systemctl disable --now crm-beta-backup@<short>.timer && systemctl enable --now crm-beta-backup@<new>.timer
```

## Data handling

Customer data stays under the root-only runtime. Reports and script output carry no secrets, addresses or names.
