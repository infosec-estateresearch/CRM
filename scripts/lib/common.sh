# shellcheck shell=bash
# Shared helpers for backup.sh, restore.sh, export.sh and deploy_custom.sh. Source, do not run.

CRM_REPO_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
CRM_PROJECT=crm-dev

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

# The dev guard: the first argument names the target environment and must be
# exactly "dev". It runs before anything else touches the host.
require_dev() {
    if [ "${1:-}" != "dev" ]; then
        echo "$(basename "$0"): refusing to run: target environment must be 'dev' (got '${1:-<none>}')" >&2
        exit 2
    fi
    CRM_RUNTIME_DIR=${CRM_RUNTIME_DIR:-/srv/CRM/runtime/dev}
    if [ "$(basename "$CRM_RUNTIME_DIR")" != "dev" ]; then
        echo "$(basename "$0"): refusing to run: runtime directory is not a dev runtime: $CRM_RUNTIME_DIR" >&2
        exit 2
    fi
    CRM_BACKUP_DIR=${CRM_BACKUP_DIR:-$CRM_RUNTIME_DIR/backups}
    CRM_ENV_FILE=${CRM_ENV_FILE:-$CRM_RUNTIME_DIR/env}
}

require_env_file() {
    [ -r "$CRM_ENV_FILE" ] || die "env file not readable: $CRM_ENV_FILE"
}

# The bind-mount source variables. Compose prefers a value in its process
# environment over the env file, so none of them may come from the environment.
CRM_PATH_VARS=(CRM_DB_DIR CRM_DATA_DIR CRM_CUSTOM_DIR CRM_CLIENT_CUSTOM_DIR)

# Fail closed unless $CRM_RUNTIME_DIR is an absolute path with no symlink in it
# and the env file's bind-mount sources are exactly its data/, custom/ and
# client/custom/, so the scripts and Compose work on the same directories.
# The env file is read as text, never sourced. Then what Compose itself
# resolves is checked too (require_compose_mounts), which is authoritative.
require_runtime_paths() {
    local canon name rel count line value
    for name in "${CRM_PATH_VARS[@]}"; do
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
    for name in CRM_DATA_DIR CRM_CUSTOM_DIR CRM_CLIENT_CUSTOM_DIR; do
        case "$name" in
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
# custom/ and client/custom/ on crm-app and crm-daemon must be exactly
# $CRM_RUNTIME_DIR/{data,custom,client/custom} (only "." and repeated or
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
for svc in ("crm-app", "crm-daemon"):
    vols = services.get(svc)
    vols = vols.get("volumes") if isinstance(vols, dict) else None
    vols = vols if isinstance(vols, list) else []
    for target, rel in want.items():
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

# docker compose runs without the bind-mount variables in its environment, so
# only the checked env file can supply them (defence in depth).
compose() {
    env -u CRM_DB_DIR -u CRM_DATA_DIR -u CRM_CUSTOM_DIR -u CRM_CLIENT_CUSTOM_DIR \
        docker compose -p "$CRM_PROJECT" -f "$CRM_REPO_DIR/deploy/compose.json" \
        --env-file "$CRM_ENV_FILE" "$@"
}

utc_stamp() {
    date -u +%Y%m%dT%H%M%SZ
}
