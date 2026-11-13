# FirmGroup — simple CRM user experience and acceptance contract

> **Provenance:** CGPT Architect delivery package of 2026-11-13 (`ER_CRM_FOUNDRY_DELIVERY_2026-11-13.zip`, sha256 `a75b5f0d1768a2a1bd945d35710e6e2067c4a7fb5e0228773946446ad9104488`), reconciled into the CRM repository by Rogue under the documentation-only assignment of 2026-11-13. CANDIDATE: not approved. Changes made during reconciliation are listed in [`docs/initiation/2026-11-13-existing-product-reassessment.md`](../initiation/2026-11-13-existing-product-reassessment.md#7-reconciliation-log).

**Status: candidate.** Account Group Members tab and independent group identity are agreed business outcomes. Must be verified in a real browser against pinned EspoCRM 10.0.12, not claimed to work merely from metadata design.

### Account detail

- Add **Group Members** near existing **Stream** and **Account** areas; avoid hiding or changing other tabs and activities.
- Header shows linked FirmGroup name and opens that group's record.
- All **other** member firms listed with name, address/postcode, tier/type and phone; clickable to Account detail, paginated if large. Exclude current Account; do not hide peers with duplicate names.
- If no FirmGroup: show **Not part of a group**. An authorised manager can create/select; a reader sees no edit action.
- Provide manager action to add one or more existing Accounts, unlink current Account, or explicitly move it from another group. All changes are server-authorised and audited.

### FirmGroup detail

- Name, optional description, member list, add/select existing firms and unlink for managers.
- Peer group does not impose a head office; `Account.parent/branches` remains unchanged.
- No `sfId` belongs on FirmGroup (CRM-native identity). An optional separate operator-owned seed source key may be created **only** when the data-migration WO defines it.
- No silent delete of group containing members; non-manager read-only; name not globally unique.

### Seeding and data quality

- On first feature release, do **not** automatically create 1,366 groups from Salesforce parent trees.
- Legacy WIP holds 36 approved groups/137 approved memberships, with 31 strict single-tree subsets, four cross-tree groups and one parentless. These require separate mapping review and PO sign-off. Do not infer missing sibling membership.
- 39 unlinked duplicate top-level names, branch names and aliases are never auto-grouped by name.
- Future seed must be deterministic on immutable Account IDs, preserve deliberate ungrouping and manual moves across reruns, and produce restricted evidence and counts-only public summaries.

### Browser acceptance journeys

1. Create a group with two unrelated peer Accounts; neither becomes `Account.parent`.
2. Open each Account, inspect Group Members and navigate to the other.
3. Remove one member; empty state and current group members update after refresh; revisit after replay to show no reseeding.
4. Add differently named firm, move one Account to another group with clear confirmation, and inspect audit.
5. Verify Staff/Intake denied write on direct API, Manager/Admin allowed, group deletion protected.
6. Verify legacy Account parent graph exactly unchanged and Stream/Account/History panels preserved.
