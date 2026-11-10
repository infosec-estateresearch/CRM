# CRM-006R, round 3: Engineer correction

- **Worktree:** `/srv/CRM/worktrees/CRM-006R`. Your round-2 work is uncommitted; continue from it. Do not modify `.forge/`.
- **Status reporting:** report `STATUS: completed`, with "Known gaps" if any.
- **Time box:** return by about 15 minutes.

## Blocking, found by the PL against the real sealed outputs on DOCKER1 (structure and keys only)
`open_reconciliation` applies the snapshot layout rule, but the **real reconcile run directory** has a third layout, and `locate()` refuses it with `snapshot_layout_unknown`:
- `<id>-reconcile/report/manifest.json`
- `<id>-reconcile/report/reconciliation.json`
- `<id>-reconcile/report/reconciliation.md`

The top level holds only `report/`. The manifest's `files` keys are relative to `report/`: exactly `["reconciliation.json", "reconciliation.md"]`. Its other keys are `mode: "reconcile"`, `previous` (bool), `snapshot_status` and `tool`.

**Fix:**
1. **Locate the reconcile manifest separately.** A reconcile run is `<id>/report/manifest.json` when the top level is exactly `{"report"}`, `report/` is a real directory, and the `<id>` name ends in `-reconcile`. Verify that manifest. Require `mode == "reconcile"` and `reconciliation.json` in `files`, as a key relative to `report/`.
2. **Bind the reconciliation to the snapshot** (your known gap). `reconciliation.json` has a `snapshot` object with these keys: `contract_sha256`, `contract_version`, `overlap_seconds`, `passes`, `quiet`, `status` and `t_start`. The extract manifest has `t_start`, `status`, and `contract.sha256` / `contract.version`.
   - Refuse (`reconciliation_snapshot_mismatch`) unless `t_start`, `status`, `contract_sha256` and `contract_version` all match the snapshot being loaded.
3. **Absent-unexplained without `--reconciliation`.** Report it as `"unknown"`, not 0. **`load.sh beta` requires `--reconciliation`**; `dev` keeps it optional.
4. **Tests:**
   - a fixture with the real reconcile layout;
   - a mismatched `t_start`, and a mismatched contract sha;
   - the old snapshot-style reconcile layout is now refused;
   - each new rule gets mutation evidence.
5. **Accepted as you proposed:** `--resume` takes the earlier output dir; the legacy layout requires both `input/` and `run/` (real L3 snapshots have both); and `snapshotManifestSha` is accepted.

Run both suites and report exact counts. Finish in the Engineer final message format.
