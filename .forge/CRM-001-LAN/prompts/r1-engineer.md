# CRM-001-LAN, round 1: Engineer

- **Work Order:** `work-orders/CRM-001.md` v1.3. For this run it is amended by the Architect correction directives already implemented (C1 and C2, accepted) and by the LAN access directive below.
- **Worktree:** `/srv/CRM/worktrees/CRM-001-LAN`, branch `forge/CRM-001-LAN`. The expected HEAD is `b60eb1513dfc034a14abbdc2fc894e5bd7faa38a`, the accepted PR #5 head. Confirm it first. Do not modify `.forge/`.
- **Scope allowlist for this run:** `deploy/**`, `scripts/**`, `tests/**`, `docs/BUILD.md`, `README.md` (usage and access sections), and `DECISIONS.md` (one new entry). Do not change `custom/`, `work-orders/` or `security/`.

## Task: the narrowest change that satisfies the LAN access directive
1. **Bind (`deploy/compose.json`).**
   - `crm-app` publishes exactly one mapping, `"${CRM_BIND_IP:?…}:8180:80"`. Remove the loopback binding. Never `0.0.0.0`, and never a mapping without a host IP.
   - `crm-db` and `crm-daemon` publish nothing.
   - Everything else stays unchanged: digests, `crm-` names, mounts, no `container_name`, no external resources.
2. **Source restriction (Apache, inside `crm-app`).**
   - Add a Git-controlled config file, for example `deploy/apache/crm-access.conf`. Mount it **read-only** into `crm-app` only, at `/etc/apache2/conf-enabled/crm-access.conf`. This is the only mount besides the three runtime mounts.
   - The file restricts every URL path, server-wide, with `<Location "/">`, which is merged after `<Directory>` and so overrides `Require all granted`. It uses `Require ip 127.0.0.1 ::1 ${CRM_ALLOWED_SOURCES}`, or something equivalent and deny-by-default.
   - `CRM_ALLOWED_SOURCES` is passed to `crm-app` from the env file as `${CRM_ALLOWED_SOURCES:?…}`. Apache expands `${VAR}` from its process environment when it parses the config.
   - Loopback must remain allowed for the container's own healthcheck.
   - Do **not** enable `remoteip` and do not trust `X-Forwarded-For` or any other header. If the variable is undefined or empty, Apache must fail to start or deny everyone. It must never fail open. State which happens, and why.
3. **Validation (fail closed).** Add a stdlib-only check, for example `scripts/check_access.py dev`, or a helper in `scripts/lib`, with the same dev guard style. The operator runs it before `up`. It reads the env file as text and refuses unless:
   - `CRM_BIND_IP` is exactly one IPv4 unicast address that is not `0.0.0.0` and not loopback;
   - `CRM_ALLOWED_SOURCES` is one or more space-separated IPv4 CIDRs, each private (RFC 1918), each with a prefix of at least /16, and never `0.0.0.0/0`;
   - `CRM_SITE_URL` uses `CRM_BIND_IP` and port 8180.

   It must not print secrets.
4. **Tests.**
   - Update the Compose policy tests, replacing "every published port binds 127.0.0.1":
     - the single env-sourced bind for crm-app;
     - no unpublished-host-IP form and no `0.0.0.0`;
     - **no literal non-loopback IP address anywhere** in `deploy/`, `scripts/` or `tests/` fixtures, which keeps IPs out of Git;
     - the access-conf mount exists, is read-only and is only on crm-app;
     - the conf denies by default, has no `Require all granted` and does not use `remoteip`.
   - Add one broken fixture per new rule, with non-vacuity evidence.
   - Add unit tests for the validator's accept and refuse cases. Use documentation addresses (RFC 5737), never real ones.
   - Update `tests/acceptance` AC9 so that the expected host IP comes from an env variable, for example `CRM_BIND_IP`, instead of the hard-coded `127.0.0.1`. Add a live check that the app is **not** published on 127.0.0.1. Keep the existing AC structure; do not alter the earlier evidence.
5. **Docs.**
   - `deploy/env.example`: names only, adding `CRM_BIND_IP` and `CRM_ALLOWED_SOURCES`.
   - `docs/BUILD.md`: access section and operator steps. Include changing the site URL on the existing install (`bin/command config:set siteUrl …`, because the entrypoint sets `siteUrl` only at install), applying the change with `up -d` without data loss, and the unauthorised-source test approach.
   - `DECISIONS.md`: one entry for LAN access in dev. It should cover the reason, the enforcement layer (Apache, because of the host-firewall prohibition), the residual risks and that TLS is mandatory before real data.
   - Do not implement TLS in this run.

## Constraints
- No network, no Docker, no browser. Standard library only. No secrets, and no real IP addresses anywhere in the repository.
- You cannot confirm the Apache merge behaviour or the source-address preservation; mark both as "to confirm at the operator stage".

## Tests you must run and report
- `python3 -m unittest discover -s tests/unit -v`, with exact counts before and after.
- `bash -n` on every script.
- Non-vacuity evidence for each new rule.

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
