"""Build the loopback DUT with Icarus and run test_endpoints under cocotb.

Run by verification/run.sh inside a throwaway cocotb environment; do not call
directly. Usage: run_bench.py [--neg corrupt|skipseq]
Exit 0 only if every run passes. With --neg the bench is expected to FAIL
(exit non-zero) and names the check that tripped.
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


def run(name, modes, *, depth=4, xw=1, yw=1, defines=None, out=None):
    runner = get_runner("icarus")
    bdir = BUILD / name
    runner.build(
        sources=[RTL / "noc_tgen.v", RTL / "noc_tchk.v", HERE / "loopback.v"],
        hdl_toplevel="loopback",
        includes=[RTL],
        defines=defines or {},
        parameters={"DEPTH": depth, "MESH_XW": xw, "MESH_YW": yw},
        build_args=["-g2005"],
        build_dir=bdir,
        always=True,
    )
    out = out or bdir / "results.json"
    os.environ.update(EP_MODES=",".join(modes), EP_OUT=str(out),
                      EP_DEPTH=str(depth), EP_XW=str(xw), EP_YW=str(yw))
    try:
        xml = runner.test(hdl_toplevel="loopback", test_module="test_endpoints",
                          test_dir=HERE, build_dir=bdir, results_xml=bdir / "results.xml")
        total, failed = get_results(xml)
        ok = total > 0 and failed == 0
    except (Exception, SystemExit):
        ok = False
    data = json.loads(Path(out).read_text()) if Path(out).exists() else {}
    return ok, data


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
