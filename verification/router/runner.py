"""Build noc_router with Icarus and run test_noc_router under cocotb.

Usage: runner.py DEPTH [NEG_DEFINE]   (called by verification/run.sh)

The cocotb-launch scaffolding is shared with the endpoints and mesh drivers in
verification/lib_bench.py; what is here is only what this bench does differently.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# python -I keeps the script's directory off sys.path, so verification/ is added
# for this import and removed again right after (lib_bench.__doc__ says why).
sys.path.insert(0, str(ROOT / "verification"))
from lib_bench import build_and_run

del sys.path[0]

depth = int(sys.argv[1])
neg = sys.argv[2] if len(sys.argv) > 2 else ""

res = build_and_run(
    name=f"d{depth}{'_' + neg if neg else ''}",
    sources=[ROOT / "rtl" / "noc_router.v"],
    hdl_toplevel="noc_router",
    test_module="test_noc_router",
    test_dir=HERE,
    build_root=HERE / "sim_build",
    defines={neg: "1"} if neg else None,
    parameters={"DEPTH": depth},
    env={"NOC_DEPTH": str(depth)},
)
print(f"runner: DEPTH={depth} NEG={neg or '-'}: {res.total - res.failed}/{res.total} tests passed")
sys.exit(0 if res.ok else 1)
