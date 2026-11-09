# Product Backlog — Estate Research CRM

- **Status:** DRAFT. This needs Matt's explicit approval. Backlog items are not Work Orders and grant no authority (FND-009, FND-012).
- **Ordering:** smallest useful increment first. Each later item depends on the ones above it unless it says otherwise.

| ID | State | Item | Value / acceptance outline | Depends on |
|---|---|---|---|---|
| CRM-PBI-001 | DEFINED | **Firms, branches and contacts baseline** on a pinned EspoCRM. Synthetic data only. | Firms with a head office and branches; same-name branches kept distinct; contacts linked to firms; search by name, postcode, phone and email; CSV export; backup and restore. WO draft: `work-orders/CRM-001.md`. | ForgeV2 sandbox acceptance on the development host |
| CRM-PBI-002 | DEFINED | **Users, roles and audit** | Named users; everyone reads all records; edit rules per team; protected deletion; field history on key fields | 001 |
| CRM-PBI-003 | DEFINED | **Activities:** calls, meetings, tasks, follow-ups, calendar | The 6 timed staff scenarios that touch activities | 001 |
| CRM-PBI-004 | PROVISIONAL | **Enquiries:** stages Enquiry → Quoted → Instructed / Lost (with a loss reason), a service-type reference list (60+ values), quoted fee | The PoC G2 tests. The CRM-versus-Case-Manager decision is needed first. | 001, 002 |
| CRM-PBI-005 | PROVISIONAL | **Pseudonymised sample import** from Salesforce (read-only), with reconciliation | Counts match per object and per parent firm; no live personal data | 001, 004; Matt's approval of the sample and pseudonymisation |
| CRM-PBI-006 | PROVISIONAL | **Email filing spike:** an ER filing service and an Outlook task pane | The PoC G3 tests | 004; test mailbox and app registration |
| CRM-PBI-007 | PROVISIONAL | **ERic read-only API adapter** | ERic reads firms and contacts through a read-only token; write attempts fail | 001, 002 |
| CRM-PBI-008 | PROVISIONAL | **TLS, LAN exposure and staff pilot** | Staff reach the CRM over TLS with a named login; timed scenarios are at least as fast as Salesforce | 002, 003; security readiness for real personal data, assessed under that item |
| CRM-PBI-009 | PLACEHOLDER | **Full migration and Salesforce switch-off** | Record-by-record reconciliation; a parallel run; switch-off before summer 2027 | All of the above |
