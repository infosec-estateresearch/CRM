WO: CRM-006R
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-005
BROWSER: no

# CRM-006R — Continuation of CRM-006 (idempotent importer)

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10 (Issue #9).
- **Why:** CRM-006 was closed BLOCKED by the delivery tooling. Its first engineer round was a planned partial round of a large WO, reported "STATUS: failed" with 6 of 8 build steps done and tested, and the tooling treats that status as terminal. Nothing was reviewed under that id.

## Scope, change and acceptance
**Identical to `work-orders/CRM-006.md` v1.0**, which is authoritative and incorporated here by reference.

There are three PL clarifications, recorded in the delivery prompts:
1. **Contract v4.** The importer accepts snapshots of contract **v4**, which comes from CRM-002-V and adds `visibleVia`. Rows of EmailMessageRelation hidden through a soft-deleted parent are skipped with the reason `parent_soft_deleted`.
2. **ER Import role.** The role gets the EspoCRM boolean scope `Import: true` in `config/access/roles.json`. Core 10.0.12 requires it to archive emails whose `from` is not the API user's own.
3. **Contact roles.** `Contact.opportunityRole.options` is set to the Salesforce `OpportunityContactRole.Role` picklist read at L1, which completes the CRM-004 deferral. Core validates relation roles against these options.

All three are allowlist additions limited to exactly these files and keys:
- `config/access/roles.json` (ER Import `Import` only);
- `tests/unit/access_policy.py`;
- `custom/Espo/Custom/Resources/metadata/entityDefs/Contact.json` (`opportunityRole.options` only), with its i18n;
- `tests/unit/test_enquiries.py` (the Contact metadata assertion).
