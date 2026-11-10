#!/usr/bin/env bash
# Functional verification of the 2 x 2 mesh through `klt functional-verification` (issue #64).
#
#   verification/fv.sh    run the three requests in verification/requests/ and write
#                         evidence/item5-functional-verification-mesh-{depth4,depth1,neg}.json
#                         exit 0 only if depth4 and depth1 pass AND the negative control fails
#
# klt is installed per run in a throwaway venv (nothing host-wide) from the PyPI release pinned
# in layout/tools.json (klayout-tools[functional-verification]==<version>).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/layout/tools.json"
die() { echo "fv.sh: $*" >&2; exit 2; }

PIN="$(jq -r .klayout_tools.version "$TOOLS")"
[ -n "$PIN" ] && [ "$PIN" != null ] || die "layout/tools.json carries no klayout_tools.version"
ICARUS_WANT="$(jq -r .icarus.version_prefix "$TOOLS")"
case "$(iverilog -V 2>&1 | head -1)" in "$ICARUS_WANT"*) ;; *) die "icarus mismatch (worker-spec gap; do not install here)";; esac

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
uv venv -q --python "$(jq -r .cocotb.python "$TOOLS")" "$WORK/venv" || die "venv failed"
uv pip install -q --python "$WORK/venv/bin/python" "klayout-tools[functional-verification]==$PIN" || die "klt install failed"
KLT="$WORK/venv/bin/klt"
GOT="$("$KLT" --version 2>&1 | tail -1)"
[ "$GOT" = "klt $PIN" ] || die "klt version mismatch: wanted 'klt $PIN', got '$GOT' (no fallback to klt on PATH)"
COCOTB_GOT="$("$WORK/venv/bin/python" -c 'import cocotb;print(cocotb.__version__)')"
echo "fv.sh: klt $PIN; cocotb $COCOTB_GOT (klt's own extra selects it; run.sh uses $(jq -r .cocotb.version "$TOOLS"))"

rc=0
for n in depth4 depth1 neg; do
  out="$ROOT/evidence/item5-functional-verification-mesh-$n.json"
  # bench results go to a per-run temp file, so concurrent runs on a shared worker cannot collide;
  # the request copy sits next to the original because its paths are relative to its directory
  res="$WORK/mesh-$n.json"
  req="$(mktemp "$ROOT/verification/requests/.run-$n.XXXXXX.json")" || die "mktemp failed"
  jq --arg o "$res" '.env.MESH_OUT=$o' "$ROOT/verification/requests/functional-verification-mesh-$n.json" > "$req"
  "$KLT" functional-verification "$req" \
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
