# CRM-008-F, round 1: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-008-F`, branch `forge/CRM-008-F`. The expected HEAD is `4bab43e7515fb171fecac453cb297ab86a3946ba`, the CRM-008 delivery record. Confirm it first. Do not modify `.forge/`.
- **Work order:** `/srv/CRM/main/work-orders/CRM-008-F.md` v1.0. Its facts were verified live by the PL on crm-dev. Keep to its allowlist (`load/**`, `tests/load/**`, `docs/IMPORT.md`).
- **Reference extractor:** copy `/srv/CRM/worktrees/.forge-scratch/CRM-006R/ref/` and change `CONTRACT_VERSION` from 3 to 4. Use the **full** selftest for A2.
- **Time box:** 30 minutes; return by about 25. Report `STATUS: completed` with Known gaps if needed.
- **Order:** extend the fake for facts 1–4 first, then show the failing run-2 writes, then fix items 1–4.

## Notes
- **Phones (item 1).** The engine's existing record GET path, if there is one, or a new `client.get(entity, id)` stays GET-only on the loopback transport. Keep the extra reads bounded: only for records whose source has two or more numbers and whose primary matches.
- **Email with no recipient as Task (item 4).** Reuse the CRM-008 Task-Email route and its fields. The description is the plain body; if there is only an HTML body, use it as-is as text with no conversion, and document that.

Run both suites, report exact counts, give mutation evidence per item, and report the A2 numbers. Finish in the Engineer final message format.
