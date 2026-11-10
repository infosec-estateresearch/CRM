# CRM-002-S, round 4: Engineer correction (final permitted execution)

- **Worktree:** `/srv/CRM/worktrees/CRM-002-S`. The expected HEAD is `9d26c40f6b25acb456c4e9db1e4bf63c53442c77`; confirm it first. Do not modify `.forge/`, and don't touch the UTF-16/DTD layers or the logout template code.
- **This is the last engineer execution.** Make small, exact changes, and verify each one.
- **Time box:** return by about 20 minutes.

## Blocking (Auditor): `stdin-credential-exception-context`
In `cli.read_stdin_credentials`, a UTF-8 or JSON failure raises `ConfigError ... from None` inside the `except` block. The raw stdin, password included, stays reachable through `e.__context__` (`.object` / `.doc`).
- **Fix:** record a flag in the `except` block, and raise **after** it, as the lone-surrogate branch already does. Every `ConfigError` raised from this function must then have `__cause__ is None` **and** `__context__ is None`.
- **Check the other places** that parse secret-bearing input the same way: `hostcheck.parse_legacy_env` / its readers, `waiver.py`, and the SOAP login response parse that holds the session id. Fix any `raise` inside an `except` there in the same way.
- **Tests:** for each such path, with a sentinel password or session id, assert that `__context__` and `__cause__` are None, and that the sentinel is absent from `repr`, `str` and `traceback.format_exception` of the raised error.

## Advisories: fix them all
1. **docs** (`docs/MIGRATION.md` ~241). Describe the fixed sets: `FAULTCODES` gives "unrecognised" for anything else, and `SF_ERROR_CODES` gives "UNKNOWN". Also note that `CountsLog` re-checks membership.
2. **log.py.** `CountsLog` renders `sf_error` only if it is in `errors.SF_ERROR_CODES`; otherwise it renders "UNKNOWN". Keep the existing "FINE" test working: add "FINE" to the set only if it is a real code that the tool uses, otherwise adjust that test. Add a test that logging `sf_error="SENTINEL_7F3A"` renders UNKNOWN.
3. **The env parser refuses the whole file** in either case below. The error gives only the line number.
   - Any non-comment line ending with an unescaped backslash, outside single quotes.
   - Any CR character.

   Add broken fixtures, including a continuation on an unrelated line before the PASS line.
4. **stdin limit.** Add a test with the literal boundary: exactly 4096 bytes of **valid** JSON is accepted, and 4097 bytes of valid JSON (padded with whitespace) is refused with the size message. Also assert `cli.MAX_STDIN_BYTES == 4096`.
5. **`waiver-hides-user-finding` (PL decision).** Under a valid identity waiver, `User.updateable` may still be waived for the **gate** decision. But the finding "User updateable: L1 finding for Architect decision, not waived" **must still be appended to `findings`**, so that it reaches the report. Add a test.

Run `python3 -I -B -m unittest discover -s tests/migrate -t . -v`. Report exact counts and give mutation evidence for each change. Finish in the Engineer final message format.
