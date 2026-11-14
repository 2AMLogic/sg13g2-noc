#!/usr/bin/env bash
# Regenerate the 2 x 2 mesh gate-level netlist (issue #24):
#   klt synthesize layout/mesh/requests/synthesize.json
# and commit-ready outputs:
#   layout/mesh/reports/synthesize.json   klt envelope
#   layout/mesh/netlist/noc_mesh.v        the generated netlist (never hand-edited)
#   layout/mesh/netlist/sources.sha256    sha256 of every RTL source the netlist came from
#
# Separately (--sta), the pre-route timing estimate of that committed netlist (issue #96):
#   klt sta layout/mesh/requests/sta-preroute.json
#   layout/mesh/reports/sta-preroute.json    klt envelope (geometry_source netlist_estimate)
# --sta never synthesizes and never writes the netlist; it reads the committed one, and refuses
# to run at all unless layout/mesh/check.sh says the committed netlist is still fresh.
#
# Usage:  layout/mesh/run.sh            regenerate and overwrite the committed files
#         layout/mesh/run.sh --check    re-synthesize into scratch and compare; exit 3 if stale
#         layout/mesh/run.sh --sta      pre-route STA of the committed netlist; no synthesis
# Needs:  yosys at the version in layout/tools.json; uvx (klt is fetched at the pinned version, never
#         installed); jq. --sta additionally needs openroad at its pinned version, the pinned PDK
#         under PDK_ROOT and python3, but not yosys. PDK_ROOT defaults to ~/share/pdk.
#         A synthesis takes minutes.
# For the fast hash-only freshness test see layout/mesh/check.sh.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MESH="$ROOT/layout/mesh"
. "$ROOT/layout/lib.sh"

require_klt

mode=write
case "${1:-}" in "") ;; --check) mode=check ;; --sta) mode=sta ;; *) die "usage: run.sh [--check|--sta]" ;; esac

if [ "$mode" = sta ]; then
  # A netlist-level estimate, not a post-route number: klt sta's verilog mode links the
  # structural netlist against liberty and times it on the clock constraint alone -- it never
  # places, routes or runs CTS -- and labels its own response geometry_source
  # "netlist_estimate". It drives openroad as a subprocess and resolves liberty from the PDK,
  # so this mode pin-checks both; synthesis needs neither, hence the split (see layout/lib.sh).
  check_pin openroad "$(jq -r .openroad.version "$ROOT/layout/tools.json")" "$(openroad -version 2>&1 | head -1)"
  stamp="$(klt pdk find --pdk "$PDK" 2>&1 | sed -n 's/^version: //p')"
  check_pin pdk "$(jq -r .klt_pdk_version_stamp "$ROOT/layout/pdk.json")" "$stamp"

  # Refuse to start unless the committed netlist is still the one its synthesis report
  # describes, so a committed estimate always describes the committed netlist.
  "$MESH/check.sh" || die "layout/mesh/check.sh failed (exit $?); the estimate would not describe the committed netlist"

  cd "$ROOT" || exit 2
  rm -rf "$MESH/requests/.klt/sta"
  mkdir -p "$MESH/reports"
  out="$MESH/reports/sta-preroute.json"
  tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
  # klt sta documents exit 0 and 1 only and deliberately has no exit 3 -- slack counts are data,
  # not a built-in gate. So this checks whether the run happened, never whether timing passed;
  # the slacks are read out of the JSON below and recorded in layout/README.md.
  klt sta "$MESH/requests/sta-preroute.json" --format json > "$tmp" || { cat "$tmp" >&2; die "klt sta failed"; }
  cp "$tmp" "$out"
  python3 -I "$ROOT/layout/smoke/sanitize.py" "$ROOT" "$PDK_ROOT" "$out"
  klt env-provenance lint-envelope "$out" || die "committed envelope carries absolute host paths"

  # The envelope records which netlist it describes itself, as
  # provenance.input.content_hash with role "netlist" -- so no second hash file is written
  # here. Assert it against the value check.sh asserts, so a committed report can never
  # describe bytes other than the committed netlist.
  want="$(jq -r .netlist_sha256 "$MESH/reports/synthesize.json")"
  got="$(jq -r '.provenance.input.content_hash | sub("^sha256:"; "")' "$out")"
  [ "$want" = "$got" ] || die "the STA envelope describes netlist $got, not the committed $want"

  jq -r '"sta: \(.status) geometry_source=\(.geometry_source) corners=\(.corners|length)",
         (.corners[] | "  \(.corner): setup \(.worst_slack_ns) ns, hold \(.worst_hold_slack_ns) ns, fmax \(.fmax_mhz) MHz, \(.timing_status)")' "$out"
  exit 0
fi

check_pin yosys "$(jq -r .yosys.version_prefix "$ROOT/layout/tools.json")" "$(yosys -V 2>&1 | head -1)"

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
