#!/usr/bin/env bash
# Deploy the repository's customisation (custom/Espo/Custom/) into the crm-dev
# runtime custom directory, which crm-app and crm-daemon mount read-write at
# /var/www/html/custom, and the CRM-owned browser code (client/custom/src/)
# into the runtime client/custom directory (CRM-CLIENT-001R). Git is the source
# of truth: each runtime tree is replaced as a whole, so files removed from Git
# disappear from the runtime too, and Admin-UI edits to custom metadata are
# overwritten. client/custom/modules (EspoCRM's reserved extension path) and
# every other entry of the runtime client/custom are never written.
#
# The containers' www-data user owns the runtime custom/ tree (the entrypoint
# chowns it on every start), so crm-app and crm-daemon are stopped before the
# authoritative path checks and the swap: nothing in the containers can then
# plant a symlink between check and use. A host process running with the
# container's uid could, so custom/ and custom/Espo are first made owned by the
# invoking user and not group- or world-writable. If crm-app was running, both are
# started again and EspoCRM's clear-cache, rebuild and update-app-timestamp run
# inside crm-app (the last one versions the client URLs, so browsers fetch the new
# client code; the new appTimestamp must be strictly greater than the old one).
# The previous trees are kept until every post-swap step has succeeded. A failure
# prints "FAILED STEP: <step>", restores the previous trees, retains the new ones as
# .failed-<stamp>, and either recovers the cache-bust (RECOVERED) or stops the stack
# (RECOVERY FAILED). Exit codes: 20 swap (both trees put back, staging removed, stack
# stopped), 21 up, 22 clear-cache, 23 rebuild, 24 update-app-timestamp (each followed by
# a recovery); if recovery itself fails: 41 stop, 42 restore trees, 43 up, 44 clear-cache,
# 45 rebuild, 46 update-app-timestamp. After the stack has stopped, INT, TERM and HUP are
# trapped: before the first swap staging is removed and the script exits 48 with the
# stack stopped; from the first swap on the same recovery runs, printing
# "INTERRUPTED: <signal>", and the script exits 47 once RECOVERED (or 41..46 on failure).
# Working trees of earlier runs (.Custom.* and .src.* with .deploy-, .old- or .failed-)
# are only listed ("LEFTOVER: <name>" on stderr), never read, moved or deleted.
# Because it can start services, the LAN access check (scripts/check_access.py)
# runs first and a refusal stops the deploy before the stack is touched.
# Usage: scripts/deploy_custom.sh dev|beta
set -euo pipefail
# shellcheck source=lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

require_target "${1:-}"
require_env_file
require_runtime_paths
# This script starts services again, so the LAN access settings must pass first.
require_access

src="$CRM_REPO_DIR/custom/Espo/Custom"
runtime_custom="$CRM_RUNTIME_DIR/custom"
[ -d "$src" ] || die "repository customisation missing: $src"
[ -d "$runtime_custom" ] || die "runtime custom directory missing: $runtime_custom (see docs/BUILD.md 7.1)"
csrc="$CRM_REPO_DIR/client/custom/src"
runtime_client="$CRM_RUNTIME_DIR/client"
runtime_client_custom="$runtime_client/custom"
[ -d "$csrc" ] && [ ! -L "$csrc" ] || die "repository client customisation missing: $csrc"
[ -z "$(find "$csrc" -type l -print -quit)" ] || die "refusing to deploy: symlink in $csrc"
[ -d "$runtime_client_custom" ] || die "runtime client/custom directory missing: $runtime_client_custom (see docs/BUILD.md 7.1)"

# Files must be readable by www-data in the container whatever the caller's umask.
umask 022
stamp=$(utc_stamp)
parent="$runtime_custom/Espo"
live="$parent/Custom"
staging="$parent/.Custom.deploy-$stamp"
old="$parent/.Custom.old-$stamp"
failed="$parent/.Custom.failed-$stamp"
live_src="$runtime_client_custom/src"
staging_src="$runtime_client_custom/.src.deploy-$stamp"
old_src="$runtime_client_custom/.src.old-$stamp"
failed_src="$runtime_client_custom/.src.failed-$stamp"

# A real directory (not a symlink) whose canonical path is exactly its lexical path.
real_dir() {
    [ ! -L "$1" ] && [ -d "$1" ] || die "refusing to deploy: not a real directory (symlink or missing): $1"
    [ "$(realpath -e -- "$1")" = "$1" ] || die "refusing to deploy: path is redirected: $1"
}
absent() {
    [ ! -e "$1" ] && [ ! -L "$1" ] || die "refusing to deploy: already exists: $1"
}
# Owned by the invoking user and not group- or world-writable, so no other uid
# can rename, replace or add entries in it.
owned_private() {
    local mode
    [ "$(stat -c %u -- "$1")" = "$(id -u)" ] \
        || die "refusing to deploy: not owned by uid $(id -u): $1"
    mode=$(stat -c %a -- "$1")
    [ $((0$mode & 022)) -eq 0 ] \
        || die "refusing to deploy: group- or world-writable (mode $mode): $1"
}
# Take a confirmed real directory away from the container uid: owner and mode
# of that one directory only (never recursive, never through a symlink).
secure_dir() {
    real_dir "$1"
    chown -h -- "$(id -u)" "$1"
    chmod go-w -- "$1"
    real_dir "$1"
    owned_private "$1"
}
# Every path the deploy touches must stay inside the canonical runtime. With
# "owned", custom/ and custom/Espo must also be owned_private (after secure_dir).
check_paths() {
    real_dir "$CRM_RUNTIME_DIR"
    owned_private "$CRM_RUNTIME_DIR"
    real_dir "$runtime_custom"
    [ "${1:-}" != owned ] || owned_private "$runtime_custom"
    if [ -e "$parent" ] || [ -L "$parent" ]; then real_dir "$parent"; fi
    [ "${1:-}" != owned ] || owned_private "$parent"
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

# The client side of check_paths: client/ and client/custom/ (and src/ if present)
# must be real, canonical directories; the working names must be unused. With
# "owned", client/ and client/custom/ must also be owned_private (after secure_dir).
# client/custom/modules and the other entries are never examined or touched.
check_client_paths() {
    real_dir "$runtime_client"
    [ "${1:-}" != owned ] || owned_private "$runtime_client"
    real_dir "$runtime_client_custom"
    [ "${1:-}" != owned ] || owned_private "$runtime_client_custom"
    if [ -e "$live_src" ] || [ -L "$live_src" ]; then real_dir "$live_src"; fi
    absent "$staging_src"
    absent "$old_src"
    absent "$failed_src"
    absent "$failed"
}

# Read EspoCRM's appTimestamp (whole seconds) from the runtime state file as text.
# Prints an integer or nothing. Nothing else of the file is ever printed.
read_app_timestamp() {
    local f="$CRM_RUNTIME_DIR/data/state.php" v
    [ -f "$f" ] && [ ! -L "$f" ] || return 0
    v=$(sed -n "s/^.*['\"]appTimestamp['\"][[:space:]]*=>[[:space:]]*\([0-9][0-9]*\).*\$/\1/p" -- "$f" | head -n 1) || true
    case "$v" in
        ''|*[!0-9]*) return 0 ;;
    esac
    echo "$v"
}

FAILED_STEP=
FAILED_DETAIL=
# update-app-timestamp, then a strict check that the value advanced. The value is
# in whole seconds, so one retry after 1 s; otherwise fail.
bump_app_timestamp() {
    local before after
    before=$(read_app_timestamp)
    before=${before:-0}
    compose exec -T -u www-data -w /var/www/html crm-app php bin/command update-app-timestamp || return 1
    after=$(read_app_timestamp)
    if [ -z "$after" ] || [ "$after" -le "$before" ]; then
        sleep 1
        compose exec -T -u www-data -w /var/www/html crm-app php bin/command update-app-timestamp || return 1
        after=$(read_app_timestamp)
        if [ -z "$after" ] || [ "$after" -le "$before" ]; then
            FAILED_DETAIL=" (not advanced)"
            return 1
        fi
    fi
    echo "appTimestamp advanced: $before -> $after"
}

# up --wait, clear-cache, rebuild, update-app-timestamp; names the failing step.
cache_steps() {
    FAILED_STEP=
    FAILED_DETAIL=
    compose up -d --wait crm-app crm-daemon || { FAILED_STEP=up; return 1; }
    compose exec -T -u www-data -w /var/www/html crm-app php bin/command clear-cache \
        || { FAILED_STEP=clear-cache; return 1; }
    compose exec -T -u www-data -w /var/www/html crm-app php bin/command rebuild \
        || { FAILED_STEP=rebuild; return 1; }
    bump_app_timestamp || { FAILED_STEP=update-app-timestamp; return 1; }
}

# Where each tree stands is read from the file system, never from a variable that a
# signal could leave stale: a tree is "installed" exactly when its staging name is gone,
# and "aside" when the live tree is gone and the old one is present.
present() { [ -e "$1" ] || [ -L "$1" ]; }
had_custom=
had_src=
swap_tree() { # live staging old
    if present "$1"; then
        mv -T -- "$1" "$3" || return 1
    fi
    mv -T -- "$2" "$1" || return 1
}
# Put one tree back as it was before the swap: the new tree (if installed) is kept as
# .failed-<stamp>, the previous tree returns. Safe to repeat and safe at any point.
unswap_tree() { # live staging old failed had
    if ! present "$2"; then
        if present "$1"; then mv -T -- "$1" "$4" || return 1; fi
        if [ -n "$5" ] && present "$3"; then mv -T -- "$3" "$1" || return 1; fi
    elif [ -n "$5" ] && ! present "$1" && present "$3"; then
        mv -T -- "$3" "$1" || return 1
    fi
}
restore_trees() {
    local rc=0
    unswap_tree "$live_src" "$staging_src" "$old_src" "$failed_src" "$had_src" || rc=1
    unswap_tree "$live" "$staging" "$old" "$failed" "$had_custom" || rc=1
    return "$rc"
}
# Staging is never live, so it is always safe to remove, and must not outlive a failure.
remove_staging() {
    remove_tree "$staging" || true
    remove_tree "$staging_src" || true
}

# Earlier runs' working trees are never read, moved or deleted by this run (the live
# trees are always copied from the repository). They are only listed, so the operator
# can remove them (docs/RELEASE.md). Names of this run's stamp are refused elsewhere.
list_leftovers() {
    local d p
    for d in "$parent" "$runtime_client_custom"; do
        for p in "$d"/.Custom.deploy-* "$d"/.Custom.old-* "$d"/.Custom.failed-* \
                 "$d"/.src.deploy-* "$d"/.src.old-* "$d"/.src.failed-*; do
            if present "$p"; then echo "LEFTOVER: ${p##*/}" >&2; fi
        done
    done
}

was_running=
swap_phase=
# Recovery after a failed post-swap step or an interruption: stop, restore the previous
# trees, and (if the stack was running) start and run the cache-bust again. Exits with
# the given code once it has recovered.
recover_and_exit() { # exit code after RECOVERED
    local code=$1 rc
    trap '' INT TERM HUP
    trap - EXIT
    recovery_failed() { # code step
        compose stop crm-daemon crm-app || true
        echo "RECOVERY FAILED: stack left stopped (step: $2); the new and previous trees are retained" >&2
        exit "$1"
    }
    echo "recovering: restoring the previous customisation" >&2
    compose stop crm-daemon crm-app || recovery_failed 41 stop
    restore_trees || recovery_failed 42 restore-trees
    remove_staging
    if [ -n "$was_running" ]; then
        if ! cache_steps; then
            case "$FAILED_STEP" in
                up) rc=43 ;; clear-cache) rc=44 ;; rebuild) rc=45 ;; *) rc=46 ;;
            esac
            recovery_failed "$rc" "$FAILED_STEP"
        fi
        echo "RECOVERED: previous customisation restored" >&2
    else
        echo "RECOVERED: previous customisation restored (crm-app was not running: left stopped)" >&2
    fi
    exit "$code"
}

# A swap that fails (before any later step): both trees go back, staging goes, the stack
# stays stopped. Nothing here is a success.
swap_failed() {
    trap '' INT TERM HUP
    trap - EXIT
    restore_trees || echo "$(basename "$0"): could not restore the previous trees (see .old-* names)" >&2
    remove_staging
    echo "FAILED STEP: swap" >&2
    echo "$(basename "$0"): swap failed; crm-app and crm-daemon are left stopped" >&2
    exit 20
}

# INT, TERM and HUP after the stack has stopped. Before the first swap: staging goes, the
# stack stays stopped and the previous trees are untouched. From the first swap on: the
# same recovery as a failed step.
on_signal() { # signal name
    trap '' INT TERM HUP
    echo "INTERRUPTED: $1" >&2
    if [ -z "$swap_phase" ]; then
        trap - EXIT
        remove_staging
        echo "$(basename "$0"): interrupted before the swap; crm-app and crm-daemon are left stopped" >&2
        exit 48
    fi
    recover_and_exit 47
}

# First pass before touching the stack, so a bad layout leaves it running.
check_paths
check_client_paths

[ -z "$(compose ps --status running -q crm-app)" ] || was_running=1
# From here on a signal is handled (on_signal); one that arrives during the stop is acted
# on as soon as the stop returns, so the stack is stopped when the script exits.
trap 'on_signal INT' INT
trap 'on_signal TERM' TERM
trap 'on_signal HUP' HUP
compose stop crm-daemon crm-app
trap 'echo "$(basename "$0"): deploy failed; crm-app and crm-daemon are left stopped" >&2' EXIT

# Authoritative pass: nothing in the containers can change the tree from here on.
# custom/ is secured first (its parent, the runtime directory, is already
# private), so custom/Espo cannot be swapped while it is secured in turn. The
# same order for client/custom/ (the parent of src/).
check_paths
check_client_paths
secure_dir "$runtime_custom"
[ -e "$parent" ] || [ -L "$parent" ] || mkdir -- "$parent"
secure_dir "$parent"
check_paths owned
# client/ is never in the container's hands (the entrypoint chowns client/custom
# and below only), so it must already be private; client/custom itself is secured.
real_dir "$runtime_client"
owned_private "$runtime_client"
secure_dir "$runtime_client_custom"
check_client_paths owned
list_leftovers
# Whether each live tree exists, read after the last check (a first deploy has none).
if present "$live"; then had_custom=1; fi
if present "$live_src"; then had_src=1; fi

trap 'remove_staging; echo "$(basename "$0"): deploy failed; crm-app and crm-daemon are left stopped" >&2' EXIT
# Stage a fresh copy beside each live tree (same filesystem), then swap them in by
# rename. The runtime custom directory itself is never replaced, because it is
# the bind-mount source and a running container keeps the original inode.
cp -R -- "$src" "$staging"
real_dir "$staging"
cp -R -- "$csrc" "$staging_src"
real_dir "$staging_src"
[ -z "$(find "$staging_src" -type l -print -quit)" ] || die "refusing to deploy: symlink in the staged client tree"
# Both trees are swapped; the previous ones are kept until every later step has
# succeeded. If any swap step fails, both trees are put back (exit 20).
swap_phase=1
swap_tree "$live" "$staging" "$old" || swap_failed
swap_tree "$live_src" "$staging_src" "$old_src" || swap_failed

if [ -z "$was_running" ]; then
    trap - EXIT INT TERM HUP
    remove_tree "$old"
    remove_tree "$old_src"
    echo "customisation deployed: $src -> $live"
    echo "client customisation deployed: $csrc -> $live_src"
    echo "crm-app was not running: left stopped, clear-cache/rebuild skipped." \
        "A first installation rebuilds by itself; otherwise re-run this script once the stack is up." \
        "The client cache-bust (update-app-timestamp) was skipped: browsers keep the old client code" \
        "until it runs. To complete it: start the stack (scripts/up.sh dev), then re-run this script."
    exit 0
fi

trap - EXIT
if ! cache_steps; then
    step=$FAILED_STEP
    echo "FAILED STEP: $step$FAILED_DETAIL" >&2
    case "$step" in
        up) code=21 ;; clear-cache) code=22 ;; rebuild) code=23 ;; *) code=24 ;;
    esac
    recover_and_exit "$code"
fi
# Every step succeeded: the previous trees are no longer needed. A signal from here on
# must not start a recovery over a half-removed previous tree.
trap - INT TERM HUP
remove_tree "$old"
remove_tree "$old_src"
echo "customisation deployed: $src -> $live"
echo "client customisation deployed: $csrc -> $live_src"
echo "crm-app and crm-daemon restarted; clear-cache and rebuild completed in crm-app; client cache-bust done"
