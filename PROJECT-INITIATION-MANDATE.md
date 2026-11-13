# Estate Research CRM — Project Initiation Mandate (PIM)

- **Status:** DRAFT for Architect review. Not approved, and grants no implementation authority.
- **Reassessment (2026-11-13):** the product scope is being expanded (Firm Groups, WIP/Revenue module) under a FOUNDRY Stage 1 v0.4 existing-product reassessment. The dated addendum [`docs/initiation/2026-11-13-existing-product-reassessment.md`](docs/initiation/2026-11-13-existing-product-reassessment.md) records the current product truth, including stale statements in this file such as B1. This file is otherwise unchanged and keeps its historical content.
- **Prepared by:** Rogue (Orchestrator), 2026-11-06, from the evidence listed in section 8.
- **Governing FOUNDRY:** `maff0000/foundry` at `5f5e4a51f8909d134c46ef8b43a9bd20d086fcc0`: `stages/01-product-discovery.md`, `standards/project-scaffolding.md`, `standards/product-records.md`, `standards/secure-engineering.md` and `standards/work-order-contract.md`.
- **Naming:** this is the FOUNDRY PIM, which the Product Owner calls the "PID". It is not a ForgeV1 `PID.md` (FND-043).

## 1. Product identity

| Item | Value |
|---|---|
| Product | Estate Research CRM |
| Owner | Estate Research Limited. Product Owner: Matt Scott. |
| Route | NEW product, replacing an existing Salesforce process. Usage is evidenced from Salesforce's own records (read-only). |
| Repository | `github.com/infosec-estateresearch/CRM`, public. Default branch `main`, created by the bootstrap commit. |
| Development execution target | `DOCKER1:/srv/CRM`. The canonical checkout is `/srv/CRM/main` and the worktree parent is `/srv/CRM/worktrees`, both owned by the multi-project PL identity. Only the bare hostname is published. Addresses and other host details are kept in restricted records (decision CRM-D011). |
| Runtime state | `/srv/CRM/runtime/<env>/`. This sits outside Git, is root-owned and has mode `0700`. It holds Compose env files and bind-mounted data. It is never in the checkout or in worktrees. |
| Delivery engine | ForgeV2, `maff0000/forgev2`, pinned at `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`, plugin 0.3.0. **Sandbox acceptance is BLOCKED** (ENGINE-SANDBOX-TEST-001, forgev2#5). |
| Out of scope | Every other application and service on the host. CRM work does not inspect, change or connect to them; a shared-host conflict is reported, not remediated. The ForgeV2 and FOUNDRY installations are used read-only. |

## 2. Product intent

Replace Estate Research's dependency on Salesforce with a self-hosted, open-source CRM that Estate Research owns. Deliver it incrementally, starting with what staff use most: **law firms (including head office and branch structure) and the people at them**. Do not recreate Salesforce. See `PRODUCT-VISION.md`.

## 3. Scope of initiation

**In scope:**
- the project records: README, Vision, Backlog, Decisions and the external code register;
- the build and deployment boundary (`docs/BUILD.md`);
- the first bounded WO draft (`work-orders/CRM-001.md`).

**Out of scope until separately approved:**
- installing EspoCRM;
- any data from Salesforce;
- any production service, container, database or network change;
- any change to Marketing, Email Builder, EmailEngine, ERic, WIP or Case Manager.

## 4. Candidate technology (not yet approved)

- **EspoCRM** is the leading candidate (AGPL-3.0, PHP 8, MariaDB). It runs as the official image, 10.0.12, pinned by digest, with MariaDB 11.4.13 (see the register).
- **Frappe CRM** is the fallback if EspoCRM fails CRM-001's acceptance gates (CRM-D010).
- Selection becomes final only after evidence from CRM-001 and Architect acceptance.

## 5. Security context

**Data sensitivity:** firm business data, personal data of professional contacts, and later enquiry details about deceased estates. That is personal data under UK GDPR.

**Trust boundaries:**
- staff browser → CRM;
- CRM → its database;
- ERic → CRM (read-only API, later);
- Outlook filer → CRM (later).

**Controls required before any real data is loaded:**
- named user accounts;
- TLS before any LAN or staff access;
- backups covered and restore tested.

**External code:** every image and dependency is registered in `security/EXTERNAL_CODE_REGISTER.yaml` before it is used.

**Public repository:** no host identity, addresses, credentials, staff names, customer or firm names, or Salesforce identifiers.

## 6. Delivery and authority

- **Authority chain:** Matt and CGPT, then the Orchestrator (Rogue), then a PL per WO, then the Engineer, Auditor, Tester and DevSecOps.
- **Approval:** each WO needs CGPT's exact-version approval on its own GitHub Issue.
- **Execution identity:** application delivery runs as the reusable multi-project PL identity, `forgev2-pl`. This repository's deploy key gives authentication to this repository only; it is not filesystem isolation (FOUNDRY-ORCH-SETUP-001 §3.7).
- **Stop rule:** no ForgeV2 application WO runs while ForgeV2 sandbox acceptance is BLOCKED.
- **Build, deployment and acceptance are separate:**
  - ForgeV2 builds and reviews; the PL pushes `forge/<WO>`, and Matt opens the PR.
  - An authorised operator deploys the PR's exact commit to the dev environment and demonstrates the functional acceptance criteria with synthetic data.
  - Matt does the walkthrough, accepts and merges.
  - A browser-only ESCALATED result is acceptable as an intermediate review result when every other check passes. It is never final acceptance.
  - Defects found at deployment stay open until corrected and retested (CRM-D013).

## 7. Blockers and unknowns

| # | Item | Status |
|---|---|---|
| B1 | ForgeV2 sandbox acceptance | BLOCKED (forgev2#5) |
| B2 | ForgeV2 specialists cannot run Docker or reach a running web app on the host, and there is no browser | Verified; see `docs/BUILD.md` §5 |
| B4 | Push rights for the bootstrap commit | The deploy key authenticates; write permission is unverified |
| U1 | Legal-entity versus office model for firms (PoC D4) | Business question |
| U2 | Where enquiries live, CRM or Case Manager (PoC D3) | Deferred to CRM-004 |

## 8. Evidence

These are held outside this repository and are restricted, because they contain staff names, firm names and Salesforce identifiers:
- Salesforce usage assessment and selection, 2026-11-03;
- the PoC design, with gates G1 to G7 and decisions D1 to D9;
- the management summary;
- the infrastructure discovery report of 2026-11-03.

Sanitised extracts may be added to `docs/` under an approved WO.
