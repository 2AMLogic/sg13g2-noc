"""Build the 2 x 2 mesh with Icarus and run test_mesh under cocotb.

Run by verification/run.sh inside a throwaway cocotb environment; do not call
directly. Usage: run_bench.py [--neg NEG_DEFINE]
Exit 0 only if every run passes at DEPTH 4 and DEPTH 1. With --neg the bench is
expected to FAIL (exit non-zero) and names the check that tripped.

The cocotb-launch scaffolding is shared with the endpoints and router drivers in
verification/lib_bench.py; what is here is only what this bench does differently.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RTL = ROOT / "rtl"
BUILD = HERE / "sim_build"
SOURCES = [RTL / f for f in ("noc_mesh.v", "noc_tile.v", "noc_router.v", "noc_tgen.v", "noc_tchk.v")]
NEGS = ("NEG_DROP_CREDIT", "NEG_CORRUPT", "NEG_SKIPSEQ")

# python -I keeps the script's directory off sys.path, so verification/ is added
# for this import and removed again right after (lib_bench.__doc__ says why).
sys.path.insert(0, str(ROOT / "verification"))
from lib_bench import build_and_run

del sys.path[0]


def run(name, modes, *, depth, neg=""):
    res = build_and_run(
        name=name,
        sources=SOURCES,
        hdl_toplevel="noc_mesh",
        test_module="test_mesh",
        test_dir=HERE,
        build_root=BUILD,
        includes=[RTL],
        defines={neg: "1"} if neg else None,
        parameters={"DEPTH": depth},
        env={"MESH_MODES": ",".join(modes), "MESH_DEPTH": str(depth)},
        results_env="MESH_OUT",
        default=[],
    )
    return res.ok, res.data


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
