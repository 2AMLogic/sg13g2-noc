#!/usr/bin/env bash
# Toolchain smoke (issue #4): push layout/smoke/counter.v through
#   klt synthesize -> place-and-route -> drc -> lvs -> sta
# on IHP SG13G2 sg13g2_stdcell and write each klt JSON envelope to
# layout/smoke/reports/. Stops at the first failing step but keeps that
# step's envelope as evidence. Single-unit runs only; nothing here fans out.
#
# Usage:  layout/smoke/run.sh            (PDK_ROOT defaults to ~/share/pdk)
# Needs:  yosys, openroad on PATH at the versions in layout/tools.json;
#         uvx (klt is fetched at the pinned version, never installed); jq; python3.
#         The IHP-Open-PDK pinned in layout/pdk.json under $PDK_ROOT/ihp-sg13g2
#         (klayout-tools scripts/fetch-ihp-sg13g2.sh lays it out).
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SMOKE="$ROOT/layout/smoke"
REQ="$SMOKE/requests"
OUT="$SMOKE/reports"
. "$ROOT/layout/lib.sh"

# --- pins -------------------------------------------------------------------
check_pin yosys "$(jq -r .yosys.version_prefix "$ROOT/layout/tools.json")" "$(yosys -V 2>&1 | head -1)"
check_pin openroad "$(jq -r .openroad.version "$ROOT/layout/tools.json")" "$(openroad -version 2>&1 | head -1)"
require_klt
stamp="$(klt pdk find --pdk "$PDK" 2>&1 | sed -n 's/^version: //p')"
check_pin pdk "$(jq -r .klt_pdk_version_stamp "$ROOT/layout/pdk.json")" "$stamp"

# --- clean ------------------------------------------------------------------
rm -rf "$REQ/.klt"
mkdir -p "$OUT"
rm -f "$OUT"/*.json
cd "$ROOT" || exit 2

GDS="layout/smoke/requests/.klt/place-and-route/smoke_counter.gds"
GATE_SPICE="layout/smoke/requests/.klt/smoke_counter.gate.spice"

step() { # name -- command...   (envelope = stdout)
  local name="$1"; shift 2
  echo "== $name"
  local env="$OUT/$name.json"
  [ "$name" = extract ] && env="$REQ/.klt/$name.json"   # intermediate, large; not committed
  mkdir -p "$(dirname "$env")"
  "$@" > "$env" 2> "$env.err"
  local rc=$?
  # klt prints its error envelope on stderr for some failures; keep it as the evidence
  [ -s "$env" ] || cp "$env.err" "$env"
  rm -f "$env.err"
  if [ $rc -ne 0 ]; then
    echo "run.sh: step '$name' failed (exit $rc); envelope kept at layout/smoke/reports/$name.json" >&2
    python3 -I "$SMOKE/sanitize.py" "$ROOT" "$PDK_ROOT" "$OUT"/*.json
    exit 1
  fi
}

step synthesize      -- klt synthesize "$REQ/synthesize.json" --format json
step place-and-route -- klt place-and-route "$REQ/place-and-route.json" --format json
step drc             -- klt drc --deck sg13g2 --pdk "$PDK" "$GDS" --format json
step extract         -- klt extract "$GDS" --deck sg13g2 --pdk "$PDK" \
                          --abstract-cells "sg13g2_*" --def-net-names \
                          -o "$GATE_SPICE" --format json
step lvs             -- klt lvs "$REQ/lvs.json" --format json
step sta             -- klt sta "$REQ/sta.json" --format json

python3 -I "$SMOKE/sanitize.py" "$ROOT" "$PDK_ROOT" "$OUT"/*.json
klt env-provenance lint-envelope "$OUT"/*.json || die "committed envelopes carry absolute host paths"

echo "== summary"
jq -r '"synthesize: \(.status) cells=\(.instance_count) area_um2=\(.area_um2)"' "$OUT/synthesize.json"
jq -r '"place-and-route: \(.status) stage=\(.stage_reached) route_drc=\(.route_drc_violation_count) tapcell_master=\(.power.tapcell_master) pdn=\(.power.pdn)"' "$OUT/place-and-route.json"
jq -r '"drc: \(.status) violations=\(.violation_count) layers_in_stream_without_rules=\(.coverage.layers_in_stream_without_rules|length) rules_skipped=\(.coverage.rules_skipped|length)"' "$OUT/drc.json"
jq -r '"lvs: \(.status) mismatches=\(.mismatch_count) power_connectivity=\(.power_connectivity.status)"' "$OUT/lvs.json"
jq -r '"sta: \(.status) corners=\(.corners|length)"' "$OUT/sta.json"
