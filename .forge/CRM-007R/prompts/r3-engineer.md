# CRM-007R, round 3: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-007R`. HEAD should be candidate `dd89164b76489ae6331dc1fef2f777d6088039bf`; confirm it.
- **Same WOs and rules, same 30-minute box.** Report `STATUS: completed`.

1. **Blocking (Auditor and Tester).** Make `check_restoretest_compose` an **allowlist**, mirroring beta's:
   - **top level:** only `name` (if used), `services`, `networks` and `volumes`. `include`, `x-*`, `secrets`, `configs` and anything else are refused;
   - **services:** exactly one service, `crm-db`, with keys only from `image` (`name@sha256:<64 hex>`), `environment`, `volumes`, `networks`, `healthcheck`, `restart`, `command` and `entrypoint` if the shipped file uses them. Everything else is refused, including `depends_on`, `ports`, `network_mode`, `security_opt`, `userns_mode`, `uts`, `cgroup`, `pid`, `ipc`, `privileged`, `cap_add`, `devices`, `tmpfs`, `extra_hosts`, `external_links`, `labels`, `sysctls`, `runtime`, `secrets` and `configs`;
   - **volume mounts:** named local volumes only, with no `bind`/`subpath`/`propagation` options;
   - networks and volumes keep the round-2 rules.
   
   Add a broken fixture or subtest per refused key (`include` especially). Keep the shipped `deploy/beta/restoretest/compose.json` passing.
2. **`export_csv.py`:** use `re.fullmatch` (or `\Z`) for `EXPORT_NAME_RE`, so `"export-n\n"` is refused. Add a test.
3. **Export URL forwarding:** add a test that the URL `export.sh` forwards to `export_csv.py` is the derived pinned URL. This kills the equivalent mutant, as documentation.

Run the unit and load suites, report exact counts, and give mutation evidence for items 1 and 2. Finish in the Engineer final message format.
