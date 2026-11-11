# CRM-006R - ESCALATED (continued in CRM-006S)
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-006R   Candidate: 375e1ca890161b0a9d569432e28f1e21905bbd6a   Base: 188af96db1f032a993448accb7ed6657f2ed2f6d (CRM-005 delivery record)   WO: work-orders/CRM-006R.md v1.0 (continues CRM-006 v1.0)
Change: crm-load, the idempotent Salesforce-snapshot to EspoCRM importer (standard library, injected transport, loopback HTTP only), plus scripts/load.sh (root, dev synthetic-only, beta extract-only) and docs/IMPORT.md.
- Input gate: the manifest verifies and contract v4 is required; RECONCILED, or drift with an Issue #9 acceptance URL; a reconciliation run bound by t_start, status and contract sha and version.
- Synthetic means a sealed selftest run, and beta refuses the synthetic marker.
- Mapping per MIGRATION-DECISIONS.
- Owners are never guessed.
- Upsert by sfId: link-multiples are merged, and nothing is ever deleted.
- Reports and exceptions contain counts and ids only.
- Config: Contact.opportunityRole options = the Salesforce OpportunityContactRole picklist (L1); the ER Import role has the Import scope (needed by core CheckFromAddress).
Tests: python3 -I -B -m unittest discover -s tests/load -t . -> Ran 112, OK; python3 -m unittest discover -s tests/unit -> Ran 311, OK; mutation evidence for every fix.
Reviews:
- Round 1 BLOCKING: selftest snapshots classed as real, a manufactured call direction, second-run phone writes, and scope. All were fixed in engineer round 4 and verified by the reviewers. Scope was closed by a PL decision: the mechanically required test-fixture changes.
- Round 2 BLOCKING (Auditor): server defaults. When a source value is blank, EspoCRM's entityDefs default is stored, for example learningPlatformAccess "No", and the next run PUTs null.
- The engineer execution limit was reached, so the work continues as CRM-006S.
Advisories carried to CRM-006S:
- phoneNumberInternational is not enforced;
- one refused phone drops its sibling phones;
- synthetic users are never exported, so the dev owner path is untested;
- varchar values are trimmed by the server.
History: CRM-006 BLOCKED by tooling (a planned partial round reported as failed); continued here.
