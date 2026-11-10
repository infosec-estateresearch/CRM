#!/usr/bin/env bash
# Back up the crm-dev or crm-beta stack: a MariaDB dump plus the runtime directories that
# crm-app and crm-daemon mount (data/, custom/, client/custom/), into
# $CRM_RUNTIME_DIR/backups/<project>-<UTC stamp>/ (umask 077: directories 0700, files 0600).
# Usage: scripts/backup.sh dev|beta
set -euo pipefail
# shellcheck source=lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

require_target "${1:-}"
require_env_file
require_runtime_paths
for dir in "${CRM_PERSISTENT_DIRS[@]}"; do
    [ -d "$CRM_RUNTIME_DIR/$dir" ] || die "$dir directory missing: $CRM_RUNTIME_DIR/$dir"
done

umask 077
name="$CRM_PROJECT-$(utc_stamp)"
dest="$CRM_BACKUP_DIR/$name"
partial="$dest.partial"
[ ! -e "$dest" ] && [ ! -e "$partial" ] || die "backup already exists: $dest"
mkdir -p "$partial"
trap 'rm -rf -- "$partial"' EXIT

# The dump runs inside crm-db with the container's own credentials, so no
# secret is passed on the host command line.
compose exec -T crm-db sh -c \
    'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" exec mariadb-dump -uroot --single-transaction --routines --triggers --events "$MARIADB_DATABASE"' \
    | gzip -c > "$partial/db.sql.gz"
archives=(db.sql.gz)
for dir in "${CRM_PERSISTENT_DIRS[@]}"; do
    archive=$(archive_for "$dir")
    # Members are stored under their runtime-relative path (data/, custom/,
    # client/custom/), so restore extracts each back into its own place.
    tar -C "$CRM_RUNTIME_DIR" -czf "$partial/$archive" "$dir"
    archives+=("$archive")
done
(cd "$partial" && sha256sum "${archives[@]}" > SHA256SUMS)

mv "$partial" "$dest"
trap - EXIT
echo "backup written: $dest"
