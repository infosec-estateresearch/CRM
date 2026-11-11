# CRM-007, round 2: Engineer

Same worktree (`/srv/CRM/worktrees/CRM-007`), same rules and time box as round 1. Your round-1 work is uncommitted in the worktree. Keep it and build on it. Report `STATUS: completed` with Known gaps if you run out of time.

## PL decisions on your round-1 notes
1. **HTTPS detection (blocking).** You were right: with the Docker userland proxy, crm-app sees the bridge gateway, not loopback, so the `<If -R '127.0.0.0/8'>` branch never applies. Fix it this way:
   - `crm-app` (beta) publishes only on `127.0.0.1`, and only the edge connects to that port. In `crm-proxy.conf`, set `SetEnv HTTPS on` **unconditionally** and `RequestHeader unset X-Forwarded-Proto` (the header is no longer used).
   - Document the trust boundary in BETA.md: anything on the host's loopback is trusted.
   - Don't pin a subnet.
   - Check that `mod_headers` / `mod_env` are enabled in the espocrm image, and say what you found and how. If you can't verify it, list it for AC5 and use only directives that exist without extra modules where possible.
2. **env.example without values:** accepted. Placeholders go in BETA.md.
3. **The image tag rule:** accepted. Check the digest only for the edge entry.
4. **"Clean runtime" means only the operator's env file, root `0600`:** accepted. Document it.
5. **`config:set` read-back via `php -r`:** acceptable. The value must be the PHP boolean `false`; the string `'false'` must fail, and your `var_export` check does that. Keep it, and add a comment.

## Close the known gaps, in this order
1. **`tests/acceptance/test_beta_safe.py`.** This is a read-only suite run against a live beta. It is allowed under the WO's `tests/**`. It must perform **no write requests** (GET only), and a unit test must enforce that.
   - It uses `CRM_BASE_URL` plus a key read from a file path, never from argv.
   - It checks:
     - the API answers;
     - the roles from `config/access` exist;
     - `phoneNumberInternational` is false;
     - `siteUrl` uses https;
     - no synthetic seed marker exists (Account name containing `SENTINEL-7f3a`, matched as a count only).
   - Unit-test it in-process against a fake.
2. **The restore test mode.**
   - `restore.sh beta --restoretest <backup>` restores into the throwaway project `crm-beta-restoretest`, which publishes nothing, has its own volumes and network, and runs under a fixed runtime path such as `/srv/CRM/runtime/beta-restoretest`.
   - It prints record-count fingerprints, then tears the project down. Teardown never touches `crm-beta` or `crm-dev` resources.
   - Unit-test the guards.
3. **Timer unit template** under `deploy/beta/` (a `.service` and a `.timer`), installed only by the operator. Document it in BETA.md.
4. **Unit tests for the rest of `deploy_release.sh`:**
   - the edge render;
   - `provision_users` beta acceptance;
   - extract the post-unpack steps into testable functions where it helps, using stubbed docker/compose commands.
5. **Docs:** fill in BUILD.md, the README usage section, BETA.md (architecture, the upstream contract the PO configures in HAProxy, operator steps, backup/restore) and RELEASE.md.

Run the unit suite, report exact counts, and give mutation evidence for the new guards (GET-only, restoretest isolation, HTTPS directive). Finish in the Engineer final message format.
