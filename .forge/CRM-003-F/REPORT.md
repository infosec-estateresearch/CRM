# CRM-003-F - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-003-F   Candidate: 769d6cbf11abef42834e1b045c96b4cd7441f474   Base: a34a9516005e899c916675e9aa15b4933150370b (CRM-006S delivery record)   WO: work-orders/CRM-003-F.md v1.0
Change:
- `Currency` is set to `{read: yes, edit: no}` in all 4 roles. EspoCRM 10.0.12's level-based scope refuses `read: all`, and that was found on the first crm-dev deploy (`provision_access` POST Role 400).
- New policy rule `level_scopes`, plus the broken fixture `access_bad_currency_all.json`.
- The 29 existing `access_bad_*.json` fixtures changed in their Currency block only. This is a PL decision, so that each fixture still breaks only its own rules.
- ACCESS.md is updated.
PL facts (live on crm-dev, synthetic probes, deleted):
- `scopes.Currency` has `aclActionList [read, edit]` and `aclLevelList [yes, no]`;
- when each scope of each role was posted on its own, only Currency was refused;
- all 4 corrected roles post with 200.
Tests: unit ran 319, OK; load ran 131, OK.
- Mutations: `read: all` restored gives 5 failures; an extra `delete` action gives 5; the rule disabled gives 8.
Reviews: Auditor, Tester and DevSecOps all PASS in round 1.
