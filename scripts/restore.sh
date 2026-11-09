#!/usr/bin/env bash
# Restore the crm-dev stack from a backup made by backup.sh.
# The current data directory is moved aside (data.replaced-<stamp>), not deleted.
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

start=$(date +%s)
stamp=$(utc_stamp)

compose stop crm-daemon crm-app

if [ -e "$CRM_RUNTIME_DIR/data" ]; then
    mv "$CRM_RUNTIME_DIR/data" "$CRM_RUNTIME_DIR/data.replaced-$stamp"
    echo "previous data moved to $CRM_RUNTIME_DIR/data.replaced-$stamp"
fi
tar -C "$CRM_RUNTIME_DIR" -xzf "$backup/data.tar.gz"

compose up -d --wait crm-db
gunzip -c "$backup/db.sql.gz" | compose exec -T crm-db sh -c \
    'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" exec mariadb -uroot "$MARIADB_DATABASE"'

compose up -d --wait

end=$(date +%s)
echo "restore completed from $backup in $((end - start))s"
