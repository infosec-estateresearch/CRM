# CRM-006S, round 2 review: Devsecops

- **Worktree:** `/srv/CRM/worktrees/CRM-006S`. It is read-only; don't touch any other path except scratch.
- **Candidate SHA:** `57997135550270f5fb1098a1e7ba403142050d44`
- **Base SHA:** `e1f9a6899e82ac5862849db0bf1f00dbcae51244` (the CRM-006R escalation record; CRM-006R was reviewed up to `375e1ca`)
- **Scratch:** `/srv/CRM/worktrees/.forge-scratch/CRM-006S`
- **Reference extractor:** `/srv/CRM/worktrees/.forge-scratch/CRM-006R/ref/` is read-only. Copy it to scratch and set `CONTRACT_VERSION` from 3 to 4 to match its own contract file, as the CRM-006R reviewers did. Its `selftest` then gives real synthetic snapshots.

Assess the candidate **independently** against `work-orders/CRM-006S.md` v1.0 (on main; the WO text is in `/srv/CRM/main/work-orders/CRM-006S.md`). CRM-006 v1.0 and the CRM-006R rules still apply.

**Blocking:**
- any record content in logs, reports or exceptions (ids and codes only);
- a delete path;
- a guessed owner;
- any manufactured or stored server-default value without an exception code;
- a second run over unchanged data that writes anything (with `phoneNumberInternational=false`);
- beta proceeding when `phoneNumberInternational` isn't confirmed false;
- weakening any CRM-006R rule (the synthetic rule, beta refusals, reconcile binding, loopback-only transport, key never in argv);
- a change outside the WO allowlist.

**PL facts** (EspoCRM 10.0.12, live on crm-dev, synthetic probes, deleted):
- **Enums with `""` in their options:** an explicit `null` is accepted, and an omitted value reads back as `null`.
- **`learningPlatformAccess`** (before this WO): `null` and `""` are refused with 400 `valid`, and an omitted value is stored as `No`.
- **`Opportunity.stage`:** `null` is refused with 400.
- **`Meeting.meetingType`:** `null` is accepted.
- **`Call.duration`:** an omitted value is stored as 300, and `null` reads back as 0.
- **Trimming:** varchar values are trimmed on save (StringTrim); text values are not.
- **Settings:** `GET Settings` exposes `phoneNumberInternational`.
- **Real data** (counts only): every StageName maps, and every Call has a blank duration.

**PL decisions:**
- A blank `CallType` keeps the CRM-006R rule: it is omitted and recorded as `call_direction_unknown` (EspoCRM shows its core default).
- An unmapped or blank stage refuses the record.
- Refusal memory is a root-only `0600` file of sha256 values, passed with `--phone-refusals`.

**Round 2.** The round-1 findings went to the engineer. Additional PL facts verified on crm-dev, which now has `phoneNumberInternational=false`:
- phones are trimmed on save;
- `Contact.salutationName` is validated against `["", "Mr.", "Ms.", "Mrs.", "Dr."]`, and every real value is in that list.

**Additional PL decisions:**
- **`syntheticEnumMap`:** it is selftest-only. It covers StageName, Status, Priority, CallType and **TaskSubtype**, and each use is recorded with the code `synthetic_enum_mapped`. Real snapshots never consult it.
- **Selftest usernames** are derived from the sfId hash.
- **Refusal file:**
  - `crm-load` requires it to be owned by the running user and opened with `O_NOFOLLOW`;
  - `load.sh` requires root and a root-owned `0700` parent.
- A real selftest produces some codes by design; they are not defects: `enum_unmapped`, `role_unmapped`, `name_unparsed`, and a single `owner_unresolved` for an owner id that is not in the snapshot's Users.

Verify the round-1 findings are fixed, and look for new defects.
