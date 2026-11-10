# CRM-006S, round 1 review: Tester

- **Worktree:** `/srv/CRM/worktrees/CRM-006S`. It is read-only; don't touch any other path except scratch.
- **Candidate SHA:** `709a59842d9f167342f962a1ae144e7c7f7b8ecf`
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

Extend the faithful fake, or subclass it, independently of the engineer's version. Prove or refute zero second-run writes with:
- blank values in every mapped field;
- padded varchar and text values;
- a refused phone next to a valid one, without and with `--phone-refusals`;
- the reference selftest.

Then run the beta precondition against `true`, missing and refused-read cases.
