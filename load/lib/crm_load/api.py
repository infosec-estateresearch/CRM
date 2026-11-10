"""EspoCRM REST client: paged list, create, update, with retry on 429 and 5xx. Never deletes."""

import time

from .errors import TransportError

PAGE = 200  # recordListMaxSizeLimit of 10.0.12
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
    def __init__(self, transport, retries=5, backoff=1.0, sleep=time.sleep):
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
        """One paged read: every record whose key is not null. Returns a list of dicts."""
        out, offset = [], 0
        select = ",".join(["id"] + [a for a in attributes if a != "id"])
        while True:
            query = [("select", select), ("maxSize", str(PAGE)), ("offset", str(offset)),
                     ("where[0][type]", "isNotNull"), ("where[0][attribute]", key)]
            self.reads += 1
            status, doc = self._send("GET", entity, query)
            if status != 200 or not isinstance(doc, dict) or not isinstance(doc.get("list"), list):
                raise TransportError("list_failed", status)
            out.extend(doc["list"])
            offset += len(doc["list"])
            if not doc["list"] or offset >= int(doc.get("total", 0)):
                return out

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
