#!/usr/bin/env bash
# Functional verification of the 2 x 2 mesh through `klt functional-verification` (issue #64).
#
#   verification/fv.sh    run the three requests in verification/requests/ and write
#                         evidence/item5-functional-verification-mesh-{depth4,depth1,neg}.json
#                         exit 0 only if depth4 and depth1 pass AND the negative control fails
#   fv.sh --emit-requests print one JSON object on stdout describing the request assembly and
#                         the bench's Python path, then exit 0 (issue #122). No pin check, no
#                         klt fetch, no writes: CI's check_fv_requests.py guards this path
#                         hermetically from fv.sh's own assembly, so one hoist cannot leave a
#                         checker describing a stale shape.
#
# klt is fetched per run by uvx (nothing host-wide, no fallback to klt on PATH) at the PyPI
# release pinned in layout/tools.json (klayout-tools[functional-verification]==<version>),
# through the layout/lib.sh preamble shared with the layout runners.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/layout/tools.json"
# pinned-toolchain preamble (die, check_pin, icarus/klt pins) comes from layout/lib.sh;
# this runner never touches the PDK, so skip its exports
LAYOUT_LIB_SKIP_PDK=1
KLT_EXTRAS="functional-verification"
KLT_PY="$(jq -r .cocotb.python "$TOOLS")"
. "$ROOT/layout/lib.sh"

# the request files carry only what makes each run distinct; fv.sh assembles the rest
# (sources, toplevel, testbench, launch options) from the shared mesh fields (issue #109)
COMMON="$ROOT/verification/mesh/klt-request-common.json"
[ -f "$COMMON" ] || die "missing $COMMON"
# the assembled request copy lives in verification/requests/, so the shared paths are
# rewritten relative to that directory (where klt resolves them)
REQ_REL="$(realpath --relative-to="$ROOT/verification/requests" "$ROOT")/"

# the bench imports bench_vocab from verification/common; klt puts only the request's
# testbench.search_path on the bench's Python path, so export the vocabulary dir here.
# Declared before the pin/klt gates so --emit-requests (which skips them) hands out the
# same declaration the real run consumes -- one Python path for both modes (issue #122)
export PYTHONPATH="$ROOT/verification/common${PYTHONPATH:+:$PYTHONPATH}"

# the one assembler for both modes: the shared mesh fields from $COMMON, paths rewritten
# relative to verification/requests/ (where klt resolves them). The optional second arg
# overrides env.MESH_OUT (where the bench writes its per-run results file); without it,
# the request's own env travels untouched
assemble_req() { # n [mesh_out]
  jq --arg o "${2:-}" --arg rel "$REQ_REL" --slurpfile s "$COMMON" '
      (.sources = ($s[0].sources | map($rel + .))
      | .hdl_toplevel = $s[0].hdl_toplevel
      | .testbench = ($s[0].testbench | .search_path = ($rel + .search_path))
      | .options.timescale = $s[0].options.timescale
      | .options.build_args = $s[0].options.build_args
      | .options.includes = ($s[0].options.includes | map($rel + .))
      | (if $o == "" then . else .env.MESH_OUT = $o end))' \
      "$ROOT/verification/requests/functional-verification-mesh-$1.json"
}

# emit-only mode: stdout only, nothing written into the repo, and none of the gates
# below (icarus pin, klt fetch, cocotb probe -- the uvx fetch is a network round-trip
# CI must not pay). Needs only jq, like the lib.sh preamble it already sourced
if [ "${1:-}" = "--emit-requests" ]; then
  jq -n \
    --arg request_dir "$ROOT/verification/requests" \
    --arg pythonpath "$PYTHONPATH" \
    --slurpfile depth4 <(assemble_req depth4) \
    --slurpfile depth1 <(assemble_req depth1) \
    --slurpfile neg <(assemble_req neg) \
    '{request_dir: $request_dir,
      pythonpath: ($pythonpath | split(":")),
      requests: {depth4: $depth4[0], depth1: $depth1[0], neg: $neg[0]}}'
  exit 0
fi

[ -n "$KLT_VER" ] && [ "$KLT_VER" != null ] || die "layout/tools.json carries no klayout_tools.version"
check_pin icarus "$(jq -r .icarus.version_prefix "$TOOLS")" "$(iverilog -V 2>&1 | head -1)"

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
require_klt
COCOTB_GOT="$(klt_uvx python -c 'import cocotb;print(cocotb.__version__)')"
echo "fv.sh: klt $KLT_VER; cocotb $COCOTB_GOT (klt's own extra selects it; run.sh uses $(jq -r .cocotb.version "$TOOLS"))"

rc=0
for n in depth4 depth1 neg; do
  out="$ROOT/evidence/item5-functional-verification-mesh-$n.json"
  # bench results go to a per-run temp file, so concurrent runs on a shared worker cannot collide;
  # the request copy sits next to the original because its paths are relative to its directory
  res="$WORK/mesh-$n.json"
  req="$(mktemp "$ROOT/verification/requests/.run-$n.XXXXXX.json")" || die "mktemp failed"
  assemble_req "$n" "$res" > "$req" || die "request assembly failed for $n"
  klt functional-verification "$req" \
      -o "$WORK/out-$n" --format json > "$out"; r=$?
  rm -f "$req"
  st="$(jq -r .status "$out" 2>/dev/null)"
  echo "fv.sh: $n -> status=$st (klt exit $r)"
  if [ "$n" = neg ]; then
    [ "$st" = fail ] || { echo "fv.sh: negative control did not fail" >&2; rc=1; }
    # the envelope carries only the test's AssertionError; the check names come from the bench's own
    # results file and are committed as a sidecar next to the envelope (AC2 of #64)
    side="$ROOT/evidence/item5-functional-verification-mesh-neg.tripped.json"
    define="$(jq -r '.options.defines|keys[0]' "$ROOT/verification/requests/functional-verification-mesh-neg.json")"
    tripped="$(jq -c '[.[].problems[]|split("]")[0]+"]"]|unique' "$res" 2>/dev/null)"
    case "$tripped" in ""|"[]") rm -f "$side"; echo "fv.sh: negative control failed but named no tripped check" >&2; rc=1;;
      *) jq -n --arg d "$define" --argjson c "$tripped" '{define:$d,checks:$c}' > "$side";; esac
    echo "fv.sh: neg tripped: $tripped"
  else [ "$st" = pass ] || rc=1; fi
done
exit $rc
