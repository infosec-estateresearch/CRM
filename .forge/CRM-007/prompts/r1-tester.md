# CRM-007, round 1 review: Tester

- **Worktree:** `/srv/CRM/worktrees/CRM-007`. It is read-only; use only scratch at `/srv/CRM/worktrees/.forge-scratch/CRM-007`.
- **Candidate SHA:** `31b63b522f26ed3ac1204ea954dba25e2a8bbc67`
- **Base SHA:** `e1f9a6899e82ac5862849db0bf1f00dbcae51244`
- **Work order:** `/srv/CRM/main/work-orders/CRM-007.md` **v1.1** (on main).

Assess the candidate independently against the work order, according to your role. The operator stage (AC3–AC7) is run later by the PL as root. Review the code, the unit tests and the docs. You start no containers and use no network.

**Blocking:**
- a beta path that can reach crm-dev resources, or the reverse;
- crm-app (beta) published on anything but `127.0.0.1`;
- an edge that admits sources outside the validated private /32 list, or binds to all interfaces;
- a real IP, hostname or person/firm name in the repo;
- a secret in argv, logs or the repo;
- a beta-safe suite that can write;
- a restore test that can touch crm-beta or crm-dev;
- a bundle that verifies when tampered, or isn't reproducible;
- synthetic seeding possible on beta;
- dev behaviour changed;
- a change outside the allowlist;
- any host firewall tooling (iptables, ufw or nftables are prohibited).

**PL decisions already taken:**
- `SetEnv HTTPS on` is unconditional, because crm-app is loopback-only and only the edge connects. With the Docker userland proxy, crm-app sees the bridge gateway, not loopback.
- env.example holds names only.
- The edge digest is checked against the register with no tag.
- A "clean runtime" holds only the operator's root `0600` env file.
- **Not yet verified, so they go to the operator stage:**
  - the espocrm image modules;
  - whether the API user can read `GET Role` and `GET Settings`;
  - `systemd-analyze verify`.
- `docs/MIGRATION-DATA-HANDLING.md` exists on main but not on this base. BETA.md citing it is acceptable once both are merged.

Run every new guard against broken inputs of your own, and run the bundle build twice to compare its bytes. Exercise deploy_release.sh's functions with stubs.
