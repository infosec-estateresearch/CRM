"""D8: parse references out of the enquiry name with tested patterns only.

A pattern table (``load/contract/name_patterns.json``) holds ``{code, regex}`` entries.
The first pattern that fully matches wins; its named groups give ``clientReference``,
``deceasedName`` and ``caseNumber``. Nothing is guessed: an unparsed name leaves the
three fields empty and the caller records ``name_unparsed``.
"""

import json
import re

from .errors import LoadError

GROUPS = ("clientReference", "deceasedName", "caseNumber")
_CODE = re.compile(r"\A[a-z0-9_]{1,40}\Z")


class NameParser:
    def __init__(self, patterns):
        self.patterns = []
        for entry in patterns:
            if not isinstance(entry, dict) or set(entry) != {"code", "regex"}:
                raise LoadError("name_pattern_invalid")
            if not isinstance(entry["code"], str) or not _CODE.fullmatch(entry["code"]):
                raise LoadError("name_pattern_invalid")
            try:
                rx = re.compile(entry["regex"])
            except (re.error, TypeError):
                raise LoadError("name_pattern_invalid") from None
            if not rx.groupindex or not set(rx.groupindex) <= set(GROUPS):
                raise LoadError("name_pattern_invalid")
            self.patterns.append((entry["code"], rx))

    @classmethod
    def from_file(cls, path):
        try:
            with open(path, "rb") as fh:
                doc = json.loads(fh.read().decode("utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            raise LoadError("name_patterns_unreadable") from None
        if not isinstance(doc, dict) or not isinstance(doc.get("patterns"), list):
            raise LoadError("name_patterns_unreadable")
        return cls(doc["patterns"])

    def parse(self, name):
        """Returns (code, {group: value}) or (None, {}) when no pattern matches."""
        if not isinstance(name, str) or not name.strip():
            return None, {}
        for code, rx in self.patterns:
            m = rx.fullmatch(name.strip())
            if m:
                return code, {g: (v.strip() if isinstance(v, str) else None)
                              for g, v in m.groupdict().items() if g in GROUPS}
        return None, {}
