# CRM-001-LAN, round 2: Engineer correction

- **Worktree:** `/srv/CRM/worktrees/CRM-001-LAN`. The expected HEAD is `49bbbe03c8f38adb717cef58c014f8ae5023288b` (your round-1 candidate). Confirm it first. Do not modify `.forge/`.
- The Work Order, the amendments and the scope allowlist are as in round 1 (directive quoted below). `DECISIONS.md` is in this run's allowlist; the PL authorised it in the round-1 brief.

## Blocking (confirmed by the reviewers, spot-checked by the PL)
1. **script-env-override.** `deploy_custom.sh` and `restore.sh` recreate `crm-app` with no access validation. `compose()` (`scripts/lib/common.sh`) only removes the four path variables from the environment. Compose prefers the process environment over the env file, so an exported `CRM_BIND_IP`, `CRM_ALLOWED_SOURCES` or `CRM_SITE_URL` changes exposure unchecked. Fix it so that:
   - `compose()` removes **every variable named in `deploy/env.example`** from the environment. Derive the list from that file, or keep one shared list with a test that it equals the file's names.
   - The env-var refusal in `require_runtime_paths` covers the same full list.
   - Every script that can start or recreate a service (`deploy_custom.sh`, `restore.sh`, and the wrapper in item 2) runs the access validation (`check_access.py` logic) and fails closed **before** any `up`.
   - Tests show the round-1 bypasses (an exported `CRM_BIND_IP` or `CRM_ALLOWED_SOURCES`, and an invalid env-file access value) give rc 0 against `49bbbe03c8f38adb717cef58c014f8ae5023288b` and are refused now.

## Advisory, fold in (small, same area)
2. **validator-not-enforced.** Add `scripts/up.sh dev`. It runs the dev guard, `require_runtime_paths` and the access validation, then `compose up -d --wait` (extra args such as `--force-recreate crm-app` are allowed).
   - BUILD.md must use it for every start.
   - State plainly in BUILD.md that a raw `docker compose up` skips the procedural check, and that only Compose's `${VAR:?}` and Apache remain in force then.
3. **bind-ip-not-private.** `CRM_BIND_IP` must be RFC 1918 **and** inside one of the `CRM_ALLOWED_SOURCES` networks.
4. **conf-policy-define-include.** The access-conf policy must also refuse:
   - `Define`, `UnDefine`, `Include` and `IncludeOptional`;
   - `SetEnv`/`SetEnvIf`/`PassEnv` affecting `CRM_ALLOWED_SOURCES`;
   - `<Macro>` and `Use`.

   Add a fixture for each.
5. **authz-merge (defence in depth).** Add `AuthMerging And` inside the `<Location "/">`, so any deny the image applies elsewhere still holds. The PL checked the running image: it denies `data/`, `application/`, `custom/` and `vendor/` with mod_rewrite `[F]`, which authz merging does not touch. Correct the comment and BUILD.md wording ("replaces"). Add a policy rule and a fixture requiring `AuthMerging And`.
6. **check-env-file-path.** `check_access.py` (and the shared helper) must refuse an env file other than `$CRM_RUNTIME_DIR/env`. Tests use a temporary runtime, so this still works there.
7. **https-investigation.** Add this PL assessment to BUILD.md as a new "HTTPS for LAN access (assessment)" subsection under the access section, adapting only the formatting. Do not implement TLS:

   > Options assessed (PL, 2026-11-10):
   > (A) TLS in crm-app's own Apache: `mod_ssl` is already loaded in the pinned image. A Git-controlled vhost conf for :443 is mounted read-only, the certificate and key come from the runtime (root, 0600, never in Git), and `${CRM_BIND_IP}:8443:443` is published, with 8180 redirecting to HTTPS or retired. No new image and no new external code.
   > (B) A reverse-proxy container (for example Caddy with `tls internal`, or Traefik) in `crm-dev`. This adds a new external image, which needs a register entry and review; Caddy's internal CA root must then be installed on staff devices.
   > (C) A host-level proxy. Rejected: shared host, and outside the CRM boundary.
   > Certificate source: ACME HTTP-01 is not possible on a LAN-only address. The candidates are an organisation internal CA (preferred if one exists); ACME DNS-01 for an internal hostname under the company domain (needs DNS API credentials held on the host); or self-signed (browser warnings; dev only).
   > Recommendation: (A), with a hostname (not an IP) and a certificate from an internal CA or DNS-01. The PO must decide the hostname and the issuer. TLS is mandatory before real data (CRM-D019).

## Tests to run and report
- `python3 -m unittest discover -s tests/unit -v`, with exact counts.
- `bash -n` on every script.
- Non-vacuity for each new rule and test.

Finish in the Engineer final message format.

## Architect directive: authorised LAN access change (amends the Work Order for this run)

Quoted verbatim, except that concrete addresses are **redacted** under the project's standing rule "no IPs in public repositories": `<LAN_HOST_IP>` is the DOCKER1 LAN address, and `<SUBNET_A>` and `<SUBNET_B>` are the two authorised internal /24 networks. The real values exist only in the runtime env file on the host.

> # CRM-001 — AUTHORISED LAN ACCESS CHANGE
>
> Matt has explicitly instructed that the Estate Research CRM must be directly accessible from both internal networks: `<SUBNET_A>`, `<SUBNET_B>`. **Target:** `<LAN_HOST_IP>:8180`
>
> This supersedes CRM-001's loopback-only access requirement for the development environment.
>
> ## Requirements
> 1. Preserve the existing running CRM, synthetic data, persistent storage and backup state.
> 2. Make the CRM accessible on port 8180 from both authorised subnets.
> 3. Restrict access to those two subnets. No access from other networks or the public internet.
> 4. Prefer binding specifically to `<LAN_HOST_IP>`, not `0.0.0.0`.
> 5. Enforce the source-subnet restrictions using an appropriate Docker-compatible mechanism. Binding to the host IP alone is insufficient.
> 6. Verify routing and return paths between both subnets.
> 7. Set EspoCRM's canonical site URL to the LAN-accessible address, preserving normal login and navigation.
> 8. Keep MariaDB inaccessible from the host network.
> 9. Do not modify unrelated containers, networks, applications or services.
> 10. Preserve the current PR #5 and its accepted test evidence.
>
> ## Security
> This is an internal LAN deployment, not public internet exposure. Investigate suitable HTTPS termination for LAN access. Prefer HTTPS for authenticated use; before introducing real customer data, TLS is mandatory. Do not weaken existing security controls or expose the administrative interface beyond the authorised networks. If the host's existing policy prevents enforcing the subnet restrictions safely, report the exact conflict rather than opening unrestricted access.
>
> ## Delivery
> Implement this as a narrowly scoped, documented CRM network-access change, with independent review where code or persistent configuration changes. Update the relevant CRM access requirements and tests. Do not silently rewrite the completed CRM-001 acceptance evidence. No unrelated Foundry, ForgeV2 or application development.

### Project constraints and facts supplied by the Project Lead
- **Standing rule (Product Owner): never use iptables, ufw or nftables.** Host firewall rules, including Docker's `DOCKER-USER` chain, are therefore not available. The source restriction must be enforced inside the CRM's own stack.
- **Standing rule: no secrets or IP addresses in the public repository.** Git may contain only variable names, loopback addresses and the logic. The bind address and the allowed source networks come from the runtime env file.
- Facts read from the running pinned `espocrm/espocrm:10.0.12` image (`crm-app`):
  - Loaded modules include `authz_core`, `authz_host`, `env`, `setenvif`, `rewrite`, `ssl`, `proxy` and `proxy_wstunnel`. **`remoteip` is not loaded.**
  - `/etc/apache2/sites-enabled/000-default.conf` is `<VirtualHost *:80>` with `DocumentRoot /var/www/html`.
  - `apache2.conf` has `<Directory /var/www/> … Require all granted`. The extra configs are in `/etc/apache2/conf-enabled/*.conf`.
  - `/var/www/html/.htaccess` has no `Require`, `Allow` or `Deny` directives.
  - The crm-app healthcheck curls `http://127.0.0.1/` inside the container.
- Docker on the host runs with default settings: iptables NAT and the userland proxy. For traffic arriving from the LAN at a published host-IP port, the container sees the real client source address. That is to be confirmed at the operator stage.
