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
| CRM-D009 | Test data uses synthetic data first. A later sample keeps firm names, pseudonymises people, and is destroyed at the close of that work. | PROPOSED | PoC D9 |
| CRM-D010 | EspoCRM is the single build candidate, replacing the side-by-side PoC. It uses the official image 10.0.12 and MariaDB 11.4.13, both pinned by digest. Frappe CRM is the fallback if CRM-001's acceptance gates fail. | PROPOSED | GO instruction, 2026-11-06 |
| CRM-D011 | Public-repository disclosure: the bare development hostname may appear (Work Orders need it). Never published: addresses, domains or other host details, credentials, staff, customer or firm names, and Salesforce identifiers. Restricted evidence lives outside this repository. | PROPOSED | Repository is PUBLIC (Matt, 2026-11-03); hostname allowed by the Architect, 2026-11-09 |
| CRM-D012 | Runtime state and secrets sit outside Git, under `/srv/CRM/runtime/<env>/`. Each environment is its own Compose project on its own network, with no published database port and no shared volumes or networks with any other application. | PROPOSED | Infrastructure discovery, 2026-11-03 |
| CRM-D013 | Delivery uses the existing ForgeV2 roles, run as the multi-project PL identity, and only after ForgeV2 sandbox acceptance. ForgeV2 builds and reviews; an authorised operator deploys and demonstrates the functional acceptance criteria with synthetic data; Matt does the walkthrough, accepts and merges. A browser-only ESCALATED result is an acceptable intermediate review result when every other check passes, but it is never final acceptance. Defects found at deployment stay open until corrected and retested. | PROPOSED | Architect decision, 2026-11-09 |

PoC D7 (Microsoft 365 test mailbox and app registration) is a prerequisite for CRM-PBI-006, not a decision.
