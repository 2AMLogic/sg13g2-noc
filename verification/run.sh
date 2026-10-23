#!/usr/bin/env bash
# Verification entry point. Dispatches on the first argument so several
# benches can share one file.
#
#   verification/run.sh endpoints              loopback sweep (issue #19); exit 0 = all runs clean
#   verification/run.sh endpoints --neg KIND   negative control, KIND = corrupt | skipseq;
#                                              exits NON-zero and names the check that tripped
#   verification/run.sh endpoints-selftest     runs both controls, exit 0 only if both trip
#
# cocotb is never installed on the host. It is provisioned per run in a
# throwaway uvx environment at the version pinned in layout/tools.json;
# iverilog comes from the worker (version checked against the same file).
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/layout/tools.json"
die() { echo "run.sh: $*" >&2; exit 2; }

COCOTB_VER="$(jq -r .cocotb.version "$TOOLS")"
[ -n "$COCOTB_VER" ] && [ "$COCOTB_VER" != null ] || die "cocotb version not pinned in layout/tools.json"
COCOTB_PY="$(jq -r .cocotb.python "$TOOLS")"
[ -n "$COCOTB_PY" ] && [ "$COCOTB_PY" != null ] || die "cocotb python not pinned in layout/tools.json"
ICARUS_WANT="$(jq -r .icarus.version_prefix "$TOOLS")"
ICARUS_GOT="$(iverilog -V 2>&1 | head -1)"
case "$ICARUS_GOT" in "$ICARUS_WANT"*) ;; *) die "icarus mismatch: pinned '$ICARUS_WANT', found '$ICARUS_GOT' (worker-spec gap; do not install here)";; esac

cocotb_py() { uvx --quiet --python "$COCOTB_PY" --from "cocotb==$COCOTB_VER" python -I "$@"; }
got="$(uvx --quiet --python "$COCOTB_PY" --from "cocotb==$COCOTB_VER" cocotb-config --version 2>&1 | tail -1)"
[ "$got" = "$COCOTB_VER" ] || die "cocotb mismatch: pinned '$COCOTB_VER', environment reports '$got'"

endpoints() {
  cocotb_py "$ROOT/verification/endpoints/run_bench.py" "$@"
}

case "${1:-}" in
  endpoints) shift; endpoints "$@" ;;
  endpoints-selftest)
    rc=0
    for k in corrupt skipseq; do
      out="$(endpoints --neg "$k" 2>&1)"; r=$?
      echo "$out" | grep -E 'NEGATIVE CONTROL|tripped'
      if [ $r -eq 0 ] || ! echo "$out" | grep -q 'tripped:'; then
        echo "selftest: control '$k' did not trip the checker" >&2; rc=1
      fi
    done
    exit $rc ;;
  *) echo "usage: $0 endpoints [--neg corrupt|skipseq] | endpoints-selftest" >&2; exit 2 ;;
esac
