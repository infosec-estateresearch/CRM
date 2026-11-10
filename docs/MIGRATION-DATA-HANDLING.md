# Migration data handling and retention controls

- **Status:** v1.0, 2026-11-10. These controls must be in force before any identifiable Salesforce record is processed (PO override, Issue #9).
- **Owner:** Rogue, as the trusted operator on DOCKER1.
- **Authority:** Matt, Product Owner.

## 1. Purpose and scope
- **Purpose:** used **only** for Estate Research's replacement CRM and for migration reconciliation.
- **Data:** the fields in `migrate/contract/salesforce-fields.json` and nothing else. Excluded:
  - attachments, `HtmlBody` and Bcc;
  - fields outside the contract.
- **History:** the full available business history (no date window), as the PO directed.
- Salesforce remains the live system of record until cutover is separately authorised.

## 2. Who can access what

| Data | Location | Access |
|---|---|---|
| Legacy credential | The existing ELT env file, read in place | Root operator only. Read at run time and piped on stdin. Never copied. |
| Raw snapshots | `/srv/CRM/runtime/migrate/snapshots/<id>/` | Root only. Directories `0700`, files `0400` once sealed. Integrity is checked by sha256 manifest. |
| Beta database and backups | `/srv/CRM/runtime/beta/…` | Root only. Application access is through named EspoCRM logins with roles. |
| Reconciliation published to GitHub | Issue #9 or the PR | **Counts, rates and statuses only.** No names, addresses, emails, ids or record text. |

- ForgeV2 specialists, developer agents, CI and prompts **never** receive record contents, credentials or snapshot paths with data in them. They work on synthetic fixtures only.
- The synthetic `crm-dev` environment never receives customer data.

## 3. Copies and backups
- Host backup jobs do **not** include `/srv/CRM` (checked on 2026-11-10), so no uncontrolled copies of the snapshots are made.
- Raw snapshots are **not** replicated further. If one is lost, it is re-extracted from Salesforce, which is still the system of record. This keeps the number of copies to a minimum.
- The beta database is backed up daily to `/srv/CRM/runtime/beta/backups` (root `0700`). Restore is tested (PBI-011).

## 4. Retention and disposal
- **Superseded snapshots:** keep at most the **two** most recent `RECONCILED` snapshots. Older ones are deleted once a newer one has been loaded and reconciled.
- **All snapshots:** delete them **30 days after cutover acceptance**, or **6 months after extraction** if cutover hasn't happened by then, unless the PO extends this in writing on #9.
- **Beta data:** kept while the beta is active. Disposal at the end of the beta is decided by the PO.
- **Disposal method:**
  - the operator deletes the sealed directory, plus any matching beta backups when their retention ends;
  - each disposal is recorded on #9 with the snapshot id and counts only;
  - **limitation:** on SSD or copy-on-write storage, deletion isn't cryptographic erasure. The volume's own encryption status is the PO's infrastructure decision.

## 5. Logs and evidence
- Extractor logs and reports are counts only. Tests enforce this with a sentinel.
- Error output reduces Salesforce faults to their codes.
- The completeness status (`RECONCILED`, `RECONCILED_WITH_DRIFT` or `INCOMPLETE`) is stated with every published reconciliation.

## 6. Known risks, accepted or escalated
- **Write-capable identity (accepted by the PO, temporary).** The existing credential can write to Salesforce. It is constrained by the independently tested allowlist, an operator-only procedure and a time-limited waiver. Retire it when a dedicated read-only identity exists, or before Summer '27 at the latest.
- **Exposure of that credential outside the CRM (escalated, not remediated here).** On 2026-11-10, a nightly host backup held a copy of the ELT env file that any local user can read. It was reported to the PO for remediation by the owner of that host job.
