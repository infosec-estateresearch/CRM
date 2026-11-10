# Release bundle (CRM-007, PBI-016)

A release is a verified bundle of one accepted commit. crm-beta is installed from it, never from a Git checkout ([BETA.md](BETA.md)).

## Build

```sh
scripts/release.sh <commit> [outdir]       # on the build host, from a checkout of this repository
sha256sum <outdir>/crm-release-<short>.tar.gz
```

- The commit must be reachable from `main`, which means accepted.
- The output is `crm-release-<12-hex>.tar.gz`: the `git archive` of the commit under `crm-release-<short>/`, plus `RELEASE.json`.
- `RELEASE.json` holds:
  - the commit;
  - the image digests from the commit's `security/EXTERNAL_CODE_REGISTER.yaml`;
  - the sha256 of every file;
  - the latest commit of each CRM-002 to CRM-006 delivery record (`.forge/<WO>*/REPORT.md`), or `null` where none exists.
- The build is reproducible:
  - members are sorted and owned by `0:0`, with the commit time;
  - gzip has no name and mtime 0;
  - two builds of the same commit are identical byte for byte (`cmp`).

## Verify

`python3 scripts/release.py verify <bundle> [--sha256 <hex>]`. It refuses:
- trailing or invalid gzip;
- members outside the top directory, links, devices, or setuid or world-writable modes;
- a member set that differs from `RELEASE.json`;
- any file digest mismatch;
- register digests that differ from `RELEASE.json`;
- an image digest in `deploy/compose.json`, `deploy/beta/compose.json` or `deploy/beta/restoretest/compose.json` that is not in the register. The edge entry `haproxy@sha256:…` carries no tag, so for it only the digest is checked;
- a bundle sha256 that differs from `--sha256`.

## Deploy

`scripts/deploy_release.sh beta <bundle> --sha256 <hex> [--upgrade]` verifies the bundle before anything else, using the `release.py` of the checkout that runs it, not the one inside the bundle. Then it deploys from the unpacked, read-only copy (operator steps in [BETA.md](BETA.md)). Each step is a shell function. `tests/unit/test_beta.py` sources the script, which runs nothing when sourced, and tests the steps with stubbed `docker` and `python3`.
