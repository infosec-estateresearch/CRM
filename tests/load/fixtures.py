"""Synthetic snapshot generator and fake EspoCRM transport for crm-load tests.

Every value is synthetic (example.test). SENTINEL appears in every free-text field so the
no-content rule can be checked on every output.
"""

import gzip
import hashlib
import io
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB = os.path.join(ROOT, "load", "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)

SENTINEL = "SENTINEL-7f3a"
# Contract v4 field lists (copied from the CRM-002 contract; load/ never imports migrate/).
FIELDS_V4 = {
    "User": ["Id", "FirstName", "LastName", "Name", "Email", "Username", "Alias", "IsActive", "ProfileId",
             "UserRoleId", "UserType", "CreatedDate", "LastLoginDate", "SystemModstamp"],
    "Profile": ["Id", "Name", "UserLicenseId", "SystemModstamp"],
    "UserRole": ["Id", "Name", "ParentRoleId", "SystemModstamp"],
    "Account": ["Id", "Name", "ParentId", "MasterRecordId", "Type", "Industry", "Phone", "Website", "Description",
                "AccountSource", "OwnerId", "ShippingStreet", "ShippingCity", "ShippingState", "ShippingPostalCode",
                "ShippingCountry", "BillingStreet", "BillingCity", "BillingState", "BillingPostalCode",
                "BillingCountry", "NumberOfEmployees", "LastActivityDate", "TLP__c", "Interested_in_integration__c",
                "Bankruptcy_Special_Rate__c", "IsDeleted", "CreatedDate", "CreatedById", "LastModifiedDate",
                "SystemModstamp"],
    "Contact": ["Id", "AccountId", "MasterRecordId", "FirstName", "LastName", "Salutation", "Title", "Department",
                "Email", "Phone", "MobilePhone", "MailingStreet", "MailingCity", "MailingState",
                "MailingPostalCode", "MailingCountry", "OwnerId", "IsDeleted", "CreatedDate", "CreatedById",
                "LastModifiedDate", "SystemModstamp"],
    "Opportunity": ["Id", "AccountId", "Name", "StageName", "Amount", "Probability", "CloseDate", "Type",
                    "LeadSource", "Description", "OwnerId", "IsClosed", "IsWon", "Loss_Reason__c",
                    "Paid_geneology_enquiry__c", "Opportunity_Service__c", "IsDeleted", "CreatedDate", "CreatedById",
                    "LastModifiedDate", "SystemModstamp"],
    "OpportunityContactRole": ["Id", "OpportunityId", "ContactId", "Role", "IsPrimary", "IsDeleted",
                               "CreatedDate", "SystemModstamp"],
    "Task": ["Id", "AccountId", "WhoId", "WhatId", "OwnerId", "Subject", "Status", "Priority", "ActivityDate",
             "Description", "TaskSubtype", "CallType", "CallDurationInSeconds", "CallDisposition",
             "CompletedDateTime", "IsClosed", "IsArchived", "IsRecurrence", "IsDeleted", "CreatedDate",
             "CreatedById", "LastModifiedDate", "SystemModstamp"],
    "Event": ["Id", "AccountId", "WhoId", "WhatId", "OwnerId", "Subject", "Type", "Location", "Description",
              "StartDateTime", "EndDateTime", "ActivityDateTime", "IsAllDayEvent", "DurationInMinutes", "IsArchived",
              "IsRecurrence", "IsDeleted", "CreatedDate", "CreatedById", "LastModifiedDate", "SystemModstamp"],
    "EmailMessage": ["Id", "ParentId", "ActivityId", "RelatedToId", "Subject", "TextBody", "FromName",
                     "FromAddress", "ToAddress", "CcAddress", "MessageDate", "Incoming", "Status",
                     "MessageIdentifier", "ThreadIdentifier", "HasAttachment", "IsDeleted", "CreatedDate",
                     "CreatedById", "LastModifiedDate", "SystemModstamp"],
    "EmailMessageRelation": ["Id", "EmailMessageId", "RelationId", "RelationType", "RelationAddress",
                             "RelationObjectType", "CreatedDate", "SystemModstamp"],
    "Note": ["Id", "ParentId", "Title", "Body", "OwnerId", "IsPrivate", "IsDeleted", "CreatedDate",
             "LastModifiedDate", "SystemModstamp"],
}
VISIBLE_VIA = {"EmailMessageRelation": [{"field": "EmailMessageId", "object": "EmailMessage"},
                                        {"field": "RelationId", "object": "Contact"}]}
SOFT = {"Account", "Contact", "Opportunity", "OpportunityContactRole", "Task", "Event", "EmailMessage", "Note"}


def sid(prefix, n):
    return f"{prefix}S7{n:010d}AAA"[:18]


U1, U2, U_INACTIVE, U_SHARED = sid("005", 1), sid("005", 2), sid("005", 3), sid("005", 4)
U_MISSING, QUEUE = sid("005", 999), sid("00G", 1)
U_AUTOMATED = sid("005", 5)                        # UserType AutomatedProcess: not exported, not provisioned
A = [sid("001", i) for i in range(1, 7)]           # A[4] soft-deleted; A[5] owned by a non-human user
C = [sid("003", i) for i in range(1, 5)]           # C[3] soft-deleted
O = [sid("006", i) for i in range(1, 8)]           # O[6] soft-deleted
T = [sid("00T", i) for i in range(1, 8)]
E = [sid("00U", i) for i in range(1, 3)]
M = [sid("02s", i) for i in range(1, 4)]          # M[2] soft-deleted
CREATED = "2020-01-02T03:04:05.000+0000"


def org(account_marker=True):
    """The synthetic org. ``account_marker`` False leaves SENTINEL out of Account Name only
    (a production-shaped snapshot for beta; every other free-text field keeps it)."""
    s = SENTINEL
    users = [
        dict(Id=U1, FirstName="Ann" + s, LastName="One" + s, Name="x" + s, Email=f"u1.{s}@example.test",
             Username="u1@example.test", Alias="u1", IsActive=True, ProfileId=sid("00e", 1), UserRoleId=sid("00E", 1), UserType="Standard"),
        dict(Id=U2, FirstName="Bob", LastName="Two" + s, Name="x", Email="u2@example.test",
             Username="u2@example.test", Alias="u2", IsActive=True, ProfileId=sid("00e", 2), UserRoleId=None,
             UserType="Standard"),
        dict(Id=U_INACTIVE, FirstName="Cy", LastName="Three", Name="x", Email="u3@example.test",
             Username="u3@example.test", Alias="u3", IsActive=False, ProfileId=sid("00e", 1), UserRoleId=None,
             UserType="Standard"),
        dict(Id=U_SHARED, FirstName="Shared", LastName="Login" + s, Name="x", Email="anc@example.test",
             Username="ancillary@example.test", Alias="anc", IsActive=True, ProfileId=sid("00e", 1),
             UserRoleId=None, UserType="Standard"),
        dict(Id=U_AUTOMATED, FirstName=None, LastName="Automated", Name="x", Email="auto@example.test",
             Username="autoproc@example.test", Alias="auto", IsActive=True, ProfileId=sid("00e", 2),
             UserRoleId=None, UserType="AutomatedProcess"),
    ]
    profiles = [dict(Id=sid("00e", 1), Name="Profile A"), dict(Id=sid("00e", 2), Name="Profile B")]
    roles = [dict(Id=sid("00E", 1), Name="Role C")]
    acc = lambda i, **kw: dict(dict(Id=A[i], Name=f"Firm {i} {s}" if account_marker else f"Firm {i}", ParentId=None, MasterRecordId=None,  # noqa
                                    Type="Tier 1", Industry="Solicitor", Phone=f"+44 1632 9600{i:02d}",
                                    Website="https://f.example.test/" + s, OwnerId=U1, Description="AccDesc " + s,
                                    ShippingStreet="1 Ship St " + s, ShippingCity="Shipton", ShippingPostalCode="S1",
                                    BillingStreet="2 Bill St " + s, BillingCity="Billton", TLP__c="TLP",
                                    IsDeleted=False, CreatedDate=CREATED), **kw)
    accounts = [acc(0), acc(1, ParentId=A[0], OwnerId=QUEUE, Type="Tier 9 " + s),
                acc(2, ParentId=A[1], OwnerId=U_MISSING, Phone="n/a"),
                acc(3, ParentId=A[4], OwnerId=U_INACTIVE), acc(4, IsDeleted=True),
                acc(5, OwnerId=U_AUTOMATED, Phone=None, Description=None)]
    con = lambda i, **kw: dict(dict(Id=C[i], AccountId=A[0], FirstName="F" + s, LastName="L" + s,  # noqa
                                    Salutation="Mr.", Title="T" + s, Email=f"c{i}.{s}@example.test",
                                    Phone=f"01632 9601{i:02d}", MobilePhone=f"+44 7700 9000{i:02d}", MailingStreet="3 Mail " + s, MailingCity="Mailton",
                                    OwnerId=U2, IsDeleted=False, CreatedDate=CREATED), **kw)
    contacts = [con(0), con(1, AccountId=A[1], Phone=None), con(2, AccountId=A[4], MobilePhone=None),
                con(3, IsDeleted=True)]
    opp = lambda i, **kw: dict(dict(Id=O[i], AccountId=A[0], Name=f"Enquiry {i} {s}", StageName="Closed Won",  # noqa
                                    Amount=100.5, CloseDate="2026-01-01", Type="New Business",
                                    LeadSource="AB" + s, OwnerId=U1, Description="OppDesc " + s, Loss_Reason__c=None,
                                    Paid_geneology_enquiry__c="Yes", Opportunity_Service__c="Service X",
                                    IsDeleted=False, CreatedDate=CREATED), **kw)
    opps = [opp(0), opp(1, StageName="Needs Analysis", CloseDate="2020-01-01", OwnerId=U_SHARED),
            opp(2, StageName="Proposal", CloseDate="2099-01-01", Opportunity_Service__c="Service Y"),
            opp(3, StageName="Closed Lost", Loss_Reason__c="Price"),
            opp(4, StageName="Closed Lost", Loss_Reason__c=None, OwnerId=QUEUE),
            opp(5, StageName="Mystery " + s, AccountId=None, Opportunity_Service__c=None, Amount=None),
            opp(6, IsDeleted=True)]
    ocr = [dict(Id=sid("00K", 1), OpportunityId=O[0], ContactId=C[0], Role="Decision Maker", IsDeleted=False),
           dict(Id=sid("00K", 2), OpportunityId=O[0], ContactId=C[1], Role=None, IsDeleted=False),
           dict(Id=sid("00K", 3), OpportunityId=O[1], ContactId=C[3], Role="Other", IsDeleted=False),
           dict(Id=sid("00K", 4), OpportunityId=O[6], ContactId=C[0], Role="Other", IsDeleted=False),
           dict(Id=sid("00K", 5), OpportunityId=O[2], ContactId=C[0], Role="Other", IsDeleted=True),
           dict(Id=sid("00K", 6), OpportunityId=O[3], ContactId=C[1], Role="Godparent " + s, IsDeleted=False)]
    task = lambda i, **kw: dict(dict(Id=T[i], AccountId=A[0], WhoId=C[0], WhatId=O[0], OwnerId=U1,  # noqa
                                     Subject="Subj " + s, Status="Completed", Priority="Normal",
                                     ActivityDate="2025-05-05", Description="Desc " + s, TaskSubtype="Task",
                                     CallType=None, CallDurationInSeconds=None,
                                     CompletedDateTime="2025-05-05T10:00:00.000+0000", IsClosed=True,
                                     IsDeleted=False, CreatedDate=CREATED), **kw)
    tasks = [task(0), task(1, TaskSubtype="Call", CallType="Outbound", CallDurationInSeconds=60, WhatId=None),
             task(2, TaskSubtype="Email", WhatId=None, AccountId=None), task(3, TaskSubtype="Email"),
             task(4, IsDeleted=True),
             task(5, Status="Open", Priority="High", CompletedDateTime=None, IsClosed=False),
             task(6, TaskSubtype="Call", CallType=None, WhatId=O[1], CompletedDateTime=None)]
    events = [dict(Id=E[0], AccountId=A[1], WhoId=C[1], WhatId=None, OwnerId=U2, Subject="Ev " + s, Type=None,
                   Description="D " + s, StartDateTime="2025-06-01T09:00:00.000+0100",
                   EndDateTime="2025-06-01T10:00:00.000+0100", IsAllDayEvent=False, IsDeleted=False,
                   CreatedDate=CREATED),
              dict(Id=E[1], AccountId=None, WhoId=None, WhatId=sid("006", 9999), OwnerId=U1, Subject="Ev2",
                   Type="Presentation", Description=None, StartDateTime=None,
                   EndDateTime="2025-06-02T10:00:00Z", IsAllDayEvent=False, IsDeleted=False, CreatedDate=CREATED)]
    emails = [dict(Id=M[0], ParentId=None, ActivityId=T[3], RelatedToId=O[0], Subject="Re " + s,
                   TextBody="Body " + s, FromName="N " + s, FromAddress=f"from.{s}@example.test",
                   ToAddress=f"a.{s}@example.test; b@example.test", CcAddress="c@example.test",
                   MessageDate="2025-07-01T12:00:00.000+0000", Incoming=True, Status="3",
                   MessageIdentifier=f"<m1.{s}@example.test>", ThreadIdentifier="thr" + s, HasAttachment=False,
                   IsDeleted=False, CreatedDate=CREATED),
              dict(Id=M[1], ParentId=None, ActivityId=T[2], RelatedToId=None, Subject="Re2", TextBody=None,
                   FromName=None, FromAddress="x@example.test", ToAddress="y@example.test", CcAddress=None,
                   MessageDate="2025-07-02T12:00:00.000+0000", Incoming=False, Status="3",
                   MessageIdentifier=None, ThreadIdentifier=None, HasAttachment=False, IsDeleted=False,
                   CreatedDate=CREATED),
              dict(Id=M[2], ParentId=None, ActivityId=None, RelatedToId=O[0], Subject="Gone " + s, TextBody=None,
                   FromName=None, FromAddress="x@example.test", ToAddress="y@example.test", CcAddress=None,
                   MessageDate="2025-07-03T12:00:00.000+0000", Incoming=True, Status="1",
                   MessageIdentifier=None, ThreadIdentifier=None, HasAttachment=False, IsDeleted=True,
                   CreatedDate=CREATED)]
    rels = [dict(Id=sid("0EM", 1), EmailMessageId=M[0], RelationId=U1, RelationType="ToAddress",
                 RelationAddress=f"a.{s}@example.test"),
            dict(Id=sid("0EM", 2), EmailMessageId=M[0], RelationId=C[0], RelationType="ToAddress",
                 RelationAddress="b@example.test"),
            dict(Id=sid("0EM", 3), EmailMessageId=M[0], RelationId=U_MISSING, RelationType="CcAddress",
                 RelationAddress="c@example.test"),
            # Hidden in Salesforce through a soft-deleted parent (contract v4 visibleVia): skipped.
            dict(Id=sid("0EM", 4), EmailMessageId=M[0], RelationId=C[3], RelationType="CcAddress",
                 RelationAddress="d@example.test"),
            dict(Id=sid("0EM", 5), EmailMessageId=M[2], RelationId=U1, RelationType="ToAddress",
                 RelationAddress="e@example.test")]
    notes = [dict(Id=sid("002", 1), ParentId=A[0], Title="N " + s, Body="B " + s, OwnerId=U1, IsDeleted=False),
             dict(Id=sid("002", 2), ParentId=A[0], Title="N", Body="B", OwnerId=U1, IsDeleted=True)]
    return {"User": users, "Profile": profiles, "UserRole": roles, "Account": accounts, "Contact": contacts,
            "Opportunity": opps, "OpportunityContactRole": ocr, "Task": tasks, "Event": events,
            "EmailMessage": emails, "EmailMessageRelation": rels, "Note": notes}


def _gz(rows):
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
        for r in sorted(rows, key=lambda r: r["Id"]):
            gz.write((json.dumps(r, separators=(",", ":")) + "\n").encode("utf-8"))
    return buf.getvalue()


def seal(root):
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            os.chmod(os.path.join(dirpath, name), 0o400)
        os.chmod(dirpath, 0o700)


def unseal(root):
    for dirpath, dirnames, filenames in os.walk(root):
        os.chmod(dirpath, 0o700)
        for name in filenames:
            os.chmod(os.path.join(dirpath, name), 0o600)


def write_selftest_manifest(parent):
    """The real selftest parent manifest: mode selftest, no contract, every file listed."""
    files = {}
    for dirpath, dirnames, filenames in os.walk(parent):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, parent).replace(os.sep, "/")
            if rel == "manifest.json":
                continue
            with open(full, "rb") as fh:
                blob = fh.read()
            files[rel] = {"sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}
    path = os.path.join(parent, "manifest.json")
    if os.path.exists(path):
        os.chmod(path, 0o600)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"tool": "synthetic", "mode": "selftest", "status": "PASS", "files": files}, fh)


def write_snapshot(root, data=None, status="RECONCILED", version=4, synthetic=True, extra=None,
                   layout="flat", sealed=True):
    """Write a snapshot ``<id>`` directory and return its path (which may differ from ``root``).

    ``synthetic`` writes the real selftest shape: ``<root>-selftest/run-1`` and ``run-2``
    (each an ``extract``-mode run with ``origin_kind`` ``production``) under a parent
    ``manifest.json`` of ``mode`` ``selftest``, sealed unless ``sealed`` is False; the
    ``run-1`` path is returned. Otherwise ``<root>-extract`` is written and returned.
    ``layout`` ``flat`` (client credentials) puts ``manifest.json`` at ``<id>/``; ``legacy``
    writes ``<id>/input/waiver.json`` and the run under ``<id>/run/``.
    """
    data = org(account_marker=synthetic) if data is None else data
    if synthetic:
        parent = root if root.endswith("-selftest") else root + "-selftest"
        os.makedirs(parent, mode=0o700)
        for run in ("run-2", "run-1"):
            out = write_snapshot(os.path.join(parent, run), data, status, version, False, extra, layout,
                                 sealed=False)
        write_selftest_manifest(parent)
        if sealed:
            seal(parent)
        return out
    if not os.path.basename(root).endswith("-extract") and os.path.basename(root) not in ("run-1", "run-2"):
        root = root + "-extract"
    os.makedirs(root, mode=0o700)
    if layout == "legacy":
        os.makedirs(os.path.join(root, "input"), mode=0o700)
        with open(os.path.join(root, "input", "waiver.json"), "w", encoding="utf-8") as fh:
            json.dump({"waiver": "synthetic " + SENTINEL}, fh)
        _write_run(os.path.join(root, "run"), data, status, version, synthetic, extra)
    else:
        assert layout == "flat"
        _write_run(root, data, status, version, synthetic, extra)
    return root


def snapshot_ref(snapshot_dir, **override):
    """The ``snapshot`` object a reconcile run of ``snapshot_dir`` records (real key set)."""
    from crm_load.snapshot import locate
    with open(os.path.join(locate(snapshot_dir), "manifest.json"), encoding="utf-8") as fh:
        m = json.load(fh)
    ref = {"contract_sha256": m["contract"]["sha256"], "contract_version": m["contract"]["version"],
           "overlap_seconds": 300, "passes": 2, "quiet": True, "status": m["status"], "t_start": m["t_start"]}
    ref.update(override)
    return ref


def write_reconcile_run(root, reconciliation, mode="reconcile", listed=True, snapshot=None,
                        layout="report"):
    """A sealed reconcile run directory in the real layout and return it.

    ``layout`` ``report`` (real): ``<id>/report/{manifest.json,reconciliation.json,
    reconciliation.md}``, ``files`` keys relative to ``report/``. ``snapshot-style`` (the
    old, now refused, layout): ``<id>/manifest.json`` with ``report/reconciliation.json``.
    ``snapshot`` is the ``snapshot`` object written into ``reconciliation.json``.
    """
    doc = dict(reconciliation)
    if snapshot is not None:
        doc["snapshot"] = snapshot
    report = os.path.join(root, "report")
    os.makedirs(report, mode=0o700)
    blobs = {"reconciliation.json": json.dumps(doc).encode("utf-8"),
             "reconciliation.md": b"# Reconciliation (synthetic)\n"}
    if not listed:
        del blobs["reconciliation.json"]
    files = {}
    for name, blob in blobs.items():
        with open(os.path.join(report, name), "wb") as fh:
            fh.write(blob)
        key = name if layout == "report" else f"report/{name}"
        files[key] = {"sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}
    manifest = {"tool": "synthetic", "mode": mode, "previous": True, "snapshot_status": "RECONCILED",
                "files": files}
    mdir = report if layout == "report" else root
    assert layout in ("report", "snapshot-style")
    with open(os.path.join(mdir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    return root


def _write_run(root, data, status, version, _synthetic, extra):
    os.makedirs(root, mode=0o700, exist_ok=True)
    files = {}

    def put(rel, blob):
        full = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(blob)
        files[rel] = {"sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}

    for obj, rows in data.items():
        put(f"objects/{obj}.jsonl.gz", _gz(rows))
        if obj in SOFT:
            put(f"deleted/{obj}.jsonl.gz", _gz([]))
    effective = {o: {"ownerCheck": "OwnerId" in f, "softDelete": o in SOFT, "changeKey": "SystemModstamp",
                     "fields": f, "unavailable": []} for o, f in FIELDS_V4.items()}
    for o, via in VISIBLE_VIA.items():
        effective[o]["visibleVia"] = via
    manifest = {"tool": "synthetic", "mode": "extract", "origin_kind": "production", "status": status,
                "t_start": "2026-11-01T00:00:00Z",
                "contract": {"version": version, "sha256": "0" * 64, "effective": effective},
                "files": files}
    manifest.update(extra or {})
    with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)


class FakeEspo:
    """In-memory EspoCRM 10.0.12 REST subset. Records every write; deletes are impossible."""

    ENTITIES = ("User", "ServiceType", "Account", "Contact", "Opportunity", "Task", "Call", "Meeting", "Email")

    # entityDefs defaults the server stores when an attribute is omitted on create (10.0.12 + custom).
    DEFAULTS = {"Account": {"learningPlatformAccess": "No"}, "Opportunity": {"stage": "Enquiry"},
                "Call": {"duration": 300, "direction": "Outbound"},
                "Task": {"status": "Not Started", "priority": "Normal"}}
    # Enums without "" in their options: null and "" are refused (400 valid). The custom one is
    # read from the entityDefs, so removing its "" option makes this fake refuse a blank again.
    CORE_NO_BLANK = {"Opportunity": {"stage"}, "Task": {"status", "priority"}, "Call": {"direction"}}
    # Core enums validated on save (PL-verified on crm-dev): a value outside the options is 400 valid.
    CORE_OPTIONS = {"Contact": {"salutationName": ("", "Mr.", "Ms.", "Mrs.", "Dr.")}}
    # text/wysiwyg attributes are stored verbatim; every other string is trimmed (StringTrim).
    TEXT = {"description", "body", "bodyPlain", "keyInformation"}
    SETTINGS_REFUSED = object()
    NULL_ACCEPTED = {("Meeting", "meetingType")}     # PL-verified: explicit null accepted, reads back null
    # 10.0.12 refusals (PL-verified, CRM-008). assignedUser is required on these entities.
    OWNER_REQUIRED = ("Task", "Call", "Meeting")
    # varchar maxLength (same values as mapping.json maxLength, copied so a wrong table there
    # is caught here). Every phone number is limited to PHONE_MAX_LENGTH.
    MAX_LENGTH = {"ServiceType": {"name": 150},
                  "Account": {"name": 249, "billingAddressCity": 100, "billingAddressState": 100,
                              "billingAddressCountry": 100, "billingAddressPostalCode": 40,
                              "shippingAddressCity": 100, "shippingAddressState": 100,
                              "shippingAddressCountry": 100, "shippingAddressPostalCode": 40},
                  "Contact": {"title": 255, "addressCity": 100, "addressState": 100, "addressCountry": 100,
                              "addressPostalCode": 40},
                  "Opportunity": {"sfStageName": 100, "sfLeadSource": 100, "clientReference": 100,
                                  "caseNumber": 100}}
    PHONE_MAX_LENGTH = 36
    # Settings before provisioning: the 10.0.12 install default currency list.
    DEFAULT_CURRENCY_LIST = ["USD"]
    # An approximation of PHP FILTER_VALIDATE_EMAIL, independent of crm_load.mapping.
    _EMAIL = re.compile(r"\A[^@\s\"(),:;<>\[\]\\]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\Z")

    def __init__(self, users=(U1, U2, U_INACTIVE, U_SHARED), hidden_sfids=(), phone_international=False,
                 settings=None):
        self.phone_international = phone_international
        # GET Settings: by default it reports phoneNumberInternational as the phone rule above.
        # The server's currency list; GET Settings reports it unless ``settings`` is given.
        self.currency_list = list(self.DEFAULT_CURRENCY_LIST)
        self.settings = ({"phoneNumberInternational": phone_international,
                          "currencyList": list(self.currency_list)} if settings is None else settings)
        self.headers = []
        self.db = {e: {} for e in self.ENTITIES}
        self.writes = []
        self.requests = []
        self.hidden = set(hidden_sfids)    # soft-deleted EspoCRM rows holding a unique sfId
        self.fail_next = []                # statuses to return before serving (e.g. 429, 503)
        self._n = 0
        for u in users:
            self._insert("User", {"sfId": u, "userName": "x"})

    def _insert(self, entity, attrs):
        self._n += 1
        rid = f"{entity[:2].lower()}{self._n:015d}"
        self.db[entity][rid] = dict(attrs, id=rid)
        return rid

    def send(self, method, path, query=None, body=None, headers=None):
        self.requests.append((method, path))
        self.headers.append(dict(headers or {}))
        if self.fail_next:
            return self.fail_next.pop(0), None
        parts = path.split("/")
        entity = parts[0]
        if entity == "Settings" and method == "GET":
            if self.settings is self.SETTINGS_REFUSED:
                return 403, None
            return 200, json.loads(json.dumps(self.settings))
        if entity == "Settings" and method == "PUT":
            if self.settings is self.SETTINGS_REFUSED:
                return 403, None
            self.writes.append((method, entity, json.loads(json.dumps(body))))
            self.settings.update(json.loads(json.dumps(body)))
            if "currencyList" in body:
                self.currency_list = list(body["currencyList"])
            return 200, json.loads(json.dumps(self.settings))
        if entity not in self.db:
            return 404, None
        if method == "GET":
            q = dict(query or [])
            assert int(q["maxSize"]) <= 200
            attr = q["where[0][attribute]"]
            assert q["where[0][type]"] == "isNotNull"
            select = q["select"].split(",")
            rows = [r for _, r in sorted(self.db[entity].items()) if r.get(attr) not in (None, "")]
            off, size = int(q["offset"]), int(q["maxSize"])
            page = [{k: json.loads(json.dumps(r.get(k))) for k in select} for r in rows[off:off + size]]
            return 200, {"total": len(rows), "list": page}
        if method == "POST":
            self.writes.append((method, entity, json.loads(json.dumps(body))))
            key = body.get("sfId")
            # A unique-index violation on sfId is an uncaught PDOException in 10.0.12: HTTP 500.
            if key and (key in self.hidden or any(r.get("sfId") == key for r in self.db[entity].values())):
                return 500, None
            # DuplicateConflict (409) on the name, unless X-Skip-Duplicate-Check is sent.
            if (headers or {}).get("X-Skip-Duplicate-Check") != "true" and body.get("name") and any(
                    r.get("name") == body["name"] for r in self.db[entity].values()):
                return 409, None
            if entity == "Opportunity" and not self._roles_valid(body):
                return 400, None
            if entity in ("Call", "Meeting") and not body.get("dateStart"):
                return 400, {"field": "dateStart", "type": "required"}
            refused = self._enum_refused(entity, body)
            if refused:
                return 400, {"field": refused, "type": "valid"}
            refused = self._refused(entity, body, create=True)
            if refused:
                return 400, refused
            stored, bad = self._server_side(entity, body)
            if bad:
                return 400, {"field": "phoneNumber", "type": "valid"}
            for attr, default in self.DEFAULTS.get(entity, {}).items():
                stored.setdefault(attr, default)               # omitted: the entityDefs default
            rid = self._insert(entity, stored)
            if entity == "Email":
                self.db[entity][rid]["messageId"] = f"dummy:{rid}"     # always replaced
            return 200, {"id": rid}
        if method == "PUT":
            self.writes.append((method, entity, json.loads(json.dumps(body))))
            rec = self.db[entity].get(parts[1])
            if rec is None:
                return 404, None
            if entity == "Opportunity" and not self._roles_valid(body):
                return 400, None
            refused = self._enum_refused(entity, body)
            if refused:
                return 400, {"field": refused, "type": "valid"}
            refused = self._refused(entity, body, create=False, current=rec)
            if refused:
                return 400, refused
            stored, bad = self._server_side(entity, body)
            if bad:
                return 400, {"field": "phoneNumber", "type": "valid"}
            stored.pop("messageId", None)
            rec.update(stored)
            return 200, dict(rec)
        return 405, None

    # Each check can be switched off (mutation tests prove each one is exercised).
    CHECKS = ("owner", "max_length", "currency", "email")

    def _refused(self, entity, body, create, current=None):
        """The 400 body EspoCRM 10.0.12 returns for ``body``, or None (CRM-008 refusals)."""
        checks = set(self.CHECKS) - getattr(self, "disabled_checks", set())
        if "owner" in checks and entity in self.OWNER_REQUIRED and \
                (create or "assignedUserId" in body) and body.get("assignedUserId") in (None, ""):
            return {"field": "assignedUser", "type": "required"}
        if "max_length" in checks:
            for attr, limit in self.MAX_LENGTH.get(entity, {}).items():
                v = body.get(attr)
                if isinstance(v, str) and len(v.strip()) > limit:
                    return {"field": attr, "type": "maxLength"}
            phones = [body.get("phoneNumber")] + [p.get("phoneNumber") for p in body.get("phoneNumberData") or []]
            if any(isinstance(n, str) and len(n.strip()) > self.PHONE_MAX_LENGTH for n in phones):
                return {"field": "phoneNumber", "type": "maxLength"}
        if "currency" in checks and body.get("amount") is not None:
            currency = body.get("amountCurrency", (current or {}).get("amountCurrency"))
            if currency not in self.currency_list:
                return {"field": "amount", "type": "validCurrency"}
        if "email" in checks and entity == "Email":
            if (create or "from" in body) and (not isinstance(body.get("from"), str) or not body["from"].strip()):
                return {"field": "from", "type": "required"}
            for attr in ("to", "cc", "from"):
                v = body.get(attr)
                if not isinstance(v, str) or (attr == "from" and "<" in v):
                    continue                     # a display name in from is dropped, not refused
                if any(not self._EMAIL.match(a.strip()) for a in v.split(";") if a.strip()):
                    return {"field": attr, "type": "valid"}
        return None

    def provision_settings(self, path=None):
        """Apply config/settings.json through the real scripts/provision_access.ensure_settings."""
        scripts = os.path.join(ROOT, "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import crm_api
        import provision_access
        client = crm_api.EspoClient("http://fake.example.test", "admin", "x", transport=self)
        counter = provision_access.Counter()
        desired = provision_access.load_settings(path or provision_access.SETTINGS_FILE)
        provision_access.ensure_settings(client, desired, counter)
        return counter.counts

    def request(self, method, url, headers, body):
        """scripts/crm_api.py transport interface onto ``send``."""
        parsed = urllib.parse.urlsplit(url)
        path = parsed.path.split("/api/v1/", 1)[1]
        status, data = self.send(method, path, urllib.parse.parse_qsl(parsed.query),
                                 None if body is None else json.loads(body), headers)
        return status, (b"" if data is None else json.dumps(data).encode("utf-8"))

    def _no_blank(self, entity):
        fields = set(self.CORE_NO_BLANK.get(entity, ()))
        path = os.path.join(ROOT, "custom", "Espo", "Custom", "Resources", "metadata", "entityDefs",
                            f"{entity}.json")
        if os.path.exists(path):
            with open(path) as fh:
                for name, f in json.load(fh).get("fields", {}).items():
                    if f.get("type") == "enum" and "" not in f.get("options", [""]) and \
                            (entity, name) not in self.NULL_ACCEPTED:
                        fields.add(name)
        return fields

    def _enum_refused(self, entity, body):
        for attr in self._no_blank(entity):
            if attr in body and body[attr] in (None, ""):
                return attr
        for attr, options in self.CORE_OPTIONS.get(entity, {}).items():
            if body.get(attr) is not None and body[attr] not in options:
                return attr
        return None

    def _phone(self, number):
        """(stored value, refused) as EspoCRM 10.0.12 with the phoneNumberInternational setting."""
        if not isinstance(number, str):
            return number, True
        if self.phone_international:
            if not number.startswith("+"):
                return number, True                      # UK national formats refused
            digits = "".join(c for c in number if c.isdigit())
            return "+" + digits, not digits
        if not any(c.isdigit() for c in number) or any(c.isalpha() or c == "/" for c in number):
            return number, True                          # junk such as n/a
        return number.strip(), False                     # stored trimmed (PL-verified on crm-dev)

    def _server_side(self, entity, body):
        """What the server stores for ``body``, and whether a phone was refused."""
        stored = json.loads(json.dumps(body))
        bad = False
        if stored.get("phoneNumber") is not None:
            stored["phoneNumber"], refused = self._phone(stored["phoneNumber"])
            bad = bad or refused
        if isinstance(stored.get("phoneNumberData"), list):
            data = []
            for p in stored["phoneNumberData"]:
                number, refused = self._phone(p.get("phoneNumber"))
                bad = bad or refused
                data.append(dict(p, phoneNumber=number, optOut=False, invalid=False))
            stored["phoneNumberData"] = data
        for attr, value in stored.items():
            if isinstance(value, str) and attr not in self.TEXT and attr not in ("phoneNumber",):
                stored[attr] = value.strip()                 # StringTrim on varchar
        if entity == "Call" and "duration" in stored and stored["duration"] is None:
            stored["duration"] = 0                           # derived from dateEnd - dateStart
        if entity == "Email" and isinstance(stored.get("from"), str) and "<" in stored["from"]:
            stored["from"] = None                        # a display name in from is dropped
        if entity == "Email":
            stored.pop("messageId", None)                # cannot be set through the API
        return stored, bad

    ROLE_OPTIONS = ("", "Business User", "Decision Maker", "Economic Buyer", "Economic Decision Maker",
                    "Evaluator", "Executive Sponsor", "Influencer", "Technical Buyer", "Other")

    def _roles_valid(self, body):
        """Core validates contactsColumns.role against Contact.opportunityRole.options (columnsValid)."""
        cols = body.get("contactsColumns") or {}
        return all(c.get("role") in self.ROLE_OPTIONS for c in cols.values())

    def by_sf(self, entity, key="sfId"):
        return {r[key]: r for r in self.db[entity].values() if r.get(key)}
