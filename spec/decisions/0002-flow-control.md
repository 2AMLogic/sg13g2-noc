# 0002 — Flow control, buffering and virtual channels

- **Status**: Proposed (preference call; reviewer to confirm at PR review)
- **Issue**: #2

## Decision (recommended)

- **Credit-based** flow control on every link.
- **4-flit** input buffer per input port; no output buffering beyond the link
  register.
- **Zero virtual channels** (README target).

## Rationale

With valid/ready, `ready` is a combinational path against the data direction.
Across a tile boundary that path crosses two placements, which is the timing
path the canary is meant to study but should not make unclosable by design.
With credits, both directions are plain registered signals: forward `valid`,
`last`, `data`; backward a one-bit credit return. Each link direction has one
register stage at the tile edge.

Buffer depth: credit round trip = 1 (link register forward) + 1 (buffer
read/credit generation) + 1 (link register back) = 3 cycles, so 4 flits
sustains one flit/cycle with margin; 2-3 would be marginal, deeper costs area.
To be confirmed by the throughput simulation at injection rate 1.0
(see `spec/noc.md`, Verification plan).

## Alternatives

- valid/ready with skid buffers: fewer wires, simpler, but a ready path crosses
  the tile boundary or needs extra skid registers anyway.
- Depth 2: smaller area; throughput < 1 flit/cycle per link. Acceptable only if
  area forces it; would be a recorded change.
