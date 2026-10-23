# rtl

## `noc_router.v`

5-port wormhole XY router with credit-based flow control, 32-bit flits, no
virtual channels (`spec/noc.md` sections 1-3, decisions 0001-0003). Plain
Verilog-2001: Icarus and Yosys both take it as is, with no conversion step.

| Parameter | Default | Meaning |
|---|---|---|
| `X`, `Y` | 0, 0 | router coordinates (2 bits each, spec section 2) |
| `DEPTH` | 4 | input FIFO flits per port, and the credits an output starts with (assumes the neighbour has the same depth). 1 to 7 |

Ports `N`=0 (+Y), `E`=1 (+X), `S`=2 (-Y), `W`=3 (-X), `L`=4 (local); buses are
flattened (port `p` is bits `[p*32 +: 32]`). Per port: `in_valid/in_last/in_data`
and `in_credit` (return), `out_valid/out_last/out_data` and `out_credit`
(arriving). `dbg_occ` and `dbg_credits` expose FIFO occupancy and output credit
counters for the credit-conservation check; leave them open in a tile.

### Design calls (inferences from the spec, not spec text)

- **Pipeline, 2 cycles in the module.** A flit on `in_*` in cycle t is written to
  the input FIFO at the end of t; in t+1 it is routed, arbitrated and switched
  into the output register; it is on `out_*` in t+2. The 1-cycle link register
  per direction lives at the tile edge, outside this module (0003).
- **Credit return is combinational from the FIFO pop** (`in_credit` is high in the
  cycle the flit leaves the FIFO), and the sender uses a credit arriving this
  cycle without waiting for its counter to update. Both depend on the tile-edge
  link register for timing: the credit input-to-output path is
  `out_credit -> grant -> in_credit`. With the link registers the loop is 4
  cycles, which is what 0002 sizes depth 4 for.
- **Arbitration**: per output, round-robin over head flits; the grant is held by
  the input that won it until its `last` flit leaves (spec section 3,
  assumption 5). Body flits follow the route latched at the head.
- **Routing**: X first, then Y, then local, from the head flit's `data[31:28]`.
  A local-input packet addressed to the router itself would loop to the local
  output; endpoints never send to themselves and the bench does not test it.
- **Negative controls**: `+define+NEG_YX_TURN` (a packet entering from N or S
  that should continue in Y is turned to E) and `+define+NEG_DROP_CREDIT` (the
  first credit return on input N is swallowed). Verification only.

Not done here: reset applied mid-traffic, mesh top, endpoints.
