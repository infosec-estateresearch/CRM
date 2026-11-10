"""Counts-only logger.

Every line is ``crm-migrate event=<name> key=value ...``. Values are numbers,
booleans, ``None`` or strings from an explicit vocabulary (mode names, statuses,
error codes, and the object and field names of the contract). Anything else is
written as ``<redacted>``, so a record value can never reach a log line even if a
caller passes one by mistake. ``sf_error`` is rendered only if it is in
``errors.SF_ERROR_CODES``; any other value is written as ``UNKNOWN``.
"""

import logging
import re

from .errors import SF_ERROR_CODES

LOGGER_NAME = "crm_migrate"

STATUSES = ("RECONCILED", "RECONCILED_WITH_DRIFT", "INCOMPLETE", "FAILED", "PASS", "FAIL")
MODES = ("contract-check", "count", "extract", "reconcile", "selftest", "hostcheck")
_BASE_VOCAB = set(STATUSES) | set(MODES) | {"query", "queryAll", "true", "false", "unavailable"}
_KEY_RE = re.compile(r"\A[a-z][a-z0-9_]{0,40}\Z")
_EVENT_RE = re.compile(r"\A[a-z][a-z0-9_.]{0,60}\Z")
_SF_ERROR_RE = re.compile(r"\A[A-Z][A-Z0-9_]{0,63}\Z")
_CODE_RE = re.compile(r"\A[a-z][a-z0-9_]{0,63}\Z")


def get_logger():
    return logging.getLogger(LOGGER_NAME)


class CountsLog:
    """Structured, counts-only event logger."""

    def __init__(self, logger=None):
        self._logger = logger or get_logger()
        self._vocab = set(_BASE_VOCAB)

    def allow(self, *words):
        for word in words:
            if isinstance(word, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,80}", word):
                self._vocab.add(word)

    def allow_contract(self, contract):
        for obj in contract.objects:
            self.allow(obj.name)
            for fld in obj.fields:
                self.allow(fld.name)

    def _render(self, key, value):
        if key == "sf_error" and value is not None:   # re-checked here: only the fixed set, else UNKNOWN
            ok = isinstance(value, str) and _SF_ERROR_RE.fullmatch(value) and value in SF_ERROR_CODES
            return value if ok else "UNKNOWN"
        if value is None or isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, str):
            if value in self._vocab:
                return value
            if key in ("code", "error") and _CODE_RE.fullmatch(value):
                return value
        return "<redacted>"

    def event(self, event_name, /, **fields):
        if not isinstance(event_name, str) or not _EVENT_RE.fullmatch(event_name):
            event_name = "invalid_event"
        parts = [f"crm-migrate event={event_name}"]
        for key in sorted(fields):
            if not _KEY_RE.fullmatch(key):
                continue
            parts.append(f"{key}={self._render(key, fields[key])}")
        self._logger.info(" ".join(parts))
