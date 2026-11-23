# Engineer brief: CRM-WIP-LINK-001R3

Worktree (the ONLY path you may change; never touch any other path): /srv/CRM/worktrees/CRM-WIP-LINK-001R3
Expected HEAD: cbfeca7668374a8c02945b21930845394501fad6 (branch forge/CRM-WIP-LINK-001R3). Do not commit; the PL commits.
Scratch dir (read-only for you unless told otherwise): /srv/CRM/worktrees/.forge-scratch/CRM-WIP-LINK-001R3

This is your ONLY execution for this Work Order. There is no correction round: get it right in one pass.

Run tests from the worktree: `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests/unit` (baseline 619 tests, OK). No network, Docker, Node, browser; PHP not assumed. Install nothing. Leave no bytecode, cache or scratch file in the worktree.

The Work Order text (verbatim) is at /srv/CRM/wo/CRM-WIP-LINK-001R3/work-orders/CRM-WIP-LINK-001R3.md. Read it completely; sections 1, 3, 4, 5, 6 and 9 are binding. Summary of the allowlist (exhaustive): 
- scripts/deploy_custom.sh: two places only (read_app_timestamp also reads data/state.php merged after the two config files; RECOVERY FAILED message when compose up had succeeded).
- tests/unit/test_scripts.py: narrow edit (layout-faithful fake docker, READ_TS constant, scenarios (i)-(v), positive controls (i),(ii)).
- docs/WIP-LINK.md: one sentence.
Everything else byte-identical to the base. Any need to change anything else: stop and report blocked.

Deliverables in your final message: suite counts before/after (no new skip, nothing removed/weakened); revert-and-rerun proof for N01 (state file not read), N02 (state file name wrong, state-internal.php), N03 (message restored to old wording after successful compose up), each naming the catching test (restore the script after each proof); proof that the new scenarios fail on the unmodified base script; list of every changed existing test line with the reason; `git diff --stat`. Final message must report `completed`, `blocked` or `failed` explicitly.
