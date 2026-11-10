# CRM-003, round 4: Engineer correction (this is the FINAL engineer execution, 4 of 4)

- **Worktree:** `/srv/CRM/worktrees/CRM-003`. The expected HEAD is `e0795bf44d481ae58df759c811843792a7a43004`. Confirm it first. Do not modify `.forge/`. The scope allowlist is unchanged.
- **Time box:** the dispatcher stops you at 30 minutes, and there is no further round. Do the blocking item first, then the advisories in order. Return your final message by about 22 minutes.

## Blocking: acl-unlisted-scopes (DevSecOps, confirmed by the PL in the real image)
EspoCRM 10.0.12 has **no `aclStrictMode` setting**, either in the defaults or in the instance config, so it runs in non-strict mode: a scope a role leaves unset is **allowed**. The PL read this list of ACL-enabled scopes from the running image:
- **entity scopes** (`acl: true`): Account, Call, Campaign, Case, Contact, Currency, Document, DocumentFolder, Email, EmailTemplate, EmailTemplateCategory, KnowledgeBaseArticle, KnowledgeBaseCategory, Lead, Meeting, Opportunity, TargetList, TargetListCategory, Task, Team, Template, User;
- **boolean scopes**: Activities, Calendar, EmailAccountScope, ExternalAccount, GlobalStream, Import, OpenApi, Webhook, WorkingTimeCalendar.

**Required:**
1. Every role in `config/access/roles.json` gets an **explicit** entry for **every** scope above.
2. **Entity scopes Estate Research doesn't use** (Lead, Campaign, TargetList, TargetListCategory, KnowledgeBaseArticle, KnowledgeBaseCategory, Template, EmailTemplate, EmailTemplateCategory, Case) are set to `false` (no access) for all four roles. This keeps generic CRM features hidden, as the PO directs.
3. **Read-only for human roles:** Currency, Document, DocumentFolder, User and Team are read all, with no create, edit or delete.
4. **Boolean scopes for human roles:**
   - Activities, Calendar and GlobalStream: `true`;
   - WorkingTimeCalendar: `true` (read);
   - Import, Webhook, OpenApi, ExternalAccount and EmailAccountScope: `false`.
5. **`ER Import`:**
   - **no** `delete` anywhere;
   - unused entity scopes `false`;
   - every boolean scope `false` (EspoCRM's own Import tool isn't used, because the importer uses REST);
   - User and Team read all.
6. **Policy test:** take this list as the authoritative scope set (a constant noting it was "verified by PL in espocrm 10.0.12"). Every role must list every scope, an unlisted scope fails, and every boolean scope must be explicit. Add broken fixtures:
   - a role missing Lead;
   - Import with any delete;
   - Staff with Import `true`.

   Update `docs/ACCESS.md` §2.
7. **Note for later WOs:** CRM-004 will add a `ServiceType` scope. Make the policy's scope set easy to extend: one constant plus the rule.

## Advisories: fix if time allows, in this order
1. **apikey-loss-window:** open the key file (`O_EXCL`, `0600`) **before** creating the API user, the same way `PasswordFile.open()` does it.
2. **legacy-shared-not-sticky:** keep the legacy shared identity's `sfId` in `config/access/legacy_shared.json` (an empty list now; the operator fills it). `provision_users.py` always forces those users inactive, never issues them a password, and refuses `--reset` for them, whatever the flags or input say.
3. **empty-name-idempotency:** treat null and `""` as equal for `firstName` and `lastName` when comparing.
4. **hook-static-check-weak:** strengthen the static test so that `->count() * 0`, `if (false && …)` and an early `return;` before the throw all fail.

Run `python3 -m unittest discover -s tests/unit -v` and report exact counts and non-vacuity evidence. Finish in the Engineer final message format.
