# CRM-CLIENT-001R2 - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-CLIENT-001R2   Candidate: 07bfaf1c01c633d6c45aba16d6587733a8c7f6a1   Base: 6e1766980e24d781d498727d4fe5db43cdeadbb7
Change: Delivers the version-controlled CRM client customisation mechanism: the `client/custom/src/` canary, `deploy_custom.sh` client deploy with cache-bust, failure recovery and signal handling, the browser runner, verifier and fixtures, docs and register entries. Image re-pin I1: runner image `v1.65.1-noble` (index 0ab41a37, amd64 ce84a3d7, config eccd588f) in the register and the verifier, with the previous pin rejected by name.
Tests: `python3 -B -m unittest discover tests/unit` as non-root from a `git archive` copy -> 643 OK, 2 skipped (base 564 OK); tests/load 223 OK; ten Tester mutations each caught. AC6b and AC12 are for the BA WO.
Reviews (final candidate): Auditor PASS, Tester PASS, DevSecOps PASS
Rounds: 1; executions engineer/auditor/tester/devsecops = 1/1/1/1 of 4
Findings: doc-register-approval-open - advisory - covered by the G1/I2 approval; entry-sh-exec-bit - advisory - no action (script run via bash, outside client/custom)
Open items / reason: S2 complete; candidate C frozen. Not accepted or merged: assurance continues at S3-S4 and in CRM-CLIENT-001R2-BA. AC8 M1-M4 mutation procedure is an Orchestrator host step; the Tester relied on the in-suite guard tests.
Pushed: see below
