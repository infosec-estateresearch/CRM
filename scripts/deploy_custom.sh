#!/usr/bin/env bash
# Deploy the repository's customisation (custom/Espo/Custom/) into the crm-dev
# runtime custom directory, which crm-app and crm-daemon mount read-write at
# /var/www/html/custom. Git is the source of truth: the runtime Espo/Custom
# tree is replaced as a whole, so files removed from Git disappear from the
# runtime too, and Admin-UI edits to custom metadata are overwritten.
#
# The containers' www-data user owns the runtime custom/ tree (the entrypoint
# chowns it on every start), so crm-app and crm-daemon are stopped before the
# authoritative path checks and the swap: nothing in the containers can then
# plant a symlink between check and use. If crm-app was running, both are
# started again and EspoCRM's clear-cache and rebuild run inside crm-app.
# Usage: scripts/deploy_custom.sh dev
set -euo pipefail
# shellcheck source=lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

require_dev "${1:-}"
require_env_file
require_runtime_paths

src="$CRM_REPO_DIR/custom/Espo/Custom"
runtime_custom="$CRM_RUNTIME_DIR/custom"
[ -d "$src" ] || die "repository customisation missing: $src"
[ -d "$runtime_custom" ] || die "runtime custom directory missing: $runtime_custom (see docs/BUILD.md 7.1)"

# Files must be readable by www-data in the container whatever the caller's umask.
umask 022
stamp=$(utc_stamp)
parent="$runtime_custom/Espo"
live="$parent/Custom"
staging="$parent/.Custom.deploy-$stamp"
old="$parent/.Custom.old-$stamp"

# A real directory (not a symlink) whose canonical path is exactly its lexical path.
real_dir() {
    [ ! -L "$1" ] && [ -d "$1" ] || die "refusing to deploy: not a real directory (symlink or missing): $1"
    [ "$(realpath -e -- "$1")" = "$1" ] || die "refusing to deploy: path is redirected: $1"
}
absent() {
    [ ! -e "$1" ] && [ ! -L "$1" ] || die "refusing to deploy: already exists: $1"
}
# Every path the deploy touches must stay inside the canonical runtime.
check_paths() {
    local mode
    real_dir "$CRM_RUNTIME_DIR"
    [ "$(stat -c %u -- "$CRM_RUNTIME_DIR")" = "$(id -u)" ] \
        || die "refusing to deploy: runtime directory is not owned by uid $(id -u): $CRM_RUNTIME_DIR"
    mode=$(stat -c %a -- "$CRM_RUNTIME_DIR")
    [ $((0$mode & 022)) -eq 0 ] \
        || die "refusing to deploy: runtime directory is group- or world-writable (mode $mode): $CRM_RUNTIME_DIR"
    real_dir "$runtime_custom"
    if [ -e "$parent" ] || [ -L "$parent" ]; then real_dir "$parent"; fi
    if [ -e "$live" ] || [ -L "$live" ]; then real_dir "$live"; fi
    absent "$staging"
    absent "$old"
}
# Remove a tree this run created or swapped out: never through a symlink, never
# across a filesystem boundary.
remove_tree() {
    if [ -L "$1" ]; then
        echo "$(basename "$0"): not removing a symlink: $1" >&2
        return 1
    fi
    [ -e "$1" ] || return 0
    rm -rf --one-file-system -- "$1"
}

# First pass before touching the stack, so a bad layout leaves it running.
check_paths

was_running=
[ -z "$(compose ps --status running -q crm-app)" ] || was_running=1
compose stop crm-daemon crm-app
trap 'echo "$(basename "$0"): deploy failed; crm-app and crm-daemon are left stopped" >&2' EXIT

# Authoritative pass: nothing in the containers can change the tree from here on.
check_paths
[ -e "$parent" ] || mkdir -- "$parent"
real_dir "$parent"

trap 'remove_tree "$staging"; echo "$(basename "$0"): deploy failed; crm-app and crm-daemon are left stopped" >&2' EXIT
# Stage a fresh copy beside the live tree (same filesystem), then swap it in by
# rename. The runtime custom directory itself is never replaced, because it is
# the bind-mount source and a running container keeps the original inode.
cp -R -- "$src" "$staging"
real_dir "$staging"
if [ -e "$live" ]; then
    mv -T -- "$live" "$old"
fi
mv -T -- "$staging" "$live"
trap - EXIT
remove_tree "$old"
echo "customisation deployed: $src -> $live"

if [ -n "$was_running" ]; then
    compose up -d --wait crm-app crm-daemon
    compose exec -T -u www-data -w /var/www/html crm-app php bin/command clear-cache
    compose exec -T -u www-data -w /var/www/html crm-app php bin/command rebuild
    echo "crm-app and crm-daemon restarted; clear-cache and rebuild completed in crm-app"
else
    echo "crm-app was not running: left stopped, clear-cache/rebuild skipped." \
        "A first installation rebuilds by itself; otherwise re-run this script once the stack is up."
fi
