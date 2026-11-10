# CRM-007R, round 2: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-007R`. HEAD should be candidate `48810aba327252b58722069ba162cc7b09b507e9`; confirm it.
- **Same WOs and rules, same 30-minute box.** Report `STATUS: completed` with Known gaps if needed.

## Blocking (all three reviewers): `export.sh` is not bound to its target
My round-1 reading of "export follows the same rule" was too narrow. Fix both directions:
1. **Output.** `export.sh <target> [name]` writes only to a **new** directory directly under that target's `$CRM_BACKUP_DIR` (constant, as for backups).
   - An optional argument may only be a bare name matching `export-[A-Za-z0-9._-]+`, never a path.
   - A path, `..`, an existing directory or a symlink is refused before any request.
   - `export_csv.py` refuses an `--out` whose parent isn't the target's backup dir: pass the target, and check it there too.
2. **URL.**
   - `export.sh dev` requires exactly dev's own URL, using `check_access.py dev --base-url` (or `base_url_problem("dev", …)`), as provisioning does;
   - `export.sh beta` keeps its existing pin, routed through the same helper.
   - Anything else is refused before any request.
3. **Tests:** reproduce the reviewers' probes (`probe_export.py`, `probe_r.py`), with mutation evidence.

## Advisories (fix these)
- **`check_restoretest_compose`:** apply the same network-spec allowlist as beta (`{}`, `driver: bridge`, `internal: true` only), and refuse volume drivers other than local and any top-level `secrets`/`configs`. Add fixtures.
- **`--legacy-unmarked` (PL decision):** accept only stamps strictly earlier than the constant cut-over `20261111T000000Z`, because every existing dev backup predates it. Add a test.
- **The `write_report` gate:** add a test in `test_isolation_007r.py` that kills that mutant on its own.

Run the unit and load suites, report exact counts, and give mutation evidence. Finish in the Engineer final message format.
