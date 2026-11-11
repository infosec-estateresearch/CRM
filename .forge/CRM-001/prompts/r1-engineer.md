# CRM-001, round 1: Engineer

- **Work Order:** `work-orders/CRM-001.md` v1.3, in the worktree at the approved commit `096748c8b4dfdab22070e1e802c6614fdf54465c`. Its SHA-256 is `6f4df2d8cd282ea69b0a8e58cd91a57cb716648c0bd669b46573b02516fc4cdc`.
- **Approval:** Architect exact-version approval is recorded on infosec-estateresearch/CRM Issue `#2`.
- **Worktree:** `/srv/CRM/worktrees/CRM-001`. The expected HEAD is `096748c8b4dfdab22070e1e802c6614fdf54465c`. Confirm it first (role rule 2).

## Task
Implement items 1–7 of the WO's **Change** section exactly. Stay within its **Scope allowlist** and respect its **Excluded** list. Read these first:
- `work-orders/CRM-001.md`
- `docs/BUILD.md`
- `DECISIONS.md` (CRM-D010, D012, D017, D018)
- `security/EXTERNAL_CODE_REGISTER.yaml`
- `README.md`

## Constraints from the WO
- You have no network, no Docker and no browser.
- Do not download anything. EspoCRM conventions come from your own knowledge; record that limitation in your NOTES.
- Use only the Python standard library. The only images are the two digests in the register.
- Do not edit EspoCRM core. Customisation lives only under `custom/Espo/Custom/`.
- `deploy/env.example` holds variable names only. Put no secret values anywhere.
- Compose project `crm-dev`: services `crm-app`, `crm-daemon`, `crm-db`; network `crm-net`. There is no `container_name`. `crm-db` publishes no ports. `crm-app` binds `127.0.0.1:8180` only. No external networks or volumes.
- Fallback rule: if AC3–AC7 need more than about 300 lines of ER code, report it under NOTES.

## Tests you must run and report
- `python3 -m unittest discover -s tests/unit -v`, with exact counts.
- `bash -n` on every script under `scripts/`.
- Non-vacuity: for each Compose policy rule, show that the test fails against a deliberately broken fixture. Put the fixtures under `tests/unit/fixtures/`.

Finish in the Engineer final message format.
