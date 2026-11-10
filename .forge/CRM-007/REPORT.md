# CRM-007 - ESCALATED (continued in CRM-007R)
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-007   Candidate: 82c05ef3abe444c1f8f01a0ed11483e526e27f40   Base: e1f9a6899e82ac5862849db0bf1f00dbcae51244   WO: work-orders/CRM-007.md v1.1
Change:
- `dev|beta` targets for all CRM-001 scripts, with beta pinned to `/srv/CRM/runtime/beta`.
- **Edge:** `crm-beta-edge` runs HAProxy 3.2.26 LTS, pinned by digest and registered. It uses host networking, admits only the upstream source list (validated private /32s) and gives 403 to everything else. Its rendered config is revalidated byte for byte.
- **crm-app (beta)** is loopback-only, with HTTPS forced on.
- **Compose:** a per-service key allowlist, with images pinned by digest.
- **Release bundle:** `release.sh`/`release.py` build a reproducible bundle that excludes `.forge/`. `deploy_release.sh` requires a mandatory `--sha256` anchor and verifies and unpacks from one private copy, then runs `verify-tree`, which checks content and modes.
- **Backups and restore:** a restoretest project with isolation checks, systemd timer templates (never installed by scripts), and `CRM_DB_DIR` checked on both targets.
- **Beta-safe acceptance:** a GET-only suite.
- **Docs:** BETA.md, RELEASE.md, BUILD.md, README Usage.
Tests: unit ran 407, OK; load ran 112, OK. There is mutation evidence for every guard.
Reviews:
- Round 1 BLOCKING: the bundle was self-attested, and `CRM_DB_DIR` was unchecked. Both were fixed in round 3.
- Round 2 BLOCKING: the README status line was outside the allowlist; it was reverted in round 4. Advisories were fixed in round 4.
- Round 3 BLOCKING:
  - `restore.sh` accepts the other environment's backup, and `CRM_BACKUP_DIR` can be overridden for beta;
  - `provision_access`/`provision_users beta` don't pin `CRM_BASE_URL`.
- The engineer execution limit was reached, so the work continues as CRM-007R.
Advisories carried to CRM-007R:
- the `CRM_DEPLOY_ROOT` seam;
- the deploy reports success when provisioning and acceptance are skipped;
- the compose network spec isn't restricted;
- AC5 (browser) is for the operator stage.
