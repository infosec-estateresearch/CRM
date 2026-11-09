# shellcheck shell=bash
# Shared helpers for backup.sh, restore.sh and export.sh. Source, do not run.

CRM_REPO_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
CRM_PROJECT=crm-dev

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

compose() {
    docker compose -p "$CRM_PROJECT" -f "$CRM_REPO_DIR/deploy/compose.json" \
        --env-file "$CRM_ENV_FILE" "$@"
}

utc_stamp() {
    date -u +%Y%m%dT%H%M%SZ
}
