# CRM-002-S, round 4: Auditor review

- **Worktree:** `/srv/CRM/worktrees/CRM-002-S`. It is read-only; don't touch any other path.
- **Candidate SHA:** `01f149ff65651652ea3e7dfa0a5727b7b4eb6fc3`
- **Base SHA:** `98f10ff6654f0c072b932ceff4243022efbfec8e` (CRM-002 DELIVERED, PR #12)
- **Scratch directory:** `/srv/CRM/worktrees/.forge-scratch/CRM-002-S`

Assess the candidate against the Work Order below, independently and according to your role.

**Highest priority (unchanged).** This adapter will be run by the operator with an **administrator-level, write-capable** Salesforce identity. Every request must pass the read-only allowlist. Any of these is **blocking**:
- a SOAP or REST request that could write, delete, merge, undelete, change a password or run Apex, and still passes the allowlist;
- a request that reaches another host;
- any path by which the password or session id could reach stdout, stderr, logs, files, exceptions (including `__context__` / `__cause__`) or argv.

**Round 4 (final permitted round for every role).** Engineer round 4 is in the candidate. Verify each item independently:
- **Blocking from round 3: `stdin-credential-exception-context`.** The engineer reports that every `raise` inside an `except` on a secret-bearing parse now sets a flag and raises after the block. This covers:
  - `cli.read_stdin_credentials`;
  - `waiver.parse_waiver` / `load_waiver`;
  - `auth_soap` (`_decode_strict_utf8`, `_HardenedXMLParser.parse`, `parse_xml`, `origin_of_server_url`, `check_login_body`);
  - `client.SalesforceClient._json`.

  Look yourself for any remaining `raise` inside an `except` whose context could hold the password, the session id or an access token, for example with `grep -n "except" migrate/lib`. `check_logout_body` was deliberately left as is: its context is a ProtocolError with a fixed message. Confirm that this is safe.
- **Advisories fixed:**
  - `CountsLog` re-checks `sf_error` against `SF_ERROR_CODES`;
  - the env parser refuses any CR and any trailing-backslash continuation in the whole file;
  - a test pins the literal 4096/4097 stdin boundary;
  - the `User updateable` finding is reported under an identity waiver;
  - `docs/MIGRATION.md` is updated.
- **Behaviour change accepted by the PL:** CRLF env files are now refused. That fails closed, and the operator checks the real file at L1.

**PL notes (unchanged):** the legacy env path comes from `CRM_LEGACY_ENV_FILE` in the root-only runtime env, and an empty default fails closed. The sandbox has no network, Docker or root, and the operator stages are outside this run. Report only defects that matter; this is the last review round.

## Work Order (verbatim, `work-orders/CRM-002-S.md` v1.0 on main)

WO: CRM-002-S
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-002
BROWSER: no

# CRM-002-S — Temporary legacy-credential adapter for the read-only extractor (operator-only)

- **Version:** v1.0, 2026-11-10.
- **Authority:** the PO priority override of 2026-11-10, recorded on Issue #9. It authorises temporary reuse of the existing Salesforce credential for a read-only migration, on these conditions:
  - every request passes an independently tested read-only allowlist;
  - only the trusted operator handles the credential and runs the extraction;
  - no secrets go anywhere public, or into prompts or logs.
- **Base:** the delivered CRM-002 v1.2 candidate on `forge/CRM-002`. The Orchestrator passes its commit as `KNOWN_COMMIT`.
- **Parent:** CRM-PBI-005, part 1.

## Outcome

`crm-migrate` can authenticate with the existing username and password credential through SOAP partner `login()`, **and with nothing else**. It uses the resulting session only through the CRM-002 read-only REST client. Every CRM-002 control stays in force:
- the allowlist;
- the origin rules;
- the metadata gate;
- the reconciled baseline;
- sealed storage;
- counts-only logs.

The adapter is explicitly temporary. It is removed or disabled once the PO's dedicated read-only identity exists, or before Summer '27, when Salesforce retires SOAP `login()`.

## Change

1. **`migrate/lib/crm_migrate/auth_soap.py`.**
   - It sends exactly one request type: `POST https://login.salesforce.com/services/Soap/u/<v>/`, with `SOAPAction: login` and a body generated from a fixed template. Username and password are XML-escaped. `<v>` comes from `CRM_SF_API_VERSION`, between 31.0 and 64.0, default `59.0`.
   - The login host is a constant. `test.salesforce.com` is allowed only through an explicit `--sandbox` flag.
   - The session can optionally be ended with `logout`: a fixed body with only the session header, sent to the origin `serverUrl` gives.
   - **No other SOAP operation can be expressed.** The allowlist in `SalesforceClient` and `HttpsTransport` gains exactly these two entries, matched on host, path pattern, `SOAPAction` and body root element.
   - **Response handling:**
     - parse with `xml.etree.ElementTree`;
     - refuse any `<!DOCTYPE` or `<!ENTITY` before parsing;
     - limit the response size;
     - on a fault, record only the `faultcode` and the first token of the `exceptionCode`. Never record the fault string.
   - **Origin binding:**
     - the origin is the scheme plus host of the `serverUrl` returned;
     - it must match `https://<label>.my.salesforce.com`;
     - it must **equal** the configured `CRM_SF_ORIGIN` exactly, otherwise the run aborts before any REST call;
     - the session id is used only as the Bearer token for that origin, and is held only in memory.
2. **Credential input: operator only, nothing persisted.**
   - New CLI option `--auth soap-legacy --credentials-stdin`. It reads one JSON object `{"username": …, "password": …}` from stdin, at most 4 KiB, then closes stdin. Values are never put into the environment, arguments, files, logs or exception messages.
   - **`scripts/migrate.sh --auth soap-legacy <mode>`**, run by root only:
     - parses **only** the two names `NIF_SRC_SALESFORCE_USER` and `NIF_SRC_SALESFORCE_PASS` from the existing ELT env file. The file path is a constant. The file is opened read-only, and its parsing is strict;
     - records the file's sha256 and mtime before and after, and **fails if either changes**, as evidence that the file was not modified;
     - pipes the JSON on stdin to `docker compose run -T --rm crm-migrate …`;
     - never copies the values into `/srv/CRM/runtime/migrate`;
     - the parser is a pure, unit-tested function (`hostcheck.parse_legacy_env`), tested against a synthetic fixture.
   - The CRM runtime env file holds only `CRM_SF_ORIGIN` and `CRM_SF_API_VERSION` for this mode.
3. **Write-capable identity waiver.**
   - `contract-check` still records every `createable`, `updateable` and `deletable` flag.
   - Under `--auth soap-legacy` **only**, the write-flag failure can be waived by `/srv/CRM/runtime/migrate/waiver.json` (root, `0600`). It must contain:
     - `{"authorisation": <a GitHub Issue #9 comment URL>, "identity": "legacy-eric", "expires": <ISO date, at most 30 days ahead>}`.
   - The file is validated by schema. An expired, missing or malformed waiver means a fail.
   - The manifest and the report state `identity: write-capable (waived: <url>)`, plus the counts of writable objects.
   - Client-credentials mode ignores the waiver completely.
   - Every other metadata-gate rule is unchanged: queryable and retrieveable, required fields, types and references.
4. **Fixtures and tests (`tests/migrate/`), in-process, with no sockets.**
   - `FakeSalesforceTransport` gains SOAP `login` and `logout` handling, a write-capable describe profile, and a sentinel password.
   - The tests cover:
     - **Refusal matrix:** every other SOAP operation (`query`, `create`, `update`, `delete`, `upsert`, `merge`, `undelete`, `emptyRecycleBin`, `setPassword`, `resetPassword`, and Apex or metadata SOAP) is refused before the transport is called, as are a wrong `SOAPAction`, a foreign login host, and a `serverUrl` whose origin differs from `CRM_SF_ORIGIN`.
     - **Parsing:** a DOCTYPE or ENTITY response is refused, and a fault is reduced to its code only.
     - **Secrets:** the sentinel password and session id never appear in stdout, stderr, logs, the manifest, exceptions or reports, in any mode, including on failures.
     - **Stdin:** the size limit and JSON shape; it never falls back to the environment.
     - **Waiver:** missing, expired, malformed and valid cases, and that client-credentials mode ignores it.
     - **Legacy env parser:** it reads only the two names; it handles quoting, `export` and duplicates (refuse); it ignores every other name.
     - **End to end:** the reconciled baseline under SOAP auth against the fake, with status `RECONCILED`.
   - Every new policy rule has a deliberately broken fixture.
5. **Docs.** `docs/MIGRATION.md` gains a § "Temporary legacy credential", covering:
   - the authority;
   - the risk: an identity that can write is constrained only by the allowlist;
   - the operator-only procedure and the waiver;
   - retirement: disable the adapter after extraction, or by Summer '27 at the latest.

## Scope

**Allowlist:**
- `migrate/**`, `tests/migrate/**`, `scripts/migrate.sh`, `deploy/migrate/**`
- `docs/MIGRATION.md`
- `.forge/CRM-002-S/**`

**Excluded:**
- any network or Salesforce access;
- reading or modifying the real ELT env file (only synthetic fixtures in tests);
- EspoCRM and `custom/`;
- any other WO's scope;
- new dependencies.

## Acceptance criteria (in the loop: synthetic, in-process)
1. **AC1:** all tests pass, with exact counts. Every new rule fails against its broken fixture.
2. **AC2:** only SOAP `login` and `logout`, built from the fixed templates, are ever passed to the transport. Every other SOAP operation and every mismatch is refused before the transport. The fake records zero write requests, SOAP or REST.
3. **AC3:** an origin mismatch between `serverUrl` and `CRM_SF_ORIGIN` aborts before any REST call.
4. **AC4:** the secret sentinels never appear in any output, file or exception.
5. **AC5:** the waiver rules behave as specified, and a write-capable identity without a valid waiver fails `contract-check` with no data query.
6. **AC6:** the legacy env parser extracts only the two names. `migrate.sh` passes `bash -n`, and its stdin pipeline is unit-testable through the pure functions.
7. **AC7:** every CRM-002 v1.2 test still passes, unchanged.

## Operator stage (after delivery, by the trusted operator only)

Each step is authorised by the PO override:
1. **O1:** synthetic self-test in the real container.
2. **L1:** metadata, with the waiver file created referencing the override.
3. **L2:** counts.
4. **L3:** full extraction, with handling per `docs/MIGRATION-DATA-HANDLING.md`.

Only the sanitised reconciliation is published.
