# CRM-001-C1, round 1: Engineer (correction of CRM-001)

- **Work Order:** `work-orders/CRM-001.md` v1.3, SHA-256 `6f4df2d8cd282ea69b0a8e58cd91a57cb716648c0bd669b46573b02516fc4cdc`, approved at `096748c8b4dfdab22070e1e802c6614fdf54465c` (Issue #2). It is amended for this run by the Architect correction directive below.
- **Worktree:** `/srv/CRM/worktrees/CRM-001-C1`, branch `forge/CRM-001-C1`. The expected HEAD is `426bb86571dfc5ff73b67bbacd8f34d1a539d0a5`, which is the CRM-001 implementation (`46e0a18`) plus its delivery record. Confirm the HEAD first (role rule 2).
- Do not modify anything under `.forge/`.

## Task: one consolidated correction
Correct the existing implementation so that it satisfies the directive. Change only what the correction needs. Stay within the WO's scope allowlist (`deploy/**`, `custom/**`, `scripts/**`, `tests/**`, plus the `docs/BUILD.md`/README updates the WO already allows).

1. **Compose mounts (`deploy/compose.json`).** No service may mount `/var/www/html` itself.
   - `crm-app` and `crm-daemon` both get exactly three bind mounts:
     - `/var/www/html/data`
     - `/var/www/html/custom`
     - `/var/www/html/client/custom`
   - Each source is a required env variable naming an absolute directory under `/srv/CRM/runtime/dev`. Keep `CRM_DATA_DIR` for `data`, and add one variable each for `custom` and `client/custom`.
   - Keep `crm-db` as it is.
   - Keep the pinned digests, the `127.0.0.1:8180` binding, the `crm-` names, no `container_name`, and no external or named volumes.
2. **Read-only customisation.**
   - The upstream entrypoint chowns `./custom` and `./client/custom` on every start, under `set -e` (see the facts below). A read-only `custom/` mount will therefore break installation and every restart. Mount the runtime directories read-write instead.
   - Keep Git as the source of truth for the customisation. Add a dev-only script under `scripts/` (it must refuse non-dev targets, like the others) that:
     - deploys the repository's `custom/Espo/Custom/` into the runtime `custom` directory deterministically, so that files removed from Git are removed from the runtime too;
     - then runs EspoCRM's clear-cache/rebuild inside `crm-app` if it is running.
   - Do not override the image entrypoint.
   - Explain the decision and its consequences in `docs/BUILD.md` §7, for installation, rebuild and restart. Admin-UI changes to custom metadata are overwritten by the next deploy. Git remains authoritative.
   - Make sure the operator sequence orders the first deploy correctly against the first start: say whether customisation is deployed before or after the first `up`, and why.
3. **Backup and restore.** These must cover the new layout:
   - the database;
   - `data/`;
   - the runtime `custom/` and `client/custom/`.
   Restore must put each back in its own place, and keep the existing move-aside behaviour. Do **not** fix the arbitrary-restore-source or CSV-formula findings in this run; the Architect deferred them.
4. **Tests.**
   - Update the Compose policy tests for the new layout:
     - no mount at `/var/www/html`;
     - the three required targets on both EspoCRM services, with env-sourced binds;
     - none of the three is read-only.
   - Add a broken fixture under `tests/unit/fixtures/` for each new rule, and show that each fixture fails.
   - Add tests for the deploy script's dev-only refusal and its deterministic copy, where this can be done without Docker.
5. **Docs.** Update `deploy/env.example` (names only), `docs/BUILD.md` §7 and the README usage section to match.

## Constraints
- You have no network, no Docker and no browser. Do not download anything.
- The image behaviour you rely on comes only from the reference facts below. Mark it in NOTES as "from the upstream source, to be confirmed at the operator stage".
- Use only the Python standard library and POSIX tools, with no new dependencies. Do not edit EspoCRM core. Put no secret values anywhere.

## Tests you must run and report
- `python3 -m unittest discover -s tests/unit -v`, with exact counts before and after the change.
- `bash -n` on every script under `scripts/`.
- The non-vacuity evidence for each new fixture.

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
