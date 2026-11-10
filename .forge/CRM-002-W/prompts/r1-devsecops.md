# CRM-002-W, round 1: DevSecOps review

- **Worktree:** `/srv/CRM/worktrees/CRM-002-W`. It is read-only; don't touch any other path.
- **Candidate SHA:** `47a8b12e01cb5f04a5f2b1118053dd588363016d`
- **Base SHA:** `8389cab297fc1f1efc72bcd082f26a330c293c60` (CRM-002-V DELIVERED, PR #25)
- **Scratch directory:** `/srv/CRM/worktrees/.forge-scratch/CRM-002-W`

Assess the candidate against the Work Order below, independently and according to your role. This is a small root-run wrapper change.

**Blocking:**
- any path where `reconcile` reads a snapshot that is not sealed or whose manifest does not verify;
- any path where the waiver or any file outside the manifest root is copied into the container input;
- any symlink or path-traversal route;
- any weakening of an existing `migrate.sh` guard.

**PL decisions on the engineer's choices:**
- (a) `sealed` stays on the whole `<id>`. This is stricter, and accepted.
- (b) A legacy snapshot with only `run/` and no `input/` is accepted. That layout is real, and the decision is accepted.

The sandbox has no root, Docker or network.

## Work Order (verbatim, `work-orders/CRM-002-W.md` v1.0 on main)

WO: CRM-002-W
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-002-V
BROWSER: no

# CRM-002-W — `reconcile` accepts the legacy-mode snapshot layout

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10 (Issue #9). This follows up the second L3.
- **Parent:** CRM-PBI-005, part 1.

## Problem (operator, 2026-11-10)
CRM-002-S changed the layout of soap-legacy runs. `migrate.sh` runs the container with `--out /out/run` and copies the waiver to `input/`. The sealed snapshot therefore looks like this:
- `<id>/input/waiver.json`
- `<id>/run/manifest.json`
- `<id>/run/objects/…` and the other run files

`finish` verifies `<id>/run`. But `cmd_reconcile` runs `verify-manifest "$SNAPSHOTS/$id"`, which means `<id>/manifest.json`, and copies the whole `<id>` as `--snapshot`. So `migrate.sh reconcile <id>` refuses every legacy-mode extract with "manifest verification failed: no manifest". The client-credentials layout, with its manifest at `<id>/manifest.json`, is unaffected.

## Change
1. **`scripts/migrate.sh`: add `snapshot_root <id>`.** It returns the directory that holds `manifest.json`, which is exactly one of:
   - `<id>`, when `<id>/manifest.json` exists, `<id>/run` does not, and there is no `input/` (the client-credentials layout);
   - `<id>/run`, when `<id>/run/manifest.json` exists, `<id>/manifest.json` does not, and the top level holds only `input/` and `run/` (the legacy layout).

   Anything else is refused, including both layouts at once or extra top-level entries. `cmd_reconcile` uses it for `sealed` and `verify-manifest`, and copies **only** that directory as `input/current` (or `input/previous`). The waiver is not copied.
2. **The run-id rule is unchanged:** inputs must still be `*-extract` snapshots.
3. **Tests**, in the style of the existing script tests:
   - both layouts reconcile;
   - mixed, extra or missing entries are refused;
   - the previous-snapshot argument works with either layout;
   - every existing test still passes.
4. **Docs:** `docs/MIGRATION.md` describes the two snapshot layouts. Downstream consumers, such as the CRM-006R importer, must locate `manifest.json` in the same way.

## Scope
- **Allowlist:** `scripts/migrate.sh`, `tests/migrate/**`, `docs/MIGRATION.md`, `.forge/CRM-002-W/**`.
- **Excluded:** everything else, Salesforce access, and real data.

## Acceptance criteria
- **AC1:** unit tests pass with non-vacuity.
- **AC2:** gitleaks is clean.
- **Operator stage:** `migrate.sh reconcile <the second L3 id>` produces `report/reconciliation.json`, sealed. Then `SOURCE_EXTRACTED` is reported on #9 with counts only.
