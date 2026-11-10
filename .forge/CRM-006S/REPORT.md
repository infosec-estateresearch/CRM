# CRM-006S - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-006S   Candidate: 57997135550270f5fb1098a1e7ba403142050d44   Base: e1f9a6899e82ac5862849db0bf1f00dbcae51244 (CRM-006R escalation record)   WO: work-orders/CRM-006S.md v1.0
Change: importer fidelity follow-up to CRM-006R.
- Blank source values are sent as explicit null, so no server default is ever stored.
- `Account.learningPlatformAccess` gains a `""` option; its default and UI behaviour are unchanged. An enum with no blank option refuses the record with `enum_blank_unrepresentable`.
- A blank Call duration is sent as null; the stored 0 counts as equal, and the record gets `call_duration_unknown`.
- varchar values and phone numbers are compared trimmed, mirroring the server's StringTrim; text values are compared verbatim; the ServiceType key is trimmed.
- Beta refuses to run unless `GET Settings` returns `phoneNumberInternational` exactly false.
- Phones are handled per number:
  - a refused number keeps its valid siblings;
  - the refusal memory is a sealed root-only 0600 file of sha256 values;
  - an unchanged refused number is never retried.
- Selftest-only behaviour:
  - usernames derived from the sfId hash;
  - Synthetic UserTypes accepted;
  - `syntheticEnumMap` used, with the code `synthetic_enum_mapped`.
  - Real snapshots never use any of these.
- Salutation goes through the enum mapping.
- An unmapped CallType gives `call_direction_unknown`.
PL facts verified live on crm-dev (synthetic probes, deleted):
- null handling: accepted for enums with a blank option and for meetingType; refused for learningPlatformAccess (before this WO) and for stage;
- Call duration: null reads back as 0;
- trimming: varchar values and phones are trimmed, text values are not;
- salutation options are validated;
- Settings exposes phoneNumberInternational.
- crm-dev is now set to phoneNumberInternational=false, the same as beta.
Tests: tests/load ran 131, OK; tests/unit ran 311, OK. There is mutation evidence for every item (14 mutants, each killed).
- Real-selftest end-to-end against the faithful fake: 6 users exported; owner_unresolved went from 130 to 1, an owner id that is not in the snapshot's Users. Relationship totals matched, and run 2 made 0 writes.
Reviews:
- Round 1:
  - Auditor, blocking: synthetic-users-not-exportable. Fixed.
  - Advisories, all fixed: phone trim, salutation, refusal-file parent/TOCTOU, count on refused probes, text-verbatim test, unmapped CallType, synthetic enum coverage.
- Round 2: Auditor, Tester and DevSecOps all PASS.
Advisories carried:
- A re-run without `--phone-refusals` retries and writes. This is documented, and the report states `supplied=false`.
- `crm-load --phone-refusals <FIFO>` hangs. `load.sh` refuses a FIFO first.
- The settings log does not distinguish the string "false" from the boolean. The refusal itself is correct.
