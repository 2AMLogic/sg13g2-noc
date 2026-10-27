#!/usr/bin/env bash
# Fast freshness test for the committed mesh netlist (issue #24), no synthesis run.
# Exit 0 only if (1) every RTL source still hashes to what layout/mesh/netlist/sources.sha256
# recorded when the netlist was generated, and (2) the committed netlist is the exact bytes
# klt reported (netlist_sha256 in layout/mesh/reports/synthesize.json).
# The authoritative regeneration test is layout/mesh/run.sh --check.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 2
M=layout/mesh
sha256sum --quiet -c "$M/netlist/sources.sha256" || { echo "check.sh: RTL changed since the netlist was generated; run layout/mesh/run.sh" >&2; exit 3; }
want="$(jq -r .netlist_sha256 "$M/reports/synthesize.json")"
got="$(sha256sum "$M/netlist/noc_mesh.v" | cut -d' ' -f1)"
[ "$want" = "$got" ] || { echo "check.sh: netlist does not match its synthesis report" >&2; exit 3; }
