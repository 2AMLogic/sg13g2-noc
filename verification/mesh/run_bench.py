"""Build the 2 x 2 mesh with Icarus and run test_mesh under cocotb.

Run by verification/run.sh inside a throwaway cocotb environment; do not call
directly. Usage: run_bench.py [--neg NEG_DEFINE | --gl [--inject-fault]]
--gl runs the committed gate-level netlist (zero delay, DEPTH 4 set only) against the
pinned PDK sg13g2_stdcell models; exit 2 if layout/mesh/check.sh fails. --inject-fault
(with --gl) swaps one cell type in a temp copy of the netlist and must make the bench fail.
Exit 0 only if every run passes at DEPTH 4 and DEPTH 1. With --neg the bench is
expected to FAIL (exit non-zero) and names the check that tripped.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cocotb_tools.runner import get_results, get_runner

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RTL = ROOT / "rtl"
BUILD = HERE / "sim_build"
SOURCES = [RTL / f for f in ("noc_mesh.v", "noc_tile.v", "noc_router.v", "noc_tgen.v", "noc_tchk.v")]
NEGS = ("NEG_DROP_CREDIT", "NEG_CORRUPT", "NEG_SKIPSEQ")


def run(name, modes, *, depth, neg="", sources=None, parameters=None, includes=None):
    runner = get_runner("icarus")
    bdir = BUILD / name
    runner.build(
        sources=sources or SOURCES,
        hdl_toplevel="noc_mesh",
        includes=[RTL] if includes is None else includes,
        defines={neg: "1"} if neg else {},
        parameters={"DEPTH": depth} if parameters is None else parameters,
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


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gate_level(inject_fault):
    """Zero-delay gate-level run of layout/mesh/netlist/noc_mesh.v (d4 set only)."""
    if subprocess.run(["bash", str(ROOT / "layout/mesh/check.sh")]).returncode != 0:
        print("run_bench: layout/mesh/check.sh failed; refusing to simulate a stale netlist", file=sys.stderr)
        sys.exit(2)
    pdk = json.loads((ROOT / "layout/pdk.json").read_text())
    pdk_root = Path(os.environ.get("PDK_ROOT", Path.home() / "share/pdk"))
    vdir = pdk_root / pdk["variant"] / "libs.ref" / pdk["cell_library"] / "verilog"
    models = [vdir / "sg13g2_udp.v", vdir / "sg13g2_stdcell.v"]
    for m in models:
        if not m.is_file():
            print(f"run_bench: cell model {m} not found (set PDK_ROOT; see layout/pdk.json)", file=sys.stderr)
            sys.exit(2)
    netlist = ROOT / "layout/mesh/netlist/noc_mesh.v"
    want = json.loads((ROOT / "layout/mesh/reports/synthesize.json").read_text())["netlist_sha256"]
    nsha = sha256(netlist)
    if nsha != want:
        print("run_bench: netlist sha256 does not match layout/mesh/reports/synthesize.json", file=sys.stderr)
        sys.exit(2)
    modes = ["sweep", "adversarial", "reset"]
    if inject_fault:
        # swap one cell type throughout in a temp copy: nand2 -> nor2 (same pins, different function)
        tmp = Path(tempfile.mkdtemp(prefix="noc-gl-fault-"))
        bad = tmp / "noc_mesh.v"
        text = netlist.read_text()
        n = text.count("sg13g2_nand2_1 ")
        bad.write_text(text.replace("sg13g2_nand2_1 ", "sg13g2_nor2_1 "))
        print(f"fault injected: {n} sg13g2_nand2_1 instances -> sg13g2_nor2_1 (temp copy {bad})")
        ok, data = run("gl_fault", modes, depth=4, sources=models + [bad], parameters={}, includes=[])
        shutil.rmtree(tmp, ignore_errors=True)
        tripped = sorted({p.split("]")[0] + "]" for r in data for p in r["problems"]})
        print(f"NEGATIVE CONTROL gate-level fault: bench {'PASSED (control failed to trip!)' if ok else 'failed as intended'}")
        for t in tripped:
            print(f"  tripped: {t}")
        for r in data:
            for p in r["problems"][:3]:
                print(f"    {p}")
        sys.exit(0 if ok else 1)
    ok, data = run("gl_d4", modes, depth=4, sources=models + [netlist], parameters={}, includes=[])
    n_bad = sum(1 for r in data if r["problems"])
    if not data:
        print("gate-level bench produced no results (crashed before any run completed); nothing recorded")
        sys.exit(1)
    summary = {
        "note": "simulated (Icarus, zero-delay gate level, committed Yosys netlist + PDK sg13g2_stdcell "
                "models); DEPTH 4 set only (the netlist is synthesized at DEPTH 4); same scoreboard as "
                "results.json",
        "netlist": "layout/mesh/netlist/noc_mesh.v",
        "netlist_sha256": nsha,
        "pdk_release_tag": pdk["release_tag"],
        "pdk_tarball_sha256": pdk["tarball_sha256"],
        "cell_model_sha256": {m.name: sha256(m) for m in models},
        "packets_per_node": 64,
        "runs": len(data),
        "runs_failed": n_bad,
    }
    (HERE / "results-gl.json").write_text(
        json.dumps({"summary": summary, "points": data}, indent=1, sort_keys=True) + "\n")
    print(f"{summary['runs']} gate-level runs, {n_bad} failed; wrote {HERE / 'results-gl.json'}")
    sys.exit(0 if ok and n_bad == 0 and data else 1)


def main():
    sys.path.insert(0, str(HERE))
    args = sys.argv[1:]
    if args[:1] == ["--gl"]:
        gate_level(args[1:] == ["--inject-fault"])
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
