# CRM-007, round 3 review: Devsecops

- **Worktree:** `/srv/CRM/worktrees/CRM-007`. It is read-only; use only scratch at `/srv/CRM/worktrees/.forge-scratch/CRM-007`.
- **Candidate SHA:** `82c05ef3abe444c1f8f01a0ed11483e526e27f40`
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

**Round 2.** The round-1 findings went to the engineer. Two were blocking: the self-attested bundle and the unchecked `CRM_DB_DIR`.

**PL decisions:**
- `--sha256` is mandatory for deploy.
- `.forge/` is excluded from the bundle (CRM-D017).
- BETA.md cites MIGRATION-DATA-HANDLING.md §4, which resolves after merge.
- The edge no longer sets `X-Forwarded-Proto`.

Verify that each round-1 finding is fixed, and look for new defects.

**Round 3** (the engineer's final execution; no further engineering rounds are possible). The round-2 findings went to the engineer.
- The README is restored to its base text outside `## Usage`.
- **PL decisions:**
  - `"CRM-002": null` in RELEASE.json is accepted;
  - tightening dev's `CRM_DB_DIR` check is intended (the live dev env is compliant);
  - `CRM_TEST_ROOT` is the only test seam, honoured only under `/tmp`.

Verify each round-2 finding is fixed, and look for new defects. Classify as **blocking** only what meets the blocking list above.
