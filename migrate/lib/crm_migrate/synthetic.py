"""In-memory synthetic Salesforce org and ``FakeSalesforceTransport``.

No sockets, no loopback: ``send`` is a plain method call. Every value is synthetic
(``example.test`` domains) and every record carries the marker ``SENTINEL-7f3a`` so tests
can prove that no record content reaches a log. Ids are Salesforce-shaped 18-character
ids with the usual key prefixes and a correct case-safe suffix, generated
deterministically; they identify nothing real.

This module ships inside the package because the ``selftest`` mode must run in the
container, where only ``migrate/`` is mounted. ``tests/migrate/fake_salesforce.py``
re-exports it for the unit tests.
"""

import datetime as _dt
import email.utils
import json
import random
import re
from urllib.parse import parse_qsl, urlsplit

from .contract import parse_soql
from .messages import Response

SENTINEL = "SENTINEL-7f3a"
FAKE_ORIGIN = "https://example.my.salesforce.com"
FAKE_API_VERSION = "62.0"
FAKE_CLIENT_ID = "synthetic-client-id-" + SENTINEL
FAKE_CLIENT_SECRET = "synthetic-client-secret-" + SENTINEL
FAKE_TOKEN = "synthetic-token-" + SENTINEL
CLOCK_START = _dt.datetime(2026, 11, 10, 9, 0, 0, tzinfo=_dt.timezone.utc)

KEY_PREFIX = {
    "Account": "001", "Contact": "003", "Opportunity": "006", "User": "005", "Group": "00G",
    "Task": "00T", "Event": "00U", "EmailMessage": "02s", "Profile": "00e", "UserRole": "00E",
    "OpportunityContactRole": "00K", "Note": "002", "EmailMessageRelation": "0Rs",
    "Lead": "00Q", "Case": "500", "UserLicense": "100", "Calendar": "023",
}
NON_REPLICATEABLE = ("EmailMessageRelation", "Note")
_SUFFIX = "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
_B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def sf_id(prefix, n):
    """Deterministic 18-character id: prefix + 'S7' + base62(n, 10) + case-safe suffix."""
    digits = ""
    for _ in range(10):
        n, r = divmod(n, 62)
        digits = _B62[r] + digits
    id15 = prefix + "S7" + digits
    suffix = ""
    for chunk in range(3):
        bits = 0
        for i, ch in enumerate(id15[chunk * 5:chunk * 5 + 5]):
            if "A" <= ch <= "Z":
                bits |= 1 << i
        suffix += _SUFFIX[bits]
    return id15 + suffix


def sf_datetime(value):
    return value.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000")


def _parse_stamp(value):
    return _dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.000+0000").replace(tzinfo=_dt.timezone.utc)


# ---------------------------------------------------------------- org model

class FakeOrg:
    """Rows per object, a deletion log, describe documents and a server clock."""

    def __init__(self, contract, *, unavailable=(), non_replicateable=NON_REPLICATEABLE,
                 describe_overrides=None, field_overrides=None):
        self.contract = contract
        self.clock = CLOCK_START
        self.rows = {o.name: {} for o in contract.objects}
        self.deleted_log = {o.name: [] for o in contract.objects}
        self.unavailable = set(unavailable)          # "Object.Field"
        self.non_replicateable = set(non_replicateable)
        self.describe_overrides = describe_overrides or {}
        self.field_overrides = field_overrides or {}  # "Object.Field" -> dict or None (remove)
        self._seq = {}

    # clock: advances one second per request
    def tick(self):
        self.clock += _dt.timedelta(seconds=1)
        return self.clock

    def new_id(self, obj):
        prefix = KEY_PREFIX[obj]
        self._seq[prefix] = self._seq.get(prefix, 0) + 1
        return sf_id(prefix, self._seq[prefix])

    def describe(self, obj):
        spec = self.contract.object(obj)
        fields = []
        for f in spec.fields:
            key = f"{obj}.{f.name}"
            if key in self.unavailable:
                continue
            entry = {"name": f.name, "type": f.type, "referenceTo": list(f.reference_to),
                     "picklistValues": ([{"value": f"Value {c}", "active": True} for c in "ABC"]
                                        if f.type in ("picklist", "combobox") else [])}
            if f.reference_match == "superset":
                entry["referenceTo"] = sorted(set(f.reference_to) | {"Case", "Lead"})
            if key in self.field_overrides:
                override = self.field_overrides[key]
                if override is None:
                    continue
                entry.update(override)
            fields.append(entry)
        # fields Salesforce has but the contract never selects
        if obj in ("Account", "Contact"):
            fields.append({"name": "ShippingAddress" if obj == "Account" else "MailingAddress",
                           "type": "address", "referenceTo": [], "picklistValues": []})
        if obj == "EmailMessage":
            fields += [{"name": "HtmlBody", "type": "textarea", "referenceTo": [], "picklistValues": []},
                       {"name": "BccAddress", "type": "string", "referenceTo": [], "picklistValues": []}]
        doc = {
            "name": obj, "keyPrefix": KEY_PREFIX[obj], "queryable": True, "retrieveable": True,
            "replicateable": obj not in self.non_replicateable, "createable": False, "updateable": False,
            "deletable": False, "fields": fields,
        }
        doc.update(self.describe_overrides.get(obj, {}))
        return doc

    # mutations -------------------------------------------------------
    def put(self, obj, row, stamp=None):
        stamp = stamp or self.clock
        row = dict(row)
        row["SystemModstamp"] = sf_datetime(stamp)
        if "LastModifiedDate" in self.contract.object(obj).field_names:
            row["LastModifiedDate"] = sf_datetime(stamp)
        self.rows[obj][row["Id"]] = row
        return row

    def update(self, obj, rid, **changes):
        row = dict(self.rows[obj][rid])
        row.update(changes)
        return self.put(obj, row)

    def insert(self, obj, row):
        row = dict(row)
        row.setdefault("Id", self.new_id(obj))
        row.setdefault("CreatedDate", sf_datetime(self.clock))
        return self.put(obj, row)

    def soft_delete(self, obj, rid):
        self.update(obj, rid, IsDeleted=True)
        self.deleted_log[obj].append((rid, self.clock))

    def hard_delete(self, obj, rid, log=True):
        """Permanent delete: the row disappears; optionally it appears in the deletion log."""
        self.rows[obj].pop(rid)
        if log:
            self.deleted_log[obj].append((rid, self.clock))

    def merge(self, obj, loser, survivor):
        self.update(obj, survivor, **{"Description" if "Description" in self.contract.object(obj).field_names
                                      else "Title": f"{SENTINEL} merged survivor"})
        self.update(obj, loser, IsDeleted=True, MasterRecordId=survivor)
        self.deleted_log[obj].append((loser, self.clock))

    # visibility --------------------------------------------------------
    def visible(self, obj, all_rows):
        out = []
        for rid in sorted(self.rows[obj]):
            row = self.rows[obj][rid]
            if not all_rows and (row.get("IsDeleted") is True or row.get("IsArchived") is True):
                continue
            out.append(row)
        return out


# ---------------------------------------------------------------- fixtures

def _value(rng, spec_field, obj, i):
    t = spec_field.type
    name = spec_field.name
    if t in ("string", "textarea", "combobox"):
        return f"{SENTINEL} {obj} {name} {i}"
    if t == "email":
        return f"{obj.lower()}{i}.sentinel-7f3a@example.test"
    if t == "phone":
        return f"000 {i:04d} {rng.randint(1000, 9999)}"
    if t == "url":
        return f"https://{obj.lower()}{i}.example.test"
    if t in ("picklist", "multipicklist"):
        return "Value " + rng.choice("ABC")
    if t == "boolean":
        return rng.random() < 0.5
    if t == "int":
        return rng.randint(0, 500)
    if t in ("double", "currency", "percent"):
        return round(rng.uniform(0, 1000), 2)
    if t == "date":
        return f"2026-{rng.randint(1, 10):02d}-{rng.randint(1, 28):02d}"
    if t == "datetime":
        return sf_datetime(CLOCK_START - _dt.timedelta(days=rng.randint(10, 300), seconds=rng.randint(0, 86399)))
    return None


def _base_row(org, rng, obj, i, **fixed):
    spec = org.contract.object(obj)
    row = {}
    for f in spec.fields:
        if f.type in ("id", "reference"):
            continue
        row[f.name] = _value(rng, f, obj, i)
    if spec.soft_delete:
        row["IsDeleted"] = False
    if "IsArchived" in spec.field_names:
        row["IsArchived"] = False
    for ref in (f for f in spec.fields if f.type == "reference"):
        row[ref.name] = None
    row["Id"] = org.new_id(obj)
    row.update(fixed)
    stamp = CLOCK_START - _dt.timedelta(days=rng.randint(10, 300), seconds=rng.randint(0, 86399))
    row["CreatedDate"] = sf_datetime(stamp - _dt.timedelta(days=5))
    for k in [k for k in row if k not in spec.field_names]:
        row.pop(k)
    return org.put(obj, row, stamp)


# Planted anomalies in every fixture size (the unit tests hard-code these numbers).
PLANTED = {
    "Account.rows": 24, "Account.ParentId.ok": 12, "Account.ParentId.orphans": 2,
    "Account.soft_deleted": 1, "Account.merged": 1,
    "Account.owner.inactive": 2, "Account.owner.group_not_allowed": 1, "Account.owner.unknown_user": 1,
    "Account.ShippingPostalCode.filled": 18, "Account.Website.filled": 8,
    "Contact.rows": 40, "Contact.AccountId.orphans": 3, "Contact.AccountId.null": 2,
    "Task.rows": 30, "Task.archived": 4, "Task.owner.queue": 3, "Task.WhatId.orphans": 2,
    "Task.WhatId.not_extracted": 1, "EmailMessage.ActivityId.orphans": 1,
    "EmailMessageRelation.unmatched_address": 4, "EmailMessageRelation.RelationId.orphans": 1,
    "OpportunityContactRole.ContactId.orphans": 1, "Opportunity.AccountId.orphans": 1,
}


def build_org(contract, *, seed=7, size="quick", **org_kwargs):
    """Deterministic, seeded fixture. ``size='full'`` adds plain rows without anomalies."""
    org = FakeOrg(contract, **org_kwargs)
    rng = random.Random(seed)
    extra = 0 if size == "quick" else 20
    profiles = [_base_row(org, rng, "Profile", i, UserLicenseId=sf_id("100", i + 1)) for i in range(3)]
    roles = []
    for i in range(3):
        roles.append(_base_row(org, rng, "UserRole", i, ParentRoleId=roles[0]["Id"] if roles else None))
    users = []
    for i in range(6):
        users.append(_base_row(org, rng, "User", i, IsActive=(i != 5), ProfileId=profiles[i % 3]["Id"],
                               UserRoleId=roles[i % 3]["Id"], FirstName=f"{SENTINEL} User {i}"))
    active = [u["Id"] for u in users[:5]]
    inactive = users[5]["Id"]
    missing_user = sf_id("005", 9999)
    missing_account = sf_id("001", 9999)
    group = sf_id("00G", 1)

    def owner(i):
        return active[i % len(active)]

    def audit(i):
        return {"CreatedById": active[i % len(active)]}

    # Accounts: 0-3 parents, 4-15 branches, 16-17 orphan parents, 18-23 standalone (+extra)
    accounts = []
    n_acc = 24 + extra
    for i in range(n_acc):
        fixed = {"OwnerId": owner(i), **audit(i), "Name": f"{SENTINEL} Firm {i}",
                 "ShippingPostalCode": None if i % 4 == 0 else f"ZZ{i} 0ZZ",
                 "Website": f"https://firm{i}.example.test" if i % 3 == 0 else None}
        if i >= 24:
            fixed["ShippingPostalCode"] = None  # extra rows keep the planted fill counts stable
            fixed["Website"] = None
        if 4 <= i <= 15:
            fixed["ParentId"] = None  # set below
        if i in (16, 17):
            fixed["ParentId"] = missing_account
        if i in (20, 21):
            fixed["OwnerId"] = inactive
        if i == 22:
            fixed["OwnerId"] = group           # Account.OwnerId does not allow Group
        if i == 23:
            fixed["OwnerId"] = missing_user
        accounts.append(_base_row(org, rng, "Account", i, **fixed))
    for i in range(4, 16):
        org.rows["Account"][accounts[i]["Id"]]["ParentId"] = accounts[i % 4]["Id"]
    org.rows["Account"][accounts[18]["Id"]]["IsDeleted"] = True                       # soft-deleted
    org.rows["Account"][accounts[19]["Id"]].update(IsDeleted=True, MasterRecordId=accounts[0]["Id"])  # merged
    for i in (18, 19):
        org.deleted_log["Account"].append((accounts[i]["Id"], CLOCK_START - _dt.timedelta(days=2)))
    acc_ids = [a["Id"] for a in accounts[:16]]

    contacts = []
    for i in range(40 + extra):
        acct = acc_ids[i % len(acc_ids)]
        if i in (0, 1, 2):
            acct = missing_account
        if i in (3, 4):
            acct = None
        contacts.append(_base_row(org, rng, "Contact", i, AccountId=acct, OwnerId=owner(i), **audit(i),
                                  LastName=f"{SENTINEL} Contact {i}"))
    con_ids = [c["Id"] for c in contacts[5:]]

    opps = []
    for i in range(30 + extra):
        acct = missing_account if i == 0 else acc_ids[i % len(acc_ids)]
        opps.append(_base_row(org, rng, "Opportunity", i, AccountId=acct, OwnerId=owner(i), **audit(i)))
    opp_ids = [o["Id"] for o in opps]

    for i in range(15):
        _base_row(org, rng, "OpportunityContactRole", i, OpportunityId=opp_ids[i % len(opp_ids)],
                  ContactId=sf_id("003", 9999) if i == 0 else con_ids[i % len(con_ids)],
                  Role=f"{SENTINEL} Role")

    tasks = []
    for i in range(30 + extra):
        what = opp_ids[i % len(opp_ids)] if i % 2 else acc_ids[i % len(acc_ids)]
        if i in (0, 1):
            what = sf_id("006", 9999)                      # orphan
        if i == 2:
            what = sf_id("500", 1)                         # Case: not extracted
        fixed = {"WhatId": what, "WhoId": con_ids[i % len(con_ids)], "AccountId": acc_ids[i % len(acc_ids)],
                 "OwnerId": group if i in (3, 4, 5) else owner(i), **audit(i),
                 "IsArchived": i in (6, 7, 8, 9)}
        tasks.append(_base_row(org, rng, "Task", i, **fixed))
    task_ids = [t["Id"] for t in tasks]

    for i in range(12 + extra):
        _base_row(org, rng, "Event", i, WhatId=opp_ids[i % len(opp_ids)], WhoId=con_ids[i % len(con_ids)],
                  AccountId=acc_ids[i % len(acc_ids)], OwnerId=owner(i), **audit(i))

    emails = []
    for i in range(15 + extra):
        emails.append(_base_row(org, rng, "EmailMessage", i,
                                ActivityId=sf_id("00T", 9999) if i == 0 else task_ids[i % len(task_ids)],
                                RelatedToId=opp_ids[i % len(opp_ids)], ParentId=None, **audit(i)))
    email_ids = [e["Id"] for e in emails]

    for i in range(30):
        rel = con_ids[i % len(con_ids)] if i % 3 else active[i % len(active)]
        addr = f"relation{i}.sentinel-7f3a@example.test"
        if i in (0, 1, 2, 3):
            rel = None                                      # unmatched address
        if i == 4:
            rel = sf_id("003", 9998)                        # orphan
        _base_row(org, rng, "EmailMessageRelation", i, EmailMessageId=email_ids[i % len(email_ids)],
                  RelationId=rel, RelationAddress=addr)

    for i in range(6):
        _base_row(org, rng, "Note", i, ParentId=acc_ids[i % len(acc_ids)], OwnerId=owner(i),
                  Title=f"{SENTINEL} Note {i}")
    return org


# ---------------------------------------------------------------- hooks

class Hook:
    """Fires ``action(org)`` on the nth matching event.

    ``event`` is ``'page'`` (after a query page for ``obj`` is served) or ``'limits'``
    (when a ``limits`` request arrives: #1 is T_start, #2 starts pass 1, and so on).
    ``every=True`` fires on every match from the nth onwards.
    """

    def __init__(self, event, action, *, obj=None, nth=1, every=False):
        self.event, self.action, self.obj, self.nth, self.every = event, action, obj, nth, every
        self.seen = 0
        self.fired = 0

    def notify(self, event, obj, org):
        if event != self.event or (self.obj is not None and obj != self.obj):
            return
        self.seen += 1
        if self.seen == self.nth or (self.every and self.seen > self.nth):
            self.fired += 1
            self.action(org)


# ---------------------------------------------------------------- transport

class FakeWriteAttempt(AssertionError):
    pass


class FakeSalesforceTransport:
    """``Transport`` implementation answering from a ``FakeOrg``. Records every request."""

    total_requests = 0
    total_write_requests = 0

    def __init__(self, org, *, origin=FAKE_ORIGIN, api_version=FAKE_API_VERSION, instance_url=None,
                 page_size=7, hooks=(), redirect_paths=(), absolute_next=False, foreign_next=False,
                 count_offset=None, hide_from_id_query=(), error_paths=(), drop_date=False):
        self.org = org
        self.origin = origin
        self.api_version = api_version
        self.instance_url = instance_url or origin
        self.page_size = page_size
        self.hooks = list(hooks)
        self.redirect_paths = [re.compile(p) for p in redirect_paths]
        self.error_paths = [re.compile(p) for p in error_paths]
        self.absolute_next = absolute_next
        self.foreign_next = foreign_next
        self.count_offset = dict(count_offset or {})
        self.hide_from_id_query = set(hide_from_id_query)
        self.drop_date = drop_date
        self.requests = []
        self.write_requests = 0
        self._cursors = {}
        self._cursor_seq = 0

    def _notify(self, event, obj=None):
        for hook in self.hooks:
            hook.notify(event, obj, self.org)

    def _resp(self, status, doc, extra=None):
        headers = {"content-type": "application/json"}
        if not self.drop_date:
            headers["date"] = email.utils.format_datetime(self.org.clock, usegmt=True)
        headers.update(extra or {})
        return Response(status, headers, json.dumps(doc).encode("utf-8"))

    def _error(self, status, code):
        return self._resp(status, [{"errorCode": code, "message": f"{SENTINEL} synthetic error body"}])

    def send(self, request):
        FakeSalesforceTransport.total_requests += 1
        self.org.tick()
        parts = urlsplit(request.url)
        self.requests.append((request.method, parts.path))
        is_token = request.method == "POST" and parts.path == "/services/oauth2/token"
        if request.method != "GET" and not is_token:
            self.write_requests += 1
            FakeSalesforceTransport.total_write_requests += 1
            raise FakeWriteAttempt("write request reached the fake")
        for rx in self.redirect_paths:
            if rx.search(parts.path):
                return self._resp(302, {}, {"location": "https://elsewhere.example.test" + parts.path})
        for rx in self.error_paths:
            if rx.search(parts.path):
                return self._error(500, "UNKNOWN_EXCEPTION")
        if is_token:
            form = dict(parse_qsl(request.body.decode("ascii")))
            if (form.get("grant_type") != "client_credentials" or form.get("client_id") != FAKE_CLIENT_ID
                    or form.get("client_secret") != FAKE_CLIENT_SECRET):
                return self._resp(400, {"error": "invalid_client", "error_description": f"{SENTINEL} bad"})
            return self._resp(200, {"access_token": FAKE_TOKEN, "instance_url": self.instance_url,
                                    "token_type": "Bearer", "id": f"{self.origin}/id/{SENTINEL}"})
        headers = dict(request.headers)
        if headers.get("Authorization") != "Bearer " + FAKE_TOKEN:
            return self._error(401, "INVALID_SESSION_ID")
        base = f"/services/data/v{self.api_version}/"
        path = parts.path
        params = dict(parse_qsl(parts.query))
        if not path.startswith(base):
            return self._error(404, "NOT_FOUND")
        rest = path[len(base):].rstrip("/")
        if rest == "limits":
            self._notify("limits")
            return self._resp(200, {"DailyApiRequests": {"Max": 15000, "Remaining": 14000}})
        if rest in ("query", "queryAll"):
            return self._query(params.get("q"), rest == "queryAll")
        if rest.startswith("query/"):
            return self._next(rest[len("query/"):])
        m = re.match(r"^sobjects/([A-Za-z0-9_]+)/(describe|deleted)$", rest)
        if m and m.group(1) in self.org.rows:
            if m.group(2) == "describe":
                return self._resp(200, self.org.describe(m.group(1)))
            return self._deleted(m.group(1), params)
        return self._error(404, "NOT_FOUND")

    def _project(self, obj, row, fields):
        rec = {"attributes": {"type": obj, "url": f"/services/data/v{self.api_version}/sobjects/{obj}/{row['Id']}"}}
        for name in fields:
            rec[name] = row.get(name)
        return rec

    def _query(self, q, all_rows):
        parsed = parse_soql(q)
        if parsed is None or parsed.object not in self.org.rows:
            return self._error(400, "MALFORMED_QUERY")
        obj = parsed.object
        rows = self.org.visible(obj, all_rows)
        if parsed.since is not None:
            rows = [r for r in rows if _parse_stamp(r["SystemModstamp"]) >= parsed.since]
        if parsed.is_count:
            return self._resp(200, {"totalSize": len(rows) + self.count_offset.get(obj, 0), "done": True,
                                    "records": []})
        spec = self.org.contract.object(obj)
        id_only = parsed.fields in (("Id", "IsDeleted", "SystemModstamp"), ("Id", "SystemModstamp"))
        if id_only and self.hide_from_id_query:
            rows = [r for r in rows if r["Id"] not in self.hide_from_id_query]
        for name in parsed.fields:
            if spec.field(name) is None or f"{obj}.{name}" in self.org.unavailable:
                return self._error(400, "INVALID_FIELD")
        records = [self._project(obj, r, parsed.fields) for r in rows]
        self._cursor_seq += 1
        locator = f"01gS7{self._cursor_seq:06d}"
        self._cursors[locator] = (obj, records)
        return self._page(locator, 0)

    def _page(self, locator, offset):
        obj, records = self._cursors[locator]
        chunk = records[offset:offset + self.page_size]
        done = offset + self.page_size >= len(records)
        doc = {"totalSize": len(records), "done": done, "records": chunk}
        if not done:
            nxt = f"/services/data/v{self.api_version}/query/{locator}-{offset + self.page_size}"
            if self.absolute_next:
                nxt = "https://elsewhere.example.test" + nxt
            elif self.foreign_next:
                nxt = f"/services/data/v{self.api_version}/sobjects/{obj}/describe"
            doc["nextRecordsUrl"] = nxt
        resp = self._resp(200, doc)
        self._notify("page", obj)
        return resp

    def _next(self, token):
        m = re.match(r"^(01gS7\d{6})-(\d+)$", token)
        if not m or m.group(1) not in self._cursors:
            return self._error(400, "INVALID_QUERY_LOCATOR")
        return self._page(m.group(1), int(m.group(2)))

    def _deleted(self, obj, params):
        if obj in self.org.non_replicateable:
            return self._error(400, "INVALID_REPLICATION_OBJECT")
        try:
            start = _dt.datetime.strptime(params["start"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
            end = _dt.datetime.strptime(params["end"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
        except (KeyError, ValueError):
            return self._error(400, "INVALID_REPLICATION_DATE")
        records = [{"id": rid, "deletedDate": sf_datetime(when)}
                   for rid, when in self.org.deleted_log[obj] if start <= when.replace(microsecond=0) <= end]
        return self._resp(200, {"deletedRecords": records, "earliestDateAvailable": sf_datetime(start),
                                "latestDateCovered": sf_datetime(end)})


# ---------------------------------------------------------------- scenarios

def _first(org, obj, predicate=lambda r: True):
    for rid in sorted(org.rows[obj]):
        row = org.rows[obj][rid]
        if row.get("IsDeleted") is not True and predicate(row):
            return rid
    raise LookupError(obj)


def _late_row(org, seconds_back):
    stamp = org.clock - _dt.timedelta(seconds=seconds_back)
    row = {"Id": org.new_id("Contact"), "LastName": f"{SENTINEL} late", "IsDeleted": False,
           "CreatedDate": sf_datetime(stamp)}
    org.put("Contact", row, stamp)


def scenario_hooks(name):
    """Hooks for a named in-run mutation scenario. Returns (hooks, fake kwargs)."""
    acc = "Account"
    if name == "none":
        return [], {}
    if name == "update":
        return [Hook("page", lambda o: o.update(acc, _first(o, acc), Phone="000 0000 0000"), obj=acc)], {}
    if name == "insert":
        return [Hook("page", lambda o: o.insert(acc, {"Name": f"{SENTINEL} new firm", "IsDeleted": False}),
                     obj=acc)], {}
    if name == "soft_delete":
        return [Hook("page", lambda o: o.soft_delete(acc, _first(o, acc)), obj=acc)], {}
    if name == "permanent_delete_logged":
        return [Hook("page", lambda o: o.hard_delete(acc, _first(o, acc), log=True), obj=acc)], {}
    if name == "permanent_delete_unlogged":
        return [Hook("page", lambda o: o.hard_delete(acc, _first(o, acc), log=False), obj=acc)], {}
    if name == "merge":
        def merge(o):
            ids = [r for r in sorted(o.rows[acc]) if o.rows[acc][r].get("IsDeleted") is not True]
            o.merge(acc, ids[1], ids[0])
        return [Hook("page", merge, obj=acc)], {}
    if name == "late_visible":
        return [Hook("page", lambda o: _late_row(o, 120), obj="Contact")], {}
    if name == "late_visible_beyond_overlap":
        return [Hook("page", lambda o: _late_row(o, 3600), obj="Contact")], {}
    if name == "continuous":
        return [Hook("limits", lambda o: o.update(acc, _first(o, acc), Phone="000 1111 2222"), nth=2,
                     every=True)], {}
    if name == "injected_id_mismatch":
        return [], {"hide_from_id_query": "first_account"}
    if name == "injected_count_mismatch":
        return [], {"count_offset": {"Task": 1}}
    raise KeyError(name)


SCENARIO_EXPECTED = {
    "none": "RECONCILED",
    "update": "RECONCILED",
    "insert": "RECONCILED",
    "soft_delete": "RECONCILED",
    "permanent_delete_logged": "RECONCILED",
    "permanent_delete_unlogged": "INCOMPLETE",
    "merge": "RECONCILED",
    "late_visible": "RECONCILED",
    "late_visible_beyond_overlap": "INCOMPLETE",
    "continuous": "RECONCILED_WITH_DRIFT",
    "injected_id_mismatch": "INCOMPLETE",
    "injected_count_mismatch": "INCOMPLETE",
}


def make_fake(contract, scenario="none", *, seed=7, size="quick", org_kwargs=None, **kwargs):
    org = build_org(contract, seed=seed, size=size, **(org_kwargs or {}))
    hooks, extra = scenario_hooks(scenario)
    if extra.get("hide_from_id_query") == "first_account":
        extra["hide_from_id_query"] = {_first(org, "Account")}
    extra.update(kwargs)
    return FakeSalesforceTransport(org, hooks=hooks, **extra)
