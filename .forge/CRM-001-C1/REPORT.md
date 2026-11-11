# CRM-001-C1 - ESCALATED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-001-C1   Candidate: ccde74094a776b39c006e5cd48f197e4add3687e   Base: 426bb86571dfc5ff73b67bbacd8f34d1a539d0a5
Change: Bounded correction of CRM-001 per the Architect review of PR #3. crm-app/crm-daemon now bind-mount data, custom and client/custom separately (EspoCRM 10 layout; nothing over /var/www/html), read-write because the image entrypoint chowns them under set -e. Git custom/ is deployed into the runtime by scripts/deploy_custom.sh dev. Backup/restore cover db + the three dirs; tests, env.example, BUILD.md §7 and README updated.
Tests: python3 -m unittest discover -s tests/unit -v -> Ran 79 tests, OK (Tester, Auditor and DevSecOps each re-ran it); bash -n all scripts OK; 14 broken compose fixtures all fail; script round trips with a stub docker pass; gitleaks no leaks.
Reviews (final candidate): Auditor PASS, Tester INCONCLUSIVE (browser only), DevSecOps PASS
Rounds: 1; executions engineer/auditor/tester/devsecops = 1/1/1/1 of 4
Findings: admin-ui-writable-claim - advisory - open (BUILD.md:138 overstates; spot-checked); browser-unverified - advisory - operator stage/AC10; image-behaviour-unconfirmed - advisory - confirm at operator stage; deploy-custom-symlink - advisory - fix before real data (spot-checked: no -L/realpath guard); env-path-divergence - advisory - open; restore-arbitrary-source - advisory - deferred by Architect, before real data; csv-formula - advisory - deferred by Architect, before real data
Open items / reason (ESCALATED or BLOCKED only): The Tester cannot drive a browser on DOCKER1 (CRM-D013 browser-only escalation). AC3–AC9 need the separately authorised operator stage; AC10 is Matt's walkthrough.
Pushed: yes (forge/CRM-001-C1)
