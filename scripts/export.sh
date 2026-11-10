#!/usr/bin/env bash
# CSV export of Accounts and Contacts through the EspoCRM API.
# Default output: $CRM_RUNTIME_DIR/backups/export-<UTC stamp>/
# Needs CRM_ADMIN_USERNAME and CRM_ADMIN_PASSWORD in the environment;
# CRM_BASE_URL defaults to http://127.0.0.1:8180 for dev; beta has no default
# (its loopback port is a host value): it must be exactly
# http://127.0.0.1:<CRM_BETA_APP_PORT>, the port read from the env file
# $CRM_RUNTIME_DIR/env (set exactly once, plain NAME=value form).
# Usage: scripts/export.sh dev|beta [output directory]
set -euo pipefail
# shellcheck source=lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

require_target "${1:-}"
if [ "$CRM_TARGET" = beta ]; then
    [ -n "${CRM_BASE_URL:-}" ] \
        || die "refusing to run: beta needs CRM_BASE_URL (http://127.0.0.1:<CRM_BETA_APP_PORT>)"
    require_env_file
    count=$(grep -Ec '^[[:space:]]*(export[[:space:]]+)?CRM_BETA_APP_PORT([^A-Za-z0-9_]|$)' -- "$CRM_ENV_FILE") || true
    [ "$count" = 1 ] || die "refusing to run: $CRM_ENV_FILE must set CRM_BETA_APP_PORT exactly once"
    app_port=$(sed -n 's/^CRM_BETA_APP_PORT=\([1-9][0-9]*\)$/\1/p' -- "$CRM_ENV_FILE")
    [ -n "$app_port" ] && [ "$app_port" -ge 1024 ] && [ "$app_port" -le 65535 ] \
        || die "refusing to run: CRM_BETA_APP_PORT in $CRM_ENV_FILE is not a port 1024-65535 in the plain form"
    [ "$CRM_BASE_URL" = "http://127.0.0.1:$app_port" ] \
        || die "refusing to run: beta's CRM_BASE_URL must be exactly http://127.0.0.1:<CRM_BETA_APP_PORT from $CRM_ENV_FILE>"
fi
umask 077
out=${2:-$CRM_BACKUP_DIR/export-$(utc_stamp)}
exec python3 "$CRM_REPO_DIR/scripts/export_csv.py" \
    --base-url "${CRM_BASE_URL:-http://127.0.0.1:8180}" --out "$out"
