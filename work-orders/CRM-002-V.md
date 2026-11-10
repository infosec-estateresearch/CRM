WO: CRM-002-V
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-002-U
BROWSER: no

# CRM-002-V — Verification for objects whose visibility follows soft-deleted parents (contract v4)

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10 (Issue #9). This follows up the first L3.
- **Parent:** CRM-PBI-005, part 1.

## L3 result (operator, 2026-11-10; counts only)
The first full extraction ran in 2 passes and 572 requests, with the legacy env file unchanged and the run sealed.
- **11 of 12 objects** are `RECONCILED`.
- **`EmailMessageRelation` is `INCOMPLETE`**, for the reason `query_count_mismatch`:
  - `query` count 94,386 against `queryAll` 94,394;
  - `queryAll` matches the id set and the baseline exactly;
  - there are no unexplained missing or new rows and no drift.

`EmailMessageRelation` has no `IsDeleted` field (`softDelete: false`), so the verifier cannot tell which rows `query` hides. The PL classified the 8 hidden rows from the snapshot itself, counts only:
- 4 belong to an `EmailMessage` that is soft-deleted (`IsDeleted = true`);
- 4 have a `RelationId` that is a soft-deleted `Contact`;
- 0 are unexplained.

Salesforce's `query` hides child rows of soft-deleted parents, and `queryAll` returns them.

## Change
1. **Contract v4.** It adds an optional per-object key, `"visibleVia"`: a list of `{"field": <reference field of this object>, "object": <contract object with softDelete true>}`. Set it on `EmailMessageRelation` only:
   - `[{"field": "EmailMessageId", "object": "EmailMessage"}, {"field": "RelationId", "object": "Contact"}]`.

   Bump `contractVersion` to 4. The loader validates the key:
   - it is only allowed when `softDelete` is false;
   - each `field` is a field of the object;
   - each `object` is an earlier contract object with `softDelete` true.

   Order matters: the parents are extracted first.
2. **Verification.** For an object with `visibleVia`, a baseline row is query-visible when, for every entry, its `field` value is not the Id of a soft-deleted row (`IsDeleted = true`) in that parent object's **final baseline of the same run**.
   - `count_query` must equal the number of visible rows **exactly**. Otherwise the object stays `INCOMPLETE`.
   - Record the hidden rows as counts per entry (`hidden_via: {"EmailMessage.EmailMessageId": n, "Contact.RelationId": m}`) in the manifest object details.
   - No other rule changes: every other mismatch still makes the object `INCOMPLETE`.
3. **Reconcile.** `reconcile` gains the deletion class `parent_soft_deleted`, counts only, for rows of `visibleVia` objects hidden through a parent. These rows are not `current`.
4. **Tests:**
   - a synthetic fixture shaped like the L3 result reaches `RECONCILED`, with the `hidden_via` counts;
   - one hidden row that a parent does not explain gives `INCOMPLETE`;
   - a parent declared after the child, or a parent with `softDelete` false, is refused at contract load;
   - the selftest still reaches `RECONCILED`;
   - every existing test still passes.
5. **Docs:** update the `docs/MIGRATION.md` sections on contract v4, `visibleVia`, the verification rule and the `parent_soft_deleted` class.

## Scope
- **Allowlist:** `migrate/**`, `tests/migrate/**`, `docs/MIGRATION.md`, `.forge/CRM-002-V/**`.
- **Excluded:** everything else, Salesforce access, and real data.

## Acceptance criteria
- **AC1:** unit tests pass with non-vacuity.
- **AC2:** gitleaks is clean.
- **Operator stage:** O1, then L1, then a fresh L3 that reaches `RECONCILED` (or `RECONCILED_WITH_DRIFT`) overall. Then `reconcile`, and `SOURCE_EXTRACTED` reported on #9 with counts only.
