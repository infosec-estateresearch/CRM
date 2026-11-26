#!/usr/bin/env python3
"""Retention settings that travel with the release (CRM-IDINT-001R, 3.6).

config/release-settings.json names the EspoCRM settings a release must leave in
force: deleted-record cleanup off, audit cleanup off, user action history kept
6 months and sign-in records 13 months. scripts/deploy_release.sh applies each
one with `bin/command config:set` and reads it back; any difference fails the
deploy. This module only validates the file and prints one line per setting:

    name <TAB> type <TAB> value-for-config:set <TAB> php-literal-expected-on-read-back

Usage: release_settings.py [path]   (default: config/release-settings.json)
Standard library only. The file holds no secret, address or credential.
"""

import json
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_PATH = os.path.join(REPO, "config", "release-settings.json")

NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
STRING_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]*$")
TYPES = ("bool", "string")

# What 3.6 requires; the file may add settings but may never relax these.
REQUIRED = {
    "cleanupDeletedRecords": ("bool", False),
    "cleanupAudit": ("bool", False),
    "cleanupActionHistoryPeriod": ("string", "6 months"),
    "cleanupAuthLogPeriod": ("string", "13 months"),
}


class SettingsError(ValueError):
    pass


def load(path=DEFAULT_PATH):
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as err:
        raise SettingsError(f"cannot read release settings {path}: {err}")
    return validate(doc)


def validate(doc):
    """The settings as [(name, type, value)], or SettingsError."""
    if not isinstance(doc, dict) or set(doc) != {"settings"} or not isinstance(doc["settings"], list):
        raise SettingsError('release settings must be {"settings": [...]}')
    out, seen = [], set()
    for item in doc["settings"]:
        if not isinstance(item, dict) or set(item) != {"name", "type", "value"}:
            raise SettingsError("every setting needs exactly name, type and value")
        name, kind, value = item["name"], item["type"], item["value"]
        if not isinstance(name, str) or not NAME.match(name):
            raise SettingsError(f"bad setting name: {name!r}")
        if name in seen:
            raise SettingsError(f"setting listed twice: {name}")
        seen.add(name)
        if kind not in TYPES:
            raise SettingsError(f"{name}: type must be one of {TYPES}")
        if kind == "bool" and not isinstance(value, bool):
            raise SettingsError(f"{name}: a bool setting needs true or false")
        if kind == "string" and not (isinstance(value, str) and STRING_VALUE.match(value)):
            raise SettingsError(f"{name}: a string setting needs a plain value")
        out.append((name, kind, value))
    for name, (kind, value) in REQUIRED.items():
        found = [s for s in out if s[0] == name]
        if len(found) != 1 or found[0][1:] != (kind, value):
            raise SettingsError(f"{name} must be {value!r} ({kind})")
    return out


def lines(settings):
    for name, kind, value in settings:
        if kind == "bool":
            yield f"{name}\t{kind}\t{'true' if value else 'false'}\t{'true' if value else 'false'}"
        else:
            yield f"{name}\t{kind}\t{value}\t'{value}'"


def main(argv=None, out=None):
    argv = sys.argv[1:] if argv is None else argv
    out = sys.stdout if out is None else out
    path = argv[0] if argv else DEFAULT_PATH
    try:
        for line in lines(load(path)):
            print(line, file=out)
    except SettingsError as err:
        print(f"release_settings.py: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
