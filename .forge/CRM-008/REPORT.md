# CRM-008 - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-008   Candidate: f86cc0b028a3ac673e72605fd34ce89ea8d6146a   Base: dfe1d55f658b40082403f716c56b2b378fcf4163 (CRM-003-F delivery record)   WO: work-orders/CRM-008.md v1.0
Change: fixes from the first crm-dev operator load.
1. **ServiceType controller.**
2. **Settings:** `config/settings.json` (currency GBP, `phoneNumberInternational` false) is applied idempotently by `provision_access.py`.
3. **Required owners:** Task, Call and Meeting with an unresolved owner are refused (`owner_required_unresolved`); no placeholder owner is used.
4. **Task-Emails with no EmailMessage** become Tasks (`task_email_imported_as_task`).
5. **maxLength:**
   - a value over the limit is sent as null with `value_too_long` (qualified attribute names), on create and update;
   - an over-length required attribute refuses the record;
   - a refused record gets no write in any later pass;
   - `service_type_refused` goes on each Opportunity whose ServiceType was refused;
   - Contact `title` is raised to 255.
6. **Email validation:** stricter than PHP by design. An invalid To/Cc is dropped (`email_address_invalid`); an invalid or blank from refuses the record.
7. **syntheticEnumMap** gains Event `Type`.
8. **Role `info`** is never sent, so a provisioning re-run makes no changes.
9. **Executable modes** for the 6 scripts.
PL facts:
- Rejection reasons were read live on crm-dev with synthetic data.
- Real-extract impact (counts only):
  - 37,295 Opportunities with an amount (currency);
  - 455 Task-Emails with no EmailMessage;
  - over-length values: 1 Contact title and 4 Contact phones;
  - the email rule would drop 3 addresses (2 To, 1 Cc) and refuse 0 From addresses;
  - 0 unresolvable Task/Event owners.
Tests: unit ran 333, OK; load ran 158, OK. There is mutation evidence for every item.
- The fake is now faithful: it refuses a missing owner, over-length values, an invalid currency, invalid emails and a missing required name.
- Full selftest end-to-end: run 1 had 0 `write_rejected`, and run 2 made 0 writes.
Reviews:
- Round 1: Auditor blocking (IMPORT.md settings), fixed. Advisories fixed: required over-length, owner tests, qualified names, notes.
- Round 2: Auditor blocking (a refused Account was written by the second pass), fixed in engineer round 4. Advisories fixed: per-Opportunity service-type code, IMPORT.md table.
- Round 3: Auditor and DevSecOps PASS; the Tester reported advisory findings only.
Advisory carried: an existing Opportunity skipped as `value_shape` can still get a contact-role write in the same run. This predates CRM-008, and the reviewer found no blocking impact.
