# Salesforce administrator setup for the read-only CRM migration

- **For:** Matt, as Salesforce administrator and Product Owner.
- **Status:** v1.1, 2026-11-10. This goes with CRM-002 v1.2. v1.1 adds § What already exists, from the verified ERiC integration check.
- **Purpose:** give the `crm-migrate` extractor on DOCKER1 **read-only API access**, so it can build a reconciled copy of the Salesforce data for the new CRM.

There are **no manual exports** in this process: no Data Loader, no Data Export Service, no reports to CSV. You set up access once. After that, every extraction is run by the tool, and only when you have authorised that stage on Issue #9.

> **What this setup does not do.** It authorises nothing on its own. The tool refuses to run unless the WO is approved and you have recorded authorisation for L1, L2 or L3 on Issue #9. You can switch everything off at any time with step 7.

## What already exists, and why two things are still new

This was verified on 2026-11-10 with one authorised login test and one metadata request. No records were read.

| Already in place | Reused for CRM-002? |
|---|---|
| The Salesforce org and its My Domain | **Yes.** It's the only origin the tool talks to. |
| Your administrator login | **Yes.** Use it for the steps below. Never share it. |
| ERiC's Salesforce login: username and password, using SOAP `login()` | **No.** It can create, edit and delete on 457 objects, including users and profiles, so it is effectively an administrator. It also uses the login method Salesforce retires in Summer '27. CRM-002 must not hold an unrestricted credential. |
| ERiC's Connected App (key stored on the host, never actually used) | **No.** Leave it alone. ERiC still depends on its configuration, and coupling CRM-002 to it would mean revoking one revokes both. |

**New (2 items):**
1. One read-only **integration user**, on the free Salesforce Integration licence.
2. One **External Client App** for CRM-002.

The read-only user is designed to be **reused later** by ERiC and WIP when they move off SOAP `login()`, so the total number of identities stays small. That ERiC/WIP move is separate work, with its own migration and rollback plan, and nothing changes for them now.

**Optional, read-only check of the existing app (5 minutes, helps ERiC's later migration):**
1. Go to Setup → App Manager.
2. Find the Connected App whose consumer key matches ERiC's. Rogue can show you the last four characters on DOCKER1 if you need to identify it.
3. Note, without changing anything:
   - its name;
   - whether "Enable Client Credentials Flow" or "Allow OAuth Username-Password Flows" is ticked;
   - which user, if any, is set as Run As.

Report those to Rogue. Never send the secret.

## 0. Before you start (10 minutes)

| Check | Where | Why |
|---|---|---|
| Org edition is Enterprise, Unlimited or Performance | Setup → Company Information | API access, and the free integration licences |
| **Salesforce Integration** licences are available (usually 5 are included) | Setup → Company Information → User Licenses | An API-only user that can't log in through the UI |
| Your My Domain hostname, `<mydomain>.my.salesforce.com` | Setup → My Domain | It's the only origin the tool will talk to. It's not a secret, but it goes only into the host env file, never into GitHub. |
| DOCKER1's public egress IP | Ask Rogue on the host, or check your firewall/HAProxy | Used for the IP restriction in step 2 |

**If no Salesforce Integration licence is available,** use a standard Salesforce licence with a cloned **read-only** profile instead. Tell Rogue, because L1 will then check more flags.

## 1. Create a permission set: "ER CRM Migration – Read Only"

Go to Setup → Permission Sets → New.
- **License:** **Salesforce API Integration**. This makes the set assignable to the integration user.
- **System permissions:** tick **only**:
  - **API Enabled**;
  - **View Setup and Configuration**, needed to read Profile and Role names;
  - **View All Users**, only needed if your user sharing is private.

  Leave everything else unticked. In particular, **don't** grant:
  - Modify All Data or Modify Metadata;
  - Manage Users;
  - Customize Application;
  - Author Apex;
  - Bulk API Hard Delete;
  - Transfer Record;
  - Edit Tasks or Edit Events;
  - Send Email;
  - Import permissions;
  - any "Manage …" permission.
- **Object settings:** for each object below, tick **Read** and **View All**. Do **not** tick Create, Edit, Delete or Modify All.

  | Object | Read | View All | Why View All |
  |---|:-:|:-:|---|
  | Accounts | ✔ | ✔ | So no firm is hidden by sharing rules |
  | Contacts | ✔ | ✔ | Same reason |
  | Opportunities | ✔ | ✔ | Same reason. Contact roles follow Opportunity access. |

  Tasks, Events, Email Messages and Notes have no separate object permission. Their visibility follows the parent records above. The tool checks whether that's enough at L1 and L2 (step 6), so you don't need to guess now.
- **Field permissions:** for Account, Contact, Opportunity, Task, Event and Email Message, tick **Read Access** (not Edit Access) on every field listed in `migrate/contract/salesforce-fields.json`. The eight custom fields matter most:
  - Account: `TLP__c`, `Interested_in_integration__c`, `Bankruptcy_Special_Rate__c`;
  - Opportunity: `Loss_Reason__c`, `Paid_geneology_enquiry__c`, `Opportunity_Service__c`, `Post_code__c`, `Key_Information__c`.

  If you miss one, the tool doesn't guess. L1 reports it by name and you add it.

**Possible fallback:** if L2 shows activities, emails or private notes missing because of sharing, the remedy is to add **View All Data** to this permission set. That's still read-only in practice, because the set has no edit or delete rights. Only do this with your explicit approval recorded on #9. **Private notes** (`IsPrivate`) are only visible to the owner or to View All Data.

## 2. Create the integration user

Go to Setup → Users → New User.
- **Name:** "ER CRM Migration (read-only)".
- **Email:** your own admin mailbox. It's used only for verification and notices.
- **Username:** something unique, for example `crm-migration@<yourdomain>.integration`.
- **User License:** **Salesforce Integration**.
- **Profile:** **Minimum Access – API Only Integrations**.
- After saving:
  - Permission Set License Assignments → add **Salesforce API Integration**;
  - Permission Set Assignments → add **ER CRM Migration – Read Only**.
- **Recommended:** limit logins to DOCKER1's egress IP. Use the profile's Login IP Ranges, or the app policy in step 3.
- **Never** give this user a password or log in as it. The OAuth flow doesn't need one.

## 3. Create the External Client App, using the client-credentials flow

Use an **External Client App**, which is Salesforce's current model. Only reuse an existing Connected App if creating an External Client App isn't possible. If so, tell Rogue, and L1 records it as the verified fallback. **Don't** reuse ERiC's existing app or credentials (see § What already exists).

Go to Setup → **External Client App Manager** → **New External Client App**.
1. **Basic information:**
   - Name: "ER CRM Migration (read-only)";
   - Contact email: yours;
   - Distribution state: **Local**.
2. **API (Enable OAuth settings):** on.
   - **Callback URL:** the form requires one, but this flow never uses it. Enter `https://localhost/unused`.
   - **OAuth scopes:** **only** "Manage user data via APIs (`api`)". Don't add `full`, `refresh_token`, `web` or anything else.
   - **Flow enablement:** tick **Enable Client Credentials Flow** only. Leave the authorisation code, device, JWT bearer and token exchange flows off.
   - **Security:** keep "Require secret for Web Server Flow" and "Require secret for Refresh Token Flow" at their defaults. They aren't used.
3. Save, then open the **Policies** tab and Edit:
   - **OAuth Policies → Client Credentials Flow:** set **Run As** to the integration user from step 2.
   - **Plugin policies / Permitted Users:** "Admin approved users are pre-authorized", then select the permission set **ER CRM Migration – Read Only**.
   - **IP Relaxation:** "Enforce IP restrictions", provided step 2 set DOCKER1's IP range.
   - **Session timeout:** 15 minutes. The tool asks for a new token for each run.
4. Wait about 10 minutes for the settings to take effect.

## 4. Hand the credentials to the host securely

On the app, open **Settings → OAuth Settings → Consumer Key and Secret**. Salesforce sends a verification code to your email first.

**The rule:** the key and secret go **directly from your browser into DOCKER1**, typed by you. Never put them in chat (Rogue or ChatGPT), email, GitHub, Teams, tickets or notes.

On DOCKER1, as root:

```
sudo /srv/CRM/main/scripts/migrate.sh credentials
```

This exists once CRM-002 is delivered and O1 has passed. It asks, without echoing, for:
- the My Domain origin, `https://<mydomain>.my.salesforce.com`;
- the consumer key;
- the consumer secret.

It writes `/srv/CRM/runtime/migrate/env` as root-only (`0600`). It never prints the values.

Rogue checks only that the file exists, its permissions, and that the variable **names** are present. Rogue never reads or displays the values.

**Rotation and revocation:**
- Rotate the secret after the beta load, and at any time you suspect exposure. Use the app's Consumer Key and Secret → **Generate new** option, then re-run `migrate.sh credentials`.
- To revoke immediately, deactivate the integration user, or turn off the client-credentials flow on the app.

## 5. What happens at each stage, and what you authorise

Each stage needs its own comment from you on **Issue #9**, for example "PO authorises CRM-002 L1".

| Stage | What the tool reads | What it does **not** read | Output | Your authorisation must say |
|---|---|---|---|---|
| **L1 – metadata** | Object and field descriptions, and the integration user's create/update/delete flags | No records at all | Pass/fail list of objects and fields; confirmation that **nothing is writable**; app type | "L1 authorised" |
| **L2 – counts** | `COUNT()` per object, both current and including recycle-bin and archived records | No record contents | Counts per object, compared with the inventory | "L2 authorised" |
| **L3 – records** | The contract fields only, for the authorised objects and date range | HTML bodies, Bcc, attachments, anything outside the contract | A sealed snapshot on DOCKER1 (root-only) and a counts-only reconciliation with a completeness status | The objects, date range, purpose, storage location (`/srv/CRM/runtime/migrate/snapshots`), retention period and disposal method |

**API usage is small.** Roughly 150k records across all objects, at up to 2,000 per page, plus the verification passes, comes to well under 1,000 API calls per full run. Typical daily allowances are in the tens of thousands.

**Completeness:** each L3 run reports one of these statuses:
- **RECONCILED:** every count and id matched.
- **RECONCILED_WITH_DRIFT:** staff were still editing records during the run. It needs your acceptance, or a follow-up delta run.
- **INCOMPLETE:** never used.

A record that disappears between runs is **never assumed deleted** unless Salesforce gives evidence of the deletion.

## 6. If L1 or L2 finds a problem

| Finding | Typical cause | Fix |
|---|---|---|
| A field is "missing" | Field-level security not granted | Step 1, field permissions: add Read Access |
| An object is "createable", "updateable" or "deletable" | Extra permission on the profile or set | Remove it. If `User` shows updateable (users can edit their own record), Rogue reports it for an Architect decision. |
| L2 counts are well below the inventory | Sharing hides records | Check View All on the object. Otherwise consider the View All Data fallback in step 1 (needs your approval on #9). |
| Token refused | App not yet active, flow not enabled, or Run As user not set | Wait 10 minutes, then re-check step 3 |

## 7. Switching it off

Do this when the migration is complete, or at any time:
1. Deactivate the integration user.
2. Delete or disable the External Client App.
3. Rogue removes `/srv/CRM/runtime/migrate/env`, and disposes of snapshots under the retention terms you set at L3.
