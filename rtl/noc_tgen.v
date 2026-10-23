// noc_tgen: LFSR-seeded traffic generator, one per node (spec/noc.md s1, s2, s5).
//
// Link out (credit-based, spec/decisions/0002): valid, last, data[31:0];
// reverse: credit (one bit, one credit per pulse). Starts with DEPTH credits.
// Packets are generated at the configured rate into a source queue (so source
// queueing counts toward latency, s5) and sent whenever credits allow. The
// generator never looks at received flits (s3 assumption 3).
//
// Rate: a packet is generated in a cycle when a 16-bit random value is below
// cfg_thresh; for flit rate r and packet length L the bench sets
// cfg_thresh = round(65536 * r / L). cfg_thresh = 65536 needs 17 bits, hence
// the width. Node ids are {y[1:0], x[1:0]}, matching the head flit of s2.
//
// Plain Verilog-2005. NEG_CORRUPT / NEG_SKIPSEQ are negative-control defines
// (off by default): they must make noc_tchk flag an error.

module noc_tgen #(
  parameter DEPTH   = 4,      // initial credits = receiver buffer depth
  parameter QAW     = 7,      // source queue holds 2**QAW packets; cfg_npkts <= 2**QAW
  parameter MESH_XW = 1,      // log2(mesh width)  (power-of-two meshes only)
  parameter MESH_YW = 1,      // log2(mesh height)
  parameter HOT_X   = 1,      // hotspot node
  parameter HOT_Y   = 1,
  parameter SEED    = 32'h1badc0de
) (
  input  wire        clk,
  input  wire        rst_n,       // active-low, synchronous

  input  wire [1:0]  my_x,
  input  wire [1:0]  my_y,

  input  wire        cfg_run,     // level: generate while high
  input  wire [1:0]  cfg_pattern, // 0 uniform, 1 transpose, 2 hotspot
  input  wire [16:0] cfg_thresh,  // packet probability, units of 1/65536
  input  wire [7:0]  cfg_len,     // flits per packet, >= 1
  input  wire [7:0]  cfg_npkts,   // packets to generate, <= 2**QAW

  output reg         out_valid,
  output reg         out_last,
  output reg  [31:0] out_data,
  input  wire        credit_in,

  // bench-visible generation log: one strobe per generated packet
  output reg         gen_valid,
  output reg  [3:0]  gen_dst,
  output reg  [15:0] gen_seq,
  output reg  [15:0] gen_count,   // packets generated so far
  output reg  [15:0] sent_pkts,   // head flits sent so far
  output wire        done         // all packets generated and fully sent
);
`include "noc_payload.vh"

  localparam NX = 1 << MESH_XW;
  localparam NY = 1 << MESH_YW;
  localparam NN = NX * NY;

  wire [3:0] my_id  = {my_y, my_x};
  wire [1:0] hot_x  = HOT_X;
  wire [1:0] hot_y  = HOT_Y;

  // ---- node index (row-major y*NX + x) <-> id ------------------------------
  wire [3:0] my_idx  = (({2'b00, my_y}) << MESH_XW) + {2'b00, my_x};
  wire [3:0] hot_idx = (({2'b00, hot_y}) << MESH_XW) + {2'b00, hot_x};

  // ---- random source: xorshift32, one step per cycle -----------------------
  reg [31:0] rng;
  wire [31:0] r1 = rng ^ (rng << 13);
  wire [31:0] r2 = r1 ^ (r1 >> 17);
  wire [31:0] r3 = r2 ^ (r2 << 5);
  wire [31:0] seed_mix = SEED ^ {4'd0, my_y, my_x, 24'h5eed01};

  wire [15:0] rnd_gen = rng[31:16];
  wire [7:0]  rnd_dst = rng[15:8];
  wire        rnd_hot = rng[7];

  // ---- destination selection (combinational on rng) ------------------------
  // Uniform over non-self nodes: r in [0, NN-1), then skip over self.
  wire [3:0] n_excl1 = NN - 1;
  wire [11:0] u1_p = rnd_dst * n_excl1;
  wire [3:0] u1_r  = u1_p[11:8];
  wire [3:0] uni_idx = (u1_r >= my_idx) ? u1_r + 4'd1 : u1_r;

  // Hotspot: half the packets to the hot node, half uniform over nodes that
  // are neither self nor hot. The hot node itself sends plain uniform.
  wire        self_is_hot = (my_idx == hot_idx);
  wire [3:0]  n_excl2 = NN - 2;
  wire [11:0] u2_p = rnd_dst * n_excl2;
  wire [3:0]  u2_r = u2_p[11:8];
  wire [3:0]  lo = (my_idx < hot_idx) ? my_idx : hot_idx;
  wire [3:0]  hi = (my_idx < hot_idx) ? hot_idx : my_idx;
  wire [3:0]  u2_a = (u2_r >= lo) ? u2_r + 4'd1 : u2_r;
  wire [3:0]  u2_b = (u2_a >= hi) ? u2_a + 4'd1 : u2_a;
  wire [3:0]  hot_other_idx = (NN > 2) ? u2_b : hot_idx;
  wire [3:0]  hs_idx = self_is_hot ? uni_idx : (rnd_hot ? hot_idx : hot_other_idx);

  wire [3:0] sel_idx = (cfg_pattern == 2'd2) ? hs_idx : uni_idx;
  wire [1:0] sel_x = sel_idx & (NX - 1);
  wire [1:0] sel_y = sel_idx >> MESH_XW;
  wire [3:0] tr_id = {my_x, my_y};            // transpose: (x, y) -> (y, x)
  wire [3:0] dst_id = (cfg_pattern == 2'd1) ? tr_id : {sel_y, sel_x};

  // transpose is undefined on the diagonal: those nodes stay idle
  wire idle_node = (cfg_pattern == 2'd1) && (my_x == my_y);

  // ---- generation ----------------------------------------------------------
  reg [15:0] seq_ctr [0:15];                  // next seq per destination
  reg [19:0] q_mem [0:(1<<QAW)-1];            // {seq, dst}
  reg [QAW:0] q_wr, q_rd;
  wire q_empty = (q_wr == q_rd);

  wire gen_more = cfg_run && !idle_node && (gen_count < {8'd0, cfg_npkts});
  wire gen_fire = gen_more && ({1'b0, rnd_gen} < cfg_thresh);

  wire [15:0] cur_seq = seq_ctr[dst_id];
`ifdef NEG_SKIPSEQ
  // negative control: the third packet skips one sequence number
  wire [15:0] new_seq = (gen_count == 16'd2) ? cur_seq + 16'd1 : cur_seq;
  wire [15:0] next_ctr = new_seq + 16'd1;
`else
  wire [15:0] new_seq = cur_seq;
  wire [15:0] next_ctr = cur_seq + 16'd1;
`endif

  // ---- transmit ------------------------------------------------------------
  reg [7:0]  credits;
  reg        in_pkt;
  reg [7:0]  fidx;                            // flit index of the next flit to send
  reg [3:0]  cur_dst;
  reg [15:0] cur_seq_tx;
  reg [15:0] pkts_tx;                         // packets started (for negative controls)

  wire [19:0] q_head = q_mem[q_rd[QAW-1:0]];
  wire [3:0]  q_dst = q_head[3:0];
  wire [15:0] q_seq = q_head[19:4];

  wire can_send = (credits != 8'd0) && (in_pkt || !q_empty);
  wire [3:0]  s_dst = in_pkt ? cur_dst : q_dst;
  wire [15:0] s_seq = in_pkt ? cur_seq_tx : q_seq;
  wire [7:0]  s_idx = in_pkt ? fidx : 8'd0;
  wire        s_last = (s_idx == cfg_len - 8'd1);

  wire [31:0] head_flit = {s_dst[1:0], s_dst[3:2], my_x, my_y, cfg_len, s_seq};
  wire [31:0] body_pl = noc_payload(my_id, s_dst, s_seq, s_idx);
`ifdef NEG_CORRUPT
  // negative control: the third packet's first body flit has one bit flipped
  wire [31:0] body_flit = (pkts_tx == 16'd3 && s_idx == 8'd1) ? (body_pl ^ 32'h00000100) : body_pl;
`else
  wire [31:0] body_flit = body_pl;
`endif

  assign done = !cfg_run ? 1'b0 :
                ((idle_node || gen_count == {8'd0, cfg_npkts}) && q_empty && !in_pkt && !out_valid);

  integer i;
  always @(posedge clk) begin
    if (!rst_n) begin
      rng <= (seed_mix == 32'd0) ? 32'h1 : seed_mix;
      for (i = 0; i < 16; i = i + 1) seq_ctr[i] <= 16'd0;
      q_wr <= 0; q_rd <= 0;
      credits <= DEPTH;
      in_pkt <= 1'b0; fidx <= 8'd0; cur_dst <= 4'd0; cur_seq_tx <= 16'd0;
      pkts_tx <= 16'd0;
      out_valid <= 1'b0; out_last <= 1'b0; out_data <= 32'd0;
      gen_valid <= 1'b0; gen_dst <= 4'd0; gen_seq <= 16'd0;
      gen_count <= 16'd0; sent_pkts <= 16'd0;
    end else begin
      rng <= r3;

      // generation
      gen_valid <= gen_fire;
      if (gen_fire) begin
        q_mem[q_wr[QAW-1:0]] <= {new_seq, dst_id};
        q_wr <= q_wr + 1'b1;
        seq_ctr[dst_id] <= next_ctr;
        gen_dst <= dst_id;
        gen_seq <= new_seq;
        gen_count <= gen_count + 16'd1;
      end

      // transmit; credits: -1 per flit sent, +1 per credit returned
      credits <= credits - {7'd0, can_send} + {7'd0, credit_in};
      out_valid <= can_send;
      if (can_send) begin
        out_last <= s_last;
        out_data <= (s_idx == 8'd0) ? head_flit : body_flit;
        if (s_idx == 8'd0) begin
          cur_dst <= q_dst;
          cur_seq_tx <= q_seq;
          q_rd <= q_rd + 1'b1;
          sent_pkts <= sent_pkts + 16'd1;
          pkts_tx <= pkts_tx + 16'd1;
        end
        if (s_last) begin
          in_pkt <= 1'b0;
          fidx <= 8'd0;
        end else begin
          in_pkt <= 1'b1;
          fidx <= s_idx + 8'd1;
        end
      end else begin
        out_last <= 1'b0;
      end
    end
  end
endmodule
