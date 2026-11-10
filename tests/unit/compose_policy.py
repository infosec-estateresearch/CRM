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


# EspoCRM 10 persistence layout (upstream Docker docs, "Migration to EspoCRM 10"):
# the persistent directories are mounted one by one, never the document root.
ESPOCRM_REPO = "espocrm/espocrm"
DOCROOT = "/var/www/html"
ESPOCRM_TARGETS = ("/var/www/html/data", "/var/www/html/custom",
                   "/var/www/html/client/custom")
REQUIRED_ENV = re.compile(r"^\$\{[A-Z][A-Z0-9_]*:\?[^}]*\}$")


def _norm_target(target):
    target = str(target or "")
    return "/" + target.strip("/") if target.startswith("/") else target


def _mounts(svc):
    """[{type, source, target, read_only}] for a service, short or long syntax."""
    out = []
    for vol in svc.get("volumes") or []:
        if isinstance(vol, dict):
            out.append({"type": vol.get("type", ""), "source": str(vol.get("source", "")),
                        "target": _norm_target(vol.get("target")),
                        "read_only": bool(vol.get("read_only"))})
            continue
        text = str(vol)
        if text.startswith("${") and "}" in text:  # ${VAR:?msg} contains a colon
            end = text.index("}") + 1
            parts = [text[:end]] + (text[end + 1:].split(":") if text[end:end + 1] == ":" else [])
        else:
            parts = text.split(":")
        if len(parts) == 1:  # anonymous volume
            out.append({"type": "volume", "source": "", "target": _norm_target(parts[0]),
                        "read_only": False})
            continue
        source, target = parts[0], parts[1]
        modes = parts[2].split(",") if len(parts) > 2 else []
        kind = "bind" if source[:1] in ("/", ".", "~", "$") else "volume"
        out.append({"type": kind, "source": source, "target": _norm_target(target),
                    "read_only": "ro" in modes})
    return out


def _is_espocrm(svc):
    ref = str(svc.get("image") or "").partition("@")[0]
    repo = ref.rsplit(":", 1)[0] if ":" in ref.rsplit("/", 1)[-1] else ref
    return repo == ESPOCRM_REPO


def rule_no_docroot_mount(doc, register=None):
    """No service mounts the EspoCRM document root itself (legacy layout)."""
    return [f"{name}: mounts {DOCROOT} itself" for name, svc in _services(doc)
            for m in _mounts(svc) if m["target"] == DOCROOT]


def rule_espocrm_mounts(doc, register=None):
    """Every EspoCRM service has exactly the three persistent bind mounts, each
    sourced from a required env variable, one distinct variable per target, and
    the same variable per target on every EspoCRM service."""
    out = []
    espo = [(name, svc) for name, svc in _services(doc) if _is_espocrm(svc)]
    if not espo:
        return ["no service runs the EspoCRM image"]
    sources = {}
    for name, svc in espo:
        mounts = _mounts(svc)
        targets = [m["target"] for m in mounts]
        if sorted(targets) != sorted(ESPOCRM_TARGETS):
            out.append(f"{name}: mounts {targets}, expected exactly {list(ESPOCRM_TARGETS)}")
        for m in mounts:
            if m["target"] not in ESPOCRM_TARGETS:
                continue
            if m["type"] != "bind":
                out.append(f"{name}: {m['target']} is a {m['type'] or '<untyped>'} mount, not a bind")
            if not REQUIRED_ENV.match(m["source"]):
                out.append(f"{name}: {m['target']} source {m['source']!r} is not a required "
                           "env variable (${VAR:?message})")
            sources.setdefault(m["target"], set()).add(m["source"])
    for target, srcs in sorted(sources.items()):
        if len(srcs) > 1:
            out.append(f"{target}: EspoCRM services use different sources {sorted(srcs)}")
    flat = [next(iter(s)) for s in sources.values() if len(s) == 1]
    if len(set(flat)) != len(flat):
        out.append("two persistent targets share one source variable")
    return out


def rule_espocrm_mounts_writable(doc, register=None):
    """The entrypoint chowns data/, custom/ and client/custom/ on every start
    under set -e, so none of them may be read-only."""
    return [f"{name}: {m['target']} is mounted read-only"
            for name, svc in _services(doc) if _is_espocrm(svc)
            for m in _mounts(svc) if m["target"] in ESPOCRM_TARGETS and m["read_only"]]


RULES = {
    "db_no_ports": rule_db_no_ports,
    "ports_loopback": rule_ports_loopback,
    "no_external": rule_no_external,
    "images_pinned": rule_images_pinned,
    "images_match_register": rule_images_match_register,
    "crm_prefix": rule_crm_prefix,
    "no_container_name": rule_no_container_name,
    "no_docroot_mount": rule_no_docroot_mount,
    "espocrm_mounts": rule_espocrm_mounts,
    "espocrm_mounts_writable": rule_espocrm_mounts_writable,
}


def check(doc, register):
    """{rule name: [violations]} for every rule."""
    return {name: fn(doc, register) for name, fn in RULES.items()}
