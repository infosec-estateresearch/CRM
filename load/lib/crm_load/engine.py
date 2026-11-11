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

import hashlib
import json
import os

from .api import WriteRejected
from .errors import LoadError
from .mapping import EXCEPTION_CODES, REFUSING_CODES, SENT_ONLY_CODES, check_shape
from .users import is_human

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


PHONE_ATTRS = ("phoneNumberData", "phoneNumber")
NUMERIC_ATTRS = ("amount",)
# CRM-009-I fact 2: a 10.0.12 list read returns a text attribute cut to its first 10,000 characters.
LIST_TEXT_LIMIT = 10000
# CRM-009-I fact 1: EspoCRM never returns Email.usersIds (list or single read): sent on create only.
CREATE_ONLY = {"Email": ("usersIds",)}
# CRM-009-I fact 3: Email addresses are stored lower case; a ';' list may be reordered.
ADDRESS_LISTS = ("to", "cc")


def _phone_text(number):
    """A phone as EspoCRM stores it with phoneNumberInternational=false: trimmed."""
    return number.strip() if isinstance(number, str) else number


def _phone_set(value):
    """phoneNumberData compared on (phoneNumber, type, primary) only, order-insensitive.

    EspoCRM reads it back with extra keys (optOut, invalid) that the importer never sends,
    and stores each number trimmed (like the phoneNumber attribute)."""
    if not isinstance(value, list):
        return None
    out = set()
    for p in value:
        if isinstance(p, dict):
            out.add((_phone_text(p.get("phoneNumber")), p.get("type"), p.get("primary") is True))
    return frozenset(out) or None


def _number(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return _norm(value)


def as_stored(value, text=False):
    """A value as EspoCRM stores it: varchar strings are trimmed (core StringTrim), text verbatim."""
    if isinstance(value, str) and not text:
        return value.strip()
    return value


def _address_set(value):
    """An Email to/cc list as EspoCRM stores it: case-insensitive, order-insensitive."""
    if not isinstance(value, str):
        return _norm(value)
    return frozenset(a.strip().lower() for a in value.split(";") if a.strip()) or None


def same_value(attr, new, old, text=False, entity=None):
    if entity == "Email" and attr in ADDRESS_LISTS:
        return _address_set(new) == _address_set(old)
    if entity == "Email" and attr == "from" and isinstance(new, str) and isinstance(old, str):
        return new.strip().lower() == old.strip().lower()
    if attr == "phoneNumberData":
        return _phone_set(new) == _phone_set(old)
    if attr in NUMERIC_ATTRS:
        return _number(_norm(new)) == _number(_norm(old))
    if entity == "Call" and attr == "duration" and _norm(new) is None and old in (0, None):
        # A null duration is stored as 0 (derived from dateEnd - dateStart): equal to blank.
        return True
    return _norm(as_stored(new, text)) == _norm(as_stored(old, text))


def refusal_hash(sf_id, field, value):
    """Content-free memory of a server-refused phone: sha256 of (sfId, field, value as stored,
    i.e. trimmed), so a number differing only in surrounding blanks is the same refusal."""
    value = _phone_text(value)
    return hashlib.sha256(json.dumps([sf_id, field, value], separators=(",", ":")).encode("utf-8")).hexdigest()


def _primaries(data):
    return [dict(p, primary=(i == 0)) for i, p in enumerate(data)]


class EspoContext:
    """Resolves Salesforce ids to EspoCRM ids through the live index."""

    def __init__(self, index, deleted=frozenset()):
        self.index = index
        self.deleted = deleted

    def soft_deleted(self, sf_id):
        return isinstance(sf_id, str) and sf_id in self.deleted

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
        self.deleted = soft_deleted_ids(snapshot)
        self.users = user_ids

    def soft_deleted(self, sf_id):
        return isinstance(sf_id, str) and sf_id in self.deleted

    def user_id(self, sf_id):
        return sf_id if sf_id in self.users else None

    def record_id(self, obj, sf_id):
        return sf_id if sf_id in self.current.get(obj, ()) else None

    def service_type_id(self, value):
        return value


def soft_deleted_ids(snapshot):
    """Ids of rows soft-deleted in the snapshot that a record may reference."""
    return frozenset(r["Id"] for o in ("Account", "Contact", "Opportunity", "Task", "Event", "EmailMessage")
                     for r in snapshot.soft_deleted(o))


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
    def __init__(self, snapshot, mapper, client, log, progress, mapping, refused=frozenset()):
        self.refused_before = frozenset(refused)    # refusal hashes from earlier runs (read only)
        self.refused = set()                        # refusal hashes this run holds
        self.text_attrs = {e: set(v) for e, v in mapping.get("textAttributes", {}).items() if e != "note"}
        self.no_blank = set(mapping.get("enumNoBlank", {}).get("attributes", []))
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
                                        "user_not_human": 0, "value_shape": 0,
                                        "enum_blank_unrepresentable": 0,
                                        "owner_required_unresolved": 0, "email_from_invalid": 0,
                                        "value_too_long": 0},
                            "targets": {}, "exceptions": {}} for o in SOURCE_OBJECTS}
        self.flagged = {}
        # CRM-008: target maxLength per entity and attribute (mapping.json maxLength).
        self.max_length = {e: dict(v) for e, v in mapping.get("maxLength", {}).items() if e != "note"}
        # CRM-008 round 3: required target attributes; an over-length one refuses the record.
        self.required = {e: set(v) for e, v in mapping.get("requiredAttributes", {}).items() if e != "note"}
        # CRM-008 round 4: records refused by upsert in this run, (object, sfId); every later
        # write for them (second passes included) is skipped. ServiceType refusals by value.
        self.refused_records = set()
        self.refused_service_types = set()

    # ---------------------------------------------------------------- index
    def _attrs(self, entity):
        spec = self.mapping["entities"].get(entity)
        if spec is None:
            return ["sfId"]
        attrs = list(spec.get("copy", {})) + list(spec.get("enum", {})) + spec.get("attributes", [])
        attrs += spec.get("secondPass", [])
        if "phoneNumberData" in attrs:
            # List reads omit phoneNumberData (CRM-008-F fact 1); phoneNumber is the primary.
            attrs.append("phoneNumber")
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
    def exception(self, obj, sf_id, reason, attribute=None):
        if reason not in EXCEPTION_CODES:
            raise LoadError("exception_code_unknown")
        k = (obj, sf_id, reason)
        if k not in self.exceptions:
            self.exceptions[k] = None
            ex = self.objects[obj]["exceptions"]
            ex[reason] = ex.get(reason, 0) + 1
        if attribute is not None:
            # The attribute name only (value_too_long, qualified Entity.attribute), never the value.
            self.exceptions[k] = sorted(set(self.exceptions[k] or []) | {attribute})

    def _limit_lengths(self, obj, sf_id, entity, attrs):
        """CRM-008 change 5: a varchar, email or phone value longer than the target maxLength
        (trimmed, as stored) is sent as null with value_too_long and its qualified attribute
        name (Entity.attribute); a phone number is dropped with phone_rejected. Never truncated.
        An over-length required attribute (requiredAttributes) refuses the record: None."""
        limits = self.max_length.get(entity)
        if not limits:
            return attrs
        out = dict(attrs)
        required = self.required.get(entity, set())
        refused = False
        for a, limit in limits.items():
            if a == "phoneNumber" and a in out and isinstance(out[a], str) and \
                    len(out[a].strip()) > limit:
                out[a] = None
                self.exception(obj, sf_id, "phone_rejected")
            elif a == "phoneNumberData" and isinstance(out.get(a), list):
                kept = [p for p in out[a] if not (isinstance(p.get("phoneNumber"), str)
                                                  and len(p["phoneNumber"].strip()) > limit)]
                if len(kept) != len(out[a]):
                    self.exception(obj, sf_id, "phone_rejected")
                    if kept and not any(p.get("primary") for p in kept):
                        kept[0] = dict(kept[0], primary=True)
                    out[a] = kept or None
            elif isinstance(out.get(a), str) and len(out[a].strip()) > limit:
                out[a] = None
                self.exception(obj, sf_id, "value_too_long", f"{entity}.{a}")
                refused = refused or a in required
        return None if refused else out

    def _count(self, obj, entity, action):
        t = self.objects[obj]["targets"].setdefault(entity, {"created": 0, "updated": 0, "unchanged": 0,
                                                             "failed": 0})
        t[action] += 1

    # ---------------------------------------------------------------- upsert
    def _refuse(self, obj, sf_id, entity, key, reason):
        """The record is not sent: counted once in skipped, remembered so no later write is made."""
        self.objects[obj]["skipped"][reason] += 1
        if entity == "ServiceType":
            self.refused_service_types.add(key)
        else:
            self.refused_records.add((obj, sf_id))
        return None

    def upsert(self, phase, obj, sf_id, entity, key, attrs, create=True):
        attrs = self._limit_lengths(obj, sf_id, entity, attrs)
        if attrs is None:
            # A required attribute is over length: null would be refused (400 required). Never sent.
            return self._refuse(obj, sf_id, entity, key, "value_too_long")
        blank_enum = [a for a in attrs if f"{entity}.{a}" in self.no_blank and _norm(attrs[a]) is None]
        if blank_enum:
            # No "" option: null and "" are refused (400 valid) and omitting stores the default.
            self.exception(obj, sf_id, "enum_blank_unrepresentable")
            return self._refuse(obj, sf_id, entity, key, "enum_blank_unrepresentable")
        attrs = self._known_refusals(obj, sf_id, attrs)
        existing = self.index[entity].get(key)
        text = self.text_attrs.get(entity, set())
        action = "unchanged"
        try:
            if existing is None:
                if not create:
                    self.exception(obj, sf_id, "opportunity_unresolved")
                    return None
                # Every mapped attribute is sent, a blank one as explicit null: an omitted one
                # would be stored as the entityDefs default (a manufactured value).
                body = {a: (None if _norm(v) is None and not _is_multi(a) else v) for a, v in attrs.items()}
                try:
                    new_id = self.client.create(entity, body)
                    self.index[entity][key] = dict(body, id=new_id)
                except WriteRejected as exc:
                    base, phones = self._split_phones(exc, body)
                    new_id = self.client.create(entity, base)
                    self.index[entity][key] = dict(base, id=new_id)
                    self._probe_phones(obj, sf_id, entity, self.index[entity][key], phones)
                action = "created"
            else:
                diff = {}
                single = {}                    # at most one GET {Entity}/{id} per record
                create_only = CREATE_ONLY.get(entity, ())
                for a, v in attrs.items():
                    if a in create_only:
                        continue               # never returned by the server: never compared or sent
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
                    elif a == "phoneNumberData" and a not in existing:
                        if not self._phones_same(entity, existing, v, single):
                            diff[a] = None if _norm(v) is None else v
                    elif not same_value(a, self._untruncated(entity, existing, a, v, a in text, single),
                                        existing.get(a), a in text, entity):
                        diff[a] = None if _norm(v) is None else v
                if diff:
                    for a in [a for a in diff if a.endswith("Columns")]:
                        ids = a[:-len("Columns")] + "Ids"
                        if ids not in diff:
                            diff[ids] = list(existing.get(ids) or [])
                    wrote = True
                    try:
                        self.client.update(entity, existing["id"], diff)
                        existing.update(diff)
                    except WriteRejected as exc:
                        base, phones = self._split_phones(exc, diff)
                        if base:
                            self.client.update(entity, existing["id"], base)
                            existing.update(base)
                        accepted = self._probe_phones(obj, sf_id, entity, existing, phones)
                        # Nothing stored (every phone probe refused, no other change): unchanged.
                        wrote = bool(base) or accepted > 0
                    if wrote:
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

    def _single(self, entity, existing, single):
        """The record's single read, ``GET {Entity}/{id}``: made once per upsert, counted in reads."""
        if "rec" not in single:
            single["rec"] = self.client.get(entity, existing["id"]) or {}
        return single["rec"]

    def _untruncated(self, entity, existing, attr, new, text, single):
        """CRM-009-I change 2: a list value of exactly LIST_TEXT_LIMIT characters that is a prefix of
        a longer desired value may be the server's cut. The record is read once and the full stored
        value replaces the cut one in the index. Returns ``new`` unchanged (the value to compare)."""
        old = existing.get(attr)
        want = as_stored(new, text)
        if isinstance(old, str) and isinstance(want, str) and len(old) == LIST_TEXT_LIMIT and \
                len(want) > LIST_TEXT_LIMIT and want.startswith(old):
            existing[attr] = self._single(entity, existing, single).get(attr)
        return new

    # ---------------------------------------------------------------- phones
    def _phones_same(self, entity, existing, new, single=None):
        """CRM-008-F change 1: a list row has no phoneNumberData, only phoneNumber (the primary).
        A different primary needs a write; one source number equal to it needs none; with two or
        more numbers the record is read once (GET {Entity}/{id}) and the full set compared."""
        numbers = [p for p in new or [] if isinstance(p, dict)]
        primary = next((_phone_text(p.get("phoneNumber")) for p in numbers if p.get("primary") is True), None)
        if _norm(primary) != _norm(_phone_text(existing.get("phoneNumber"))):
            return False
        if len(numbers) <= 1:
            return True
        stored = self._single(entity, existing, {} if single is None else single).get("phoneNumberData")
        existing["phoneNumberData"] = stored
        return same_value("phoneNumberData", new, stored)

    def _known_refusals(self, obj, sf_id, attrs):
        """Drop numbers the server refused before (same sfId, field and value): never retried."""
        memory = self.refused_before | self.refused
        if not memory:
            return attrs
        attrs = dict(attrs)
        if isinstance(attrs.get("phoneNumber"), str) and \
                refusal_hash(sf_id, "phoneNumber", attrs["phoneNumber"]) in memory:
            self.refused.add(refusal_hash(sf_id, "phoneNumber", attrs["phoneNumber"]))
            self.exception(obj, sf_id, "phone_refused")
            attrs["phoneNumber"] = None
        if isinstance(attrs.get("phoneNumberData"), list):
            keep = []
            for p in attrs["phoneNumberData"]:
                h = refusal_hash(sf_id, "phoneNumberData", p.get("phoneNumber"))
                if h in memory:
                    self.refused.add(h)
                    self.exception(obj, sf_id, "phone_refused")
                else:
                    keep.append(p)
            attrs["phoneNumberData"] = _primaries(keep) or None
        return attrs

    @staticmethod
    def _split_phones(exc, attrs):
        """A 400 on the field phoneNumber: the write without the phones, and the phones to probe."""
        if exc.status != 400 or exc.field != "phoneNumber" or not any(attrs.get(a) for a in PHONE_ATTRS):
            raise exc
        base = {a: v for a, v in attrs.items() if a not in PHONE_ATTRS}
        phones = {a: attrs[a] for a in PHONE_ATTRS if attrs.get(a)}
        return base, phones

    def _probe_phones(self, obj, sf_id, entity, record, phones):
        """One write per number (bounded by the numbers on the record): the valid ones are kept,
        each refused one is remembered by hash and reported as phone_refused (record id only).
        Returns the number of accepted (stored) probe writes."""
        accepted = 0
        if phones.get("phoneNumber"):
            value = phones["phoneNumber"]
            try:
                self.client.update(entity, record["id"], {"phoneNumber": value})
                record["phoneNumber"] = value
                accepted += 1
            except WriteRejected as exc:
                if exc.status != 400 or exc.field != "phoneNumber":
                    raise
                self.refused.add(refusal_hash(sf_id, "phoneNumber", value))
                self.exception(obj, sf_id, "phone_refused")
        if phones.get("phoneNumberData"):
            kept = []
            for p in phones["phoneNumberData"]:
                trial = _primaries(kept + [p])
                try:
                    self.client.update(entity, record["id"], {"phoneNumberData": trial})
                    kept.append(p)
                    record["phoneNumberData"] = trial
                    accepted += 1
                except WriteRejected as exc:
                    if exc.status != 400 or exc.field != "phoneNumber":
                        raise
                    self.refused.add(refusal_hash(sf_id, "phoneNumberData", p.get("phoneNumber")))
                    self.exception(obj, sf_id, "phone_refused")
        return accepted

    # ---------------------------------------------------------------- phases
    def _source(self, obj):
        rows = self.s.rows(obj)
        cur = [r for r in rows if r.get("IsDeleted") is not True]
        o = self.objects[obj]
        o["source_rows"] = len(rows)
        o["source_current"] = len(cur)
        o["skipped"]["soft_deleted"] = len(rows) - len(cur)
        # A dict or list in a mapped field: that record is an exception, never a traceback.
        ok = []
        for r in cur:
            try:
                check_shape(obj, r, self.mapping)
            except LoadError as exc:
                self.exception(obj, r["Id"], exc.code)
                o["skipped"]["value_shape"] += 1
                continue
            ok.append(r)
        cur = ok
        unexplained = self.s.absent_unexplained(obj)
        if unexplained is not None:
            o["skipped"]["absent_unexplained"] = unexplained
        return cur

    def _server_stamped(self, obj, row, entity, stored):
        """CRM-008-G round 3 (PL decision, state-based): a Task whose stored state after the
        upsert is Completed with sfCompletedAt null has a dateCompleted EspoCRM stamped itself
        (the save time). Recorded (id only) on every run, for each such Task that was stored
        or already exists; ``stored`` is None for a refused or rejected record (no code)."""
        if entity == "Task" and stored is not None and stored.get("status") == "Completed" and \
                _norm(stored.get("sfCompletedAt")) is None:
            self.exception(obj, row["Id"], "date_completed_server_stamped")

    def _record_exc(self, obj, row, codes):
        """Record the codes; True when one of them refuses the record (never sent)."""
        for c in codes:
            self.exception(obj, row["Id"], c)
        refused = [c for c in codes if c in REFUSING_CODES]
        for c in dict.fromkeys(refused):
            self.objects[obj]["skipped"][c] += 1
        return bool(refused)

    def run(self):
        m, ctx = self.mapper, EspoContext(self.index, soft_deleted_ids(self.s))
        self.build_index()
        users = self._source("User")
        self.objects["User"]["skipped"]["user_not_human"] = sum(
            1 for r in users if not is_human(r, self.s.synthetic is True))
        # ServiceType: distinct Opportunity_Service__c values, by name with sfValue.
        opps = self._source("Opportunity")
        # Keyed on the value as stored (trimmed, like every varchar): a padded value is the same type.
        values = sorted({r["Opportunity_Service__c"].strip() for r in opps
                         if isinstance(r.get("Opportunity_Service__c"), str) and r["Opportunity_Service__c"].strip()})
        first = {}
        for r in opps:
            if isinstance(r.get("Opportunity_Service__c"), str):
                first.setdefault(r["Opportunity_Service__c"].strip(), r["Id"])
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
            # A record refused in pass 1 gets no write at all, not even its parent link.
            if r["Id"] in self.index["Account"] and ("Account", r["Id"]) not in self.refused_records:
                self._upsert_quiet("account_parent", "Account", r, "Account", attrs)
        for r in self._source("Contact"):
            attrs, exc = m.contact(r, ctx)
            self._record_exc("Contact", r, exc)
            self.upsert("contact", "Contact", r["Id"], "Contact", r["Id"], attrs)
        for r in opps:
            attrs, exc = m.opportunity(r, ctx)
            self._record_exc("Opportunity", r, exc)
            service = r.get("Opportunity_Service__c")
            if isinstance(service, str) and service.strip() in self.refused_service_types:
                # Its ServiceType was refused: no link, and a code on this Opportunity (id only).
                attrs["serviceTypeId"] = None
                self.exception("Opportunity", r["Id"], "service_type_refused")
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
            # CRM-008: a Task-Email no EmailMessage represents is a Task, unless an earlier
            # run already created it as an Email (it is never moved).
            routed = None if entity == "Email" and r["Id"] in self.index["Email"] else emailed_tasks
            entity, attrs, exc = m.task(r, ctx, routed)
            if self._record_exc("Task", r, exc):
                continue
            stored = self.upsert("task", "Task", r["Id"], entity, r["Id"], attrs)
            self._server_stamped("Task", r, entity, stored)
        for r in self._source("Event"):
            attrs, exc = m.event(r, ctx)
            if self._record_exc("Event", r, exc):
                continue
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
            as_email = r["Id"] in self.index["Email"]
            kept = not as_email and r["Id"] in self.index["Task"]
            has_to = attrs["to"] is not None
            if kept or (not has_to and not as_email):
                # CRM-008-F change 4: Email.to is required; no recipient -> a Task.
                # CRM-008-G: one an earlier run created as a Task stays a Task (never moved,
                # never also POSTed as an Email), even once it has a recipient.
                attrs, exc = m.email_message_as_task(r, task_by_id, ctx)
                if has_to:
                    exc = [("email_kept_as_task" if c == "email_without_recipient_imported_as_task"
                            else c) for c in exc]
                sent_only = [c for c in exc if c in SENT_ONLY_CODES]
                if self._record_exc("EmailMessage", r, [c for c in exc if c not in SENT_ONLY_CODES]):
                    continue
                stored = self.upsert("email_message", "EmailMessage", r["Id"], "Task", r["Id"], attrs)
                if stored is not None:
                    self._record_exc("EmailMessage", r, sent_only)
                self._server_stamped("EmailMessage", r, "Task", stored)
                continue
            if not has_to:
                # An Email from an earlier run stays an Email; null to would be refused (400).
                del attrs["to"]
            if self._record_exc("EmailMessage", r, exc):
                continue
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
            codes = []
            if self.mapper.ref("Opportunity", opp, ctx, codes, "opportunity_unresolved") is None:
                self.exception("OpportunityContactRole", r["Id"], (codes or ["opportunity_unresolved"])[0])
                continue
            cid = self.mapper.ref("Contact", r.get("ContactId"), ctx, codes, "contact_unresolved")
            if cid is None:
                self.exception("OpportunityContactRole", r["Id"], (codes or ["contact_unresolved"])[0])
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
            if ("Opportunity", opp) in self.refused_records:
                continue          # the Opportunity was refused in this run: its roles are not written
            attrs = {"contactsIds": sorted(contacts),
                     "contactsColumns": {c: {"role": role} for c, role in sorted(contacts.items())}}
            self.upsert("contact_roles", "OpportunityContactRole", opp, "Opportunity", opp, attrs, create=False)

    def _flag_existing(self):
        keys = {e: set() for e in ENTITIES}
        deleted = {}
        for obj, entities in (("Account", ("Account",)), ("Contact", ("Contact",)),
                              ("Opportunity", ("Opportunity",)), ("Task", ("Task", "Call", "Email")),
                              ("Event", ("Meeting",)), ("EmailMessage", ("Email", "Task"))):
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
