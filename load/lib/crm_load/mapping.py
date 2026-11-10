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
})

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


def addresses(value):
    """Salesforce address list ('a; b' or 'a, b') -> ';'-separated, or None."""
    if blank(value):
        return None
    parts = [p.strip() for p in re.split(r"[;,]", value) if p.strip()]
    return ";".join(parts) or None


class Mapper:
    def __init__(self, mapping, lead_map, name_parser, as_of, t_start=None):
        self.m = mapping
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

    def _parent(self, row, ctx, exc):
        """parent from WhatId by key prefix (Opportunity or Account), falling back to AccountId."""
        for field in ("WhatId", "AccountId"):
            ref = row.get(field)
            if blank(ref):
                continue
            obj = self.object_of(ref)
            if obj in ("Opportunity", "Account"):
                pid = ctx.record_id(obj, ref)
                if pid is not None:
                    return obj, pid
            if field == "WhatId":
                continue
        if not blank(row.get("WhatId")) or not blank(row.get("AccountId")):
            exc.append("activity_parent_unresolved")
        return None, None

    def _who_contacts(self, row, ctx):
        who = row.get("WhoId")
        if self.object_of(who) == "Contact":
            cid = ctx.record_id("Contact", who)
            if cid is not None:
                return [cid]
        return []

    # ---------------------------------------------------------------- entities
    @staticmethod
    def phones(row):
        """Phone (Office, primary when present) and MobilePhone (Mobile) -> phoneNumberData."""
        data = []
        for field, kind in (("Phone", "Office"), ("MobilePhone", "Mobile")):
            if not blank(row.get(field)):
                data.append({"phoneNumber": row[field], "type": kind, "primary": not data})
        return data or None

    def account(self, row, ctx):
        exc = []
        attrs = self._simple("Account", row, exc)
        attrs.update(self._legacy(row, ctx, exc))
        return attrs, exc

    def account_parent(self, row, ctx):
        exc = []
        ref = row.get("ParentId")
        if blank(ref):
            return {"parentId": None}, exc
        pid = ctx.record_id("Account", ref)
        if pid is None:
            exc.append("parent_unresolved")
        return {"parentId": pid}, exc

    def contact(self, row, ctx):
        exc = []
        attrs = self._simple("Contact", row, exc)
        attrs["phoneNumberData"] = self.phones(row)
        attrs.update(self._legacy(row, ctx, exc))
        attrs["accountId"] = None
        if not blank(row.get("AccountId")):
            attrs["accountId"] = ctx.record_id("Account", row["AccountId"])
            if attrs["accountId"] is None:
                exc.append("account_unresolved")
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
            exc.append("stage_unmapped")
        attrs["stage"] = stage
        close = attrs["closeDate"]
        attrs["legacyStale"] = bool(stage in self.m["staleStages"] and close is not None and close < self.as_of)
        attrs["lossReason"] = self._enum("Opportunity.lossReason", row.get("Loss_Reason__c"), exc)
        attrs["lossReasonLegacyMissing"] = bool(stage == self.m["lostStage"] and attrs["lossReason"] is None)
        attrs["accountId"] = None
        if not blank(row.get("AccountId")):
            attrs["accountId"] = ctx.record_id("Account", row["AccountId"])
            if attrs["accountId"] is None:
                exc.append("account_unresolved")
        service = row.get("Opportunity_Service__c")
        attrs["serviceTypeId"] = None if blank(service) else ctx.service_type_id(service)
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

    def task_entity(self, row):
        return self.m["taskSubtypeEntity"].get(row.get("TaskSubtype"), "Task")

    def task(self, row, ctx):
        exc = []
        entity = self.task_entity(row)
        attrs = self._legacy(row, ctx, exc)
        attrs["name"] = text(row.get("Subject"))
        ptype, pid = self._parent(row, ctx, exc)
        attrs["parentType"], attrs["parentId"] = ptype, pid
        when = self._dt(row.get("CompletedDateTime"), exc) or attrs["sfCreatedAt"]
        if entity == "Task":
            status = row.get("Status")
            attrs["status"] = self.m["taskStatusMap"].get(status) if isinstance(status, str) else None
            if not blank(status) and attrs["status"] is None:
                exc.append("status_unmapped")
            prio = row.get("Priority")
            attrs["priority"] = self.m["taskPriorityMap"].get(prio) if isinstance(prio, str) else None
            if not blank(prio) and attrs["priority"] is None:
                exc.append("enum_unmapped")
            attrs["dateEndDate"] = self._date(row.get("ActivityDate"), exc)
            attrs["dateCompleted"] = self._dt(row.get("CompletedDateTime"), exc)
            attrs["description"] = text(row.get("Description"))
        elif entity == "Call":
            attrs["status"] = self.m["callStatus"]
            ctype = row.get("CallType")
            if blank(ctype):
                attrs["direction"] = self.m["callDirectionDefault"]
            else:
                attrs["direction"] = self.m["callDirectionMap"].get(ctype) if isinstance(ctype, str) else None
                if attrs["direction"] is None:
                    exc.append("enum_unmapped")
            attrs["dateStart"] = when
            dur = row.get("CallDurationInSeconds")
            attrs["duration"] = dur if type(dur) is int and dur >= 0 else None
            attrs["description"] = text(row.get("Description"))
            attrs["contactsIds"] = self._who_contacts(row, ctx)
        else:
            attrs["status"] = "Archived"
            attrs["bodyPlain"] = text(row.get("Description"))
            attrs["body"] = attrs["bodyPlain"]
            attrs["isHtml"] = False
            attrs["dateSent"] = when
        return entity, attrs, exc

    def event(self, row, ctx):
        exc = []
        attrs = self._legacy(row, ctx, exc)
        attrs["name"] = text(row.get("Subject"))
        etype = row.get("Type")
        if blank(etype):
            attrs["meetingType"] = self.m["meetingTypeUntyped"]
        else:
            attrs["meetingType"] = self._enum("Meeting.meetingType", etype, exc)
        attrs["dateStart"] = self._dt(row.get("StartDateTime") or row.get("ActivityDateTime"), exc)
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
        attrs["from"] = text(row.get("FromAddress"))
        attrs["to"] = addresses(row.get("ToAddress"))
        attrs["cc"] = addresses(row.get("CcAddress"))
        attrs["bodyPlain"] = text(row.get("TextBody"))
        attrs["body"] = attrs["bodyPlain"]
        attrs["isHtml"] = False
        attrs["dateSent"] = self._dt(row.get("MessageDate"), exc)
        attrs["messageId"] = text(row.get("MessageIdentifier"))
        attrs["sfEmailMessageId"] = row["Id"]
        attrs["sfThreadIdentifier"] = text(row.get("ThreadIdentifier"))
        attrs["sfActivityId"] = text(row.get("ActivityId"))
        # parent: RelatedToId (Opportunity/Account), else the linked Task's parent
        ptype = pid = None
        related = row.get("RelatedToId")
        if self.object_of(related) in ("Opportunity", "Account"):
            pid = ctx.record_id(self.object_of(related), related)
            ptype = self.object_of(related) if pid else None
        if pid is None and not blank(row.get("ActivityId")) and row["ActivityId"] in task_rows:
            sub = []
            ptype, pid = self._parent(task_rows[row["ActivityId"]], ctx, sub)
        if pid is None and (not blank(related) or not blank(row.get("ActivityId"))):
            exc.append("activity_parent_unresolved")
        attrs["parentType"], attrs["parentId"] = ptype, pid
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
