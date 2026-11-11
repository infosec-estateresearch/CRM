WO: CRM-009-H
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main
BROWSER: no

# CRM-009-H — crm-load paged read: handle an unknown list total (Email)

- **Version:** v1.0, 2026-11-11.
- **Authority:** the PO final UAT direction (2026-11-11).
- **Defect:** the first real crm-beta load created every Email it could, but its index read and the relationship reconciliation saw only the first page of Email. As a result:
  - `index entity=Email records=200`, although 34138 Emails with an sfId exist in the database;
  - `activity_parents` reported espocrm 12666 against a snapshot of 46535;
  - a re-run would try to create about 33.9k Emails again. The `sf_id` unique index rejects these with HTTP 500, so the idempotency acceptance (0 writes on re-run) cannot pass.

## Facts (verified by the PL live on crm-beta, EspoCRM 10.0.12)
- `GET Email?maxSize=1&where[0][type]=isNotNull&where[0][attribute]=sfId` returns `total: -1` with a non-empty `list`. EspoCRM does not count Email lists.
- The same request for Meeting returns the true total, 2943.
- `load/lib/crm_load/api.py` `list_all` stops when `offset >= int(doc.get("total", 0))`. With total -1, it stops after the first page.
- `scripts/crm_api.py` `list_all` already treats a negative total as unknown and pages until a page comes back empty.
- A direct read-only DB count gives Email 34138, Task 9213, Call 495 and Meeting 2943 records with an sfId. Of these, 33986, 9050, 492 and 2925 have a parent: 46453 in total.

## Change
1. **`load/lib/crm_load/api.py` `list_all`.**
   - A missing, non-integer or negative `total` means the total is unknown. Keep paging, advancing the offset by the rows received, until a page returns fewer rows than `PAGE` (including an empty page).
   - With a non-negative total, the existing behaviour is unchanged.
   - When a total is known and the records read do not equal it, raise `TransportError("list_incomplete", ...)`. The read stays GET only.
   - No other client behaviour changes.
2. **`tests/load/fixtures.py`.** Add an option for the fake list endpoint to return `total: -1` for chosen entities (for example Email), as in 10.0.12. The default stays unchanged.
3. **`tests/load/test_load.py`.** Add tests:
   - more than 200 Emails with `total: -1` are all indexed;
   - a re-run makes 0 writes;
   - `activity_parents` matches.
   - Include mutation evidence: reverting the fix makes the new tests fail.
4. **`docs/IMPORT.md`.** Add one line: paged reads tolerate an unknown total.

## Allowlist
- `load/lib/crm_load/api.py`
- `tests/load/fixtures.py`
- `tests/load/test_load.py`
- `docs/IMPORT.md`

## Acceptance
- **A1:** the unit and load suites pass, run as non-root, with mutation evidence.
- **A2 (operator):** a re-run of the crm-beta load from the new release indexes every Email, makes 0 writes, and reports equal relationship totals, apart from records the report lists as failed or unresolved.
