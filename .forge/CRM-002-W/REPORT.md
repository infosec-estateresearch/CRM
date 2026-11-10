# CRM-002-W - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-002-W   Candidate: 47a8b12e01cb5f04a5f2b1118053dd588363016d   Base: 8389cab297fc1f1efc72bcd082f26a330c293c60 (CRM-002-V DELIVERED)   WO: work-orders/CRM-002-W.md v1.0
Change: a migrate.sh snapshot_root helper recognises exactly the client-credentials layout (<id>/manifest.json) or the legacy layout (<id>/run/manifest.json, with only input/ and run/), refusing symlinks or non-regular entries. cmd_reconcile verifies that root and copies only it into the container input; the waiver is never copied. The whole <id> must be sealed.
Tests: bash -n OK; python3 -I -B -m unittest discover -s tests/migrate -t . -v -> Ran 323, OK (skipped=1).
Reviews: round 1 Auditor, Tester and DevSecOps PASS.
Advisories: the new docs heading splits an existing bullet list; one generic refusal message covers several layout errors.
Operator stage: reconcile the second L3, then SOURCE_EXTRACTED.
