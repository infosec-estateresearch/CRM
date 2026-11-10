#!/usr/bin/env python3
"""Fail-closed check of the crm-dev LAN access settings (CRM-D019), standard library only.

Run it before every `docker compose ... up`:

    python3 scripts/check_access.py dev

It reads the runtime env file as text (it is never sourced or executed) and
refuses (exit 1) unless:
- CRM_BIND_IP is exactly one IPv4 unicast address, not 0.0.0.0 and not loopback;
- CRM_ALLOWED_SOURCES is one or more space-separated IPv4 CIDRs, each inside
  RFC 1918, each /16 or longer, none overlapping the crm-net subnet;
- CRM_SITE_URL is http://<CRM_BIND_IP>:8180 (optionally with a trailing "/").
Each name must be assigned exactly once, in the plain NAME=value form, and none
may be set in the process environment, because Compose would prefer it to the
env file.

The dev guard is the same as the shell scripts': the first argument must be
exactly "dev" and the runtime directory must be named "dev" (exit 2 otherwise).

Nothing from the env file is printed: problems are reported by variable name and
position only, never by value.
"""

import ipaddress
import json
import os
import re
import sys
import urllib.parse

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COMPOSE_PATH = os.path.join(REPO, "deploy", "compose.json")
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
    return []


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
    if "CRM_BIND_IP" in values:
        errors += validate_bind_ip(values["CRM_BIND_IP"])
    if "CRM_ALLOWED_SOURCES" in values:
        errors += validate_sources(values["CRM_ALLOWED_SOURCES"], avoid)
    if "CRM_SITE_URL" in values:
        bind = values.get("CRM_BIND_IP")
        errors += validate_site_url(values["CRM_SITE_URL"],
                                    bind if bind and not validate_bind_ip(bind) else None)
    return errors


def main(argv=None, environ=None):
    argv = sys.argv[1:] if argv is None else argv
    environ = os.environ if environ is None else environ
    target = argv[0] if argv else ""
    if target != "dev" or len(argv) != 1:
        print(f"{prog()}: refusing to run: target environment must be 'dev' "
              f"(got '{target or '<none>'}')", file=sys.stderr)
        return 2
    runtime = environ.get("CRM_RUNTIME_DIR") or DEFAULT_RUNTIME
    if os.path.basename(runtime) != "dev":
        print(f"{prog()}: refusing to run: runtime directory is not a dev runtime: {runtime}",
              file=sys.stderr)
        return 2
    env_file = environ.get("CRM_ENV_FILE") or os.path.join(runtime, "env")
    try:
        with open(env_file, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        print(f"{prog()}: env file not readable: {env_file}", file=sys.stderr)
        return 1
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
