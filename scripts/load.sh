#!/usr/bin/env bash
# Load one sealed Salesforce snapshot into EspoCRM through crm-load (CRM-006).
# Usage (root only):
#   scripts/load.sh [--accept-drift URL] [--resume PREVIOUS-OUT-DIR] [--reconciliation RECONCILE-RUN-DIR]
#                   <dev|beta> <snapshot-dir> <new-output-dir>
#
#   dev   accepts only a synthetic snapshot (manifest mode "selftest");
#   beta  refuses a synthetic snapshot.
#
#   --accept-drift URL   passed to crm-load; must be
#                        https://github.com/infosec-estateresearch/CRM/issues/9#issuecomment-<digits>.
#                        crm-load requires it for a RECONCILED_WITH_DRIFT manifest and refuses
#                        it for a RECONCILED one.
#   --resume DIR         an earlier, interrupted output of the same snapshot sha and target;
#                        crm-load checks the sha. It is only read; the new output is separate.
#   --reconciliation DIR the sealed *-reconcile run (<id>-reconcile/report/manifest.json) whose
#                        report/reconciliation.json supplies the absent_unexplained counts;
#                        crm-load checks it names this snapshot. Required for beta, optional
#                        for dev (without it the counts are reported as "unknown").
#
# Guards, all checked before anything runs:
#   * the caller is root; each option is given at most once;
#   * the snapshot is a canonical path directly under $SNAPSHOT_BASE, and sealed:
#     owned by root, directories 0700, files 0400, no symlinks or special files;
#   * manifest.json is in exactly one layout (the CRM-002-W rule):
#       <id>/manifest.json, with no <id>/run and no <id>/input; or
#       <id>/run/manifest.json, with no <id>/manifest.json and only input/ and run/ at the top;
#   * beta is given --reconciliation; the reconciliation run, when given, is sealed the same
#     way directly under $SNAPSHOT_BASE;
#   * the resume directory, when given, is a canonical root-owned 0700 directory holding only
#     root-owned 0600 regular files, under a root-owned 0700 parent;
#   * the output directory does not exist and its parent is a root-owned 0700
#     directory; crm-load creates it 0700 and its files 0600;
#   * $RUNTIME_BASE/<target>/load.env is a root-owned 0600 regular file holding exactly
#     CRM_LOAD_HOST, CRM_LOAD_PORT and CRM_LOAD_API_KEY (NAME=value lines; it is
#     parsed, never sourced).
# crm-load runs as python3 -I -B with a clean environment holding only those three
# variables. The key is never printed.
set -euo pipefail
umask 077

# Fixed paths. Tests run a copy with these four lines rewritten; nothing else overrides them.
REQUIRED_UID=0
SNAPSHOT_BASE=/srv/CRM/runtime/migrate/snapshots
RUNTIME_BASE=/srv/CRM/runtime
REPO_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)

PROG=load.sh
die() {
    echo "$PROG: refusing to run: $*" >&2
    exit 2
}

USAGE="usage: $PROG [--accept-drift URL] [--resume DIR] [--reconciliation DIR] <dev|beta> <snapshot-dir> <new-output-dir>"
DRIFT_RE='^https://github\.com/infosec-estateresearch/CRM/issues/9#issuecomment-[0-9]{1,20}$'
accept_drift=
resume=
reconciliation=
have_drift=0
have_resume=0
have_rec=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --accept-drift)
            [ "$have_drift" -eq 0 ] || die "--accept-drift given twice"
            [ "$#" -ge 2 ] || die "$USAGE"
            have_drift=1; accept_drift=$2; shift 2 ;;
        --resume)
            [ "$have_resume" -eq 0 ] || die "--resume given twice"
            [ "$#" -ge 2 ] || die "$USAGE"
            have_resume=1; resume=$2; shift 2 ;;
        --reconciliation)
            [ "$have_rec" -eq 0 ] || die "--reconciliation given twice"
            [ "$#" -ge 2 ] || die "$USAGE"
            have_rec=1; reconciliation=$2; shift 2 ;;
        --) shift; break ;;
        -*) die "unknown option" ;;
        *) break ;;
    esac
done
[ "$#" -eq 3 ] || die "$USAGE"
target=$1
snapshot=$2
outdir=$3
if [ "$have_drift" -eq 1 ]; then
    [[ "$accept_drift" =~ $DRIFT_RE ]] || die "--accept-drift must be an Issue #9 comment URL"
fi

case "$target" in
    dev|beta) ;;
    *) die "target must be 'dev' or 'beta' (got '$target')" ;;
esac

[ "$EUID" -eq "$REQUIRED_UID" ] || die "must be run as root"

# owner_mode PATH -> "<uid> <octal mode>" of PATH itself (no symlink following).
owner_mode() {
    stat -c '%u %a' -- "$1"
}

# sealed_dir LABEL PATH -> prints the canonical path of a sealed directory directly under
# $SNAPSHOT_BASE (root-owned, directories 0700, files 0400, no links or special files).
sealed_dir() {
    local label=$1 path=$2 canon bad
    case "$path" in
        /*) ;;
        *) die "$label path must be absolute" ;;
    esac
    [ -d "$path" ] && [ ! -L "$path" ] || die "$label is not a directory: $path"
    canon=$(realpath -e -- "$path") || die "$label path does not resolve"
    [ "$canon" = "${path%/}" ] || die "$label path is not canonical"
    [ "$(dirname -- "$canon")" = "$SNAPSHOT_BASE" ] || die "$label must be directly under $SNAPSHOT_BASE"
    [ "$(owner_mode "$SNAPSHOT_BASE")" = "$REQUIRED_UID 700" ] || die "$SNAPSHOT_BASE must be root-owned 0700"
    [ "$(owner_mode "$canon")" = "$REQUIRED_UID 700" ] || die "$label is not sealed (root 0700)"
    bad=$(find "$canon" \( -type l -o ! \( -type d -o -type f \) \
            -o ! -uid "$REQUIRED_UID" \
            -o \( -type d ! -perm 0700 \) -o \( -type f ! -perm 0400 \) \) -print -quit)
    [ -z "$bad" ] || die "$label is not sealed (root, directories 0700, files 0400, no links)"
    printf '%s\n' "$canon"
}

# --- snapshot -------------------------------------------------------------------
canonical=$(sealed_dir snapshot "$snapshot") || exit 2
# Exactly one layout (CRM-002-W). The waiver under input/ is never read.
if [ -e "$canonical/manifest.json" ] || [ -L "$canonical/manifest.json" ]; then
    [ ! -e "$canonical/run" ] && [ ! -L "$canonical/run" ] && [ ! -e "$canonical/input" ] \
        && [ ! -L "$canonical/input" ] \
        || die "snapshot layout is ambiguous: manifest.json at the top and a run/ or input/ directory"
    [ -f "$canonical/manifest.json" ] || die "snapshot has no manifest.json"
else
    top=$(cd -- "$canonical" && LC_ALL=C ls -A)
    [ "$top" = "input"$'\n'"run" ] && [ -d "$canonical/input" ] && [ -d "$canonical/run" ] \
        || die "snapshot layout unknown: expected <id>/manifest.json, or only input/ and run/ at the top"
    [ -f "$canonical/run/manifest.json" ] || die "snapshot has no manifest.json (looked in run/)"
fi

# --- reconciliation run (required for beta, optional for dev) -----------------------
extra=()
if [ "$target" = "beta" ] && [ "$have_rec" -eq 0 ]; then
    die "beta requires --reconciliation"
fi
if [ "$have_rec" -eq 1 ]; then
    rec_canonical=$(sealed_dir "reconciliation run" "$reconciliation") || exit 2
    [ "$rec_canonical" != "$canonical" ] || die "reconciliation run must not be the snapshot"
    extra+=(--reconciliation "$rec_canonical")
fi
if [ "$have_drift" -eq 1 ]; then
    extra+=(--accept-drift "$accept_drift")
fi

# --- output directory -------------------------------------------------------------
case "$outdir" in
    /*) ;;
    *) die "output directory must be absolute" ;;
esac
outdir=${outdir%/}
[ ! -e "$outdir" ] && [ ! -L "$outdir" ] || die "output directory already exists: $outdir"
parent=$(dirname -- "$outdir")
[ -d "$parent" ] && [ ! -L "$parent" ] || die "output parent is not a directory"
[ "$(realpath -e -- "$parent")" = "$parent" ] || die "output parent path is not canonical"
[ "$(owner_mode "$parent")" = "$REQUIRED_UID 700" ] || die "output parent must be root-owned 0700"
case "$outdir/" in
    "$canonical"/*) die "output directory must not be inside the snapshot" ;;
esac

# --- resume directory (optional) ----------------------------------------------------
if [ "$have_resume" -eq 1 ]; then
    case "$resume" in
        /*) ;;
        *) die "resume directory must be absolute" ;;
    esac
    resume=${resume%/}
    [ -d "$resume" ] && [ ! -L "$resume" ] || die "resume directory is not a directory: $resume"
    [ "$(realpath -e -- "$resume")" = "$resume" ] || die "resume directory path is not canonical"
    [ "$resume" != "$outdir" ] || die "resume directory must differ from the output directory"
    rparent=$(dirname -- "$resume")
    [ "$(owner_mode "$rparent")" = "$REQUIRED_UID 700" ] || die "resume parent must be root-owned 0700"
    [ "$(owner_mode "$resume")" = "$REQUIRED_UID 700" ] || die "resume directory is not sealed (root 0700)"
    bad=$(find "$resume" -mindepth 1 \( ! -type f -o ! -uid "$REQUIRED_UID" -o ! -perm 0600 \) -print -quit)
    [ -z "$bad" ] || die "resume directory is not sealed (root-owned 0600 regular files only)"
    case "$resume/" in
        "$canonical"/*) die "resume directory must not be inside the snapshot" ;;
    esac
    extra+=(--resume "$resume")
fi

# --- runtime env --------------------------------------------------------------------
envfile="$RUNTIME_BASE/$target/load.env"
[ -f "$envfile" ] && [ ! -L "$envfile" ] || die "env file missing: $envfile"
[ "$(owner_mode "$envfile")" = "$REQUIRED_UID 600" ] || die "env file must be root-owned 0600: $envfile"
CRM_LOAD_HOST=
CRM_LOAD_PORT=
CRM_LOAD_API_KEY=
seen=" "
while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
        ''|'#'*) continue ;;
    esac
    name=${line%%=*}
    [ "$name" != "$line" ] || die "env file: malformed line"
    value=${line#*=}
    case "$name" in
        CRM_LOAD_HOST|CRM_LOAD_PORT|CRM_LOAD_API_KEY) ;;
        *) die "env file: unexpected variable" ;;
    esac
    case "$seen" in
        *" $name "*) die "env file: $name assigned twice" ;;
    esac
    seen="$seen$name "
    printf -v "$name" '%s' "$value"
done < "$envfile"
[ -n "$CRM_LOAD_HOST" ] || die "env file: CRM_LOAD_HOST missing"
[ -n "$CRM_LOAD_PORT" ] || die "env file: CRM_LOAD_PORT missing"
[ -n "$CRM_LOAD_API_KEY" ] || die "env file: CRM_LOAD_API_KEY missing"
[ "$CRM_LOAD_HOST" = "127.0.0.1" ] || die "env file: CRM_LOAD_HOST must be 127.0.0.1"
case "$CRM_LOAD_PORT" in
    ''|*[!0-9]*) die "env file: CRM_LOAD_PORT must be a number" ;;
esac

# --- run ------------------------------------------------------------------------------
cd /
exec env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin LANG=C.UTF-8 \
    CRM_LOAD_HOST="$CRM_LOAD_HOST" CRM_LOAD_PORT="$CRM_LOAD_PORT" CRM_LOAD_API_KEY="$CRM_LOAD_API_KEY" \
    python3 -I -B "$REPO_DIR/load/bin/crm-load.py" load "$canonical" --target "$target" --out "$outdir" \
    ${extra[@]+"${extra[@]}"}
