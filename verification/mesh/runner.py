"""Build noc_mesh with Icarus and run test_mesh under cocotb (issue #40).

Usage: runner.py [NEG_DEFINE]   (called by verification/run.sh mesh)
With NEG_DEFINE (NEG_SKIPSEQ or NEG_CORRUPT) the bench is expected to FAIL
and exits non-zero naming the checker flag that tripped.
"""
import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_results, get_runner

here = Path(__file__).resolve().parent
root = here.parents[1]
rtl = root / "rtl"
neg = sys.argv[1] if len(sys.argv) > 1 else ""

build_dir = here / "sim_build" / (neg or "clean")
r = get_runner("icarus")
r.build(
    sources=[rtl / f for f in ("noc_mesh.v", "noc_tile.v", "noc_router.v",
                               "noc_tgen.v", "noc_tchk.v")],
    hdl_toplevel="noc_mesh",
    includes=[rtl],
    defines={neg: 1} if neg else {},
    build_args=["-g2005"],
    timescale=("1ns", "1ps"),
    build_dir=build_dir,
    always=True,
)
os.environ["MESH_NEG"] = neg
xml = r.test(
    hdl_toplevel="noc_mesh",
    test_module="test_mesh",
    test_dir=here,
    build_dir=build_dir,
    results_xml=build_dir / "results.xml",
)
total, failed = get_results(xml)
print(f"runner: mesh NEG={neg or '-'}: {total - failed}/{total} tests passed")
sys.exit(1 if failed else 0)
