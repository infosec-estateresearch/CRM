# CRM-001-C2, round 1: Engineer (second correction of CRM-001)

- **Work Order:** `work-orders/CRM-001.md` v1.3 (SHA-256 `6f4df2d8cd282ea69b0a8e58cd91a57cb716648c0bd669b46573b02516fc4cdc`). For this run it is amended by Architect directives 1 and 2 below.
- **Worktree:** `/srv/CRM/worktrees/CRM-001-C2`, branch `forge/CRM-001-C2`. The expected HEAD is `56ddd8b8a34e26c8beacc79e4e8afc21a69a3266`: the CRM-001 implementation plus correction C1 (`ccde740`), which is accepted. Confirm the HEAD first (role rule 2).
- Do not modify anything under `.forge/`.

## Task: the smallest correction that satisfies directive 2
1. **`scripts/deploy_custom.sh` must fail closed** if any path it works on could redirect an operation outside the intended runtime. That covers:
   - `$CRM_RUNTIME_DIR`;
   - `custom/`;
   - the managed parent `custom/Espo`;
   - the live tree `custom/Espo/Custom`;
   - the staging and replacement (old-tree) names.

   **Threat model.** On every start, the crm-app entrypoint chowns `custom/` to the container's `www-data` user, so code running as `www-data` can change that tree, including while the script runs. Checks that the container can race between check and use are not enough. Either make the sequence race-free, or stop `crm-app` and `crm-daemon` before the checks and the swap, then start them again and run the rebuild. Pick one and justify it in NOTES.

   **Expected checks:**
   - The canonical path of every component equals its expected lexical path under the canonical runtime, with no symlinks anywhere.
   - `$CRM_RUNTIME_DIR` and the directories above `custom/` are owned by the invoking user (root in operation) and are not group- or world-writable.
   - The staging and old-tree names must not already exist.

   **Deletion:** no unbounded recursive deletion. Any removal must stay on one filesystem and must never follow a symlink.
2. **Fail closed on divergence from the env file.**
   - Read `CRM_DATA_DIR`, `CRM_CUSTOM_DIR` and `CRM_CLIENT_CUSTOM_DIR` from `$CRM_ENV_FILE`, without sourcing or executing it.
   - Refuse to run unless each one canonically equals `$CRM_RUNTIME_DIR/{data,custom,client/custom}`.
   - Put the check in `scripts/lib/common.sh`. Call it from `deploy_custom.sh`, and also from `backup.sh` and `restore.sh` (one call each), because they rely on the same paths.
3. **Focused regression tests** in `tests/unit/`, using a temporary runtime and a stub `docker`, as the existing script tests do.
   - Plant a symlink in turn at each guarded component (runtime dir, `custom`, `custom/Espo`, `custom/Espo/Custom`, and a pre-existing staging/old name).
   - For each, assert a non-zero exit, and assert that an unrelated sentinel directory, the symlink's target, has an unchanged content hash.
   - Add a test for the group/world-writable refusal.
   - Add a divergence test for each of the three env variables, plus one for a missing variable.
   - Show non-vacuity: at least the symlink tests must fail against the C1 version of the script.
4. **Docs.**
   - Update `docs/BUILD.md` §7 for any change in operator sequence, for example if deploy now stops and starts the app.
   - Correct the §7.2 Admin-UI wording: the deployed tree is root-owned until the next container start.

Out of scope: do not touch the restore-source or CSV findings, or anything outside `deploy/**`, `custom/**`, `scripts/**`, `tests/**`, `docs/BUILD.md` and the README usage section.

## Constraints
No network, no Docker, no browser. Use only the standard library and POSIX tools. No secrets.

## Tests you must run and report
- `python3 -m unittest discover -s tests/unit -v`, with exact counts before and after.
- `bash -n` on every script.
- Non-vacuity evidence.

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
