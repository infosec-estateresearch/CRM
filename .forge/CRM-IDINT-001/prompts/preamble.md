## GOVERNING RULINGS (binding; these govern the Work Order text below wherever it differs)

- **Approved artifact:** PR #93, commit `1717537ec7e1ad716273f6d5ca60f86c62000469`, `work-orders/CRM-IDINT-001.md`, SHA-256 `a7899d276c781736eb53d482731320a272262836470dd305d2421df0d0680f93`.
- **Base and known commit:** `5c56fcd8c1fe7b6257e11aae2276ce0878f9be20`.
- **Rulings:**
  1. Dispatch of this exact version: yes, once E0 to E6 pass.
  2. At most **three** executions per role for this ledger.
  3. One corrective successor within a cumulative maximum of four executions per role: yes in principle. **Its exact artifact needs separate approval.** The correction comment on Issue #92 governs the contradictory wording in section 7: there is **no standing authority**. You do not write, start or dispatch a successor.
  4. Operator runtime and browser proof: yes. A browser-only ESCALATED close is intermediate, never acceptance.
  5. The superseded expectations of section 4: accepted.
  6. Section 3.5: **option (a)**. Roles with permission to edit the record may retire or supersede it through the controlled and audited workflow.
- The draft labels in the Work Order file ("DRAFT", "Not approved. No dispatch", "No ruling has decided it", and the approval choices it leaves open) predate this approval and are superseded by this section. They are not a contradiction in acceptance criteria.

### PASS rule and what closes the Work Order (verbatim)
- Criterion A13 needs, on the same unchanged candidate: Auditor **PASS**, DevSecOps **PASS**, and Tester **PASS**, or **INCONCLUSIVE solely for browser and live-runtime behaviour** with every sandbox-executable criterion passing.
- A reviewer verdict `FINDINGS` is not a PASS. Do not record the findings of a FINDINGS verdict as advisory or rejected to reach DELIVER, unless you disprove one with evidence, which you record. Observations stated under a PASS may be advisory.
- Browser gate (WO section 6): when everything else passes and the Tester is inconclusive solely for browser and live-runtime behaviour, close **ESCALATED** with that reason **without a further Tester execution to retry it**. That is the expected successful result on this host.
- A Tester that is inconclusive for any other reason, or any other inconclusive reviewer, is handled by the engine rules inside the budget of section 2.

### Test environment and binding reminders (verbatim)
- Unit suite: `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests/unit`, from the worktree. Baseline at the base: 624, OK. The Work Order records 11 PHP skips where PHP is absent.
- The specialists have no network, Docker, browser or EspoCRM runtime. Do not install anything. State plainly what was not executed. The Orchestrator performs the runtime and browser proof of WO section 8; do not claim it.
- Leave no bytecode, cache or scratch file in the worktree or the repository.
- Boundary: WO section 4. A needed change outside it is a stop condition: report BLOCKED, never work around it. WIP is on hold: the "Open WIP / Revenue" item and its handler stay unchanged; the only related change is the scope-guard repair of WO section 3.9.
- **The repository is public.** Anything you commit or push (including `.forge/` records) carries no credential, host address, personal, customer or firm data. In published records name findings by safe identifiers and keep exploit detail of anything still present on a running system in your private records. A genuine finding that cannot be reported safely is BLOCKED, never PASS.
- Pre-existing root-owned entries in the repository's Git directory, and a root-owned bytecode directory under `load/`, are preserved state. Do not repair, re-own, reset or clean them. If a Git operation fails for an ownership reason, report BLOCKED with the exact error.

Execution budget: at most 3 executions per role for this ledger. A missing standing successor authority or the three-execution limit is NOT a finding.
