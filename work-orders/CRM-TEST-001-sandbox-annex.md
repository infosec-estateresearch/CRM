# CRM-TEST-001: ForgeV2 sandbox entry-gate evidence annex

- **Version:** v1.1 DRAFT, 2026-11-13, prepared by Rogue (Orchestrator) for CGPT review. v1.1 adds §7 (the fresh per-WO gate assessment requested in CGPT's review of `1dc7cb3a`, item 7) and corrects the §2 notes and the §5 inference. §1 to §4 are otherwise unchanged.
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

- **Note a (v1.1).** A root-owned bytecode cache appeared in the engine install on 2026-11-10. It is ignored by Git, and no tracked content changed. It is now attributed: it was **created by the Orchestrator (Rogue) running `/srv/forgev2/plugin/bin/forge-ledger --help` as root** at 2026-11-10T12:59:31Z. It is **not remediated**: changing ForgeV2 is out of authority. Details are in §7.3.
- **Note b.** The 13:36Z mtime was caused by this annex's own read-only `git status` (Git's optional index-lock attempt). No file was added, removed or changed. A 13:07Z change earlier that day does not appear in any Rogue session log. It is unattributed, and no entry changed. Future engine reads should use `GIT_OPTIONAL_LOCKS=0`, so that they do not touch directory metadata.

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
- **Observed sandbox effect (corrected in v1.1):** sandboxed CRM-009-H and CRM-009-I runs (2026-11-11) report the unit suite passing, while the same test fails on the host. The mechanism is **unverified**.
  - The dispatch settings deny reads only to the PL's home, its Claude configuration and the ForgeV2 state directory, so the path being invisible (the v1.0 wording) is the less likely explanation.
  - The likelier explanation is the bubblewrap user namespace showing root-owned host files with an unmapped (overflow) uid.
  - The WO no longer depends on either explanation (WO §2 item 4, §6a M2).

## 6. Sufficiency assessment for a narrowly scoped CRM-TEST-001 acceptance

*This is the v1.0 assessment, kept for the record. CGPT's v1.0 review (item 7) decided its question 1: run 2 may be reused as a basis for a CRM-TEST-001-specific decision, but it is not transferable automatically. §7 supersedes this section.*

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

## 7. Fresh per-WO gate assessment for CRM-TEST-001 (v1.1)

**Method:** read-only, on DOCKER1, 2026-11-13 after 13:40Z.
- Engine Git reads used `GIT_OPTIONAL_LOCKS=0`; the engine `.git` directory mtime stayed at 13:36:12Z, as recorded in §2.
- No sandbox, smoke test or bubblewrap probe was run, and ForgeV2 was not modified.
- **This section is evidence, not acceptance.** The explicit CRM-TEST-001 sandbox acceptance is a separate CGPT decision (WO §11, G2).

### 7.1 Engine revision and protected installation

- **Revision:** `/srv/forgev2` HEAD is `63b6b8ab6c6d3c12d1ef3f0aeabe2ca22fbefb82`; `refs/heads/main` and `origin/HEAD` are the same commit. This is the revision pinned in the CRM-001 acceptance.
- **Working tree:** `git status --porcelain --ignored` shows no tracked change. The only ignored entry is `plugin/lib/__pycache__/` (§7.3).
- **Write exposure:** `find /srv/forgev2 -writable`, run as `forgev2-pl`, returns **0 paths**. The installation is root-owned and is not writable by the PL or by specialists, which run as the same uid.
- **Overlap guard:** the engine refuses any project root or worktree overlapping `/srv/forgev2`, `/srv/foundry` or its own install (`forgelib.PROTECTED_INSTALLS`, `validate_project_target`). `/srv/CRM/main` and `/srv/CRM/worktrees` do not overlap.

### 7.2 Current Claude and bubblewrap identity

| Item | Value |
|---|---|
| Claude Code | `/usr/local/bin/claude`, 2.1.317, root 0755, mtime 2026-11-04T14:02:44Z, sha256 `eb224419e344575faa4a1f39b290b649425a10cd5ee2ef1d003480cd9ae57eb0` |
| Run-2 Claude version | 2.1.317 (`claude_code_version` in the run-2 `engineer.jsonl` init record) |
| bubblewrap | `/usr/bin/bwrap`, 0.12.0-1~deb13u1, root 0755, not setuid, sha256 `573236e5328ac2ebb08f59ae3a9805b4f8d12bdef14be8af4450d5463294985f` |

- **Missing run-2 binary hash (stated, not established):** run 2 recorded only the owner, the mode (`host:claude-binary` PASS) and the version, not a hash. The identity of today's binary with the run-2 binary therefore rests on:
  - the same version string;
  - the same owner and mode;
  - a file mtime (2026-11-04) earlier than run 2 (2026-11-09).

  This is strong circumstantial evidence, not a cryptographic proof. The hashes above are the baseline that G5 must re-check before dispatch.

### 7.3 The ignored root-owned bytecode file

`plugin/lib/__pycache__/forgelib.cpython-313.pyc`: root 0644, 54,270 bytes, mtime 2026-11-10T12:59:31.584Z, sha256 `1e456d81c48efcc6d3ba1f65b08cb3e5ef68f09c5d71261fe1620769c5ec52c1`.

**Established:**
- **Origin.** It was created by the Orchestrator, Rogue, as root, running `/srv/forgev2/plugin/bin/forge-ledger --help` at 2026-11-10T12:59:31.511Z. This is from Rogue's session transcript, 73 ms before the file's mtime. Python wrote the cache as a side effect of importing `forgelib`. This was a Rogue boundary lapse (a root process writing inside the protected install), and it is reported, not remediated.
- **Header.** Its header matches the tracked source `plugin/lib/forgelib.py` (sha256 `6a7d587a79da13de733dc41a97e6f499c163062151175acda74918ca19f6dc55`, 33,209 bytes, mtime 2026-11-04T12:01:36Z): the CPython 3.13 magic number, timestamp-validated, with the same source mtime and size. Python will therefore use it when `forgelib` is imported, including by the PL's `forge-*` commands.
- **Code.** Its code object is **semantically identical** to a fresh compile of the tracked source. A recursive comparison of bytecode, constants, names, variables, line and exception tables, flags and nested code objects found no difference. The raw marshal bytes differ by 7 bytes (54,263 against 54,270), which is consistent with marshal reference-flag non-determinism, not with different code.
- **Exposure.** Specialists do not import `forgelib`; only the PL-side `forge-*` tools do. The file is not writable by uid 1002.

**Not established:**
- that the bytes are identical to any earlier cache, because none existed at run 2;
- that no other root process ever rewrote it (only the mtime is evidence);
- that it is harmless beyond semantic equivalence (for example, against a future source change: Python would then recompile, and fail to write as uid 1002).

**Not done:** removal. Deleting it would modify ForgeV2, which is outside this authority. Its removal, or its acceptance as benign, is a decision for CGPT or the engine owner under engine-development authority (`forgedev`).

**Prevention:** Rogue will not run engine helpers as root again. If a root read is ever unavoidable, it will use `PYTHONDONTWRITEBYTECODE=1`, and Git reads will use `GIT_OPTIONAL_LOCKS=0`.

### 7.4 Run-2 evidence and checksums relied on

- **Directory:** `/root/forgev2-evidence/SANDBOX-SMOKE/run2-20261109T171810Z/` (root 0700, 44 files). The sha256 of its `sha256sum *` manifest is `8f71a9302b61ce0307b447102cd2f9b3909a543843b7578bf1f8c2b4614ade8f`.
- **Key files:**
  - `RESULT.txt`: `d652fbf9…ebae14` (`SUMMARY PASS=180 FAIL=0 NOT_RUN=0`);
  - `settings-all-roles.json`: `6944f419…f44b` (all four roles have `allowUnsandboxedCommands: false`);
  - `console.log`: `ce1d6695…df3b`;
  - `probe.sh`: `3a0bdc7c…8ed5`.
- **Accepted scripts (unchanged):** `sandbox-smoke.sh` `45e00ca5…217ee`; `evaluate.py` `bb0ca083…f8`.
- **Relevance to CRM-TEST-001:**
  - Canary and credential reads were denied for all four roles.
  - Git metadata, ref, hook, record and checkout writes were denied.
  - Network was denied (HTTPS, loopback, UNIX socket, nested user namespace).
  - Reviewers could not write the worktree, and the Engineer could.
  - Edits outside the permitted paths were denied.
  - The setup failed closed without bubblewrap.
  - The engine was unchanged.
- **Not covered by run 2:** the CRM worktree layout (run 2 used a `/tmp` fixture project), and how `/srv/CRM/runtime` appears inside the sandbox.

### 7.5 PL identity, worktree, scratch and log boundaries

| Boundary | Value | Specialist access (from `forgelib.sandbox_settings`, engine `63b6b8ab`) |
|---|---|---|
| PL | `forgev2-pl` uid 1002, group `forgev2-pl` only; `forge-dispatch` refuses root (`require_non_root`) | n/a |
| Worktree | `/srv/CRM/worktrees/CRM-TEST-001` (proposed; created by `forge-start` after approval) | Engineer: write (never `.git` or `.forge`, both deny-listed). Reviewers: read only. |
| Scratch | `/srv/CRM/worktrees/.forge-scratch/CRM-TEST-001` | All roles: write; it is the starting directory |
| Specialist HOME | fresh `tempfile.mkdtemp(prefix="forgev2-<role>-")`, removed after each run | write; a private view |
| Ledger and records | `/home/forgev2-pl/.local/state/forgev2/{ledgers,records}/3b6369e4f8e78d83/CRM-TEST-001/` | **denyRead** (PL home and state directory), never writable |
| Claude login and configuration | the PL's `~/.claude` | **denyRead** |
| Network | none (`allowedDomains: []`, `strictAllowlist: true`) | denied |

### 7.6 Protected runtime and engine paths are not permitted specialist write paths

- **Permitted write set:** for the Engineer, it is exactly {worktree, scratch, temporary HOME}; for reviewers, {scratch, temporary HOME}. All are under `/srv/CRM/worktrees/` or a fresh `/tmp/forgev2-<role>-*`.
- **Paths outside that set:** none of these is in or under it: `/srv/forgev2`, `/srv/foundry`, `/srv/src/foundry`, `/srv/CRM/main`, `/srv/CRM/runtime` (and `/beta`), `/srv/CRM/deploy` and `/srv/CRM/releases`.
- **Filesystem permissions, as uid 1002:**
  - `/srv/CRM/runtime` is not writable;
  - `/srv/CRM/runtime/beta` is not writable;
  - `/srv/CRM/runtime/beta/env` is not readable;
  - `/srv/forgev2` has 0 writable paths.
- **Read exposure (stated):** the sandbox does not deny-list reads of `/srv/CRM`. Specialists can read what uid 1002 can read on the host, including the canonical checkout and the metadata of world-traversable directories. They cannot read the root-0700 beta runtime's contents.

### 7.7 No unsandboxed fallback

- **Engine settings:** `sandbox_settings` (engine `63b6b8ab`) sets `enabled: true`, `failIfUnavailable: true`, `allowUnsandboxedCommands: false`, `excludedCommands: []`, `enableWeakerNestedSandbox: false`, `allowNestedUserNamespaces: false` and `disableAllHooks: true`.
- **Evidence:** run 2 confirmed these values for all four roles (`settings:all-roles-fail-closed` PASS), and `p4:fail-closed` PASS: without bubblewrap, 0 Bash attempts succeeded.
- **Integrity check:** `forge-dispatch` also checks that the Claude binary and its directory are root-owned and not group- or world-writable before it starts (`check_runtime`).
- **Caveat (found in v1.1):** `check_runtime` skips that binary check when the environment variable `FORGE_CLAUDE` is set, and then uses the named executable. `forge-dispatch` records any such override as a `claude` key on the spawn event in the ledger.
  - The sandbox settings still apply to whatever binary runs, but the binary identity would no longer be the one assessed here.
  - **Current state:** none of the 197 spawn events across all CRM WO ledgers carries an override, and `FORGE_CLAUDE` is unset in `forgev2-pl`'s login shell.
  - **G5 therefore also requires:** `FORGE_CLAUDE` unset in the PL's dispatch environment, and no `claude` key on any CRM-TEST-001 spawn event. The PL verifies both, and the reviewers' evidence is checked against them.

### 7.8 Conclusion for CGPT

- **Unchanged since run 2:** the engine revision, tracked tree, Claude version, bubblewrap version, accepted scripts and sandbox settings are unchanged, and the protected paths are outside every permitted specialist write path.
- **Deviations from run 2:** two deviations are identified and characterised, and neither is a tracked-content change:
  1. the root-written bytecode cache (§7.3), which is semantically identical to its source;
  2. the absent run-2 binary hash (§7.2).
- **Rogue's assessment:** nothing found here **prevents** a bounded, CRM-TEST-001-specific acceptance, but that acceptance is CGPT's decision.
- **If CGPT decides that either deviation needs remediation or new evidence first:** the WO is **BLOCKED** at G2 or G5. The remedy (removing the cache under engine authority, or a new authorised sandbox run) is outside this assignment.
