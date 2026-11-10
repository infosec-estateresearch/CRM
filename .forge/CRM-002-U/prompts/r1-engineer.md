# CRM-002-U, round 1: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-002-U`, branch `forge/CRM-002-U`. The expected HEAD is `ecf2a169ecd4da1f11147cd122d785ad3f66cfbf`, the CRM-002-T delivery. Confirm it first. Do not modify `.forge/`.
- The Work Order below (verbatim) is authoritative. Keep the change small.
- **Time box:** return by about 20 minutes.

**PL notes:**
- The L1 facts in the WO are schema facts verified by the PL against the real org. Don't change any other field.
- The synthetic org must match contract v3:
  - Account `Interested_in_integration__c` is a picklist;
  - `RelationAddress` is a string;
  - the two Opportunity fields are removed.

  `selftest` must still reach RECONCILED with every mutation scenario.
- Grep for every `contractVersion` / `CONTRACT_VERSION` / "expected 2" reference, including tests and docs.
- Run `python3 -I -B -m unittest discover -s tests/migrate -t . -v`. Report exact counts and mutation evidence.

Finish in the Engineer final message format.

## Work Order (verbatim, `work-orders/CRM-002-U.md` v1.0 on main)

WO: CRM-002-U
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-002-T
BROWSER: no

# CRM-002-U — Source-field contract v3 (L1 corrections) and type reporting in the gate

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10 (Issue #9). Follow-up to L1.
- **Parent:** CRM-PBI-005, part 1.

## L1 result (operator, 2026-11-10; schema only)
`contract-check --auth soap-legacy` ran end to end: SOAP login, 12 describes, then logout. The legacy env file was unchanged, and the run directory was sealed. The gate failed on 3 of the 12 objects. The PL then read the real field types through the reviewed, allowlisted client. The schema facts are below:

| Object.field | Contract v2 | Salesforce |
|---|---|---|
| `Account.Interested_in_integration__c` | boolean, required | **picklist** |
| `Opportunity.Post_code__c` | string, optional | **reference to Opportunity** (`Post_code__r`), a self-lookup and not a postcode |
| `Opportunity.Key_Information__c` | textarea, optional | **absent** (no such field) |
| `EmailMessageRelation.RelationAddress` | email, required | **string** |

All 12 objects report createable, updateable or deletable for this identity. That is expected for the write-capable legacy identity, and it is waived under `waiver.json`. The `User updateable` finding is reported, as designed.

## Change
1. **`migrate/contract/salesforce-fields.json`, contract version 3.**
   - `Account.Interested_in_integration__c`: type `picklist`, still required.
   - `EmailMessageRelation.RelationAddress`: type `string`, still required.
   - Remove `Opportunity.Post_code__c` and `Opportunity.Key_Information__c`. Neither carries the data its purpose names. Excluding unneeded fields follows the data-minimisation rule.
   - Bump `contractVersion` to 3, and update `CONTRACT_VERSION` together with every place that checks it.
   - No other field changes.
2. **Gate reporting.** For each `type_mismatch` and `reference_mismatch`, `contract-check.json` records the **described type name**, and for a reference the `referenceTo` object names, beside the field name. For example: `{"field": "X", "expected": "boolean", "described": "picklist"}`. These are schema identifiers only. Validate them against `[A-Za-z][A-Za-z0-9_]{0,79}`, and record anything else as `"unrecognised"`. Logs keep counts only.
3. **Tests:**
   - a fixture describe in the shape of the L1 result above passes the v3 gate;
   - a v2-shaped contract is refused with `contract_version`;
   - the mismatch report contains the described type and refuses a non-identifier type value;
   - the synthetic org in `synthetic.py` is updated to the v3 schema, so `selftest` still reaches `RECONCILED`;
   - every existing test still passes.
4. **Docs:**
   - `docs/MIGRATION.md`: contract v3 and the mismatch report fields.
   - `docs/SALESFORCE-DATA-INVENTORY.md`: one line each, saying that Salesforce has no enquiry postcode field and no key-information field. Downstream consumers (CRM-004 `postcode` and `keyInformation`) stay empty on import.

## Scope
- **Allowlist:**
  - `migrate/**`
  - `tests/migrate/**`
  - `docs/MIGRATION.md`
  - `docs/SALESFORCE-DATA-INVENTORY.md`
  - `.forge/CRM-002-U/**`
- **Excluded:** `custom/`, `load/`, `scripts/`, Salesforce access, and real data.

## Acceptance criteria
- **AC1:** unit tests pass with non-vacuity.
- **AC2:** gitleaks is clean.
- **Operator stage:**
  - O1 `selftest` reaches `RECONCILED` on the delivered commit;
  - L1 `contract-check` passes the gate (`ok=true`), with only the identity waivers and the reported `User updateable` finding;
  - then L2 (count) and L3 (extract).
