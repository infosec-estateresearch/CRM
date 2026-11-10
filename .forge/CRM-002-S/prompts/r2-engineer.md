# CRM-002-S, round 2: Engineer correction

- **Worktree:** `/srv/CRM/worktrees/CRM-002-S`. The expected HEAD is `9f3b54a3e6463a819a0aafe9e228734a01342feb` (your round-1 candidate). Confirm it first. Do not modify `.forge/`. The WO and the scope allowlist are as in round 1.
- **Time box:** return by about 25 minutes. Do the blocking item first.

## Blocking (found independently by the Auditor and the Tester)
**soap-dtd-utf16-bypass.** `auth_soap.parse_xml` searches the raw bytes for `b"<!DOCTYPE"` and `b"<!ENTITY"`. A UTF-16 response, with or without a BOM, gets past that search, and expat then expands its internal entities. In one probe an entity-defined value became the session id.

The fix needs defence in depth:
1. Refuse any response body that isn't **strict UTF-8**:
   - decode it with `bytes.decode("utf-8", "strict")`;
   - refuse a BOM other than none or the UTF-8 BOM;
   - refuse an XML declaration whose `encoding` isn't `utf-8` (case-insensitive), or that is missing while the first bytes look like UTF-16 or UTF-32.
2. Search the **decoded** text for `<!DOCTYPE` and `<!ENTITY` (case-insensitive) and refuse on a match.
3. Parse with an `xml.etree.ElementTree.XMLParser` whose underlying expat parser **raises** from `StartDoctypeDeclHandler`, `EntityDeclHandler` and `ExternalEntityRefHandler`. Disable external entity resolution, so that a DTD is refused even if the text check is bypassed.
4. Tests: UTF-16LE, UTF-16BE (with and without BOM), UTF-32, a declared `encoding="utf-16"`, mixed case `<!doctype`, and DTD-in-UTF-8. Each must be refused **before** any element value is used. Add a non-vacuity mutation for each of the three layers.

## Advisories (fix all; they're small)
1. **logout-exception-escapes:**
   - `_logout` catches **any** exception, logs only `soap_logout ok=false code=<class name>`, and never changes the run's exit code;
   - `main` keeps its fixed-code-only stderr in every case;
   - also make `Request.__repr__` (and `__str__`) redact headers and body, showing only the method and the path without its query, so no session id or password can ever appear in a traceback;
   - add tests for both.
2. **Anchors:** replace every remaining `^…$` used with `.match` with `re.fullmatch` (or `\A…\Z`) in `errors`, `log`, `extract`, `manifest`, `hostcheck` and `contract`. Add a trailing-`\n` test for each validator that feeds a log, error or file name.
3. **fake-soap-write-classification:** the fake classifies SOAP requests by **body root element** as well as `SOAPAction`. Any SOAP body whose root operation isn't `login` or `logout` counts as a write attempt.
4. **legacy-env-shell-metachar:** refuse unquoted values that contain any of `;&|<>()$`\`` or whitespace. Quoted values must be closed properly, with no trailing characters.
5. **PL decision on the legacy env path:** the real path must not be committed.
   - `scripts/migrate.sh --auth soap-legacy` reads it from `CRM_LEGACY_ENV_FILE` in the **root-only runtime env** `/srv/CRM/runtime/migrate/env`, which is already guarded at root `0600`. Add the name to `deploy/migrate/env.legacy.example`.
   - `hostcheck` validates it: an absolute path; no symlinked component (`realpath` equals the path); a regular file; owned by root; not group- or world-writable.
   - It is still empty by default, so the command refuses ("not configured") until the operator sets it. Add tests.

Run `python3 -I -B -m unittest discover -s tests/migrate -t . -v` and `bash -n scripts/migrate.sh`, and report exact counts and non-vacuity evidence. Finish in the Engineer final message format.
