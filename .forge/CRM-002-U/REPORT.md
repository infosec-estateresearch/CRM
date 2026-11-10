# CRM-002-U - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-002-U   Candidate: 63c93d0fa9fe059cf6428b5678fab172d75cbd8e   Base: ecf2a169ecd4da1f11147cd122d785ad3f66cfbf (CRM-002-T DELIVERED)   WO: work-orders/CRM-002-U.md v1.0
Change: source-field contract v3, from the L1 schema facts. Account.Interested_in_integration__c is now a picklist and EmailMessageRelation.RelationAddress a string; Opportunity.Post_code__c (a self-lookup) and Key_Information__c (absent) are removed. The gate's type and reference mismatch entries now record the described type and referenceTo as validated identifiers, with anything else recorded as "unrecognised"; logs stay counts-only.
Tests: python3 -I -B -m unittest discover -s tests/migrate -t . -v -> Ran 301, OK (skipped=1). The full selftest reaches RECONCILED, and an L1-shaped fixture passes the v3 gate. The Auditor's own mutation run killed every mutant.
Reviews: round 1 Auditor, Tester and DevSecOps PASS.
Advisories: contractVersion 3.0 is accepted as 3 (as v2 accepted 2.0); _reference_ok raises on a non-hashable referenceTo (fails closed, with no report); the historic ERiC coverage row in the inventory is kept.
Operator stage: O1 and L1 re-run on this commit, then L2 and L3.
