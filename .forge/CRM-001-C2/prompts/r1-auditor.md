# CRM-001-C2, round 1: Auditor review

- **Worktree:** `/srv/CRM/worktrees/CRM-001-C2`. Read-only; do not touch any other path.
- **Candidate SHA:** `37b2f31318cf38ed6fb62658a244fe45539eb9a4`
- **Base SHA:** `56ddd8b8a34e26c8beacc79e4e8afc21a69a3266` (the CRM-001 implementation plus correction C1; the Work Order's own base is `096748c8b4dfdab22070e1e802c6614fdf54465c`)
- **Scratch directory:** `/srv/CRM/worktrees/.forge-scratch/CRM-001-C2`

Assess the candidate against the Work Order below, as amended by the Architect correction directives 1 and 2 that follow it, independently and according to your role.

## Work Order (verbatim, `work-orders/CRM-001.md` at the base SHA)

WO: CRM-001
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main
BROWSER: yes

# CRM-001 — Firms, branches and contacts baseline (EspoCRM, synthetic data)

- **Version:** v1.3, 2026-11-09. v1.2 added the learning-platform access field (R3). v1.3 adds the `crm-` naming rule (R27, CRM-D018): services `crm-app`, `crm-daemon` and `crm-db`, and network `crm-net`. AC9 names these. Nothing else changes.
- **Status:** DRAFT. It needs CGPT's exact-version approval on its GitHub Issue, naming this path and the commit that contains it. It must **not run** while ForgeV2 sandbox acceptance on DOCKER1 is BLOCKED (forgev2#5).
- **Parent PBI:** CRM-PBI-001.
- **Governing FOUNDRY:** `5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0`.
- **Engine:** ForgeV2 `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, plugin 0.3.0, from `/srv/forgev2/plugin`, run as `forgev2-pl`.
- **`KNOWN_COMMIT`:** the commit named in the approval comment. The Orchestrator passes it at dispatch, because FOUNDRY forbids a WO naming the commit that contains it.

## Outcome

A pinned, isolated EspoCRM dev environment, defined entirely in this repository. It supports:
- firms with a head office and branches;
- same-name branches;
- contacts at firms;
- search, duplicate warnings, backup, restore and export.

It is demonstrated with deterministic synthetic data. No real data and no Salesforce access.

## Change

1. **`deploy/compose.json`** (JSON is valid Compose YAML) and **`deploy/env.example`** (variable names only):
   - `crm-app`: `espocrm/espocrm:10.0.12@sha256:b50245d1e291b2636116b0396ce0d06018ffcded6a6c61c7af2420443a20f3ec`.
   - `crm-daemon`: the same image with entrypoint `docker-daemon.sh`.
   - `crm-db`: `mariadb:11.4.13@sha256:d1891ede5a559f1086f55053bb8cc1569b0298338c4d72d71725a7f74f6ba620`.
   - One project network, `crm-net`, `172.16.10.0/24`. `crm-app` publishes only `127.0.0.1:8180:80`. `crm-db` has no `ports`.
   - **Naming (CRM-D018):** Compose project `crm-dev`. Every service, network and named volume key starts with `crm-`. There is no `container_name`; Compose generates instance names such as `crm-dev-crm-app-1` and `crm-dev_crm-net`.
   - No `external` networks or volumes. Data is bind-mounted from `/srv/CRM/runtime/dev/{db,data}`, given in the env file.
   - `./custom` is mounted read-only at `/var/www/html/custom`.
   - Healthchecks on `crm-app` and `crm-db`.
2. **`custom/Espo/Custom/Resources/…`** (EspoCRM metadata, layouts, i18n `en_US`), and PHP only where metadata cannot do the job:
   - **Account self-link:** a `parent` link (head office) and its inverse `branches`, with a Branches relationship panel on the firm record.
   - **Account `type` options become the tiers:** Tier 1, Tier 2, Tier 3, Tier 4, Tier 5, Prospect, Closed/Ceased Trading.
   - **Account `industry` options:** Solicitor, Other Legal Service, Barrister, Accountant, Other.
   - **New varchar field `practiceManagementSystem`.**
   - **New enum field `learningPlatformAccess`:** No, TLP, Full Access, E-Course. It appears on the detail view and as a list filter.
   - The billing address is the firm address and is shown on list and detail views.
   - **Account duplicate check:** name plus postcode.
   - **Contacts:** the native Contact–Account link. Duplicate check on email address.
3. **`scripts/seed_synthetic.py`**, Python standard library only:
   - Deterministic for a given `--seed`.
   - Creates: 1 parent with 34 branches; 24 parents with 1–8 branches each; 40 stand-alone firms; 2 branches sharing one base name; every value of tier, industry and learning-platform access used at least once; about 600 contacts at `@example.test`; 5 near-duplicate firm or contact pairs, kept back for the duplicate test.
   - Writes through the EspoCRM REST API. HTTP goes through an injectable transport, so it can be unit-tested with no network.
4. **`scripts/backup.sh`, `restore.sh`, `export.sh`:**
   - Database dump plus `data/` into `/srv/CRM/runtime/dev/backups/`, and restore from it.
   - CSV export of Accounts and Contacts through the API.
   - Each one refuses to run unless its target environment is `dev`.
5. **`tests/unit/`**, with no stack and no network:
   - **Seeder:** determinism and the shape described in item 3.
   - **Compose policy:** `crm-db` has no `ports`; every published port binds `127.0.0.1`; no `external` networks or volumes; every `image` has `@sha256:`; the images equal the register's digests; every service, network and named volume key starts with `crm-`; no service sets `container_name`.
   - **Metadata:** every JSON file parses, and the link and field names are consistent between entityDefs, layouts and i18n.
   - **Scripts:** the shell scripts pass `bash -n`, and the `dev` guard refuses other targets.
6. **`tests/acceptance/`**, which needs the running dev stack: one test per live acceptance criterion below. It reads the base URL and the admin credential from the environment and never stores them.
7. Update **`docs/BUILD.md`** (usage) and **`security/EXTERNAL_CODE_REGISTER.yaml`** (usage confirmed). Add a **README** usage section.

## Scope

**Allowlist:**
- `deploy/**`, `custom/**`, `scripts/**`, `tests/**`
- `docs/BUILD.md`, `security/EXTERNAL_CODE_REGISTER.yaml`
- the usage section of `README.md`
- ForgeV2's own delivery record, `.forge/CRM-001/**`

**Excluded:**
- enquiries, activities, email, Outlook, the ERic adapter, Salesforce access of any kind, real data, Frappe;
- TLS, LAN binding, production;
- new dependencies beyond the two registered images and the Python standard library;
- paid extensions; editing EspoCRM core;
- any path outside this repository, and any other service on the host.

## Roles and verification

**In the ForgeV2 loop:** existing roles, sequence and limits are unchanged. Specialists have no network, no Docker and no browser.
- **Engineer:** implements items 1–7 and runs the unit tests. Must not download anything; EspoCRM conventions come from the role's own knowledge, and that limitation is recorded in the delivery record.
- **Auditor:** scope and allowlist; the policy tests can fail (each one fails against a deliberately broken fixture); no core edits.
- **Tester:**
  - runs `python3 -m unittest discover -s tests/unit -v`, plus a `bash -n` check of every script;
  - cannot drive a browser on this host, so it returns browser assessment **inconclusive**, with reason.
- **DevSecOps:** gitleaks; no secret values; `env.example` holds names only; Compose isolation; digests match the register; no new dependency.

**Expected loop outcome:** ESCALATED, for the browser only, with every other review PASS. Under CRM-D013 this is acceptable as an intermediate result. It is **not** acceptance. Any other ESCALATED or BLOCKED result goes back to the Architect.

**After the loop:**
- The PL pushes `forge/CRM-001`; Matt opens the PR.
- The **operator stage**, with Matt's authorisation: deploy from the exact PR head commit (`docs/BUILD.md` §4), seed, run `tests/acceptance`, and record the evidence on the WO Issue (sanitised).
- **Product acceptance:** Matt's walkthrough, then merge.
- Defects found at deployment stay open, are fixed under a follow-up WO, and are retested before acceptance.

## Acceptance criteria

**In the loop:**
1. **AC1:** the unit tests pass. Each policy test fails when its rule is broken (Auditor checks).
2. **AC2:** gitleaks is clean, no secret values are present, and the digests match the register.

**Operator stage (synthetic data):**
3. **AC3:** every seeded firm exists. Every branch shows its parent, and the 34-branch parent lists all 34 in its Branches panel.
4. **AC4:** the two same-name branches save as distinct records, with no merge or rename.
5. **AC5:** contacts appear on their firm. The tier and industry filters return the seeded counts.
6. **AC6:** each of 10 seeded probes (partial firm name, postcode, phone, contact email, surname) returns the right record in the top 5 results.
7. **AC7:** creating each held-back near-duplicate raises EspoCRM's duplicate warning.
8. **AC8:** backup, destroy the stack, restore, and every record returns; restore time is recorded. The CSV export is complete against the seeded counts.
9. **AC9:** checking only the project's own resources, `docker network inspect crm-dev_crm-net` lists only `crm-dev-crm-*` containers, `crm-db` has no host port, `crm-app` binds `127.0.0.1` only, and the project uses no external networks or volumes. A shared-host conflict is reported, not remediated.

**Product acceptance:**
10. **AC10:** Matt's walkthrough of AC3–AC7 in the browser over an SSH tunnel is recorded on the Issue.

**Fallback rule:** if AC3–AC7 need more than about 300 lines of ER code, report it, and the Frappe fallback is reassessed (CRM-D010).

## Prerequisites (entry gates)

1. ForgeV2 sandbox acceptance on DOCKER1 is recorded by Matt.
2. The bootstrap commit is on `main`, and the CRM-001 Issue exists.
3. CGPT's exact-version approval of this file is recorded on the Issue.
4. `forgev2-pl` has its Claude login, Git identity and write access to this repository with its key (the `git push --dry-run` at bootstrap is the check).
5. **For the operator stage only:** Matt authorises the operator and the dev environment `/srv/CRM/runtime/dev`.

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
