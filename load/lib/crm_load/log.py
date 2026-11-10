"""Counts-only logging: ``crm-load event=<name> key=value``.

Values must be ints, bools, None, or tokens from a safe vocabulary (codes, object and
entity names). Anything else is printed as ``<redacted>``, so record content can never
reach a log line.
"""

import re
import sys

_SAFE = re.compile(r"\A[A-Za-z][A-Za-z0-9_.:-]{0,63}\Z")


def safe_value(value):
    if value is None or isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and _SAFE.fullmatch(value):
        return value
    return "<redacted>"


class Log:
    def __init__(self, stream=None):
        self.stream = stream if stream is not None else sys.stderr
        self.lines = []

    def event(self, name, **fields):
        parts = [f"crm-load event={safe_value(name)}"]
        parts += [f"{k}={safe_value(v)}" for k, v in sorted(fields.items())]
        line = " ".join(parts)
        self.lines.append(line)
        self.stream.write(line + "\n")
