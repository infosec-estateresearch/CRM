# CRM-001-C2, round 2: Engineer correction

- **Worktree:** `/srv/CRM/worktrees/CRM-001-C2`. The expected HEAD is `37b2f31318cf38ed6fb62658a244fe45539eb9a4` (your round-1 candidate). Confirm it first.
- The Work Order and Architect directives 1 and 2 are as in round 1: `work-orders/CRM-001.md`, plus the directives quoted at the end of this brief. Do not modify `.forge/`.

## Consolidated correction: blocking findings (the reviewers confirmed them and the PL spot-checked them)
1. **env-divergence-shell-override.** Compose takes `CRM_DATA_DIR`, `CRM_CUSTOM_DIR`, `CRM_CLIENT_CUSTOM_DIR` (and `CRM_DB_DIR`) from the process environment before `--env-file`. `require_runtime_paths` checks only the file. With `CRM_CUSTOM_DIR=/etc` exported, `deploy_custom.sh dev` returns rc 0, and `compose config` resolves the custom source to `/etc`. Make it fail closed:
   - `require_runtime_paths` refuses to run if any of the four variables is set in the process environment;
   - as defence in depth, `compose()` runs `docker compose` with those variables removed from its environment (`env -u …`).
2. **env-divergence-colon-form.** Compose's env-file parser also accepts `NAME: value`, and the later line wins. The once-only count regex (`common.sh` line 62) matches only `NAME=`, so a second `CRM_CUSTOM_DIR: /etc` line gets through. Make it fail closed:
   - Count **every** line that could assign the name in any form: optional leading whitespace, optional `export`, the name, then any non-identifier character. There must be exactly one such line, and it must be the plain `NAME=<abs path>` form. Refuse anything else.
   - Also check what Compose itself resolves, which is authoritative:
     - in `deploy_custom.sh`, `backup.sh` and `restore.sh` (through the shared helper), run `compose config --format json` after the static check;
     - parse it with `python3 -I` (standard library only);
     - require the bind sources for `/var/www/html/data`, `/var/www/html/custom` and `/var/www/html/client/custom`, on both `crm-app` and `crm-daemon`, to equal `$CRM_RUNTIME_DIR/{data,custom,client/custom}`;
     - fail closed on any mismatch, a missing mount, or a failure of `compose config`.

     Never print the resolved config: it contains secrets. Discard it after parsing. The stub `docker` in the tests must emit a representative `config --format json` document.

## Advisory findings to fold in (small, same area)
3. **remove-tree-guard-untested.** Add tests that fail if `remove_tree`'s symlink refusal or `--one-file-system` is removed. Show the mutation evidence.
4. **host-uid-toctou / host-uid33-race.** After stopping the containers, close the remaining race from a host process with the container's uid:
   - before the authoritative checks, make `custom/` and `custom/Espo` owned by the invoking uid and not group- or world-writable;
   - use `chown -h` and `chmod` non-recursively, on paths that you have confirmed are real directories, and confirm again afterwards;
   - then verify owner and mode as part of `check_paths`.

   The entrypoint re-owns them on the next start, which is expected. Record this in BUILD.md "Path safety". Where the tests cannot chown, test the mode part and note the limit.

Out of scope: the restore-source, restore-extraction and CSV findings, which are recorded for later. Keep the change minimal.

## Tests to run and report
- `python3 -m unittest discover -s tests/unit -v`, with exact counts.
- `bash -n` on every script.
- Non-vacuity for each new test, run against round-1 candidate `37b2f31318cf38ed6fb62658a244fe45539eb9a4` (shell override and colon form must give rc 0 there and rc != 0 now).

Finish in the Engineer final message format.

## Architect correction directive (amends the Work Order for this run)

This run is the bounded correction of CRM-001 that the Architect required in their review of PR #3. The directive is quoted verbatim below. Where it conflicts with the Work Order (in particular, the WO's "`./custom` is mounted read-only at `/var/www/html/custom`" and "Data is bind-mounted from `/srv/CRM/runtime/dev/{db,data}`"), the directive governs. The rest of the Work Order applies unchanged.

> # CRM-001 — Architect Review of PR #3
>
> **Verdict: TARGETED CORRECTION REQUIRED**
>
> Reviewed head: 426bb86571dfc5ff73b67bbacd8f34d1a539d0a5
> Engineering candidate: 46e0a1852080faa94d5c0d9332d5d5c14d0cf6c5
>
> ## Required correction
>
> EspoCRM 10 recommends mounting its persistent directories individually, rather than mounting the entire application directory at /var/www/html.
>
> The current Compose file mounts CRM_DATA_DIR over /var/www/html and then overlays custom/ read-only.
>
> This creates a credible first-start failure risk and differs from the documented EspoCRM 10 deployment arrangement.
>
> Reference: https://docs.espocrm.com/administration/docker/installation/
>
> Before deployment:
>
> 1. Reconcile the Compose mounts with EspoCRM 10's documented persistence requirements.
> 2. Preserve the CRM's isolated data directories, pinned images, localhost-only port and crm-prefixed resources.
> 3. Keep backup/restore scripts, relevant tests and BUILD.md consistent with the corrected layout.
> 4. Verify the implications of read-only customisations for installation and rebuild.
> 5. Re-run the relevant unit tests and independent assurance checks.
>
> Use the existing bounded CRM-001 repair process. Do not create a new work order or expand scope.
>
> ## Other observations
>
> The duplicate-detection classes use EspoCRM's documented extension mechanism, but the actual warnings remain unverified until integration testing.
>
> The arbitrary restore source and CSV formula-handling issues are not blockers for synthetic testing. Record them for correction before real customer data is introduced.
>
> Do not merge PR #3 or deploy this version.

### Reference facts supplied by the Project Lead (from public upstream sources, 2026-11-10)

EspoCRM's Docker documentation (URL above), Compose example, `espocrm` service:
```
    volumes:
      - espocrm-data:/var/www/html/data
      - espocrm-custom:/var/www/html/custom
      - espocrm-custom-client:/var/www/html/client/custom
```
Its "Migration to EspoCRM 10" section: "Starting from v10.0, mounting the entire /var/www/html directory is no longer required." For local directories it replaces `./espocrm:/var/www/html` with `./espocrm/data:/var/www/html/data`, `./espocrm/custom:/var/www/html/custom` and `./espocrm/client/custom:/var/www/html/client/custom`, and says "Repeat this for all EspoCRM service containers". The daemon in the Docker Run example uses `--volumes-from espocrm`.

Image source, github.com/espocrm/espocrm-docker, default branch, `latest/apache/` (its Dockerfile sets `ENV ESPOCRM_VERSION 10.0.12`). This was read from the source repository, **not** from the pinned image digest, so it must be confirmed at the operator stage. sha256 of the files read: Dockerfile `ce64689b…700b`, docker-entrypoint.sh `9f0b7032…20e2`, entrypoint-utils.sh `f4199a41…5ba5`, docker-daemon.sh `d7b6aac3…3d85`.

- Dockerfile: the application is copied into `/var/www/html` in the image, owned by root. Then `chown -R www-data:www-data ./data ./custom ./client/custom`. `ENTRYPOINT [ "docker-entrypoint.sh" ]`.
- docker-entrypoint.sh starts with `set -euo pipefail`.
- `isLegacy()` is true when `/var/www/html` itself is a mount point. In legacy mode the entrypoint warns "LEGACY INSTALLATION METHOD DETECTED … Do not mount /var/www/html directly … No further EspoCRM upgrades will be available". If `bin/command` is missing (an empty bind mount over `/var/www/html`), it prints "Container startup aborted" and runs `exit 1`.
- Non-legacy start: if `bin/command config:get isInstalled` is true it runs `actionMigrate`; otherwise `actionInstall`.
- `actionInstall`: clears `data/cache`, `config:populate`, sets the database config, then `setPermissions`, `bin/command rebuild`, `create-admin-user`, `set-password`, `siteUrl`, `populate-scheduled-jobs`, `app-check`, then sets `isInstalled=true`.
- `actionMigrate`: `clear-cache`, `migrate`, then `setPermissions`.
- `setPermissions() { chown -R www-data:www-data ./data ./custom ./client/custom; }`. It runs under `set -e`, on every start (install and migrate).
- docker-daemon.sh: `exitIfNotReady` (`bin/command app-check`, otherwise "Waiting for the main container to be ready..." and exit 0), then `exec php /var/www/html/daemon.php`.

## Architect correction directive 2 (amends the Work Order for this run; it follows directive 1 above)

Quoted verbatim:

> # CRM-001 PR #4 — Architect Review
>
> **Verdict: CONDITIONALLY ACCEPTED for operator-stage preparation. One safety correction required before executing the root-run deployment script.**
>
> Exact reviewed head: 56ddd8b8a34e26c8beacc79e4e8afc21a69a3266
>
> The EspoCRM 10 mount correction is accepted.
>
> ## Required immediate action
>
> Fix the symlink/path-traversal risk in `scripts/deploy_custom.sh`.
>
> The script must fail closed if its runtime path, managed parent, live tree, staging destination or replacement destination can redirect operations outside the intended CRM runtime.
>
> Use appropriate canonical-path, symlink and directory-ownership checks. Avoid unsafe recursive deletion. Verify the protection with a deliberately planted symlink and confirm that an unrelated sentinel directory remains unchanged.
>
> Make the smallest possible correction to the existing CRM candidate. Add focused regression tests.
>
> Also verify that the runtime environment paths used by the deployment script match the configured Compose mount paths. Fail closed on divergence.
>
> Do not expand this into a framework improvement.
>
> ## Scope
>
> CRM only. Synthetic data only. The unrelated restoration-source, CSV formula and ForgeV2 lifecycle improvements remain recorded for later resolution.
