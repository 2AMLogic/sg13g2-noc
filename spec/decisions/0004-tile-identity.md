# 0004 — Tile identity: node id as a port

- **Status**: Proposed (reviewer to confirm at PR review)
- **Issue**: #44 (part (a) of #26)
- **Blocks**: #45 (part (b), tile place-and-route) via the RTL change in #47

## Problem

`rtl/noc_tile.v` takes the node id as parameters (`parameter [1:0] X`, `Y`,
lines 16-17) and `noc_mesh` instantiates four tiles with four different
`(X, Y)` values. Synthesis therefore yields four different netlists. Decision
0003 says one tile is placed and routed once and then stepped and repeated;
with parameters there is no single tile to repeat.

## Options

| | A. Node id as a port | B. Parameters, four masters |
|---|---|---|
| RTL | `X`/`Y` become `my_x`/`my_y` input ports on `noc_tile` and `noc_router`; the mesh ties them to constants. One change, filed as #47. | None. |
| Verification | The #25 2 x 2 scoreboard bench and tile/router benches re-run once (behaviour is unchanged). | None. |
| P&R cost | One tile run (about 2 h, per the earlier builder pass), one LEF abstract. | Four tile runs (about 8 h), four LEFs. |
| What is repeated | One master, placed four times: the property the canary exists to test. | Four masters that differ only in tied-off constants. Tiles are not interchangeable, so "step and repeat" is not exercised. |
| Pins | `my_x`/`my_y` add 4 pins and need tie cells at mesh level. | Identity is inside the netlist; no pins. |
| Risk | Constant tie-offs at mesh level; the router no longer constant-folds identity compares, so a few cells grow. Measured when #47 lands. | Boundary timing and abutment checked on four different masters, so a pass on one says little about the others. |

## Decision (recommended)

**Option A: node id is a port.** Four P&R runs would verify four tiles and
leave the repeat-and-abut step untested, which is the point of the project
(CLAUDE.md, "the seams between tiles are the point"). The RTL change is small
and behaviour-preserving, and its verification already exists.

Consequences:

- #47 makes the change. **#47 blocks #45**: part (b) must not start P&R on the
  parameterised tile.
- All other `noc_tile` parameters (`DEPTH`, `QAW`, `MESH_XW/YW`, `HOT_X/Y`,
  `GSEED`, `CSEED`) stay parameters and must be equal across the four
  instances so one netlist is valid. `GSEED`/`CSEED` seed the traffic generator
  and checker; per-tile seed diversity, if wanted, must come from `my_x/my_y`
  inside the generator, not from a per-instance parameter. #47 checks this.

## cfg / status pins

The tile exposes about 206 pins besides the 280 link pins and `clk`/`rst_n`:
7 `cfg_*` inputs (about 40 bits) and the endpoint observability outputs
(`gen_*`, `done`, `err`, `e_*`, `err_count`, `rx_*`, about 165 bits), counted
from the port list in `rtl/noc_tile.v`.

- **Link pins** sit on the four edges on the fixed mirrored grid of decision
  0003.
- **cfg/status pins stay on the tile master**, grouped on one edge band, and
  do not go through the neighbours. Placing the four copies with mirrored
  orientations (R0, MY, MX, R180 for tiles (0,0), (1,0), (0,1), (1,1)) makes
  that band face outward on all four tiles, so the pins reach the mesh boundary
  with short top-level routes and no feedthrough through other tiles. Which edge
  carries the band is fixed in #45 against the link pin grid; the fallback if
  mirrored placement is not usable with abutment is feedthrough routing over
  the macros, recorded as a new decision.
- `cfg_*` is broadcast from mesh-level ports to all four tiles; status outputs
  are per-tile mesh ports. Reducing the mesh-level pin count (a status mux or
  scan chain) is not part of this decision.

## Out of scope

The RTL edit (#47), pin placement, and any P&R.
