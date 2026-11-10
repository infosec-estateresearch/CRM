"""Compose isolation policy for CRM-001 (CRM-D012, CRM-D018), standard library only.

Each rule is a function taking the parsed Compose document (and the register
digests where needed) and returning a list of violation strings; an empty
list means the rule holds.
"""

import ipaddress
import json
import os
import re

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMPOSE_PATH = os.path.join(REPO, "deploy", "compose.json")
REGISTER_PATH = os.path.join(REPO, "security", "EXTERNAL_CODE_REGISTER.yaml")
ACCESS_CONF_PATH = os.path.join(REPO, "deploy", "apache", "crm-access.conf")
PREFIX = "crm-"
LOOPBACK = "127.0.0.1"
APP_PORT = "8180"
BIND_VAR = "CRM_BIND_IP"
BIND_ENV = re.compile(r"^\$\{CRM_BIND_IP:\?[^}]*\}$")
SOURCES_VAR = "CRM_ALLOWED_SOURCES"
SOURCES_ENV = re.compile(r"^\$\{CRM_ALLOWED_SOURCES:\?[^}]*\}$")
CRM_NET_SUBNET = "172.16.10.0/24"  # the project's own Docker subnet (WO CRM-001 item 1)
IPV4_LITERAL = re.compile(r"(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?:/[0-9]{1,2})?(?![0-9.])")

# The Apache access file: Git-controlled, mounted read-only into crm-app only.
ACCESS_CONF_SOURCE = "./apache/crm-access.conf"  # relative to deploy/, the project directory
ACCESS_CONF_TARGET = "/etc/apache2/conf-enabled/crm-access.conf"


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


def _port_spec(port):
    """(host_ip, published, target) for one ports entry, short or long syntax.

    A host IP of the form ${VAR:?message} is returned as written; its message
    may contain colons."""
    if isinstance(port, dict):
        return (str(port.get("host_ip", "")), str(port.get("published", "")),
                str(port.get("target", "")))
    text = str(port).split("/", 1)[0]
    if text.startswith("${") and "}" in text:
        end = text.index("}") + 1
        rest = text[end:].lstrip(":").split(":") if text[end:end + 1] == ":" else []
        return text[:end], rest[0] if len(rest) > 1 else "", rest[-1] if rest else ""
    if text.startswith("["):  # [ipv6]:host:container
        ip, rest = text[1:].split("]", 1)
        parts = rest.lstrip(":").split(":")
        return ip, parts[0] if len(parts) > 1 else "", parts[-1]
    parts = text.split(":")
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return "", parts[0], parts[1]
    return "", "", parts[0]  # container port only: random host port on all interfaces


def _published(port):
    """(host_ip, published) for one ports entry, short or long syntax."""
    return _port_spec(port)[:2]


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


def _literal_ip(text):
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


def rule_ports_host_ip(doc, register=None):
    """Every published port names a host IP, and never the unspecified address:
    no "8180:80", no bare container port, no 0.0.0.0 or ::, no host networking."""
    out = []
    for name, svc in _services(doc):
        if svc.get("network_mode") == "host":
            out.append(f"{name}: network_mode host bypasses port binding")
        for port in svc.get("ports") or []:
            host_ip, _, _ = _port_spec(port)
            ip = _literal_ip(host_ip)
            if not host_ip:
                out.append(f"{name}: port {port!r} has no host IP (binds every interface)")
            elif ip is not None and ip.is_unspecified:
                out.append(f"{name}: port {port!r} binds the unspecified address")
    return out


def rule_app_single_env_bind(doc, register=None):
    """crm-app publishes exactly ${CRM_BIND_IP:?...}:8180:80; no other service publishes."""
    out = []
    services = doc.get("services") or {}
    if "crm-app" not in services:
        return ["service crm-app is missing"]
    ports = services["crm-app"].get("ports") or []
    if len(ports) != 1:
        out.append(f"crm-app publishes {len(ports)} mappings, expected exactly 1")
    for port in ports:
        host_ip, published, target = _port_spec(port)
        if not BIND_ENV.match(host_ip) or published != APP_PORT or target != "80":
            out.append(f"crm-app: port {port!r} is not "
                       f"${{{BIND_VAR}:?...}}:{APP_PORT}:80")
    for name, svc in _services(doc):
        if name != "crm-app" and svc.get("ports"):
            out.append(f"{name} publishes ports")
    return out


def _strings(node, path=()):
    """(path, string) for every string in a JSON document, keys included."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield path + (key,), str(key)
            yield from _strings(value, path + (key,))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _strings(value, path + (i,))
    elif isinstance(node, str):
        yield path, node


def literal_ips(text):
    """[(literal, ip_network or ip_address)] for every IP literal in text.

    IPv4 dotted quads (with an optional /prefix) and IPv6 candidates (tokens of
    hex digits and colons that parse as an address)."""
    found = []
    for m in IPV4_LITERAL.finditer(text):
        try:
            value = (ipaddress.ip_network(m.group(0), strict=False) if "/" in m.group(0)
                     else ipaddress.ip_address(m.group(0)))
        except ValueError:
            continue
        found.append((m.group(0), value))
    for token in re.split(r"[^0-9A-Fa-f:]+", text):
        if token.count(":") >= 2:
            ip = _literal_ip(token)
            if ip is not None and ip.version == 6:
                found.append((token, ip))
    return found


def rule_no_literal_ip(doc, register=None):
    """No IP literal other than loopback anywhere in the Compose document. The
    only exception is the project's own subnet, CRM_NET_SUBNET, as the IPAM
    subnet of a top-level network (rule_crm_prefix checks the network's name)."""
    out = []
    for path, text in _strings(doc):
        for literal, value in literal_ips(text):
            if value.is_loopback:
                continue
            if (len(path) == 6 and path[0] == "networks" and path[2:4] == ("ipam", "config")
                    and path[5] == "subnet" and text == CRM_NET_SUBNET):
                continue
            out.append(f"{'.'.join(map(str, path))}: literal address {literal!r}")
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
        # the access file mount is checked by rule_access_conf_mount
        mounts = [m for m in _mounts(svc) if m["target"] != ACCESS_CONF_TARGET]
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


def rule_access_conf_mount(doc, register=None):
    """crm-app bind-mounts the Git-controlled access file read-only at its
    conf-enabled path; no other service mounts it or anything at that target."""
    out = []
    services = doc.get("services") or {}
    if "crm-app" not in services:
        return ["service crm-app is missing"]
    for name, svc in _services(doc):
        found = [m for m in _mounts(svc)
                 if m["target"] == ACCESS_CONF_TARGET
                 or os.path.basename(m["source"]) == os.path.basename(ACCESS_CONF_SOURCE)]
        if name != "crm-app":
            out += [f"{name}: mounts the access file ({m['target']})" for m in found]
            continue
        if len(found) != 1:
            out.append(f"crm-app: {len(found)} access-file mounts, expected exactly 1")
            continue
        m = found[0]
        if m["type"] != "bind" or m["source"] != ACCESS_CONF_SOURCE \
                or m["target"] != ACCESS_CONF_TARGET:
            out.append(f"crm-app: access file mount is {m['type']} {m['source']!r} -> "
                       f"{m['target']!r}, expected bind {ACCESS_CONF_SOURCE!r} -> "
                       f"{ACCESS_CONF_TARGET!r}")
        if not m["read_only"]:
            out.append("crm-app: access file is not mounted read-only")
    return out


def rule_access_sources_env(doc, register=None):
    """crm-app receives CRM_ALLOWED_SOURCES as a required env-file variable."""
    app = (doc.get("services") or {}).get("crm-app")
    if app is None:
        return ["service crm-app is missing"]
    env = app.get("environment") or {}
    if isinstance(env, list):
        env = dict(e.split("=", 1) if "=" in e else (e, None) for e in env)
    value = env.get(SOURCES_VAR)
    if not isinstance(value, str) or not SOURCES_ENV.match(value):
        return [f"crm-app: {SOURCES_VAR} is {value!r}, expected ${{{SOURCES_VAR}:?...}}"]
    return []


RULES = {
    "db_no_ports": rule_db_no_ports,
    "ports_host_ip": rule_ports_host_ip,
    "app_single_env_bind": rule_app_single_env_bind,
    "no_literal_ip": rule_no_literal_ip,
    "no_external": rule_no_external,
    "images_pinned": rule_images_pinned,
    "images_match_register": rule_images_match_register,
    "crm_prefix": rule_crm_prefix,
    "no_container_name": rule_no_container_name,
    "no_docroot_mount": rule_no_docroot_mount,
    "espocrm_mounts": rule_espocrm_mounts,
    "espocrm_mounts_writable": rule_espocrm_mounts_writable,
    "access_conf_mount": rule_access_conf_mount,
    "access_sources_env": rule_access_sources_env,
}


def check(doc, register):
    """{rule name: [violations]} for every rule."""
    return {name: fn(doc, register) for name, fn in RULES.items()}


# --- deploy/apache/crm-access.conf -------------------------------------------
# Each conf rule takes the file's text and returns a list of violations.

REQUIRE_LINE = "Require ip 127.0.0.1 ::1 ${CRM_ALLOWED_SOURCES}"


def load_conf(path=ACCESS_CONF_PATH):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _directives(text):
    """Effective lines: comments and blank lines dropped, whitespace collapsed.
    Apache continues a line ending in a backslash; so does this."""
    out, buf = [], ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        line = " ".join((buf + line).split())
        buf = ""
        if line and not line.startswith("#"):
            out.append(line)
    if buf.strip():
        out.append(" ".join(buf.split()))
    return out


def conf_rule_deny_by_default(text):
    """Exactly one <Location "/"> block (every URL path), and its only directive
    is the Require ip line for loopback plus ${CRM_ALLOWED_SOURCES}. No other
    section that merges after <Directory> (<Location*>, <If*>, <Else>, <Proxy*>)
    could override it for a sub-path, and no Require stands outside it."""
    lines = _directives(text)
    others = [l for l in lines if re.match(r"(?i)^<(LocationMatch|If|ElseIf|Else|Proxy|"
                                           r"ProxyMatch|VirtualHost)\b", l)]
    if others:
        return [f"section that could override the restriction: {l!r}" for l in others]
    requires = [l for l in lines if re.match(r"(?i)^require\b", l)]
    if len(requires) != 1:
        return [f"{len(requires)} Require directives, expected exactly the one in <Location \"/\">"]
    opens = [i for i, l in enumerate(lines) if re.match(r"(?i)^<Location\s", l)]
    if len(opens) != 1:
        return [f"{len(opens)} <Location> blocks, expected exactly one, for \"/\""]
    start = opens[0]
    if not re.match(r'(?i)^<Location\s+("/"|/)\s*>$', lines[start]):
        return [f"the <Location> block is {lines[start]!r}, not for \"/\""]
    try:
        end = next(i for i in range(start + 1, len(lines))
                   if re.match(r"(?i)^</Location\s*>$", lines[i]))
    except StopIteration:
        return ["the <Location \"/\"> block is not closed"]
    body = lines[start + 1:end]
    if body != [REQUIRE_LINE]:
        return [f"the <Location \"/\"> block holds {body!r}, expected exactly [{REQUIRE_LINE!r}]"]
    return []


def conf_rule_no_grant(text):
    """Nothing grants access: no Require other than "Require ip", no
    "Require all granted", no legacy Allow/Order/Satisfy, no Require*-blocks."""
    out = []
    for line in _directives(text):
        word = line.split()[0].lower()
        if word == "require" and (len(line.split()) < 2 or line.split()[1].lower() != "ip"):
            out.append(f"grant other than Require ip: {line!r}")
        elif word in ("allow", "deny", "order", "satisfy", "<requireany>", "<requireall>",
                      "<requirenone>", "authmerging"):
            out.append(f"access directive not allowed here: {line!r}")
        elif re.search(r"(?i)\ball\s+granted\b", line):
            out.append(f"grants everyone: {line!r}")
    return out


def conf_rule_no_remoteip(text):
    """No header-derived client address: no mod_remoteip, no X-Forwarded-For or
    similar, no module loading, no environment-based access."""
    pattern = re.compile(r"(?i)remoteip|x-forwarded|x-real-ip|\bforwarded\b|\bloadmodule\b"
                         r"|\bsetenvif|\bproxyprotocol\b")
    return [f"trusts a header or loads a module: {line!r}"
            for line in _directives(text) if pattern.search(line)]


CONF_RULES = {
    "conf_deny_by_default": conf_rule_deny_by_default,
    "conf_no_grant": conf_rule_no_grant,
    "conf_no_remoteip": conf_rule_no_remoteip,
}


def check_conf(text):
    """{conf rule name: [violations]} for every conf rule."""
    return {name: fn(text) for name, fn in CONF_RULES.items()}


# --- literal addresses in the repository ---------------------------------------
# Git holds variable names, loopback and logic only (standing rule). Real values
# live in the runtime env file.

RFC1918_BLOCKS = {"10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"}
# Documentation networks (RFC 5737, RFC 3849): never routed, allowed as test data only.
DOC_NETS = tuple(ipaddress.ip_network(n) for n in
                 ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32"))
SCANNED = ("deploy", "scripts", "tests")


def allowed_literal(rel, literal, value):
    """Is this literal acceptable in file rel (repository-relative, "/"-separated)?

    Everywhere: loopback, the unspecified address (0.0.0.0, ::, /0), and the
    RFC 1918 block definitions themselves. deploy/compose.json and tests/: the
    crm-net subnet. tests/ only: documentation addresses (RFC 5737, RFC 3849) and
    IPv4 special-purpose addresses no LAN host is numbered from (0/8, link-local,
    multicast, reserved and broadcast), which the validator tests refuse."""
    if value.is_loopback or literal in RFC1918_BLOCKS:
        return True
    if isinstance(value, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
        if value.prefixlen == 0 or value.network_address.is_loopback:
            return True
    elif value.is_unspecified:
        return True
    in_tests = rel.startswith("tests/")
    if literal == CRM_NET_SUBNET and (in_tests or rel == "deploy/compose.json"):
        return True
    if in_tests:
        net = value if hasattr(value, "prefixlen") else ipaddress.ip_network(value)
        if any(net.version == d.version and net.subnet_of(d) for d in DOC_NETS):
            return True
        first = net.network_address
        return net.version == 4 and (first.packed[0] == 0 or first.is_link_local
                                     or first.is_multicast or first.is_reserved)
    return False


def scan_literal_ips(root=REPO, dirs=SCANNED):
    """["path:line: literal"] for every literal address not allowed by allowed_literal."""
    out = []
    for top in dirs:
        for base, subdirs, files in os.walk(os.path.join(root, top)):
            subdirs[:] = sorted(d for d in subdirs if d != "__pycache__")
            for fname in sorted(files):
                path = os.path.join(base, fname)
                rel = os.path.relpath(path, root).replace(os.sep, "/")
                try:
                    with open(path, encoding="utf-8") as fh:
                        lines = fh.read().splitlines()
                except (UnicodeDecodeError, OSError):
                    out.append(f"{rel}: not readable as UTF-8 text")
                    continue
                for n, line in enumerate(lines, start=1):
                    for literal, value in literal_ips(line):
                        if not allowed_literal(rel, literal, value):
                            out.append(f"{rel}:{n}: {literal}")
    return out
