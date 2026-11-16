# CRM-CLIENT-001R - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-CLIENT-001R   Candidate: 9271b481e013d4ed76338b49d4f25b89ca79b126   Base: 6e1766980e24d781d498727d4fe5db43cdeadbb7
Change: S1-S2 of the recovery WO. Adds the CRM-owned client/custom/src tree with the AMD release canary, and extends scripts/deploy_custom.sh to deploy it with update-app-timestamp, failure recovery, leftover listing and signal handling (R5). Adds the hardened browser runner, isolation probe, journeys and offline evidence verifier under tests/browser, with the R4 pre-launch order, tests, docs and register entries.
Tests: python3 -m unittest discover -s tests/unit (non-root, copy without Git metadata) -> 642 OK, 2 skipped (baseline 564 OK, 1 skip); tests/load -> 223 OK. AC6b and AC12 belong to CRM-CLIENT-001R-BA and were not assessed.
Reviews (final candidate): Auditor PASS, Tester PASS, DevSecOps PASS
Rounds: 1 review round (one Engineer correction before commit for a commit-scan false positive on a test literal, fixed by generating the value at run time, no suppression); executions engineer/auditor/tester/devsecops = 2/1/1/1 of 4
Findings: doc-register-approval-open - advisory - the three register entries carry approval: none until CGPT accepts them (G3, operator gate before S3)
Open items: S3-S7 assurance sequence (operator run, then CRM-CLIENT-001R-BA). This DELIVERED is not acceptance or merge; the PR is "do not merge: assurance continues in CRM-CLIENT-001R-BA". No beta deployment.
Pushed: see below
