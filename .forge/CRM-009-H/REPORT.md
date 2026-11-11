# CRM-009-H - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-009-H   Candidate: 3c54f73f769e5c1eb4489b1be6475d8236c287bc   Base: e131266 (main, with the WO merged)   WO: work-orders/CRM-009-H.md v1.0

Change: crm-load `list_all` handles the EspoCRM 10.0.12 Email list's unknown total (-1).
- An unknown total (missing, non-integer, bool or negative) pages until a page comes back short.
- Every page is ordered by id ascending, and rows are de-duplicated by id.
- A full page that adds no new id, or reaching the 10,000-page ceiling, raises `list_stalled`.
- A known total must equal the distinct rows read; otherwise `list_incomplete` is raised.

Round 1: the tester found one blocking issue (unknown-total-unbounded-loop); the reviewers also raised advisories on ordering and de-duplication. Corrected in round 2.
Round 2: auditor PASS, tester PASS, devsecops PASS, with advisories only:
- known-total-request-shape / known-total-path-additions: the known-total path also gains ordering, de-duplication and the stall guard. This is wider than "unchanged" but intended.
- mutation-evidence-shape / mutation-evidence-scope: reverting the whole file makes most tests error, because the fake asserts orderBy on every page.
- unknown-total-short-cap: if recordListMaxSizeLimit were ever set below 200, an unknown-total read would stop early.
Tests (non-root): unit 561 OK; load 218 OK.
A2 (operator): the crm-beta re-run is performed by the PL after release.
