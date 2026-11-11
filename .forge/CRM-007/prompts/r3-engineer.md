# CRM-007, round 3: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-007`. HEAD should be candidate `31b63b522f26ed3ac1204ea954dba25e2a8bbc67`; confirm it.
- **Same WO v1.1, same rules.** Report `STATUS: completed` with Known gaps if you run out of time (30-minute box; return by about 25 minutes).
- Do the blocking items first.

## Blocking 1: the bundle can be tampered with (all three reviewers)
`RELEASE.json` is unsigned and sits inside the bundle. Anyone who changes a file and recomputes `RELEASE.json` gets a bundle that verifies and deploys.
- **`--sha256 HEX` is mandatory** in `deploy_release.sh`. If it is missing or malformed, die before step 1, with no docker calls and no deploy dir created. `release.py verify` stays usable without it for inspection, but then it prints a warning that the bundle is not anchored.
- Also anchor the image digests outside the bundle: `deploy_release.sh` compares the bundle's `RELEASE.json` image digests with the bundle's register, as now. **In addition**, it checks that `--sha256` matches the bundle's own sha256.
- **Tests:**
  - a consistently re-hashed `RELEASE.json` is refused without `--sha256`, and with a wrong one;
  - with the right one it proceeds.
- **Verify what you extract:**
  1. copy the bundle into a root-only private temp file;
  2. compute its sha256 from that copy;
  3. verify that same copy;
  4. unpack from it;
  5. after unpacking, re-check every unpacked file against `RELEASE.json`, with no extras and none missing.
- **On `--upgrade` with an existing `/srv/CRM/deploy/<short>`:** check every file against `RELEASE.json`, and refuse on any difference or extra file.

## Blocking 2: `CRM_DB_DIR` is unchecked (all three reviewers)
- Add `CRM_DB_DIR` to `require_runtime_paths`; it must be exactly `$CRM_RUNTIME_DIR/db`.
- Check the Compose-resolved crm-db `/var/lib/mysql` bind in `require_compose_mounts`.
- Do both for **both** targets. Dev behaviour is otherwise unchanged: dev's db is already `/srv/CRM/runtime/dev/db`.
- **Tests:** beta with the dev db is refused, dev with the beta db is refused, and a control case passes.

## Advisories: fix these
- **Bundle contents (PL decision):** exclude `.forge/**` from the bundle, per CRM-D017. Record the exclusion in `RELEASE.json` (`excluded: [".forge/"]`) and in RELEASE.md. Delivery-record commits stay listed by SHA.
- **Retention:** BETA.md cites `docs/MIGRATION-DATA-HANDLING.md` §4 for retention. That file is on main, and the citation becomes valid on merge. Remove the "PO's decision" wording.
- **Edge policy:**
  - normalise whitespace (any run of spaces or tabs counts as one separator) before matching;
  - allow only the directives and sections the template uses;
  - refuse unknown directives, a second `server`, `mode tcp`, `use_backend`, and any `http-request allow`.
- **Upstream sources** must be exactly `a.b.c.d` or `a.b.c.d/32`, so a trailing `/` is refused.
- **Compose policy:** refuse
  - external or named networks and volumes;
  - a bind source outside `$CRM_RUNTIME_DIR` or the release dir;
  - `docker.sock`;
  - a missing `user` on the edge, or one with uid 0 in any form.
- **Restore test:**
  - a missing table count makes the run exit non-zero;
  - the `CRM_RESTORETEST_DIR` parent must be exactly `/srv/CRM/runtime`; a test-only override is allowed under a tmp root only.
- **Unit tests** that kill the three surviving mutants:
  - the forwarded-header rule;
  - compose digest in the register;
  - gzip `mtime=0`: build twice with a different clock, or patch time.
- **Drop the edge's `X-Forwarded-Proto` set** and the policy rule requiring it (Apache discards the header now). Keep `X-Forwarded-For` handling as it is.
- **README:** fix the status line ("Nothing is installed or released") and the duplicate `### Usage` heading.

Run the unit suite, report exact counts, and give mutation evidence for each blocking fix and each new policy rule. Finish in the Engineer final message format.
