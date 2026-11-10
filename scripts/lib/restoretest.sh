# shellcheck shell=bash
# CRM-007 restore test: restore a crm-beta backup into the throwaway Compose
# project crm-beta-restoretest, print record-count fingerprints, tear it down.
# Sourced by restore.sh after lib/common.sh and `require_target beta`.
# Source, do not run.
#
# Isolation (each is a guard below, unit-tested in tests/unit/test_beta.py):
# - the project name, the Compose file and the runtime path are constants,
#   never derived from input; the runtime path's parent must be exactly
#   /srv/CRM/runtime. A test-only override (another directory named
#   beta-restoretest) is allowed only under the tmp root /tmp, as a sibling of
#   $CRM_RUNTIME_DIR;
# - deploy/beta/restoretest/compose.json must pass the isolation policy
#   (`check_access.py restoretest`): one crm-db, no published or exposed port,
#   no bind mount, its own project-scoped volume and internal network;
# - every docker call goes through rt_compose, which always passes
#   `-p crm-beta-restoretest -f <restoretest compose>`; nothing here calls
#   compose() (the crm-beta project) or names crm-beta/crm-dev resources;
# - teardown is `down -v` of crm-beta-restoretest only, then removal of the
#   restore-test runtime directory, re-checked by name first.

CRM_RT_PROJECT=crm-beta-restoretest
CRM_RT_COMPOSE_FILE=$CRM_REPO_DIR/deploy/beta/restoretest/compose.json
CRM_RT_DEFAULT_DIR=/srv/CRM/runtime/beta-restoretest
CRM_RT_PARENT=/srv/CRM/runtime
CRM_RT_TEST_ROOT=/tmp
CRM_RT_SECRET_NAME=CRM_RESTORETEST_DB_ROOT_PASSWORD
# The EspoCRM tables fingerprinted (live rows, deleted = 0).
CRM_RT_TABLES=(account contact opportunity call meeting task email user team role)

rt_refuse() {
    echo "$(basename "$0"): refusing to run the restore test: $*" >&2
    exit 2
}

# All guards, before anything touches the host or Docker.
rt_guard() {
    local parent
    [ "$CRM_TARGET" = beta ] && [ "$CRM_PROJECT" = crm-beta ] \
        || rt_refuse "the restore test is for crm-beta backups only"
    case "$CRM_RT_PROJECT" in
        crm-beta-restoretest) ;;
        *) rt_refuse "project name is not crm-beta-restoretest: $CRM_RT_PROJECT" ;;
    esac
    [ "$CRM_RT_PROJECT" != "$CRM_PROJECT" ] && [ "$CRM_RT_PROJECT" != crm-dev ] \
        || rt_refuse "the restore-test project must differ from crm-beta and crm-dev"
    [ "$CRM_RT_COMPOSE_FILE" = "$CRM_REPO_DIR/deploy/beta/restoretest/compose.json" ] \
        && [ "$CRM_RT_COMPOSE_FILE" != "$CRM_COMPOSE_FILE" ] \
        || rt_refuse "unexpected restore-test Compose file: $CRM_RT_COMPOSE_FILE"
    CRM_RT_DIR=${CRM_RESTORETEST_DIR:-$CRM_RT_DEFAULT_DIR}
    [ "$(basename -- "$CRM_RT_DIR")" = beta-restoretest ] \
        || rt_refuse "runtime directory is not named beta-restoretest: $CRM_RT_DIR"
    case "$CRM_RT_DIR" in
        /*) ;;
        *) rt_refuse "runtime directory must be an absolute path: $CRM_RT_DIR" ;;
    esac
    parent=$(dirname -- "$CRM_RT_DIR")
    case "$parent" in
        "$CRM_RT_PARENT") ;;
        "$CRM_RT_TEST_ROOT"/*)
            # Test-only override: under the tmp root, next to the (test) beta runtime.
            [ "$parent" = "$(dirname -- "$CRM_RUNTIME_DIR")" ] \
                || rt_refuse "a test override of $CRM_RT_DIR must sit next to $CRM_RUNTIME_DIR"
            ;;
        *) rt_refuse "the parent of $CRM_RT_DIR must be exactly $CRM_RT_PARENT" ;;
    esac
    [ "$(realpath -e -- "$parent" 2>/dev/null)" = "$parent" ] \
        || rt_refuse "the parent of $CRM_RT_DIR must exist and be canonical (no symlink)"
    case "$CRM_RT_DIR/" in
        "$CRM_RUNTIME_DIR"/*) rt_refuse "$CRM_RT_DIR is inside the crm-beta runtime" ;;
    esac
    case "$CRM_RUNTIME_DIR/" in
        "$CRM_RT_DIR"/*) rt_refuse "the crm-beta runtime is inside $CRM_RT_DIR" ;;
    esac
    if [ -e "$CRM_RT_DIR" ] || [ -L "$CRM_RT_DIR" ]; then
        rt_refuse "$CRM_RT_DIR already exists (another restore test, or a killed one: run" \
            "'docker compose -p $CRM_RT_PROJECT -f $CRM_RT_COMPOSE_FILE down -v' and remove it)"
    fi
    [ -z "${!CRM_RT_SECRET_NAME+set}" ] \
        || rt_refuse "$CRM_RT_SECRET_NAME is set in the environment; unset it"
    python3 -I "$CRM_REPO_DIR/scripts/check_access.py" restoretest \
        || rt_refuse "deploy/beta/restoretest/compose.json failed the isolation policy"
}

# docker compose for crm-beta-restoretest only. No beta env-file name reaches it.
rt_compose() {
    local name unset=()
    [ "$CRM_RT_PROJECT" = crm-beta-restoretest ] || rt_refuse "rt_compose: wrong project"
    for name in "${CRM_ENV_NAMES[@]}"; do
        unset+=(-u "$name")
    done
    env "${unset[@]}" docker compose -p "$CRM_RT_PROJECT" -f "$CRM_RT_COMPOSE_FILE" \
        --env-file "$CRM_RT_DIR/env" "$@"
}

# Removes crm-beta-restoretest's containers, network and volume, then its
# runtime directory. Touches nothing else. Returns non-zero if any step failed.
rt_teardown() {
    local rc=0
    [ "$CRM_RT_PROJECT" = crm-beta-restoretest ] || rt_refuse "teardown: wrong project"
    [ "$(basename -- "${CRM_RT_DIR:-}")" = beta-restoretest ] || rt_refuse "teardown: wrong directory"
    echo "tearing down $CRM_RT_PROJECT"
    if [ -f "$CRM_RT_DIR/env" ]; then
        rt_compose down -v --remove-orphans --timeout 10 || rc=1
    fi
    rm -rf -- "$CRM_RT_DIR" || rc=1
    return "$rc"
}

# rt_count <table>: live rows, or "missing" if the query fails.
rt_count() {
    local n
    n=$(rt_compose exec -T crm-db sh -c \
        'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" exec mariadb -uroot -N -B "$MARIADB_DATABASE" -e "$1"' \
        sh "SELECT COUNT(*) FROM \`$1\` WHERE deleted = 0" 2>/dev/null) || n=
    case "$n" in
        ''|*[!0-9]*) echo missing ;;
        *) echo "$n" ;;
    esac
}

# rt_run <verified backup directory>
rt_run() {
    local backup=$1 dir table n start missing=0
    start=$(date +%s)
    umask 077
    mkdir -m 0700 -- "$CRM_RT_DIR" || rt_refuse "cannot create $CRM_RT_DIR"
    trap 'rt_teardown || echo "$(basename "$0"): teardown of $CRM_RT_PROJECT failed" >&2' EXIT
    # A throwaway root password: generated here, only in this 0600 file, never printed.
    printf '%s=%s\n' "$CRM_RT_SECRET_NAME" "$(od -An -tx1 -N32 /dev/urandom | tr -d ' \n')" \
        > "$CRM_RT_DIR/env"

    mkdir -m 0700 -- "$CRM_RT_DIR/files"
    for dir in "${CRM_PERSISTENT_DIRS[@]}"; do
        tar -C "$CRM_RT_DIR/files" -xzf "$backup/$(archive_for "$dir")" \
            || die "restore test: $(archive_for "$dir") did not unpack"
        [ -d "$CRM_RT_DIR/files/$dir" ] || die "restore test: $(archive_for "$dir") holds no $dir"
    done

    rt_compose up -d --wait crm-db
    gunzip -c "$backup/db.sql.gz" | rt_compose exec -T crm-db sh -c \
        'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" exec mariadb -uroot "$MARIADB_DATABASE"' \
        || die "restore test: the database dump did not load"

    echo "restore test fingerprint ($(basename -- "$backup")):"
    for table in "${CRM_RT_TABLES[@]}"; do
        n=$(rt_count "$table")
        echo "  table $table: $n"
        [ "$n" != missing ] || missing=$((missing + 1))
    done
    for dir in "${CRM_PERSISTENT_DIRS[@]}"; do
        n=$(find "$CRM_RT_DIR/files/$dir" -type f | wc -l)
        echo "  files $dir: $n"
    done

    trap - EXIT
    rt_teardown || die "restore test: teardown of $CRM_RT_PROJECT failed"
    [ "$missing" -eq 0 ] \
        || die "restore test FAILED: $missing table count(s) missing; $CRM_RT_PROJECT removed"
    echo "restore test completed in $(( $(date +%s) - start ))s; $CRM_RT_PROJECT removed"
}
