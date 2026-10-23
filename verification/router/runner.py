"""Build noc_router with Icarus and run test_noc_router under cocotb.

Usage: runner.py DEPTH [NEG_DEFINE]   (called by verification/run.sh)
"""
import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_results, get_runner

here = Path(__file__).resolve().parent
root = here.parents[1]
depth = int(sys.argv[1])
neg = sys.argv[2] if len(sys.argv) > 2 else ""

build_dir = here / "sim_build" / f"d{depth}{'_' + neg if neg else ''}"
r = get_runner("icarus")
r.build(
    sources=[root / "rtl" / "noc_router.v"],
    hdl_toplevel="noc_router",
    parameters={"X": 1, "Y": 1, "DEPTH": depth},
    defines={neg: 1} if neg else {},
    build_args=["-g2005"],
    timescale=("1ns", "1ps"),
    build_dir=build_dir,
    always=True,
)
os.environ["NOC_DEPTH"] = str(depth)
xml = r.test(
    hdl_toplevel="noc_router",
    test_module="test_noc_router",
    test_dir=here,
    build_dir=build_dir,
    results_xml=build_dir / "results.xml",
)
total, failed = get_results(xml)
print(f"runner: DEPTH={depth} NEG={neg or '-'}: {total - failed}/{total} tests passed")
sys.exit(1 if failed else 0)
