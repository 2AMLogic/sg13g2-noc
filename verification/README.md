# verification

Cold start (needs `iverilog` at the version in `layout/tools.json`, `uv`, `jq`,
and network the first time):

```
verification/run.sh router                       # DEPTH=4, then DEPTH=1; exit 0 = all pass
NEG=NEG_YX_TURN verification/run.sh router       # negative control, must exit 1
NEG=NEG_DROP_CREDIT verification/run.sh router   # negative control, must exit 1
```

cocotb is not installed on the worker (a worker-spec gap, reported on the PR).
`run.sh` creates `verification/.venv` (gitignored) and installs the cocotb
version pinned in `layout/tools.json` into it; nothing host-wide is touched, and
it refuses to run on a pin mismatch.

## `router/`

`test_noc_router.py` drives `rtl/noc_router.v` in isolation at (X, Y) = (1, 1) of
a notional 4 x 4 mesh. The bench plays the tile edge: one link register per
direction (forward flit, reverse credit), so the credit round trip is the 4
cycles 0002 sizes depth 4 for. Sources obey credits; sinks buffer `DEPTH` flits
and return a credit when they consume, optionally with random bounded stalls.

Checks, named in every failure message:

- `[scoreboard]` (spec section 5): no loss, no duplication, in order per
  (source input, destination), payload and `last` intact (which also catches
  interleaving), packet leaves the output XY says, injected equals delivered.
- `[credit-conservation]`: every cycle, for all ten links, source/router credits +
  flits in flight or buffered + credits in flight = `DEPTH`.
- `[watchdog]`: no flit accepted at any output for 100 cycles while flits are in
  the system.
- `[drain]`: everything accepted within 200 + 4 x (max stall + 2) x (flits still
  in the network when injection ends) cycles.

Tests: a packet from every input to every output it can legally reach (1 and 4
flits); zero-load latency; back-to-back packets; two inputs contending for one
output; random legal traffic at rates 0.05 / 0.3 / 0.7 / 1.0 with lengths 1, 4,
16; the adversarial test (all five inputs, 16-flit packets, rate 1.0, random
sink stalls, then a four-neighbour hotspot to the local output); uncontended
throughput. `run.sh` runs the whole set at `DEPTH=4` and `DEPTH=1`.

Latency and throughput lines are labelled SIMULATED and carry their pattern,
length and DEPTH. In the packet header the source field `[27:24]` holds the
input port number here, standing in for the source node.

Not covered here: reset applied mid-traffic and the rate x length sweeps
(mesh/endpoint benches), and the watchdog has no negative control of its own
(the credit-drop control is caught first by the credit assertion).
