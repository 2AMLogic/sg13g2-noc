# 0003 — Physical plan

- **Status**: Proposed. Numeric tile size/pitch is **Deferred** (see below).
- **Issue**: #2

## Decision (recommended)

- **Hierarchical place-and-route**: one router+endpoint tile is placed and routed
  once, then stepped and repeated into the mesh. A flat run would not exercise
  the tile-reuse and boundary-timing surface this canary targets.
- **Links abut**: tile-edge link pins are on a fixed grid and mirror across
  adjacent tiles, so neighbouring tiles connect by abutment with no channel.
  Fallback if abutment fails DRC/LVS: a routing channel between tiles, recorded
  as a new decision.
- **Link buffering**: every link has one register at the sender's tile edge
  (decision 0002), so inter-tile wires are single-cycle point-to-point. No
  repeaters are planned by hand; the flow inserts buffers (OpenROAD
  repair_design/repair_timing) and the report records what it inserted.
- **Tile size and pitch**: Deferred. Unblocker: synthesized router area from
  the toolchain smoke (#4) and the first Yosys run. Decider: reviewer, via a
  follow-up decision record. Until then no tile dimension is quoted.

## Alternatives

- Flat P&R of the whole mesh: simpler flow, does not test hierarchy.
- Channel-routed links: relaxes abutment alignment, adds area and a routing
  step; kept as fallback.
