#!/usr/bin/env bash
# Deploy the repository's customisation (custom/Espo/Custom/) into the crm-dev
# runtime custom directory, which crm-app and crm-daemon mount read-write at
# /var/www/html/custom. Git is the source of truth: the runtime Espo/Custom
# tree is replaced as a whole, so files removed from Git disappear from the
# runtime too, and Admin-UI edits to custom metadata are overwritten.
# If crm-app is running, EspoCRM's clear-cache and rebuild then run inside it.
# Usage: scripts/deploy_custom.sh dev
set -euo pipefail
# shellcheck source=lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

require_dev "${1:-}"
require_env_file

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
mkdir -p "$parent"
[ ! -e "$staging" ] && [ ! -e "$old" ] || die "a deploy with stamp $stamp already exists"
trap 'rm -rf -- "$staging"' EXIT

# Stage a fresh copy beside the live tree (same filesystem), then swap it in by
# rename. The runtime custom directory itself is never replaced, because it is
# the bind-mount source and a running container keeps the original inode.
cp -R -- "$src" "$staging"
if [ -e "$live" ]; then
    mv -- "$live" "$old"
fi
mv -- "$staging" "$live"
trap - EXIT
rm -rf -- "$old"
echo "customisation deployed: $src -> $live"

if [ -n "$(compose ps --status running -q crm-app)" ]; then
    compose exec -T -u www-data -w /var/www/html crm-app php bin/command clear-cache
    compose exec -T -u www-data -w /var/www/html crm-app php bin/command rebuild
    echo "clear-cache and rebuild completed in crm-app"
else
    echo "crm-app is not running: clear-cache/rebuild skipped." \
        "A first installation rebuilds by itself; otherwise re-run this script once the stack is up."
fi
