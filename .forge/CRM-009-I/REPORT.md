# CRM-009-I - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-009-I   Candidate: 4265b71501958ce30407eebc76ebe2b638f0a186   Base: c3c0fef (main, with the WO merged)   WO: work-orders/CRM-009-I.md v1.0

Change: crm-load re-run convergence against EspoCRM 10.0.12.
- Email `usersIds` is sent on create only. This is an accepted limitation: later Salesforce user-relation changes are not propagated.
- A list-read text of exactly 10,000 characters that is a prefix of a longer desired value is re-read once with a single GET before comparing.
- Email `to`/`cc` are compared as case-insensitive address sets, and `from` case-insensitively.
- Create bodies, write order, retries, refusals and exception codes are unchanged.

Round 1: auditor PASS; tester FINDINGS (advisory only); devsecops PASS (advisory only). Advisories:
- text-shortened-to-cut: a stored value over 10k characters whose source shrinks to exactly its first 10k characters is not written.
- addr-dup-collapse: a source address list that differs only by a repeated address counts as equal.
- single-read-transport-error: more records can now reach the single read; a non-200 response there raises read_failed, as the existing phone read does.
Tests (non-root): unit 561 OK; load 223 OK; mutation evidence for each item.
A2 (operator): the crm-beta re-run is performed by the PL after release.
