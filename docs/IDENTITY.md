# ERm identity contract

**Status:** direction accepted (Architect ruling C-1, relayed 2026-11-26, [Issue #91](https://github.com/infosec-estateresearch/CRM/issues/91)). Delivered only by approved Work Orders; nothing here is evidence of implementation. Product: ERm, Estate Research's relationship management product built on EspoCRM. ERm is the only master of the identities below.

## Identifiers

| Name | Record | Notes |
|---|---|---|
| FirmID | `Account.id` | one per firm record, including each branch |
| GroupID | `FirmGroup.id` | independent group of firms |
| ContactID | `Contact.id` | one per person record |
| Legacy key | `sfId` | Salesforce cross-reference only; never the canonical key |

Identifiers are opaque ASCII strings. Consumers allow up to 36 characters, compare case-sensitively and never parse them.

## Invariants

1. An identifier is issued once, by ERm. It is never changed and never reassigned.
2. Identity records are retired, not deleted. Automatic removal of deleted records is disabled.
3. Every identifier ever issued resolves to `active`, `retired`, or `superseded` with a successor.
4. Record merge is not used for firms, contacts or groups.
5. A contact's primary firm is one of its linked firms. Other firm links are preserved. No primary firm is invented: a contact without a valid one is listed and reconciled explicitly.
6. A firm belongs to at most one group, which may be set when the firm is created. Membership is not inherited from a parent firm. Parent and branch are a separate relationship.
7. A contact's GroupID is derived from its primary firm. It is never stored separately.
8. Every change of an identity relationship is authorised on the server and audited with actor, time, previous and new identifiers, for all users, whatever route is used. The change does not succeed unless its audit record is durably stored. A route that cannot do so is disabled.
9. These rules apply to administrators as to other users.
10. Backup, restore, upgrade and migration preserve identifiers and relationships, verified by comparison.
11. Keeping identity and audit history does not require keeping all personal information indefinitely; personal data retention is decided separately.

## Lifecycle

| Event | Rule |
|---|---|
| Rename | identifier unchanged; audited |
| Duplicate record | one survivor; the other is retired and superseded by it |
| Business merger | the absorbed firm is retired with a successor and effective date; its history stays |
| Demerger | new identifiers for new entities, each recording its predecessor |
| Group merger | the surviving group keeps its identifier; the other is retired with a successor |
| Closure or departure | retired or marked inactive; kept |
| Restore to an earlier point | identifiers issued after that point are reconciled against an independent identity register; none disappears unnoticed |

## Identity register

An independent identity register is built and tested: restore to an earlier database state, successor resolution, cycle prevention, and reconciliation of identifiers issued after the restored backup.

## Migration

Production data descends from one database lineage. Later source loads update by `sfId`, compare against the previous accepted source, never overwrite accepted changes made in ERm, and never delete. A recorded date (identity genesis) marks when identifiers become permanent and may be stored by other systems; before it is declared, any consumer already holding beta identifiers is confirmed. The preferred production route is a verified beta-derived database in a separately prepared production runtime (design approval only, not cutover authority). Consumer access may be prepared before genesis; use waits for it.

## Integration

Consuming systems have read-only access with their own revocable identity. They pull changes and reconcile the full set of identifiers periodically. They follow successor pointers and never delete or repoint a stored reference on their own. No second customer identity master is created. ERm does not depend on any consuming system. Access to other systems' databases is outside this contract.

| Resource | Fields |
|---|---|
| Firm | firmId, name, type, town, postcode, groupId, parentFirmId, state, successor, modifiedAt |
| Group | groupId, name, state, successor, modifiedAt |
| Contact | contactId, name, e-mail addresses, primaryFirmId, firm links, state, successor, modifiedAt |
