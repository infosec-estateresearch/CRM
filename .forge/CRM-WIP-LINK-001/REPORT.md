# CRM-WIP-LINK-001 - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-WIP-LINK-001   Candidate: 3a5e7cd13bb31bd84c7f21ff4c9a5dc42ee40aea   Base: 6e1766980e24d781d498727d4fe5db43cdeadbb7
Change: "Open WIP / Revenue" button on the Account detail page (clientDefs `menu` item plus AMD handler `client/custom/src/handlers/account-open-wip.js`, link only, no network/storage). Minimal client-asset delivery added to `scripts/deploy_custom.sh` (stage, `mv -T` swap, `update-app-timestamp` cache-bust, marker-based managed removal, restore on failure with exit codes 20-30, leftovers listed). New tests `test_wip_link.py` and `test_client_delivery.py`; docs `docs/WIP-LINK.md`; limited edits to `docs/BUILD.md` and `tests/unit/test_scripts.py`.
Tests: `python3 -m unittest discover -s tests/unit` -> 609 tests, OK (base 564, OK, 1 skipped; +45 new tests). JavaScript is NOT executed in the sandbox; the behaviour table and delivery journeys D1-D7 are for the operator annex (WO section 8).
Reviews (final candidate): Auditor FINDINGS (two advisory-only findings, no blocking), Tester PASS, DevSecOps PASS (gitleaks 0)
Rounds: 1; executions engineer/auditor/tester/devsecops = 1/1/1/1 (Engineer cap 3, 2 unused)
Findings:
- handler-at-sign - advisory - handler rejects any "@" anywhere in the base (stricter than WO 3.1, which rejects user-info only); fails closed, I verified it at handler lines 47-49; left as is.
- harness-edit-scope - advisory - fake-docker harness in test_scripts.py gained `update-app-timestamp` / `appTimestamp` cases (not an assertion; needed by the new cache-bust). Listed here.
test_scripts.py edits (reasons): (1) FAKE_DOCKER fixture: two new cases for the timestamp calls; (2) new constant READ_TS; (3) test_running_app_gets_clear_cache_then_rebuild: expected calls now end with read, update-app-timestamp, read; (4) test_writable_dirs_are_made_private_after_the_stop: expected chown list gains `client/custom`.
Non-vacuity: Tester broke the handler (protocol, user-info, query/fragment, encodeURIComponent, noopener, fallback host, hard-coded host: all caught) and the script (marker, leftovers, swap: caught; `! -L` in real_dir is an equivalent mutation, covered by `realpath -e`). Engineer: 23 handler mutations and 27 script-rule removals all detected.
Open items for the Orchestrator / CGPT:
- AC6 asks for PASS from all three reviewers; the Auditor's verdict word is FINDINGS (advisory only). The ledger permits delivery. If CGPT wants a literal PASS, two Engineer executions remain, but the only possible correction would loosen the "@" check.
- Unverified in a real EspoCRM (annex): that `update-app-timestamp` stores `appTimestamp` where the script reads it (`data/config.php` / `config-internal.php`); whether `wipBaseUrl` reaches non-admin users' `getConfig()` (annex J3).
- Engineer's choices where the WO was silent: an unmanaged runtime `src` is replaced on install with a notice (old tree kept until success); with the stack not running the cache steps are skipped and the script says so; "RECOVERED ... left stopped" when crm-app was not running.
- BUILD.md has two nearby sentences edited beyond the two named statements (swap order, post-restart command list).
Pushed: see below
