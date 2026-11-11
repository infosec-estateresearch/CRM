"""EspoCRM REST client: paged list, single read, create, update, with retry on 429 and 5xx. Never deletes."""

import time

from .errors import TransportError

PAGE = 200  # recordListMaxSizeLimit of 10.0.12
MAX_PAGES = 10000  # CRM-009-H: backstop on one paged read (2M rows); beyond it, list_stalled
SKIP_DUPLICATE_CHECK = {"X-Skip-Duplicate-Check": "true"}


class WriteRejected(Exception):
    def __init__(self, status, field=None):
        super().__init__(status)
        self.status = status
        self.field = field          # the validation failure's field on a 400, else None


def _field(status, doc):
    if status == 400 and isinstance(doc, dict) and isinstance(doc.get("field"), str):
        return doc["field"]
    return None


class EspoClient:
    def __init__(self, transport, retries=5, backoff=1.0, sleep=time.sleep, unknown=None,
                 max_pages=MAX_PAGES):
        self.unknown = unknown
        self.max_pages = max_pages
        self.t = transport
        self.retries = retries
        self.backoff = backoff
        self.sleep = sleep
        self.writes = 0
        self.reads = 0

    def _send(self, method, path, query=None, body=None, headers=None):
        attempt = 0
        while True:
            status, doc = self.t.send(method, path, query, body, headers)
            if status == 429 or status >= 500:
                if attempt >= self.retries:
                    return status, None
                self.sleep(self.backoff * (2 ** attempt))
                attempt += 1
                continue
            return status, doc

    def list_all(self, entity, attributes, key="sfId"):
        """One paged read: every record whose key is not null. Returns a list of dicts.

        CRM-009-H: 10.0.12 does not count Email lists (``total: -1``). A missing, non-integer
        or negative total is unknown: paging continues until a page has fewer than PAGE rows.
        Every page is ordered by ``id`` ascending and rows are de-duplicated by ``id``. A full
        page that adds no new id (a server ignoring ``offset``), or reaching ``max_pages``,
        fails with ``list_stalled``. A known total must equal the distinct records read,
        else ``list_incomplete``."""
        out, seen, offset, pages = [], set(), 0, 0
        select = ",".join(["id"] + [a for a in attributes if a != "id"])
        while True:
            if pages >= self.max_pages:
                raise TransportError("list_stalled", None)
            query = [("select", select), ("maxSize", str(PAGE)), ("offset", str(offset)),
                     ("orderBy", "id"), ("order", "asc"),
                     ("where[0][type]", "isNotNull"), ("where[0][attribute]", key)]
            self.reads += 1
            pages += 1
            status, doc = self._send("GET", entity, query)
            if status != 200 or not isinstance(doc, dict) or not isinstance(doc.get("list"), list):
                raise TransportError("list_failed", status)
            rows = doc["list"]
            added = 0
            for row in rows:
                rid = row.get("id") if isinstance(row, dict) else None
                if not isinstance(rid, str) or not rid:
                    raise TransportError("list_failed", status)
                if rid not in seen:
                    seen.add(rid)
                    out.append(row)
                    added += 1
            if len(rows) >= PAGE and not added:
                raise TransportError("list_stalled", status)
            offset += len(rows)
            total = doc.get("total")
            if not isinstance(total, int) or isinstance(total, bool) or total < 0:
                if len(rows) < PAGE:
                    return out
            elif not rows or offset >= total:
                if len(out) != total:
                    raise TransportError("list_incomplete", status)
                return out

    def get(self, entity, record_id):
        """One single-record read, ``GET {Entity}/{id}`` (CRM-008-F: list reads omit
        phoneNumberData; a single-record read returns it). Counted in ``reads``."""
        self.reads += 1
        status, doc = self._send("GET", f"{entity}/{record_id}")
        if status != 200 or not isinstance(doc, dict):
            raise TransportError("read_failed", status)
        return doc

    def setting(self, name):
        """One application setting from ``GET Settings``; ``unknown`` if the read is refused."""
        self.reads += 1
        status, doc = self._send("GET", "Settings")
        if status != 200 or not isinstance(doc, dict) or name not in doc:
            return self.unknown
        return doc[name]

    def create(self, entity, attrs):
        self.writes += 1
        # Branch firms share names: every create skips EspoCRM's duplicate-name check
        # (core CreateParamsFetcher). Uniqueness is on sfId, enforced by the index.
        status, doc = self._send("POST", entity, None, attrs, SKIP_DUPLICATE_CHECK)
        if status not in (200, 201) or not isinstance(doc, dict) or not doc.get("id"):
            raise WriteRejected(status, _field(status, doc))
        return doc["id"]

    def update(self, entity, record_id, attrs):
        self.writes += 1
        status, doc = self._send("PUT", f"{entity}/{record_id}", None, attrs)
        if status != 200:
            raise WriteRejected(status, _field(status, doc))
