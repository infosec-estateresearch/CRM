# CRM-TEST-001 - DELIVERED
Repository: infosec-estateresearch/CRM   Branch: forge/CRM-TEST-001   Candidate: f514f55e9143067f92e61ecc806508332f183dde   Base: c5a8cc3f (main, with the WO merged in PR #57)   WO: work-orders/CRM-TEST-001.md v1.2 (CGPT exact-version approval of 7e7c2d0c, Issue #56)

**Change** (`tests/unit/test_beta.py` only; patch sha256 87d0c2d2aaad6923a0b86dbb2e697e2c8419ea9f0273dec185e50c0b1a0f417c):
- `test_shell_guard` is now hermetic. A new opt-in fixture variable, `FAKE_NONROOT_DIR`, makes the fake `stat` play a non-root owner for exactly one path, so the no-seam case is refused whatever the host holds at `/srv/CRM/runtime/beta`.
- Added tests:
  - **T-a′:** the pinning-message assertions;
  - **T-b:** a present, non-private runtime is refused at the ownership/mode branch;
  - **T-c:** a fixture self-test;
  - **T-d:** a defective-guard fixture.
- No production guard, script or application changed.

**Round 1:** Engineer completed. Auditor, Tester and DevSecOps PASSED (each 1 of 4 executions). The CGPT Architect accepted the work with recorded limitations (Issue #56).

**Advisories:**
- `ac4-record-completeness`: the first host record lacked some command lines, exit codes and timestamps. A complete re-run transcript was added (Issue #56, comment 6857501985). DevSecOps reviewed it; the Tester did not, because ForgeV2 refused a second Tester dispatch once the decision was DELIVER. CGPT accepted this.
- `t-a-touches-real-runtime-metadata` / `t-a-real-path-metadata`: T-a stats the real runtime's mode, never its contents.
- `tester-forge-listing`: the Tester listed committed `.forge` file names (names only).
- `engineer-runtime-stat`: the Engineer ran a metadata-only `stat` of `/srv/CRM/runtime` in the sandbox, a WO §5 deviation. It showed uid 65534 and confirmed the user-namespace explanation.
- An empty `.claude/.cc-writes` directory was created by the harness in the snapshot. No candidate file changed.
- The host copies included `.forge`; all of them were removed.

**Tests (non-root):**
- Sandbox: unit 564 OK (1 skip, no Git metadata); load 223 OK.
- Host, as `nobody`: at the base, `test_shell_guard` fails (`0 != 2`); at the candidate, unit 564 OK and load 223 OK.
- M1 to M4 were detected both in the sandbox and on the host.
- The real runtime metadata was identical before and after.

**Evidence:**
- The PL snapshot manifest's sha256 is `4f9e21f8…a489a32` (295 files, verified against the commit).
- The PL evidence files (gates record, host record, manifests) are under `forgev2-pl:~/crm-evidence/CRM-TEST-001/`; their index `CRM-TEST-001.sha256` has sha256 `5bdbccd3…` for the host-record index. They are kept outside the records directory, because `forge-commit` publishes only `REPORT.md` and `prompts/`.
- `prompts/r2-tester.md` is the authorised reassessment prompt. ForgeV2 refused to dispatch it, and no execution was consumed.
