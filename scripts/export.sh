#!/usr/bin/env bash
# CSV export of Accounts and Contacts through the EspoCRM API.
# Default output: $CRM_RUNTIME_DIR/backups/export-<UTC stamp>/
# Needs CRM_ADMIN_USERNAME and CRM_ADMIN_PASSWORD in the environment;
# CRM_BASE_URL defaults to http://127.0.0.1:8180.
# Usage: scripts/export.sh dev [output directory]
set -euo pipefail
# shellcheck source=lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

require_dev "${1:-}"
umask 077
out=${2:-$CRM_BACKUP_DIR/export-$(utc_stamp)}
exec python3 "$CRM_REPO_DIR/scripts/export_csv.py" \
    --base-url "${CRM_BASE_URL:-http://127.0.0.1:8180}" --out "$out"
