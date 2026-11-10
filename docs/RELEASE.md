# Release bundle (CRM-007, PBI-016)

A release is a verified bundle of one accepted commit. crm-beta is installed from it, never from a Git checkout ([BETA.md](BETA.md)).

## Build

```sh
scripts/release.sh <commit> [outdir]       # on the build host, from a checkout of this repository
sha256sum <outdir>/crm-release-<short>.tar.gz
```

- The commit must be reachable from `main`, which means accepted.
- The output is `crm-release-<12-hex>.tar.gz`: the `git archive` of the commit under `crm-release-<short>/`, plus `RELEASE.json`.
- **Excluded:** `.forge/**` (the delivery records; PL decision under CRM-D017). `RELEASE.json` records this as `"excluded": [".forge/"]`, and `verify` refuses a bundle that does not record it or holds anything under `.forge/`. The delivery records stay listed by commit SHA (below).
- `RELEASE.json` holds:
  - the commit;
  - the image digests from the commit's `security/EXTERNAL_CODE_REGISTER.yaml`;
  - the sha256 of every file;
  - the latest commit of each CRM-002 to CRM-006 delivery record (`.forge/<WO>*/REPORT.md`), or `null` where none exists;
  - `excluded`: `[".forge/"]`.
- The build is reproducible:
  - members are sorted and owned by `0:0`, with the commit time;
  - gzip has no name and mtime 0;
  - two builds of the same commit are identical byte for byte (`cmp`).

## Verify

`python3 scripts/release.py verify <bundle> [--sha256 <hex>]`.

**Anchoring.** `RELEASE.json` is inside the bundle and unsigned: anyone who changes a file and re-computes `RELEASE.json` gets a bundle that is internally consistent. Only the bundle's sha256 from the release record (`sha256sum` on the build host) anchors it. Without `--sha256`, `verify` is for inspection only and prints a warning that the bundle is NOT ANCHORED. `--sha256` must be exactly 64 lower-case hex digits; `deploy_release.sh` always requires it.

It refuses:
- trailing or invalid gzip;
- members outside the top directory, links, devices, or setuid or world-writable modes;
- a member set that differs from `RELEASE.json`;
- any file digest mismatch;
- register digests that differ from `RELEASE.json`;
- an image digest in `deploy/compose.json`, `deploy/beta/compose.json` or `deploy/beta/restoretest/compose.json` that is not in the register. The edge entry `haproxy@sha256:…` carries no tag, so for it only the digest is checked;
- a bundle sha256 that differs from `--sha256`;
- `RELEASE.json` without `"excluded": [".forge/"]`, or any member under `.forge/`.

`python3 scripts/release.py verify-tree <dir> <bundle> --sha256 <hex>` re-verifies the anchored bundle and then refuses unless `<dir>` holds exactly its files: every file listed in `RELEASE.json` plus `RELEASE.json` itself, byte for byte, with no extra, missing or changed file, no extra directory and no link or special file.

## Deploy

`scripts/deploy_release.sh beta <bundle> --sha256 <hex> [--upgrade]`. `--sha256` is mandatory: if it is missing or malformed the script stops before step 1, with no docker call and no deploy directory. It verifies the bundle before anything else, using the `release.py` of the checkout that runs it, not the one inside the bundle:
1. it copies the bundle into a root-only private temp file (directory `0700`, file `0600`);
2. computes the sha256 of that copy and compares it with `--sha256`;
3. verifies that same copy (`release.py verify --sha256`);
4. unpacks from that copy only;
5. re-checks every unpacked file against `RELEASE.json` (`release.py verify-tree`) before moving it into `/srv/CRM/deploy/<short>`.

With `--upgrade` and an existing `/srv/CRM/deploy/<short>`, that directory is checked the same way, and any difference or extra file refuses the deploy. Then it deploys from the unpacked, read-only copy (operator steps in [BETA.md](BETA.md)). Each step is a shell function. `tests/unit/test_beta.py` sources the script, which runs nothing when sourced, and tests the steps with stubbed `docker` and `python3`.
