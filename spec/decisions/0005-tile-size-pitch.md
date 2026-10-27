# 0005 — Tile size and pitch

- **Status**: Proposed (reviewer to confirm at PR review)
- **Issue**: #44 (part (a) of #26)
- **Closes**: the "Tile size and pitch: Deferred" bullet of
  [0003](0003-physical-plan.md), by appending; 0003 is not edited.

## Input

Per-tile `klt synthesize` of `noc_tile` (X=0, Y=0 defaults), committed as
`layout/tile/reports/synthesize.json`, request `layout/tile/requests/synthesize.json`,
klt `0.8.1.dev413+g9165bae2fc5e`, 10 ns clock target, `sg13g2_stdcell`, about 40 s:

| | |
|---|---|
| Instances | 42,960 |
| Cell area | 743,441 um^2 (0.743 mm^2) |
| of which sequential | 404,011 um^2 (54 %) |
| Abc critical path estimate | 3.87 ns (a synthesis-time estimate, not STA) |

For comparison the whole 2 x 2 mesh (`layout/mesh/reports/synthesize.json`) is
174,619 cells, 2,996,134 um^2; four tiles are 2,973,766 um^2, so the mesh top
adds under 1 % of cells and nothing here depends on it.

## What the P&R tile contains

The tile as synthesized: the router (`noc_router`), the traffic generator
(`noc_tgen`) and the checker (`noc_tchk`), the four edge link registers, and
all cfg/status logic. The generator and checker are included because they are
inside `noc_tile`; the target has no other endpoint (CLAUDE.md scope). They are
a large share of the area, so this tile is bigger than a bare router would be.
Splitting them out would be a new decision, not made here.

## Decision (recommended)

- **Target utilization: 60 %** (stated assumption, not measured; first-pass
  value for a flop-heavy block with a 280-pin link interface and routing room
  for hierarchical abutment).
- **Tile outline: 1120 um x 1120 um** (1.254 mm^2): 743,441 / 0.60 = 1.239 mm^2,
  side 1113 um, rounded up to 1120 um. Resulting utilization 59.3 %.
- **Pitch: 1120 um in X and Y.** Links abut (decision 0003), so pitch equals
  tile size. The 2 x 2 mesh is 2240 um x 2240 um (5.0 mm^2).
- Pin pitch on a 1120 um edge: the 280 link pins fall on four edges, about 70
  per edge, so pin density is not the constraint.

## Revisit rule

Figures are pre-placement synthesis numbers. If #45 cannot close at this
outline (utilization, congestion, or timing), the change is a new appended
record with the tile run as evidence, not an edit here, and the hierarchical
approach stays. Latency, power and clock numbers are not claimed by this record.
