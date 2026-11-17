# Engineer task: CRM-WIP-INT-001D (round 1, the ONLY Engineer execution allowed)

Worktree (work ONLY here; never touch any other path): /srv/CRM/worktrees/CRM-WIP-INT-001D
Expected HEAD: 1a1e80873b3abe5ba049923447f4fc2ee3784e6d (branch forge/CRM-WIP-INT-001D)
Scratch dir: /srv/CRM/worktrees/.forge-scratch/CRM-WIP-INT-001D
Do not read /home/WIP, /home/ELT, any .env, or any path outside the worktree (and your own temp dirs). No network.

## Change requested (WO text, essentials verbatim)

Outcome: A behavioural test fails when the loader's TLS host-name check (CURLOPT_SSL_VERIFYHOST) is weakened, while certificate verification (CURLOPT_SSL_VERIFYPEER) stays pinned by the existing F4 test. The production code does not change.

Allowlist (exact path): tests/unit/test_wip_panel.py. That is the only file that may differ from the base. WipLoader.php must stay byte-identical to the base (blob a1582260c90b598854406b2320af1df679461649).

Technique: a certificate generated at test time and explicitly trusted by pointing PHP's curl.cainfo at it (`php -d curl.cainfo=<certificate file>`) passes chain verification. Against `https://127.0.0.1:<port>`, VERIFYHOST 2 then accepts it only if the certificate names the target:
- cert names IP:127.0.0.1, trusted: VERIFYHOST 2 accepted (stub receives 1 request); VERIFYHOST 0 accepted.
- cert names only DNS:wrong.example, trusted: VERIFYHOST 2 refused (curl error 60), stub receives 0 requests; VERIFYHOST 0 accepted, stub receives 1 request.
- any cert not trusted: refused in both (VERIFYPEER hides VERIFYHOST, which is why the existing F4 test cannot see it).

Tests to add (one test each; names indicative):
- H1: A trusted certificate whose name does not match the URL is refused. Generate a self-signed certificate and key ONLY in the test's temporary directory with the `openssl` command, `-addext subjectAltName=DNS:wrong.example` (no IP name). Start the HTTPS loopback stub with it. Run the production loader against https://127.0.0.1:<port> with PHP started as `php -d curl.cainfo=<that certificate>`. Expect {"wipStatus": "WIP unavailable", "wipCases": ""}, zero requests received by the stub, and a log line carrying only the failure class (as the F4 test asserts). Also assert, independently of the loader, that the certificate IS trusted: a Python `ssl` client with cafile=<certificate> and check_hostname=False gets a 200 from the stub, and the same client with host-name checking on fails with a certificate-verification error. This proves the refusal is caused by the name, not trust.
- H2: Positive control. A second certificate generated the same way, `-addext subjectAltName=IP:127.0.0.1`, trusted the same way. The loader returns "WIP data available" for a valid contract reply and the stub receives exactly one request.

Support change inside the same file: `run_loader` needs a way to pass extra PHP command-line settings (for `-d curl.cainfo=...`). Add an optional parameter whose default leaves every existing call unchanged. Do not change any existing test's behaviour or expectations. No key or certificate is committed. If `openssl` is missing the tests FAIL loudly (no skip), as the existing F4 test does. TLS verification stays enabled in the loader and in every test.

Non-vacuity evidence required in your final report: in a SCRATCH COPY that is never committed (copy the tree or the two needed files to a temp dir; if you must mutate the worktree's WipLoader.php, restore it byte-identical and verify the blob id), change CURLOPT_SSL_VERIFYHOST from 2 to 0 in WipLoader.php and show H1 failing (and H2 still passing); restore. Then change it to 1 and report the observed result (do not assume equivalence). Report test names and failures. The existing F4 test must continue to fail when VERIFYPEER is turned off (verify the same way).

Exclusions: no other file (no PHP, metadata, layout, role, i18n, deploy/, config/, scripts/, no other test file, no docs). No refactoring, renaming or reformatting. No new framework or dependency. Do not git commit (the PL commits).

Stop conditions (report `blocked`, do not work around): the curl.cainfo technique not working in your sandbox (no substitute technique, no mocking TLS, no skip); a new test showing the loader is wrong (report, never fix); any need for network, database, env file, browser.

## Verification you must run and report
- Whole existing unit suite as your unprivileged account: 599 tests at base, `OK (skipped=1)` (known unrelated Git-metadata test). Report counts before and after; 0 failures. PHP tests must have run; a skip does not count. Find the test command from the repo.
- Static checks: `git diff --stat` touches only tests/unit/test_wip_panel.py; WipLoader.php blob unchanged; no key/cert material in the diff; no `skip` introduced; gitleaks on the diff if available.
- Use placeholders for any URL/token in your report. Your final message must start with the status word `completed`, `blocked` or `failed`, followed by your report.
