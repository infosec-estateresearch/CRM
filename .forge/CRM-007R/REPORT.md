# CRM-007R - DELIVERED (continuation of CRM-007)
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-007R   Candidate: ab106746793fbe2b218c02c83280d749326f4fe3   Base: e09dfb8a2478be2ce31f66735d3e724651ad2c6a (CRM-007 escalation record)   WO: work-orders/CRM-007R.md v1.0 (with CRM-007 v1.1)
Change: crm-beta isolation follow-up.
- **Backups are bound to their environment.**
  - `CRM_BACKUP_DIR` is a constant.
  - A `TARGET` marker is covered by `SHA256SUMS`.
  - `restore.sh` accepts only `crm-<target>-<stamp>` directly under the target's own backup dir.
  - `--legacy-unmarked` is dev-only and accepts only stamps before `20261111T000000Z`.
- **Exports are bound to their target:** an export goes only to a bare-named new directory under the target's backup dir, and its URL is pinned for both targets, in `export.sh` and in `export_csv.py`.
- **Provisioning is pinned:** `provision_access` and `provision_users` accept only the target's own URL (beta `http://127.0.0.1:<app port>`; dev `http://<CRM_BIND_IP>:8180`).
- **The deploy root is constant**, with ownership and mode checks.
- **Deploy is fully verified:** it refuses to start without its provisioning and acceptance inputs, and writes no report with skipped steps.
- **Compose policy:** beta networks are bridge/internal only. The restoretest compose is a full allowlist: the top level, crm-db keys and mount options.
Tests: unit ran 476, OK; load ran 112, OK. There is mutation evidence for every item, and the earlier reviewers' cross-environment probes are all refused before any request.
Reviews:
- Round 1 BLOCKING: export was not bound to its target. Fixed.
- Round 2 BLOCKING: the restoretest policy was a denylist, so `include` was accepted. Fixed.
- Round 3: Auditor, Tester and DevSecOps all PASS.
Advisories carried:
- restoretest values (network attachment, environment) are not value-checked; the network is internal, so nothing crosses environments;
- the restoretest image is checked for shape, not against the registered digest;
- `--legacy-unmarked` doesn't check that a stamp is a valid UTC time.
- AC3–AC7 are for the operator stage.
