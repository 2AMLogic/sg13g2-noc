# sg13g2-noc

A small network-on-chip mesh on
[IHP SG13G2](https://github.com/IHP-GmbH/IHP-Open-PDK), a 130 nm SiGe
BiCMOS open PDK — narrow-link routers in a 2-D mesh, FlooNoC-class — designed
by AI agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools) and the
open-source cocotb + Icarus, Yosys and OpenROAD flow.

**Status: just opened, specification phase.** Nothing is designed yet.

**Built agent-native.** Every specification, decision record, testbench, and
line of documentation here is produced by AI agents working from a ratified
spec and an append-only evidence trail — not human-authored work that agents
merely assisted with. Verification is the product: every claim traces to a
recorded result. Where the agents hit friction with the open-source tooling —
most often [klayout-tools](https://github.com/2AMLogic/klayout-tools) — that
friction is filed as a public issue against the tool itself, so the fix
benefits everyone using SG13G2, not just this repo.

## Why this block, on this PDK

Open NoC generators exist and are well documented, but to our knowledge none
has been carried through to a tape-out on an open PDK. A NoC is also a block
whose difficulty is **between** tiles rather than inside them: identical
router tiles stepped and repeated, long point-to-point links crossing tile
boundaries, and timing paths that leave one tile's placement
and land in another's. Hierarchical place-and-route, tile abutment, and
link timing across a tiled floorplan are the tool surface this canary exists
to stress.

SG13G2's standard-cell library (`sg13g2_stdcell`) runs from a 1.2 V core
supply.

## Standing on public prior art

- **[FlooNoC](https://github.com/pulp-platform/FlooNoC)** (PULP Platform,
  ETH Zurich / University of Bologna) — a configurable NoC with narrow and
  wide links, routers, and network interfaces. This block targets the
  narrow-link configuration. Whether its SystemVerilog is adopted as-is,
  converted, or used as a reference for a smaller in-repo router is decided
  in `spec/`, with its licence checked for compatibility.

## Scope

- **In scope**: routers, the mesh topology and links, simple network
  interfaces at each node, on-chip traffic generators and checkers so the
  mesh can be exercised without a host, and the physical design and timing
  closure of the tiled mesh.
- **Not in scope**: wide links, compute or memory at the endpoints, a
  processor, clock-domain crossing between tiles (the mesh is one clock
  domain at the target), and the pad ring.

## Target specification (DRAFT — ratified when the spec PR merges, see issue #2 and [spec/noc.md](spec/noc.md))

| Parameter | Target | Fallback | Stretch |
|---|---|---|---|
| Topology | 2 x 2 mesh, 5-port routers | 1 router + 2 endpoints | 4 x 4 mesh |
| Routing | dimension-ordered (XY), deadlock-free by construction | — | — |
| Link | 32-bit narrow flit, credit-based flow control, 4-flit input buffers, no virtual channels (`spec/decisions/0002`) | — | 64-bit |
| Endpoints | traffic generator + checker per node | — | AXI4-Lite endpoint |
| Signoff clock (post-route STA, slow corner) | 100 MHz | 50 MHz | 200 MHz |
| Correctness | no flit loss, duplication or reordering per source–destination pair | — | — |
| Signoff | DRC + LVS clean, STA closed at every ratified corner (slow 1.08 V/125 °C, typ 1.20 V/25 °C, fast 1.32 V/−40 °C) | — | — |

Latency and throughput are reported from simulation under named traffic
patterns (uniform random, transpose, hotspot) at stated injection rates.

Maturity ladder: spec ratified → router verified in isolation → mesh
verified under traffic → synthesized with timing met → tiles placed and
routed, DRC/LVS-clean → mesh assembled, link timing closed → shuttle seat →
measured silicon. **Current position: pre-spec.**

## Repo layout

```
spec/          ratified spec + decision records
rtl/           router, link, network interface, traffic generator/checker
verification/  cocotb testbenches, scoreboards, traffic-pattern runs
layout/        tile and mesh GDS + DRC/LVS reports + STA reports (klayout-tools driven)
measurements/  silicon characterization (empty until tape-out)
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
