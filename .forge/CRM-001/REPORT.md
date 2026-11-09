# CRM-001 - ESCALATED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-001   Candidate: 46e0a1852080faa94d5c0d9332d5d5c14d0cf6c5   Base: 096748c8b4dfdab22070e1e802c6614fdf54465c

Change:
- Compose project `crm-dev` with `crm-app`, `crm-daemon` and `crm-db`, digest-pinned, on `crm-net`, published on loopback only.
- EspoCRM `custom/` metadata: parent and branches self-link; tier, industry, practice management system and learning-platform access fields; duplicate checks on firm name plus postcode, and on contact email.
- Deterministic stdlib seeder; dev-guarded backup, restore and export scripts.
- Unit and acceptance tests; BUILD.md usage section.

Tests:
- `python3 -m unittest discover -s tests/unit -v` -> 62 OK.
- `bash -n` on all scripts -> OK.
- Tester applied 21 mutations; every one fails the suite.
- gitleaks clean.

Reviews (final candidate): Auditor PASS, Tester INCONCLUSIVE (browser unavailable on host), DevSecOps PASS
Rounds: 1; executions engineer/auditor/tester/devsecops = 1/1/1/1 of 4

Findings (all advisory):
- ro-custom-under-docroot / custom-ro-nested-mount: check first-run install at the operator stage.
- espo-conventions-unverified: confirmed by AC3/AC6/AC7 at the operator stage.
- restore-leaves-new-tables, restore-arbitrary-source, csv-formula-injection, plaintext-base-url: deferred; dev and synthetic data only.

Open items / reason: browser-only escalation (CRM-D013). This is not acceptance. Still to do: the operator stage (AC3-AC9 against the running stack, under separate authorisation) and Matt's walkthrough (AC10).

Pushed: yes (forge/CRM-001)
