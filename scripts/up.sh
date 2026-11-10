#!/usr/bin/env bash
# Start (or recreate) the crm-dev stack. This is the only supported way to run
# `up` (docs/BUILD.md §7.6). Before Compose is called it runs, in order:
# - the dev guard (the first argument must be exactly "dev");
# - the env-file and runtime path checks, which also refuse any env-file
#   variable set in the process environment (require_runtime_paths);
# - the LAN access check, scripts/check_access.py (require_access).
# Any failure exits non-zero before `up` runs. Then it runs
# `docker compose ... up -d --wait` with any further arguments appended, for
# example `--force-recreate crm-app`.
# Usage: scripts/up.sh dev [extra `up` arguments]
set -euo pipefail
# shellcheck source=lib/common.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

require_dev "${1:-}"
shift
require_env_file
require_runtime_paths
require_access

compose up -d --wait "$@"
