#!/usr/bin/env bash
# Restore the crm-dev stack from a backup made by backup.sh.
# Each current runtime directory (data/, custom/, client/custom/) is moved
# aside to <dir>.replaced-<stamp>, not deleted, and replaced from the backup.
# Usage: scripts/restore.sh dev <backup name or path>
set -euo pipefail
# shellcheck source=lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

require_dev "${1:-}"
require_env_file
backup=${2:-}
[ -n "$backup" ] || die "usage: $(basename "$0") dev <backup name or path>"
case "$backup" in
    */*) ;;
    *) backup="$CRM_BACKUP_DIR/$backup" ;;
esac
[ -f "$backup/SHA256SUMS" ] || die "not a backup directory: $backup"
(cd "$backup" && sha256sum --quiet -c SHA256SUMS) || die "checksum mismatch in $backup"
for archive in db.sql.gz $(for d in "${CRM_PERSISTENT_DIRS[@]}"; do archive_for "$d"; done); do
    [ -f "$backup/$archive" ] && grep -q "  $archive\$" "$backup/SHA256SUMS" \
        || die "backup is incomplete (no checksummed $archive): $backup"
done

start=$(date +%s)
stamp=$(utc_stamp)

compose stop crm-daemon crm-app

for dir in "${CRM_PERSISTENT_DIRS[@]}"; do
    if [ -e "$CRM_RUNTIME_DIR/$dir" ]; then
        mv "$CRM_RUNTIME_DIR/$dir" "$CRM_RUNTIME_DIR/$dir.replaced-$stamp"
        echo "previous $dir moved to $CRM_RUNTIME_DIR/$dir.replaced-$stamp"
    fi
done
for dir in "${CRM_PERSISTENT_DIRS[@]}"; do
    mkdir -p "$(dirname "$CRM_RUNTIME_DIR/$dir")"
    tar -C "$CRM_RUNTIME_DIR" -xzf "$backup/$(archive_for "$dir")"
    [ -d "$CRM_RUNTIME_DIR/$dir" ] || die "$(archive_for "$dir") did not restore $dir"
done

compose up -d --wait crm-db
gunzip -c "$backup/db.sql.gz" | compose exec -T crm-db sh -c \
    'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" exec mariadb -uroot "$MARIADB_DATABASE"'

compose up -d --wait

end=$(date +%s)
echo "restore completed from $backup in $((end - start))s"
