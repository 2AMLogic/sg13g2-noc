#!/usr/bin/env bash
# Cold-start entry point for the testbenches.
#
# Usage:  verification/run.sh router            # DEPTH=4 then DEPTH=1
#         NEG=NEG_YX_TURN verification/run.sh router      # negative control
#         NEG=NEG_DROP_CREDIT verification/run.sh router
# Needs:  iverilog (version prefix in layout/tools.json), uv, network for the
#         first run. cocotb is not installed on the worker: it goes into a venv
#         inside this directory (.venv, gitignored), at the version pinned in
#         layout/tools.json. Nothing host-wide is touched.
# Exit:   0 all tests passed; 1 a test failed (the output names the check that
#         tripped: scoreboard / credit-conservation / watchdog / drain);
#         2 setup or pin problem.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VDIR="$ROOT/verification"
TOOLS="$ROOT/layout/tools.json"
die() { echo "run.sh: $*" >&2; exit 2; }

check_pin() { # name want got
  case "$3" in "$2"*) ;; *) die "$1 mismatch: pinned '$2', found '$3' (worker-spec gap; do not install host-wide)";; esac
}

[ $# -ge 1 ] || die "usage: run.sh router"
cmd="$1"

check_pin icarus "$(jq -r .icarus.version_prefix "$TOOLS")" "$(iverilog -V 2>&1 | head -1)"
COCOTB_VER="$(jq -r .cocotb.version "$TOOLS")"
[ -n "$COCOTB_VER" ] && [ "$COCOTB_VER" != null ] || die "layout/tools.json has no cocotb.version"

PY="$VDIR/.venv/bin/python"
if [ ! -x "$PY" ] || [ "$("$VDIR/.venv/bin/cocotb-config" --version 2>/dev/null)" != "$COCOTB_VER" ]; then
  command -v uv >/dev/null || die "uv not found; cannot create the cocotb venv"
  rm -rf "$VDIR/.venv"
  uv venv --quiet "$VDIR/.venv" || die "venv creation failed"
  VIRTUAL_ENV="$VDIR/.venv" uv pip install --quiet "cocotb==$COCOTB_VER" || die "cocotb==$COCOTB_VER install into the venv failed"
fi
check_pin cocotb "$COCOTB_VER" "$("$VDIR/.venv/bin/cocotb-config" --version 2>&1)"

case "$cmd" in
  router)
    NEG="${NEG:-}"
    case "$NEG" in ""|NEG_YX_TURN|NEG_DROP_CREDIT) ;; *) die "unknown NEG '$NEG'";; esac
    rc=0
    for depth in 4 1; do
      echo "== router DEPTH=$depth NEG=${NEG:--}"
      "$PY" -I "$VDIR/router/runner.py" "$depth" "$NEG" || rc=1
      [ $rc -eq 0 ] || break
    done
    exit $rc
    ;;
  *) die "unknown bench '$cmd'";;
esac
