# Migration data handling and retention controls

- **Status:** v1.0, 2026-11-10; sections 2, 3 and 6 amended 2026-11-26. These controls must be in force before any identifiable Salesforce record is processed (PO override, Issue #9).
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
| Off-host copies of the beta backups | Operator backup storage | Encrypted before leaving the host. The decryption key is in restricted operator custody, apart from the copies and the application. |
| Reconciliation published to GitHub | Issue #9 or the PR | **Counts, rates and statuses only.** No names, addresses, emails, ids or record text. |

- ForgeV2 specialists, developer agents, CI and prompts **never** receive record contents, credentials or snapshot paths with data in them. They work on synthetic fixtures only.
- The synthetic `crm-dev` environment never receives customer data.

## 3. Copies and backups
- Other host backup jobs do **not** include the CRM runtime (checked on 2026-11-10 and 2026-11-26).
- Raw snapshots are **not** replicated further, including by the ERm backup below. If one is lost, it has to be extracted again from Salesforce, which is still the system of record, once live retrieval is authorised again (section 6). This keeps the number of copies to a minimum.
- **Schedule.** No backup schedule was installed before 2026-11-26. On that day one nightly operator timer was installed (02:30 plus up to 15 minutes). Its first run, started by hand through the same service on 2026-11-26, succeeded. The first timer-started run is due on 2026-11-27 and is not covered by this statement.
- **Content.** Each run keeps a root-only local copy (the newest seven scheduled copies) and an encrypted off-host copy: database dump, application data and customisation directories, runtime configuration and the release bundle. Manual recovery copies made on 2026-11-26 are pinned.
- **Checks.** The job verifies the dump and reads the encrypted copy back to compare checksums; it cannot decrypt. A failure shows in the service state and in a host login notice. There is no remote alert yet.
- **Restore.** On 2026-11-26 the application was started in an isolated environment from the decrypted off-host copy of that first run, without the job daemon. Identity digests for firms, contacts, contact-firm links, enquiries, users and role links equalled the live ones, the application became healthy and an administrator signed in. File attachments are not proven (none exist). This is one proof; no periodic restore test is scheduled.
- **Off-host retention** (seven daily, four weekly, three monthly) is **report-only** until removal has been verified and enabled. It applies only to ERm-owned copies and never to pinned ones.

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
- **Salesforce access is read-only.** Nothing is created, updated, deleted or changed in Salesforce.
- **The write-capable identity waiver has expired.** The existing credential can write to Salesforce. The time-limited waiver that allowed its use for extraction expired on 2026-11-24; it is not renewed or reused, and the extractor refuses an expired waiver. **Live retrieval is disabled pending authorised authentication.** Development continues on synthetic data. The existing credential is to be retired when a dedicated read-only identity exists, or before Summer '27 at the latest.
