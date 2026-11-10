# CRM-006S, round 1: Engineer (importer fidelity follow-up to CRM-006R)

- **Worktree:** `/srv/CRM/worktrees/CRM-006S`, branch `forge/CRM-006S`. The expected HEAD is `e1f9a6899e82ac5862849db0bf1f00dbcae51244`, the CRM-006R escalation record. Confirm it first. Do not modify `.forge/`.
- **Work order:** `work-orders/CRM-006S.md` v1.0, on main. Read it, and keep strictly to its allowlist.
- **Reference material:** `/srv/CRM/worktrees/.forge-scratch/CRM-006R/ref/`, a read-only copy of the extractor with contract v4. Use its `selftest` to produce real synthetic snapshots, as the reviewers did. Work in `/srv/CRM/worktrees/.forge-scratch/CRM-006S/`.
- **Status reporting.** If the time box ends before you finish, report **`STATUS: completed`** with a precise "Known gaps" list. Use `failed` only if the work cannot be done at all.
- **Time box:** the dispatcher stops you at 30 minutes. Return by about 25 minutes.

## The blocking finding (CRM-006R round-2 Auditor, verbatim summary)
When a source value is blank, the importer leaves the attribute out of the create body (engine.py around :225). The server then stores its entityDefs default, and every later run PUTs null (`same_value(None, default)` is False, around :247). The Auditor reproduced this with a FakeEspo subclass that applies defaults on POST: the second run made 7 writes. They were `PUT Account [learningPlatformAccess]` ×5, `PUT Opportunity [stage]` and `PUT Call [duration]`. FakeEspo models no defaults, so the existing zero-writes test cannot catch this.

## Facts verified by the PL live on crm-dev (EspoCRM 10.0.12, synthetic probes, deleted)
- **Core enums with `""` in their options** (Account `type`, `industry`):
  - explicit `null` is accepted on create and on update;
  - an omitted value reads back as `null`.
- **`Account.learningPlatformAccess`** (options without `""`, default `No`):
  - `null` gets `400 validationFailure`, field `learningPlatformAccess`, type `valid`;
  - `""` also gets 400;
  - an omitted value is stored as `No`.
  - Real data has many blank values, so WO item 2 adds a `""` option.
- **`Opportunity.stage`** (the custom options have no `""`):
  - `null` gets 400 `valid`;
  - an omitted value is stored as the default.
  - Every StageName in the real data maps through `stageMap`. An unmapped or blank stage must still never be defaulted: refuse that record with `enum_blank_unrepresentable` (or keep `enum_unmapped`, and refuse it either way).
- **`Meeting.meetingType`:** an explicit `null` is accepted and reads back as `null`.
- **`Call.duration`:**
  - an omitted value is stored as `300` (the core default);
  - an explicit `null` is accepted, but **reads back as `0`**, because EspoCRM derives `duration` from `dateEnd − dateStart`.
  - In the real data, every Call has a blank `CallDurationInSeconds`.
  - **PL decision:** for a blank source duration, send `duration: null` explicitly. Treat a stored `0` as equal to a blank source, so it is never a difference. Record `call_duration_unknown` once per record (at create, or on the first run that sees it). Document in IMPORT.md that EspoCRM shows 0 minutes for these calls.
- **varchar vs text:**
  - varchar values are **trimmed** on save (the core `StringTrim` sanitizer: `"  x  "` is stored as `"x"`);
  - `text` fields (for example `description`) are stored **verbatim**.
  - Decide the type from the target entityDefs (core types as listed in mapping.json or your attribute table; custom ones from `custom/.../entityDefs`).
  - Apply the same trim to the ServiceType lookup key, so a padded `Opportunity_Service__c` never creates a duplicate ServiceType (DevSecOps advisory).
- **Settings:** `GET Settings` (an admin or API user) returns `phoneNumberInternational`; it is `true` on dev. The API user of the beta load must be able to read it. If the read is refused, treat it as "not confirmed false", so beta refuses.

## The work
Follow WO items 1–7 and acceptance A1–A7. Notes:
- **Make the fake faithful first.**
  - Extend FakeEspo so that it applies these entityDefs defaults on POST when an attribute is omitted: `learningPlatformAccess` `No`, `stage` its default, Call `duration` `300`, Call `direction` `Outbound`.
  - It refuses `null` and `""` for enums that have no `""` option.
  - It stores Call `duration` `null` as `0`.
  - It trims varchar values and leaves text values as sent.
  - It answers `GET Settings`.
  - Keep the existing faithful behaviours: phones, `from`, `messageId` and the link-multiples.
  - Then prove that run 2 makes **zero writes**, both with the reference selftest and with fixtures carrying blanks, padded strings and a refused phone next to a valid one.
- **Per-phone (item 5):**
  - when the server refuses `phoneNumberData` with `400` on `phoneNumber`, find which numbers it refuses (for example one retry per number, within a small bound), keep the valid siblings, and record `phone_refused` per refused number by record id only;
  - the refusal memory must be content-free, for example a sha256 of `(sfId, field, value)` in the existing state or exceptions;
  - an unchanged source value must not be retried on a later run, and the run must not count as a write.
- **Do not weaken** any rule from CRM-006R: the synthetic rule, beta refusals, no manufactured direction, the date fallbacks with codes, loopback-only transport and no key in argv.

Run both suites, report exact counts, and give mutation evidence for each WO item. Finish in the Engineer final message format.
