"""Pure mapping from snapshot rows to EspoCRM attribute dicts (per load/contract/mapping.json).

Every function returns ``(attrs, exception_codes)``. ``attrs`` hold only target attributes;
missing source values become ``None`` (never invented). Exception codes come from
``EXCEPTION_CODES``.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone

from .errors import LoadError

CONTRACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "contract")

EXCEPTION_CODES = frozenset({
    "owner_queue_or_group", "owner_unresolved",
    "account_unresolved", "parent_unresolved", "contact_unresolved", "opportunity_unresolved",
    "activity_parent_unresolved",
    "enum_unmapped", "stage_unmapped", "status_unmapped",
    "name_unparsed",
    "exists_soft_deleted_in_sf", "exists_not_in_snapshot",
    "duplicate_conflict", "write_rejected", "write_failed",
    "role_unmapped",
    "user_not_exportable",
    "datetime_invalid",
    "phone_rejected",
    "call_direction_unknown",
    "date_start_from_activity_date", "date_start_from_created",
    "value_shape",
    "parent_soft_deleted_in_sf",
    "enum_blank_unrepresentable", "call_duration_unknown", "phone_refused",
    "synthetic_enum_mapped",
    # CRM-008
    "owner_required_unresolved", "task_email_imported_as_task", "value_too_long",
    "email_address_invalid", "email_from_invalid", "service_type_refused",
    # CRM-008-F
    "title_unstorable_without_account", "date_completed_not_storable",
    "email_without_recipient_imported_as_task", "owner_from_created_by", "priority_server_default",
})
# Codes that refuse the record: it is never sent (CRM-008).
REFUSING_CODES = frozenset({"owner_required_unresolved", "email_from_invalid"})
# Core entities whose assignedUser is required: true in EspoCRM 10.0.12 (CRM-008 fact 3).
OWNER_REQUIRED = frozenset({"Task", "Call", "Meeting"})

# Every source field a mapping function reads, per object (besides those named in
# mapping.json copy/enum). A dict or list in any of them is ``value_shape`` for that record.
SOURCE_FIELDS = {
    "Account": ("OwnerId", "CreatedDate", "ParentId"),
    "Contact": ("OwnerId", "CreatedDate", "AccountId", "Phone", "MobilePhone"),
    "Opportunity": ("OwnerId", "CreatedDate", "AccountId", "CloseDate", "StageName", "Loss_Reason__c",
                    "Opportunity_Service__c", "LeadSource", "Name"),
    "OpportunityContactRole": ("OpportunityId", "ContactId", "Role"),
    "Task": ("OwnerId", "CreatedDate", "Subject", "WhatId", "AccountId", "WhoId", "CompletedDateTime",
             "TaskSubtype", "Status", "Priority", "ActivityDate", "Description", "CallType",
             "CallDurationInSeconds"),
    "Event": ("OwnerId", "CreatedDate", "Subject", "Type", "StartDateTime", "ActivityDateTime", "EndDateTime",
              "IsAllDayEvent", "Description", "WhatId", "AccountId"),
    "EmailMessage": ("CreatedDate", "Subject", "FromName", "FromAddress", "ToAddress", "CcAddress", "TextBody",
                     "MessageDate", "ThreadIdentifier", "ActivityId", "RelatedToId"),
    "EmailMessageRelation": ("EmailMessageId", "RelationId"),
}
_ENTITY_OF = {"Account": "Account", "Contact": "Contact", "Opportunity": "Opportunity"}
_DIGIT = re.compile(r"[0-9]")

_SF_DT = re.compile(r"\A(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})\Z")
_DATE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")


def load_json(name, directory=None):
    path = os.path.join(directory or CONTRACT_DIR, name)
    try:
        with open(path, "rb") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        raise LoadError("contract_file_unreadable") from None


def blank(value):
    return value is None or (isinstance(value, str) and value.strip() == "")


def text(value):
    return None if blank(value) else value


def espo_datetime(value):
    """Salesforce ISO datetime -> EspoCRM 'YYYY-MM-DD HH:MM:SS' UTC. Raises ValueError."""
    if blank(value):
        return None
    m = _SF_DT.fullmatch(value)
    if not m:
        raise ValueError("datetime")
    tz = m.group(3)
    if tz == "Z":
        offset = timedelta(0)
    else:
        sign = 1 if tz[0] == "+" else -1
        digits = tz[1:].replace(":", "")
        offset = sign * timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
    dt = datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S") - offset
    return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def espo_date(value):
    if blank(value):
        return None
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise ValueError("date")
    return value


def check_shape(obj, row, mapping):
    """Raise LoadError('value_shape') if a field the mapping reads holds a dict or a list."""
    fields = set(SOURCE_FIELDS.get(obj, ()))
    spec = mapping["entities"].get(_ENTITY_OF.get(obj, ""), {})
    fields |= set(spec.get("copy", {}).values()) | set(spec.get("enum", {}).values())
    for f in fields:
        if isinstance(row.get(f), (dict, list)):
            raise LoadError("value_shape")


def phone_usable(value):
    """A phone worth sending: a string holding at least one digit. 'n/a' and the like are not."""
    return isinstance(value, str) and bool(_DIGIT.search(value))


# A conservative approximation of PHP FILTER_VALIDATE_EMAIL, which EspoCRM uses for
# email addresses (CRM-008 change 6). Anything it accepts, PHP accepts; some addresses PHP
# accepts are refused here (quoted local parts, IP-literal domains, non-ASCII, numeric
# TLDs): a borderline address is dropped rather than sent and refused by the server.
_LOCAL_ATOM = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_EMAIL = re.compile(rf"\A{_LOCAL_ATOM}(?:\.{_LOCAL_ATOM})*@(?:{_LABEL}\.)+[A-Za-z]{{2,63}}\Z")


def email_valid(value):
    """True for an address EspoCRM accepts: dot-atom local part (at most 64 characters), a
    dotted domain of LDH labels (each 1-63, no leading or trailing hyphen) ending in an
    alphabetic TLD, 254 characters at most, ASCII only, no whitespace."""
    if not isinstance(value, str) or len(value) > 254 or not value.isascii():
        return False
    if not _EMAIL.fullmatch(value):
        return False
    return len(value.rsplit("@", 1)[0]) <= 64


def addresses(value, exc=None):
    """Salesforce address list ('a; b' or 'a, b') -> ';'-separated, or None.

    With ``exc``, an invalid address is dropped from the list (email_address_invalid)."""
    if blank(value):
        return None
    parts = [p.strip() for p in re.split(r"[;,]", value) if p.strip()]
    if exc is not None:
        valid = [p for p in parts if email_valid(p)]
        if len(valid) != len(parts):
            exc.append("email_address_invalid")
        parts = valid
    return ";".join(parts) or None


class Mapper:
    def __init__(self, mapping, lead_map, name_parser, as_of, t_start=None, synthetic=False):
        self.m = mapping
        # Selftest only: a real snapshot never consults syntheticEnumMap.
        self.synthetic_map = mapping.get("syntheticEnumMap", {}) if synthetic is True else {}
        self.lead_map = lead_map.get("map", {}) if isinstance(lead_map, dict) else {}
        self.names = name_parser
        self.as_of = as_of
        self.t_start = t_start          # manifest t_start as 'YYYY-MM-DD HH:MM:SS' UTC
        self.prefixes = mapping["keyPrefixes"]

    # ---------------------------------------------------------------- helpers
    def _enum(self, key, value, exc):
        if blank(value):
            return None
        if value in self.m["enums"][key]:
            return value
        exc.append("enum_unmapped")
        return None

    def _synthetic(self, key, value, exc=None):
        """The selftest-only target for a synthetic picklist value, or None (always None for a
        real snapshot). A use is recorded as synthetic_enum_mapped when ``exc`` is given."""
        table = self.synthetic_map.get(key)
        target = table.get(value) if isinstance(table, dict) and isinstance(value, str) else None
        if target is not None and exc is not None:
            exc.append("synthetic_enum_mapped")
        return target

    def _dt(self, value, exc):
        try:
            return espo_datetime(value)
        except (ValueError, TypeError):
            exc.append("datetime_invalid")
            return None

    def _date(self, value, exc):
        try:
            return espo_date(value)
        except (ValueError, TypeError):
            exc.append("datetime_invalid")
            return None

    def ref(self, obj, sf_id, ctx, exc, code):
        """The EspoCRM id of a current ``obj`` record, never one soft-deleted in the snapshot."""
        if blank(sf_id):
            return None
        if ctx.soft_deleted(sf_id):
            exc.append("parent_soft_deleted_in_sf")
            return None
        rid = ctx.record_id(obj, sf_id)
        if rid is None and code:
            exc.append(code)
        return rid

    def object_of(self, sf_id):
        if not isinstance(sf_id, str) or len(sf_id) < 3:
            return None
        return self.prefixes.get(sf_id[:3])

    def _simple(self, entity, row, exc):
        spec = self.m["entities"][entity]
        attrs = {a: text(row.get(src)) for a, src in spec.get("copy", {}).items()}
        for a, src in spec.get("enum", {}).items():
            attrs[a] = self._enum(f"{entity}.{a}", row.get(src), exc)
        return attrs

    def owner(self, row, ctx, exc):
        """Owner resolution: a provisioned user, or empty with an exception. Never guessed."""
        owner = row.get("OwnerId")
        if blank(owner):
            exc.append("owner_unresolved")
            return None
        uid = ctx.user_id(owner)
        if uid is not None:
            return uid
        exc.append("owner_queue_or_group" if self.object_of(owner) == "Group" else "owner_unresolved")
        return None

    def _legacy(self, row, ctx, exc, owner=True):
        out = {"sfId": row["Id"], "sfCreatedAt": self._dt(row.get("CreatedDate"), exc)}
        if owner:
            out["sfOwnerId"] = text(row.get("OwnerId"))
            out["assignedUserId"] = self.owner(row, ctx, exc)
        return out

    @staticmethod
    def require_owner(attrs, exc):
        """Task, Call and Meeting need an owner (core required): an unresolved one refuses the
        record (owner_required_unresolved). The owner is never guessed; no placeholder."""
        if attrs.get("assignedUserId") is None:
            if "owner_unresolved" in exc:
                exc.remove("owner_unresolved")
            exc.append("owner_required_unresolved")

    def _parent(self, row, ctx, exc):
        """parent from WhatId by key prefix (Opportunity or Account), falling back to AccountId.

        A reference to a record soft-deleted in the snapshot is never linked."""
        deleted = False
        for field in ("WhatId", "AccountId"):
            ref = row.get(field)
            if blank(ref):
                continue
            obj = self.object_of(ref)
            if ctx.soft_deleted(ref):
                deleted = True
                continue
            if obj in ("Opportunity", "Account"):
                pid = ctx.record_id(obj, ref)
                if pid is not None:
                    return obj, pid
        if deleted:
            exc.append("parent_soft_deleted_in_sf")
        elif not blank(row.get("WhatId")) or not blank(row.get("AccountId")):
            exc.append("activity_parent_unresolved")
        return None, None

    def _who_contacts(self, row, ctx):
        who = row.get("WhoId")
        if self.object_of(who) == "Contact" and not ctx.soft_deleted(who):
            cid = ctx.record_id("Contact", who)
            if cid is not None:
                return [cid]
        return []

    # ---------------------------------------------------------------- entities
    @staticmethod
    def phones(row, exc):
        """Phone (Office, primary when present) and MobilePhone (Mobile) -> phoneNumberData.

        A value with no digit (``n/a``) is never sent: ``phone_rejected``."""
        data = []
        for field, kind in (("Phone", "Office"), ("MobilePhone", "Mobile")):
            if blank(row.get(field)):
                continue
            if not phone_usable(row[field]):
                exc.append("phone_rejected")
                continue
            data.append({"phoneNumber": row[field], "type": kind, "primary": not data})
        return data or None

    def account(self, row, ctx):
        exc = []
        attrs = self._simple("Account", row, exc)
        if attrs.get("phoneNumber") is not None and not phone_usable(attrs["phoneNumber"]):
            exc.append("phone_rejected")
            attrs["phoneNumber"] = None
        attrs.update(self._legacy(row, ctx, exc))
        return attrs, exc

    def account_parent(self, row, ctx):
        exc = []
        ref = row.get("ParentId")
        if blank(ref):
            return {"parentId": None}, exc
        return {"parentId": self.ref("Account", ref, ctx, exc, "parent_unresolved")}, exc

    def contact(self, row, ctx):
        exc = []
        attrs = self._simple("Contact", row, exc)
        attrs["phoneNumberData"] = self.phones(row, exc)
        attrs.update(self._legacy(row, ctx, exc))
        attrs["accountId"] = self.ref("Account", row.get("AccountId"), ctx, exc, "account_unresolved")
        if attrs["accountId"] is None:
            # CRM-008-F fact 2: EspoCRM stores a Contact's title through its account link; without
            # one it reads back null. It is not sent, and not compared.
            if attrs.get("title") is not None:
                exc.append("title_unstorable_without_account")
            attrs.pop("title", None)
        return attrs, exc

    def opportunity(self, row, ctx):
        exc = []
        attrs = self._simple("Opportunity", row, exc)
        attrs.update(self._legacy(row, ctx, exc))
        attrs["amountCurrency"] = self.m["currency"] if attrs.get("amount") is not None else None
        attrs["closeDate"] = self._date(row.get("CloseDate"), exc)
        raw_stage = row.get("StageName")
        stage = self.m["stageMap"].get(raw_stage) if isinstance(raw_stage, str) else None
        if stage is None:
            stage = self._synthetic("Opportunity.StageName", raw_stage, exc)
        if stage is None:
            exc.append("stage_unmapped")
        attrs["stage"] = stage
        close = attrs["closeDate"]
        attrs["legacyStale"] = bool(stage in self.m["staleStages"] and close is not None and close < self.as_of)
        attrs["lossReason"] = self._enum("Opportunity.lossReason", row.get("Loss_Reason__c"), exc)
        attrs["lossReasonLegacyMissing"] = bool(stage == self.m["lostStage"] and attrs["lossReason"] is None)
        attrs["accountId"] = self.ref("Account", row.get("AccountId"), ctx, exc, "account_unresolved")
        service = row.get("Opportunity_Service__c")
        attrs["serviceTypeId"] = None if blank(service) else ctx.service_type_id(service.strip())
        lead = self.lead_map.get(row.get("LeadSource")) if isinstance(row.get("LeadSource"), str) else None
        attrs["introducedById"] = None
        attrs["channel"] = None
        if isinstance(lead, dict):
            if lead.get("introducedBySfUserId"):
                attrs["introducedById"] = ctx.user_id(lead["introducedBySfUserId"])
            if lead.get("channel"):
                attrs["channel"] = self._enum("Opportunity.channel", lead["channel"], exc)
        _code, parsed = self.names.parse(row.get("Name"))
        if _code is None:
            exc.append("name_unparsed")
        for g in ("clientReference", "deceasedName", "caseNumber"):
            attrs[g] = text(parsed.get(g))
        return attrs, exc

    def task_entity(self, row, exc=None, emailed=None):
        """The target entity of a Task row. With ``emailed`` (the ActivityIds of every
        EmailMessage), a Task-Email that no EmailMessage represents is a Task (CRM-008): an
        Email needs a from address, which only an EmailMessage has."""
        sub = row.get("TaskSubtype")
        entity = self.m["taskSubtypeEntity"].get(sub) if isinstance(sub, str) else None
        if entity is None:
            entity = self._synthetic("Task.TaskSubtype", sub, exc)
        entity = entity or "Task"
        if entity == "Email" and emailed is not None and row.get("Id") not in emailed:
            if exc is not None:
                exc.append("task_email_imported_as_task")
            return "Task"
        return entity

    def task(self, row, ctx, emailed=None):
        exc = []
        entity = self.task_entity(row, exc, emailed)
        attrs = self._legacy(row, ctx, exc)
        if entity in OWNER_REQUIRED:
            self.require_owner(attrs, exc)
        attrs["name"] = text(row.get("Subject"))
        ptype, pid = self._parent(row, ctx, exc)
        attrs["parentType"], attrs["parentId"] = ptype, pid
        completed = self._dt(row.get("CompletedDateTime"), exc)
        if entity == "Task":
            status = row.get("Status")
            attrs["status"] = self.m["taskStatusMap"].get(status) if isinstance(status, str) else None
            if attrs["status"] is None:
                attrs["status"] = self._synthetic("Task.Status", status, exc)
            if not blank(status) and attrs["status"] is None:
                exc.append("status_unmapped")
            prio = row.get("Priority")
            attrs["priority"] = self.m["taskPriorityMap"].get(prio) if isinstance(prio, str) else None
            if attrs["priority"] is None:
                attrs["priority"] = self._synthetic("Task.Priority", prio, exc)
            if not blank(prio) and attrs["priority"] is None:
                exc.append("enum_unmapped")
            attrs["dateEndDate"] = self._date(row.get("ActivityDate"), exc)
            # CRM-008-F fact 3: dateCompleted is kept only with status Completed; otherwise it reads
            # back null, so it is neither sent nor compared.
            if attrs["status"] == "Completed":
                attrs["dateCompleted"] = completed
            elif completed is not None:
                exc.append("date_completed_not_storable")
            attrs["description"] = text(row.get("Description"))
        elif entity == "Call":
            attrs["status"] = self.m["callStatus"]
            # direction is sent only when known: EspoCRM shows its core default (Outbound)
            # otherwise, so the attribute is left out, never sent empty, never invented.
            # A blank and an unmapped CallType are treated alike (call_direction_unknown).
            ctype = row.get("CallType")
            if blank(ctype):
                exc.append("call_direction_unknown")
            else:
                direction = self.m["callDirectionMap"].get(ctype) if isinstance(ctype, str) else None
                if direction is None:
                    direction = self._synthetic("Task.CallType", ctype, exc)
                if direction is None:
                    exc.append("enum_unmapped")
                    exc.append("call_direction_unknown")
                else:
                    attrs["direction"] = direction
            attrs["dateStart"] = self._required_start(completed, row.get("ActivityDate"), attrs, exc)
            dur = row.get("CallDurationInSeconds")
            attrs["duration"] = dur if type(dur) is int and dur >= 0 else None
            if attrs["duration"] is None:
                # Sent as explicit null; EspoCRM shows 0 (derived from dateEnd - dateStart).
                exc.append("call_duration_unknown")
            attrs["description"] = text(row.get("Description"))
            attrs["contactsIds"] = self._who_contacts(row, ctx)
        else:
            attrs["status"] = "Archived"
            attrs["bodyPlain"] = text(row.get("Description"))
            attrs["body"] = attrs["bodyPlain"]
            attrs["isHtml"] = False
            attrs["dateSent"] = completed      # not required: never the created date
        return entity, attrs, exc

    def _required_start(self, when, activity_date, attrs, exc):
        """Call/Meeting dateStart is required in core: fall back only with a per-record code."""
        if when is not None:
            return when
        day = self._date(activity_date, exc)
        if day is not None:
            exc.append("date_start_from_activity_date")
            return day + " 00:00:00"
        if attrs.get("sfCreatedAt") is not None:
            exc.append("date_start_from_created")
            return attrs["sfCreatedAt"]
        return None

    def event(self, row, ctx):
        exc = []
        attrs = self._legacy(row, ctx, exc)
        self.require_owner(attrs, exc)
        attrs["name"] = text(row.get("Subject"))
        etype = row.get("Type")
        if blank(etype):
            attrs["meetingType"] = self.m["meetingTypeUntyped"]
        elif isinstance(etype, str) and etype in self.m["enums"]["Meeting.meetingType"]:
            attrs["meetingType"] = etype
        else:
            # Selftest only (CRM-008 change 7): synthetic Event Type values.
            attrs["meetingType"] = self._synthetic("Event.Type", etype, exc)
            if attrs["meetingType"] is None:
                attrs["meetingType"] = self._enum("Meeting.meetingType", etype, exc)
        attrs["dateStart"] = self._required_start(
            self._dt(row.get("StartDateTime") or row.get("ActivityDateTime"), exc), None, attrs, exc)
        attrs["dateEnd"] = self._dt(row.get("EndDateTime"), exc)
        end = attrs["dateEnd"]
        attrs["status"] = "Held" if end is not None and self.t_start is not None and end < self.t_start \
            else "Planned"
        attrs["isAllDay"] = row.get("IsAllDayEvent") is True
        attrs["description"] = text(row.get("Description"))
        ptype, pid = self._parent(row, ctx, exc)
        attrs["parentType"], attrs["parentId"] = ptype, pid
        # Attendees: the owner only. EventRelation is not in the contract.
        attrs["usersIds"] = [attrs["assignedUserId"]] if attrs["assignedUserId"] else []
        return attrs, exc

    def email_message(self, row, relations, task_rows, ctx):
        """EmailMessage (+ its EmailMessageRelation rows) -> archived Email. No Bcc, no HTML."""
        exc = []
        attrs = self._legacy(row, ctx, exc, owner=False)
        attrs["status"] = "Archived"
        attrs["name"] = text(row.get("Subject"))
        # ``from`` takes the bare address only (a display name there makes EspoCRM drop it);
        # the display form goes to fromString.
        attrs["from"] = text(row.get("FromAddress"))
        if attrs["from"] is not None:
            attrs["from"] = attrs["from"].strip()
        if not email_valid(attrs["from"]):
            exc.append("email_from_invalid")         # Email.from is required: refused, never sent
        name = text(row.get("FromName"))
        attrs["fromString"] = (f"{name} <{attrs['from']}>" if name and attrs["from"] else attrs["from"])
        attrs["to"] = addresses(row.get("ToAddress"), exc)
        attrs["cc"] = addresses(row.get("CcAddress"), exc)
        attrs["bodyPlain"] = text(row.get("TextBody"))
        attrs["body"] = attrs["bodyPlain"]
        attrs["isHtml"] = False
        attrs["dateSent"] = self._dt(row.get("MessageDate"), exc)
        # messageId cannot be set through the API (the server writes dummy:<id>): not mapped.
        attrs["sfEmailMessageId"] = row["Id"]
        attrs["sfThreadIdentifier"] = text(row.get("ThreadIdentifier"))
        attrs["sfActivityId"] = text(row.get("ActivityId"))
        attrs["parentType"], attrs["parentId"] = self._email_parent(row, task_rows, ctx, exc)
        users = []
        for rel in relations:
            rid = rel.get("RelationId")
            if self.object_of(rid) == "User":
                uid = ctx.user_id(rid)
                if uid is not None and uid not in users:
                    users.append(uid)
        attrs["usersIds"] = sorted(users)
        attrs["assignedUserId"] = None
        attrs["sfOwnerId"] = None
        return attrs, exc

    def email_message_as_task(self, row, task_rows, ctx):
        """CRM-008-F change 4: an EmailMessage whose To list is empty after validation (Email.to
        is required) -> Task, as the CRM-008 Task-Email rule: Subject is the name, TextBody the
        description, status Completed, dateCompleted from MessageDate, the parent as for the Email.
        The owner is the linked Task's (ActivityId); if there is none or it doesn't resolve, the
        EmailMessage's CreatedById when it is a provisioned user (owner_from_created_by, a recorded
        fact); otherwise the record is refused (owner_required_unresolved). Never guessed.
        priority has no source and is not sent: core default Normal (priority_server_default)."""
        exc = []
        addresses(row.get("ToAddress"), exc)
        addresses(row.get("CcAddress"), exc)
        attrs = self._legacy(row, ctx, exc, owner=False)
        linked = task_rows.get(row.get("ActivityId")) if isinstance(row.get("ActivityId"), str) else None
        owner_exc = []
        attrs["sfOwnerId"] = text(linked.get("OwnerId")) if linked else None
        attrs["assignedUserId"] = self.owner(linked, ctx, owner_exc) if linked else None
        created_by = row.get("CreatedById")
        if attrs["assignedUserId"] is None and isinstance(created_by, str) and ctx.user_id(created_by) is not None:
            # Fallback (CRM-008-F round 2): the Salesforce user who logged the message. The linked
            # Task's owner_unresolved/owner_queue_or_group is dropped: the record has an owner.
            attrs["sfOwnerId"] = created_by
            attrs["assignedUserId"] = ctx.user_id(created_by)
            exc.append("owner_from_created_by")
        else:
            exc.extend(owner_exc)
        self.require_owner(attrs, exc)
        exc.append("priority_server_default")
        attrs["name"] = text(row.get("Subject"))
        attrs["status"] = "Completed"
        attrs["dateEndDate"] = None
        attrs["dateCompleted"] = self._dt(row.get("MessageDate"), exc)
        attrs["description"] = text(row.get("TextBody"))
        attrs["parentType"], attrs["parentId"] = self._email_parent(row, task_rows, ctx, exc)
        exc.append("email_without_recipient_imported_as_task")
        return attrs, exc

    def _email_parent(self, row, task_rows, ctx, exc):
        """parent: RelatedToId (Opportunity/Account), else the linked Task's parent."""
        ptype = pid = None
        related = row.get("RelatedToId")
        deleted = False
        if not blank(related) and ctx.soft_deleted(related):
            deleted = True
        elif self.object_of(related) in ("Opportunity", "Account"):
            pid = ctx.record_id(self.object_of(related), related)
            ptype = self.object_of(related) if pid else None
        if pid is None and not blank(row.get("ActivityId")) and row["ActivityId"] in task_rows:
            sub = []
            ptype, pid = self._parent(task_rows[row["ActivityId"]], ctx, sub)
            deleted = deleted or "parent_soft_deleted_in_sf" in sub
        if pid is None and deleted:
            exc.append("parent_soft_deleted_in_sf")
        elif pid is None and (not blank(related) or not blank(row.get("ActivityId"))):
            exc.append("activity_parent_unresolved")
        return ptype, pid
