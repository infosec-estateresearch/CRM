#!/usr/bin/env bash
# Restore the crm-dev or crm-beta stack from a backup made by backup.sh.
# Each current runtime directory (data/, custom/, client/custom/) is moved
# aside to <dir>.replaced-<stamp>, not deleted, and replaced from the backup.
# Because it starts the stack, the LAN access check (scripts/check_access.py)
# runs first and a refusal stops the restore before the stack is touched.
#
# Restore test (CRM-007, beta only): `restore.sh beta --restoretest <backup>`
# restores the backup into the throwaway project crm-beta-restoretest instead
# (no published port, its own volume and network, runtime
# /srv/CRM/runtime/beta-restoretest), prints record-count fingerprints and
# tears it down. crm-beta itself is not stopped or touched (lib/restoretest.sh).
#
# Usage: scripts/restore.sh dev|beta <backup name or path>
#        scripts/restore.sh beta --restoretest <backup name or path>
set -euo pipefail
# shellcheck source=lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

require_target "${1:-}"
restoretest=
if [ "${2:-}" = --restoretest ]; then
    [ "$CRM_TARGET" = beta ] || {
        echo "$(basename "$0"): refusing to run: --restoretest is for beta only" >&2
        exit 2
    }
    restoretest=1
    backup=${3:-}
    [ -n "$backup" ] && [ $# -eq 3 ] \
        || die "usage: $(basename "$0") beta --restoretest <backup name or path>"
    # shellcheck source=lib/restoretest.sh
    . "$CRM_REPO_DIR/scripts/lib/restoretest.sh"
    rt_guard
else
    require_env_file
    require_runtime_paths
    # This script starts services again, so the LAN access settings must pass first.
    require_access
    backup=${2:-}
    [ -n "$backup" ] || die "usage: $(basename "$0") $CRM_TARGET <backup name or path>"
fi
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

if [ -n "$restoretest" ]; then
    rt_run "$backup"
    exit 0
fi

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
