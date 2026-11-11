# CRM-009-F - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-009-F   Candidate: cf327dc3ace95e080f35034b95b9ec280a76d13e   Base: 479027a (main, with the WO merged)   WO: work-orders/CRM-009-F.md v1.0
Change: in `deploy_release.sh` step 6, `phoneNumberInternational` is now set with `config:set ... false --type=bool`, and `siteUrl` with an explicit `--type=string`. The strict read-back is unchanged.
Cause: EspoCRM's `config:set` defaults to the string type, so the first crm-beta deploy stopped at step 6 (`''false''`). The PL verified this live.
Tests (non-root): unit ran 556, OK; load ran 202, OK. There is mutation evidence for both the reverted fix and a loosened read-back.
Reviews: round 1, Auditor, Tester and DevSecOps all PASS, with advisories only: a redundant assert, A2 being operator-only, and shellcheck not being available.
