#!/usr/bin/env bash
# Functional verification of the 2 x 2 mesh through `klt functional-verification` (issue #64).
#
#   verification/fv.sh    run the three requests in verification/requests/ and write
#                         evidence/item5-functional-verification-mesh-{depth4,depth1,neg}.json
#                         exit 0 only if depth4 and depth1 pass AND the negative control fails
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
  jq --arg o "$res" '.env.MESH_OUT=$o' "$ROOT/verification/requests/functional-verification-mesh-$n.json" > "$req"
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
