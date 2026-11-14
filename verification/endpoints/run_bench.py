"""Build the loopback DUT with Icarus and run test_endpoints under cocotb.

Run by verification/run.sh inside a throwaway cocotb environment; do not call
directly. Usage: run_bench.py [--neg corrupt|skipseq]
Exit 0 only if every run passes. With --neg the bench is expected to FAIL
(exit non-zero) and names the check that tripped.

The cocotb-launch scaffolding is shared with the mesh and router drivers in
verification/lib_bench.py; what is here is only what this bench does differently.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RTL = ROOT / "rtl"
BUILD = HERE / "sim_build"

# python -I keeps the script's directory off sys.path, so verification/ is added
# for this import and removed again right after (lib_bench.__doc__ says why).
sys.path.insert(0, str(ROOT / "verification"))
from lib_bench import build_and_run

del sys.path[0]


def run(name, modes, *, depth=4, xw=1, yw=1, defines=None):
    res = build_and_run(
        name=name,
        sources=[RTL / "noc_tgen.v", RTL / "noc_tchk.v", HERE / "loopback.v"],
        hdl_toplevel="loopback",
        test_module="test_endpoints",
        test_dir=HERE,
        build_root=BUILD,
        includes=[RTL],
        defines=defines,
        parameters={"DEPTH": depth, "MESH_XW": xw, "MESH_YW": yw},
        env={"EP_MODES": ",".join(modes), "EP_DEPTH": str(depth),
             "EP_XW": str(xw), "EP_YW": str(yw)},
        results_env="EP_OUT",
        default={},
    )
    return res.ok, res.data


def main():
    sys.path.insert(0, str(HERE))
    args = sys.argv[1:]
    if args[:1] == ["--neg"]:
        kind = args[1]
        define = {"corrupt": "NEG_CORRUPT", "skipseq": "NEG_SKIPSEQ"}[kind]
        ok, data = run("neg_" + kind, ["neg"], defines={define: "1"})
        tripped = sorted({p for r in data.get("points", []) for p in r["problems"]
                          if p.startswith("checker error flag")})
        print(f"NEGATIVE CONTROL {define}: bench {'PASSED (control failed to trip!)' if ok else 'failed as intended'}")
        for t in tripped:
            print(f"  tripped: {t}")
        sys.exit(0 if ok else 1)

    allres = {"points": [], "coords": []}
    good = True
    for name, modes, kw in [
        ("main", ["sweep", "coords"], {}),
        ("depth1", ["depth1"], {"depth": 1}),
        ("mesh4x4", ["coords"], {"xw": 2, "yw": 2}),
    ]:
        ok, data = run(name, modes, **kw)
        good &= ok
        for sec in allres:
            allres[sec] += data.get(sec, [])
    n_bad = sum(1 for sec in allres for r in allres[sec] if r["problems"] or r["errors"])
    summary = {
        "note": "simulated (Icarus loopback, generator -> link register -> checker); "
                "latency is generation to last flit accepted, in cycles",
        "packets_per_run": 64,
        "runs": sum(len(v) for v in allres.values()),
        "runs_failed": n_bad,
    }
    (HERE / "results.json").write_text(
        json.dumps({"summary": summary, **allres}, indent=1, sort_keys=True) + "\n")
    print(f"{summary['runs']} runs, {n_bad} failed; wrote {HERE / 'results.json'}")
    sys.exit(0 if good and n_bad == 0 else 1)


if __name__ == "__main__":
    main()
