# CRM-006R, round 2: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-006R`. Your round-1 work is uncommitted in the worktree; continue from it. Do not modify `.forge/`.
- **Status reporting:** if you can't finish, report `STATUS: completed` with "Known gaps".
- **Time box:** return by about 20 minutes.

## PL decisions
1. **Authorised: the test exception.** Apply your proposed `tests/unit/test_access_policy.py` change for `Contact.opportunityRole` (`audited` plus `options` only). It must still refuse any other override key on that field, so add one broken-fixture case. The unit suite must be fully green.
2. **Snapshot layout (new, blocking for the real load).** Legacy-mode snapshots, which the real extraction produces, are laid out like this:
   - `<id>/input/waiver.json`
   - `<id>/run/manifest.json`
   - `<id>/run/objects/…` and the other run files

   The client-credentials layout has `manifest.json` at `<id>/`. `crm-load` and `load.sh` must locate `manifest.json` in exactly one of these two layouts. Use the same rule as CRM-002-W (in progress):
   - `<id>` when `<id>/manifest.json` exists, there is no `run/` and no `input/`;
   - `<id>/run` when `<id>/run/manifest.json` exists, there is no `<id>/manifest.json`, and the top level holds only `input/` and `run/`.

   Anything else is refused. The waiver is never read. The reconciliation report (`report/reconciliation.json`) comes from a **separate** `*-reconcile` run directory, not inside the snapshot. So make it an optional `--reconciliation <path>` argument, verified against its own sealed manifest, rather than assuming a location. Add tests for both layouts and for the refusals.
3. **`load.sh` must support `--accept-drift <URL>`**, passed through to `crm-load`. The URL must match `https://github.com/infosec-estateresearch/CRM/issues/9#issuecomment-<digits>`. It is required only when the manifest status is `RECONCILED_WITH_DRIFT`. Also add `--resume <previous output dir>`, which must be a sealed earlier output for the same snapshot sha. Add tests for both.
4. **Re-run the round-1 mutation evidence** for the gate, idempotency, owner resolution and the no-content rule on the final code, and report it.

Run both suites and report exact counts. Finish in the Engineer final message format.
