# CRM-002-V - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-002-V   Candidate: 4a2ee7b57cc01d4de419d9523060de0fcfbd3839   Base: 123b1f0604352c216b48e5cceb0b090adc8b199b (CRM-002-U DELIVERED)   WO: work-orders/CRM-002-V.md v1.0
Change: contract v4 adds `visibleVia` to EmailMessageRelation (via EmailMessage.EmailMessageId and Contact.RelationId), validated at load. Verification counts a row as query-visible only if none of its parents is soft-deleted in the same run's final baseline, and count_query must match exactly; the hidden_via counts go to the manifest. Reconcile gains the class parent_soft_deleted. The synthetic org and selftest cover the L3 shape, plus an unexplained hidden row that gives INCOMPLETE.
Tests: python3 -I -B -m unittest discover -s tests/migrate -t . -v -> Ran 315, OK (skipped=1).
Reviews: round 1 Auditor PASS, Tester PASS, DevSecOps advisory only.
Accepted limit: the query check compares counts, not id sets, so two opposite Salesforce errors on one object could cancel out. The IsDeleted/IsArchived rule shares this limit, and the WO specifies exact count equality. Hardening option for later: compare the id set from an id-only `query`.
Operator stage: O1, L1, then a fresh L3 and reconcile on this commit.
