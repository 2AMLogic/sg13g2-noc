# rtl

Plain Verilog-2005 (no SystemVerilog; see the SV seam in `CLAUDE.md`). Node
ids are `{y[1:0], x[1:0]}`; link and head-flit formats are `spec/noc.md` §2.

## Endpoints (issue #19)

One generator and one checker per node (`spec/noc.md` §1). They do not depend
on the router and are reused unchanged by the mesh.

| File | Role |
|---|---|
| `noc_tgen.v` | Traffic generator |
| `noc_tchk.v` | Checker / sink |
| `noc_payload.vh` | `noc_payload(src, dst, seq, idx)`: body-flit payload, shared by both |

### `noc_tgen`

Link out: `out_valid`, `out_last`, `out_data[31:0]`; in: `credit_in` (one bit).
Starts with `DEPTH` credits and sends only while credits > 0. Packets are
generated into a source queue and sent as credits allow, so source queueing
counts toward latency. It never looks at received flits (§3 assumption 3).

Parameters: `DEPTH` (4), `QAW` (7; queue holds 2**QAW packets, `cfg_npkts`
must not exceed it), `MESH_XW`/`MESH_YW` (log2 of mesh width/height; power-of-two
meshes only), `HOT_X`/`HOT_Y` (hotspot node), `SEED`.

Inputs: `my_x`, `my_y`, `cfg_run` (level), `cfg_pattern` (0 uniform,
1 transpose, 2 hotspot), `cfg_thresh` (packet probability per cycle in
1/65536, 17 bits so 1.0 fits), `cfg_len` (flits per packet, >= 1),
`cfg_npkts` (packets to generate, <= 128).

Bench-visible outputs: `gen_valid`/`gen_dst`/`gen_seq` (one strobe per
generated packet), `gen_count`, `sent_pkts`, `done`.

Design calls (not spec text; the issue asks that they be recorded here):

- **Rate**: Bernoulli packet generation, p = rate / length, as a 16-bit LFSR
  (xorshift32) compare. The bench computes `cfg_thresh = round(65536 * rate / length)`
  and reports the achieved offered rate. At high rates the measured figure is
  taken over a short window of 64 packets and can exceed the target by chance.
- **Patterns**: uniform is over non-self nodes. Transpose sends (x, y) to
  (y, x); diagonal nodes have no transpose partner and stay idle. Hotspot sends
  half the packets to the hot node and half uniformly over nodes that are
  neither self nor hot; the hot node itself sends uniform.
- **Sequence numbers**: one counter per destination, starting at 0, assigned at
  generation. No timestamp travels in the flit (the §2 head has none); latency
  is computed in the bench by joining the generator and checker logs.
- **Negative controls**: `-DNEG_CORRUPT` flips a bit in the first body flit of
  the third packet; `-DNEG_SKIPSEQ` skips one sequence number on the third
  packet. Both are off by default.

### `noc_tchk`

Accepts every flit on arrival (§3 assumption 2); there is no ready signal.
`credit_out` returns one credit per accepted flit, delayed by a bounded random
0..`cfg_stall_max` cycles (the "bounded stall"). Inputs: `my_x`, `my_y`,
`cfg_check_dst` (1 in the mesh, 0 in a many-to-one loopback), `cfg_stall_max`.

Checks per {src, dst} pair, with sticky flags `e_loss`, `e_dup`, `e_payload`,
`e_dest`, `e_frame`, an overall `err`, and `err_count`. The expected-sequence
table is keyed on {src, dst}, so it works unchanged when one checker sees many
destinations. After a sequence error the expectation resyncs to seq+1, so a
single fault counts once. `rx_flits`, `rx_pkts` and a per-packet strobe
(`rx_pkt_valid`, `rx_src`, `rx_dst`, `rx_seq`) feed the scoreboard.

Both modules elaborate under `yosys synth`:

```
yosys -p 'read_verilog -I rtl rtl/noc_tgen.v; synth -top noc_tgen'
yosys -p 'read_verilog -I rtl rtl/noc_tchk.v; synth -top noc_tchk'
```
