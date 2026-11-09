# Product Vision — Estate Research CRM

- **Status:** DRAFT. This needs Matt's explicit approval of this exact version (FOUNDRY Stage 1).
- **Prepared by:** Rogue, 2026-11-06, from the read-only Salesforce usage assessment of 2026-11-03.

## Purpose

Estate Research uses Salesforce as three things:
- an address book of law firms and their people;
- an enquiry log;
- an email filing cabinet.

We will replace it with a self-hosted CRM that we own, with no licence fees, shaped around how we actually work. It must be in place before Salesforce retires the login method ERic depends on (summer 2027).

## Who it serves

- **Business development:** looks up firms, records meetings and presentations, sets follow-ups, pulls regional lists.
- **Enquiry and ancillary services:** logs requests from firms, files the related emails, quotes fees, records instructions.
- **Administration:** imports data and produces lists.

About 21 staff use it daily. Everyone gets a named login; there will be no shared accounts.

## What matters most (measured daily use in Salesforce)

| Use | Per day |
|---|---|
| Open a firm record | ~430 |
| Search for a firm, person or enquiry | ~110 |
| Log an enquiry | ~75 |
| File a chosen Outlook email to an enquiry | ~28 |
| Add a contact | ~25 |
| Set a follow-up | ~23 |
| Record a meeting | ~4 |

## Product Goal for the first releases

**Staff can find any firm, see its head office and branches, and find and maintain the people at those firms at least as fast as in Salesforce, on a CRM Estate Research runs itself.**

## Outcomes

1. Firms and contacts are managed in the new CRM, including head office and branch structure. 42% of firms are branches.
2. Activities (calls, meetings, follow-ups) and enquiries follow in later increments.
3. Selective Outlook email filing works with any CRM, through an ER-owned service.
4. ERic reads the CRM through a read-only API, never through SQL.
5. Salesforce data is migrated with record-by-record reconciliation, and Salesforce is switched off.

## Out of scope

Dashboards, forecasting, quotes, products, marketing campaigns (these stay in the existing email platform), an internal social feed, and recreating Salesforce in general.

## Constraints

- Open source and free. Estate Research keeps its own version.
- Core changes are kept separate (ER extension plus numbered patches), so upstream security fixes still apply.
- Salesforce stays **read-only** throughout.
- No real personal data until the security gates are met.
- Marketing, Email Builder, EmailEngine, ERic, WIP and Case Manager are not affected by CRM work.
