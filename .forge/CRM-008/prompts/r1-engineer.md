# CRM-008, round 1: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-008`, branch `forge/CRM-008`. The expected HEAD is `dfe1d55f658b40082403f716c56b2b378fcf4163`, the CRM-003-F delivery record. Confirm it first. Do not modify `.forge/`.
- **Work order:** `/srv/CRM/main/work-orders/CRM-008.md` v1.0. Its facts were verified live by the PL on crm-dev and counted on the real extract. Keep strictly to its allowlist.
- **Reference extractor:** copy `/srv/CRM/worktrees/.forge-scratch/CRM-006R/ref/` to your scratch area and change `CONTRACT_VERSION` from 3 to 4. Use the **full** selftest (not `--quick`); the PL's operator run used a full selftest.
- **Scratch:** `/srv/CRM/worktrees/.forge-scratch/CRM-008/`.
- **Time box:** 30 minutes; return by about 25. Report `STATUS: completed` with Known gaps if time runs out. Order: Change 1, 2, 9 and 8 (quick), then 3, 4, 5, 6 and 7, then the A2 fake extensions.

## Notes
- **Change 2:** the Settings `PUT` needs admin. `provision_access.py` already runs as admin. Read `GET Settings` first and send only the keys that differ. Put the expected values in `config/settings.json` and assert them in the access policy tests.
- **Change 4:** the route is decided in mapping. For a Task-Email (subtype Email or ListEmail) whose Id is not any EmailMessage's `ActivityId`, the entity is Task. Keep `represented_by_email_message` for the others. If a row was already created as an Email in an earlier run, don't move it; the dev runtime will be reloaded from scratch.
- **Change 5:** take the limits from the facts and put them in `mapping.json` `maxLength`. Add a test that checks every entry against the custom entityDefs where the field is custom (Contact `title` is now 255).
- **Change 6:** document the validation rule you implement. Prefer refusing a borderline address over sending one EspoCRM would refuse.
- **Change 9:** Git modes. Use `git update-index --chmod=+x` or `chmod +x` in the worktree. ForgeV2 commits the mode change.

Run both suites, report exact counts, and give mutation evidence per Change item. Finish in the Engineer final message format.
