#!/usr/bin/env bash
# Functional verification of the 2 x 2 mesh through `klt functional-verification` (issue #64).
#
#   verification/fv.sh    run the three requests in verification/requests/ and write
#                         evidence/item5-functional-verification-mesh-{depth4,depth1,neg}.json
#                         exit 0 only if depth4 and depth1 pass AND the negative control fails
#
# klt is built per run in a throwaway venv (nothing host-wide) from the commit named in
# layout/tools.json. That version string is not on any package index, so the commit is taken
# from a klayout-tools checkout: KLT_SRC_REPO (default ~/GitHub/klayout-tools).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/layout/tools.json"
die() { echo "fv.sh: $*" >&2; exit 2; }

PIN="$(jq -r .klayout_tools.version "$TOOLS")"; SHA="${PIN##*+g}"
[ -n "$SHA" ] && [ "$SHA" != "$PIN" ] || die "klayout_tools.version '$PIN' carries no +g<sha>"
ICARUS_WANT="$(jq -r .icarus.version_prefix "$TOOLS")"
case "$(iverilog -V 2>&1 | head -1)" in "$ICARUS_WANT"*) ;; *) die "icarus mismatch (worker-spec gap; do not install here)";; esac

REPO="${KLT_SRC_REPO:-$HOME/GitHub/klayout-tools}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/src"
git -C "$REPO" archive "$SHA" | tar -x -C "$WORK/src" || die "commit $SHA not available in $REPO"
uv venv -q --python "$(jq -r .cocotb.python "$TOOLS")" "$WORK/venv" || die "venv failed"
uv pip install -q --python "$WORK/venv/bin/python" "$WORK/src[functional-verification]" || die "klt install failed"
KLT="$WORK/venv/bin/klt"
COCOTB_GOT="$("$WORK/venv/bin/python" -c 'import cocotb;print(cocotb.__version__)')"
echo "fv.sh: klt from $SHA; cocotb $COCOTB_GOT (klt's own extra selects it; run.sh uses $(jq -r .cocotb.version "$TOOLS"))"

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
