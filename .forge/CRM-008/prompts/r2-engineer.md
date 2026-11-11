# CRM-008, round 2: Engineer

Same worktree (`/srv/CRM/worktrees/CRM-008`), same WO and rules, and the same 30-minute box (return by about 25). Your round-1 work is uncommitted in the worktree. Keep it. Report `STATUS: completed` with Known gaps if needed.

## Close the round-1 gaps
1. **A2: a faithful fake.** Extend `tests/load/fixtures.py` FakeEspo to refuse what 10.0.12 refuses (all PL-verified):
   - a missing or null `assignedUserId` on Task, Call and Meeting gives 400 `assignedUser required`;
   - a varchar or phone value longer than its `maxLength` gives 400 `maxLength`. Use the same table as `mapping.json`, with Contact `title` 255; phone numbers are limited to 36;
   - a non-null `amount` whose `amountCurrency` is not in Settings `currencyList` gives 400 `amount validCurrency`. The fake's Settings default is `["USD"]` until provisioning sets GBP, so test both cases: the loader against USD-only Settings refuses every amount, and against GBP Settings it passes;
   - an invalid email address in `to`, `cc` or `from` gives 400 `valid`, and a blank `from` on Email gives 400 `from required`.
   
   Then prove that run 1 has **0 `write_rejected`** and run 2 has **0 writes**: once on the in-repo fixtures and once on a real full selftest (item 2).
2. **A real full selftest.**
   - Copy `/srv/CRM/worktrees/.forge-scratch/CRM-006R/ref/` to scratch, set `CONTRACT_VERSION` from 3 to 4, and run `selftest` **without** `--quick`. Seal it as the reviewers did.
   - Run `crm-load users`, then provisioning into the fake (with GBP Settings), then load run-1 twice, the second time with `--phone-refusals`.
   - Report the run-1 created/failed counts per entity, the exception counts by code, `write_rejected` (must be 0), and the run-2 writes (must be 0).
3. **Tidy-up:** if it's easy, restore `mapping.json` arrays to their original inline formatting so the diff shows only real changes.

Run both suites, report exact counts, and give mutation evidence that each new fake refusal is exercised: disable it and a test fails. Finish in the Engineer final message format.
