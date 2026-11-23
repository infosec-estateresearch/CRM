# CRM-WIP-LINK-001R2 - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-WIP-LINK-001R2   Candidate: cbfeca7668374a8c02945b21930845394501fad6   Base: 3a5e7cd13bb31bd84c7f21ff4c9a5dc42ee40aea
Change: Added marker-guard tests (install/update/removal x symlink, dangling symlink, outside-canary symlink, directory, FIFO; second-pass planted-while-stopping; positive controls) and mutation-table entries M05, M05a-M05d. Added `@`-anywhere rule tests for wipBaseUrl, and reworded the two docs statements in docs/WIP-LINK.md. scripts/deploy_custom.sh, the handler, the metadata and test_scripts.py are byte-identical to the base (blob ids checked by the PL).
Tests: `python3 -B -m unittest discover -s tests/unit` -> 619 tests OK (baseline 609, +10, none removed; no new skip). JavaScript not executed in the sandbox.
Reviews (final candidate): Auditor PASS, Tester PASS, DevSecOps PASS (gitleaks 0)
Rounds: 1; executions engineer/auditor/tester/devsecops = 1/1/1/1 of 4 for this ledger. Cumulative for the chain (original + this WO): 2/2/2/2, within the 3/4/4/4 budget.
Mutations: M05, M05a, M05b, M05c, M05d each fail 3-4 of the new marker tests (Engineer, Auditor and Tester each reproduced this by revert-and-rerun). Catching tests: test_marker_that_is_not_a_regular_file_is_refused_on_{install,update,removal} and test_marker_replaced_by_a_link_while_the_stack_stops_is_refused. The handler `@` check is shown non-vacuous by the Tester (4 failures when deleted).
Original advisories: handler-at-sign - resolved (stricter rule written in docs and pinned by tests; handler unchanged). harness-edit-scope - resolved (the test_scripts.py diff equals the 3.3 register, Auditor-verified).
Findings: none
Not done by the PL/specialists (per WO, Orchestrator steps): the full 11-mutation sweep, a fresh export re-run, the R9/D8 browser assurance. Not claimed.
Open items / reason: none
Pushed: see below
