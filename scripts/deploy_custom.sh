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
# plant a symlink between check and use. A host process running with the
# container's uid could, so custom/ and custom/Espo are first made owned by the
# invoking user and not group- or world-writable. If crm-app was running, both are
# started again and EspoCRM's clear-cache and rebuild run inside crm-app.
# Because it can start services, the LAN access check (scripts/check_access.py)
# runs first and a refusal stops the deploy before the stack is touched.
#
# Browser assets (CRM-WIP-LINK-001): the repository's client/custom/src is
# delivered the same way into the runtime client/custom/src (the other entries of
# client/custom, such as modules/, are never read, written or listed). The tree
# is staged beside src (.src.deploy-<stamp>) and swapped in by rename; the
# previous custom/Espo/Custom and src are kept (.Custom.old-<stamp>,
# .src.old-<stamp>) until clear-cache, rebuild and update-app-timestamp have
# succeeded, and the stored appTimestamp must strictly increase so browsers
# fetch the new code. The marker client/custom/.src-managed-by-git records that
# the script manages src: a repository without client/custom/src removes the
# runtime src only when the marker is present. With neither a repository nor a
# runtime src the script behaves exactly as it did before this delivery existed.
# Earlier failed runs' working trees are only listed on stderr (LEFTOVER: <name>).
#
# On a failure after the stack stopped, both trees are put back as they were,
# the new trees are kept as .Custom.failed-<stamp> and .src.failed-<stamp>, the
# step is named on stderr (FAILED STEP: <step>) and the exit code is the step's:
#   20 stage-custom       copy of custom/Espo/Custom into staging
#   21 stage-client       copy of client/custom/src into staging
#   22 swap-custom        rename of the custom/Espo/Custom trees
#   23 swap-client        rename of the client/custom/src trees
#   24 up                 docker compose up -d --wait
#   25 clear-cache
#   26 rebuild
#   27 update-app-timestamp (also: the stored appTimestamp did not advance)
#   28 marker             writing or removing client/custom/.src-managed-by-git
#   29 interrupted        INT, TERM or HUP after the stack stopped
#   30 cleanup            deleting the previous trees after success (the new
#                         trees stay installed; the old ones stay as .old-<stamp>)
#   Other failures before the swap (path checks, refusals) exit 1 as before.
# If crm-app was running it is started again and the cache steps re-run, then
# RECOVERED is printed; if that fails, or crm-app was not running, the stack is
# left stopped and RECOVERY FAILED / "left stopped" says so.
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

# Files must be readable by www-data in the container whatever the caller's umask.
umask 022
stamp=$(utc_stamp)
parent="$runtime_custom/Espo"
live="$parent/Custom"
staging="$parent/.Custom.deploy-$stamp"
old="$parent/.Custom.old-$stamp"
failed="$parent/.Custom.failed-$stamp"

# Browser assets: only client/custom/src is managed.
csrc="$CRM_REPO_DIR/client/custom/src"
client_dir="$CRM_RUNTIME_DIR/client"
client_custom="$client_dir/custom"
csrc_live="$client_custom/src"
cstaging="$client_custom/.src.deploy-$stamp"
cold="$client_custom/.src.old-$stamp"
cfailed="$client_custom/.src.failed-$stamp"
marker="$client_custom/.src-managed-by-git"

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

# What the browser-asset delivery does this run: install (the repository has
# client/custom/src), remove (it has none, the runtime has one and the marker
# says the script manages it), unmanaged (the same without the marker: left
# untouched) or none (neither has one: the script behaves as it always did).
decide_client_mode() {
    if [ -e "$csrc" ] || [ -L "$csrc" ]; then
        cmode=install
    elif [ -e "$csrc_live" ] || [ -L "$csrc_live" ]; then
        if [ -f "$marker" ] && [ ! -L "$marker" ]; then cmode=remove; else cmode=unmanaged; fi
    else
        cmode=none
    fi
}
# The repository source: a real directory with no symlink and no special file.
check_client_source() {
    [ ! -L "$csrc" ] && [ -d "$csrc" ] \
        || die "refusing to deploy: client source is not a real directory: $csrc"
    [ -z "$(find "$csrc" -type l -print -quit)" ] \
        || die "refusing to deploy: symlink inside the client source: $csrc"
    [ -z "$(find "$csrc" -not -type f -not -type d -print -quit)" ] \
        || die "refusing to deploy: special file inside the client source: $csrc"
}
# The client/ side of check_paths. client/ is checked, never changed: it must
# already be real, canonical and private. Only client/custom is secured (below).
check_client_paths() {
    real_dir "$client_dir"
    owned_private "$client_dir"
    real_dir "$client_custom"
    [ "${1:-}" != owned ] || owned_private "$client_custom"
    if [ -e "$csrc_live" ] || [ -L "$csrc_live" ]; then real_dir "$csrc_live"; fi
    if [ -e "$marker" ] || [ -L "$marker" ]; then
        [ ! -L "$marker" ] && [ -f "$marker" ] \
            || die "refusing to deploy: the marker is not a regular file: $marker"
    fi
    absent "$cstaging"
    absent "$cold"
    absent "$cfailed"
    absent "$failed"
}
# Names only: earlier failed runs' trees are never read, moved or deleted.
list_leftovers() {
    local d p
    for d in "$client_custom" "$parent"; do
        for p in "$d"/.src.deploy-* "$d"/.src.old-* "$d"/.src.failed-* \
                 "$d"/.Custom.deploy-* "$d"/.Custom.old-* "$d"/.Custom.failed-*; do
            if [ -e "$p" ] || [ -L "$p" ]; then echo "LEFTOVER: $(basename "$p")" >&2; fi
        done
    done
}

# First pass before touching the stack, so a bad layout leaves it running.
check_paths
decide_client_mode
first_mode=$cmode
if [ "$cmode" != none ]; then
    [ "$cmode" != install ] || check_client_source
    check_client_paths
fi

was_running=
[ -z "$(compose ps --status running -q crm-app)" ] || was_running=1
compose stop crm-daemon crm-app
trap 'echo "$(basename "$0"): deploy failed; crm-app and crm-daemon are left stopped" >&2' EXIT

# Authoritative pass: nothing in the containers can change the tree from here on.
# custom/ is secured first (its parent, the runtime directory, is already
# private), so custom/Espo cannot be swapped while it is secured in turn.
check_paths
secure_dir "$runtime_custom"
[ -e "$parent" ] || [ -L "$parent" ] || mkdir -- "$parent"
secure_dir "$parent"
check_paths owned
decide_client_mode
[ "$cmode" = "$first_mode" ] || die "refusing to deploy: the client/custom/src layout changed while the stack stopped"
if [ "$cmode" != none ]; then
    [ "$cmode" != install ] || check_client_source
    check_client_paths
    secure_dir "$client_custom"
    check_client_paths owned
    list_leftovers
fi

if [ "$cmode" = none ]; then
    # Neither side has client/custom/src: exactly the behaviour before the
    # browser-asset delivery existed.
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
    exit 0
fi

# ---- Transactional path: custom/Espo/Custom and client/custom/src together ----
# State of each tree, so that a failure puts back exactly what was moved.
custom_aside=; custom_new=; client_aside=; client_new=
in_recovery=

app_exec() {
    compose exec -T -u www-data -w /var/www/html crm-app "$@"
}
# The stored appTimestamp (whole seconds), read from the application's own config.
read_app_timestamp() {
    local value
    value=$(app_exec php -r '$a = include "data/config.php"; $b = is_file("data/config-internal.php") ? include "data/config-internal.php" : []; $c = is_file("data/state.php") ? include "data/state.php" : []; echo (int) (array_merge($a, $b, $c)["appTimestamp"] ?? 0);') || return 1
    case "$value" in
        ''|*[!0-9]*) echo "$(basename "$0"): cannot read appTimestamp (got '$value')" >&2; return 1 ;;
    esac
    printf '%s\n' "$value"
}
# update-app-timestamp, then the stored value must have strictly increased;
# the clock has whole-second resolution, so one retry after one second.
advance_app_timestamp() {
    local before after
    before=$(read_app_timestamp) || return 1
    app_exec php bin/command update-app-timestamp || return 1
    after=$(read_app_timestamp) || return 1
    if [ "$after" -le "$before" ]; then
        sleep 1
        app_exec php bin/command update-app-timestamp || return 1
        after=$(read_app_timestamp) || return 1
    fi
    if [ "$after" -le "$before" ]; then
        echo "$(basename "$0"): appTimestamp did not advance ($before -> $after)" >&2
        return 1
    fi
}
stage_custom() {
    cp -R -- "$src" "$staging" && real_dir "$staging"
}
stage_client() {
    cp -R -- "$csrc" "$cstaging" && real_dir "$cstaging" \
        && [ -z "$(find "$cstaging" -type l -print -quit)" ]
}
swap_custom() {
    if [ -e "$live" ]; then
        mv -T -- "$live" "$old" || return 1
        custom_aside=1
    fi
    mv -T -- "$staging" "$live" || return 1
    custom_new=1
}
swap_client() {
    if [ -e "$csrc_live" ]; then
        mv -T -- "$csrc_live" "$cold" || return 1
        client_aside=1
    fi
    if [ "$cmode" = install ]; then
        mv -T -- "$cstaging" "$csrc_live" || return 1
        client_new=1
    fi
}
write_marker() {
    if [ "$cmode" = install ]; then
        printf '%s\n' "client/custom/src is managed by scripts/deploy_custom.sh" > "$marker"
    else
        rm -f -- "$marker"
    fi
}
# Put both trees back as they were. Failures here are reported, not fatal.
restore_trees() {
    local rc=0
    if [ -n "$client_new" ]; then mv -T -- "$csrc_live" "$cfailed" || rc=1; fi
    if [ -n "$client_aside" ]; then mv -T -- "$cold" "$csrc_live" || rc=1; fi
    if [ -n "$custom_new" ]; then mv -T -- "$live" "$failed" || rc=1; fi
    if [ -n "$custom_aside" ]; then mv -T -- "$old" "$live" || rc=1; fi
    remove_tree "$staging" || rc=1
    remove_tree "$cstaging" || rc=1
    return $rc
}
# FAILED STEP: name it, restore both trees, start the stack again if it was
# running, and exit with the step's own code.
fail_step() {
    local step=$1 code=$2 ok=1 up_ok=
    [ -z "$in_recovery" ] || exit "$code"
    in_recovery=1
    trap '' INT TERM HUP
    trap - EXIT
    echo "$(basename "$0"): FAILED STEP: $step" >&2
    if ! restore_trees; then
        ok=
        echo "$(basename "$0"): the previous trees could not all be put back; see the .old-$stamp and .failed-$stamp names" >&2
    fi
    if [ -n "$ok" ] && [ -n "$was_running" ]; then
        # In this chain app_exec runs only after compose up succeeded: note it.
        app_exec() { up_ok=1; compose exec -T -u www-data -w /var/www/html crm-app "$@"; }
        { compose up -d --wait crm-app crm-daemon \
            && app_exec php bin/command clear-cache \
            && app_exec php bin/command rebuild \
            && app_exec php bin/command update-app-timestamp; } >&2 || ok=
    fi
    if [ -n "$ok" ] && [ -n "$was_running" ]; then
        echo "$(basename "$0"): RECOVERED: previous trees restored, crm-app and crm-daemon started again" >&2
    elif [ -n "$ok" ]; then
        echo "$(basename "$0"): RECOVERED: previous trees restored; crm-app was not running and is left stopped" >&2
    elif [ -n "$up_ok" ]; then
        echo "$(basename "$0"): RECOVERY FAILED: previous trees restored and crm-app and crm-daemon started, but a cache step failed" >&2
    else
        echo "$(basename "$0"): RECOVERY FAILED: crm-app and crm-daemon are left stopped" >&2
    fi
    exit "$code"
}
run_step() {
    local step=$1 code=$2
    shift 2
    "$@" || fail_step "$step" "$code"
}

trap 'remove_tree "$staging"; remove_tree "$cstaging"; echo "$(basename "$0"): deploy failed; crm-app and crm-daemon are left stopped" >&2' EXIT
trap 'fail_step interrupted 29' INT TERM HUP

case "$cmode" in
    install)
        if [ -e "$csrc_live" ] && [ ! -e "$marker" ]; then
            echo "client/custom/src exists without the marker $marker: replacing it with the repository tree (kept until every step succeeds)"
        fi ;;
    unmanaged) echo "client/custom/src exists without the marker $marker: left untouched (not managed by this script)" ;;
esac

run_step stage-custom 20 stage_custom
[ "$cmode" != install ] || run_step stage-client 21 stage_client
run_step swap-custom 22 swap_custom
if [ "$cmode" = install ] || [ "$cmode" = remove ]; then
    run_step swap-client 23 swap_client
fi
echo "customisation deployed: $src -> $live"
case "$cmode" in
    install) echo "client assets deployed: $csrc -> $csrc_live" ;;
    remove) echo "client assets removed: $csrc_live (the repository has none and the marker says this script manages it)" ;;
esac

if [ -n "$was_running" ]; then
    run_step up 24 compose up -d --wait crm-app crm-daemon
    run_step clear-cache 25 app_exec php bin/command clear-cache
    run_step rebuild 26 app_exec php bin/command rebuild
    run_step update-app-timestamp 27 advance_app_timestamp
fi
if [ "$cmode" = install ] || [ "$cmode" = remove ]; then
    run_step marker 28 write_marker
fi

# Every step succeeded: the previous trees can go.
trap - INT TERM HUP
trap - EXIT
cleanup_rc=0
remove_tree "$old" || cleanup_rc=1
if [ -n "$client_aside" ]; then remove_tree "$cold" || cleanup_rc=1; fi
if [ "$cleanup_rc" -ne 0 ]; then
    echo "$(basename "$0"): FAILED STEP: cleanup (the previous trees remain as .old-$stamp; the new trees are installed)" >&2
    exit 30
fi

if [ -n "$was_running" ]; then
    echo "crm-app and crm-daemon restarted; clear-cache and rebuild completed in crm-app"
    echo "application timestamp advanced"
else
    echo "crm-app was not running: left stopped, clear-cache/rebuild skipped." \
        "A first installation rebuilds by itself; otherwise re-run this script once the stack is up." \
        "The application timestamp was not advanced."
fi
