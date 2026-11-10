# CRM-006S, round 2: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-006S`. HEAD should be candidate `709a59842d9f167342f962a1ae144e7c7f7b8ecf`; confirm it.
- **Same WO and rules.** Report `STATUS: completed` with Known gaps if time runs out (30-minute box; return by about 25 minutes).
- **Reference extractor:** copy `/srv/CRM/worktrees/.forge-scratch/CRM-006R/ref/` to your scratch area and set `CONTRACT_VERSION` from 3 to 4 to match its contract file. Then `selftest --quick` gives a **real** synthetic snapshot. Use it for the A1 and A5 proofs this round, not only the hand-made fixtures.

## Blocking (Auditor): synthetic users still don't load
On a real selftest snapshot, all 6 synthetic users are refused as `user_not_exportable`. Their Usernames contain a space and no `@`, so `_user_name` fails (users.py:76). The A5 test uses only `fx.org()` and cannot see this.
- **Fix:** in **selftest snapshots only**, derive the EspoCRM username deterministically from the sfId, for example `syn-` followed by the first 10 hex characters of sha256(sfId), lowercase.
- Real snapshots keep the existing rule, unchanged.
- Add a test that uses the real selftest Username shape, and prove that a dev load of the real selftest resolves owners (`owner_unresolved` falls to 0 for owners who are synthetic users).

## PL facts and decisions (verified live on crm-dev today)
1. **Phones are trimmed on save** with `phoneNumberInternational=false`: `"  01632 960000  "` is stored as `"01632 960000"`.
   - Compare the numbers in `phoneNumberData` trimmed, the same way as the `phoneNumber` attribute, and make the refusal-memory hash use the trimmed value.
   - Make the fake trim phones too. (crm-dev now has `phoneNumberInternational=false`, the same as beta.)
2. **`Contact.salutationName` is validated:**
   - core options are `["", "Mr.", "Ms.", "Mrs.", "Dr."]`;
   - an unlisted value gets 400 `valid`.
   - Route it through the enum mapping, so a value that isn't listed becomes `enum_unmapped` with **null sent** (the core options include `""`), plus a test. Every real value is already in the list.
3. **Synthetic enum values on dev (PL decision):**
   - add a selftest-only `syntheticEnumMap` to `mapping.json`. For a **selftest snapshot only**, it maps the synthetic `Value A`/`Value B`/`Value C` of StageName, Task Status, Priority and CallType to valid target values, so dev exercises the Opportunity, Task, Call and contact-role paths end to end;
   - record each use with the code `synthetic_enum_mapped` (counts);
   - real snapshots never consult the map, and a test proves this (beta with the map present still gives `enum_blank_unrepresentable` / `enum_unmapped` exactly as before);
   - document it in IMPORT.md.
4. **An unmapped, non-blank CallType** gets the same treatment as a blank one: direction omitted, with the code `call_direction_unknown` (plus `enum_unmapped`). Document it.
5. **Refusal memory:**
   - `load.sh` additionally requires the refusal file's parent directory to be root-owned `0700`, the same rule as `--resume`;
   - `crm-load` opens the file with `os.open(path, O_RDONLY | O_NOFOLLOW)`, then uses `fstat` to check that it is a regular, root-owned `0600` file;
   - IMPORT.md requires passing the previous run's `phone-refusals.json` on every re-run, and the load report states whether a refusal file was supplied.
6. **Counting:** when an update writes nothing because every phone probe was refused, count the record as `unchanged`, not `updated`.
7. **Tests:** add a test that fails if text attributes are trimmed before comparison (mutation M10: `if isinstance(value, str) and not text:` changed to `if isinstance(value, str):`).

Run both suites, report exact counts, and give mutation evidence for each item. Also report the dev end-to-end on the real selftest: run-1 counts by entity, `owner_unresolved`, and run 2 `writes == 0`. Finish in the Engineer final message format.
