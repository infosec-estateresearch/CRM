"""Policy checkers for ``deploy/migrate/compose.json`` and ``scripts/migrate.sh``.

Each returns a list of violated rule ids; an empty list means the policy holds. The tests
run them against the real files and against deliberately broken copies.
"""

import re

EXPECTED_IMAGE_TAG = "python:3.13.9-slim-trixie"
RUN_USER = "64021:64021"
LIVE = "crm-migrate"
SELFTEST = "crm-migrate-selftest"
NETWORK = "crm-migrate-net"
ENV_FILE = "/srv/CRM/runtime/migrate/env"


def register_digest(register_text, name="python"):
    """Digest of a candidate entry in the YAML register (parsed without a YAML library)."""
    block = None
    for chunk in re.split(r"\n  - name: ", "\n" + register_text):
        if chunk.split("\n", 1)[0].strip() == name:
            block = chunk
    if block is None:
        return None
    m = re.search(r'^\s+digest: "(sha256:[0-9a-f]{64})"', block, re.M)
    return m.group(1) if m else None


def compose_violations(doc, digest):
    v = []
    if doc.get("name") != "crm-migrate":
        v.append("project_name")
    services = doc.get("services") or {}
    if set(services) != {LIVE, SELFTEST}:
        v.append("service_set")
    if "volumes" in doc:
        v.append("named_volumes")
    for net_name, net in (doc.get("networks") or {}).items():
        if not net_name.startswith("crm-"):
            v.append("network_prefix")
        if isinstance(net, dict) and (net.get("external") or net.get("name")):
            v.append("external_network")
    if set((doc.get("networks") or {})) != {NETWORK}:
        v.append("network_set")
    for name, svc in services.items():
        if not name.startswith("crm-"):
            v.append("service_prefix")
        image = svc.get("image", "")
        if image != f"{EXPECTED_IMAGE_TAG}@{digest}" or digest is None:
            v.append("image_digest")
        if "build" in svc:
            v.append("build")
        if "ports" in svc or "expose" in svc:
            v.append("ports")
        if "container_name" in svc:
            v.append("container_name")
        if svc.get("read_only") is not True:
            v.append("read_only")
        if svc.get("cap_drop") != ["ALL"] or svc.get("cap_add"):
            v.append("cap_drop")
        if "no-new-privileges:true" not in (svc.get("security_opt") or []):
            v.append("no_new_privileges")
        if svc.get("user") != RUN_USER:
            v.append("user")
        if svc.get("privileged"):
            v.append("privileged")
        for key in ("pid", "ipc", "devices", "extra_hosts", "external_links", "volumes_from", "links"):
            if key in svc:
                v.append(f"forbidden_{key}")
        tmpfs = svc.get("tmpfs") or []
        if not any(t.startswith("/tmp:") and "noexec" in t.split(":", 1)[1].split(",") for t in tmpfs):
            v.append("tmpfs_noexec")
        if svc.get("entrypoint") != ["python", "-I", "-B", "/opt/crm-migrate/bin/crm-migrate.py"]:
            v.append("entrypoint")
        v += _volume_violations(svc.get("volumes") or [])
        if name == SELFTEST:
            if svc.get("network_mode") != "none" or "networks" in svc:
                v.append("selftest_network_none")
            if "env_file" in svc or "environment" in svc:
                v.append("selftest_no_env")
        if name == LIVE:
            if "network_mode" in svc:
                v.append("live_network_mode")
            if svc.get("networks") != [NETWORK]:
                v.append("live_network")
            if svc.get("env_file") != [ENV_FILE]:
                v.append("live_env_file")
            if "environment" in svc:
                v.append("live_environment")
    return sorted(set(v))


def _volume_violations(volumes):
    v = []
    writable = []
    code_mount = False
    for vol in volumes:
        if not isinstance(vol, dict) or vol.get("type") != "bind":
            v.append("non_bind_volume")
            continue
        if (vol.get("bind") or {}).get("create_host_path") is not False:
            v.append("create_host_path")
        if vol.get("read_only") is True:
            if vol.get("target") == "/opt/crm-migrate" and vol.get("source") == "../../migrate":
                code_mount = True
            continue
        writable.append(vol)
    if not code_mount:
        v.append("code_mount_read_only")
    if len(writable) != 1:
        v.append("writable_binds")
    for vol in writable:
        if vol.get("target") != "/out" or not str(vol.get("source", "")).startswith("${CRM_MIGRATE_RUN_DIR:?"):
            v.append("writable_bind_is_out")
    return v


# ---------------------------------------------------------------- migrate.sh

SCRIPT_RULES = {
    "strict_mode": r"^set -euo pipefail$",
    "umask": r"^umask 077$",
    "root_only": r'\[\[ \$\{EUID\} -eq 0 \]\] \|\| die',
    "target_guard": r"^require target \"\$target\"$",
    "runtime_guard": r"^require runtime-dirs$",
    "runtime_path": r"^readonly RUNTIME=/srv/CRM/runtime/migrate$",
    "exported_secret_guard": r"^require env-clean \"\$ENV_EXAMPLE\"$",
    "exported_secret_bash": r'\[\[ -z "\$\{!name\+set\}" \]\] \|\| die',
    "uid_guard": r'^require uid-free "\$\(getent passwd "\$RUN_UID" \|\| true\)" "\$\(getent group "\$RUN_GID" \|\| true\)"$',
    "env_unset": r'unset_args\+=\(-u "\$name"\)',
    "env_wrapper": r'^\s+env "\$\{unset_args\[@\]\}" CRM_MIGRATE_RUN_DIR="\$RUN_DIR" \\$',
    "no_project_env_file": r"--env-file /dev/null",
    "run_dir_absent": r"^\s+require run-dir-absent \"\$RUN_DIR\"$",
    "run_dir_mkdir": r'^\s+mkdir -m 0700 -- "\$RUN_DIR" \|\| die',
    "run_dir_owner": r'^\s+chown "\$RUN_UID:\$RUN_GID" -- "\$RUN_DIR"$',
    "seal_owner": r"chown -R --no-dereference root:root",
    "seal_dirs": r"find \"\$dir\" -type d -exec chmod 0700 \{\} \+",
    "seal_files": r"find \"\$dir\" -type f -exec chmod 0400 \{\} \+",
    "seal_check": r"check sealed \"\$dir\"",
    "seal_fail_exit": r"exit 20",
    "manifest_reverify": r"check verify-manifest \"\$2\"",
    "credentials_silent": r'read -rs -p "Consumer secret: " client_secret',
    "credentials_tmp_same_dir": r'mktemp -p "\$RUNTIME"',
    "credentials_atomic": r'mv -T -f -- "\$CRED_TMP" "\$ENV_FILE"',
    "credentials_mode": r'chmod 0600 -- "\$CRED_TMP"',
}
XTRACE_RE = r"^\s*set -[a-z]*x"


def script_violations(text):
    v = [rule for rule, rx in SCRIPT_RULES.items() if not re.search(rx, text, re.M)]
    if re.search(XTRACE_RE, text, re.M):
        v.append("xtrace")
    for line in text.splitlines():
        if re.search(r"(echo|printf)\b.*\$\{?(origin|client_id|client_secret|api_version)\b", line) and \
                not line.strip().startswith("printf 'CRM_SF_"):
            v.append("echo_values")
    docker_lines = [ln for ln in text.splitlines() if re.search(r"^\s*docker compose\b", ln)]
    if len(docker_lines) != 1 or not docker_lines[0].strip().startswith("docker compose --project-name"):
        v.append("docker_outside_wrapper")
    return sorted(set(v))
