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

Buffer depth: a credit is returned when a flit leaves the input buffer, not
when it arrives, so the round trip includes the router's own pipeline. With
the recommended 2-cycle router (`spec/noc.md` section 1): 1 (link register
forward) + 2 (buffer write to buffer read through route compute and switch
allocation) + 1 (link register back) = 4 cycles, plus any cycle the sender
spends updating its credit counter. Depth 4 is therefore the minimum that can
sustain one flit/cycle on an uncontended link, with no margin; depth 2 or 3
caps a link at 2/4 or 3/4 flit/cycle. Deeper buffers cost area for no gain
until contention is measured. The sizing is to be confirmed by the throughput
simulation at injection rate 1.0 (see `spec/noc.md`, Verification plan); if
that run shows a link below 1 flit/cycle with the pipeline as built, the
recorded change is depth 8, not acceptance of the loss.

## Alternatives

- valid/ready with skid buffers: fewer wires, simpler, but a ready path crosses
  the tile boundary or needs extra skid registers anyway.
- Depth 2: smaller area; throughput < 1 flit/cycle per link. Acceptable only if
  area forces it; would be a recorded change.
