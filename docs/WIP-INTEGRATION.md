# WIP integration: the Account WIP panel (CRM-WIP-INT-001R2)

The Account detail page can show a firm's current WIP cases, read live from the
existing WIP application's read-only JSON API. The CRM stores nothing from WIP,
holds no WIP column and sends nothing to WIP except one authenticated `GET`.
The contract is `docs/architecture/crm-wip-integration-amendment.md` section 5.

## Configuration

Two optional names in the runtime env file (`deploy/env.example` lists them with
no value; real values never go into Git):

| Name | Meaning |
|---|---|
| `CRM_WIP_API_URL` | Base URL of the WIP API, `http` or `https`, no credentials, query or fragment |
| `CRM_WIP_API_TOKEN` | Bearer token of the WIP API |

`deploy/compose.json` passes them to `crm-app` as `${VAR:-}`, so an environment
without them starts unchanged and the panel shows "WIP unavailable".
After editing the env file run `scripts/up.sh <env>` to recreate `crm-app`, then
`scripts/deploy_custom.sh <env>` and `scripts/provision_access.py`.

## Who sees it

Only a user holding the `WipSummary` scope (Admin always). `config/access/roles.json`
sets it `false` in every role; granting it to a role is a product decision (PO-W1)
and is not made here. A user without it gets no WIP field, the panel stays hidden
and the server makes no outbound request, whatever the Account holds.

## Statuses

| Status | When |
|---|---|
| WIP data available | valid reply with cases |
| No current WIP cases | firm is in WIP and has none |
| Firm not found in WIP | WIP answered 404 |
| No Salesforce ID on this Account | `sfId` empty or not 18 letters and digits; nothing is sent |
| WIP unavailable | anything else: not configured, timeout (2 s connect, 3 s total), refusal, 401, 409, 422, 5xx, redirect, reply over 256 KiB, bad JSON or shape |

Failures never break the Account page. The log holds the failure class and HTTP
status only, never the token, URL, `sfId` or body.

## Rollback

Remove the two lines from the runtime env file and recreate `crm-app`: the panel
then reads "WIP unavailable" for authorised users. To remove the feature,
revert the change in Git and run `scripts/deploy_custom.sh <env>`. No data
migration is needed because nothing is stored.
