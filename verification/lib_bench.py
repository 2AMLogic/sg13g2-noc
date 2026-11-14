"""Shared cocotb-launch preamble for the three bench drivers.

Imported (never run) by verification/endpoints/run_bench.py,
verification/mesh/run_bench.py and verification/router/runner.py, mirroring
layout/lib.sh on the shell side: this file owns what every bench must do
identically, and each driver keeps only what is genuinely its own -- which
sources it builds, which test module it runs, and how it shapes and reports
its results.

Invariants owned here (they had drifted apart across the three copies, issue #90):

- Icarus through cocotb's runner, ``build_args=["-g2005"]``, and the same
  ``timescale`` for every bench, rather than one bench depending on a
  timescale directive inside its own DUT that the others do not have.
- ``always=True`` and a per-run build directory under the caller's ``sim_build/``.
- **The per-build results file is deleted before the run.** ``sim_build/`` is
  gitignored but persists between runs on a worker, and the file is written by
  the cocotb test rather than by the build, so ``always=True`` does not clear
  it. Without this, a run whose build or import failed read the *previous*
  run's results: that false-passed the endpoints negative control, which
  reported ``tripped:`` for checks that this run never executed.
- ``build()`` and ``test()`` are wrapped, so a failure during compile,
  elaboration or import is reported as a failed run by the harness itself
  instead of killing the driver with a traceback. The simulator's own
  diagnostics still stream to stderr.
- A run passes only if it ran at least one test and none of them failed; zero
  tests is a failure, not a pass.

Importing it: the drivers run under ``python -I`` (verification/run.sh), which
implies ``-P``, so the script's own directory is not on ``sys.path`` and this
file's directory has to be added explicitly. Each driver adds it, imports, and
removes it again -- cocotb copies ``sys.path`` into the simulator's
``PYTHONPATH``, and ``verification/`` holds subdirectories (``requests/``) that
would shadow same-named installed packages in that child process.
"""
import json
import os
from pathlib import Path
from typing import NamedTuple

from cocotb_tools.runner import get_results, get_runner

BUILD_ARGS = ["-g2005"]
TIMESCALE = ("1ns", "1ps")
RESULTS_NAME = "results.json"


class BenchRun(NamedTuple):
    """One build-and-run of one bench.

    ok:     the verdict -- at least one test ran and none failed
    total:  tests reported by cocotb (0 if the build or the run raised)
    failed: tests that failed
    data:   this run's own results file, parsed, or `default` if it wrote none
    """

    ok: bool
    total: int
    failed: int
    data: object


def build_and_run(*, name, sources, hdl_toplevel, test_module, test_dir,
                  build_root, includes=(), defines=None, parameters=None,
                  env=None, results_env=None, default=None):
    """Build `sources` with Icarus and run `test_module` against them.

    name:        build subdirectory under `build_root`, one per run
    env:         environment the bench reads its configuration from
    results_env: name of the variable carrying this run's results path, if the
                 bench writes one (the path itself is chosen here)
    default:     returned as `data` when the bench wrote no results file
    """
    bdir = Path(build_root) / name
    out = bdir / RESULTS_NAME
    # Before the build, not after it: whatever goes wrong below, this run must
    # never be able to read the previous run's results.
    if out.exists():
        out.unlink()

    runner = get_runner("icarus")
    total = failed = 0
    try:
        runner.build(
            sources=list(sources),
            hdl_toplevel=hdl_toplevel,
            includes=list(includes),
            defines=dict(defines or {}),
            parameters=dict(parameters or {}),
            build_args=list(BUILD_ARGS),
            timescale=TIMESCALE,
            build_dir=bdir,
            always=True,
        )
        environ = dict(env or {})
        if results_env:
            environ[results_env] = str(out)
        os.environ.update(environ)
        xml = runner.test(
            hdl_toplevel=hdl_toplevel,
            test_module=test_module,
            test_dir=test_dir,
            build_dir=bdir,
            results_xml=bdir / "results.xml",
        )
        total, failed = get_results(xml)
    except (Exception, SystemExit):
        total = failed = 0

    data = json.loads(out.read_text()) if out.exists() else default
    return BenchRun(total > 0 and failed == 0, total, failed, data)
