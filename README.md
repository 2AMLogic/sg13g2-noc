# sg13g2-noc

A small network-on-chip mesh on
[IHP SG13G2](https://github.com/IHP-GmbH/IHP-Open-PDK), a 130 nm SiGe
BiCMOS open PDK — narrow-link routers in a 2-D mesh, FlooNoC-class — designed
by AI agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools) and the
open-source cocotb + Icarus, Yosys and OpenROAD flow.

**Status: spec ratified; router and endpoints verified in isolation.** The
mesh, synthesis, place-and-route and signoff are not done yet.

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

## T1 evidence

The block's machine-readable T1 state is
[`manifests/sg13g2-noc.json`](manifests/sg13g2-noc.json) (the block manifest;
`evidence` cites the testbench-inventory attestation, item 9, and the repo-hygiene attestation, item 10; every other item is unmet) and its verdict of record is
[`manifests/sg13g2-noc.signoff.json`](manifests/sg13g2-noc.signoff.json). CI
(`.github/workflows/signoff.yml`) fails if the committed verdict no longer
reproduces. The `klayout-tools` version is pinned in `.github/klt-version`.
Regenerate the verdict with:

```
uvx --from "klayout-tools==$(cat .github/klt-version)" klt signoff --manifest manifests/sg13g2-noc.json --format json > manifests/sg13g2-noc.signoff.json
```

(`klt signoff` exits 3 when items are unmet; the report is still written.)

## Reproducing results

Every bench is driven by `verification/run.sh`. Icarus and Yosys are worker
tools; cocotb is provisioned per run in a throwaway `uvx` environment at the
version pinned in `layout/tools.json`. Details: [verification/README.md](verification/README.md).

| Command | What it proves | Approx. runtime |
|---|---|---|
| `verification/run.sh router` | Router bench at `DEPTH=4` then `DEPTH=1`; exit 0 = all checks pass | see `verification/README.md` |
| `NEG=NEG_YX_TURN verification/run.sh router` | Negative control: a YX turn is caught; must exit 1 | as above |
| `NEG=NEG_DROP_CREDIT verification/run.sh router` | Negative control: a dropped credit is caught; must exit 1 | as above |
| `verification/run.sh endpoints` | Generator-to-checker loopback sweep; no loss, duplication or reordering; writes `verification/endpoints/results.json` | about 20 s |
| `verification/run.sh endpoints --neg corrupt` (or `skipseq`) | Negative control: the checker trips and names the check; must exit non-zero | seconds |
| `verification/run.sh endpoints-selftest` | Runs both endpoint controls; exit 0 only if both trip | about 20 s |
| `verification/run.sh mesh` | 2 x 2 mesh scoreboard, patterns x rates x lengths, adversarial deadlock runs, depth 1, reset mid-traffic; exit 0 = all pass; writes `verification/mesh/results.json` | about 3.5 min |
| `NEG=NEG_DROP_CREDIT\|NEG_CORRUPT\|NEG_SKIPSEQ verification/run.sh mesh` | Mesh negative controls: the tripped check is named; must exit 1 | about 15 s each |
| `verification/run.sh all` | Every bench plus the mesh controls; the item-9 cold start | about 4 min |

The item-9 attestation (`attest/item9.json`, `evidence/item9.json`) is regenerated
and checked the same way with `--attest 9`. The item-10 attestation is regenerated and checked with:

```
uvx --from "klayout-tools==$(cat .github/klt-version)" klt signoff --attest 10 --inventory attest/item10.json -o evidence/item10.json
uvx --from "klayout-tools==$(cat .github/klt-version)" klt signoff --attest 10 --inventory attest/item10.json --check evidence/item10.json
```

then the verdict command above. Latency and throughput are simulated, never
measured.

## Target specification (ratified 2026-10-20 by the merge of #6; see [spec/noc.md](spec/noc.md))

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
measured silicon. **Current position: router verified in isolation (#21); traffic generator/checker
loopback verified (#20); 2 x 2 mesh verified under traffic (#25, simulated RTL). Post-route, P&R and signoff: not yet.**

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
