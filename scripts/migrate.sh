#!/usr/bin/env bash
# scripts/migrate.sh: operator wrapper for the crm-migrate extractor (CRM-002).
#
#   migrate.sh [migrate] selftest [--quick]
#   migrate.sh [migrate] contract-check
#   migrate.sh [migrate] count
#   migrate.sh [migrate] extract [--passes N] [--overlap-minutes M]
#   migrate.sh [migrate] reconcile <snapshot-id> [<previous-snapshot-id>]
#   migrate.sh [migrate] credentials
#   migrate.sh [migrate] --auth soap-legacy [--sandbox] contract-check|count|extract [...]
#
# Root only. The optional first argument is the target and must be "migrate".
# Every run writes a new snapshots/<UTC id>-<mode>/ directory owned 64021:64021 (0700),
# runs one container, then seals it (root:root, directories 0700, files 0400) and
# re-verifies the manifest checksums. See docs/MIGRATION.md.
set -euo pipefail
umask 077
export LC_ALL=C

readonly RUNTIME=/srv/CRM/runtime/migrate
readonly SNAPSHOTS="$RUNTIME/snapshots"
readonly ENV_FILE="$RUNTIME/env"
readonly RUN_UID=64021
readonly RUN_GID=64021
readonly PROJECT=crm-migrate
readonly PYTHON=/usr/bin/python3

SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
REPO="$(dirname -- "$(dirname -- "$SCRIPT_PATH")")"
readonly SCRIPT_PATH REPO
readonly COMPOSE_FILE="$REPO/deploy/migrate/compose.json"
readonly ENV_EXAMPLE="$REPO/deploy/migrate/env.example"
readonly ENV_EXAMPLE_LEGACY="$REPO/deploy/migrate/env.legacy.example"
readonly ENTRY="$REPO/migrate/bin/crm-migrate.py"
readonly SUBCOMMANDS=" selftest contract-check count extract reconcile credentials "

RUN_DIR=""
CRED_TMP=""
ENV_NAMES=()

die() { printf 'migrate.sh: refused: %s\n' "$*" >&2; exit 1; }
usage() { sed -n '4,10p' "$SCRIPT_PATH" | sed 's/^# \{0,1\}//' >&2; exit 2; }

# Host checks are pure functions in migrate/lib/crm_migrate/hostcheck.py (unit-tested).
check() { "$PYTHON" -I -B "$ENTRY" hostcheck "$@"; }
require() { check "$@" || die "host check '$1' failed"; }

is_subcommand() { [[ "$SUBCOMMANDS" == *" $1 "* ]]; }

# CRM-002-S legacy checks print to stdout for capture (fingerprint) or the container pipe.
legacy_require() { "$PYTHON" -I -B "$ENTRY" hostcheck "$@" || die "legacy host check '$1' failed"; }

# ------------------------------------------------------------------ arguments
target=migrate
auth=client-credentials
sandbox_args=()
if [[ $# -ge 1 ]] && [[ "$1" != --auth ]] && ! is_subcommand "$1"; then
    target="$1"
    shift
fi
if [[ $# -ge 1 && "$1" == --auth ]]; then
    [[ $# -ge 2 && "$2" == soap-legacy ]] || usage
    auth=soap-legacy
    shift 2
    if [[ $# -ge 1 && "$1" == --sandbox ]]; then
        sandbox_args=(--sandbox)
        shift
    fi
fi
[[ $# -ge 1 ]] || usage
sub="$1"
shift
is_subcommand "$sub" || usage

# ------------------------------------------------------------------ guards (every subcommand)
[[ ${EUID} -eq 0 ]] || die "must be run as root"
[[ -x "$PYTHON" ]] || die "$PYTHON is required"
require target "$target"
[[ -f "$ENV_EXAMPLE" && -f "$ENTRY" && -f "$COMPOSE_FILE" ]] || die "repository files missing"
mapfile -t ENV_NAMES < <("$PYTHON" -I -B "$ENTRY" hostcheck env-names "$ENV_EXAMPLE")
[[ ${#ENV_NAMES[@]} -gt 0 ]] || die "no variable names found in env.example"
# Refuse if any env-file variable is exported in the calling shell.
for name in "${ENV_NAMES[@]}"; do
    [[ -z "${!name+set}" ]] || die "$name is exported in the calling shell; unset it first"
done
require env-clean "$ENV_EXAMPLE"
require runtime-dirs
require uid-free "$(getent passwd "$RUN_UID" || true)" "$(getent group "$RUN_GID" || true)"
if [[ "$auth" == soap-legacy ]]; then
    [[ -f "$ENV_EXAMPLE_LEGACY" ]] || die "repository files missing"
    for name in NIF_SRC_SALESFORCE_USER NIF_SRC_SALESFORCE_PASS CRM_LEGACY_ENV_FILE; do
        [[ ! -v "$name" ]] || die "$name is set in the calling shell; unset it first"
    done
fi

# ------------------------------------------------------------------ helpers
compose_run() {
    # Compose never sees an env-file variable from this process environment, so the
    # env file cannot be overridden, and no project .env file is read for interpolation.
    local service="$1"
    shift
    local unset_args=()
    local name
    for name in "${ENV_NAMES[@]}" COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES COMPOSE_ENV_FILES; do
        unset_args+=(-u "$name")
    done
    env "${unset_args[@]}" CRM_MIGRATE_RUN_DIR="$RUN_DIR" \
        docker compose --project-name "$PROJECT" --file "$COMPOSE_FILE" --env-file /dev/null \
        run --rm --no-deps -T "$service" "$@"
}

new_run_dir() {
    local mode="$1" id
    id="$(date -u +%Y%m%dT%H%M%SZ)-$mode"
    require run-id "$id"
    RUN_DIR="$SNAPSHOTS/$id"
    [[ ! -e "$RUN_DIR" && ! -L "$RUN_DIR" ]] || die "run directory already exists"
    require run-dir-absent "$RUN_DIR"
    mkdir -m 0700 -- "$RUN_DIR" || die "cannot create the run directory"
    chown "$RUN_UID:$RUN_GID" -- "$RUN_DIR"
    require run-dir-prepared "$RUN_DIR"
    printf 'migrate.sh: run directory %s\n' "$RUN_DIR"
}

seal() {
    local dir="$1"
    chown -R --no-dereference root:root -- "$dir" &&
        find "$dir" -type d -exec chmod 0700 {} + &&
        find "$dir" -type f -exec chmod 0400 {} + &&
        check sealed "$dir"
}

finish() {
    # finish <run dir> <directory holding manifest.json> <tool exit code>
    if ! seal "$1"; then
        printf 'migrate.sh: FAILED: the run directory could not be sealed\n' >&2
        exit 20
    fi
    if ! check verify-manifest "$2"; then
        printf 'migrate.sh: FAILED: manifest checksums did not re-verify after sealing\n' >&2
        exit 21
    fi
    printf 'migrate.sh: sealed root:root 0700/0400 and checksums re-verified; tool exit code %s\n' "$3"
    exit "$3"
}

run_container() {
    local service="$1" mode="$2"
    shift 2
    command -v docker >/dev/null || die "docker is required"
    new_run_dir "$mode"
    local rc=0
    compose_run "$service" "$mode" --out /out "$@" || rc=$?
    finish "$RUN_DIR" "$RUN_DIR" "$rc"
}

require_env_file() {
    require env-file "$ENV_EXAMPLE"
}

run_legacy() {
    # TEMPORARY (CRM-002-S): the legacy username/password go from the ELT env file (read-only,
    # parsed by hostcheck.parse_legacy_env) straight into the container's stdin. They are never
    # written to /srv/CRM/runtime/migrate, an argument list or the environment. The ELT env
    # file's path is CRM_LEGACY_ENV_FILE in $ENV_FILE (never committed); hostcheck refuses
    # while it is empty, and checks it is absolute, symlink-free, a root-owned regular file
    # and not group- or world-writable.
    local mode="$1"
    shift
    command -v docker >/dev/null || die "docker is required"
    local before after rc=0
    before="$(legacy_require legacy-fingerprint)" || die "legacy env file could not be fingerprinted"
    legacy_require waiver-file
    new_run_dir "$mode"
    local args=(--out /out/run --auth soap-legacy --credentials-stdin "${sandbox_args[@]}")
    if [[ -f "$RUNTIME/waiver.json" ]]; then
        mkdir -m 0700 -- "$RUN_DIR/input"
        install -m 0400 -o "$RUN_UID" -g "$RUN_GID" -- "$RUNTIME/waiver.json" "$RUN_DIR/input/waiver.json"
        chown "$RUN_UID:$RUN_GID" -- "$RUN_DIR/input"
        args+=(--waiver /out/input/waiver.json)
    fi
    "$PYTHON" -I -B "$ENTRY" hostcheck legacy-credentials |
        compose_run crm-migrate "$mode" "${args[@]}" "$@" || rc=$?
    after="$(legacy_require legacy-fingerprint)" || after="unavailable"
    if [[ "$before" != "$after" ]]; then
        printf 'migrate.sh: FAILED: the legacy env file changed during the run (sha256 or mtime)\n' >&2
        [[ "$rc" -ne 0 ]] || rc=22
    else
        printf 'migrate.sh: legacy env file unchanged (sha256 and mtime equal before and after)\n'
    fi
    finish "$RUN_DIR" "$RUN_DIR/run" "$rc"
}

# ------------------------------------------------------------------ subcommands
cmd_selftest() {
    local args=()
    case "${1:-}" in
        "") ;;
        --quick) args+=(--quick) ;;
        *) usage ;;
    esac
    [[ $# -le 1 ]] || usage
    run_container crm-migrate-selftest selftest "${args[@]}"
}

cmd_live() {
    local mode="$1"
    shift
    local args=()
    if [[ "$mode" == extract ]]; then
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --passes | --overlap-minutes)
                    [[ $# -ge 2 && "$2" =~ ^[0-9]{1,4}$ ]] || usage
                    args+=("$1" "$2")
                    shift 2
                    ;;
                *) usage ;;
            esac
        done
    else
        [[ $# -eq 0 ]] || usage
    fi
    if [[ "$auth" == soap-legacy ]]; then
        require env-file "$ENV_EXAMPLE_LEGACY"
        run_legacy "$mode" "${args[@]}"
    fi
    require_env_file
    run_container crm-migrate "$mode" "${args[@]}"
}

cmd_reconcile() {
    [[ $# -ge 1 && $# -le 2 ]] || usage
    local id
    for id in "$@"; do
        require run-id "$id"
        [[ "$id" == *-extract ]] || die "reconcile inputs must be extract snapshots"
        [[ -d "$SNAPSHOTS/$id" && ! -L "$SNAPSHOTS/$id" ]] || die "snapshot not found"
        require sealed "$SNAPSHOTS/$id"
        require verify-manifest "$SNAPSHOTS/$id"
    done
    command -v docker >/dev/null || die "docker is required"
    new_run_dir reconcile
    # Temporary input copy inside the root-only tree, readable by the run UID only for
    # the duration of the run, then removed before sealing.
    mkdir -m 0700 -- "$RUN_DIR/input"
    cp -R -P -- "$SNAPSHOTS/$1" "$RUN_DIR/input/current"
    local args=(--snapshot /out/input/current --out /out/report)
    if [[ $# -eq 2 ]]; then
        cp -R -P -- "$SNAPSHOTS/$2" "$RUN_DIR/input/previous"
        args+=(--previous /out/input/previous)
    fi
    chown -R --no-dereference "$RUN_UID:$RUN_GID" -- "$RUN_DIR/input"
    local rc=0
    # Reconcile needs no Salesforce access: it runs in the network-less, secret-less service.
    compose_run crm-migrate-selftest reconcile "${args[@]}" || rc=$?
    rm -rf --one-file-system -- "$RUN_DIR/input"
    finish "$RUN_DIR" "$RUN_DIR/report" "$rc"
}

cmd_credentials() {
    [[ $# -eq 0 ]] || usage
    [[ -t 0 ]] || die "credentials must be entered interactively on a terminal"
    local origin client_id client_secret api_version
    local origin_re='^https://[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.sandbox)?\.my\.salesforce\.com$'
    local id_re='^[A-Za-z0-9._]{16,256}$'
    local secret_re='^[A-Za-z0-9._~+/=-]{16,512}$'
    local version_re='^[0-9]{2,3}\.[0-9]$'
    read -rs -p "My Domain origin (https://<mydomain>.my.salesforce.com): " origin
    printf '\n' >&2
    [[ "$origin" =~ $origin_re ]] || die "origin must be https://<mydomain>[.sandbox].my.salesforce.com"
    read -rs -p "Consumer key: " client_id
    printf '\n' >&2
    [[ "$client_id" =~ $id_re ]] || die "consumer key has an unexpected format"
    read -rs -p "Consumer secret: " client_secret
    printf '\n' >&2
    [[ "$client_secret" =~ $secret_re ]] || die "consumer secret has an unexpected format"
    read -rs -p "REST API version (NN.N, as confirmed at L1): " api_version
    printf '\n' >&2
    [[ "$api_version" =~ $version_re ]] || die "API version must look like NN.N"
    CRED_TMP="$(mktemp -p "$RUNTIME" .env.XXXXXXXX)"
    trap 'rm -f -- "$CRED_TMP"' EXIT
    chmod 0600 -- "$CRED_TMP"
    chown root:root -- "$CRED_TMP"
    # printf is a shell builtin: the values never appear in any process argument list.
    {
        printf 'CRM_SF_ORIGIN=%s\n' "$origin"
        printf 'CRM_SF_CLIENT_ID=%s\n' "$client_id"
        printf 'CRM_SF_CLIENT_SECRET=%s\n' "$client_secret"
        printf 'CRM_SF_API_VERSION=%s\n' "$api_version"
    } >"$CRED_TMP"
    mv -T -f -- "$CRED_TMP" "$ENV_FILE"
    trap - EXIT
    CRED_TMP=""
    require_env_file
    printf 'migrate.sh: wrote %s (root:root 0600; values not shown)\n' "$ENV_FILE"
}

[[ "$auth" == client-credentials || "$sub" == contract-check || "$sub" == count || "$sub" == extract ]] ||
    die "--auth soap-legacy applies to contract-check, count and extract only"
case "$sub" in
    selftest) cmd_selftest "$@" ;;
    contract-check | count | extract) cmd_live "$sub" "$@" ;;
    reconcile) cmd_reconcile "$@" ;;
    credentials) cmd_credentials "$@" ;;
    *) usage ;;
esac
