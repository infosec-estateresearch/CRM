# CRM-009-G - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-009-G   Candidate: b77f355df3998fda6cc99f62f7cc422b0a0f10e9   Base: 468ffe5 (main, with the WO merged)   WO: work-orders/CRM-009-G.md v1.0
Change: the beta-safe suite's role check now uses `AdminRoleReader`.
- It is a subclass of ReadOnlyClient, sends GET only, and can read only `Role`.
- It authenticates with the EspoCRM admin through `Espo-Authorization`, using credentials from the environment, never printed or kept.
- With no credentials, the check fails and never skips.
- All other checks use the API key.
- `deploy_release.sh` passes the credentials to the suite through the environment.
Cause: EspoCRM never lets an API-key user read Role, so the first complete crm-beta deploy failed its own acceptance suite (the PL verified this live).
Tests (non-root): unit ran 561, OK. There is mutation evidence.
Reviews: round 1, advisories only.
- Auditor (FINDINGS, advisory only): the env prefix is a no-op, and no test can fail on it.
- Tester (PASS): no test checks argv on the python3 call, the prefix line is unguarded, and output is not checked at fd level.
- DevSecOps (PASS): the prefix is untested, the default urllib redirect handler forwards auth headers (as it already does for the API key), and the tests use exact-match secret scanning.
