# CRM-008, round 3: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-008`. HEAD should be candidate `68c32e2f59b45b1a1058873e46f55e3b3e6778b0`; confirm it.
- **Same WO and rules, same 30-minute box.** Report `STATUS: completed` with Known gaps if needed.

## Blocking (Auditor)
1. **`docs/IMPORT.md` prerequisites.** State that the target must have Settings `currencyList ["GBP"]`, `defaultCurrency` and `baseCurrency` `GBP` (otherwise every Opportunity with an amount gets `400 amount validCurrency`) and `phoneNumberInternational false`. Also state that `provision_access.py <target>` applies all four from `config/settings.json`, idempotently. Update the phone-setting bullet to match.

## Advisories (PL decisions; fix these)
2. **Required attribute too long.** If an over-length value is a **required** attribute (Account `name`, ServiceType `name`), **refuse the record** with `value_too_long` instead of sending null. Count it in `skipped.value_too_long`. Make the fake check required `name` on Account and ServiceType. Add tests.
3. **Qualified attribute names.** `value_too_long` attribute names are qualified by target entity, for example `ServiceType.name` and `Opportunity.sfLeadSource`, so an Opportunity row never appears to have a long name.
4. **Owner tests.** Add a load test showing that a Contact, an Opportunity and an Email with an unresolved owner are still written, with `owner_unresolved` (not `owner_required_unresolved`). It must fail under the Auditor's mutations (require_owner in contact/opportunity; Email in OWNER_REQUIRED).
5. **IMPORT.md, two further notes:**
   - an over-length value is also sent as null on **update**, so it clears that field;
   - the email rule is stricter than PHP `FILTER_VALIDATE_EMAIL`, by design. PL count on the real extract (counts only): 3 addresses (2 To, 1 Cc) would be dropped with `email_address_invalid`, and 0 From addresses would be refused.
6. **Shebangs.** Leave `scripts/crm_api.py` and `load/bin/crm-load.py` as they are, executable without a shebang. Their documented use is `python3 -I -B`. Mention this in the IMPORT.md usage note.

Run both suites, report exact counts, and give mutation evidence for items 2–4. Finish in the Engineer final message format.
