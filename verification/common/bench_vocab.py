"""Scoreboard vocabulary shared by the endpoint-side cocotb benches (issue #99).

Imported (never run) by verification/endpoints/test_endpoints.py and
verification/mesh/test_mesh.py. It is the test-module counterpart of
verification/lib_bench.py: lib_bench.py owns what every bench *driver* must do
identically, this file owns the vocabulary the benches must agree on -- the
checker's flag names and their text, the sweep grid, and the two derived bounds.

Owned here because both benches had already drifted apart on it (issue #99):
the same five flag names and the same grid were transcribed twice, and the
flag-text table had acquired two spellings. A sixth check added to
rtl/noc_tchk.v must be added in exactly one place, not two, because a bench
that misses the edit does not fail -- it silently stops looking at the new flag.

Not owned here, and deliberately so: anything a bench genuinely does
differently. Each bench keeps its own ``PATTERNS`` (the mesh adds a fourth,
"diagonal"), its own node geometry (``NN``, ``ID``) and its own ``HOT``
encoding (a node id in the mesh, coordinates in the endpoints bench). Each also
keeps its own failure-message prefix: the mesh names every check in brackets
(``[checker]``, ``[scoreboard]``, ... -- test_mesh.__doc__ lists them), the
endpoints bench does not. Unifying those prefixes is a separate question.

Importing it: this directory holds *only* this module, and each driver puts
this directory -- never ``verification/`` -- on ``sys.path`` before ``test()``.
cocotb copies ``sys.path`` into the simulator's ``PYTHONPATH``, and
``verification/`` holds subdirectories (``requests/``) that would shadow
same-named installed packages in that child process; see lib_bench.__doc__.
Keep that rule when adding to this directory: whatever lands here becomes a
top-level importable name inside the simulator.
"""

# ---- sweep grid ----
RATES = [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
LENGTHS = [1, 4, 16]
NPKTS = 64          # packets per run (per node, in the mesh); seq per (src, dst)
                    # pair stays far below 65536
WATCHDOG = 400      # cycles with no accepted flit while packets are outstanding

# ---- the checker's sticky error flags ----
# These are the output ports of rtl/noc_tchk.v:42-:46 (e_loss, e_dup, e_payload,
# e_dest, e_frame), read off the DUT by name. Adding a check to noc_tchk.v means
# adding it to CHECK_NAMES and CHECK_TEXT here -- this is the one place to edit.
CHECK_NAMES = ["e_loss", "e_dup", "e_payload", "e_dest", "e_frame"]
CHECK_TEXT = {
    "e_loss": "sequence (loss/skip)",
    "e_dup": "sequence (duplicate/reorder)",
    "e_payload": "payload",
    "e_dest": "destination",
    "e_frame": "framing",
}


def thresh(rate, length):
    """cfg_thresh for an offered rate: the generator's 16-bit injection threshold."""
    return round(65536 * rate / length)


def drain_bound(total_flits, stall_max, depth):
    """Cycles allowed after the last packet is generated: every flit in the system at
    the worst per-flit pace (credit round trip + sink stall + buffer depth), plus slack.

    total_flits is the whole system's outstanding flit count -- packets * length,
    summed over every injecting node.
    """
    return total_flits * (stall_max + 4 + depth) + 1000
