# Open WIP / Revenue (CRM-WIP-LINK-001)

An EspoCRM Account's detail page shows an **Open WIP / Revenue** button for users who may read Accounts. It opens `<wipBaseUrl>/crm/firm/<Account id>` in a new tab. The CRM holds no WIP data, makes no request to the WIP application and stores nothing.

## The `wipBaseUrl` runtime parameter

- **What:** the base address of the independent WIP application, as an absolute `http:` or `https:` URL with a host. A path prefix is allowed and one trailing `/` is ignored. User-info (`user:pass@`), a query (`?x=1`) and a fragment (`#x`) are refused.
- **Where:** EspoCRM's runtime configuration of the target (`data/config.php` in the runtime `data/` directory, key `wipBaseUrl`), never in this repository and never in the env file. Set it per environment with a value such as `<scheme>://<wip-host>:<port>` (placeholder only), then reload the CRM page in the browser.
- **If it is missing or invalid** the button shows the warning "The WIP link is not configured." and nothing opens. There is no default address.
- The record id must be letters and digits only; otherwise a warning is shown and nothing opens.

## Delivery

`scripts/deploy_custom.sh dev` delivers `custom/Espo/Custom` as before and also `client/custom/src` (the handler `handlers/account-open-wip.js`):

```
scripts/deploy_custom.sh dev
```

- Only the runtime `client/custom/src` is managed. `client/custom/modules` and every other entry of `client/custom` are never read, written or listed.
- The source `client/custom/src` must be a real directory with no symlink inside. The runtime `client/` must be a real directory owned by the invoking user and not group- or world-writable.
- The new tree is staged as `.src.deploy-<UTC>` beside `src` and swapped in by rename. The previous `src` and `custom/Espo/Custom` are kept as `.src.old-<UTC>` and `.Custom.old-<UTC>` until `clear-cache`, `rebuild` and `update-app-timestamp` have succeeded.
- After `rebuild` the script runs `update-app-timestamp` and checks that the stored `appTimestamp` strictly increased (one retry after one second), so browsers fetch the new code.
- The marker `client/custom/.src-managed-by-git` is written after a successful install.
- If crm-app was not running, it stays stopped, the cache steps are skipped and the timestamp is not advanced; run the script again once the stack is up.

## Rollback

Check out the base (or any commit without `client/custom/src`) and run `scripts/deploy_custom.sh dev`. The runtime `src` and the marker are removed, but only if the marker is present. If `src` exists without the marker it is left untouched and the script prints a notice. The original Account page returns.

## Failure and restore

If a step after the stack stopped fails (or the script is interrupted), both trees are put back as they were, the new trees are kept as `.Custom.failed-<UTC>` and `.src.failed-<UTC>`, stderr shows `FAILED STEP: <step>`, and the exit code is the step's:

| Code | Step |
|---|---|
| 20 | stage-custom |
| 21 | stage-client |
| 22 | swap-custom |
| 23 | swap-client |
| 24 | up |
| 25 | clear-cache |
| 26 | rebuild |
| 27 | update-app-timestamp (also: the stored value did not advance) |
| 28 | marker |
| 29 | interrupted |
| 30 | cleanup (new trees installed; old trees remain as `.old-<UTC>`) |

If crm-app was running it is started again and the cache steps re-run (`RECOVERED`); if that fails, or the trees cannot all be put back, `RECOVERY FAILED` is printed and the stack stays stopped. Working trees of earlier failed runs are listed on stderr as `LEFTOVER: <name>` and never touched; remove them by hand after inspection.

## Verification

1. After the deploy, open an Account: the button is present. Click it: a new tab opens at `<wipBaseUrl>/crm/firm/<Account id>`.
2. Set `wipBaseUrl` to a value with a scheme other than `http:`/`https:`, with user-info, query or fragment, or empty: the warning appears and nothing opens.
3. Stop the WIP application: the Account page and its panels still work.
4. Deploy the base: the button, `client/custom/src` and the marker are gone; `client/custom/modules` is unchanged.
5. `scripts/backup.sh dev` archives `client/custom` including the handler (`client-custom.tar.gz`).
