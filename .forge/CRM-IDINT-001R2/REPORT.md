# CRM-IDINT-001R2 - ESCALATED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-IDINT-001R2   Candidate: abd1b04dd7d91f809ca3bf29fb29c15cf19c449a   Base: 4cb4beca2b8940d63e0706c2d3a50f81cfaee1df
Change: Identity integrity recovery. S1-S2 transactional save and ERm repository/relation classes (atomic relate, unrelate, mass relate); S3 compensating writes removed with in-request audit memory reset on rollback; S4 system-write restriction and in-save link-list refusal; S5 enquiry merge disabled; S6/W1 release settings loop fixed with a stand-in that reads stdin; W3 tests and mutations; W4 live-suite test corrections; W5 docs/IDENTITY-TEST-CHANGES.md; docs updated.
Tests: CRM_PLATFORM_REFERENCE=<reference> python3 -B -m unittest discover -s tests/unit -> 720 tests OK, 0 skipped (Tester and Auditor; A16 test ran, 19 tests). Base was 716.
Reviews (final candidate): Auditor PASS, Tester PASS, DevSecOps PASS. Each gave an explicit S3 conclusion; Tester removed the reset in scratch copies and tests failed on both the save and relation paths.
Early operator gate (SMOKE-E1, uncommitted Engineer work): PASS, all stages. Not acceptance.
Rounds: 1; executions engineer/auditor/tester/devsecops = 1/1/1/1 of 2 (order budget)
Findings: stale-put-back-wording - advisory - comment/doc wording only, not fixed; ledger-reset-scope - advisory - future outer catching transactions must call the reset; enquiry-restore-unaudited - advisory - belongs to CRM-AUDIT-001.
Open items / reason: Escalated solely for browser and live-runtime behaviour. Not observable by any specialist here: A11, A14, A17, A19, A20, A21 and the live parts of A1-A5, A7-A10, A18. The operator proof must be repeated on this unchanged candidate. The S3 rule is covered only by unit tests and review.
Pushed: see below
