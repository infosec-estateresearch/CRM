# CRM-002-T, round 1: Tester review

- **Worktree:** `/srv/CRM/worktrees/CRM-002-T`. It is read-only; don't touch any other path.
- **Candidate SHA:** `211a5a58de6eec36d010ef926aac5d607965aa6f`
- **Base SHA:** `76a3fdaa5782558ab708cb53c2d3341481f9bde6` (CRM-002-S DELIVERED, PR #17)
- **Scratch directory:** `/srv/CRM/worktrees/.forge-scratch/CRM-002-T`

Assess the candidate against the Work Order below, independently and according to your role. This is a small change to `hostcheck.parse_legacy_env`.

**Priority:** the CRM must read **exactly** the credential the consumer's loader reads, or refuse.
- **Blocking:** any input where the CRM accepts a target value that differs from what the reference loader (the algorithm in the WO) reads.
- **Blocking:** any path by which a value, or a characteristic of a value, reaches an error message, a log or the output.
- **Blocking:** any change outside the allowlist, or any weakening of CRM-002-S controls other than the shell-safe refusal this WO replaces.

**PL decisions on the engineer's notes:**
1. **Accepted:** the whole-file unclosed-quote refusal is removed. The consumer has no quote semantics, and quotes are refused inside target values.
2. **Accepted:** the extra whole-file refusal of the non-LF line breaks that `str.splitlines` honours. It is the same ambiguity class as CR.
3. **Accepted:** the backslash check runs on the stripped line.
4. **Accepted:** printable non-ASCII characters in values.

**PL counts-only check of the real file** (no values printed): no CR, no continuation, none of the extra line-break characters, and exactly one unquoted definition of each target name.

The sandbox has no network, Docker or root.

## Work Order (verbatim, `work-orders/CRM-002-T.md` v1.0 on main)

WO: CRM-002-T
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-002-S
BROWSER: no

# CRM-002-T — Legacy env parser: consumer-literal value semantics

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10 (Issue #9). This is a follow-up to CRM-002-S, which was DELIVERED as PR #17.
- **Parent:** CRM-PBI-005, part 1.

## Problem
`hostcheck.parse_legacy_env` (CRM-002-S) accepts an unquoted value only if it is *shell-safe*, matching `[^\s'"\\`$;&|<>()]+`. The PL ran a counts-only pre-check of the real legacy env file, printing no values. The file has no CR, no continuation lines, no quotes, and exactly one definition of each name. But one of the two credential values contains a character in the refused set `;&|<>()`. So L1 would fail closed, and the extraction could not start.

The file is never sourced by a shell. Its only consumer (the existing ERiC loader) reads each line like this:
1. strip it;
2. skip it if it is empty or starts with `#`;
3. skip it if it has no `=`;
4. split it at the first `=`;
5. strip the key and the value.

There is no quote, escape or shell processing, so the value is literal. The CRM must read the same credential that the consumer reads. Modifying the credential or its file is forbidden (PO override).

## Change
1. **Literal reading.** `parse_legacy_env` reads the two target names `NIF_SRC_SALESFORCE_USER` and `NIF_SRC_SALESFORCE_PASS` with the consumer's literal semantics, exactly as described in "Problem". Every CRM-002-S refusal that guards against an **ambiguous** reading stays. The parser refuses the whole file on any of these:
   - any CR;
   - any line, other than a comment, ending in a backslash;
   - a duplicate definition of a target name;
   - a value that is missing or empty.
2. **Characters refused in a target value** (the reading would be ambiguous, or the value was probably meant to be quoted):
   - `'` `"` `` ` `` `$` `\`;
   - any whitespace or control character inside the value;
   - any non-printable character.

   The characters `;&|<>()#!*?{}[]~^%@=+,.:/-_` are **accepted** as literal characters.
   - Note that `=` after the first one is part of the value, as it is for the consumer.
   - An `export ` prefix is **refused** for target names, because the consumer would treat `export NIF_…` as a different key.
3. **Other lines.** Lines with other names are not interpreted beyond the whole-file CR and continuation checks.
4. **Error messages** give only the line number and the reason code, never a value or a character class.
5. **Tests** (in-process, synthetic values only):
   - a synthetic password containing each newly accepted character is read exactly as a reference implementation of the consumer's loader reads it (a differential test over a generated corpus);
   - every refused case has a fixture;
   - `=` inside a value;
   - an `export` prefix;
   - the error messages contain no sentinel value;
   - every CRM-002-S test still passes. Change any test that asserted the old shell-safe refusal of `;&|<>()` to assert acceptance, and list those tests.
6. **Docs:** update `docs/MIGRATION.md` § "Temporary legacy credential" to describe the consumer-literal semantics. Do not name any real value or say which characters it contains.

## Scope
- **Allowlist:**
  - `migrate/lib/crm_migrate/hostcheck.py`
  - `tests/migrate/**`
  - `docs/MIGRATION.md`
  - `.forge/CRM-002-T/**`
- **Excluded:** every other file, the real env file, Salesforce access, and any change to the allowlist or to transport code.

## Acceptance criteria
- **AC1:** the unit tests pass with non-vacuity (mutation evidence), and the differential test agrees with the reference loader on every corpus entry that is not refused.
- **AC2:** gitleaks is clean, and no real value or value characteristic appears anywhere in the repository.
- **Operator stage:** the PL runs `hostcheck legacy-credentials` against the real file in counts-only mode. It reports that both names parsed, and prints no values. Then O1, followed by L1.
