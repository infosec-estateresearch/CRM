# CRM-008, round 2 review: Tester

- **Worktree:** `/srv/CRM/worktrees/CRM-008`, read-only. Scratch: `/srv/CRM/worktrees/.forge-scratch/CRM-008`.
- **Candidate:** `ea07c2f25ff37160633573dd953979a9519ce763`
- **Base:** `dfe1d55f658b40082403f716c56b2b378fcf4163` (the CRM-003-F delivery record).
- **WO:** `/srv/CRM/main/work-orders/CRM-008.md` v1.0. Its facts were verified live by the PL on crm-dev and counted on the real extract.
- **Reference extractor:** copy `/srv/CRM/worktrees/.forge-scratch/CRM-006R/ref/` and set `CONTRACT_VERSION` from 3 to 4. A full selftest (not `--quick`) gives real synthetic data.

Assess the candidate independently.

**Blocking:**
- record content in logs, reports or exceptions (ids, codes and attribute names only);
- a delete path;
- a guessed owner or placeholder owner;
- a truncated or manufactured value;
- `write_rejected` on run 1 or any write on run 2 against a faithful fake;
- weakening any CRM-006/006R/006S rule;
- the Settings step not idempotent;
- a change outside the WO allowlist.

**PL decisions:**
- Task, Call and Meeting with an unresolved owner are refused (`owner_required_unresolved`).
- A Task-Email without an EmailMessage becomes a Task (`task_email_imported_as_task`).
- An over-length value is sent as null with `value_too_long` (attribute names only).
- An invalid To/Cc address is dropped (`email_address_invalid`); an invalid or blank from refuses the record.
- Role `info` is documentation only.

**Round 2.** The round-1 findings went to the engineer; one was blocking: IMPORT.md did not document the Settings.

**PL decisions:**
- An over-length **required** attribute refuses the record (`value_too_long`); other over-length attributes are sent as null on create **and** update.
- Attribute names are qualified (`Entity.attribute`).
- `crm_api.py` and `crm-load.py` stay executable without a shebang; IMPORT.md says to run them with `python3 -I -B`.
- **Email rule:** stricter than PHP by design. PL count on the real extract: 3 addresses dropped and 0 From addresses refused.

Verify the round-1 findings are fixed, and look for new defects.
