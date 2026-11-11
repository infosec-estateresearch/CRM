# CRM-007, round 4: Engineer (final execution)

- **Worktree:** `/srv/CRM/worktrees/CRM-007`. HEAD should be candidate `4ba1a5476c3dabf13f650667a42d54eb9399da1f`; confirm it.
- **This is your last execution.** Keep every change small and tested. Report `STATUS: completed` with Known gaps if you run out of time.
- Do item 1 first.

1. **Blocking (scope).** Revert the README `**Status:**` line (line 5) to exactly its base text at `e1f9a68`. My round-3 instruction to rewrite it was outside the WO allowlist. README edits stay inside `## Usage` only.
2. **Compose policy: switch to an allowlist.** In `check_beta_compose`, refuse any key that isn't in an explicit per-service allowlist of the keys the shipped `deploy/beta/compose.json` uses:
   - services: `image`, `environment`, `healthcheck`, `networks`, `ports`, `restart`, `volumes`, `depends_on`, `entrypoint`, `command` if used;
   - edge: additionally `cap_drop`, `read_only`, `security_opt`, `user`, and `network_mode: host`;
   - top level: `name` (if used), `services`, `networks`.

   This closes `volumes_from`, `network_mode: container:`, `pid`/`ipc`, `env_file`, `extends`, `include`, `external_links`, `secrets`/`configs`, `container_name`, `devices`, `privileged`, `cap_add`, `build`, and an unpinned image (`image` must be `name@sha256:<64 hex>`). Write one test per refused key (subtests are fine).
3. **Edge config revalidation.** `check_access.py beta`, without `--render`, compares the on-disk `/srv/CRM/runtime/beta/edge/haproxy.cfg` with `render_edge()` byte for byte and fails closed on any difference or if the file is missing. When the file changes, `up.sh beta` re-renders it, then force-recreates `crm-beta-edge`. Add tests.
4. **`export.sh beta`** requires `CRM_BASE_URL` to be exactly `http://127.0.0.1:<CRM_BETA_APP_PORT from the checked env file>`, as provision and seed do. Add a test.
5. **`verify-tree`** refuses setuid/setgid and world-writable files, as `verify` does for tar members. Add a test.
6. **Pin beta's runtime.** Outside tests, the beta runtime is the constant `/srv/CRM/runtime/beta`. Any test seam must be explicit, for example a `CRM_TEST_ROOT` honoured only when it is under `/tmp`. Dev is unchanged.
7. **Remove the dead code:** `TARGET_ENV = "dev"` in `provision_access.py` and the unused `require_dev()` in `common.sh`. Do both only if grep confirms there are no readers.

**PL decisions (no change needed):**
- `"CRM-002": null` in `RELEASE.json` is accepted, because CRM-002 has no ForgeV2 REPORT in `.forge/`. Document it in RELEASE.md if it isn't there already.
- Tightening dev's `CRM_DB_DIR` check is intended. The PL confirmed that the live dev env has `CRM_DB_DIR=/srv/CRM/runtime/dev/db`.

Run the unit suite and the load suite, report exact counts, and give mutation evidence for items 2–6. Finish in the Engineer final message format.
