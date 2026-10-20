# sg13g2-noc specification

Status key: **Ratified** = fixed by the README target table or the issue text,
recorded as-is. **Recommended** = a preference call drafted by the agent;
becomes ratified only when a reviewer merges this file. **Deferred** = names its
unblocker and decider. No README target, fallback or stretch value is relaxed
here.

## 1. Parameter table

| Parameter | Target | Fallback | Stretch | Status |
|---|---|---|---|---|
| Topology | 2 x 2 mesh, 5-port routers (N, E, S, W, local) | 1 router + 2 endpoints | 4 x 4 mesh | Ratified |
| Routing | dimension-ordered XY (Ratified); wormhole switching (Recommended: with 4-flit buffers and 16-flit packets, cut-through or store-and-forward would need packet-sized buffers) | — | — | Ratified / Recommended |
| Flit width | 32-bit data | — | 64-bit | Ratified |
| Header | see section 2 | — | — | Recommended |
| Flow control | credit-based (0002) | — | — | Recommended |
| Buffer depth | 4 flits per input port | — | — | Recommended |
| Virtual channels | 0 | — | — | Ratified (issue #2: zero at the target; the README table does not mention VCs) |
| Router pipeline | 2 cycles/hop in the router + 1 cycle link register = 3 cycles/hop zero-load | — | — | Recommended |
| Router source | in-repo router; FlooNoC as reference only (0001) | — | — | Recommended |
| Endpoints | traffic generator + checker per node | — | AXI4-Lite endpoint | Ratified |
| Clocking | one clock domain, no CDC | — | — | Ratified |
| Reset | single active-low synchronous reset, registered once at each tile edge; deassertion skew across tiles under 1 cycle, checked as ordinary STA paths | — | — | Recommended |
| Signoff clock | 100 MHz post-route, slow corner | 50 MHz | 200 MHz | Ratified |
| Correctness | no loss, duplication or reordering per src–dst pair | — | — | Ratified |
| Signoff | DRC + LVS clean; STA closed at every corner in section 4 | — | — | Ratified |
| Tile size / pitch | — | — | — | Deferred (0003): unblocker #4 synthesis area; decider reviewer |
| Abut vs channel; hierarchical vs flat P&R | abut, hierarchical (0003) | channel | — | Recommended |
| Long-link buffering | one link register per direction at tile edge; flow inserts buffers (0003) | — | — | Recommended |
| Latency/throughput patterns | section 5 | — | — | Recommended |

## 2. Flit and header format (Recommended)

Link signals per direction: `valid`, `last`, `data[31:0]`; reverse direction:
`credit`. A packet is a head flit followed by zero or more body flits; `last`
is set on the final flit (a one-flit packet is a head with `last`).

Head flit: `data[31:30]` dest X, `[29:28]` dest Y, `[27:26]` source X,
`[25:24]` source Y, `[23:16]` packet length in flits (diagnostic), `[15:0]`
per-(source, destination) sequence number — the packet id the scoreboard in
section 5 keys on; it wraps at 65536, which bounds one run's packets per pair.
Coordinates are 2 bits so 4 x 4 (stretch) needs no format change.
Body flits are 32-bit payload. Packets are never interleaved on a link
(wormhole, no VCs).

## 3. Deadlock freedom (XY routing, no VCs)

Claim: wormhole XY routing on a 2-D mesh without virtual channels is
deadlock-free.

Argument. Number the unidirectional channels so that every X channel is lower
than every Y channel, and within each of the four direction classes (+X, −X,
+Y, −Y) a channel's number increases along its direction of travel (so +X
channels increase with x, −X channels increase as x decreases, and likewise in
y). Injection channels are numbered below all X channels and ejection channels
above all Y channels. XY routing only takes a channel after channels of lower
number: a packet traverses X channels, then Y channels, never Y then X, and
within a dimension moves monotonically in one direction, so its channel
sequence is strictly increasing. A wormhole packet blocked across several
routers holds consecutive channels of that sequence, so every edge of the
channel dependency graph goes from a lower to a higher number, the graph is
acyclic, and by Dally and Seitz routing with an acyclic CDG is deadlock-free.

Assumptions (must hold in RTL and are tested):
1. Routing is deterministic XY: no Y-to-X turn and no 180° turn.
2. Endpoints always eventually sink ejected flits (the checker never
   backpressures indefinitely). Otherwise a consumption dependency closes a
   cycle outside the CDG.
3. No request/response dependency between endpoints: the traffic generator does
   not wait on received flits. A request/reply protocol would need separate VCs
   or networks and is out of scope.
4. Credits are never lost or duplicated; buffer depth is at least 1 per input.
5. Each output arbiter is round-robin and holds its grant until `last`, so a
   granted packet is not starved. Determinism excludes livelock.

Buffer sizing does not affect deadlock freedom under 1–4, only throughput.

## 4. PVT corners for STA

Library: `sg13g2_stdcell`, core supply 1.2 V nominal. File names read from
IHP-Open-PDK commit `5e6d592e4002946a4616f798c357f0f3c06cf3b6` (upstream HEAD on
2026-10-17), directory `ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/`. The repo's
pin of record is `layout/pdk.json` (#4): release `v0.3.0`, which is 638 commits
behind that HEAD, but all six Liberty files in this directory are byte-identical
at both refs (same git blob ids, checked 2026-10-20), so the names and values
below hold for the pinned release.

| Corner | Liberty file | Supply / temperature |
|---|---|---|
| Slow (signoff clock, setup) | `sg13g2_stdcell_slow_1p08V_125C.lib` | 1.08 V, 125 °C |
| Typical | `sg13g2_stdcell_typ_1p20V_25C.lib` | 1.20 V, 25 °C |
| Fast (hold) | `sg13g2_stdcell_fast_1p32V_m40C.lib` | 1.32 V, −40 °C |

Supply and temperature were confirmed against the library headers at the pinned
commit (each file, lines 46–48 and its `operating_conditions` block):
`nom_voltage : 1.08 / 1.2 / 1.32`, `nom_temperature : 125 / 25 / -40`,
`nom_process : 1` in all three; library `revision : 0.1.4`, dated 2025-11-04.
So the three files are exactly 1.2 V −10% / nominal / +10%. The
`slow_1p35V_125C`, `typ_1p50V_25C` and `fast_1p65V_m40C` files in the same
directory (headers 1.35 / 1.5 / 1.65 V) are the 1.5 V ±10% set and are not used;
the design's `klt sta` request lists only the three corners above, unlike the
smoke fixture's, which fans out to all six.

## 5. Verification plan

Scoreboard (cocotb, per node, built from generator and checker logs):
- **No loss**: every injected packet id appears at its destination exactly once.
- **No duplication**: a repeated (src, id) at a checker fails the run.
- **In order**: per (src, dst) pair, sequence numbers arrive strictly increasing.
- **Payload integrity**: received flit contents equal what was injected.
- A run ends only after drain; undrained flits fail it.

Traffic patterns: uniform random, transpose, hotspot (one node receiving 50% of
traffic). Each is swept over injection rates 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0
flits/node/cycle with packet lengths 1, 4 and 16 flits. Latency and throughput
are quoted only with pattern, rate and packet length, and labelled simulated.

Every run injects a fixed number of packets per node (offered at the stated
rate; at rates above saturation — the hotspot at 1.0 offers two flits/cycle to
one ejection port — the generator queues them) and then stops, so "drain" is
well defined: the run passes only if every injected packet is accepted within a
stated cycle bound after injection ends. Latency is measured from generation,
not from entry to the network, so source queueing counts.

Adversarial deadlock test: all nodes inject long packets simultaneously at rate
1.0 to the diagonally opposite node (all five ports in the isolated router
test); a hotspot run with buffer depth 1; and randomized, bounded sink stalls.
It passes only if all packets drain within the bound above; a watchdog fails
the run on no progress (no flit accepted anywhere for a stated number of
cycles). This targets the argument in section 3, including assumption 2.

Also checked: a credit-conservation assertion (credits + buffered flits =
depth), and reset applied mid-traffic.

## 6. Open questions

1. **Traffic patterns and rates**: answered in section 5.
2. **Does the SG13G2 starter deck cover a standard-cell tile?** Deferred.
   Unblocker: results of toolchain smoke #4. Decider: the reviewer of #4. Any
   gap becomes a generic issue on `2AMLogic/klayout-tools`.
3. **Long-link buffering**: answered in 0003 (register per direction, flow
   inserts buffers). Whether the flow's repair is adequate is Deferred to the
   first post-route STA (unblocker: mesh P&R; decider: reviewer).
