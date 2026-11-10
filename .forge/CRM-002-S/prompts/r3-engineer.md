# CRM-002-S, round 3: Engineer correction

- **Worktree:** `/srv/CRM/worktrees/CRM-002-S`. The expected HEAD is `525b7a85336bbd0b641b0419c899e791abf791d6`. Confirm it first. Do not modify `.forge/`. The WO and the scope allowlist are unchanged.
- In round 2 the UTF-16/DTD fix was verified by all three reviewers. Tester and DevSecOps PASS. **Don't touch it** except where an item below needs you to.
- **Time box:** return by about 20 minutes. Use small, targeted changes.

## Blocking (Auditor): logout-template-untested
Removing the "logout body must be byte-identical to its fixed template" check (`if expected != body: raise RefusedRequest…`) leaves the suite green. Add tests that fail without it:
- a logout with an altered body: an extra element, a different session-header shape, or a different operation inside a logout envelope;
- a logout whose `SOAPAction` is `logout` but whose body is any non-template variant.

Show the mutation result: rule removed means the suite fails.

## Advisories (fix all)
1. **faultcode-echo:** never print a server-supplied `faultcode` verbatim.
   - Map it to a **fixed** vocabulary: `sf:INVALID_LOGIN`, `sf:LOGIN_MUST_USE_SECURITY_TOKEN`, `sf:INVALID_SESSION_ID`, `sf:API_DISABLED_FOR_ORG`, `sf:REQUEST_LIMIT_EXCEEDED`, `sf:PASSWORD_LOCKOUT`, `sf:INVALID_OPERATION_WITH_EXPIRED_PASSWORD`, `sf:LOGIN_RATE_EXCEEDED`, `soapenv:Client`, `soapenv:Server`.
   - Anything else prints as `faultcode=unrecognised`.
   - Apply the same rule to the REST `errorCode` echo, if it isn't already fixed-vocabulary.
   - Add tests, including a password-shaped faultcode that must not appear.
2. **stdin-size-check-untested:** add a **valid-JSON** fixture padded past 4096 bytes, which must be refused by the size check.
3. **env-fallback-test-narrow:** add a test that patches `os.environ` with `NIF_SRC_SALESFORCE_*` and `CRM_SF_*` values, gives empty stdin, and asserts a refusal with `credentials_stdin`.
4. **legacy-env-multiline-quote:** refuse the whole file if any line opens a quote it doesn't close on the same line. This is ambiguous, so it fails closed. Add a test.
5. **surrogate-credential:** validate that username and password encode to UTF-8 (`strict`) in `read_stdin_credentials`. Refuse them otherwise with a clean `ConfigError` (`credentials_invalid`), with no exception that carries the value. Add a test.

Run `python3 -I -B -m unittest discover -s tests/migrate -t . -v` and report exact counts and the non-vacuity result for each new test. Finish in the Engineer final message format.
