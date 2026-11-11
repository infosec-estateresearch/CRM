WO: CRM-009-I
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main
BROWSER: no

# CRM-009-I — crm-load re-run convergence: Email users, long text, address normalisation

- **Version:** v1.0, 2026-11-11.
- **Authority:** the PO final UAT direction (2026-11-11), which requires no duplicates and idempotent re-import.
- **Defect:** with CRM-009-H in place, re-runs of the real crm-beta load index every record and create nothing. But every re-run (load-2 and load-3, identical results) updates the same 31,509 Emails, plus 15 Tasks, 9 Meetings, 1 Contact and 1 Opportunity. The comparison never converges, so the zero-write re-run acceptance cannot pass.

## Facts (verified by the PL live on crm-beta, EspoCRM 10.0.12)
The PL ran a read-only diagnostic: crm-load against crm-beta with a transport that forwards only GETs and records the attribute keys of the PUTs it would send.
1. **`Email.usersIds`.**
   - It is in 29,697 of the would-be Email PUTs.
   - EspoCRM never returns `usersIds` for Email, on either the list read or the single read. The loader therefore sees it as empty and always merges it.
   - The relation was stored on create: the `email_user` table holds 30,611 rows across 29,516 imported Emails.
2. **Long text truncation.**
   - In the list read, text attributes are truncated to their first 10,000 characters.
   - Example: an Email body is 10,000 characters in the list read and 17,318 in the single read. The list value is an exact prefix, and the single read equals the value the loader sends.
   - This affects `Email.body` and `Email.bodyPlain` (5,706 records). The same rule explains the Task and Meeting `description` repeats.
3. **Address normalisation.** EspoCRM stores email addresses in lower case and may reorder the `;` list.
   - Of 1,500 sampled Email PUTs, `to` differed only in case or order 183 times, `from` only in case 146 times, and `cc` only in case or order 64 times.
   - In the same sample, no address difference was anything else.

## Change
1. **`Email.usersIds`:** set on create only.
   - On update it is never compared and never sent, because the server never returns it.
   - Document this: a later change to an Email's Salesforce user relations is not propagated. Count that as an accepted limitation.
2. **Truncated text** (list-read value of exactly 10,000 characters and a desired value longer than that):
   - If the list value is an exact prefix of the desired value, do one single-record `GET {Entity}/{id}` and compare against that value. Count the read in `reads`.
   - If the list value is not a prefix, it is a real difference.
   - The rule applies to every text attribute the loader compares (Email `body`/`bodyPlain`, Task/Call/Meeting/Opportunity/Account/Contact `description`, and others).
3. **Email `to`/`cc`:** compare as case-insensitive sets of the trimmed `;`-separated addresses. Email `from` is compared case-insensitively. A real difference still sends the mapped value.
4. **Nothing else changes:** create bodies, write order, retries, refusals and exception codes stay as they are.

## Allowlist
- `load/lib/crm_load/engine.py`
- `load/lib/crm_load/mapping.py` (only if needed for item 1)
- `tests/load/fixtures.py`
- `tests/load/test_load.py`
- `docs/IMPORT.md`

## Tests
The fake must emulate the 10.0.12 behaviours above:
- Email reads omit `usersIds`;
- list reads truncate text to a 10,000-character prefix;
- addresses are stored in lower case and the list may be reordered.

Required tests:
- A load followed by a re-run with long bodies, mixed-case and reordered addresses and Email users makes **0 writes**.
- A genuinely changed body beyond 10,000 characters, a genuinely changed address, and a changed short description are still updated.
- Mutation evidence: reverting each item makes its test fail.

## Acceptance
- **A1:** unit and load suites pass as non-root, with mutation evidence.
- **A2 (operator):** a re-run of the crm-beta load makes 0 updates and 0 creates. Records already reported as failed may be re-attempted and are counted separately.
