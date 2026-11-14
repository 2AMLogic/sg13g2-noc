"""Hermetic self-test for lib_bench.py's two anti-false-pass invariants.

    python3 -I verification/selftest_lib_bench.py     # exit 0 = both hold

Run directly, not through verification/run.sh: that script validates the pinned
Icarus and cocotb versions before it dispatches, and this test deliberately
needs neither. cocotb_tools.runner is stubbed in sys.modules before lib_bench
is imported, so the only thing under test is lib_bench's own ordering and
verdict -- no simulator, no build, no sim_build/ directory is touched.

The invariants (lib_bench.__doc__, issue #90, PR #91, issue #92):

- **stale-results deletion** -- the per-build results file is deleted *before*
  runner.build(), so a run whose build, elaboration or import fails cannot read
  the previous run's results. sim_build/ is gitignored but persists between runs
  on a worker, and the file is written by the cocotb test rather than by the
  build, so always=True does not clear it.
- **zero-test rejection** -- a run passes only if it ran at least one test and
  none failed; zero tests is a failure, not a pass.

They are observable only through two different fields of BenchRun, and each is
blind to the other's mutation (measured on issue #92). When build() raises:
deleting the unlink leaves `ok` False -- the zeroed total fails `total > 0`
independently -- while `data` silently becomes the stale dict, which is what the
drivers narrate from (endpoints/run_bench.py reads data["points"] to print its
`tripped:` lines). Weakening the verdict to `failed == 0` leaves `data` correct
while `ok` becomes True for a run that never compiled. So the stale-results
case below asserts on *both* fields; one alone would be insensitive to one hole.

The third scenario is a positive control: without it, a build_and_run that
failed every run and returned `default` for every data would satisfy the other
two. A test of a false-pass guard must not itself be satisfiable by a harness
that passes nothing.
"""
import importlib.util
import json
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE / "lib_bench.py"

# Distinguishable on sight in a failure message, and nothing like each other.
STALE = {"selftest": "stale results, written by an earlier run",
         "points": [{"problems": ["checker error flag: payload check"]}]}
DEFAULT = {"selftest": "default: this run wrote no results"}
FRESH = {"selftest": "written by this run",
         "points": [{"problems": []}]}

FAILURES = []


def check(ok, invariant, what):
    """Record one assertion. Keeps going, so one run reports every break."""
    print(f"  {'ok  ' if ok else 'FAIL'}  {what}")
    if not ok:
        FAILURES.append((invariant, what))


class StubRunner:
    """Stands in for cocotb's IcarusRunner, driven by `state`."""

    def __init__(self, state):
        self.state = state

    def build(self, **kwargs):
        self.state.built = True
        # The real runner creates the build directory before it compiles, so a
        # raising build() still leaves one behind -- which is the whole reason
        # a stale results.json can survive in it.
        Path(kwargs["build_dir"]).mkdir(parents=True, exist_ok=True)
        if self.state.build_raises:
            raise RuntimeError("stub: compile/elaboration failed")

    def test(self, **kwargs):
        self.state.tested = True
        if self.state.on_test is not None:
            self.state.on_test(Path(kwargs["build_dir"]))
        return Path(kwargs["build_dir"]) / "results.xml"


def install_cocotb_stub():
    """Put a stub cocotb_tools.runner in sys.modules. Call before importing.

    lib_bench does `from cocotb_tools.runner import get_results, get_runner` at
    module scope, so the stub has to be in sys.modules first. It also shadows a
    real cocotb if one happens to be installed, which keeps this test identical
    on a bare runner and on a worker that has the bench environment.
    """
    state = types.SimpleNamespace(build_raises=False, results=(0, 0),
                                  on_test=None, built=False, tested=False)

    def get_runner(name):
        if name != "icarus":
            raise AssertionError(f"stub: unexpected simulator {name!r}")
        return StubRunner(state)

    def get_results(xml):
        return state.results

    runner = types.ModuleType("cocotb_tools.runner")
    runner.get_runner = get_runner
    runner.get_results = get_results
    pkg = types.ModuleType("cocotb_tools")
    pkg.__path__ = []
    pkg.runner = runner
    sys.modules["cocotb_tools"] = pkg
    sys.modules["cocotb_tools.runner"] = runner
    return state, get_runner, get_results


def load_lib_bench():
    """Import lib_bench.py by path.

    The drivers insert verification/ into sys.path and remove it again; by path
    is equivalent here and leaves sys.path alone. Either way it cannot be a
    plain `import lib_bench`: python3 -I implies -P, so this script's own
    directory is not on sys.path.
    """
    if not LIB.is_file():
        sys.exit(f"selftest: {LIB} not found")
    spec = importlib.util.spec_from_file_location("lib_bench_under_test", LIB)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_bench(lib, state, build_root, name):
    """Call build_and_run the way the drivers do, minus anything real.

    results_env is left unset on purpose: the results path is chosen inside
    build_and_run either way, and passing one would make it os.environ.update()
    this process. Nothing here depends on the bench reading the path.
    """
    state.built = state.tested = False
    return lib.build_and_run(
        name=name,
        sources=[],
        hdl_toplevel="dut",
        test_module="test_dut",
        test_dir=build_root,
        build_root=build_root,
        default=DEFAULT,
    )


def scenario_stale_results(lib, state, build_root):
    """build() raises with a previous run's results.json on disk."""
    print("stale-results deletion: build() raises over a stale results.json")
    name = "neg_stale"
    out = Path(build_root) / name / lib.RESULTS_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(STALE))

    state.build_raises = True
    # (1, 0) would be a passing run: proves the verdict is lib_bench's own and
    # not something the stub handed it. build() raises before test() runs, so
    # these numbers must never reach the verdict.
    state.results = (1, 0)
    state.on_test = None
    res = run_bench(lib, state, build_root, name)

    check(state.built and not state.tested, "selftest premise",
          "build() was reached and raised before test() ran")
    check(res.data != STALE, "stale-results deletion",
          "BenchRun.data is not the stale file's contents")
    check(res.data == DEFAULT, "stale-results deletion",
          "BenchRun.data is the `default` the caller passed")
    check(not out.exists(), "stale-results deletion",
          "the stale results.json was deleted before the build")
    # Same scenario, the other invariant: a run whose build raised has no
    # passing tests to its name, whatever is on disk.
    check(res.ok is False, "zero-test rejection",
          "BenchRun.ok is False when build() raised")
    check(res.total == 0 and res.failed == 0, "zero-test rejection",
          "BenchRun.total and .failed are 0 when build() raised")


def scenario_zero_tests(lib, state, build_root):
    """The run completes but cocotb reports no tests at all."""
    print("zero-test rejection: a run that executed no tests")
    name = "neg_zero"
    state.build_raises = False
    state.results = (0, 0)
    state.on_test = None
    res = run_bench(lib, state, build_root, name)

    check(state.tested, "selftest premise",
          "the run completed and test() ran")
    check(res.ok is False, "zero-test rejection",
          "BenchRun.ok is False when total == 0 and failed == 0")
    check(res.total == 0, "zero-test rejection",
          "BenchRun.total reports the 0 tests cocotb counted")
    check(res.data == DEFAULT, "stale-results deletion",
          "BenchRun.data is the `default` when the run wrote no results")


def scenario_passing_run(lib, state, build_root):
    """Positive control: the guards must not fail a run that really passed.

    A stale file is planted here too, so this also shows the deletion reads
    *this* run's results rather than resurrecting the previous ones.
    """
    print("positive control: a passing run over a stale results.json")
    name = "pos_pass"
    out = Path(build_root) / name / lib.RESULTS_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(STALE))

    state.build_raises = False
    state.results = (3, 0)
    state.on_test = lambda bdir: (bdir / lib.RESULTS_NAME).write_text(
        json.dumps(FRESH))
    res = run_bench(lib, state, build_root, name)

    check(state.tested, "selftest premise",
          "the run completed and test() ran")
    check(res.ok is True, "no vacuous pass",
          "BenchRun.ok is True when 3 tests ran and none failed")
    check(res.data == FRESH, "no vacuous pass",
          "BenchRun.data is this run's own results file")
    check(res.data != STALE, "stale-results deletion",
          "BenchRun.data is not the stale file a passing run overwrote")


def scenario_failing_tests(lib, state, build_root):
    """A run whose tests ran and failed is a failure, not a pass."""
    print("no vacuous pass: a run with failing tests")
    name = "neg_failed"
    state.build_raises = False
    state.results = (3, 1)
    state.on_test = lambda bdir: (bdir / lib.RESULTS_NAME).write_text(
        json.dumps(FRESH))
    res = run_bench(lib, state, build_root, name)

    check(res.ok is False, "no vacuous pass",
          "BenchRun.ok is False when 1 of 3 tests failed")
    check((res.total, res.failed) == (3, 1), "no vacuous pass",
          "BenchRun.total and .failed carry cocotb's counts")


def main():
    state, get_runner, get_results = install_cocotb_stub()
    lib = load_lib_bench()
    # If cocotb were importable for real, lib_bench would have bound its
    # functions instead and nothing below would be testing the stub.
    if (lib.get_runner, lib.get_results) != (get_runner, get_results):
        sys.exit("selftest: lib_bench did not pick up the cocotb stub")
    print(f"selftest: {LIB} under a stubbed cocotb_tools.runner")

    with tempfile.TemporaryDirectory(prefix="selftest-lib-bench-") as tmp:
        # A fresh build_root per run: no real sim_build/ is read or written,
        # and there is no state to carry between invocations.
        for scenario in (scenario_stale_results, scenario_zero_tests,
                         scenario_passing_run, scenario_failing_tests):
            scenario(lib, state, tmp)

    if FAILURES:
        broken = sorted({invariant for invariant, _ in FAILURES})
        print(f"\nselftest: FAILED -- {len(FAILURES)} assertion(s), "
              f"invariant(s) broken: {', '.join(broken)}")
        for invariant, what in FAILURES:
            print(f"  {invariant}: {what}")
        print("\nlib_bench.py no longer guarantees what verification/README.md "
              "and its own docstring claim. See issue #92.")
        return 1
    print("\nselftest: ok -- stale-results deletion and zero-test rejection "
          "both hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
