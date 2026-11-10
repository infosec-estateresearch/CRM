"""Idempotent upsert of a gated snapshot into EspoCRM.

* One paged read per entity at start builds an in-memory index keyed on ``sfId``
  (``sfValue`` for ServiceType). Records are created if absent and updated with only the
  changed attributes. A second run on the same snapshot makes zero writes.
* link-multiple attributes (``*Ids`` / ``*Columns``) are merged with what EspoCRM already
  holds, so the importer never removes a link.
* Nothing is ever deleted. Soft-deleted Salesforce rows are never created; EspoCRM records
  whose sfId is not current in the snapshot are flagged in the exceptions, not removed.
* ``progress.jsonl`` records every write (ids and codes only). A resumed run re-reads the
  index, so completed writes are found and not repeated, and credits them from the log so
  the report equals that of an uninterrupted run.
"""

import json
import os

from .api import WriteRejected
from .errors import LoadError
from .mapping import EXCEPTION_CODES

ENTITIES = ("User", "ServiceType", "Account", "Contact", "Opportunity", "Task", "Call", "Meeting", "Email")
SF_TO_ENTITY = {"Account": "Account", "Contact": "Contact", "Opportunity": "Opportunity"}
SOURCE_OBJECTS = ("User", "Account", "Contact", "Opportunity", "OpportunityContactRole", "Task", "Event",
                  "EmailMessage", "EmailMessageRelation", "Note")


def _norm(value):
    if value is None or value == "" or value == [] or value == {}:
        return None
    if isinstance(value, list):
        return sorted(value, key=str)
    return value


def _is_multi(attr):
    return attr.endswith("Ids") or attr.endswith("Columns")


class EspoContext:
    """Resolves Salesforce ids to EspoCRM ids through the live index."""

    def __init__(self, index):
        self.index = index

    def user_id(self, sf_id):
        rec = self.index["User"].get(sf_id)
        return rec["id"] if rec else None

    def record_id(self, obj, sf_id):
        entity = SF_TO_ENTITY.get(obj)
        rec = self.index[entity].get(sf_id) if entity else None
        return rec["id"] if rec else None

    def service_type_id(self, value):
        rec = self.index["ServiceType"].get(value)
        return rec["id"] if rec else None


class SnapshotContext:
    """Resolves against the snapshot itself: the expected relationship totals."""

    def __init__(self, snapshot, user_ids):
        self.current = {o: {r["Id"] for r in snapshot.current(o)} for o in SF_TO_ENTITY}
        self.users = user_ids

    def user_id(self, sf_id):
        return sf_id if sf_id in self.users else None

    def record_id(self, obj, sf_id):
        return sf_id if sf_id in self.current.get(obj, ()) else None

    def service_type_id(self, value):
        return value


class Progress:
    def __init__(self, path, previous=None):
        """``path`` is a new progress file; ``previous`` an earlier run's, read only.

        The earlier entries are copied first, so a resumed output can itself be resumed.
        """
        self.path = path
        self.done = {}
        entries = []
        if previous is not None:
            try:
                with open(previous, "r", encoding="utf-8") as fh:
                    for line in fh:
                        if line.strip():
                            e = json.loads(line)
                            self.done[(e["p"], e["k"])] = e["a"]
                            entries.append(e)
            except (OSError, ValueError, KeyError, TypeError):
                raise LoadError("resume_progress_unreadable") from None
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self.fh = os.fdopen(fd, "a", encoding="utf-8")
        for e in entries:
            self.fh.write(json.dumps({"p": e["p"], "k": e["k"], "a": e["a"]}, separators=(",", ":")) + "\n")
        self.fh.flush()

    def record(self, phase, key, action):
        self.fh.write(json.dumps({"p": phase, "k": key, "a": action}, separators=(",", ":")) + "\n")
        self.fh.flush()
        os.fsync(self.fh.fileno())

    def close(self):
        self.fh.close()


class Loader:
    def __init__(self, snapshot, mapper, client, log, progress, mapping):
        self.s = snapshot
        self.mapper = mapper
        self.client = client
        self.log = log
        self.progress = progress
        self.mapping = mapping
        self.index = {}
        self.exceptions = {}           # (object, sfId, reason) -> None, insertion-ordered
        self.objects = {o: {"source_rows": 0, "source_current": 0,
                            "skipped": {"soft_deleted": 0, "absent_unexplained": 0, "out_of_scope": 0,
                                        "represented_by_email_message": 0, "parent_soft_deleted": 0,
                                        "user_not_human": 0},
                            "targets": {}, "exceptions": {}} for o in SOURCE_OBJECTS}
        self.flagged = {}

    # ---------------------------------------------------------------- index
    def _attrs(self, entity):
        spec = self.mapping["entities"].get(entity)
        if spec is None:
            return ["sfId"]
        attrs = list(spec.get("copy", {})) + list(spec.get("enum", {})) + spec.get("attributes", [])
        attrs += spec.get("secondPass", [])
        return list(dict.fromkeys([spec.get("key", "sfId")] + attrs))

    def build_index(self):
        for entity in ENTITIES:
            key = self.mapping["entities"].get(entity, {}).get("key", "sfId")
            rows = self.client.list_all(entity, self._attrs(entity), key=key)
            idx = {}
            for row in rows:
                k = row.get(key)
                if isinstance(k, str) and k:
                    idx[k] = row
            self.index[entity] = idx
            self.log.event("index", entity=entity, records=len(idx))

    # ---------------------------------------------------------------- bookkeeping
    def exception(self, obj, sf_id, reason):
        if reason not in EXCEPTION_CODES:
            raise LoadError("exception_code_unknown")
        k = (obj, sf_id, reason)
        if k not in self.exceptions:
            self.exceptions[k] = None
            ex = self.objects[obj]["exceptions"]
            ex[reason] = ex.get(reason, 0) + 1

    def _count(self, obj, entity, action):
        t = self.objects[obj]["targets"].setdefault(entity, {"created": 0, "updated": 0, "unchanged": 0,
                                                             "failed": 0})
        t[action] += 1

    # ---------------------------------------------------------------- upsert
    def upsert(self, phase, obj, sf_id, entity, key, attrs, create=True):
        existing = self.index[entity].get(key)
        action = "unchanged"
        try:
            if existing is None:
                if not create:
                    self.exception(obj, sf_id, "opportunity_unresolved")
                    return None
                body = {a: v for a, v in attrs.items() if _norm(v) is not None}
                new_id = self.client.create(entity, body)
                self.index[entity][key] = dict(body, id=new_id)
                action = "created"
            else:
                diff = {}
                for a, v in attrs.items():
                    old = existing.get(a)
                    if _is_multi(a):
                        if a.endswith("Ids"):
                            merged = list(dict.fromkeys(list(old or []) + list(v or [])))
                            if set(merged) != set(old or []):
                                diff[a] = merged
                        else:
                            merged = dict(old or {})
                            merged.update(v or {})
                            if merged != (old or {}):
                                diff[a] = merged
                    elif _norm(v) != _norm(old):
                        diff[a] = v
                if diff:
                    for a in [a for a in diff if a.endswith("Columns")]:
                        ids = a[:-len("Columns")] + "Ids"
                        if ids not in diff:
                            diff[ids] = list(existing.get(ids) or [])
                    self.client.update(entity, existing["id"], diff)
                    existing.update(diff)
                    action = "updated"
        except WriteRejected as exc:
            if exc.status == 409:
                # EspoCRM's duplicate-name check; every POST skips it, so this should not occur.
                self.exception(obj, sf_id, "duplicate_conflict")
            elif exc.status is not None and 400 <= exc.status < 500:
                self.exception(obj, sf_id, "write_rejected")
            else:
                self.exception(obj, sf_id, "write_failed")
            self._count(obj, entity, "failed")
            return None
        if action != "unchanged":
            self.progress.record(phase, sf_id, action)
        else:
            action = self.progress.done.get((phase, sf_id), "unchanged")
        self._count(obj, entity, action)
        return self.index[entity].get(key)

    # ---------------------------------------------------------------- phases
    def _source(self, obj):
        rows = self.s.rows(obj)
        cur = [r for r in rows if r.get("IsDeleted") is not True]
        o = self.objects[obj]
        o["source_rows"] = len(rows)
        o["source_current"] = len(cur)
        o["skipped"]["soft_deleted"] = len(rows) - len(cur)
        unexplained = self.s.absent_unexplained(obj)
        if unexplained is not None:
            o["skipped"]["absent_unexplained"] = unexplained
        return cur

    def _record_exc(self, obj, row, codes):
        for c in codes:
            self.exception(obj, row["Id"], c)

    def run(self):
        m, ctx = self.mapper, EspoContext(self.index)
        self.build_index()
        users = self._source("User")
        self.objects["User"]["skipped"]["user_not_human"] = sum(
            1 for r in users if r.get("UserType") != "Standard")
        # ServiceType: distinct Opportunity_Service__c values, by name with sfValue.
        opps = self._source("Opportunity")
        values = sorted({r["Opportunity_Service__c"] for r in opps
                         if isinstance(r.get("Opportunity_Service__c"), str) and r["Opportunity_Service__c"].strip()})
        first = {}
        for r in opps:
            first.setdefault(r.get("Opportunity_Service__c"), r["Id"])
        for v in values:
            # The value is content: progress and exceptions carry the first Opportunity Id instead.
            self.upsert("service_type", "Opportunity", first[v], "ServiceType", v, {"name": v, "sfValue": v})
        accounts = self._source("Account")
        for r in accounts:
            attrs, exc = m.account(r, ctx)
            self._record_exc("Account", r, exc)
            self.upsert("account", "Account", r["Id"], "Account", r["Id"], attrs)
        # Second pass: parents, once every Account exists.
        for r in accounts:
            attrs, exc = m.account_parent(r, ctx)
            self._record_exc("Account", r, exc)
            if r["Id"] in self.index["Account"]:
                self._upsert_quiet("account_parent", "Account", r, "Account", attrs)
        for r in self._source("Contact"):
            attrs, exc = m.contact(r, ctx)
            self._record_exc("Contact", r, exc)
            self.upsert("contact", "Contact", r["Id"], "Contact", r["Id"], attrs)
        for r in opps:
            attrs, exc = m.opportunity(r, ctx)
            self._record_exc("Opportunity", r, exc)
            self.upsert("opportunity", "Opportunity", r["Id"], "Opportunity", r["Id"], attrs)
        self._contact_roles(ctx)
        tasks = self._source("Task")
        task_by_id = {r["Id"]: r for r in tasks}
        emails = self._source("EmailMessage")
        emailed_tasks = {r.get("ActivityId") for r in emails if r.get("ActivityId")}
        for r in tasks:
            entity = m.task_entity(r)
            if entity == "Email" and r["Id"] in emailed_tasks:
                self.objects["Task"]["skipped"]["represented_by_email_message"] += 1
                continue
            entity, attrs, exc = m.task(r, ctx)
            self._record_exc("Task", r, exc)
            self.upsert("task", "Task", r["Id"], entity, r["Id"], attrs)
        for r in self._source("Event"):
            attrs, exc = m.event(r, ctx)
            self._record_exc("Event", r, exc)
            self.upsert("event", "Event", r["Id"], "Meeting", r["Id"], attrs)
        # Contract v4 visibleVia: a relation whose EmailMessage or Contact is soft-deleted is
        # hidden in Salesforce; it is skipped, never imported (deletion class parent_soft_deleted).
        hidden_parents = {r["Id"] for r in self.s.soft_deleted("EmailMessage")} | \
            {r["Id"] for r in self.s.soft_deleted("Contact")}
        relations = {}
        for rel in self._source("EmailMessageRelation"):
            if rel.get("EmailMessageId") in hidden_parents or rel.get("RelationId") in hidden_parents:
                self.objects["EmailMessageRelation"]["skipped"]["parent_soft_deleted"] += 1
                continue
            relations.setdefault(rel.get("EmailMessageId"), []).append(rel)
        for r in emails:
            attrs, exc = m.email_message(r, relations.get(r["Id"], []), task_by_id, ctx)
            self._record_exc("EmailMessage", r, exc)
            self.upsert("email_message", "EmailMessage", r["Id"], "Email", r["Id"], attrs)
        notes = self._source("Note")
        self.objects["Note"]["skipped"]["out_of_scope"] = len(notes)
        self._flag_existing()

    def _upsert_quiet(self, phase, obj, row, entity, attrs):
        """A second-pass update: counted separately so pass 1 counts stay per record."""
        before = {k: dict(v) for k, v in self.objects[obj]["targets"].items()}
        res = self.upsert(phase, obj, row["Id"], entity, row["Id"], attrs, create=False)
        after = self.objects[obj]["targets"]
        for ent, counts in after.items():
            for action, n in counts.items():
                delta = n - before.get(ent, {}).get(action, 0)
                if delta:
                    counts[action] -= delta
                    sp = self.objects[obj].setdefault("second_pass", {"updated": 0, "unchanged": 0, "failed": 0,
                                                                      "created": 0})
                    sp[action] += delta
        return res

    def _contact_roles(self, ctx):
        by_opp = {}
        for r in self._source("OpportunityContactRole"):
            opp = r.get("OpportunityId")
            if ctx.record_id("Opportunity", opp) is None:
                self.exception("OpportunityContactRole", r["Id"], "opportunity_unresolved")
                continue
            cid = ctx.record_id("Contact", r.get("ContactId"))
            if cid is None:
                self.exception("OpportunityContactRole", r["Id"], "contact_unresolved")
                continue
            role = r.get("Role")
            if role is None:
                role = ""
            elif role not in self.mapping["enums"]["Contact.opportunityRole"] or role == "":
                # Core validates the role against Contact.opportunityRole.options (400 columnsValid).
                self.exception("OpportunityContactRole", r["Id"], "role_unmapped")
                role = ""
            by_opp.setdefault(opp, {})[cid] = role
        for opp, contacts in sorted(by_opp.items()):
            attrs = {"contactsIds": sorted(contacts),
                     "contactsColumns": {c: {"role": role} for c, role in sorted(contacts.items())}}
            self.upsert("contact_roles", "OpportunityContactRole", opp, "Opportunity", opp, attrs, create=False)

    def _flag_existing(self):
        keys = {e: set() for e in ENTITIES}
        deleted = {}
        for obj, entities in (("Account", ("Account",)), ("Contact", ("Contact",)),
                              ("Opportunity", ("Opportunity",)), ("Task", ("Task", "Call", "Email")),
                              ("Event", ("Meeting",)), ("EmailMessage", ("Email",))):
            for r in self.s.rows(obj):
                if r.get("IsDeleted") is True:
                    deleted[r["Id"]] = obj
                else:
                    for e in entities:
                        keys[e].add(r["Id"])
        for entity in ("Account", "Contact", "Opportunity", "Task", "Call", "Meeting", "Email"):
            n = 0
            for sf_id in sorted(set(self.index[entity]) - keys[entity]):
                n += 1
                obj = deleted.get(sf_id)
                if obj:
                    self.exception(obj, sf_id, "exists_soft_deleted_in_sf")
                else:
                    src = self.mapper.object_of(sf_id) or entity
                    if src not in self.objects:
                        src = {"Call": "Task", "Meeting": "Event", "Email": "EmailMessage"}.get(entity, entity)
                    self.exception(src, sf_id, "exists_not_in_snapshot")
            self.flagged[entity] = n
