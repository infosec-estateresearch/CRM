WO: CRM-WIP-002
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: main — CONDITIONAL: the commit that delivers an accepted CRM-WIP-001 (does not exist yet; no SHA is asserted)

# CRM-WIP-002: Account WIP/Revenue tab, the first usable WIP interface

- **Version:** v0.1 **CONDITIONAL DRAFT**, 2026-11-16. **Not approval-ready** (gate U0).
- **Issue:** https://github.com/infosec-estateresearch/CRM/issues/64
- **Prepared by:** Rogue (Orchestrator), under the CGPT *CRM/WIP Delivery Mission*, Phase 4. **No implementation, no dispatch.**
- **Header note.** There is no `BROWSER:` line, because this WO is user-visible. Real-browser assurance follows the accepted **CL-D7** pattern: operator-run journeys with the CRM-CLIENT-001 runner, then a companion `CRM-WIP-002-BA` WO whose Tester and DevSecOps assess the raw evidence, with only public-safe summaries in Git.
- **Requirements:** WIP-04, 05, 06, 07, 08, 10, 13, 15, 17, 18; the wip-field-contract *Form/API contract*.

## 1. Dependencies

- **CRM-CLIENT-001** (delivered by its recovery WO **CRM-CLIENT-001R**, #65 / PR #66): client delivery, AMD modules, cache-bust, browser runner and evidence route.
- **CRM-FG-001:** the Account page Group Members tab coexists with this tab.
- **CRM-WIP-001:** entities, validation, guards and denial.
- **PO-W1** stays open. Until it is decided, the only user who sees the tab in synthetic UAT is **Admin**, with deny-by-default for every staff role. Staff use needs PO-W1, which goes into the consolidated business-decision set before final acceptance.

## 2. Intended outcome

On `#Account/view/<id>`, a native **WIP/Revenue** tab (an AMD view from `client/custom/src/wip/`) sits beside Stream, Group Members, Enquiries and Activities.

1. **List.** The tab lists this Account's cases only: reference, status, instruction date, and latest observation date and values. It paginates and has a sortable reference column.
   - **Empty state:** *No WIP cases for this firm*.
   - **No access:** the tab is absent. This is never a broken panel.
2. **Open a case** from the list. The detail shows the case fields, the derived current group (read-only label "Current group"), and its observations ordered by `observedAt` descending. **Back to firm** returns to the Account tab.
3. **Create a case** through a guided form.
   - The firm is **prefilled and read-only** from the route.
   - It covers the case fields and an optional first observation.
   - The request goes through one custom action, `POST /WipCase/action/createForAccount`, which saves the case and the first observation **atomically** in one transaction.
   - The server derives `accountId` from the action's `accountId` and checks it again: the Account exists, the actor can read it, and the actor has WipCase create.
4. **Add or edit an observation** through a separate action carrying a `requestId`, so a retry doesn't create a duplicate. Edits are audited (WIP-001).
5. **Labels and display (WIP-17).**
   - Labels: "WIP value", "Fees invoiced", "Revised or actual yield (source value)", "Estimated yield".
   - Values render as GBP from the exact decimal string, with no float arithmetic in the client.
   - Blank shows as "—", never "£0.00".
6. **Validation (WIP-06, 07, 18).**
   - The browser gives hints and the server enforces.
   - Field-level messages: required reference, unknown status, impossible or out-of-range date, negative amount, more than 2 decimals, overflow, exponent or separator junk, duplicate reference.
   - No SQL, path, stack or other-record data appears in an error.
7. **Tamper resistance (WIP-10).**
   - The UI never sends `firmGroupId`, `sourceKind`, `origin` or `source*`, and the server refuses them anyway.
   - A crafted request cannot create a case for an Account other than the action's verified target, change a case's Account, or attach an observation to a case on another Account. The WIP-001 immutability and relation guards apply.
8. **Containment (WIP-13, WIP-15).** If the WIP view throws or its API errors, the tab shows a bounded error, and Stream, Account details, Group Members, Enquiries, Contacts and Activities still render and work.

## 3. In scope (draft allowlist; finalised at U0)

- `client/custom/src/wip/**`: AMD views, templates and CSS, with no third-party JS and no `innerHTML` with record data (CL-D1, CLIENT-001 AC1 rules)
- `custom/Espo/Custom/Resources/metadata/clientDefs/Account.json`: the tab or bottom-panel definition only
- `custom/Espo/Custom/Resources/layouts/Account/*`: the tab placement only
- `custom/Espo/Custom/Resources/metadata/clientDefs/Wip*.json`, `layouts/Wip*/**` and `i18n/en_US/Wip*.json`
- `custom/Espo/Custom/Resources/routes.json`: the two WIP actions only
- `custom/Espo/Custom/Tools/Wip/**`: the action services
- `tests/unit/test_wip_ui_static.py`, `tests/acceptance/test_wip_actions.py` and `tests/browser/wip/**`: journeys run by the CLIENT-001 runner
- documentation

## 4. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| U-AC1 | **Real-browser journeys** run on synthetic crm-dev as Admin. Each one checks **visible, working behaviour**: clicks, typed input, submission, rendered text and a navigation result. DOM existence alone does not count.<br>**J1** Open the Account, open the WIP/Revenue tab, see the case list or the empty state.<br>**J2** Create a case with a first observation, see it listed after save and after a refresh.<br>**J3** Open the case, add an observation, edit it, and see the ordering and the audit entry; go *Back to firm*.<br>**J4** Each validation error in §2.6 is shown in the field-level message and nothing is saved.<br>**J5** Paginate across more than one page.<br>**J6** The Group Members tab, Stream, Enquiries, Contacts and Activities still work.<br>**J7** Fault-injected WIP view: bounded error, the rest of the page works.<br>**J8** As ER Staff (WIP denied): no tab, and direct URLs to WIP records are denied | BA evidence (CL-D7); Tester verdict per journey |
| U-AC2 | **API tamper set:** create for a foreign Account through the action body or path mismatch; observation for a case on another Account; `accountId` or `wipCaseId` change; `firmGroupId` injection; a replayed `requestId`. Each is refused or idempotent, with fingerprints unchanged | `test_wip_actions.py` |
| U-AC3 | **Atomicity:** a failure in the first observation leaves no case row; a failure in the case leaves no observation | API fault injection |
| U-AC4 | **Static client rules:** AMD only; no `innerHTML` with data; no float parsing of amounts; labels per WIP-17 | unit |
| U-AC5 | **Regression:** the WIP-001, FG-001 and CLIENT-001 suites; the unit suite; load; bundle verify | host procedure |

## 5. Gates

| Gate | Requirement | State |
|---|---|---|
| **U0** | CRM-WIP-001 accepted and merged; base pinned per CL-D8; allowlist final | **open, blocks approval** |
| U1 | CGPT exact-version approval on #64 | open |
| U2 | `CRM-WIP-002-BA` final version, approved after the operator run | open |
| UT | **Technical gates:**<br>• UT-1: the Account detail tab mechanism in 10.0.12 (`clientDefs` bottom panels or tabs) coexisting with the FG tab;<br>• UT-2: client currency formatting from decimal strings without float | open |

**Stop:** a staff role grant before PO-W1; any revenue figure or aggregation; any real data.
