# Decisions — Estate Research CRM

Nothing in this file is approved yet. Each row records its status. Approval goes on the GitHub Issue that names the exact version of this file.

| ID | Decision | Status | Source |
|---|---|---|---|
| CRM-D001 | Fork policy: upstream core unmodified. ER code lives in an extension (`custom/`). Any unavoidable core change is a numbered patch file, re-applied and tested at every upgrade. | PROPOSED | PoC D1 |
| CRM-D002 | Paid extensions are allowed only case by case, on a 5-year cost basis. None are used in CRM-001. | PROPOSED | PoC D2 |
| CRM-D003 | Enquiries stay in the CRM for now. Revisit with the Case Manager owners before CRM-PBI-004. | PROPOSED | PoC D3 |
| CRM-D004 | Firms are modelled as office-level records with a parent (head office) link, as in Salesforce today. | PROPOSED | PoC D4 |
| CRM-D005 | Email attachments: body only at first, with attachment names listed. | PROPOSED | PoC D5 |
| CRM-D006 | System of record: the CRM owns firms, contacts, enquiries and activities. Case Manager owns cases, WIP owns financial WIP, and ERic reads all of them and owns none. | PROPOSED | PoC D6 |
| CRM-D008 | Named users only. The shared login ends. | PROPOSED | PoC D8 |
| CRM-D009 | Data progression: (1) synthetic data (CRM-001); (2) a pseudonymised sample that keeps firm names and is destroyed when PBI-005 closes; (3) approved Salesforce data, **only** in the beta environment and only after Matt's data-protection approval (PBI-011). Real data never enters this repository. | PROPOSED | PoC D9; beta direction 2026-11-09 |
| CRM-D010 | EspoCRM is the single build candidate, replacing the side-by-side PoC. It uses the official image 10.0.12 and MariaDB 11.4.13, both pinned by digest. Frappe CRM is the fallback if CRM-001's acceptance gates fail. | PROPOSED | GO instruction, 2026-11-06 |
| CRM-D011 | Public-repository disclosure: the bare development hostname may appear (Work Orders need it). Never published: addresses, domains or other host details, credentials, staff, customer or firm names, and Salesforce identifiers. Restricted evidence lives outside this repository. | PROPOSED | Repository is PUBLIC (Matt, 2026-11-03); hostname allowed by the Architect, 2026-11-09 |
| CRM-D012 | Runtime state and secrets sit outside Git, under `/srv/CRM/runtime/<env>/`. Each environment is its own Compose project on its own network, with no published database port and no shared volumes or networks with any other application. | PROPOSED | Infrastructure discovery, 2026-11-03 |
| CRM-D013 | Delivery uses the existing ForgeV2 roles, run as the multi-project PL identity, and only after ForgeV2 sandbox acceptance. ForgeV2 builds and reviews; an authorised operator deploys and demonstrates the functional acceptance criteria with synthetic data; Matt does the walkthrough, accepts and merges. A browser-only ESCALATED result is an acceptable intermediate review result when every other check passes, but it is never final acceptance. Defects found at deployment stay open until corrected and retested. | PROPOSED | Architect decision, 2026-11-09 |
| CRM-D014 | Salesforce stays the system of record, read-only to this project, until cutover (PBI-015). The beta holds a copy: beta entries are trial entries, and staff keep working in Salesforce. | PROPOSED | Beta direction, 2026-11-09 |
| CRM-D015 | The import is repeatable and idempotent. Every migrated record stores its Salesforce id as an external key. Each run produces a reconciliation report and a rejects list. Mapping and clean-up rules are code and documentation in this repository; the extracted data lives only in the restricted runtime. | PROPOSED | PoC G5-3; usage assessment §7 |
| CRM-D016 | Beta acceptance is not cutover approval. The beta does not require live Outlook filing; cutover does (PBI-014). | PROPOSED | Beta direction, 2026-11-09 |
| CRM-D017 | Delivery is fully containerised. Customers install from a versioned release bundle plus images pinned by digest, needing only Docker Engine and Compose. The production image bakes ER customisations into an image built from the pinned upstream image; the core is not forked (CRM-D001). Dev stacks may bind-mount `custom/`. Beta and production use the same release. | PROPOSED | Product Owner, 2026-11-09 |
| CRM-D018 | Lowercase `crm-` prefix on Compose services, networks, named volumes and ER images (e.g. `crm-app`, `crm-net`, `crm-espocrm`). Each environment has a distinct project name (`crm-dev`, `crm-beta`, `crm-prod`). No hard-coded `container_name` unless an operational need is recorded; Compose generates instance names from project and service. Lowercase because Docker requires it for project and image names. | PROPOSED | Product Owner, 2026-11-09 |
| CRM-D019 | LAN access to the dev CRM (dev only). **Why:** Matt instructed direct access from the two authorised internal networks. This supersedes CRM-001's loopback-only access for dev. **Bind:** `crm-app` publishes 8180 on the host's LAN address only (`CRM_BIND_IP`), never on `0.0.0.0`, and no longer on `127.0.0.1`. The database and the daemon publish nothing. **Enforcement layer:** Apache inside `crm-app`. A read-only, Git-controlled `<Location "/">` holds `AuthMerging And` and `Require ip 127.0.0.1 ::1 ${CRM_ALLOWED_SOURCES}`, so it can only narrow the authorization that already applies. Apache is used because the standing rule rules out host firewalls (no iptables, ufw or nftables, so no `DOCKER-USER` chain). No header is trusted (no `mod_remoteip`). Addresses live only in the runtime env file. **Fail closed:** `scripts/check_access.py dev` refuses bad values (the bind address must be RFC 1918 and inside an allowed network). `scripts/up.sh dev`, `deploy_custom.sh` and `restore.sh` run it before any `up`, refuse any env-file name set in the shell environment, and remove every such name from Compose's environment. A raw `docker compose up` skips the check; Compose refuses an unset or empty variable. Apache does not start if the variable is undefined, and admits loopback only if it is empty. **Residual risks:** plain HTTP on the LAN; every host in the authorised networks reaches the login and admin UI; address-based trust admits a compromised host inside those networks; host-local processes may be admitted. The Apache merge behaviour and source-address preservation are still to be confirmed at the operator stage. **TLS is mandatory before any real data** (CRM-PBI-008). | PROPOSED | Architect directive "CRM-001 authorised LAN access change", on Matt's instruction |

PoC D7 (Microsoft 365 test mailbox and app registration) is a prerequisite for CRM-PBI-006, not a decision.

Open decision for PBI-016: how the ER image reaches a customer host, either as a registry package or as an offline image archive in the release bundle.

Business decisions needed before PBI-005 can close:
- whether to archive firms with no recorded activity;
- how to treat the legacy notes;
- how to resolve the flagged duplicate sets.

## Expanded scope — proposed decisions (2026-11-13)

These come from the CGPT Architect delivery package of 2026-11-13 (`CRM-D-W01` to `W13`; mapping in [`docs/initiation/2026-11-13-existing-product-reassessment.md` §9](docs/initiation/2026-11-13-existing-product-reassessment.md#9-decision-id-mapping)).
- **Status:** all are PROPOSED. PO-agreed concepts still need Matt's exact-version approval, recorded on GitHub.
- **Earlier rows:** none of the rows above is rewritten. CRM-D004 and CRM-D006 are amended by CRM-D031, not edited.
- **Doctrine:** these are CRM product decisions, not FOUNDRY or ForgeV2 doctrine.

| ID | Decision | Status | Source |
|---|---|---|---|
| CRM-D020 | CRM owns Accounts, Contacts, Firm Groups, Enquiries, staff identities and their relationships. WIP reads these and never becomes a competing master. | PROPOSED | PO direction (conversation), 2026-11-13 |
| CRM-D021 | The new WIP is a **CRM functional module**: one CRM product and release, with WIP's domain and extension code kept separate and independently testable. Ordinary CRM work must survive a WIP failure. This is logical separation, not process isolation. | PROPOSED | PO direction, 2026-11-13 |
| CRM-D022 | New WIP code and documentation live in this repository. The legacy WIP repository, database, workbook and source history stay unchanged: no submodule, subtree, cross-repo runtime dependency or history merge. | PROPOSED | Architect, 2026-11-13 |
| CRM-D023 | An independent `FirmGroup` entity with an optional Account `firmGroup` link (zero or one group per firm), not a designated group-Account. Peer firms can share a group without a parent. ER Managers and Admins change membership; ER Staff and Intake view. The Salesforce-derived `parent`/`branches` link (CRM-D004) is kept and stays independent. | PROPOSED | PO and Architect, 2026-11-12/13 |
| CRM-D024 | **No blanket seeding** of Firm Groups from the 1,366 Salesforce parent trees. Rogue proposed this on 2026-11-12; it is withdrawn on HELM evidence (the 36 curated WIP groups are mostly subsets of a tree or cross several trees). Population is a separate, reviewed, PO-authorised data operation (CRM-PBI-024). | PROPOSED | Architect correction on HELM evidence, 2026-11-13 |
| CRM-D025 | The first WIP capability is an **Account WIP/Revenue tab**: a list for that firm only, validated add/edit, and the correct Account link. A broad dashboard or an importer is not a prerequisite. | PROPOSED | PO MVP scope, 2026-11-13 |
| CRM-D026 | A left-hand **WIP/Revenue** navigation workspace comes only *after* the Account MVP is accepted. It must be functional, never an inert placeholder. | PROPOSED | PO, 2026-11-13 |
| CRM-D027 | `WipCase` has a required CRM `accountId` (exposed as `firmId`). WIP exposes the current, **derived, read-only** `firmGroupId` (`groupId`) from CRM. WIP never stores or edits group membership. A group move changes current views, not financial rows. | PROPOSED | PO identity requirement, 2026-11-13 |
| CRM-D028 | **Revenue is not defined.** Workbook month sheets are instruction cohorts and revisions, and `actual_yield` is a blended field. There is no automatic revenue, period-flow, snapshot or group-sum interpretation until the PO defines revenue (CRM-PBI-026). | PROPOSED | Architect, financial integrity, 2026-11-13 |
| CRM-D029 | WIP financial access is **deny-by-default**, separate from general CRM Account read (R12), and enforced in the server, the API and the GUI, with attributable change history. | PROPOSED | Architect, security, 2026-11-13 |
| CRM-D030 | The interim workbook/CSV path stays separate from the manual MVP. A later importer needs a verified source contract, recovery of the skipped sheets, a deterministic Salesforce-id crosswalk, rejects, provenance and an approved real-data migration. | PROPOSED | Architect, import, 2026-11-13 |
| CRM-D031 | **Amends CRM-D004 and CRM-D006.** D004 (parent/head-office link) stays valid for the historical branch hierarchy, alongside Firm Groups (D023). D006's "WIP owns financial WIP" now means the CRM's WIP module owns financial case *references* and observations. **Case Manager provenance:** D006's "Case Manager owns cases" is a *proposed* ownership boundary from the PoC (D6), not a verified operational integration. HELM could not inspect Case Manager directly, and no CRM–Case Manager interface exists or is specified. The WIP module must not replace any operational or legal Case Manager function without separate product authority. | PROPOSED | Architect, 2026-11-13 |
| CRM-D032 | Work proceeds through the FOUNDRY Stage 1 existing-product reassessment, the revised living Vision and Backlog, and separately exact-approved, bounded WOs. No broad approval substitutes for any WO. | PROPOSED | FOUNDRY Stage 1 v0.4 |

Questions held for later PO decisions; they do not block the synthetic MVP:
- which staff may read, add or edit WIP financials (proposed start: a dedicated WIP Finance grant, admins for operator UAT, everyone else denied);
- the live transitional exchange format (XLSX or CSV);
- what qualifies as revenue;
- source correction of the skipped sheets, impossible or missing dates, the reject backlog and the summary-formula typo;
- whether Case Manager keeps the operational case records (default: yes);
- whether group financial reporting uses current or historical membership (current for the MVP; historical deferred).
