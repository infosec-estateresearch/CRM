#!/usr/bin/env bash
# CSV export of Accounts and Contacts through the EspoCRM API.
# Usage: scripts/export.sh dev|beta [export-<name>]
#
# CRM-007R: an export is bound to its target in both directions.
# - Output: always a new directory directly under the target's constant
#   backup directory $CRM_RUNTIME_DIR/backups, named export-<UTC stamp> or the
#   optional bare name, which must match export-[A-Za-z0-9._-]+ (never a path,
#   no '..'). An existing directory or symlink of that name is refused.
# - URL: exactly the target's own base URL, as `check_access.py <target>
#   --base-url` reads it from the target's env file $CRM_RUNTIME_DIR/env:
#   dev http://<CRM_BIND_IP>:8180 (used when CRM_BASE_URL is unset), beta
#   http://127.0.0.1:<CRM_BETA_APP_PORT> (beta has no default: CRM_BASE_URL
#   must be set to it). Any other CRM_BASE_URL is refused.
# Everything is refused before any request. export_csv.py checks both again.
# Needs CRM_ADMIN_USERNAME and CRM_ADMIN_PASSWORD in the environment.
set -euo pipefail
# shellcheck source=lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

require_target "${1:-}"
[ $# -le 2 ] || die "usage: export.sh dev|beta [export-<name>]"
if [ "$CRM_TARGET" = beta ] && [ -z "${CRM_BASE_URL:-}" ]; then
    die "refusing to run: beta needs CRM_BASE_URL (http://127.0.0.1:<CRM_BETA_APP_PORT>)"
fi

name=${2:-export-$(utc_stamp)}
[[ "$name" =~ ^export-[A-Za-z0-9._-]+$ ]] && [[ "$name" != *..* ]] \
    || die "refusing to run: the export name must be a bare name export-[A-Za-z0-9._-]+ (not a path, no '..')"

require_env_file
url=$(CRM_RUNTIME_DIR=$CRM_RUNTIME_DIR CRM_ENV_FILE=$CRM_ENV_FILE \
      python3 -I "$CRM_REPO_DIR/scripts/check_access.py" "$CRM_TARGET" --base-url) \
    || die "refusing to run: cannot determine the $CRM_TARGET base URL from $CRM_ENV_FILE (CRM_BASE_URL)"
[ -n "$url" ] || die "refusing to run: cannot determine the $CRM_TARGET base URL from $CRM_ENV_FILE (CRM_BASE_URL)"
if [ "$CRM_TARGET" = beta ]; then
    [ "$CRM_BASE_URL" = "$url" ] \
        || die "refusing to run: beta's CRM_BASE_URL must be exactly http://127.0.0.1:<CRM_BETA_APP_PORT from $CRM_ENV_FILE>"
else
    [ -z "${CRM_BASE_URL:-}" ] || [ "$CRM_BASE_URL" = "$url" ] \
        || die "refusing to run: dev's CRM_BASE_URL must be exactly http://<CRM_BIND_IP from $CRM_ENV_FILE>:8180 (or unset)"
fi

umask 077
if [ ! -e "$CRM_BACKUP_DIR" ] && [ ! -L "$CRM_BACKUP_DIR" ]; then
    mkdir -m 0700 -- "$CRM_BACKUP_DIR" || die "cannot create the $CRM_TARGET backup directory $CRM_BACKUP_DIR"
fi
[ -d "$CRM_BACKUP_DIR" ] && [ ! -L "$CRM_BACKUP_DIR" ] \
    && [ "$(realpath -e -- "$CRM_BACKUP_DIR")" = "$CRM_BACKUP_DIR" ] \
    || die "refusing to run: the $CRM_TARGET backup directory is not a real canonical directory: $CRM_BACKUP_DIR"
out=$CRM_BACKUP_DIR/$name
[ ! -e "$out" ] && [ ! -L "$out" ] || die "refusing to run: the export directory already exists: $out"

CRM_RUNTIME_DIR=$CRM_RUNTIME_DIR CRM_ENV_FILE=$CRM_ENV_FILE \
    exec python3 "$CRM_REPO_DIR/scripts/export_csv.py" "$CRM_TARGET" --base-url "$url" --out "$out"
