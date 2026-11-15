"""Hermetic guard on the klt functional-verification path (issue #122).

    python3 -I verification/check_fv_requests.py    # exit 0 = everything resolves

`verification/fv.sh` is the only driver of the `klt functional-verification`
requests behind the three attested `evidence/item5-functional-verification-mesh-*.json`
envelopes, and nothing else exercises it: a real run needs Icarus, cocotb and a
uvx fetch of pinned klt (~3 min), so signoff.yml cannot run it (item 9's cold
start is local_only). That is how the commit hoisting `bench_vocab` into
`verification/common` (ecf7ae5) left `fv.sh` broken on main for 30 commits --
the request files and the bench's imports were only ever exercised by hand.

This check asks `fv.sh --emit-requests` for fv.sh's *own* request assembly and
Python path (one JSON object on stdout; no re-declaration here, so a future
hoist cannot leave a checker describing a stale shape) and asserts, with no
simulator and no klt:

- every `sources` and `options.includes` entry exists, resolved relative to
  `verification/requests/` (where klt resolves them);
- `testbench.search_path` is a directory holding `<testbench.module>.py`;
- every module the testbench imports (collected with `ast`, executing nothing)
  resolves against the search path plus the PYTHONPATH fv.sh exports -- except
  RUNTIME_PROVIDED below, the packages a klt extra installs on the bench's
  runtime Python. A decorated import (cocotb.test() runs at import time) would
  make importing the module to probe it both a simulator dependency and a red
  herring for legitimate bench changes; ast + find_spec is fooled by neither.
"""
import ast
import importlib.util
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
FV = HERE / "fv.sh"

# Modules the pinned klt extra (layout/tools.json: functional-verification) provides
# on the bench's runtime Python, so find_spec legitimately misses them here -- CI and
# the workers install neither cocotb nor Icarus host-wide. Keep this short and
# explicit: a name belongs here only if the klt extra installs it at run time;
# everything else must resolve from the request's search_path plus fv.sh's PYTHONPATH.
RUNTIME_PROVIDED = {"cocotb"}


def bench_imports(module_file):
    """Top-level import names in the testbench module; the module is never executed."""
    tree = ast.parse(module_file.read_text(), filename=str(module_file))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def unresolved_imports(module_file, pythonpath):
    """Import names that resolve from neither the search path nor fv.sh's PYTHONPATH."""
    saved = sys.path[:]
    sys.path[:0] = [str(module_file.parent)] + [str(p) for p in pythonpath]
    try:
        out = []
        for mod in bench_imports(module_file):
            if mod in RUNTIME_PROVIDED:
                continue
            try:
                found = importlib.util.find_spec(mod)
            except (ImportError, ValueError):
                found = None
            if found is None:
                out.append(mod)
        return sorted(out)
    finally:
        sys.path[:] = saved


def main():
    emit = subprocess.run(["bash", str(FV), "--emit-requests"],
                          capture_output=True, text=True)
    if emit.returncode != 0:
        sys.stderr.write(emit.stderr)
        print(f"check_fv_requests: fv.sh --emit-requests exited {emit.returncode}",
              file=sys.stderr)
        return 1
    try:
        spec = json.loads(emit.stdout)
        request_dir = pathlib.Path(spec["request_dir"])
        pythonpath = [pathlib.Path(p) for p in spec["pythonpath"]]
    except (ValueError, KeyError, TypeError) as e:
        print(f"check_fv_requests: cannot use fv.sh --emit-requests output: {e}",
              file=sys.stderr)
        return 1

    problems = []
    benches = {}  # testbench module file -> request names carrying it
    for name, req in sorted(spec["requests"].items()):
        if not isinstance(req, dict):
            problems.append(f"{name}: assembled request is not a JSON object")
            continue
        # the assembly sets each of these from klt-request-common.json; its going
        # missing is itself a drift, not a vacuous pass
        for field, want in (("sources", list), ("options", dict), ("testbench", dict)):
            if not isinstance(req.get(field), want):
                problems.append(f"{name}: assembled request carries no {field}")
        if not isinstance(req.get("sources"), list):
            continue
        for entry in req["sources"]:
            if not (request_dir / entry).exists():
                problems.append(f"{name}: sources entry missing: {entry}")
        options = req.get("options") or {}
        for entry in options.get("includes") or []:
            if not (request_dir / entry).exists():
                problems.append(f"{name}: options.includes entry missing: {entry}")
        tb = req.get("testbench") or {}
        search_path, module = tb.get("search_path"), tb.get("module")
        if not search_path or not module:
            problems.append(f"{name}: testbench needs search_path and module")
            continue
        if not (request_dir / search_path).is_dir():
            problems.append(f"{name}: testbench.search_path is not a directory: {search_path}")
            continue
        module_file = (request_dir / search_path / f"{module}.py").resolve()
        if not module_file.is_file():
            problems.append(f"{name}: testbench module missing: {search_path}/{module}.py")
            continue
        benches.setdefault(module_file, []).append(name)

    for module_file, users in sorted(benches.items()):
        unresolved = unresolved_imports(module_file, pythonpath)
        if unresolved:
            rel = module_file.relative_to(HERE.parent)
            problems.append(
                f"{', '.join(users)}: imports of {rel} resolve from neither the "
                f"testbench search_path nor fv.sh's PYTHONPATH: {', '.join(unresolved)}")

    if problems:
        for p in problems:
            print(f"check_fv_requests: {p}", file=sys.stderr)
        print(f"check_fv_requests: {len(problems)} problem(s) on the fv.sh path",
              file=sys.stderr)
        return 1
    print(f"check_fv_requests: {len(spec['requests'])} request(s) assemble and resolve; "
          f"bench imports satisfiable ({', '.join(sorted(RUNTIME_PROVIDED))} runtime-provided)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
