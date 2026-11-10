#!/usr/bin/env bash
# Build the release bundle crm-release-<shortsha>.tar.gz from an accepted commit
# (reachable from main) of this repository: git archive plus RELEASE.json.
# Reproducible byte for byte; see scripts/release.py and docs/RELEASE.md.
# Usage: scripts/release.sh <commit> [output directory]
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
commit=${1:-}
[ -n "$commit" ] || { echo "usage: $(basename "$0") <commit> [output directory]" >&2; exit 2; }
out=${2:-.}
[ -d "$out" ] || { echo "$(basename "$0"): output directory missing: $out" >&2; exit 1; }
umask 022
exec python3 -I "$repo/scripts/release.py" build "$commit" --repo "$repo" --out "$out"
