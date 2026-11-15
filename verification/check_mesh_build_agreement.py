"""Drift check: the mesh build's two surviving declarations must agree.

    python3 -I verification/check_mesh_build_agreement.py
                                                    # exit 0 = all seven fields agree

The mesh build is declared twice on the verification side (issue #109's
collapse left exactly two): mesh/run_bench.py -- its SOURCES plus the keyword
arguments run() passes to build_and_run, and lib_bench.py's TIMESCALE and
BUILD_ARGS -- for the cocotb path, and mesh/klt-request-common.json for the
klt functional-verification path. Nothing else compares them, so a file added
to one declaration and not the other leaves klt elaborating a different design
than the bench of record builds (issue #114).

This check imports the bench with cocotb_tools stubbed -- it never builds and
never runs -- records what run() actually passes to build_and_run, and
compares every field the request JSON declares:

    JSON field               Python side
    sources                  run() kwarg sources        (set of repo-relative paths)
    hdl_toplevel             run() kwarg hdl_toplevel
    testbench.module         run() kwarg test_module
    testbench.search_path    run() kwarg test_dir       (repo-relative path)
    options.includes         run() kwarg includes       (set of repo-relative paths)
    options.timescale        lib_bench.TIMESCALE        (ordered sequence)
    options.build_args       lib_bench.BUILD_ARGS       (ordered sequence)

Reading what the bench *passes* rather than what it stores is not a style
choice: hdl_toplevel and test_module are literal keyword arguments inside
run(), not module attributes, so no constant-reading approach can see them.
sources and includes compare as sets -- compile-unit order carries no
elaboration semantics under Icarus with -g2005 -- while timescale and
build_args compare as ordered sequences, where order is semantic. The check
also fails on any JSON key it does not compare, so a field added to the
request file later forces a deliberate decision instead of silently joining
the unguarded set.

Hermetic like selftest_lib_bench.py: no cocotb, no Icarus, no klt, no
sim_build/ directory is touched. It runs on every pull request beside that
selftest (.github/workflows/signoff.yml), which the bench itself cannot --
item 9's cold start is local_only.
"""
import importlib.util
import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent            # verification/
ROOT = HERE.parent                                # repo root
BENCH = HERE / "mesh" / "run_bench.py"
REQUEST = HERE / "mesh" / "klt-request-common.json"

# The keys this check knows, per level. _comment is documentation, not a
# declaration. Anything else in the JSON is a field this check does not
# compare and therefore fails on -- see the module docstring.
TOP_KEYS = {"_comment", "sources", "hdl_toplevel", "testbench", "options"}
TESTBENCH_KEYS = {"module", "search_path"}
OPTIONS_KEYS = {"timescale", "build_args", "includes"}

FAILURES = []
COMPARED = []


def check(ok, invariant, what):
    """Record one assertion. Keeps going, so one run reports every break."""
    print(f"  {'ok  ' if ok else 'FAIL'}  {what}")
    if not ok:
        FAILURES.append((invariant, what))


def fatal(what, detail):
    """A declaration could not be read; there is nothing to compare. Exit 1."""
    print(f"FAIL  cannot read {what}: {detail}", file=sys.stderr)
    sys.exit(1)


def install_cocotb_stub():
    """Put a stub cocotb_tools.runner in sys.modules. Call before importing.

    lib_bench does `from cocotb_tools.runner import get_results, get_runner`
    at module scope, so the stub has to be in sys.modules first. It also
    shadows a real cocotb if one happens to be installed, which keeps this
    check identical on a bare runner and on a worker that has the bench
    environment.
    """
    runner = types.ModuleType("cocotb_tools.runner")
    runner.get_runner = lambda name: None
    runner.get_results = lambda xml: (0, 0)
    pkg = types.ModuleType("cocotb_tools")
    pkg.__path__ = []
    pkg.runner = runner
    sys.modules["cocotb_tools"] = pkg
    sys.modules["cocotb_tools.runner"] = runner


def load_bench():
    """Import run_bench.py by path; side-effect-free behind its __main__ guard.

    The module's own sys.path insert/delete around
    `from lib_bench import build_and_run` is self-cleaning, and python3 -I
    implies -P, so by path is the only way this script can import it.
    """
    if not BENCH.is_file():
        fatal(BENCH, "file not found")
    spec = importlib.util.spec_from_file_location("run_bench_under_check", BENCH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal(BENCH, f"import raised {type(e).__name__}: {e}")
    return module


def capture_bench_kwargs(bench):
    """Run mod.run() against a recording build_and_run; return its kwargs.

    What the bench passes to build_and_run is the Python declaration of
    record -- see the module docstring for why the module's constants alone
    are not enough.
    """
    captured = {}

    def recorder(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(ok=True, data=[])

    bench.build_and_run = recorder
    try:
        bench.run("probe", ["sweep"], depth=4)
    except Exception as e:
        fatal(f"run() of {BENCH}", f"raised {type(e).__name__}: {e}")
    if not captured:
        fatal(f"run() of {BENCH}", "build_and_run was never reached")
    return captured


def load_request():
    """Parse the klt request JSON, naming the file on any failure."""
    if not REQUEST.is_file():
        fatal(REQUEST, "file not found")
    try:
        return json.loads(REQUEST.read_text())
    except ValueError as e:
        fatal(REQUEST, f"unparseable JSON: {e}")


def take(request, *keys):
    """Descend request by keys; every key must be present and navigable."""
    node = request
    walked = []
    for key in keys:
        walked.append(key)
        if not isinstance(node, dict) or key not in node:
            fatal(REQUEST, f"key {'.'.join(walked)!r} missing")
        node = node[key]
    return node


def rel(p):
    """Repo-root-relative POSIX form of a bench path.

    A path that escapes the repo root stays absolute, which then reads as the
    mismatch it is rather than aborting the comparison run.
    """
    rp = Path(p).resolve()
    try:
        return rp.relative_to(ROOT).as_posix()
    except ValueError:
        return rp.as_posix()


def check_set(invariant, json_val, py_val, label):
    """One set-valued field: order carries no meaning, membership does."""
    a, b = set(json_val), set(py_val)
    check(a == b, invariant,
          f"{label}: only in JSON {sorted(a - b)}, only on the bench side "
          f"{sorted(b - a)}  (JSON {sorted(a)} vs bench {sorted(b)})")
    COMPARED.append(invariant)


def check_scalar(invariant, json_val, py_val, label):
    check(json_val == py_val, invariant,
          f"{label}: JSON {json_val!r} vs bench {py_val!r}")
    COMPARED.append(invariant)


def check_ordered(invariant, json_val, py_val, label):
    check(list(json_val) == list(py_val), invariant,
          f"{label}: JSON {list(json_val)} vs bench {list(py_val)} "
          f"(order is semantic)")
    COMPARED.append(invariant)


def main():
    request = load_request()

    install_cocotb_stub()
    bench = load_bench()
    lib = sys.modules.get("lib_bench")
    if lib is None:
        fatal("lib_bench.py", "not imported by run_bench.py as expected")
    kw = capture_bench_kwargs(bench)

    # The Python side's five fields, all of them required to have been passed.
    missing = [k for k in ("sources", "hdl_toplevel", "test_module",
                           "test_dir", "includes") if k not in kw]
    if missing:
        fatal(f"run() of {BENCH}", f"did not pass {', '.join(missing)}")
    for const in ("TIMESCALE", "BUILD_ARGS"):
        if not hasattr(lib, const):
            fatal("lib_bench.py", f"constant {const} missing")

    # The JSON side's seven, all required to be present and readable.
    take(request, "sources")
    take(request, "hdl_toplevel")
    take(request, "testbench", "module")
    take(request, "testbench", "search_path")
    take(request, "options", "timescale")
    take(request, "options", "build_args")
    take(request, "options", "includes")

    print(f"mesh build agreement: {BENCH} + lib_bench.py "
          f"vs {REQUEST}")

    # An uncompared key is exactly the drift this check exists to catch, one
    # field over -- fail on it rather than silently ignoring it.
    for level, keys, known in (("top level", request, TOP_KEYS),
                               ("testbench", request.get("testbench", {}),
                                TESTBENCH_KEYS),
                               ("options", request.get("options", {}),
                                OPTIONS_KEYS)):
        for key in sorted(set(keys) - known):
            check(False, "uncompared key",
                  f"{level}: JSON declares {key!r}, which this check does "
                  f"not compare")

    check_set("sources",
              request["sources"], [rel(p) for p in kw["sources"]],
              "compile units")
    check_scalar("hdl_toplevel",
                 request["hdl_toplevel"], kw["hdl_toplevel"],
                 "hdl toplevel")
    check_scalar("testbench.module",
                 request["testbench"]["module"], kw["test_module"],
                 "testbench module")
    check_scalar("testbench.search_path",
                 request["testbench"]["search_path"], rel(kw["test_dir"]),
                 "testbench search path")
    check_set("options.includes",
              request["options"]["includes"], [rel(p) for p in kw["includes"]],
              "include directories")
    check_ordered("options.timescale",
                  request["options"]["timescale"], lib.TIMESCALE,
                  "timescale")
    check_ordered("options.build_args",
                  request["options"]["build_args"], lib.BUILD_ARGS,
                  "build args")

    if len(COMPARED) != 7:
        # Unreachable by construction; guards the exit below against ever
        # reporting a pass that did not compare every field.
        sys.exit(f"internal error: compared {len(COMPARED)} of 7 fields")

    if FAILURES:
        broken = sorted({invariant for invariant, _ in FAILURES})
        print(f"\nagreement check: FAILED -- {len(FAILURES)} assertion(s), "
              f"field(s) broken: {', '.join(broken)}")
        for invariant, what in FAILURES:
            print(f"  {invariant}: {what}")
        print("\nrun_bench.py / lib_bench.py and klt-request-common.json no "
              "longer describe the same mesh build. Fix whichever "
              "declaration is wrong, or extend this check if a new field is "
              "legitimate. See issue #114.")
        return 1
    print("\nagreement check: ok -- all 7 fields agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
