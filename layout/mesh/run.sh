#!/usr/bin/env bash
# Regenerate the 2 x 2 mesh gate-level netlist (issue #24):
#   klt synthesize layout/mesh/requests/synthesize.json
# and commit-ready outputs:
#   layout/mesh/reports/synthesize.json   klt envelope
#   layout/mesh/netlist/noc_mesh.v        the generated netlist (never hand-edited)
#   layout/mesh/netlist/sources.sha256    sha256 of every RTL source the netlist came from
#
# Usage:  layout/mesh/run.sh            regenerate and overwrite the committed files
#         layout/mesh/run.sh --check    re-synthesize into scratch and compare; exit 3 if stale
# Needs:  yosys at the version in layout/tools.json; uvx (klt is fetched pinned, never
#         installed); jq. PDK_ROOT defaults to ~/share/pdk. A synthesis takes minutes.
# For the fast hash-only freshness test see layout/mesh/check.sh.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MESH="$ROOT/layout/mesh"
export PDK_ROOT="${PDK_ROOT:-$HOME/share/pdk}"
export PDK="$(jq -r .variant "$ROOT/layout/pdk.json")"
KLT_VER="$(jq -r .klayout_tools.version "$ROOT/layout/tools.json")"
klt() { uvx --quiet --from "klayout-tools==$KLT_VER" klt "$@"; }
die() { echo "run.sh: $*" >&2; exit 2; }

mode=write
case "${1:-}" in "") ;; --check) mode=check ;; *) die "usage: run.sh [--check]" ;; esac

want="$(jq -r .yosys.version_prefix "$ROOT/layout/tools.json")"
got="$(yosys -V 2>&1 | head -1)"
case "$got" in "$want"*) ;; *) die "yosys mismatch: pinned '$want', found '$got' (worker-spec gap; do not install here)";; esac

cd "$ROOT" || exit 2
rm -rf "$MESH/requests/.klt"
tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
klt synthesize "$MESH/requests/synthesize.json" --format json > "$tmp" || { cat "$tmp" >&2; die "klt synthesize failed"; }
net="$MESH/requests/.klt/synthesize/mesh/noc_mesh_synth.v"
[ -s "$net" ] || die "no netlist produced"

if [ "$mode" = check ]; then
  rc=0
  cmp -s "$net" "$MESH/netlist/noc_mesh.v" || { echo "run.sh: committed netlist differs from a fresh synthesis" >&2; rc=3; }
  exit $rc
fi

mkdir -p "$MESH/reports" "$MESH/netlist"
cp "$tmp" "$MESH/reports/synthesize.json"
cp "$net" "$MESH/netlist/noc_mesh.v"
( cd "$ROOT" && sha256sum rtl/noc_mesh.v rtl/noc_tile.v rtl/noc_router.v rtl/noc_tgen.v rtl/noc_tchk.v rtl/noc_payload.vh ) > "$MESH/netlist/sources.sha256"
jq -r '"synthesize: \(.status) cells=\(.instance_count) area_um2=\(.area_um2)"' "$MESH/reports/synthesize.json"
