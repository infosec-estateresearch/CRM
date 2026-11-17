# CRM–WIP integration amendment (2026-11-17)

> **Status: PROPOSED. Documentation only; no code authority.** It needs a CGPT exact-version approval, relayed through Matt and recorded on [Issue #71](https://github.com/infosec-estateresearch/CRM/issues/71). It supersedes the CRM-owned WIP design **in part**. No earlier text is edited or deleted. Where earlier text conflicts with this amendment, this amendment prevails once approved.

**Sources:** the Product Owner's course correction and CGPT's architectural correction (2026-11-17); CGPT's scope approval ("approved to prepare", 2026-11-17); Rogue's read-only technical assessment of the same day. All CRM-WIP decisions in `DECISIONS.md` are `PROPOSED`, not approved. This amendment says so where it matters.

## 1. Why the design changes

The 2026-11-13 package modelled WIP as a new CRM-owned module (`WipCase`, `WipFinancialPeriod`, importer, group logic). That rebuilds an application that already exists and already works. CGPT has accepted responsibility for approving that model.

What the existing WIP application provides (verified read-only on 2026-11-17; repository `infosec-estateresearch/WIP`, `main` at `91b2af19877b498ed307ee9f1218b3243b2b60ba`, 2026-06-08):

- its own MariaDB database, with company mirrors keyed by **Salesforce Account id**, cases, one financial observation per case and period, audit, and a cutover restriction on manual writes;
- an hourly Salesforce sync, which is the **only** creator of WIP company rows, and a Mastercopy import;
- company groups, with a review wizard and audit;
- read-only SQL **contract views** for consumers (`v_eric_wip_company_summary`, `v_eric_wip_current_cases`) and a documented SELECT-only database user for them;
- a FastAPI web GUI. Every GET route returns HTML. It has no authentication, it binds all interfaces, and every request uses a full-DML database user. **The service is stopped.** There is no JSON endpoint.

**Objective:** open a firm in EspoCRM and see its WIP information, retrieved from the existing WIP application.

## 2. Architecture

```
EspoCRM Account (sfId)
   │  server-side read of the Account page, user's WIP permission checked
   ▼
CRM read loader  ──authenticated GET, read-only, 2 s connect / 3 s total──►  WIP read-only JSON API
   │                                                                          │  SELECT-only database principal
   │                                                                          ▼
   │                                                                  WIP contract views (WIP database)
   ▼
two read-only, non-persistent Account fields  →  native Account detail panel
```

- The match key is the Salesforce Account id **only**. No company-name matching, no fuzzy matching, no second company master.
- The browser never talks to WIP. The WIP service token stays on the CRM server.
- CRM stores nothing from WIP. WIP stores nothing from CRM.

## 3. Ownership

| WIP owns | CRM owns |
|---|---|
| WIP database, company mirrors, cases, financial observations, imports, audit, lifecycle controls, cutover restrictions on manual writes, WIP groups | Account, Contact, Enquiry and their security; user authorisation; presentation of the WIP panel |

## 4. What is superseded

Nothing below is rewritten in place. This table is the transparent record. "Retained" means the intent stays and the wording is adapted here.

| Item | Disposition | Note |
|---|---|---|
| CRM-D006, as re-read by CRM-D031 | **Superseded in part** | "WIP owns financial WIP" is restored in its plain sense. D031's reading ("the CRM's WIP module owns financial case references and observations") is superseded. D031's other parts stay (D004 stays valid; the Case Manager provenance caution stays) |
| CRM-D020 | Retained, narrowed | CRM owns Account, Contact, Enquiry. The Firm Group part is **held** (D034) |
| CRM-D021, D022 | **Superseded** | WIP is not a CRM module and its code stays in its own repository. Only the thin CRM display code lives here |
| CRM-D023, D024 | **Held** (D034) | FirmGroup is a separate decision; not superseded |
| CRM-D025 | **Superseded in form** | The first capability is a read-only Account panel fed from WIP. "List for that firm only, no importer prerequisite" is retained. CRM add/edit is superseded |
| CRM-D026 | **Superseded** | No WIP navigation workspace is planned. Revisit only on a PO request after the Account display is accepted |
| CRM-D027 | **Superseded** | `WipCase.accountId` and a CRM-derived `firmGroupId` are not built |
| CRM-D028, D029, D030 | Retained | Revenue is undefined (D028). Financial access is deny-by-default (D029), now enforced in the CRM server and by WIP API authentication. The importer stays WIP's (D030) |
| CRM-D032 | Unaffected | |
| CRM-PBI-019, 020, 021, 022, 025 | **Superseded** | CRM-owned WIP model, tab with manual entry, derived group, workspace, history transition |
| CRM-PBI-023 | **Superseded** | A CRM-side importer is not built. WIP's own Mastercopy import stays |
| CRM-PBI-018, 024, 027 | **Held** | FirmGroup entity, population and group reporting (D034) |
| CRM-PBI-026, 028, 029 | Unaffected | Revenue definition stays a PO decision. PBI-029 (documentation reconciliation) is partly delivered by this amendment |
| WIP-01, 02, 03, 05, 06, 07, 08, 09, 10, 12, 14, 16, 18, 19 | **Superseded** | They describe CRM-owned WIP entities, manual entry, validation, audit and migration |
| WIP-04 | Retained, adapted | The Account panel shows this firm's WIP cases only, with a clear no-records state. Read-only |
| WIP-11, 13, 15, 17 | **Retained** | Deny-by-default financial access (WIP-11); a WIP failure never breaks the Account page (WIP-13); existing Account tabs keep working (WIP-15); correct labels and no invented revenue (WIP-17) |
| Work Orders CRM-WIP-001 to 004 | **Superseded** | The drafts are not dispatched and not deleted. PR #62 and Issues #63 and #64 stay open as records |
| CRM-FG-001, FG-01 to FG-11 | **Held** | See D034 |
| CRM-CLIENT-001, 001R, 001R2, PR #69, candidate `07bfaf1c` | **Preserved, unmerged, unchanged** | Not needed by this integration. Relevant again only if custom client JavaScript is later required |

## 5. Interface and presentation contract

**Request** (server to server only): `GET /api/v1/accounts/{sfId}/wip` with `Authorization: Bearer <service token>`. `{sfId}` is exactly 18 letters and digits.

**Response, 200** (all amounts are decimal strings; a missing amount is `null`, never `"0.00"`; no totals; at most 50 cases; `truncated` is true when more exist):

```json
{"salesforceAccountId":"<18 chars>","companyName":"Synthetic Firm LLP","truncated":false,
 "cases":[{"reference":"SYN-001","name":"Matter A","type":"…","status":"Open","openedAt":"2026-01-12",
           "wip":"10250.00","feesInvoiced":"2500.00","estimatedYield":"12000.00",
           "actualYield":null,"asOf":"2026-05-31"}]}
```

**Errors:** 401 bad or missing token; 422 malformed id; 404 the firm is not in WIP; 503 WIP database unavailable. Error bodies carry no detail.

**Data rule:** one row per case, from WIP's own current-cases view: the latest financial observation (by `as_of_date`) of each case that is not closed, rejected or archived. The API computes nothing.

**Panel (Account detail, native fields and layout):** a status line, then one line per case. Labels follow WIP-17: "WIP value", "Fees invoiced", "Revised or actual yield (source value)", "Estimated yield", and "as of <date>". A blank amount shows "—". The status line is one of:

| Status | Meaning |
|---|---|
| WIP data available | cases follow |
| No current WIP cases | the firm is in WIP and has none |
| Firm not found in WIP | WIP returned 404 |
| No Salesforce ID on this Account | nothing is sent to WIP |
| WIP unavailable | any other failure, including a timeout or not configured |

The panel is absent for a user without the WIP permission.

**Not shown:** totals, group totals, "revenue", or any figure WIP's views do not give per case. `v_eric_wip_company_summary.current_wip_value` is **not** used: it sums every period of an open case, so it may overstate. The WIP owner must confirm its meaning before any total is shown.

## 6. Reused components

WIP: the contract views and their documented SELECT-only user pattern; the Salesforce-id firm identity; the existing FastAPI and `pymysql` stack; the existing `TestClient` and fake-database test pattern. CRM: EspoCRM's supported `readLoaderClassNameList`, native fields and layout, role scopes, the `custom/Espo/Custom` delivery by `scripts/deploy_custom.sh`, and the existing access-policy tests. **Not built:** a WIP entity, importer, revision logic, calculation, group store, client JavaScript framework, or any change to the EspoCRM core.

## 7. Security and failure containment

- **Service access.** One bearer token, compared in constant time. The WIP API refuses to start without it. It serves one route only, with no documentation or schema endpoints, no CORS and no write method. It is bound to a non-public address, never `0.0.0.0`, and the existing unauthenticated WIP GUI stays stopped and separate. No firewall rules are used (standing rule).
- **Database.** A SELECT-only principal on the two views. The API never connects as the full-DML WIP user.
- **CRM.** The WIP fields are read-only and not stored. The loader runs only when the user holds the WIP permission, checked on the server, and makes no outbound call otherwise. The permission is explicit `false` for every role in `config/access/roles.json`; this WO grants it to no role (PO-W1 stays open). Admin is the only user who sees the panel until PO-W1 is decided.
- **Secrets.** The URL and token come from the runtime env file, outside Git, never from record data. They never appear in logs, errors, Git or any browser response. The URL is fixed by configuration, redirects are not followed, and the Account's `sfId` is validated before it is placed in the path.
- **Failure.** Timeouts are 2 s to connect and 3 s overall. Every failure becomes the "WIP unavailable" status and the Account page still loads. Residual: when WIP is down, each Account open by an authorised user waits up to 3 s.
- **No new exposure of the existing WIP GUI.** It is outside this scope and is not touched.

## 8. Next bounded step

One Work Order, [`work-orders/CRM-WIP-INT-001.md`](../../work-orders/CRM-WIP-INT-001.md), with a synthetic proof and **no** reuse of the CRM-CLIENT-001R2 D0–D5 browser sequence. The milestone is one synthetic Account in crm-dev displaying cases read from a disposable WIP database that was built from WIP's own migrations. **No implementation is dispatched before this amendment and that Work Order are approved.** The WO needs one delivery decision for the WIP-side code (its gate G4).

## 9. Open items (none blocks approval of this amendment)

1. **PO-W1:** who may see WIP financials. Default: Admin only.
2. **After the Salesforce cutover,** a CRM-native Account has no `sfId`, so it has no WIP match. A PO decision is needed before cutover.
3. **FirmGroup:** WIP already has group tables, review and audit. Confirm that WIP's approved groups meet the required business meaning before any CRM group work. If wanted, they can later come back read-only in the same JSON.
4. **Database principal:** the documented SELECT-only user is unverified (no credentials were read). Creating it on the live WIP database is a WIP-owner change.
5. **Lifecycle:** no permanent WIP API service is started or specified here.
6. **Currency:** the contract views do not expose currency. Amounts are shown as held in WIP, which records GBP by default. The WIP owner confirms before any non-GBP data exists.
7. **Access-policy semantics:** `tests/unit/access_policy.py` says an unset scope is allowed. The 10.0.12 source suggests an unset scope is denied. The WO requires an explicit `false` for every role either way, and a live test of a role that omits it.
