"""Build the 2 x 2 mesh with Icarus and run test_mesh under cocotb.

Run by verification/run.sh inside a throwaway cocotb environment; do not call
directly. Usage: run_bench.py [--neg NEG_DEFINE]
Exit 0 only if every run passes at DEPTH 4 and DEPTH 1. With --neg the bench is
expected to FAIL (exit non-zero) and names the check that tripped.
"""
import json
import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_results, get_runner

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RTL = ROOT / "rtl"
BUILD = HERE / "sim_build"
SOURCES = [RTL / f for f in ("noc_mesh.v", "noc_tile.v", "noc_router.v", "noc_tgen.v", "noc_tchk.v")]
NEGS = ("NEG_DROP_CREDIT", "NEG_CORRUPT", "NEG_SKIPSEQ")


def run(name, modes, *, depth, neg=""):
    runner = get_runner("icarus")
    bdir = BUILD / name
    runner.build(
        sources=SOURCES,
        hdl_toplevel="noc_mesh",
        includes=[RTL],
        defines={neg: "1"} if neg else {},
        parameters={"DEPTH": depth},
        build_args=["-g2005"],
        timescale=("1ns", "1ps"),
        build_dir=bdir,
        always=True,
    )
    out = bdir / "results.json"
    if out.exists():
        out.unlink()
    os.environ.update(MESH_MODES=",".join(modes), MESH_OUT=str(out), MESH_DEPTH=str(depth))
    try:
        xml = runner.test(hdl_toplevel="noc_mesh", test_module="test_mesh", test_dir=HERE,
                          build_dir=bdir, results_xml=bdir / "results.xml")
        total, failed = get_results(xml)
        ok = total > 0 and failed == 0
    except (Exception, SystemExit):
        ok = False
    data = json.loads(out.read_text()) if out.exists() else []
    return ok, data


def main():
    sys.path.insert(0, str(HERE))
    args = sys.argv[1:]
    if args[:1] == ["--neg"]:
        neg = args[1]
        if neg not in NEGS:
            print(f"unknown negative control {neg}; one of {', '.join(NEGS)}", file=sys.stderr)
            sys.exit(2)
        ok, data = run("neg_" + neg, ["neg"], depth=4, neg=neg)
        tripped = sorted({p.split("]")[0] + "]" for r in data for p in r["problems"]})
        print(f"NEGATIVE CONTROL {neg}: bench {'PASSED (control failed to trip!)' if ok else 'failed as intended'}")
        for t in tripped:
            print(f"  tripped: {t}")
        for r in data:
            for p in r["problems"][:3]:
                print(f"    {p}")
        sys.exit(0 if ok else 1)

    allres = []
    good = True
    for name, modes, depth in [("d4", ["sweep", "adversarial", "reset"], 4),
                               ("d1", ["depth1", "reset"], 1)]:
        ok, data = run(name, modes, depth=depth)
        good &= ok
        allres += data
    n_bad = sum(1 for r in allres if r["problems"])
    summary = {
        "note": "simulated (Icarus, noc_mesh 2 x 2, cfg broadcast to all four tiles); latency is "
                "generation to last flit accepted, in cycles; throughput is flits accepted per "
                "node per cycle from first generation to last accept",
        "packets_per_node": 64,
        "runs": len(allres),
        "runs_failed": n_bad,
    }
    (HERE / "results.json").write_text(
        json.dumps({"summary": summary, "points": allres}, indent=1, sort_keys=True) + "\n")
    print(f"{summary['runs']} runs, {n_bad} failed; wrote {HERE / 'results.json'}")
    sys.exit(0 if good and n_bad == 0 else 1)


if __name__ == "__main__":
    main()
