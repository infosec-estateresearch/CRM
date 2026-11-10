"""Write-capable identity waiver (CRM-002-S, ``--auth soap-legacy`` only).

The legacy identity can write. Under ``--auth soap-legacy`` only, the metadata gate's
``createable`` / ``updateable`` / ``deletable`` failure can be waived by
``/srv/CRM/runtime/migrate/waiver.json`` (root, ``0600``; checked on the host by
``hostcheck.check_waiver_file_stat``)::

    {"authorisation": "<GitHub Issue #9 comment URL>", "identity": "legacy-eric",
     "expires": "YYYY-MM-DD"}

``expires`` is an ISO date, not in the past and at most 30 days ahead. Anything else,
including an extra key, means a fail. Client-credentials mode never reads it.
"""

import datetime as _dt
import json
import re

from .errors import ConfigError

WAIVER_PATH = "/srv/CRM/runtime/migrate/waiver.json"
WAIVER_IDENTITY = "legacy-eric"
MAX_WAIVER_DAYS = 30
MAX_WAIVER_BYTES = 4096
GITHUB_HOST = "github.com"
ISSUE_COMMENT_PREFIX = "https://" + GITHUB_HOST + "/infosec-estateresearch/CRM/issues/9#issuecomment-"
_URL_RE = re.compile(r"\A" + re.escape(ISSUE_COMMENT_PREFIX) + r"[0-9]{1,20}\Z")
_DATE_RE = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
KEYS = ("authorisation", "expires", "identity")


def _fail(detail):
    raise ConfigError("waiver_invalid", detail=detail)


class _DuplicateKey(Exception):
    """Internal marker; never escapes ``parse_waiver``."""


def _no_duplicates(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise _DuplicateKey()
    return dict(pairs)


def parse_waiver(raw, today):
    """Validate waiver bytes against the schema; ``today`` is a ``datetime.date`` (UTC).

    Every ``ConfigError`` is raised outside an ``except`` block, so none carries a
    ``__context__`` that holds the file content."""
    if not isinstance(raw, bytes) or len(raw) > MAX_WAIVER_BYTES:
        _fail("waiver missing or too large")
    doc, parsed, dup = None, False, False
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
        parsed = True
    except _DuplicateKey:
        dup = True
    except (UnicodeDecodeError, ValueError):
        pass
    finally:
        raw = None
    if dup:
        _fail("waiver repeats a key")
    if not parsed:
        _fail("waiver is not valid JSON")
    if not isinstance(doc, dict) or tuple(sorted(doc)) != KEYS:
        _fail("waiver must hold exactly authorisation, identity, expires")
    url, identity, expires = doc["authorisation"], doc["identity"], doc["expires"]
    if not isinstance(url, str) or not _URL_RE.fullmatch(url):
        _fail("authorisation must be a GitHub Issue 9 comment URL")
    if identity != WAIVER_IDENTITY:
        _fail("identity must be legacy-eric")
    if not isinstance(expires, str) or not _DATE_RE.fullmatch(expires):
        _fail("expires must be an ISO date YYYY-MM-DD")
    try:
        when = _dt.date.fromisoformat(expires)
    except ValueError:
        when = None
    if when is None:
        _fail("expires must be an ISO date YYYY-MM-DD")
    if when < today:
        raise ConfigError("waiver_expired", detail="the waiver has expired")
    if when > today + _dt.timedelta(days=MAX_WAIVER_DAYS):
        _fail("expires is more than 30 days ahead")
    return {"authorisation": url, "identity": identity, "expires": expires}


def load_waiver(path, today=None):
    today = today or _dt.datetime.now(_dt.timezone.utc).date()
    raw = None
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_WAIVER_BYTES + 1)
    except OSError:
        raw = None
    if raw is None:
        _fail("waiver file cannot be read")
    return parse_waiver(raw, today)
