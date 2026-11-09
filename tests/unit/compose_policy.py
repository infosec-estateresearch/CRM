"""Compose isolation policy for CRM-001 (CRM-D012, CRM-D018), standard library only.

Each rule is a function taking the parsed Compose document (and the register
digests where needed) and returning a list of violation strings; an empty
list means the rule holds.
"""

import json
import os
import re

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMPOSE_PATH = os.path.join(REPO, "deploy", "compose.json")
REGISTER_PATH = os.path.join(REPO, "security", "EXTERNAL_CODE_REGISTER.yaml")
PREFIX = "crm-"
LOOPBACK = "127.0.0.1"


def load_compose(path=COMPOSE_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_register(path=REGISTER_PATH):
    """{name: {"version": first token, "digest": sha256:...}} from the register.

    A deliberately small parser for the register's flat candidate list, so the
    tests need no YAML library."""
    entries = {}
    current = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split(" #", 1)[0].rstrip()
            m = re.match(r"^\s*-\s+name:\s*(\S+)\s*$", line)
            if m:
                current = entries.setdefault(m.group(1), {})
                continue
            m = re.match(r"^\s+(version|digest):\s*\"?([^\"]+)\"?\s*$", line)
            if m and current is not None:
                current[m.group(1)] = m.group(2).split()[0]
    return entries


def _services(doc):
    return (doc.get("services") or {}).items()


def _published(port):
    """(host_ip, published) for one ports entry, short or long syntax."""
    if isinstance(port, dict):
        return str(port.get("host_ip", "")), str(port.get("published", ""))
    text = str(port).split("/", 1)[0]
    if text.startswith("["):  # [ipv6]:host:container
        ip, rest = text[1:].split("]", 1)
        parts = rest.lstrip(":").split(":")
        return ip, parts[0] if len(parts) > 1 else ""
    parts = text.split(":")
    if len(parts) == 3:
        return parts[0], parts[1]
    if len(parts) == 2:
        return "", parts[0]
    return "", ""  # container port only: random host port on all interfaces


def rule_db_no_ports(doc, register=None):
    db = (doc.get("services") or {}).get("crm-db")
    if db is None:
        return ["service crm-db is missing"]
    out = []
    if db.get("ports"):
        out.append("crm-db publishes ports")
    if db.get("network_mode") == "host":
        out.append("crm-db uses host networking")
    return out


def rule_ports_loopback(doc, register=None):
    out = []
    for name, svc in _services(doc):
        if svc.get("network_mode") == "host":
            out.append(f"{name}: network_mode host bypasses port binding")
        for port in svc.get("ports") or []:
            host_ip, _ = _published(port)
            if host_ip != LOOPBACK:
                out.append(f"{name}: port {port!r} is not bound to {LOOPBACK}")
    return out


def rule_no_external(doc, register=None):
    out = []
    for section in ("networks", "volumes"):
        for key, spec in (doc.get(section) or {}).items():
            if isinstance(spec, dict) and spec.get("external"):
                out.append(f"{section}.{key} is external")
    return out


def _images(doc):
    return [(name, svc.get("image", "")) for name, svc in _services(doc)]


def rule_images_pinned(doc, register=None):
    out = []
    for name, image in _images(doc):
        if not re.search(r"@sha256:[0-9a-f]{64}$", image or ""):
            out.append(f"{name}: image {image!r} is not pinned by @sha256 digest")
    return out


def rule_images_match_register(doc, register):
    out = []
    for name, image in _images(doc):
        ref, _, digest = (image or "").partition("@")
        repo, _, tag = ref.rpartition(":") if ":" in ref else (ref, "", "")
        entry = register.get(repo.rsplit("/", 1)[-1])
        if entry is None:
            out.append(f"{name}: image {repo!r} is not in the register")
            continue
        if digest != entry.get("digest"):
            out.append(f"{name}: digest {digest or '<none>'} != register {entry.get('digest')}")
        if tag != entry.get("version"):
            out.append(f"{name}: tag {tag or '<none>'} != register version {entry.get('version')}")
    return out


def rule_crm_prefix(doc, register=None):
    out = []
    for section in ("services", "networks", "volumes"):
        for key in (doc.get(section) or {}):
            if not key.startswith(PREFIX):
                out.append(f"{section}.{key} does not start with {PREFIX!r}")
    return out


def rule_no_container_name(doc, register=None):
    return [f"{name}: sets container_name" for name, svc in _services(doc)
            if "container_name" in svc]


RULES = {
    "db_no_ports": rule_db_no_ports,
    "ports_loopback": rule_ports_loopback,
    "no_external": rule_no_external,
    "images_pinned": rule_images_pinned,
    "images_match_register": rule_images_match_register,
    "crm_prefix": rule_crm_prefix,
    "no_container_name": rule_no_container_name,
}


def check(doc, register):
    """{rule name: [violations]} for every rule."""
    return {name: fn(doc, register) for name, fn in RULES.items()}
