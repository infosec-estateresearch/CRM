#!/usr/bin/env bash
# Clean-host deploy of a release bundle into crm-beta (CRM-007, PBI-017).
# Run as root at the operator stage. --sha256 HEX (the bundle digest from the
# release record) is mandatory: RELEASE.json sits inside the bundle and is not
# signed, so only that outside digest anchors it. Without a well-formed
# --sha256 the script stops before step 1 (no docker call, no deploy dir).
# In order, any failure stops the deploy:
#  1. copy the bundle into a root-only private temp file, check the copy's
#     sha256 against --sha256, verify that same copy (scripts/release.py
#     verify --sha256); every later step uses only the copy;
#  2. refuse a non-empty beta runtime unless --upgrade: "empty" means nothing
#     but the operator's env file (root, 0600) is in /srv/CRM/runtime/beta;
#  3. unpack the copy into /srv/CRM/deploy/<shortsha> (a constant; the deploy
#     root and an existing <shortsha> must be root-owned and not group- or
#     other-writable), root-owned and read-only,
#     after re-checking every unpacked file against RELEASE.json (release.py
#     verify-tree: no extra, missing or changed file); with --upgrade and an
#     existing /srv/CRM/deploy/<shortsha>, that tree is re-checked the same way
#     and any difference or extra file refuses the deploy;
#  4. create the runtime (root 0700: db, data, custom, client/custom, backups);
#  5. from the unpacked release: check_access.py beta --render (edge config),
#     then the validated CRM_BETA_MODE (check_access.py beta --mode, CRM-009) is
#     printed (the mode only, never an address), up.sh beta, deploy_custom.sh beta;
#  6. siteUrl := CRM_SITE_URL (--type=string) and phoneNumberInternational :=
#     false (--type=bool; config:set defaults to --type=string, CRM-009-F) via
#     bin/command config:set, then read phoneNumberInternational back: anything
#     but exactly the PHP boolean false fails the deploy (the CRM-006S load
#     precondition);
#  7. provision access (CRM-003) and run the beta-safe acceptance suite
#     (read-only, GET only). Both are mandatory (CRM-007R): the script refuses
#     to start without CRM_ADMIN_USERNAME, CRM_ADMIN_PASSWORD,
#     CRM_PROVISION_KEY_FILE (and CRM_BETA_SAFE_KEY_FILE with --upgrade). The
#     base URL is never operator input: it is http://127.0.0.1:<CRM_BETA_APP_PORT>
#     from the checked beta env file;
#  8. write a sanitised deploy report (no secrets, no addresses) to
#     /srv/CRM/runtime/beta/deploy-report-<stamp>.json.
# Never seeds synthetic data.
#
# Every step is a function, so tests/unit/test_beta.py can source this file
# (nothing runs when sourced) and drive one step with stubbed docker/python3.
# Usage: scripts/deploy_release.sh beta <bundle> --sha256 HEX [--upgrade]
set -euo pipefail
# shellcheck source=lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

# Bundle verification, from the checkout running this script (never from the
# bundle itself, which is not yet trusted).
# verify_bundle <bundle> <sha256> <private dir>: copies the bundle into the
# root-only private directory (0700, file 0600), checks the copy's sha256 and
# verifies that same copy. Prints the copy's path; later steps read only it.
verify_bundle() {
    local bundle=$1 sha=$2 dir=$3 copy got
    [ -f "$bundle" ] && [ ! -L "$bundle" ] || die "refusing to deploy: not a regular file: $bundle"
    [ -d "$dir" ] && [ ! -L "$dir" ] && [ "$(stat -c '%a' -- "$dir")" = 700 ] \
        || die "refusing to deploy: the private staging directory is not 0700: $dir"
    copy="$dir/$(basename -- "$bundle")"
    (umask 077 && cp -- "$bundle" "$copy") || die "refusing to deploy: cannot copy the bundle"
    chmod 0600 -- "$copy"
    got=$(sha256sum < "$copy" | cut -d" " -f1)
    [ "$got" = "$sha" ] || die "refusing to deploy: the bundle's sha256 does not match --sha256"
    python3 -I "$CRM_REPO_DIR/scripts/release.py" verify "$copy" --sha256 "$sha" >&2 \
        || die "refusing to deploy: the bundle failed verification"
    echo "$copy"
}

# verify_tree <dir> <bundle copy> <sha256>: exactly the bundle's files.
verify_tree() {
    python3 -I "$CRM_REPO_DIR/scripts/release.py" verify-tree "$1" "$2" --sha256 "$3" >&2
}

# The runtime holds only the operator's env file (root, 0600) unless --upgrade.
check_runtime_empty() {
    local upgrade=$1 others
    [ -d "$CRM_RUNTIME_DIR" ] && [ ! -L "$CRM_RUNTIME_DIR" ] \
        || die "refusing to deploy: $CRM_RUNTIME_DIR must exist (root 0700) and hold the env file"
    [ "$(stat -c '%u %a' -- "$CRM_RUNTIME_DIR")" = "0 700" ] \
        || die "refusing to deploy: $CRM_RUNTIME_DIR must be owned by root with mode 0700"
    [ -f "$CRM_RUNTIME_DIR/env" ] && [ ! -L "$CRM_RUNTIME_DIR/env" ] \
        && [ "$(stat -c '%u %a' -- "$CRM_RUNTIME_DIR/env")" = "0 600" ] \
        || die "refusing to deploy: $CRM_RUNTIME_DIR/env must be a regular file, root, mode 0600"
    others=$(find "$CRM_RUNTIME_DIR" -mindepth 1 -maxdepth 1 ! -name env | wc -l)
    if [ "$others" -ne 0 ] && [ -z "$upgrade" ]; then
        die "refusing to deploy: $CRM_RUNTIME_DIR is not empty ($others entries besides env); use --upgrade"
    fi
}

# require_root_owned <dir>: a real directory owned by uid 0 and not group- or
# other-writable (CRM-007R: the deploy root, and an existing release before
# verify-tree on --upgrade).
require_root_owned() {
    local dir=$1 owner mode
    [ -d "$dir" ] && [ ! -L "$dir" ] || die "refusing to deploy: not a real directory: $dir"
    read -r owner mode < <(stat -c '%u %a' -- "$dir")
    [ "$owner" = 0 ] || die "refusing to deploy: $dir must be owned by root (uid $owner)"
    (( (8#$mode & 8#022) == 0 )) || die "refusing to deploy: $dir is group- or other-writable (mode $mode)"
}

# unpack_release <bundle copy> <short> <upgrade> <sha256>: prints the release directory.
unpack_release() {
    local bundle=$1 short=$2 upgrade=$3 sha=$4 dest staging
    dest="$CRM_DEPLOY_ROOT/$short"
    umask 022
    mkdir -p -- "$CRM_DEPLOY_ROOT"
    require_root_owned "$CRM_DEPLOY_ROOT"
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        [ -n "$upgrade" ] || die "refusing to deploy: $dest already exists"
        require_root_owned "$dest"
        verify_tree "$dest" "$bundle" "$sha" \
            || die "refusing to deploy: the existing $dest differs from the bundle's RELEASE.json"
    else
        staging=$(umask 077 && mktemp -d "$CRM_DEPLOY_ROOT/.unpack-XXXXXX")
        tar -xzf "$bundle" -C "$staging" --no-same-owner --no-same-permissions
        if [ "$(ls -A -- "$staging")" != "crm-release-$short" ] \
                || ! verify_tree "$staging/crm-release-$short" "$bundle" "$sha"; then
            chmod -R u+w -- "$staging"
            rm -rf -- "$staging"
            die "refusing to deploy: the unpacked files differ from the bundle's RELEASE.json"
        fi
        chmod 0755 -- "$staging"
        mv -T -- "$staging/crm-release-$short" "$dest"
        rmdir -- "$staging"
        chown -R 0:0 -- "$dest"
        chmod -R a-w -- "$dest"
    fi
    echo "$dest"
}

make_runtime() {
    local d
    umask 077
    for d in db data custom client client/custom backups; do
        [ -e "$CRM_RUNTIME_DIR/$d" ] || mkdir -m 0700 -- "$CRM_RUNTIME_DIR/$d"
    done
    chmod 0700 -- "$CRM_RUNTIME_DIR/backups"
}

# run_clean <command...>: runs it without any beta env-file name in its
# environment. The operator exports CRM_ADMIN_USERNAME/PASSWORD for step 7, and
# up.sh/deploy_custom.sh refuse to run while an env-file name is set.
run_clean() {
    local name unset=()
    for name in "${CRM_BETA_ENV_NAMES[@]}"; do
        unset+=(-u "$name")
    done
    env "${unset[@]}" "$@"
}

# 5a. Render the edge configuration from the release; fail closed.
render_edge() {
    local dest=$1
    CRM_RUNTIME_DIR=$CRM_RUNTIME_DIR run_clean python3 -I "$dest/scripts/check_access.py" beta --render \
        || die "refusing to deploy: the edge settings failed scripts/check_access.py beta"
}

# 5a'. deploy_mode <release dir>: prints the validated CRM_BETA_MODE (production
# or uat), from the checked env file; fail closed.
deploy_mode() {
    local dest=$1
    CRM_RUNTIME_DIR=$CRM_RUNTIME_DIR run_clean python3 -I "$dest/scripts/check_access.py" beta --mode \
        || die "refusing to deploy: CRM_BETA_MODE failed scripts/check_access.py beta --mode"
}

# 5b. Start the stack and deploy the customisation, from the release.
start_stack() {
    local dest=$1
    CRM_RUNTIME_DIR=$CRM_RUNTIME_DIR run_clean bash "$dest/scripts/up.sh" beta
    CRM_RUNTIME_DIR=$CRM_RUNTIME_DIR run_clean bash "$dest/scripts/deploy_custom.sh" beta
}

# check_phone_value <php var_export output>: only the PHP boolean false passes.
# var_export prints false for the boolean and 'false' (quoted) for the string,
# so the string "false", 0, NULL or a missing key all fail.
check_phone_value() {
    [ "$1" = false ] || die "phoneNumberInternational read back as '$1', not exactly false"
}

# 6. siteUrl and phoneNumberInternational, then the read-back. config:set
# defaults to --type=string, which stores the string 'false' (CRM-009-F), so the
# boolean needs --type=bool.
configure_site() {
    local dest=$1 site_url got
    # shellcheck source=lib/common.sh
    . "$dest/scripts/lib/common.sh"
    require_target beta
    site_url=$(sed -n 's/^CRM_SITE_URL=//p' -- "$CRM_ENV_FILE")
    [ -n "$site_url" ] || die "CRM_SITE_URL is not set in $CRM_ENV_FILE"
    compose exec -T -u www-data -w /var/www/html crm-app php bin/command config:set siteUrl "$site_url" --type=string
    compose exec -T -u www-data -w /var/www/html crm-app php bin/command config:set phoneNumberInternational false --type=bool
    # Read data/config.php back with php -r (PL decision, CRM-007 r2): var_export
    # tells the boolean false apart from the string 'false'.
    got=$(compose exec -T -u www-data -w /var/www/html crm-app php -r \
        '$c = include "data/config.php"; echo var_export($c["phoneNumberInternational"] ?? null, true);')
    check_phone_value "$got"
}

# run_beta_safe <release dir>: the read-only suite in-process; it must run all
# its tests (a skip counts as a failure).
run_beta_safe() {
    local dest=$1
    python3 -I -B -c '
import sys, unittest
sys.path.insert(0, sys.argv[1] + "/tests/acceptance")
import test_beta_safe
suite = unittest.defaultTestLoader.loadTestsFromModule(test_beta_safe)
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() and not result.skipped and result.testsRun > 0 else 1)
' "$dest"
}

# CRM-007R: a deploy completes only when provisioning and acceptance both ran,
# so it refuses to start without their inputs: CRM_ADMIN_USERNAME,
# CRM_ADMIN_PASSWORD, CRM_PROVISION_KEY_FILE (a new file for the API key) and,
# with --upgrade (the API user already exists, so no new key is written),
# CRM_BETA_SAFE_KEY_FILE naming an existing key file. No CRM_BASE_URL: it is
# derived. There is no skip and no bypass.
# require_deploy_inputs <upgrade>
require_deploy_inputs() {
    local upgrade=$1 name
    for name in CRM_ADMIN_USERNAME CRM_ADMIN_PASSWORD CRM_PROVISION_KEY_FILE; do
        [ -n "${!name:-}" ] \
            || die "refusing to deploy: $name is required (access provisioning and beta-safe acceptance are mandatory)"
    done
    if [ -n "$upgrade" ] || [ -n "${CRM_BETA_SAFE_KEY_FILE:-}" ]; then
        [ -n "${CRM_BETA_SAFE_KEY_FILE:-}" ] && [ -f "$CRM_BETA_SAFE_KEY_FILE" ] \
            && [ ! -L "$CRM_BETA_SAFE_KEY_FILE" ] \
            || die "refusing to deploy: CRM_BETA_SAFE_KEY_FILE must name an existing API key file (required with --upgrade)"
    else
        [ ! -e "$CRM_PROVISION_KEY_FILE" ] && [ ! -L "$CRM_PROVISION_KEY_FILE" ] \
            || die "refusing to deploy: CRM_PROVISION_KEY_FILE must not exist yet (provisioning writes the new key there); for an existing API user set CRM_BETA_SAFE_KEY_FILE"
    fi
}

# 7. Access and beta-safe acceptance (operator-supplied credentials only).
# Sets PROVISIONED and ACCEPTANCE for the report.
provision_and_accept() {
    local dest=$1 url
    PROVISIONED=failed ACCEPTANCE=failed
    require_deploy_inputs "${2:-}"
    # The base URL is never taken from the operator: it is beta's loopback URL,
    # read from the checked beta env file (check_access.py beta --base-url).
    url=$(python3 -I "$CRM_REPO_DIR/scripts/check_access.py" beta --base-url) \
        || die "cannot determine the beta base URL from $CRM_RUNTIME_DIR/env"
    export CRM_BASE_URL=$url
    python3 -B "$dest/scripts/provision_access.py" beta --key-file "$CRM_PROVISION_KEY_FILE" >/dev/null \
        || die "access provisioning failed"
    PROVISIONED=done
    # The key: CRM_BETA_SAFE_KEY_FILE if given, else the file provisioning just
    # wrote (only a newly created API user gets one).
    CRM_BETA_SAFE_KEY_FILE=${CRM_BETA_SAFE_KEY_FILE:-$CRM_PROVISION_KEY_FILE}
    [ -f "$CRM_BETA_SAFE_KEY_FILE" ] \
        || die "beta-safe acceptance needs an API key file: set CRM_BETA_SAFE_KEY_FILE (the API user already existed, so no new key was written)"
    # The role check reads Role as the admin (CRM-009-G): the credentials go in
    # through the environment only, never argv.
    CRM_ADMIN_USERNAME=$CRM_ADMIN_USERNAME CRM_ADMIN_PASSWORD=$CRM_ADMIN_PASSWORD \
    CRM_BETA_SAFE_KEY_FILE=$CRM_BETA_SAFE_KEY_FILE CRM_BETA_SAFE_MODE=${DEPLOY_MODE:-production} \
        run_beta_safe "$dest" \
        || die "beta-safe acceptance failed"
    ACCEPTANCE=passed
}

# 8. write_report <release dir> <bundle> <upgrade>: prints the report path.
write_report() {
    local dest=$1 bundle=$2 upgrade=$3 stamp report
    [ "${PROVISIONED:-}" = done ] && [ "${ACCEPTANCE:-}" = passed ] \
        || die "refusing to report success: provisioning is '${PROVISIONED:-unset}' and acceptance '${ACCEPTANCE:-unset}'"
    stamp=$(utc_stamp)
    report="$CRM_RUNTIME_DIR/deploy-report-$stamp.json"
    python3 -I -c '
import json, sys
keys = ("commit", "short", "images", "delivery_records")
m = {k: v for k, v in json.load(open(sys.argv[1])).items() if k in keys}
m.update(target="beta", project="crm-beta", stamp=sys.argv[2], upgrade=sys.argv[3] == "1",
         bundle_sha256=sys.argv[4], phoneNumberInternational=False,
         access=sys.argv[5], acceptance=sys.argv[6])
print(json.dumps(m, indent=2, sort_keys=True))
' "$dest/RELEASE.json" "$stamp" "${upgrade:-0}" "$(sha256sum < "$bundle" | cut -d" " -f1)" \
        "$PROVISIONED" "$ACCEPTANCE" > "$report"
    chmod 0600 -- "$report"
    echo "$report"
}

# CRM-007R: the deploy root is the constant /srv/CRM/deploy. The only seam is
# for tests: with CRM_TEST_ROOT (already checked by pin_beta_runtime: an
# existing canonical directory under /tmp) it is $CRM_TEST_ROOT/deploy.
# A CRM_DEPLOY_ROOT naming anything else is refused.
CRM_DEPLOY_ROOT_CONST=/srv/CRM/deploy
pin_deploy_root() {
    local want=$CRM_DEPLOY_ROOT_CONST
    if [ -n "${CRM_TEST_ROOT:-}" ]; then
        case "$CRM_TEST_ROOT" in
            /tmp/?*) want=$CRM_TEST_ROOT/deploy ;;
            *) die "refusing to run: CRM_TEST_ROOT must be under /tmp: $CRM_TEST_ROOT" ;;
        esac
    fi
    if [ -n "${CRM_DEPLOY_ROOT:-}" ] && [ "$CRM_DEPLOY_ROOT" != "$want" ]; then
        die "refusing to run: the deploy root is $want (CRM_DEPLOY_ROOT is $CRM_DEPLOY_ROOT)"
    fi
    CRM_DEPLOY_ROOT=$want
}

main() {
    local bundle upgrade= sha= short dest report copy
    [ "${1:-}" = beta ] || {
        echo "$(basename "$0"): refusing to run: target environment must be 'beta' (got '${1:-<none>}')" >&2
        exit 2
    }
    bundle=${2:-}
    [ -n "$bundle" ] || die "usage: $(basename "$0") beta <bundle> --sha256 HEX [--upgrade]"
    shift 2
    while [ $# -gt 0 ]; do
        case "$1" in
            --upgrade) upgrade=1 ;;
            --sha256) [ $# -ge 2 ] || die "--sha256 needs a value"; sha=$2; shift ;;
            *) die "unknown argument: $1" ;;
        esac
        shift
    done
    # The bundle's digest from the release record anchors it (RELEASE.json is
    # inside the bundle and unsigned): mandatory and well-formed, before step 1.
    [[ "$sha" =~ ^[0-9a-f]{64}$ ]] \
        || die "refusing to deploy: --sha256 HEX (64 lower-case hex digits, from the release record) is required"
    [ "$(id -u)" = 0 ] || die "refusing to run: deploy_release.sh must run as root"
    pin_beta_runtime  # /srv/CRM/runtime/beta (lib/common.sh)
    [ "$(basename "$CRM_RUNTIME_DIR")" = beta ] || {
        echo "$(basename "$0"): refusing to run: runtime directory is not a beta runtime: $CRM_RUNTIME_DIR" >&2
        exit 2
    }
    pin_deploy_root
    require_deploy_inputs "$upgrade"

    CRM_STAGE_DIR=$(umask 077 && mktemp -d "${TMPDIR:-/tmp}/crm-deploy-XXXXXX")
    trap 'rm -rf -- "$CRM_STAGE_DIR"' EXIT
    copy=$(verify_bundle "$bundle" "$sha" "$CRM_STAGE_DIR")  # 1
    short=$(basename "$bundle" .tar.gz); short=${short#crm-release-}
    check_runtime_empty "$upgrade"                           # 2
    dest=$(unpack_release "$copy" "$short" "$upgrade" "$sha")  # 3
    make_runtime                                             # 4
    load_env_names "$dest/deploy/beta/env.example"
    CRM_BETA_ENV_NAMES=("${CRM_ENV_NAMES[@]}")
    [ "${#CRM_BETA_ENV_NAMES[@]}" -gt 0 ] || die "no env-file names in the release's deploy/beta/env.example"
    export CRM_RUNTIME_DIR
    render_edge "$dest"                                      # 5
    DEPLOY_MODE=$(deploy_mode "$dest")
    echo "crm-beta mode: $DEPLOY_MODE"
    start_stack "$dest"
    configure_site "$dest"                                   # 6
    provision_and_accept "$dest" "$upgrade"                  # 7
    report=$(write_report "$dest" "$copy" "$upgrade")        # 8
    echo "deployed $short to crm-beta ($DEPLOY_MODE mode); report: $report"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
