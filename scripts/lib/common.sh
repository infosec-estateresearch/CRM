# shellcheck shell=bash
# Shared helpers for backup.sh, restore.sh, export.sh, deploy_custom.sh, up.sh and
# deploy_release.sh. Source, do not run. Targets: dev and beta (require_target).

CRM_REPO_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
CRM_PROJECT=crm-dev
CRM_TARGET=dev
CRM_COMPOSE_FILE=$CRM_REPO_DIR/deploy/compose.json

# The runtime directories crm-app and crm-daemon bind-mount, relative to
# $CRM_RUNTIME_DIR, and the backup archive that holds each one.
CRM_PERSISTENT_DIRS=(data custom client/custom)
archive_for() {
    case "$1" in
        data) echo data.tar.gz ;;
        custom) echo custom.tar.gz ;;
        client/custom) echo client-custom.tar.gz ;;
        *) die "unknown persistent directory: $1" ;;
    esac
}

die() {
    echo "$(basename "$0"): $*" >&2
    exit 1
}

# The target guard: the first argument names the target environment and must
# be exactly "dev" or "beta". It runs before anything else touches the host.
# Each target has a fixed Compose project and Compose file (constants, never
# derived from input); the runtime directory must be named after the target.
# beta additionally requires a runtime directory owned by root with mode 0700
# (require_private_runtime).
require_target() {
    case "${1:-}" in
        dev)
            CRM_TARGET=dev
            CRM_PROJECT=crm-dev
            CRM_COMPOSE_FILE=$CRM_REPO_DIR/deploy/compose.json
            ;;
        beta)
            CRM_TARGET=beta
            CRM_PROJECT=crm-beta
            CRM_COMPOSE_FILE=$CRM_REPO_DIR/deploy/beta/compose.json
            load_env_names "$CRM_REPO_DIR/deploy/beta/env.example"
            ;;
        *)
            echo "$(basename "$0"): refusing to run: target environment must be 'dev' or 'beta' (got '${1:-<none>}')" >&2
            exit 2
            ;;
    esac
    CRM_RUNTIME_DIR=${CRM_RUNTIME_DIR:-/srv/CRM/runtime/$CRM_TARGET}
    if [ "$(basename "$CRM_RUNTIME_DIR")" != "$CRM_TARGET" ]; then
        echo "$(basename "$0"): refusing to run: runtime directory is not a $CRM_TARGET runtime: $CRM_RUNTIME_DIR" >&2
        exit 2
    fi
    CRM_BACKUP_DIR=${CRM_BACKUP_DIR:-$CRM_RUNTIME_DIR/backups}
    CRM_ENV_FILE=${CRM_ENV_FILE:-$CRM_RUNTIME_DIR/env}
    if [ "$CRM_TARGET" = beta ]; then
        require_private_runtime
    fi
}

# The CRM-001 dev-only guard, kept for callers that serve dev only.
require_dev() {
    if [ "${1:-}" != "dev" ]; then
        echo "$(basename "$0"): refusing to run: target environment must be 'dev' (got '${1:-<none>}')" >&2
        exit 2
    fi
    require_target dev
}

# beta: the runtime directory (and its backups directory, if present) must be
# a real directory owned by root (uid 0) with mode 0700, because it holds
# customer data.
require_private_runtime() {
    local dir owner
    for dir in "$CRM_RUNTIME_DIR" "$CRM_BACKUP_DIR"; do
        [ "$dir" != "$CRM_BACKUP_DIR" ] || [ -e "$dir" ] || [ -L "$dir" ] || continue
        if [ -L "$dir" ] || [ ! -d "$dir" ]; then
            echo "$(basename "$0"): refusing to run: not a real directory: $dir" >&2
            exit 2
        fi
        owner=$(stat -c '%u %a' -- "$dir")
        if [ "$owner" != "0 700" ]; then
            echo "$(basename "$0"): refusing to run: $dir must be owned by root with mode 0700 (is uid/mode $owner)" >&2
            exit 2
        fi
    done
}

# The env file is always $CRM_RUNTIME_DIR/env: the one the access check and
# the path checks read is the one Compose gets.
require_env_file() {
    [ "$CRM_ENV_FILE" = "$CRM_RUNTIME_DIR/env" ] \
        || die "refusing to run: the env file must be $CRM_RUNTIME_DIR/env (CRM_ENV_FILE is $CRM_ENV_FILE)"
    [ -r "$CRM_ENV_FILE" ] || die "env file not readable: $CRM_ENV_FILE"
}

# The bind-mount source variables.
CRM_PATH_VARS=(CRM_DB_DIR CRM_DATA_DIR CRM_CUSTOM_DIR CRM_CLIENT_CUSTOM_DIR)

# Every variable the env file defines, read from the names in deploy/env.example
# (the single list). Compose prefers a value in its process environment over
# the env file, so none of them may come from the environment: the scripts
# refuse to run if one is set (require_runtime_paths), and compose() removes
# all of them before calling docker.
# beta reads its own list, deploy/beta/env.example (require_target).
load_env_names() {
    CRM_ENV_NAMES=()
    if [ -r "$1" ]; then
        mapfile -t CRM_ENV_NAMES < <(sed -n 's/^\([A-Z][A-Z0-9_]*\)=.*$/\1/p' -- "$1")
    fi
}
load_env_names "$CRM_REPO_DIR/deploy/env.example"
require_env_names() {
    [ "${#CRM_ENV_NAMES[@]}" -gt 0 ] \
        || die "refusing to run: no variable names could be read from $CRM_REPO_DIR/deploy/env.example"
}

# Fail closed unless the LAN access settings in the env file pass
# scripts/check_access.py (CRM-D019). Every script that can start or recreate
# a service runs this before anything touches the stack.
require_access() {
    CRM_RUNTIME_DIR=$CRM_RUNTIME_DIR CRM_ENV_FILE=$CRM_ENV_FILE \
        python3 -I "$CRM_REPO_DIR/scripts/check_access.py" "$CRM_TARGET" \
        || die "refusing to run: the LAN access settings in $CRM_ENV_FILE failed scripts/check_access.py"
}

# Fail closed unless $CRM_RUNTIME_DIR is an absolute path with no symlink in it
# and the env file's bind-mount sources are exactly its db/, data/, custom/ and
# client/custom/, so the scripts and Compose work on the same directories (for
# both targets: beta's database is never dev's, and the reverse).
# The env file is read as text, never sourced. Then what Compose itself
# resolves is checked too (require_compose_mounts), which is authoritative.
require_runtime_paths() {
    local canon name rel count line value
    require_env_names
    for name in "${CRM_ENV_NAMES[@]}"; do
        [ -z "${!name+set}" ] \
            || die "refusing to run: $name is set in the environment; Compose would prefer it to the env file. Unset it."
    done
    case "$CRM_RUNTIME_DIR" in
        /*) ;;
        *) die "runtime directory must be an absolute path: $CRM_RUNTIME_DIR" ;;
    esac
    canon=$(realpath -e -- "$CRM_RUNTIME_DIR") || die "runtime directory missing: $CRM_RUNTIME_DIR"
    [ "$canon" = "$CRM_RUNTIME_DIR" ] \
        || die "runtime directory is not canonical (symlink, '.', '..' or trailing '/'): $CRM_RUNTIME_DIR -> $canon"
    for name in CRM_DB_DIR CRM_DATA_DIR CRM_CUSTOM_DIR CRM_CLIENT_CUSTOM_DIR; do
        case "$name" in
            CRM_DB_DIR) rel=db ;;
            CRM_DATA_DIR) rel=data ;;
            CRM_CUSTOM_DIR) rel=custom ;;
            *) rel=client/custom ;;
        esac
        # Every line that could assign $name in any form Compose accepts
        # (NAME=, NAME: , export NAME, leading blanks, ...) counts.
        count=$(grep -Ec "^[[:space:]]*(export[[:space:]]+)?$name([^A-Za-z0-9_]|\$)" -- "$CRM_ENV_FILE") || true
        [ "$count" = 1 ] || die "env file must set $name exactly once (found ${count:-0}): $CRM_ENV_FILE"
        line=$(grep -E "^$name=" -- "$CRM_ENV_FILE") \
            || die "env file must set $name in the plain form $name=<path>: $CRM_ENV_FILE"
        value=${line#*=}
        case "$value" in
            \"*\") value=${value#\"}; value=${value%\"} ;;
            \'*\') value=${value#\'}; value=${value%\'} ;;
        esac
        case "$value" in
            /*) ;;
            *) die "$name in $CRM_ENV_FILE must be an absolute path (got '$value')" ;;
        esac
        canon=$(realpath -m -- "$value")
        [ "$canon" = "$CRM_RUNTIME_DIR/$rel" ] \
            || die "$name in $CRM_ENV_FILE is '$value', which resolves to $canon, not $CRM_RUNTIME_DIR/$rel"
    done
    require_compose_mounts
}

# Authoritative check: the bind sources Compose itself resolves for data/,
# custom/ and client/custom/ on crm-app and crm-daemon, and for /var/lib/mysql
# on crm-db, must be exactly $CRM_RUNTIME_DIR/{data,custom,client/custom,db}
# (only "." and repeated or
# trailing "/" may differ; no "..", no symlink). The resolved config holds the
# secrets, so it goes straight from Compose into the parser, is never printed
# or stored, and the parser reports only mount targets and sources.
CRM_MOUNT_CHECK='
import json, os, sys
runtime = sys.argv[1]
want = {"/var/www/html/data": "data", "/var/www/html/custom": "custom",
        "/var/www/html/client/custom": "client/custom"}
try:
    services = json.load(sys.stdin)["services"]
    assert isinstance(services, dict)
except Exception:
    sys.exit("compose config did not produce a readable document")
bad = []
for svc, wanted in (("crm-app", want), ("crm-daemon", want), ("crm-db", {"/var/lib/mysql": "db"})):
    vols = services.get(svc)
    vols = vols.get("volumes") if isinstance(vols, dict) else None
    vols = vols if isinstance(vols, list) else []
    for target, rel in wanted.items():
        expected = runtime + "/" + rel
        found = [v for v in vols if isinstance(v, dict) and v.get("target") == target]
        if len(found) != 1:
            bad.append(f"{svc} {target}: {len(found)} mounts, expected exactly 1")
            continue
        src = found[0].get("source")
        if found[0].get("type") != "bind" or not isinstance(src, str) or ".." in src.split("/") \
                or os.path.normpath(src) != expected or os.path.realpath(src) != expected:
            bad.append(f"{svc} {target}: Compose resolves the source to {src!r}, not {expected}")
for line in bad:
    print(line, file=sys.stderr)
sys.exit(1 if bad else 0)
'
require_compose_mounts() {
    compose config --format json | python3 -I -c "$CRM_MOUNT_CHECK" "$CRM_RUNTIME_DIR" \
        || die "refusing to run: the bind mounts Compose resolves do not match $CRM_RUNTIME_DIR (or compose config failed)"
}

# docker compose runs without any env-file variable (every name in
# deploy/env.example) in its environment, so only the checked env file can
# supply them (defence in depth).
compose() {
    local name unset=()
    require_env_names
    for name in "${CRM_ENV_NAMES[@]}"; do
        unset+=(-u "$name")
    done
    env "${unset[@]}" \
        docker compose -p "$CRM_PROJECT" -f "$CRM_COMPOSE_FILE" \
        --env-file "$CRM_ENV_FILE" "$@"
}

utc_stamp() {
    date -u +%Y%m%dT%H%M%SZ
}
