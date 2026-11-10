# CRM-006R, round 4: Engineer correction (last permitted engineer execution)

- **Worktree:** `/srv/CRM/worktrees/CRM-006R`. The expected HEAD is `b683d1a4bc9076de64d6385f9f45d330d808ba85` (your committed candidate); confirm it first. Do not modify `.forge/`.
- **This is the last engineer execution.** Make exact, verified changes, and report `STATUS: completed`.
- **Time box:** return by about 25 minutes.

## Blocking 1: the synthetic marker (Auditor and Tester)
The real selftest output was checked by the PL on DOCKER1. `<id>-selftest/manifest.json` has `mode: "selftest"` and no contract. The synthetic snapshots are `<id>-selftest/run-1/` and `<id>-selftest/run-2/`, each with `manifest.json` `mode: "extract"`, `origin_kind: "production"` and a contract.
- **Synthetic means exactly this:** the snapshot path is `<SNAPSHOT_BASE>/<name>-selftest/run-1` or `/run-2`; the parent `<name>-selftest/manifest.json` exists and verifies, and has `mode == "selftest"`; and the parent is sealed.
- **`dev` loads only snapshots that are synthetic** by that rule.
- **`beta` loads only a `<SNAPSHOT_BASE>/<name>-extract` directory**, in the legacy or client-credentials layout. It refuses any path under a `*-selftest` directory. As defence in depth, it also refuses (`synthetic_content_in_beta`) if any Account `Name` in the snapshot contains `SENTINEL-7f3a`, the marker on every synthetic record.
- Remove the `mode == "selftest"` snapshot rule. Update `load.sh` to match: for dev, the snapshot argument is the `run-N` path, and its sealed/canonical checks apply to the parent selftest directory. Add tests.

## Blocking 2: second-run writes (Auditor; Tester and DevSecOps advisories)
Facts verified by the PL live on crm-dev (synthetic probes, deleted afterwards):
- **Phones.** `phoneNumberData` reads back with extra keys: `[{"phoneNumber", "type", "primary", "optOut": false, "invalid": false}]`.
  - Compare only `(phoneNumber, type, primary)`, as an order-insensitive set.
  - With the CRM setting `phoneNumberInternational = true` (the default), UK national formats such as `01632 960000` are **refused** with `400 phoneNumber valid`, and `+44…` is normalised to `+441632960000`.
  - With `phoneNumberInternational = false`, numbers are stored **verbatim**, and only junk such as `n/a` is refused. CRM-007 sets it to `false` on beta, and `docs/IMPORT.md` must state this as an operator precondition.
  - If a create or update still fails with `400` on the field `phoneNumber`, retry **once without `phoneNumberData`** and record `phone_rejected`. The record is kept and the phone isn't invented.
- **Email:**
  - `from` must be the **bare address**. `"Name <addr>"` in `from` is silently dropped, so `from` is null. The display name goes in `fromString` as `"FromName <FromAddress>"`, or just the address when there is no name.
  - **`messageId` cannot be set through the API.** The server always replaces it with `dummy:<id>`. Don't send it and don't compare it. Count the Salesforce `MessageIdentifier` as `not_mapped`, or document it; `sfThreadIdentifier` stays.
  - List reads return `to` and `cc` as `;`-joined strings, as sent. `dateSent` comes back as `YYYY-MM-DD HH:MM:SS` UTC.
- **Dates and numbers.** Normalise every datetime you send to `YYYY-MM-DD HH:MM:SS` UTC, and every date to `YYYY-MM-DD`, so the comparison is exact. Compare `amount` numerically.
- **Fake EspoCRM.** Make it reproduce all of these behaviours: extra phone keys, phone refusal under the international setting, `from` dropped when it has a display name, `messageId` replaced. Then prove that a second run makes **zero writes** against that fake.

## Blocking 3: manufactured values (Auditor and DevSecOps)
- **Call direction.** Core `Call.direction` defaults to `Outbound` (verified). For a blank `CallType`, **don't send direction**, and record `call_direction_unknown`, counted, with the ids in exceptions. Document that EspoCRM shows its core default.
  - Remove `callDirectionDefault` from `mapping.json`.
  - Map `CallType` `Inbound` and `Outbound` exactly.
- **Required dates.** Core `Call.dateStart` and `Meeting.dateStart` are `required: true` (verified). When `CompletedDateTime` is null, using `ActivityDate`, then `CreatedDate`, is allowed **only with** an exception code per record: `date_start_from_activity_date` or `date_start_from_created`. Email `dateSent` is not required: if it can't be derived, leave it null; don't fall back to the created date.

## Scope finding (Auditor, blocking): PL decision
The changes to `tests/unit/test_access_policy.py`, the `tests/unit/fixtures/access_bad_*.json` files (each flips only ER Import `Import`) and the new `overrides_bad_opportunity_role_required.json` are **authorised retroactively** under "the related tests". They follow mechanically from the authorised `roles.json` and `opportunityRole` changes, and they are recorded in the delivery record. **Make no further changes outside the allowlist.**

## Advisories: fix these, they are cheap
- **`load.sh` API key:** pass it only through the environment. Export it, then use `env -i` with `CRM_LOAD_API_KEY` by name, or read it in Python from the root-only `load.env`. It must never appear in argv.
- **`load.sh` output dir:** refuse anything under `$SNAPSHOT_BASE`.
- **Username collision:** two Salesforce users with the same local part both become `user_not_exportable`.
- **Non-scalar values:** a dict or list in any mapped field gives a coded `LoadError` (`value_shape`) for that record, which becomes an exception. Never let it surface as a traceback.
- **Email contacts:** document that EspoCRM associates contacts with archived email through the addresses. No contact links are written.
- **Soft-deleted parent:** don't link a current record to a parent that is soft-deleted in the snapshot (`parent_soft_deleted_in_sf`, an exception).
- **D8:** the empty pattern table stays (PL decision). The patterns come from a counts-only analysis after the load. Document it.
- Rename `HttpsTransport` to `LoopbackHttpTransport`.

Run both suites, report exact counts, and give mutation evidence for each blocking fix. Finish in the Engineer final message format.
