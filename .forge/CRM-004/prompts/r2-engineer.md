# CRM-004, round 2: Engineer correction

- **Worktree:** `/srv/CRM/worktrees/CRM-004`. The expected HEAD is `9317bef82771e9797087d3e5b0ab1a460ffc9ff8`. Confirm it first. Do not modify `.forge/`. The WO and the round-1 scope clarification still apply, with the additions below.
- **Time box:** return by about 20 minutes.

## Blocking, raised by the PL (verified in the EspoCRM 10.0.12 image)
**Core Opportunity `amount` and `closeDate` are `required: true`** (`name` too; `account` and `probability` are not). This breaks:
- the quick create (R8, AC3), which doesn't include them;
- the import: in Salesforce only 2–68% of enquiries carry a fee, depending on stage, and the importer must never invent one.

Set `"required": false` on `amount` and `closeDate` in the custom Opportunity entityDefs. Keep them audited. Add a policy rule and a broken fixture: amount and closeDate must not be required. Also document this in `docs/ENQUIRIES.md`.

## PL decisions on the review findings
1. **contact-role-options (Auditor, blocking): closed by PL decision.** The Salesforce OpportunityContactRole picklist values are only known after L1, when the describe picklist is read. Inventing them is forbidden. So the deferral **is accepted**:
   - roles are stored raw in the relation's `role` column;
   - the picklist options are added after L1 from the real describe values, in a later change;
   - keep the test asserting that Contact is unchanged.

   Make `docs/ENQUIRIES.md` say exactly this.
2. **ServiceType ER Import writes: accepted.** The importer must create the 60+ ServiceType records from the snapshot. Note the deviation from "only admins" in `docs/ENQUIRIES.md`: the import user only, no delete, and deactivated after the load.
3. **API exemption: narrow it** to the named import user. The hook exempts only when `$this->user->getType() === User::TYPE_API` **and** `$this->user->getUserName() === 'er-import'`. Use the same userName as in `config/access/api_users.json`; verify it there. Update the static rule and the fixture.
4. **opp-sfid-read-untested:** extend `rule_sf_id_admin_only`, or add a rule, so that a human role with `read` on `Opportunity.sfId` fails. Add a fixture.
5. **enquiry-label-elsewhere: authorised.** Add `custom/Espo/Custom/Resources/i18n/en_US/Account.json` and `Contact.json` overrides **only** for `links.opportunities` = "Enquiries", plus any matching `fields.opportunities` label. Merge into the CRM-003 Account i18n if it exists; don't replace it.
6. **stage-map-merge and admin-legacy-edit: accepted as documented limits.** EspoCRM merges metadata recursively, and admins bypass role field ACL. Add one sentence for each to `docs/ENQUIRIES.md`.

Run `python3 -m unittest discover -s tests/unit -v` and report exact counts and non-vacuity evidence for the new rules. Finish in the Engineer final message format.
