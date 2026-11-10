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

# Fail closed unless $CRM_RUNTIME_DIR is an absolute path with no symlink in it
# and the env file's bind-mount sources are exactly its data/, custom/ and
# client/custom/, so the scripts and Compose work on the same directories.
# The env file is read as text, never sourced.
require_runtime_paths() {
    local canon name rel count line value
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
        count=$(grep -Ec "^[[:space:]]*(export[[:space:]]+)?$name[[:space:]]*=" -- "$CRM_ENV_FILE") || true
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
}

compose() {
    docker compose -p "$CRM_PROJECT" -f "$CRM_REPO_DIR/deploy/compose.json" \
        --env-file "$CRM_ENV_FILE" "$@"
}

utc_stamp() {
    date -u +%Y%m%dT%H%M%SZ
}
