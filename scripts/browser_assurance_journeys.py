"""Journey steps J1 to J6 (CRM-BROWSER-001). Runs INSIDE the runner container only (never on
the host), driven by browser_assurance_runner.py. A step function takes a context `c` and
returns (observed, entity, record id, stored data it expects to read back by API).
`observed` is "performed", "not offered", "refused" (or "timeout"); the expectation is never
derived here: it comes from tests/browser/expectations.json.

Platform facts relied on (reference /srv/CRM/wo/CRM-BROWSER-001/reference/espocrm/client):
  res/templates/record/panel-actions.tpl (panel `.dropdown-toggle`, `data-action`);
  res/templates/fields/link-multiple/edit.tpl (input.main-element, data-action=clearLink);
  lib/original/espo-main.js: views/record/list (massActionList remove, merge, massUpdate),
  views/record/merge (button[data-action=merge]), relationship panel actions selectRelated,
  removeRelated, unlinkRelated, modal button[data-name=select]; the merge request goes to
  `Action`; access denied is shown by controller error403 after Espo.Exceptions.AccessDenied.
Selectors confirmed at runtime by operator gate 2 are noted in docs/BUILD.md."""

import re
import time

STEP_MS = 20000
REFUSAL = "#notification.alert-danger, .field.has-error, .modal .alert-danger"
DENIED = "You don't have access to this area"


class Ctx:
    def __init__(self, page, base, tag, kind, user, admin):
        self.page, self.base, self.tag, self.kind, self.user, self.admin = page, base, tag, kind, user, admin
        self.fx = {}  # fixtures and records of this account kind


# --- helpers -------------------------------------------------------------------------

def denied(page):
    try:
        return DENIED in page.inner_text("body")
    except Exception:
        return False


def goto(c, route):
    c.page.goto(f"{c.base}/#{route}", wait_until="load")


def open_screen(c, route, ready):
    """'ready' when the awaited marker of THIS screen is there; 'denied' when the access-denied
    screen shows. The runner starts every step from a blank page, so no earlier screen can match."""
    goto(c, route)
    deadline = time.time() + STEP_MS / 1000
    while time.time() < deadline:
        if c.page.query_selector(ready):
            return "ready"
        if denied(c.page):
            return "denied"
        c.page.wait_for_timeout(250)
    raise RuntimeError(f"neither {ready} nor the access-denied screen appeared on #{route}")


def offered(page, selector):
    """True when at least one VISIBLE element matches (hidden duplicates of menu items exist)."""
    return page.locator(f"{selector}:visible").count() > 0


def click_visible(page, selector):
    page.locator(f"{selector}:visible").first.click(timeout=STEP_MS)


def choose(page, scope, text):
    page.fill(f"{scope} input.main-element, {scope} input[type=text]", text)
    page.click(".autocomplete-suggestion", timeout=STEP_MS)


def outcome(page, entity, rid=None):
    """performed: the record route is shown; refused: an error message, field error or dialog
    error is shown. A 'Saving...' notice is neither."""
    pattern = re.compile(rf"#{entity}/view/([A-Za-z0-9]+)")
    deadline = time.time() + STEP_MS / 1000
    while time.time() < deadline:
        m = pattern.search(page.url)
        if m and (rid is None or m.group(1) == rid):
            return "performed", m.group(1)
        if page.query_selector(REFUSAL):
            return "refused", None
        page.wait_for_timeout(250)
    return "timeout", None


def refusal_shown(page):
    """refused when an error message appears; timeout when nothing happens."""
    deadline = time.time() + STEP_MS / 1000
    while time.time() < deadline:
        if page.query_selector(REFUSAL):
            return "refused"
        page.wait_for_timeout(250)
    return "timeout"


def slug(c):
    return c.kind.replace("-", "")


def name(c, label):
    return f"BR {label} {c.tag}{slug(c)}"


def save(c, entity, rid=None):
    c.page.click("button[data-action=save]")
    return outcome(c.page, entity, rid)


def make_record(c, entity, data):
    return c.admin.create(entity, data)["id"]


def put(c, entity, rid, data):
    """Setup of a step's starting data, by API as administrator (not a step)."""
    c.admin.call("PUT", f"{entity}/{rid}", data=data)


def fixtures(c):
    """Records every journey after J1 works on, made by API as administrator (setup, not a step)."""
    if c.fx.get("ready"):
        return
    uid = c.admin.call("GET", "User", params={"where[0][type]": "equals", "where[0][attribute]": "userName",
                                               "where[0][value]": c.user})["list"]
    owner = uid[0]["id"] if uid else None
    f = c.fx
    f["firm"] = {"id": make_record(c, "Account", {"name": name(c, "FxFirm")}), "name": name(c, "FxFirm")}
    f["firm2"] = {"id": make_record(c, "Account", {"name": name(c, "FxFirm2")}), "name": name(c, "FxFirm2")}
    f["branch"] = {"id": make_record(c, "Account", {"name": name(c, "FxBranch")}), "name": name(c, "FxBranch")}
    f["contact"] = {"id": make_record(c, "Contact", {"firstName": "Browser", "lastName": f"BRC{c.tag}{slug(c)}",
                                                     "accountsIds": [f["firm"]["id"]]}),
                    "name": f"Browser BRC{c.tag}{slug(c)}"}
    f["contact2"] = {"id": make_record(c, "Contact", {"firstName": "Browser", "lastName": f"BRD{c.tag}{slug(c)}"}),
                     "name": f"Browser BRD{c.tag}{slug(c)}"}
    close = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 86400 * 30))
    for key, label in (("enquiry", "Enquiry"), ("enquiry2", "Enquiry2")):
        f[key] = {"id": make_record(c, "Opportunity", {"name": name(c, label), "accountId": f["firm"]["id"],
                                                       "closeDate": close, "amount": 1000, "amountCurrency": "GBP",
                                                       "assignedUserId": owner}), "name": name(c, label)}
    f["ready"] = True


def need(c, *keys):
    for k in keys:
        if not c.fx.get(k, {}).get("id"):
            raise RuntimeError(f"prerequisite missing: {k}")


def list_open(c, entity):
    """Open a list and wait until it has rendered (typing earlier cancels its first request)."""
    if open_screen(c, entity, "input[data-name=textFilter]") == "denied":
        return False
    c.page.wait_for_selector("tr[data-id]", timeout=STEP_MS)
    return True


def list_search(c, text):
    c.page.fill("input[data-name=textFilter]", text)
    c.page.press("input[data-name=textFilter]", "Enter")


def link_contact_to_enquiry(c, enquiry_id, contact):
    """The enquiry record's contacts panel: select the contact in the dialog."""
    p = c.page
    p.wait_for_selector(".panel[data-name=contacts]", timeout=STEP_MS)
    sel = ".panel[data-name=contacts] [data-action=selectRelated]"
    if not offered(p, sel):
        p.locator(".panel[data-name=contacts] .dropdown-toggle:visible").first.click()
    click_visible(p, sel)
    p.wait_for_selector(".modal tr[data-id]", timeout=STEP_MS)
    list_in_dialog = ".modal input[data-name=textFilter]"
    p.fill(list_in_dialog, contact["name"])
    p.press(list_in_dialog, "Enter")
    p.check(f".modal tr[data-id='{contact['id']}'] input.record-checkbox", timeout=STEP_MS)
    p.click(".modal button[data-name=select]")
    p.wait_for_selector(f".panel[data-name=contacts] tr[data-id='{contact['id']}']", timeout=STEP_MS)


# --- J1 create -----------------------------------------------------------------------

def create_screen(c, entity):
    return open_screen(c, f"{entity}/create", "button[data-action=save]")


def j1_create_firm(c):
    n = name(c, "Firm")
    if create_screen(c, "Account") == "denied":
        return "not offered", "Account", None, None
    c.page.fill(".field[data-name=name] input", n)
    observed, rid = save(c, "Account")
    c.fx["j1firm"] = {"id": rid, "name": n}
    return observed, "Account", rid, {"name": n}


def j1_create_branch(c):
    need(c, "j1firm")
    n = name(c, "Branch")
    if create_screen(c, "Account") == "denied":
        return "not offered", "Account", None, None
    c.page.fill(".field[data-name=name] input", n)
    choose(c.page, ".field[data-name=parent]", c.fx["j1firm"]["name"])
    observed, rid = save(c, "Account")
    return observed, "Account", rid, {"name": n, "parentId": c.fx["j1firm"]["id"]}


def j1_create_contact(c):
    need(c, "j1firm")
    last = f"BRContact{c.tag}{slug(c)}"
    if create_screen(c, "Contact") == "denied":
        return "not offered", "Contact", None, None
    c.page.fill("input[data-name=firstName]", "Browser")
    c.page.fill("input[data-name=lastName]", last)
    choose(c.page, ".field[data-name=accounts]", c.fx["j1firm"]["name"])
    observed, rid = save(c, "Contact")
    c.fx["j1contact"] = {"id": rid, "name": f"Browser {last}"}
    return observed, "Contact", rid, {"lastName": last, "accountsIds": [c.fx["j1firm"]["id"]]}


def j1_create_enquiry(c):
    need(c, "j1firm", "j1contact")
    n = name(c, "Enquiry")
    if create_screen(c, "Opportunity") == "denied":
        return "not offered", "Opportunity", None, None
    c.page.fill(".field[data-name=name] input", n)
    c.page.fill(".field[data-name=closeDate] input", time.strftime("%Y-%m-%d", time.gmtime(time.time() + 86400 * 30)))
    c.page.fill(".field[data-name=amount] input[data-name=amount]", "1000")
    choose(c.page, ".field[data-name=account]", c.fx["j1firm"]["name"])
    if c.kind != "administrator":
        # The create screen leaves Assigned User empty and the ER roles cannot edit an enquiry
        # nobody is assigned to: assign the signed-in user (see docs/BUILD.md).
        choose(c.page, ".field[data-name=assignedUser]", f"Browser {c.kind}")
    observed, rid = save(c, "Opportunity")
    if observed == "performed":
        link_contact_to_enquiry(c, rid, c.fx["j1contact"])
    return observed, "Opportunity", rid, {"name": n, "accountId": c.fx["j1firm"]["id"],
                                         "contactsIds": [c.fx["j1contact"]["id"]]}


# --- J2 edit -------------------------------------------------------------------------

def edit_description(c, entity, key):
    fixtures(c)
    rec = c.fx[key]
    text = f"edited by browser assurance {c.tag}"
    if open_screen(c, f"{entity}/edit/{rec['id']}", "button[data-action=save]") == "denied":
        return "not offered", entity, rec["id"], None
    c.page.fill(".field[data-name=description] textarea", text)
    observed, rid = save(c, entity, rec["id"])
    return observed, entity, rec["id"], {"description": text} if observed == "performed" else None


def j2_edit_firm(c):
    return edit_description(c, "Account", "firm")


def j2_edit_contact(c):
    return edit_description(c, "Contact", "contact")


def j2_edit_enquiry(c):
    return edit_description(c, "Opportunity", "enquiry")


# --- J3 search -----------------------------------------------------------------------

def search_open(c, entity, key):
    fixtures(c)
    rec = c.fx[key]
    if not list_open(c, entity):
        return "not offered", entity, None, None
    list_search(c, rec["name"])
    c.page.click(f"tr[data-id='{rec['id']}'] a.link[data-id='{rec['id']}']", timeout=STEP_MS)
    observed, rid = outcome(c.page, entity, rec["id"])
    return observed, entity, rec["id"], {"id": rec["id"]}


def j3_search_firm(c):
    return search_open(c, "Account", "firm")


def j3_search_contact(c):
    return search_open(c, "Contact", "contact")


def j3_search_enquiry(c):
    return search_open(c, "Opportunity", "enquiry")


# --- J4 relationships ----------------------------------------------------------------

def edit_link(c, entity, key, scope, target, stored, replace=False):
    rec = c.fx[key]
    if open_screen(c, f"{entity}/edit/{rec['id']}", "button[data-action=save]") == "denied":
        return "not offered", entity, rec["id"], None
    if replace:
        c.page.click(f"{scope} [data-action=clearLink]")
    choose(c.page, scope, c.fx[target]["name"])
    observed, _ = save(c, entity, rec["id"])
    return observed, entity, rec["id"], stored if observed == "performed" else None


def j4_set_branch_parent(c):
    fixtures(c)
    return edit_link(c, "Account", "branch", ".field[data-name=parent]", "firm", {"parentId": c.fx["firm"]["id"]})


def j4_change_branch_parent(c):
    fixtures(c)
    put(c, "Account", c.fx["branch"]["id"], {"parentId": c.fx["firm"]["id"]})
    return edit_link(c, "Account", "branch", ".field[data-name=parent]", "firm2",
                     {"parentId": c.fx["firm2"]["id"]}, replace=True)


def j4_link_second_firm(c):
    fixtures(c)
    put(c, "Contact", c.fx["contact"]["id"], {"accountsIds": [c.fx["firm"]["id"]]})
    return edit_link(c, "Contact", "contact", ".field[data-name=accounts]", "firm2",
                     {"accountsIds": [c.fx["firm"]["id"], c.fx["firm2"]["id"]]})


def j4_switch_primary_firm(c):
    """Contact edit form: the second linked firm's menu, 'Set primary' (there is no account field)."""
    fixtures(c)
    f = c.fx
    put(c, "Contact", f["contact"]["id"], {"accountsIds": [f["firm"]["id"], f["firm2"]["id"]],
                                           "accountId": f["firm"]["id"]})
    if open_screen(c, f"Contact/edit/{f['contact']['id']}", "button[data-action=save]") == "denied":
        return "not offered", "Contact", f["contact"]["id"], None
    item = f".field[data-name=accounts] .list-group-item[data-id='{f['firm2']['id']}']"
    c.page.click(f"{item} .dropdown-toggle", timeout=STEP_MS)
    click_visible(c.page, f"{item} [data-action=setPrimary]")
    observed, _ = save(c, "Contact", f["contact"]["id"])
    return observed, "Contact", f["contact"]["id"], {"accountId": f["firm2"]["id"]} if observed == "performed" else None


def j4_change_enquiry_firm(c):
    fixtures(c)
    return edit_link(c, "Opportunity", "enquiry", ".field[data-name=account]", "firm2",
                     {"accountId": c.fx["firm2"]["id"]}, replace=True)


def account_tab(c, firm_id):
    """The firm screen on its Account tab, where the contacts and enquiries panels are."""
    state = open_screen(c, f"Account/view/{firm_id}", ".detail-button-container")
    if state == "ready":
        c.page.locator("button[data-tab]").filter(has_text="Account").first.click(timeout=STEP_MS)
    return state


def panel_row(panel, rid):
    return f".panel[data-name={panel}] tr[data-id='{rid}']"


def j4_related_panels(c):
    """Firm 2 shows its contact and enquiry on the Account tab's related panels."""
    fixtures(c)
    f = c.fx
    put(c, "Contact", f["contact"]["id"], {"accountsIds": [f["firm"]["id"], f["firm2"]["id"]]})
    put(c, "Opportunity", f["enquiry"]["id"], {"accountId": f["firm2"]["id"]})
    if account_tab(c, f["firm2"]["id"]) == "denied":
        return "not offered", "Account", f["firm2"]["id"], None
    for panel, key in (("contacts", "contact"), ("opportunities", "enquiry")):
        c.page.wait_for_selector(panel_row(panel, f[key]["id"]), timeout=STEP_MS)
    return "performed", "Account", f["firm2"]["id"], {"id": f["firm2"]["id"]}


def j4_branch_parent_screen(c):
    """The branch's parent is shown on the branch's own screen and agrees with the stored data."""
    fixtures(c)
    f = c.fx
    put(c, "Account", f["branch"]["id"], {"parentId": f["firm"]["id"]})
    if open_screen(c, f"Account/view/{f['branch']['id']}", ".detail-button-container") == "denied":
        return "not offered", "Account", f["branch"]["id"], None
    c.page.wait_for_selector(f".field[data-name=parent] a[data-id='{f['firm']['id']}']", timeout=STEP_MS)
    return "performed", "Account", f["branch"]["id"], {"parentId": f["firm"]["id"]}


def j4_branches_panel(c):
    """Base behaviour: the firm screen has no branches related panel (unmet against J4 'see them on
    the related panels'). Positive check: the Account tab loaded and shows no branches panel."""
    fixtures(c)
    f = c.fx
    put(c, "Account", f["branch"]["id"], {"parentId": f["firm"]["id"]})
    if account_tab(c, f["firm"]["id"]) == "denied":
        return "not offered", "Account", f["firm"]["id"], None
    c.page.wait_for_selector(".panel[data-name=contacts]", timeout=STEP_MS)
    if c.page.locator(".panel[data-name=branches]").count():
        return "performed", "Account", f["firm"]["id"], {"id": f["firm"]["id"]}
    return "not offered", "Account", f["firm"]["id"], {"id": f["firm"]["id"]}


# --- J5 identity integrity -----------------------------------------------------------

def unchanged_usable(c, entity, rid, stored):
    """The record is still stored as declared and the page still works."""
    c.page.goto(f"{c.base}/#{entity}/view/{rid}", wait_until="load")
    c.page.wait_for_selector(".detail-button-container", timeout=STEP_MS)
    return stored


def delete_record(c, entity, key):
    fixtures(c)
    rec = c.fx[key]
    if open_screen(c, f"{entity}/view/{rec['id']}", ".detail-button-container") == "denied":
        return "not offered", entity, rec["id"], {"deleted": False}
    p = c.page
    if p.locator(".detail-button-container .dropdown-toggle").count():
        p.locator(".detail-button-container .dropdown-toggle").first.click()
    if not offered(p, "[data-action=delete]"):
        return "not offered", entity, rec["id"], {"deleted": False}
    click_visible(p, "[data-action=delete]")
    p.click(".modal [data-name=confirm]")
    observed = outcome_refused(p)
    unchanged_usable(c, entity, rec["id"], None)
    return observed, entity, rec["id"], {"deleted": False}


def outcome_refused(page):
    deadline = time.time() + STEP_MS / 1000
    while time.time() < deadline:
        if page.query_selector(REFUSAL):
            return "refused"
        if "/view/" not in page.url:
            return "performed"
        page.wait_for_timeout(250)
    return "timeout"


def list_selection(c, entity, keys):
    """Open the list, search this kind's own fixtures, tick the rows; None when not offered.
    The text filter is starts-with: '%' makes it a contains search."""
    fixtures(c)
    if not list_open(c, entity):
        return None
    list_search(c, f"%{c.tag}{slug(c)}")
    for k in keys:
        c.page.check(f"tr[data-id='{c.fx[k]['id']}'] input.record-checkbox", timeout=STEP_MS)
    return True


def list_action(c, entity, keys, action):
    rid = c.fx[keys[0]]["id"] if c.fx.get(keys[0]) else None
    if list_selection(c, entity, keys) is None:
        return "not offered", entity, rid, {"deleted": False}
    p = c.page
    if not offered(p, ".actions-button"):
        return "not offered", entity, rid, {"deleted": False}
    click_visible(p, ".actions-button")
    if not offered(p, f"a[data-action={action}]"):
        return "not offered", entity, rid, {"deleted": False}
    click_visible(p, f"a[data-action={action}]")
    if action == "remove":
        p.click(".modal [data-name=confirm]")
    else:
        p.click("button[data-action=merge]", timeout=STEP_MS)
    return refusal_shown(p), entity, rid, {"deleted": False}


def j5_delete_firm_record(c):
    return delete_record(c, "Account", "firm")


def j5_delete_contact_record(c):
    return delete_record(c, "Contact", "contact")


def j5_delete_firm_list(c):
    return list_action(c, "Account", ["firm"], "remove")


def j5_delete_contact_list(c):
    return list_action(c, "Contact", ["contact"], "remove")


def panel_action(c, action):
    """The firm's contacts panel: the contact's row menu, then the action; 'not offered' when the
    menu has no such entry. Returns (observed, firm id) with the dialog confirmed."""
    f = c.fx
    if account_tab(c, f["firm"]["id"]) == "denied":
        return "not offered"
    row = panel_row("contacts", f["contact"]["id"])
    c.page.wait_for_selector(row, timeout=STEP_MS)
    c.page.click(f"{row} .dropdown-toggle")
    if not offered(c.page, f"[data-action={action}]"):
        return "not offered"
    click_visible(c.page, f"[data-action={action}]")
    c.page.click(".modal [data-name=confirm]")
    return refusal_shown(c.page)


def j5_delete_contact_related(c):
    """Contacts panel Remove (administrator only is offered it)."""
    fixtures(c)
    observed = panel_action(c, "removeRelated")
    return observed, "Contact", c.fx["contact"]["id"], {"deleted": False}


def j5_unlink_primary_firm(c):
    """Contacts panel Unlink of the contact's primary firm; the step sets which firm is primary."""
    fixtures(c)
    f = c.fx
    put(c, "Contact", f["contact"]["id"], {"accountsIds": [f["firm"]["id"], f["firm2"]["id"]],
                                           "accountId": f["firm"]["id"]})
    observed = panel_action(c, "unlinkRelated")
    return observed, "Contact", f["contact"]["id"], {"accountId": f["firm"]["id"]}


def j5_merge_firm(c):
    return list_action(c, "Account", ["firm", "firm2"], "merge")


def j5_merge_contact(c):
    return list_action(c, "Contact", ["contact", "contact2"], "merge")


def j5_merge_enquiry(c):
    return list_action(c, "Opportunity", ["enquiry", "enquiry2"], "merge")


def audit_record(c):
    """First identity audit record's view screen; None when the list is not offered."""
    if open_screen(c, "IdentityAudit", "tr[data-id]") == "denied":
        return None
    rid = c.page.get_attribute("tr[data-id]", "data-id")
    open_screen(c, f"IdentityAudit/view/{rid}", ".detail-button-container")
    return rid


def j5_audit_edit(c):
    """Identity audit record: Edit and Save. The administrator is offered it and the server refuses."""
    fixtures(c)
    rid = audit_record(c)
    if rid is None or not offered(c.page, ".detail-button-container [data-action=edit]"):
        return "not offered", "IdentityAudit", rid, None
    click_visible(c.page, ".detail-button-container [data-action=edit]")
    c.page.fill(".field[data-name=name] input", f"edited {c.tag}")
    c.page.click("button[data-action=save]")
    observed = refusal_shown(c.page)
    unchanged_usable(c, "IdentityAudit", rid, None)
    return observed, "IdentityAudit", rid, {"id": rid}


def j5_audit_remove(c):
    """Identity audit record: Remove. The administrator is offered it and the server refuses."""
    fixtures(c)
    rid = audit_record(c)
    if rid is None:
        return "not offered", "IdentityAudit", rid, None
    if c.page.locator(".detail-button-container .dropdown-toggle").count():
        c.page.locator(".detail-button-container .dropdown-toggle").first.click()
    if not offered(c.page, "[data-action=delete]"):
        return "not offered", "IdentityAudit", rid, {"id": rid}
    click_visible(c.page, "[data-action=delete]")
    c.page.click(".modal [data-name=confirm]")
    observed = outcome_refused(c.page)
    unchanged_usable(c, "IdentityAudit", rid, None)
    return observed, "IdentityAudit", rid, {"id": rid}


# --- J6 permissions ------------------------------------------------------------------

def area(c, route, ready):
    if open_screen(c, route, ready) == "denied":
        return "not offered", "User", None, None
    return "performed", "User", None, None


def j6_administration(c):
    return area(c, "Admin", "#main .admin-content")


def j6_import(c):
    return area(c, "Import", "#main .import-container")


def j6_user_create_screen(c):
    return area(c, "User/create", "button[data-action=save]")


def direct_request(c, method, path, data):
    """A request from the signed-in session, through the platform's own request object."""
    c.page.goto(c.base + "/#", wait_until="load")
    c.page.wait_for_selector("#main", timeout=STEP_MS)
    return c.page.evaluate(
        """async ([m, p, d]) => { try { const r = await Espo.Ajax.request(p, m, JSON.stringify(d));
              return {status: 200, id: r && r.id}; } catch (e) { return {status: e.status || -1}; } }""",
        [method, path, data])


def user_exists(c, uname):
    return c.admin.call("GET", "User", params={"where[0][type]": "equals", "where[0][attribute]": "userName",
                                                "where[0][value]": uname})["list"]


def j6_request_create_user(c):
    uname = f"br-new-{slug(c)}-{c.tag}"
    res = direct_request(c, "POST", "User", {"userName": uname, "lastName": "Created", "type": "regular"})
    exists = user_exists(c, uname)
    if res["status"] >= 400:
        if exists:
            raise RuntimeError("a refused request created a user")
        return "refused", "User", None, None
    return "performed", "User", res.get("id"), {"userName": uname}


def j6_request_edit_user(c):
    target = make_record(c, "User", {"userName": f"br-target-{slug(c)}-{c.tag}", "lastName": "Target", "type": "regular"})
    res = direct_request(c, "PUT", f"User/{target}", {"title": "changed"})
    stored = c.admin.call("GET", f"User/{target}").get("title")
    if res["status"] >= 400:
        if stored == "changed":
            raise RuntimeError("a refused request changed a user")
        return "refused", "User", target, {"title": stored}
    return "performed", "User", target, {"title": "changed"}


JOURNEY_STEPS = {
    "J1": {"create-firm": j1_create_firm, "create-branch": j1_create_branch,
           "create-contact": j1_create_contact, "create-enquiry": j1_create_enquiry},
    "J2": {"edit-firm": j2_edit_firm, "edit-contact": j2_edit_contact, "edit-enquiry": j2_edit_enquiry},
    "J3": {"search-firm": j3_search_firm, "search-contact": j3_search_contact, "search-enquiry": j3_search_enquiry},
    "J4": {"set-branch-parent": j4_set_branch_parent, "change-branch-parent": j4_change_branch_parent,
           "link-second-firm": j4_link_second_firm, "switch-primary-firm": j4_switch_primary_firm,
           "change-enquiry-firm": j4_change_enquiry_firm, "related-panels": j4_related_panels,
           "branch-parent-screen": j4_branch_parent_screen, "branches-panel": j4_branches_panel},
    "J5": {"delete-firm-record": j5_delete_firm_record, "delete-contact-record": j5_delete_contact_record,
           "delete-firm-list": j5_delete_firm_list, "delete-contact-list": j5_delete_contact_list,
           "delete-contact-related": j5_delete_contact_related,
           "merge-firm": j5_merge_firm, "merge-contact": j5_merge_contact, "merge-enquiry": j5_merge_enquiry,
           "unlink-primary-firm": j5_unlink_primary_firm,
           "audit-edit": j5_audit_edit, "audit-remove": j5_audit_remove},
    "J6": {"administration-area": j6_administration, "import-area": j6_import,
           "user-create-screen": j6_user_create_screen, "request-create-user": j6_request_create_user,
           "request-edit-user": j6_request_edit_user},
}
