#!/usr/bin/env bash
# Start (or recreate) the crm-dev or crm-beta stack. This is the only supported way to run
# `up` (docs/BUILD.md §7.6). Before Compose is called it runs, in order:
# - the target guard (the first argument must be exactly "dev" or "beta");
# - the env-file and runtime path checks, which also refuse any env-file
#   variable set in the process environment (require_runtime_paths);
# - the LAN access check, scripts/check_access.py (require_access); for beta
#   with --render, which re-renders /srv/CRM/runtime/beta/edge/haproxy.cfg.
# Any failure exits non-zero before `up` runs. Then it runs
# `docker compose ... up -d --wait` with any further arguments appended, for
# example `--force-recreate crm-app`. If the beta edge configuration changed,
# it then force-recreates crm-beta-edge: the edge bind-mounts that one file,
# so a running edge would keep serving the replaced one.
# Usage: scripts/up.sh dev|beta [extra `up` arguments]
set -euo pipefail
# shellcheck source=lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

require_target "${1:-}"
shift
require_env_file
require_runtime_paths
if [ "$CRM_TARGET" = beta ]; then
    edge_before=$(edge_config_digest)
    require_access --render
    edge_after=$(edge_config_digest)
    [ -n "$edge_after" ] || die "the edge configuration was not rendered"
else
    require_access
fi

compose up -d --wait "$@"
if [ "$CRM_TARGET" = beta ] && [ "$edge_before" != "$edge_after" ]; then
    echo "edge configuration changed; recreating crm-beta-edge"
    compose up -d --wait --force-recreate --no-deps crm-beta-edge
fi
