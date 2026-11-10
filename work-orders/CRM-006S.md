WO: CRM-006S
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-006R
BROWSER: no

# CRM-006S — Importer fidelity follow-up to CRM-006R

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10 (Issue #9).
- **Why:** CRM-006R was closed ESCALATED. Every round-1 blocker was fixed and verified. The round-2 Auditor raised a new blocking finding, `server-defaults-rerun-writes`, after the engineer had used all 4 executions. This WO fixes that finding and the four carried advisories. `work-orders/CRM-006.md` v1.0 and the CRM-006R clarifications still govern everything else.

## Facts verified by the PL (EspoCRM 10.0.12 on crm-dev, synthetic probes, deleted)
- **Core and custom enums that have `""` in their options:**
  - explicit `null` is accepted on create and on update;
  - an omitted value reads back as null.
- **`Account.learningPlatformAccess`** (options `No, TLP, Full Access, E-Course`, default `No`):
  - explicit `null` gets 400 `validationFailure` / `valid`;
  - `""` gets 400 as well;
  - an omitted value is stored as `No`.
- **In Salesforce, `TLP__c` is blank on a material share of Accounts.** The figure is held in protected storage and is not reproduced here.
- **Values are not stored exactly as sent:**
  - varchar values are trimmed on save (the core StringTrim sanitizer);
  - text fields (for example `description`) are stored verbatim.
- **`GET Settings` exposes `phoneNumberInternational`.** It is `true` on dev; beta will be set to `false`.

## Change
1. **No stored server defaults.** On create and update, every mapped attribute whose source value is blank is sent as an explicit `null`. Omitting it lets the server store its default, which is a manufactured value. Rule: after the first run, every blank source value must read back as blank.
2. **Blank option for learningPlatformAccess.** `custom/Espo/Custom/Resources/metadata/entityDefs/Account.json` gets `""` as the first option of `learningPlatformAccess`. The default `No` and the order of the other options are unchanged, so the UI behaviour for new records stays the same. `load/contract/mapping.json` `enums` and the i18n are updated to match, and so is the CRM-003 test that asserts this field.
   - Add a test that fails if a mapped enum target can receive a blank source value but has no `""` option.
   - A mapped enum target with no blank option and a blank source value is refused with the exception code `enum_blank_unrepresentable` and the record id only. It is never defaulted.
3. **Compare as the server stores.** Before comparing a varchar attribute with the stored value, trim it the way the server's StringTrim sanitizer does. Text attributes are compared verbatim. On a second run over identical data, a value with leading or trailing spaces must cause zero writes.
4. **Phone precondition.** `load.sh beta` (and the engine in its beta mode) reads `GET Settings` before writing anything. It refuses to run with exit code ≠ 0 and the exception code `phone_international_enabled` when `phoneNumberInternational` is not exactly `false`. Dev reports the value and continues.
5. **Per-phone handling.**
   - If one phone number is refused, the valid sibling numbers on the same record are still stored.
   - The refused number is reported once (`phone_refused`, record id only). On later runs it is not retried while the source value is unchanged, and it never causes a write.
   - How the refusal is remembered must be deterministic and must not contain customer data, for example a hash of the source value in the importer state. Document it in `docs/IMPORT.md`.
6. **Synthetic users on dev.**
   - In selftest snapshots, the user filter accepts the synthetic UserType values so that the dev owner path runs end to end.
   - Real snapshots keep the `Standard`-only rule.
   - Tests cover both.
7. **`docs/IMPORT.md`.** Document items 1–6.

## Allowlist
- `load/**`
- `tests/load/**`
- `scripts/load.sh`
- `docs/IMPORT.md`
- `custom/Espo/Custom/Resources/metadata/entityDefs/Account.json`, with its i18n (`learningPlatformAccess` only)
- the existing CRM-003 unit tests and policy mirror that assert that field, changed only as needed for item 2

## Acceptance
- **A1, server defaults:** an end-to-end test against the fake transport, which models server defaults, null-refusing enums and StringTrim the way the PL facts describe them. Run 1 stores no default value for a blank source. Run 2 makes **zero** writes.
- **A2, enum gap:** an enum target without `""` gives `enum_blank_unrepresentable`. Mutation evidence: removing the `""` option makes the guard test fail.
- **A3, phone precondition:** beta refuses on `phoneNumberInternational` true or missing; dev continues.
- **A4, phones:** a refused phone keeps its valid siblings, and a second run makes zero writes and no retry.
- **A5, synthetic users:** synthetic users load on dev, and real snapshots still accept only Standard users.
- **A6, test suites:** `python3 -I -B -m unittest discover -s tests/load -t .` and `python3 -m unittest discover -s tests/unit` both pass. Mutation evidence is given for each item.
- **A7, no customer data:** the change and its records contain no customer data, host addresses or record identifiers. gitleaks is clean.
