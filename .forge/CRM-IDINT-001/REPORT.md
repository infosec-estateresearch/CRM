# CRM-IDINT-001 - ESCALATED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-IDINT-001   Candidate: 65eab11d68583555b378dd2bff36a1d237db3d1a   Base: 5c56fcd8c1fe7b6257e11aae2276ce0878f9be20
Change: Identity integrity (CRM-PBI-035): server hooks and controllers refusing delete, merge, import, supplied identifiers and unaudited identity-relationship changes for every account; an append-only IdentityAudit scope with audit-or-fail and read-back; primary-firm rule and read-only exceptions report; retire/supersede with successor chain (option (a)); release settings applied and read back at deploy; over-length refusal; scope-guard repair (3.9); route-matrix acceptance suite; docs updated.
Tests: PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests/unit (non-root, PHP 8.4 present) -> 683 tests, OK, 0 skipped (base 624). Acceptance suites A1-A11 not executed (no EspoCRM in sandbox).
Reviews (final candidate): Auditor PASS, Tester INCONCLUSIVE (solely browser and live-runtime; every sandbox-executable criterion passed; 16 control mutations detected), DevSecOps PASS
Rounds: 2; executions engineer/auditor/tester/devsecops = 2/2/2/2 (budget 3 each, not exceeded)
Findings:
- new-contact-link-audit-unproven - blocking (round 1, DevSecOps) - fixed in round 2: new-contact firm links audited in afterSave, de-duplicated, undone together with an audit failure
- audit-before-save-orphan - advisory - documented as residual risk
- create-undo-leaves-link-rows - advisory - link rows removed on undo; residual documented
- Round 2 advisory observations (no action): audit-before-change-orphan, option-read-fail-open, admin-metadata-residual, readback-recordid-mutation-survives
Open items / reason: Closed ESCALATED by the browser gate (Tester inconclusive twice, solely for browser and live runtime). This is not final acceptance: A11, A14 and the WO section 8 operator runtime and browser proof remain. The operator must confirm EspoCRM assumptions the sandbox could not check: relate/unrelate/mass-relate hook names and firing, the `import` save option, the merge controller override, the junction name `AccountContact`, the four 3.6 setting names (cleanupAuditLog least certain), and that a new contact's link rows are audited exactly once. No successor was written or dispatched (no standing authority).
Pushed: see final message
