# Shared preamble for the runners (layout/{smoke,tile,mesh}/run.sh and
# verification/{run,fv}.sh). Sourced, not executed. The caller sets ROOT (repo root)
# first. This defines the pinned-toolchain setup and helpers; each runner keeps its
# own explicit list of check_pin calls, because which tools it pin-checks depends on
# what it runs (mesh runs synthesis only, so it checks yosys but not openroad or the pdk).
#
# Provides: KLT_VER, KLT_SPEC, klt(), die(), check_pin(), require_klt(); plus
# PDK_ROOT, PDK (exported) unless the caller sets LAYOUT_LIB_SKIP_PDK=1 before sourcing
# (the verification runners don't need the PDK and must not fail if layout/pdk.json
# is unreadable). klt is always fetched by uvx at the pinned PyPI version; there is
# no fallback to `klt` on PATH. Optional knobs, set before sourcing: KLT_EXTRAS adds
# extras to the klayout-tools requirement (fv.sh sets functional-verification) and
# KLT_PY pins the uvx python (fv.sh pins .cocotb.python); the layout runners set
# neither. die() prefixes its message with the sourcing runner's basename.

DIE_PREFIX="$(basename "${BASH_SOURCE[1]:-$0}")"

if [ "${LAYOUT_LIB_SKIP_PDK:-0}" = 1 ]; then
  :
else
  export PDK_ROOT="${PDK_ROOT:-$HOME/share/pdk}"
  export PDK="$(jq -r .variant "$ROOT/layout/pdk.json")"
fi
KLT_VER="$(jq -r .klayout_tools.version "$ROOT/layout/tools.json")"
if [ -n "${KLT_EXTRAS:-}" ]; then
  KLT_SPEC="klayout-tools[$KLT_EXTRAS]==$KLT_VER"
else
  KLT_SPEC="klayout-tools==$KLT_VER"
fi
klt_uvx() { # run a command inside the pinned klt environment (klt() runs its klt entry point)
  if [ -n "${KLT_PY:-}" ]; then
    uvx --quiet --python "$KLT_PY" --from "$KLT_SPEC" "$@"
  else
    uvx --quiet --from "$KLT_SPEC" "$@"
  fi
}
klt() { klt_uvx klt "$@"; }

die() { echo "$DIE_PREFIX: $*" >&2; exit 2; }

check_pin() { # name want got
  case "$3" in "$2"*) ;; *) die "$1 mismatch: pinned '$2', found '$3' (worker-spec gap; do not install here)";; esac
}

require_klt() {
  local got_klt
  got_klt="$(klt --version 2>&1 | tail -1)"
  [ "$got_klt" = "klt $KLT_VER" ] || die "klt does not resolve from '$KLT_SPEC' at the pinned version: wanted 'klt $KLT_VER', got '$got_klt' (no fallback to klt on PATH)"
}
