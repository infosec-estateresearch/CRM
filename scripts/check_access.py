#!/usr/bin/env python3
"""Fail-closed check of the crm-dev LAN access settings (CRM-D019) and of the
crm-beta edge settings (CRM-007), standard library only.

    python3 scripts/check_access.py beta [--render]
    python3 scripts/check_access.py beta --mode
    python3 scripts/check_access.py restoretest
    python3 scripts/check_access.py dev|beta --base-url

beta validates CRM_BETA_* and CRM_SITE_URL in /srv/CRM/runtime/beta/env, the
beta compose bind policy, the crm-app scheme policy (crm-proxy.conf, or
crm-proxy-uat.conf in UAT mode, CRM-009) and the rendered edge configuration
(see the beta section below); --render then writes it to
<runtime>/edge/haproxy.cfg. Without --render, beta also refuses unless the
on-disk <runtime>/edge/haproxy.cfg is byte for byte the rendered one
(scripts/up.sh beta re-renders it and recreates the edge). beta --mode prints
the validated CRM_BETA_MODE (production or uat) and nothing else. restoretest checks only the isolation policy
of deploy/beta/restoretest/compose.json (restore.sh beta --restoretest).
The rest of this docstring describes dev.

Run it before every `docker compose ... up`:

    python3 scripts/check_access.py dev

It reads the runtime env file as text (it is never sourced or executed) and
refuses (exit 1) unless:
- CRM_BIND_IP is exactly one IPv4 unicast address inside RFC 1918, not
  0.0.0.0 and not loopback, and inside one of the CRM_ALLOWED_SOURCES networks;
- CRM_ALLOWED_SOURCES is one or more space-separated IPv4 CIDRs, each inside
  RFC 1918, each /16 or longer, none overlapping the crm-net subnet;
- CRM_SITE_URL is http://<CRM_BIND_IP>:8180 (optionally with a trailing "/").
Each name must be assigned exactly once, in the plain NAME=value form, and none
may be set in the process environment, because Compose would prefer it to the
env file. The env file must be $CRM_RUNTIME_DIR/env: a CRM_ENV_FILE naming
any other file is refused, so the file checked is the one the scripts give
Compose.

The dev guard is the same as the shell scripts': the first argument must be
exactly "dev" and the runtime directory must be named "dev" (exit 2 otherwise).

Nothing from the env file is printed: problems are reported by variable name and
position only, never by value.
"""

import ipaddress
import json
import os
import re
import socket
import sys
import urllib.parse

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COMPOSE_PATH = os.path.join(REPO, "deploy", "compose.json")
ENV_EXAMPLE_PATH = os.path.join(REPO, "deploy", "env.example")
DEFAULT_RUNTIME = "/srv/CRM/runtime/dev"
PORT = 8180
MIN_PREFIX = 16
NAMES = ("CRM_BIND_IP", "CRM_ALLOWED_SOURCES", "CRM_SITE_URL")

# RFC 1918 private address blocks.
RFC1918 = tuple(ipaddress.IPv4Network(n) for n in
                ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))

DOTTED_QUAD = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
CIDR = re.compile(r"^\d{1,3}(\.\d{1,3}){3}/\d{1,2}$")


def prog():
    return os.path.basename(sys.argv[0] or "check_access.py")


def _ipv4(text):
    """IPv4Address for a strict dotted quad, else None."""
    if not DOTTED_QUAD.match(text):
        return None
    try:
        return ipaddress.IPv4Address(text)  # also rejects octets > 255 and leading zeros
    except ValueError:
        return None


def validate_bind_ip(value):
    if value is None or value == "":
        return ["CRM_BIND_IP is empty"]
    addr = _ipv4(value)
    if addr is None:
        return ["CRM_BIND_IP is not exactly one IPv4 address in dotted-quad form"]
    if addr.is_unspecified or addr.packed[0] == 0:  # "this network", 0/8
        return ["CRM_BIND_IP is the unspecified address or in the 'this network' block "
                "(would bind all interfaces)"]
    if addr.is_loopback:
        return ["CRM_BIND_IP is a loopback address; LAN access needs the host's LAN address"]
    if addr.is_multicast or addr.is_reserved or addr.is_link_local:
        return ["CRM_BIND_IP is not a unicast LAN address (multicast, reserved, broadcast or link-local)"]
    if not any(addr in block for block in RFC1918):
        return ["CRM_BIND_IP is not inside an RFC 1918 private block"]
    return []


def validate_bind_in_sources(bind_ip, sources):
    """The bind address must lie inside one of the allowed networks.

    Call only with values that passed validate_bind_ip and validate_sources."""
    addr = ipaddress.IPv4Address(bind_ip)
    if not any(addr in ipaddress.IPv4Network(n) for n in sources.split()):
        return ["CRM_BIND_IP is not inside any CRM_ALLOWED_SOURCES network"]
    return []


def env_example_names(path=ENV_EXAMPLE_PATH):
    """Every variable name deploy/env.example assigns (NAME= lines), in order.

    The same list scripts/lib/common.sh reads for CRM_ENV_NAMES."""
    with open(path, encoding="utf-8") as fh:
        return [m.group(1) for m in
                (re.match(r"^([A-Z][A-Z0-9_]*)=", line) for line in fh) if m]


def validate_sources(value, avoid=()):
    """avoid: networks no source may overlap (the crm-net subnet)."""
    if value is None or value.strip() == "":
        return ["CRM_ALLOWED_SOURCES is empty"]
    if not re.fullmatch(r"[0-9./ ]+", value):
        return ["CRM_ALLOWED_SOURCES may contain only IPv4 CIDRs separated by spaces"]
    out = []
    for i, token in enumerate(value.split(), start=1):
        where = f"CRM_ALLOWED_SOURCES entry {i}"
        if not CIDR.match(token):
            out.append(f"{where} is not an IPv4 CIDR of the form a.b.c.d/nn")
            continue
        try:
            net = ipaddress.IPv4Network(token, strict=True)
        except ValueError:
            out.append(f"{where} is not a valid network (bad address, prefix or host bits set)")
            continue
        if net.prefixlen == 0:
            out.append(f"{where} is the whole address space (/0, everyone)")
            continue
        if net.prefixlen < MIN_PREFIX:
            out.append(f"{where} is wider than /{MIN_PREFIX}")
        if not any(net.subnet_of(block) for block in RFC1918):
            out.append(f"{where} is not inside an RFC 1918 private block")
        for other in avoid:
            if net.overlaps(other):
                out.append(f"{where} overlaps the crm-net Docker subnet, which would admit "
                           "traffic relayed by the Docker gateway")
    return out


def validate_site_url(value, bind_ip):
    if value is None or value == "":
        return ["CRM_SITE_URL is empty"]
    try:
        url = urllib.parse.urlsplit(value)
        port = url.port
    except ValueError:
        return ["CRM_SITE_URL is not a valid URL"]
    out = []
    if url.scheme != "http":
        out.append("CRM_SITE_URL must use http (TLS is not implemented in this stack yet)")
    if url.username is not None or url.password is not None:
        out.append("CRM_SITE_URL must not contain user information")
    if bind_ip is None or url.hostname != bind_ip:
        out.append("CRM_SITE_URL host is not CRM_BIND_IP")
    if port != PORT:
        out.append(f"CRM_SITE_URL must name port {PORT} explicitly")
    if url.path not in ("", "/") or url.query or url.fragment:
        out.append("CRM_SITE_URL must have no path, query or fragment")
    return out


def read_env_values(text, names=NAMES):
    """({name: value}, [errors]) from env-file text, never executing it.

    Every line that could assign a name in any form Compose accepts
    (NAME=, NAME: value, export NAME, leading blanks, a bare NAME) counts;
    exactly one is allowed, and it must be the plain NAME=value form."""
    lines = text.splitlines()
    values, errors = {}, []
    for name in names:
        any_form = re.compile(rf"^\s*(export\s+)?{name}([^A-Za-z0-9_]|$)")
        hits = [l for l in lines if any_form.match(l)]
        if len(hits) != 1:
            errors.append(f"env file must set {name} exactly once (found {len(hits)})")
            continue
        line = hits[0]
        if not line.startswith(f"{name}="):
            errors.append(f"env file must set {name} in the plain form {name}=<value>")
            continue
        value = line[len(name) + 1:]
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif "#" in value:
            errors.append(f"{name} must not carry an inline comment")
            continue
        else:
            value = value.strip()
        values[name] = value
    return values, errors


def compose_subnets(path=COMPOSE_PATH):
    """The IPAM subnets of every network in deploy/compose.json."""
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    nets = []
    for spec in (doc.get("networks") or {}).values():
        for cfg in ((spec or {}).get("ipam") or {}).get("config") or []:
            if cfg.get("subnet"):
                nets.append(ipaddress.ip_network(cfg["subnet"]))
    return nets


def check(text, environ, compose_path=COMPOSE_PATH):
    """[errors] for env-file text; empty means the settings are acceptable."""
    errors = [f"{n} is set in the process environment; Compose would prefer it to the "
              "env file. Unset it." for n in NAMES if n in environ]
    try:
        avoid = [n for n in compose_subnets(compose_path) if n.version == 4]
    except (OSError, ValueError, AttributeError) as err:
        return errors + [f"cannot read the crm-net subnet from {compose_path}: {type(err).__name__}"]
    values, env_errors = read_env_values(text)
    errors += env_errors
    bind_errors = sources_errors = ["missing"]
    if "CRM_BIND_IP" in values:
        bind_errors = validate_bind_ip(values["CRM_BIND_IP"])
        errors += bind_errors
    if "CRM_ALLOWED_SOURCES" in values:
        sources_errors = validate_sources(values["CRM_ALLOWED_SOURCES"], avoid)
        errors += sources_errors
    if not bind_errors and not sources_errors:
        errors += validate_bind_in_sources(values["CRM_BIND_IP"], values["CRM_ALLOWED_SOURCES"])
    if "CRM_SITE_URL" in values:
        bind = values.get("CRM_BIND_IP")
        errors += validate_site_url(values["CRM_SITE_URL"],
                                    bind if bind and not validate_bind_ip(bind) else None)
    return errors


# --- beta (CRM-007) -----------------------------------------------------------
# crm-beta is reachable only through the edge proxy (crm-beta-edge, HAProxy on
# the host network). crm-app publishes only 127.0.0.1:${CRM_BETA_APP_PORT}.
# The edge configuration is rendered from the Git-controlled template
# deploy/beta/edge/haproxy.cfg.tmpl and validated fail-closed, both the values
# (validate_beta) and the rendered text (check_edge_config).

BETA_DEFAULT_RUNTIME = "/srv/CRM/runtime/beta"
BETA_COMPOSE_PATH = os.path.join(REPO, "deploy", "beta", "compose.json")
BETA_ENV_EXAMPLE_PATH = os.path.join(REPO, "deploy", "beta", "env.example")
EDGE_TEMPLATE_PATH = os.path.join(REPO, "deploy", "beta", "edge", "haproxy.cfg.tmpl")
EDGE_CFG_REL = os.path.join("edge", "haproxy.cfg")
EDGE_SERVICE = "crm-beta-edge"
BETA_NAMES = ("CRM_BETA_BIND_IP", "CRM_BETA_PORT", "CRM_BETA_UPSTREAM_SOURCES",
              "CRM_BETA_HOSTNAME", "CRM_BETA_APP_PORT", "CRM_SITE_URL")
MAX_UPSTREAM_SOURCES = 4
# CRM-009: CRM_BETA_MODE selects production (the default: absent or empty) or
# uat. It is optional, so it is not in BETA_NAMES (each of which must be set
# exactly once). In uat mode CRM_BETA_HOSTNAME is optional too (and must be empty).
BETA_MODE_NAME = "CRM_BETA_MODE"
BETA_MODES = ("production", "uat")
UAT_MIN_PREFIX = 16
# UAT sources must not overlap a Docker bridge subnet: the edge runs on the
# host network, so a container on any bridge reaches it from that bridge's
# subnet. crm-beta-net has no fixed subnet (Docker assigns it from its default
# bridge pool inside 172.16.0.0/12), so the whole of 172.16.0.0/12 is refused,
# plus every subnet deploy/compose.json (crm-dev) declares.
DOCKER_DEFAULT_POOL = ipaddress.IPv4Network("172.16.0.0/12")
# A strict DNS name: at least two labels, letters/digits/hyphens, no leading or
# trailing hyphen, each label 1-63 characters, 253 characters at most.
HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
                         r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$")
APP_PORT_BIND = re.compile(r"^127\.0\.0\.1:\$\{CRM_BETA_APP_PORT:\?[^}]*\}:80$")


def _private_unicast(addr):
    return (not addr.is_unspecified and addr.packed[0] != 0 and not addr.is_loopback
            and not addr.is_multicast and not addr.is_reserved and not addr.is_link_local
            and any(addr in block for block in RFC1918))


def validate_beta_bind_ip(value):
    if not value:
        return ["CRM_BETA_BIND_IP is empty"]
    addr = _ipv4(value)
    if addr is None:
        return ["CRM_BETA_BIND_IP is not exactly one IPv4 address in dotted-quad form"]
    if addr.is_unspecified:
        return ["CRM_BETA_BIND_IP is the unspecified address (would bind all interfaces)"]
    if not _private_unicast(addr):
        return ["CRM_BETA_BIND_IP is not a unicast RFC 1918 address"]
    return []


def validate_port(name, value):
    if not value or not re.fullmatch(r"[1-9][0-9]{3,4}", value) or not 1024 <= int(value) <= 65535:
        return [f"{name} is not an integer port between 1024 and 65535"]
    return []


def validate_upstream_sources(value):
    """1-4 space-separated RFC 1918 single hosts, as a.b.c.d or a.b.c.d/32."""
    if value is None or value.strip() == "":
        return ["CRM_BETA_UPSTREAM_SOURCES is empty"]
    if not re.fullmatch(r"[0-9./ ]+", value):
        return ["CRM_BETA_UPSTREAM_SOURCES may contain only IPv4 /32s separated by spaces"]
    # Exactly a.b.c.d or a.b.c.d/32 per entry (a bare trailing "/" is refused).
    tokens = value.split()
    out = []
    if len(tokens) > MAX_UPSTREAM_SOURCES:
        out.append(f"CRM_BETA_UPSTREAM_SOURCES has {len(tokens)} entries; at most "
                   f"{MAX_UPSTREAM_SOURCES} are allowed")
    for i, token in enumerate(tokens, start=1):
        where = f"CRM_BETA_UPSTREAM_SOURCES entry {i}"
        m = re.fullmatch(r"([0-9.]+)(/32)?", token)
        if not m:
            out.append(f"{where} is not a single host (exactly a.b.c.d or a.b.c.d/32)")
            continue
        address = m.group(1)
        addr = _ipv4(address)
        if addr is None:
            out.append(f"{where} is not an IPv4 address")
            continue
        if not _private_unicast(addr):
            out.append(f"{where} is not a unicast RFC 1918 host")
    return out


def read_optional_value(text, name):
    """(value or None if absent, [errors]) for an optional env-file name: absent
    is allowed; otherwise the read_env_values rules apply (once, plain form)."""
    any_form = re.compile(rf"^\s*(export\s+)?{name}([^A-Za-z0-9_]|$)")
    if not any(any_form.match(l) for l in text.splitlines()):
        return None, []
    values, errors = read_env_values(text, (name,))
    return values.get(name), errors


def beta_mode(text):
    """(mode, [errors]) from beta env-file text: production when CRM_BETA_MODE is
    absent or empty, uat, or (None, errors) for anything else (fail closed)."""
    value, errors = read_optional_value(text, BETA_MODE_NAME)
    if errors:
        return None, errors
    if value in (None, ""):
        return "production", []
    if value not in BETA_MODES:
        return None, [f"{BETA_MODE_NAME} must be empty, 'production' or 'uat'"]
    return value, []


def validate_uat_sources(value, avoid=()):
    """CRM-009 UAT mode: 1-4 space-separated RFC 1918 IPv4 networks a.b.c.d/N,
    N 16-32, no host bits set, none overlapping a Docker bridge subnet
    (DOCKER_DEFAULT_POOL and avoid)."""
    if value is None or value.strip() == "":
        return ["CRM_BETA_UPSTREAM_SOURCES is empty"]
    if not re.fullmatch(r"[0-9./ ]+", value):
        return ["CRM_BETA_UPSTREAM_SOURCES may contain only IPv4 networks separated by spaces"]
    tokens = value.split()
    out = []
    if len(tokens) > MAX_UPSTREAM_SOURCES:
        out.append(f"CRM_BETA_UPSTREAM_SOURCES has {len(tokens)} entries; at most "
                   f"{MAX_UPSTREAM_SOURCES} are allowed")
    for i, token in enumerate(tokens, start=1):
        where = f"CRM_BETA_UPSTREAM_SOURCES entry {i}"
        if not CIDR.fullmatch(token) or _ipv4(token.split("/")[0]) is None:
            out.append(f"{where} is not an IPv4 network of the form a.b.c.d/N")
            continue
        try:
            net = ipaddress.IPv4Network(token, strict=True)
        except ValueError:
            out.append(f"{where} is not a valid network (bad prefix or host bits set)")
            continue
        if not UAT_MIN_PREFIX <= net.prefixlen <= 32:
            out.append(f"{where} must have a prefix from /{UAT_MIN_PREFIX} to /32")
            continue
        if not any(net.subnet_of(block) for block in RFC1918):
            out.append(f"{where} is not inside an RFC 1918 private block")
            continue
        if net.overlaps(DOCKER_DEFAULT_POOL) or any(net.overlaps(o) for o in avoid):
            out.append(f"{where} overlaps a Docker bridge subnet (172.16.0.0/12 or a crm-dev "
                       "compose network), which would admit traffic from containers")
    return out


def validate_uat_site_url(value, bind_ip, port):
    if value not in (f"http://{bind_ip}:{port}", f"http://{bind_ip}:{port}/"):
        return ["CRM_SITE_URL must be exactly http://<CRM_BETA_BIND_IP>:<CRM_BETA_PORT> in uat mode"]
    return []


def validate_hostname(value):
    if not value or not HOSTNAME_RE.match(value):
        return ["CRM_BETA_HOSTNAME is not a lower-case DNS name (letters, digits, hyphens, "
                "at least two labels)"]
    return []


def validate_beta_site_url(value, hostname):
    if value != f"https://{hostname}":
        return ["CRM_SITE_URL must be exactly https://<CRM_BETA_HOSTNAME>"]
    return []


def _dev_subnets():
    """The IPv4 subnets deploy/compose.json (crm-dev) declares; fail closed."""
    return [n for n in compose_subnets(COMPOSE_PATH) if n.version == 4]


def validate_beta(values, mode="production"):
    errors = []
    errors += validate_beta_bind_ip(values.get("CRM_BETA_BIND_IP"))
    errors += validate_port("CRM_BETA_PORT", values.get("CRM_BETA_PORT"))
    errors += validate_port("CRM_BETA_APP_PORT", values.get("CRM_BETA_APP_PORT"))
    if mode == "uat":
        try:
            avoid = _dev_subnets()
        except (OSError, ValueError, AttributeError) as err:
            return errors + [f"cannot read the crm-dev subnets from {COMPOSE_PATH}: "
                             f"{type(err).__name__}"]
        errors += validate_uat_sources(values.get("CRM_BETA_UPSTREAM_SOURCES"), avoid)
        if values.get("CRM_BETA_HOSTNAME"):
            errors.append("CRM_BETA_HOSTNAME must be empty or absent in uat mode")
        if not errors:
            errors += validate_uat_site_url(values.get("CRM_SITE_URL"),
                                            values["CRM_BETA_BIND_IP"], values["CRM_BETA_PORT"])
    elif mode == "production":
        errors += validate_upstream_sources(values.get("CRM_BETA_UPSTREAM_SOURCES"))
        errors += validate_hostname(values.get("CRM_BETA_HOSTNAME"))
        if not validate_hostname(values.get("CRM_BETA_HOSTNAME")) and "CRM_SITE_URL" in values:
            errors += validate_beta_site_url(values["CRM_SITE_URL"], values["CRM_BETA_HOSTNAME"])
    else:
        return errors + ["unknown CRM_BETA_MODE"]
    if not errors and values["CRM_BETA_PORT"] == values["CRM_BETA_APP_PORT"]:
        errors.append("CRM_BETA_PORT and CRM_BETA_APP_PORT must differ")
    for name in ("CRM_BETA_PORT", "CRM_BETA_APP_PORT"):
        if values.get(name) == str(PORT):
            errors.append(f"{name} must not be {PORT}, the crm-dev port (seeding refuses beta by it)")
    return errors


# Bind sources deploy/beta/compose.json may use: the env-file path variables
# (checked against $CRM_RUNTIME_DIR by require_runtime_paths and the resolved
# config by require_compose_mounts), literal paths under the beta runtime, and
# relative paths inside the release directory.
BETA_BIND_VAR = re.compile(r"\$\{CRM_(DB|DATA|CUSTOM|CLIENT_CUSTOM)_DIR:\?[^}]*\}")


def _bind_source_ok(src):
    if not isinstance(src, str) or "docker.sock" in src or ".." in src.split("/"):
        return False
    if BETA_BIND_VAR.fullmatch(src) or src == PROXY_MOUNT_SOURCE:
        return True
    if src.startswith(BETA_DEFAULT_RUNTIME + "/") and "$" not in src:
        return True
    return src.startswith("./") and "$" not in src and "//" not in src


# CRM-007R: a top-level beta network may be only {}, {"driver": "bridge"},
# {"internal": true} or a combination of those. driver_opts (a routed bridge),
# ipam, any other driver (macvlan, ipvlan, host, ...) and any other key are refused.
BETA_NETWORK_KEYS = frozenset({"driver", "internal"})


def _beta_network_errors(name, spec):
    out = [f"beta compose network {name}: key {key!r} is not allowed (only driver: bridge "
           "and internal: true)" for key in sorted(set(spec) - BETA_NETWORK_KEYS)]
    if "driver" in spec and spec["driver"] != "bridge":
        out.append(f"beta compose network {name}: driver {spec['driver']!r} is refused "
                   "(only bridge)")
    if "internal" in spec and spec["internal"] is not True:
        out.append(f"beta compose network {name}: internal may only be true")
    return out


def _beta_resources_errors(doc, services):
    """No external or named networks/volumes, no bind source outside the beta
    runtime or the release directory, never docker.sock."""
    out = []
    for kind in ("networks", "volumes"):
        top = doc.get(kind) or {}
        if not isinstance(top, dict):
            out.append(f"beta compose top-level {kind} is not a mapping")
            continue
        for name, spec in top.items():
            if spec is not None and not isinstance(spec, dict):
                out.append(f"beta compose {kind[:-1]} {name}: not a mapping")
            elif spec and ("external" in spec or "name" in spec):
                out.append(f"beta compose {kind[:-1]} {name}: external or named {kind} are refused")
            elif kind == "networks":
                out += _beta_network_errors(name, spec or {})
    if doc.get("volumes"):
        out.append("beta compose declares named volumes; crm-beta uses bind mounts only")
    if "docker.sock" in json.dumps(doc):
        out.append("beta compose mentions docker.sock")
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        for vol in svc.get("volumes") or []:
            if isinstance(vol, str):
                src, typ = vol.split(":", 1)[0], ("bind" if vol[:1] in "./$~" else "volume")
            elif isinstance(vol, dict):
                src, typ = vol.get("source"), vol.get("type")
            else:
                out.append(f"{name}: unreadable volume entry")
                continue
            if typ != "bind":
                out.append(f"{name}: {typ!r} mount refused; crm-beta uses bind mounts only")
            elif not _bind_source_ok(src):
                out.append(f"{name}: bind source {src!r} is outside the beta runtime and the "
                           "release directory")
    return out


# The allowlist (CRM-007 r4): every key deploy/beta/compose.json may use. Any
# other key (volumes_from, pid, ipc, env_file, extends, include, external_links,
# secrets, configs, container_name, devices, privileged, cap_add, build,
# x-*, ...) is refused, so a new Compose feature cannot widen the policy.
BETA_TOP_KEYS = frozenset({"name", "services", "networks"})
BETA_SERVICE_KEYS = frozenset({"image", "environment", "healthcheck", "networks", "ports",
                               "restart", "volumes", "depends_on", "entrypoint", "command"})
BETA_EDGE_KEYS = BETA_SERVICE_KEYS | {"cap_drop", "read_only", "security_opt", "user",
                                      "network_mode"}
# name[:tag]@sha256:<64 hex>: every image is pinned by digest.
PINNED_IMAGE = re.compile(r"^[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*"
                          r"(?:/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*)*"
                          r"(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?@sha256:[0-9a-f]{64}$")


def _beta_allowlist_errors(doc, services):
    out = [f"beta compose top-level key {key!r} is not allowed"
           for key in sorted(set(doc) - BETA_TOP_KEYS)]
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        allowed = BETA_EDGE_KEYS if name == EDGE_SERVICE else BETA_SERVICE_KEYS
        out += [f"{name}: key {key!r} is not allowed" for key in sorted(set(svc) - allowed)]
        image = svc.get("image")
        if not isinstance(image, str) or not PINNED_IMAGE.match(image):
            out.append(f"{name}: image must be pinned as name@sha256:<64 hex>")
    return out


# CRM-009: crm-app mounts the Git-controlled scheme policy file for
# CRM_BETA_MODE straight from the release directory. Compose resolves the
# source from the env file: absent or empty -> crm-proxy.conf (production, as
# before), production -> crm-proxy-production.conf (a byte-identical copy,
# enforced), uat -> crm-proxy-uat.conf. check_beta checks the file the mode
# resolves to with that mode's policy, and refuses any other mode value, so no
# mode can mount an unchecked file. A mode change changes the resolved source,
# so `up` recreates crm-app.
PROXY_TARGET = "/etc/apache2/conf-enabled/crm-proxy.conf"
PROXY_MOUNT_SOURCE = "./apache/crm-proxy${CRM_BETA_MODE:+-${CRM_BETA_MODE}}.conf"


def _mount_fields(vol):
    if isinstance(vol, dict):
        return vol.get("source"), vol.get("target"), vol
    if isinstance(vol, str):
        parts = vol.split(":")
        return parts[0], (parts[1] if len(parts) > 1 else None), None
    return None, None, None


def _beta_proxy_mount_errors(services):
    """crm-app mounts exactly the scheme policy file for CRM_BETA_MODE
    (PROXY_MOUNT_SOURCE), read-only, directly from the release directory (it
    is never copied anywhere), at PROXY_TARGET; nothing else mounts anything
    into /etc/apache2 or mounts an apache file from anywhere else."""
    out, found = [], []
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        for vol in svc.get("volumes") or []:
            src, target, spec = _mount_fields(vol)
            apache_src = isinstance(src, str) and ("/apache/" in src or src.startswith("apache/"))
            apache_dst = isinstance(target, str) and (target == "/etc/apache2"
                                                      or target.startswith("/etc/apache2/"))
            if not (apache_src or apache_dst):
                continue
            if name == "crm-app" and target == PROXY_TARGET and src == PROXY_MOUNT_SOURCE \
                    and spec is not None and spec.get("type") == "bind" \
                    and spec.get("read_only") is True and set(spec) == {
                        "type", "source", "target", "read_only"}:
                found.append(vol)
            else:
                out.append(f"{name}: mount into /etc/apache2 or of an apache file is refused "
                           f"(only crm-app {PROXY_MOUNT_SOURCE} -> {PROXY_TARGET}, read-only)")
    if len(found) != 1:
        out.append(f"crm-app must mount exactly {PROXY_MOUNT_SOURCE} read-only at {PROXY_TARGET} "
                   "(the scheme policy file for CRM_BETA_MODE)")
    return out


def check_beta_compose(doc):
    """The beta bind policy, on deploy/beta/compose.json: only allowlisted keys,
    every image pinned by digest, crm-app publishes exactly
    127.0.0.1:${CRM_BETA_APP_PORT}:80, the edge runs hardened on the host
    network and publishes nothing, and no other service publishes a port."""
    out = []
    services = doc.get("services") if isinstance(doc, dict) else None
    if not isinstance(services, dict):
        return ["beta compose has no services"]
    if doc.get("name") != "crm-beta":
        out.append("beta compose project name is not crm-beta")
    out += _beta_allowlist_errors(doc, services)
    for name, svc in services.items():
        if not isinstance(svc, dict):
            out.append(f"{name}: not a mapping")
            continue
        ports = svc.get("ports") or []
        if name == "crm-app":
            if (len(ports) != 1 or not isinstance(ports[0], str)
                    or not APP_PORT_BIND.match(ports[0])):
                out.append("crm-app must publish exactly 127.0.0.1:${CRM_BETA_APP_PORT}:80")
        elif ports:
            out.append(f"{name}: publishes ports; only crm-app may (on loopback)")
        if svc.get("network_mode") == "host" and name != EDGE_SERVICE:
            out.append(f"{name}: network_mode host is allowed for {EDGE_SERVICE} only")
    out += _beta_resources_errors(doc, services)
    out += _beta_proxy_mount_errors(services)
    edge = services.get(EDGE_SERVICE)
    if not isinstance(edge, dict):
        return out + [f"{EDGE_SERVICE} service missing"]
    if edge.get("network_mode") != "host":
        out.append(f"{EDGE_SERVICE} must use network_mode host (to see real source addresses)")
    if edge.get("read_only") is not True:
        out.append(f"{EDGE_SERVICE} must have a read-only root filesystem")
    if edge.get("cap_drop") != ["ALL"]:
        out.append(f"{EDGE_SERVICE} must drop all capabilities")
    if edge.get("cap_add"):
        out.append(f"{EDGE_SERVICE} adds capabilities; its port is unprivileged, so none are needed")
    if "no-new-privileges:true" not in (edge.get("security_opt") or []):
        out.append(f"{EDGE_SERVICE} must set no-new-privileges")
    user = edge.get("user")
    uid = str(user).split(":", 1)[0].strip() if user is not None else ""
    if user is None or uid == "":
        out.append(f"{EDGE_SERVICE} must set a non-root user")
    elif uid == "root" or re.fullmatch(r"\+?0+", uid):
        out.append(f"{EDGE_SERVICE} must not run as root (uid 0 in any form)")
    if edge.get("privileged"):
        out.append(f"{EDGE_SERVICE} must not be privileged")
    return out


def _edge_lines(text):
    """Non-comment lines, each with any run of spaces or tabs as one space."""
    out = []
    for raw in text.splitlines():
        line = " ".join(raw.split("#", 1)[0].split())
        if line:
            out.append(line)
    return out


# The sections and directives the template uses; nothing else is accepted.
EDGE_SECTIONS = {
    "global": {"log", "maxconn"},
    "defaults": {"mode", "log", "option", "timeout"},
    "frontend crm_beta_edge": {"bind", "acl", "http-request", "default_backend"},
    "backend crm_beta_app": {"option", "server"},
}
EDGE_OPTIONS = {"defaults": {"option httplog"}, "backend crm_beta_app": {"option forwardfor"}}
EDGE_HTTP_REQUEST_ACTIONS = {"del-header", "deny"}


def _edge_structure_errors(lines):
    out, section, seen = [], None, []
    for line in lines:
        word = line.split()[0]
        if word in ("global", "defaults", "frontend", "backend", "listen", "userlist",
                    "peers", "resolvers", "mailers", "program", "cache", "ring",
                    "http-errors", "fcgi-app"):
            section = line
            if section not in EDGE_SECTIONS:
                out.append(f"edge section not allowed: {line}")
            elif section in seen:
                out.append(f"edge section repeated: {line}")
            seen.append(section)
            continue
        if section is None:
            out.append(f"edge directive outside any section: {line}")
            continue
        allowed = EDGE_SECTIONS.get(section)
        if allowed is None:
            continue  # the section itself is already refused
        if word == "use_backend":
            out.append("edge must not use use_backend (only default_backend crm_beta_app)")
        elif word not in allowed:
            out.append(f"edge directive not allowed in '{section}': {word}")
        elif word == "option" and line not in EDGE_OPTIONS.get(section, set()):
            out.append(f"edge option not allowed in '{section}': {line}")
        elif word == "http-request":
            action = line.split()[1] if len(line.split()) > 1 else ""
            if action not in EDGE_HTTP_REQUEST_ACTIONS:
                out.append(f"edge http-request action not allowed: {action or '<none>'}")
        elif word == "default_backend" and line != "default_backend crm_beta_app":
            out.append("edge default_backend must be crm_beta_app")
        elif word == "mode" and line != "mode http":
            out.append(f"edge must run in mode http, not '{line}'")
    if set(seen) != set(EDGE_SECTIONS):
        out.append("edge must have exactly the sections global, defaults, "
                   "frontend crm_beta_edge and backend crm_beta_app")
    return out


def check_edge_config(text, mode="production"):
    """The edge policy, on rendered HAProxy configuration text. [] = acceptable.
    CRM-009: in uat mode the trusted_upstream list holds networks
    (validate_uat_sources) instead of single hosts."""
    lines = _edge_lines(text)
    out = _edge_structure_errors(lines)
    binds = [l for l in lines if l.split()[0] == "bind"]
    if len(binds) != 1:
        out.append(f"edge must have exactly one bind line (found {len(binds)})")
    for b in binds:
        parts = b.split()
        addr, _, port = (parts[1] if len(parts) > 1 else "").rpartition(":")
        ip = _ipv4(addr)
        if ip is None or not _private_unicast(ip):
            out.append("edge bind address is not one RFC 1918 unicast address "
                       "(all interfaces, a wildcard or a name are refused)")
        if validate_port("edge bind port", port):
            out.append("edge bind port is not between 1024 and 65535")
        if len(parts) != 2:
            out.append("edge bind line carries extra options")
    if "mode http" not in lines:
        out.append("edge must run in mode http")
    for t in ("timeout connect", "timeout client", "timeout server", "timeout http-request"):
        if not any(l.startswith(t + " ") for l in lines):
            out.append(f"edge must set {t}")
    acls = [l.split() for l in lines if l.startswith("acl trusted_upstream ")]
    if len(acls) != 1 or len(acls[0]) < 4 or acls[0][2] != "src":
        out.append("edge must define exactly one 'acl trusted_upstream src <hosts>' with a "
                   "source list")
    else:
        listed = " ".join(acls[0][3:])
        if mode == "production":
            problems = validate_upstream_sources(listed)
        elif mode == "uat":
            try:
                problems = validate_uat_sources(listed, _dev_subnets())
            except (OSError, ValueError, AttributeError) as err:
                problems = [f"cannot read the crm-dev subnets: {type(err).__name__}"]
        else:
            problems = ["unknown CRM_BETA_MODE"]
        out += [e.replace("CRM_BETA_UPSTREAM_SOURCES", "edge trusted_upstream") for e in problems]
    other_acl = [l for l in lines if l.startswith("acl ") and not l.startswith("acl trusted_upstream ")]
    if other_acl:
        out.append("edge defines other ACLs; only trusted_upstream is allowed")
    deny = "http-request deny deny_status 403 if !trusted_upstream"
    reqs = [l for l in lines if l.startswith("http-request ")]
    if not reqs or reqs[0] != "http-request del-header X-Forwarded-For if !trusted_upstream" \
            or len(reqs) < 2 or reqs[1] != deny:
        out.append("edge must first delete X-Forwarded-For from untrusted sources and then "
                   "deny them with 403, before any other http-request rule")
    for l in reqs:
        if re.search(r"(?i)x-forwarded|forwarded", l) and "set-header" in l \
                and not l.endswith(" if trusted_upstream"):
            out.append("a forwarded header is set without the trusted_upstream condition")
    if any(l.startswith("tcp-request") or l.startswith("http-request allow") for l in lines):
        out.append("edge must not use tcp-request or http-request allow rules")
    fwd = [l for l in lines if l.startswith("option forwardfor")]
    if fwd != ["option forwardfor"]:
        out.append("edge must have exactly one plain 'option forwardfor' (after the deny, so "
                   "only trusted requests carry it)")
    servers = [l.split() for l in lines if l.startswith("server ")]
    if len(servers) > 1:
        out.append(f"edge must have exactly one server (found {len(servers)})")
    if len(servers) != 1 or len(servers[0]) < 3 or not re.fullmatch(
            r"127\.0\.0\.1:[0-9]{4,5}", servers[0][2]) \
            or validate_port("edge server port", servers[0][2].rsplit(":", 1)[1]):
        out.append("edge must forward to exactly one server on 127.0.0.1:<CRM_BETA_APP_PORT>")
    if _edge_wildcard_lines(lines, mode):
        out.append("edge configuration names an unspecified address or a wildcard")
    return out


def _base_wildcard_rule(line):
    """The base (CRM-007) substring rule, unchanged: any "0.0.0.0", any "::" or
    a "*:" token anywhere in the line."""
    return "0.0.0.0" in line or re.search(r"(^|\s)\*:", line) or "::" in line


def _edge_wildcard_lines(lines, mode):
    """The lines that name an unspecified address or a wildcard (CRM-009 r3,
    PL decision on prod-edge-check-relaxed). production (and any other mode):
    the base substring rule on every line, unchanged, so production refuses at
    least everything base refused. uat: the same, except on the single
    `acl trusted_upstream src ...` line, whose networks may legitimately
    contain the text "0.0.0.0" (the first /16 of 10/8). With no or several such lines
    nothing is exempt. In both modes every trusted_upstream line also gets the
    parsed check (_wildcard_token), which in production only adds refusals."""
    acl = [l for l in lines if l.startswith("acl trusted_upstream src ")]
    exempt = acl[0] if mode == "uat" and len(acl) == 1 else None
    bad = []
    for l in lines:
        if l != exempt and _base_wildcard_rule(l):
            bad.append(l)
        elif l in acl and any(_wildcard_token(t) for t in l.split()):
            bad.append(l)
    return bad


def _strip_quotes(text):
    """text without any surrounding single or double quotes."""
    return text.strip("'\"")


def _address_candidates(token):
    """The address-like parts of one config token: the token itself and, for
    comma lists, quoted forms, [addr]:port, addr:port (any port text: 8443, *,
    a name), addr/N and ipv4@/ipv6@ forms, the address alone."""
    out = []
    for part in _strip_quotes(token).split(","):
        part = _strip_quotes(part)
        for prefix in ("ipv4@", "ipv6@"):
            if part.lower().startswith(prefix):
                part = part[len(prefix):]
        found = [part]
        bracket = re.fullmatch(r"\[([^\]]*)\](?::[^:]*)?", part)
        if bracket:
            found.append(bracket.group(1))
        host, sep, _port = part.rpartition(":")
        if sep:
            found.append(host)  # "0.0.0.0:8443"/"0.0.0.0:*" -> "0.0.0.0", ":::8443" -> "::"
        for cand in list(found):
            if "/" in cand:
                found.append(cand.split("/", 1)[0])
        out += [_strip_quotes(c) for c in found]
    return out


def _legacy_ipv4_unspecified(cand):
    """True for the classic inet_aton spellings of 0.0.0.0 that ipaddress
    refuses: "0", "00", "0x0", "0.0", "0x0.0.0.0", "0000.0.0.0" ..."""
    if not re.fullmatch(r"(?i)(0x[0-9a-f]+|[0-9]+)(\.(0x[0-9a-f]+|[0-9]+)){0,3}", cand):
        return False
    try:
        return socket.inet_aton(cand) == b"\0\0\0\0"
    except OSError:
        return False


def _wildcard_token(token):
    """True if token names the unspecified address (0.0.0.0 or ::, in any
    spelling ipaddress or inet_aton accepts, quoted or not, with or without /N
    or :port, the port numeric or not) or the * wildcard. Parsed, never a
    substring match: a 10/8 network whose text contains "0.0.0.0" is not a
    wildcard. Used only on the UAT trusted_upstream line (_edge_wildcard_lines)."""
    for cand in _address_candidates(token):
        if cand == "*" or _legacy_ipv4_unspecified(cand):
            return True
        try:
            addr = ipaddress.ip_address(cand)
        except ValueError:
            continue
        if addr.is_unspecified:
            return True
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None \
                and addr.ipv4_mapped.is_unspecified:
            return True
    return False


PROXY_CONF_PATH = os.path.join(REPO, "deploy", "beta", "apache", "crm-proxy.conf")
PROXY_UAT_CONF_PATH = os.path.join(REPO, "deploy", "beta", "apache", "crm-proxy-uat.conf")
PROXY_PRODUCTION_COPY_PATH = os.path.join(REPO, "deploy", "beta", "apache",
                                          "crm-proxy-production.conf")
# CRM-009: the Git-controlled scheme policy file for each CRM_BETA_MODE.
PROXY_CONFS = {"production": PROXY_CONF_PATH, "uat": PROXY_UAT_CONF_PATH}


def proxy_conf_for(text):
    """(mode, path of the file Compose mounts for it) from beta env-file text,
    as PROXY_MOUNT_SOURCE resolves; (None, None) for a refused mode."""
    value, errors = read_optional_value(text, BETA_MODE_NAME)
    mode = beta_mode(text)[0]
    if errors or mode is None:
        return None, None
    if value == "production":
        return mode, PROXY_PRODUCTION_COPY_PATH
    return mode, PROXY_CONFS[mode]


def proxy_copy_errors(original=None, copy=None):
    """crm-proxy-production.conf must be byte for byte crm-proxy.conf (the
    paths default to the module constants, read at call time)."""
    original = PROXY_CONF_PATH if original is None else original
    copy = PROXY_PRODUCTION_COPY_PATH if copy is None else copy
    try:
        with open(original, "rb") as a, open(copy, "rb") as b:
            same = a.read() == b.read()
    except OSError as err:
        return [f"cannot compare {os.path.basename(copy)} with crm-proxy.conf: "
                f"{type(err).__name__}"]
    return [] if same else [f"{os.path.basename(copy)} must be byte for byte crm-proxy.conf"]
PROXY_MODULES = {"env_module": "/usr/lib/apache2/modules/mod_env.so",
                 "headers_module": "/usr/lib/apache2/modules/mod_headers.so"}


def check_proxy_conf(text, mode="production"):
    """The crm-app HTTPS policy (PL decision on CRM-007 r1), on
    deploy/beta/apache/crm-proxy.conf text. [] = acceptable.

    Exactly one unconditional `SetEnv HTTPS on` and one unconditional
    `RequestHeader unset X-Forwarded-Proto` at top level. The only blocks allowed
    are `<IfModule !env_module|!headers_module>` holding just the matching
    LoadModule. Nothing may make the scheme depend on the request or the peer.

    CRM-009, mode "uat" (deploy/beta/apache/crm-proxy-uat.conf): the same, but
    with no SetEnv at all (plain HTTP), so only the header removal and the
    `<IfModule !headers_module>` block are allowed."""
    if mode not in PROXY_CONFS:
        return ["unknown CRM_BETA_MODE for the scheme policy"]
    name = os.path.basename(PROXY_CONFS[mode])
    allowed = ("SetEnv HTTPS on", "RequestHeader unset X-Forwarded-Proto") \
        if mode == "production" else ("RequestHeader unset X-Forwarded-Proto",)
    modules = PROXY_MODULES if mode == "production" else {
        "headers_module": PROXY_MODULES["headers_module"]}
    out = []
    lines = _edge_lines(text)  # comments and blank lines removed
    depth, block = 0, None
    top = []
    for line in lines:
        low = line.lower()
        if low.startswith("</"):
            if depth == 0:
                out.append(f"unbalanced closing tag: {line}")
                continue
            depth, block = depth - 1, None
            continue
        if low.startswith("<"):
            m = re.fullmatch(r"<IfModule\s+!(\w+)>", line)
            if depth != 0 or not m or m.group(1) not in modules:
                out.append(f"block not allowed (only <IfModule !{'|!'.join(modules)}>): {line}")
            depth, block = depth + 1, (m.group(1) if m else None)
            continue
        if depth:
            want = f"LoadModule {block} {PROXY_MODULES.get(block, '?')}"
            if " ".join(line.split()) != want:
                out.append(f"only '{want}' may appear inside <IfModule !{block}>")
            continue
        top.append(" ".join(line.split()))
    if depth:
        out.append("unclosed block")
    if mode == "production" and top.count("SetEnv HTTPS on") != 1:
        out.append("crm-proxy.conf must set 'SetEnv HTTPS on' exactly once, unconditionally")
    if top.count("RequestHeader unset X-Forwarded-Proto") != 1:
        out.append(f"{name} must 'RequestHeader unset X-Forwarded-Proto' exactly once, "
                   "unconditionally")
    for line in top:
        if line not in allowed:
            out.append(f"directive not allowed in {name}: {line}")
    return out


RESTORETEST_PROJECT = "crm-beta-restoretest"
RESTORETEST_COMPOSE_PATH = os.path.join(REPO, "deploy", "beta", "restoretest", "compose.json")
RESTORETEST_NETWORK = "restoretest-net"
# CRM-007R r3: the restore-test compose is an allowlist, as beta's is. Every key
# the shipped file uses, and nothing else: include, x-*, secrets, configs at top
# level, and depends_on, ports, network_mode, security_opt, labels, ... (any key
# not listed here, including restart/command/entrypoint, which the shipped file
# does not use) on crm-db are refused, so a new Compose feature cannot widen it.
RESTORETEST_TOP_KEYS = frozenset({"name", "services", "networks", "volumes"})
RESTORETEST_DB_KEYS = frozenset({"image", "environment", "volumes", "networks", "healthcheck"})
# A mount is {type: volume, source: <the project volume>, target: /var/lib/mysql}
# only: no bind/volume/tmpfs option blocks (bind, subpath, propagation, nocopy),
# no read_only/consistency.
RESTORETEST_MOUNT_KEYS = frozenset({"type", "source", "target"})


def check_restoretest_compose(doc):
    """The restore-test isolation policy, on deploy/beta/restoretest/compose.json.
    [] = acceptable. The throwaway project shares nothing with crm-beta or
    crm-dev: its own project name, one crm-db service on the registered MariaDB
    image, no published or exposed port, no host network, no bind mount, only
    its own project-scoped named volume and internal network (no `name:` or
    `external`, which could alias another project's resources). CRM-007R: the
    network may set only driver: bridge and internal: true (beta's allowlist),
    the volume only driver: local. r3: top-level and crm-db keys are allowlisted
    (RESTORETEST_TOP_KEYS, RESTORETEST_DB_KEYS) and the one mount may carry no
    options (RESTORETEST_MOUNT_KEYS)."""
    out = []
    if not isinstance(doc, dict):
        return ["restoretest compose is not a mapping"]
    out += [f"restoretest compose: top-level {key!r} is not allowed"
            for key in sorted(set(doc) - RESTORETEST_TOP_KEYS, key=str)]
    if doc.get("name") != RESTORETEST_PROJECT:
        out.append(f"restoretest compose project name is not {RESTORETEST_PROJECT}")
    services = doc.get("services")
    if not isinstance(services, dict) or set(services) != {"crm-db"}:
        return out + ["restoretest compose must define exactly one service, crm-db"]
    db = services["crm-db"]
    if not isinstance(db, dict):
        return out + ["crm-db: not a mapping"]
    out += [f"crm-db: key {key!r} is not allowed in the restore test"
            for key in sorted(set(db) - RESTORETEST_DB_KEYS, key=str)]
    image = db.get("image")
    if not isinstance(image, str) or not image.startswith("mariadb:") \
            or not PINNED_IMAGE.fullmatch(image):
        out.append("crm-db must use the digest-pinned mariadb image (mariadb:<tag>@sha256:<64 hex>)")
    vols = db.get("volumes") or []
    if not isinstance(vols, list) or len(vols) != 1 or not isinstance(vols[0], dict) \
            or vols[0].get("type") != "volume" or vols[0].get("target") != "/var/lib/mysql" \
            or not isinstance(vols[0].get("source"), str):
        out.append("crm-db must mount exactly one named volume at /var/lib/mysql (no bind mounts)")
    elif set(vols[0]) - RESTORETEST_MOUNT_KEYS:
        out.append("crm-db: the volume mount may set only type, source and target (refused: "
                   + ", ".join(repr(k) for k in sorted(set(vols[0]) - RESTORETEST_MOUNT_KEYS,
                                                       key=str)) + ")")
    vol_name = vols[0].get("source") if isinstance(vols, list) and vols \
        and isinstance(vols[0], dict) and isinstance(vols[0].get("source"), str) else None
    top_vols = doc.get("volumes")
    if not isinstance(top_vols, dict) or set(top_vols) != {vol_name}:
        out.append("restoretest compose must declare exactly the one volume crm-db mounts")
    else:
        spec = top_vols[vol_name] or {}
        if not isinstance(spec, dict) or "name" in spec or "external" in spec or "driver_opts" in spec:
            out.append("the restoretest volume must be project-scoped (no name, external or driver_opts)")
        elif set(spec) - {"driver"} or spec.get("driver", "local") != "local":
            out.append("the restoretest volume may set only driver: local")
    nets = db.get("networks")
    if not isinstance(nets, dict) or set(nets) != {RESTORETEST_NETWORK}:
        out.append(f"crm-db must join only {RESTORETEST_NETWORK}")
    top_nets = doc.get("networks")
    if not isinstance(top_nets, dict) or set(top_nets) != {RESTORETEST_NETWORK}:
        out.append(f"restoretest compose must declare only {RESTORETEST_NETWORK}")
    else:
        spec = top_nets[RESTORETEST_NETWORK] or {}
        if not isinstance(spec, dict) or "name" in spec or "external" in spec \
                or spec.get("internal") is not True:
            out.append(f"{RESTORETEST_NETWORK} must be internal and project-scoped "
                       "(no name or external)")
        else:  # the same allowlist as beta: only driver: bridge and internal: true
            out += _beta_network_errors(RESTORETEST_NETWORK, spec)
    return out


def render_edge(values, template_path=EDGE_TEMPLATE_PATH):
    """The edge configuration for already validated values."""
    with open(template_path, encoding="utf-8") as fh:
        text = fh.read()
    sources = " ".join(t if "/" in t else t + "/32"
                       for t in values["CRM_BETA_UPSTREAM_SOURCES"].split())
    subs = {"@CRM_BETA_BIND_IP@": values["CRM_BETA_BIND_IP"],
            "@CRM_BETA_PORT@": values["CRM_BETA_PORT"],
            "@CRM_BETA_UPSTREAM_SOURCES@": sources,
            "@CRM_BETA_APP_PORT@": values["CRM_BETA_APP_PORT"]}
    for key, val in subs.items():
        if text.count(key) != 1:
            raise ValueError(f"edge template must contain {key} exactly once")
        text = text.replace(key, val)
    if "@" in text:
        raise ValueError("edge template has an unknown placeholder")
    return text


def check_beta(text, environ, compose_path=BETA_COMPOSE_PATH, template_path=EDGE_TEMPLATE_PATH,
               proxy_conf_path=None):
    """([errors], rendered edge config or None) for beta env-file text.
    proxy_conf_path defaults to the scheme policy file for CRM_BETA_MODE."""
    errors = [f"{n} is set in the process environment; Compose would prefer it to the "
              "env file. Unset it." for n in BETA_NAMES + (BETA_MODE_NAME,) if n in environ]
    mode, mode_errors = beta_mode(text)
    if mode_errors:
        return errors + mode_errors, None
    if proxy_conf_path is None:
        proxy_conf_path = proxy_conf_for(text)[1]
        errors += proxy_copy_errors()
    try:
        with open(compose_path, encoding="utf-8") as fh:
            errors += check_beta_compose(json.load(fh))
    except (OSError, ValueError) as err:
        errors.append(f"cannot read {compose_path}: {type(err).__name__}")
    try:
        with open(proxy_conf_path, encoding="utf-8") as fh:
            errors += check_proxy_conf(fh.read(), mode)
    except (OSError, UnicodeDecodeError) as err:
        errors.append(f"cannot read {proxy_conf_path}: {type(err).__name__}")
    if mode == "uat":  # CRM_BETA_HOSTNAME is optional (and must be empty)
        values, env_errors = read_env_values(
            text, tuple(n for n in BETA_NAMES if n != "CRM_BETA_HOSTNAME"))
        hostname, host_errors = read_optional_value(text, "CRM_BETA_HOSTNAME")
        env_errors += host_errors
        values["CRM_BETA_HOSTNAME"] = hostname or ""
    else:
        values, env_errors = read_env_values(text, BETA_NAMES)
    errors += env_errors
    if env_errors:
        return errors, None
    errors += validate_beta(values, mode)
    if errors:
        return errors, None
    try:
        rendered = render_edge(values, template_path)
    except (OSError, ValueError) as err:
        return errors + [f"edge template: {err}"], None
    edge_errors = check_edge_config(rendered, mode)
    return errors + edge_errors, (None if edge_errors else rendered)



def write_edge_config(runtime, rendered):
    """Atomically write $runtime/edge/haproxy.cfg (dir 0755, file 0644: the edge
    runs as user haproxy and must read it; it holds no secret)."""
    edge_dir = os.path.join(runtime, "edge")
    if os.path.islink(edge_dir):
        raise OSError("edge directory is a symlink")
    os.makedirs(edge_dir, mode=0o755, exist_ok=True)
    os.chmod(edge_dir, 0o755)
    target = os.path.join(runtime, EDGE_CFG_REL)
    tmp = target + ".tmp"
    if os.path.lexists(tmp):
        os.unlink(tmp)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(rendered)
    os.chmod(tmp, 0o644)
    os.replace(tmp, target)
    return target


TEST_ROOT_PARENT = "/tmp/"


def beta_runtime(environ):
    """(runtime, None) or (None, why). beta's runtime is the constant
    BETA_DEFAULT_RUNTIME; the only seam, for tests, is CRM_TEST_ROOT, honoured
    only when it is a canonical existing directory under /tmp (runtime
    $CRM_TEST_ROOT/beta). A CRM_RUNTIME_DIR naming anything else is refused."""
    want = BETA_DEFAULT_RUNTIME
    root = environ.get("CRM_TEST_ROOT") or ""
    if root:
        if not root.startswith(TEST_ROOT_PARENT) or root == TEST_ROOT_PARENT:
            return None, f"CRM_TEST_ROOT must be under /tmp: {root}"
        if not os.path.isdir(root) or os.path.realpath(root) != root:
            return None, f"CRM_TEST_ROOT must be an existing canonical directory: {root}"
        want = os.path.join(root, "beta")
    given = environ.get("CRM_RUNTIME_DIR") or ""
    if given and given != want:
        return None, f"the beta runtime is {want} (CRM_RUNTIME_DIR is {given})"
    return want, None


BETA_APP_PORT_RE = re.compile(r"^[1-9][0-9]{3,4}$")


def target_runtime(target, environ):
    """(runtime, None) or (None, why): target's runtime directory, as the
    shell scripts' require_target resolves it (beta pinned by beta_runtime;
    dev from CRM_RUNTIME_DIR, default DEFAULT_RUNTIME; named after the target)."""
    if target == "beta":
        runtime, problem = beta_runtime(environ)
        if problem:
            return None, problem
    elif target == "dev":
        runtime = environ.get("CRM_RUNTIME_DIR") or DEFAULT_RUNTIME
    else:
        return None, f"target environment must be 'dev' or 'beta' (got '{target}')"
    if os.path.basename(runtime) != target:
        return None, f"runtime directory is not a {target} runtime: {runtime}"
    return runtime, None


# CRM-007R: an export is a new directory export-<name> directly under the
# target's constant backup directory $runtime/backups.
# Use fullmatch: `$` alone would also accept a trailing newline ("export-n\n").
EXPORT_NAME_RE = re.compile(r"export-[A-Za-z0-9._-]+")


def export_out_problem(target, out, environ):
    """None if out may be created as target's export directory; otherwise why
    not. out must be <target runtime>/backups/<export-name>, the backup
    directory a real (canonical, non-symlink) directory, and out must not
    exist yet (not even as a dangling symlink)."""
    runtime, problem = target_runtime(target, environ)
    if problem:
        return problem
    backups = os.path.join(runtime, "backups")
    name = os.path.basename(out)
    if not EXPORT_NAME_RE.fullmatch(name) or ".." in name:
        return "the export directory must be named export-[A-Za-z0-9._-]+ (no '..')"
    if out != os.path.join(backups, name):
        return f"the export directory must sit directly under {backups} (the {target} backups)"
    if os.path.islink(backups) or not os.path.isdir(backups) \
            or os.path.realpath(backups) != backups:
        return f"the {target} backup directory is not a real canonical directory: {backups}"
    if os.path.lexists(out):
        return f"the export directory already exists: {out}"
    return None


def pinned_base_url(target, environ):
    """(url, None) or (None, why): the one base URL the provisioning scripts
    may use for target (CRM-007R), read from that target's checked env file
    with read_env_values, never from input.
    - beta: http://127.0.0.1:<CRM_BETA_APP_PORT> (the runtime is pinned as for
      `check_access.py beta`);
    - dev: http://<CRM_BIND_IP>:8180 (CRM_BIND_IP as validated by
      `check_access.py dev`)."""
    runtime, problem = target_runtime(target, environ)
    if problem:
        return None, problem
    names = ("CRM_BETA_APP_PORT",) if target == "beta" else ("CRM_BIND_IP",)
    env_file = os.path.join(runtime, "env")
    if (environ.get("CRM_ENV_FILE") or env_file) != env_file:
        return None, f"the env file must be {env_file}"
    try:
        with open(env_file, encoding="utf-8") as fh:
            values, errors = read_env_values(fh.read(), names)
    except (OSError, UnicodeDecodeError):
        return None, f"env file not readable: {env_file}"
    if errors:
        return None, "; ".join(errors)
    if target == "beta":
        port = values["CRM_BETA_APP_PORT"]
        if not BETA_APP_PORT_RE.match(port) or not 1024 <= int(port) <= 65535:
            return None, f"CRM_BETA_APP_PORT in {env_file} is not a port 1024-65535"
        return f"http://127.0.0.1:{port}", None
    bind_errors = validate_bind_ip(values["CRM_BIND_IP"])
    if bind_errors:
        return None, "; ".join(bind_errors)
    return f"http://{values['CRM_BIND_IP']}:{PORT}", None


def base_url_problem(target, url, environ):
    """None if url is exactly target's pinned base URL; otherwise why not.
    The message never contains the URL or the bind address."""
    want, problem = pinned_base_url(target, environ)
    if problem:
        return f"cannot determine the {target} base URL: {problem}"
    if url != want:
        if target == "beta":
            return ("the beta base URL must be exactly http://127.0.0.1:<CRM_BETA_APP_PORT "
                    "from the beta env file>")
        return f"the dev base URL must be exactly http://<CRM_BIND_IP from the dev env file>:{PORT}"
    return None


def edge_config_problem(runtime, rendered):
    """None if $runtime/edge/haproxy.cfg is byte for byte what render_edge()
    gives for the checked env file; otherwise why not (fail closed: missing,
    a symlink, unreadable or different)."""
    path = os.path.join(runtime, EDGE_CFG_REL)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as fh:
            on_disk = fh.read()
    except OSError as err:
        return f"the edge configuration {path} is not readable ({type(err).__name__})"
    if on_disk != rendered.encode("utf-8"):
        return f"the edge configuration {path} differs from the one rendered from the env file"
    return None


def main(argv=None, environ=None):
    argv = sys.argv[1:] if argv is None else argv
    environ = os.environ if environ is None else environ
    target = argv[0] if argv else ""
    if argv == ["restoretest"]:
        # The restore-test isolation policy only (restore.sh beta --restoretest).
        try:
            with open(RESTORETEST_COMPOSE_PATH, encoding="utf-8") as fh:
                errors = check_restoretest_compose(json.load(fh))
        except (OSError, ValueError) as err:
            errors = [f"cannot read {RESTORETEST_COMPOSE_PATH}: {type(err).__name__}"]
        for err in errors:
            print(f"{prog()}: refused: {err}", file=sys.stderr)
        return 1 if errors else 0
    if target in ("dev", "beta") and argv[1:] == ["--base-url"]:
        # The pinned base URL of the target (beta: loopback only), for
        # deploy_release.sh and export.sh.
        url, problem = pinned_base_url(target, environ)
        if problem:
            print(f"{prog()}: refusing to run: {problem}", file=sys.stderr)
            return 1
        print(url)
        return 0
    render = target == "beta" and argv[1:] == ["--render"]
    show_mode = target == "beta" and argv[1:] == ["--mode"]
    if target not in ("dev", "beta") or (len(argv) != 1 and not render and not show_mode):
        print(f"{prog()}: refusing to run: target environment must be 'dev' or 'beta' "
              f"(got '{target or '<none>'}')", file=sys.stderr)
        return 2
    if target == "beta":
        runtime, problem = beta_runtime(environ)
        if problem:
            print(f"{prog()}: refusing to run: {problem}", file=sys.stderr)
            return 2
    else:
        runtime = environ.get("CRM_RUNTIME_DIR") or DEFAULT_RUNTIME
    if os.path.basename(runtime) != target:
        print(f"{prog()}: refusing to run: runtime directory is not a {target} runtime: {runtime}",
              file=sys.stderr)
        return 2
    env_file = os.path.join(runtime, "env")
    if (environ.get("CRM_ENV_FILE") or env_file) != env_file:  # empty = unset, as in the shell
        print(f"{prog()}: refusing to run: the env file must be {env_file} "
              f"(CRM_ENV_FILE is {environ['CRM_ENV_FILE']})", file=sys.stderr)
        return 1
    try:
        with open(env_file, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        print(f"{prog()}: env file not readable: {env_file}", file=sys.stderr)
        return 1
    if target == "beta":
        if show_mode:  # CRM-009: the mode only, never an address
            if BETA_MODE_NAME in environ:
                print(f"{prog()}: refused: {BETA_MODE_NAME} is set in the process environment",
                      file=sys.stderr)
                return 1
            mode, mode_errors = beta_mode(text)
            for err in mode_errors:
                print(f"{prog()}: refused: {err}", file=sys.stderr)
            if mode_errors:
                return 1
            print(mode)
            return 0
        errors, rendered = check_beta(text, environ)
        for err in errors:
            print(f"{prog()}: refused: {err}", file=sys.stderr)
        if errors:
            return 1
        mode = beta_mode(text)[0]
        if render:
            try:
                write_edge_config(runtime, rendered)
            except OSError as err:
                print(f"{prog()}: cannot write the edge configuration: {type(err).__name__}",
                      file=sys.stderr)
                return 1
            print(f"{prog()}: edge configuration rendered to {os.path.join(runtime, EDGE_CFG_REL)}")
        else:
            problem = edge_config_problem(runtime, rendered)
            if problem:
                print(f"{prog()}: refused: {problem}; run scripts/up.sh beta to re-render it "
                      "and recreate the edge", file=sys.stderr)
                return 1
        names = BETA_NAMES if mode == "production" else tuple(
            n for n in BETA_NAMES if n != "CRM_BETA_HOSTNAME")
        count = len(read_env_values(text, names)[0]["CRM_BETA_UPSTREAM_SOURCES"].split())
        print(f"{prog()}: beta access settings OK ({mode} mode): CRM_BETA_BIND_IP, CRM_BETA_PORT, "
              f"{count} upstream source(s), CRM_BETA_HOSTNAME, CRM_BETA_APP_PORT, CRM_SITE_URL, "
              f"beta compose bind policy, edge policy, crm-proxy {mode} scheme policy")
        return 0
    errors = check(text, environ)
    for err in errors:
        print(f"{prog()}: refused: {err}", file=sys.stderr)
    if errors:
        return 1
    count = len(read_env_values(text)[0]["CRM_ALLOWED_SOURCES"].split())
    print(f"{prog()}: access settings OK: CRM_BIND_IP, {count} network(s) in "
          "CRM_ALLOWED_SOURCES, CRM_SITE_URL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
