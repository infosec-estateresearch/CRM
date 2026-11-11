# CRM-009-H, round 2: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-009-H`. The expected HEAD is `9c652009a7dc958afa4aa6f3d84c4c79609b7034` (round 1 candidate). Do not modify `.forge/`. Allowlist unchanged (WO v1.0).
- **Round 1 review:** tester BLOCKING `unknown-total-unbounded-loop`; all three reviewers raised advisories on unordered paging, unbounded paging and missing de-duplication. Fix all of them in `load/lib/crm_load/api.py` `list_all`:
  1. Send `orderBy=id` and `order=asc` on every page, as `scripts/crm_api.py` does. The PL verified this live on 10.0.12: Email (total -1) and Account both return ids in ascending order with `orderBy=id&order=asc`.
  2. De-duplicate by `id`. If a full page adds no new id, raise `TransportError("list_stalled", status)`, so the read can never loop forever.
  3. Add a hard page ceiling as a backstop, for example 10,000 pages (2M rows). Raise `list_stalled` if it is hit.
  4. Keep the known-total `list_incomplete` check, comparing it against the de-duplicated count.
- **Tests:** add tests for a server that ignores offset (total -1 and full pages: `list_stalled`, no writes), for orderBy/order on every page in the fake's query assertions, and for duplicate rows across pages. Include mutation evidence.
- Run the unit and load suites as non-root. Time box 20 minutes. Report `STATUS: completed` in the Engineer final message format.
