# CRM-TEST-001: ForgeV2 sandbox entry-gate evidence annex

- **Version:** v1.0 DRAFT, 2026-11-13, prepared by Rogue (Orchestrator) for CGPT review.
- **Companion to:** `work-orders/CRM-TEST-001.md`.
- **What this is not:** it is not a sandbox acceptance, not a new sandbox test, and not a claim of general ForgeV2 acceptance.
- **Method:** every value below was read on DOCKER1 on 2026-11-13 with read-only commands. No sandbox test was run, and ForgeV2 and FOUNDRY were not altered.

## 1. Existing acceptance (the only one on record)

- **Record:** `maff0000/forgev2#5`, comment 6746699026 (2026-11-09T17:24:35Z): *"ACCEPTED FOR CRM-001 ONLY … not a general ForgeV2 release certification or approval of ENGINE-SANDBOX-TEST-001 implementation."*
- **What it pinned:**
  - engine `/srv/forgev2` at `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`;
  - test files `sandbox-smoke.sh` (`45e00ca58e68604f88662d2f77f0d93da6f0903cc8899b21ad09807cc96217ee`) and `evaluate.py` (`bb0ca08365be7575dcabaa264a2b718422472591223a90c838541320d18b2cf8`);
  - evidence `/root/forgev2-evidence/SANDBOX-SMOKE/run2-20261109T171810Z/`.
- **Provenance limitation (stated in the acceptance):** CGPT relied on HELM's reported summary and did not open the root-only evidence directory.
- **Status:** ENGINE-SANDBOX-TEST-001 (`maff0000/forgev2#5`) is still **OPEN**. General sandbox acceptance is **unverified**, as recorded in `docs/initiation/2026-11-13-existing-product-reassessment.md` §2 and `docs/delivery/crm-module-sequencing.md`.

## 2. Installed engine identity, now and as tested

| Item | Run 2 (2026-11-09) | Now (2026-11-13) | Same? |
|---|---|---|---|
| `/srv/forgev2` HEAD | `63b6b8ab…` | `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82` (`refs/heads/main` = `origin/HEAD`) | yes |
| Tracked tree (`git status --porcelain`) | clean | clean | yes |
| Ignored files (`--ignored`) | none | `plugin/lib/__pycache__/` (`forgelib.cpython-313.pyc`, root, 2026-11-10T12:59:31Z) | **no** (see note a) |
| `.git` entries (names, owners, sizes) | baseline listing | identical | yes |
| `.git` directory mtime | 2026-11-06T16:49:22Z | 2026-11-13T13:36:12Z | **no** (see note b) |
| Claude Code binary `/usr/local/bin/claude` | 2.1.317, root 0755 | 2.1.317, root 0755, mtime 2026-11-04T14:02:44Z, sha256 `eb224419e344575faa4a1f39b290b649425a10cd5ee2ef1d003480cd9ae57eb0` | yes (version, owner and mode match; the run-2 binary hash was not recorded) |
| bubblewrap `/usr/bin/bwrap` | not setuid | 0.12.0-1~deb13u1, root 0755, not setuid | yes |

- **Note a.** A root-owned bytecode cache appeared in the engine install on 2026-11-10. This is consistent with a root-run engine helper importing `forgelib`. It is ignored by Git, and no tracked content changed. It is **not remediated**: changing ForgeV2 is out of authority. It is reported for CGPT's assessment.
- **Note b.** The 13:36Z mtime was caused by this annex's own read-only `git status` (Git's optional index-lock attempt). No file was added, removed or changed. An earlier 13:07Z change that day was observed but not attributed. It is probably a similar read. Future engine reads should use `GIT_OPTIONAL_LOCKS=0`, so that they do not touch directory metadata.

## 3. Accepted test scripts and results

- **Scripts:** `/root/wo-drafts/sandbox-smoke/sandbox-smoke.sh` and `evaluate.py` currently hash to the accepted values (§1). They are unchanged.
- **Run 2:**
  - `RESULT.txt` sha256 is `d652fbf93adaf523eeb5db91e7eb72d077b0e0f5222ee1681b013b5bfeebae14`, and its summary is `PASS=180 FAIL=0 NOT_RUN=0`.
  - Other hashes: `settings-all-roles.json` `6944f419…f44b`; `probe.sh` `3a0bdc7c…8ed5`.
  - Coverage, for each of Engineer, Auditor, Tester and DevSecOps:
    - canary and credential reads are denied;
    - Git metadata, refs, hooks, the record directory and checkout writes are denied;
    - external HTTPS, loopback, UNIX socket and nested user namespace are denied;
    - reviewers cannot write the worktree; the Engineer can;
    - an Edit outside the permitted paths is denied;
    - the setup fails closed without bubblewrap;
    - the engine is unchanged.
  - Run 1 (`PASS=172 FAIL=4 NOT_RUN=1`) is superseded. Its leftovers were declared not to block CRM-001.
- **Limitations carried forward:**
  1. It is a fixture project (`SMOKE-1` under `/tmp/fv2smoke-*`), not the CRM worktree layout.
  2. The `pl-home:listing-changed` NOTE has to be compared by hand.
  3. It is not independently reviewed by CGPT (§1).
  4. It does not test the visibility of `/srv/CRM/runtime` paths from inside the sandbox.

## 4. CRM project paths and execution identity (as they would be used)

| Item | Verified value |
|---|---|
| Execution and control host | DOCKER1 (no remote route) |
| Canonical checkout | `DOCKER1:/srv/CRM/main`, `forgev2-pl:forgev2-pl` 0750, `main` = `8a40862535336dd126d36f82088af7435d2c1931` |
| Worktree parent | `DOCKER1:/srv/CRM/worktrees` (`forgev2-pl` 0750). Proposed worktree: `/srv/CRM/worktrees/CRM-TEST-001`. Scratch: `/srv/CRM/worktrees/.forge-scratch/CRM-TEST-001` (parent `forgev2-pl` 0755). |
| PL identity | `forgev2-pl`, uid 1002, groups `forgev2-pl` only |
| Specialist identity | `claude -p` processes started by `/srv/forgev2/plugin/bin/forge-dispatch`, as uid 1002, each in a fresh empty HOME, with Claude Code's sandbox enforced (bubblewrap, no network, no unsandboxed fallback) |
| Ledger and records | `/home/forgev2-pl/.local/state/forgev2/{ledgers,records}/3b6369e4f8e78d83/CRM-TEST-001/` (parents 0700 `forgev2-pl`) |
| Engine-development identity (not used) | `forgedev`, uid 1003 |

## 5. Protected boundaries relevant to this WO

- **Engine** `/srv/forgev2`: root-owned and read-only to uid 1002. No application path overlaps it.
- **FOUNDRY:** `/srv/src/foundry` (`forgedev`) and the reference copies are not used as a project path.
- **Real beta runtime** `/srv/CRM/runtime/beta`: root 0700. Its env file is unreadable to uid 1002 and to `nobody`.
- **Other protected paths:** `/srv/CRM/deploy`, `/srv/CRM/releases`, and the PL's home and Claude login. The run-2 canaries cover the PL home and the login.
- **Observed sandbox effect:** sandboxed CRM-009-H and CRM-009-I runs (2026-11-11) report the unit suite passing, while the same test fails on the host. This is consistent with `/srv/CRM/runtime/beta` being invisible inside the sandbox. It is inferred, not verified.

## 6. Sufficiency assessment for a narrowly scoped CRM-TEST-001 acceptance

**Rogue's view, which is for CGPT to decide:** the run-2 evidence is *plausibly sufficient* for a CRM-TEST-001-only acceptance, for these reasons:
- the engine revision, Claude Code version, bubblewrap and the accepted scripts are the same as in run 2;
- the WO's risk surface is narrow: one test file, no network, no credentials, no real-data access by specialists;
- the run-2 controls cover exactly the specialist risks that apply (credential and canary reads, Git and engine writes, network).

**Evidence that is missing, or needs CGPT's view, before approval:**
1. A CGPT decision on whether the CRM-001-only acceptance may be extended by exact reference to CRM-TEST-001, or whether new evidence is required. A new sandbox run would need its own authorisation.
2. An assessment of note a (the root-owned `__pycache__` in the engine install) and whether it affects the "engine unchanged" condition.
3. The run-2 Claude binary hash was not recorded, so binary identity rests on version, owner and mode, plus an mtime before run 2.
4. The run-2 evidence is still root-only and has not been independently reviewed by CGPT. Rogue can provide hashes or excerpts if CGPT asks.
5. Whether `/srv/CRM/runtime` is invisible from inside the sandbox has not been verified. It matters only for the inference in WO §2 item 4, which is why AC4 is a host procedure.

**Until CGPT records an acceptance that applies to CRM-TEST-001, dispatch is BLOCKED (WO §11, G2).**
