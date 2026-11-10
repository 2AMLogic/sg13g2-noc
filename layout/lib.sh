# Shared preamble for the layout runners (layout/{smoke,tile,mesh}/run.sh). Sourced, not executed.
# The caller sets ROOT (repo root) first. This defines the pinned-toolchain setup and helpers;
# each runner keeps its own explicit list of check_pin calls, because which tools it pin-checks
# depends on what it runs (mesh runs synthesis only, so it checks yosys but not openroad or the pdk).
#
# Provides: PDK_ROOT, PDK (exported), KLT_VER, KLT_SPEC, klt(), die(), check_pin(), require_klt().
# klt is always fetched by uvx at the pinned PyPI version; there is no fallback to `klt` on PATH.

export PDK_ROOT="${PDK_ROOT:-$HOME/share/pdk}"
export PDK="$(jq -r .variant "$ROOT/layout/pdk.json")"
KLT_VER="$(jq -r .klayout_tools.version "$ROOT/layout/tools.json")"
KLT_SPEC="klayout-tools==$KLT_VER"
klt() { uvx --quiet --from "$KLT_SPEC" klt "$@"; }

die() { echo "run.sh: $*" >&2; exit 2; }

check_pin() { # name want got
  case "$3" in "$2"*) ;; *) die "$1 mismatch: pinned '$2', found '$3' (worker-spec gap; do not install here)";; esac
}

require_klt() {
  local got_klt
  got_klt="$(klt --version 2>&1 | tail -1)"
  [ "$got_klt" = "klt $KLT_VER" ] || die "klt does not resolve from '$KLT_SPEC' at the pinned version: wanted 'klt $KLT_VER', got '$got_klt' (no fallback to klt on PATH)"
}
