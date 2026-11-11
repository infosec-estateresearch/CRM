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
# CRM-007R: the backup must be this target's own: directly under
# $CRM_RUNTIME_DIR/backups, named crm-<target>-<UTC stamp>, with a checksummed
# TARGET marker naming the target. Anything else is refused before any docker
# call. Dev only: a legacy backup with no marker (made before CRM-007R) is
# accepted with the explicit flag --legacy-unmarked, and only if it is stamped
# before the cut-over 20261111T000000Z (CRM_LEGACY_CUTOVER in lib/common.sh).
#
# Usage: scripts/restore.sh dev|beta <backup name or path>
#        scripts/restore.sh dev --legacy-unmarked <backup name or path>
#        scripts/restore.sh beta --restoretest <backup name or path>
set -euo pipefail
# shellcheck source=lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

require_target "${1:-}"
restoretest= legacy=
case "${2:-}" in
    --restoretest)
        [ "$CRM_TARGET" = beta ] || {
            echo "$(basename "$0"): refusing to run: --restoretest is for beta only" >&2
            exit 2
        }
        restoretest=1 ;;
    --legacy-unmarked)
        [ "$CRM_TARGET" = dev ] || {
            echo "$(basename "$0"): refusing to run: --legacy-unmarked is for dev only; beta never accepts a backup without its TARGET marker" >&2
            exit 2
        }
        legacy=1 ;;
esac
if [ -n "$restoretest$legacy" ]; then
    backup=${3:-}
    [ -n "$backup" ] && [ $# -eq 3 ] \
        || die "usage: $(basename "$0") $CRM_TARGET ${2} <backup name or path>"
else
    backup=${2:-}
    [ -n "$backup" ] || die "usage: $(basename "$0") $CRM_TARGET <backup name or path>"
fi
# CRM-007R: only this target's own, marked backup, checked before any docker
# call (lib/common.sh resolve_backup).
resolve_backup "$backup" "$legacy"
backup=$CRM_BACKUP_PATH
if [ -n "$restoretest" ]; then
    # shellcheck source=lib/restoretest.sh
    . "$CRM_REPO_DIR/scripts/lib/restoretest.sh"
    rt_guard
else
    require_env_file
    require_runtime_paths
    # This script starts services again, so the LAN access settings must pass first.
    require_access
fi

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
