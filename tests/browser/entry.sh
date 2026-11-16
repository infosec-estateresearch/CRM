#!/usr/bin/env bash
# CRM-CLIENT-001R2 annex B3: container entry point. Runs as uid 65534 in the hardened
# runner (read-only rootfs, no capabilities, internal network). Order:
#   1. offline, hash-locked install of the two wheels into tmpfs (annex B2);
#   2. isolation probe: a hard gate before any journey (annex B4);
#   3. journeys.py: the pre-launch gate first (binary sha256 and ldd of the browser and of the
#      Node driver, libatomic.so.1 included; nothing is started if it fails), then identity checks,
#      the compatibility probe and journeys J1-J5 (annex B2.3, B5, B6).
# The operator-side deploy steps between journeys use the control files that
# journeys.py documents. Configuration comes only from the environment; missing
# values fail loudly. Never run this on the host.
set -Eeuo pipefail

: "${CRM_BROWSER_BASE_URL:?CRM_BROWSER_BASE_URL is required}"
: "${CRM_BROWSER_USERNAME:?CRM_BROWSER_USERNAME is required (env file)}"
: "${CRM_BROWSER_PASSWORD:?CRM_BROWSER_PASSWORD is required (env file)}"

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
evidence=${CRM_EVIDENCE_DIR:-/evidence}
[ -d "$evidence" ] && [ -w "$evidence" ] || { echo "entry.sh: $evidence is not a writable directory" >&2; exit 2; }

# 1. offline install; pip has no route to any index (--no-index) and refuses unhashed files.
python3 -m pip install --no-index --find-links /wheels --require-hashes --only-binary=:all: \
    --no-deps --target /tmp/pydeps -r "$here/requirements.lock"

# PYTHONPATH carries the install; -I and -E would ignore it, so they are not used.
export PYTHONPATH=/tmp/pydeps
py() { python3 -s -B "$@"; }

# 2. isolation proof first. Targets are data supplied by the operator.
py "$here/probe_isolation.py" --targets "$evidence/probe-targets.json" --out "$evidence/isolation.json"

# 3. identity, compatibility probe, journeys.
exec python3 -s -B "$here/journeys.py" --base-url "$CRM_BROWSER_BASE_URL" --out "$evidence"
