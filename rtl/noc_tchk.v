// noc_tchk: traffic checker / sink, one per node (spec/noc.md s1, s3, s5).
//
// Accepts every flit on arrival (s3 assumption 2: always sinks; there is no
// ready signal) and owns credit return. The optional stall delays each credit
// by a bounded random 0..cfg_stall_max cycles, which throttles the sender
// without ever refusing a flit.
//
// Checks, per source and destination pair {src, dst}:
//   e_loss    sequence number above the expected one (a packet was skipped)
//   e_dup     sequence number below the expected one (repeat or reorder)
//   e_payload body flit differs from noc_payload(src, dst, seq, idx)
//   e_dest    head flit dest differs from my_x/my_y (only if cfg_check_dst)
//   e_frame   body flit without head, or `last` inconsistent with the length field
// Errors are sticky flags plus a counter. After a sequence error the expected
// number resyncs to seq+1, so one fault is counted once.
//
// Node ids are {y[1:0], x[1:0]} as in noc_tgen. Plain Verilog-2005.

module noc_tchk #(
  parameter SEED = 32'h0c0ffee1,
  // 0: sequence table keyed on {src, dst} (256 entries; loopback bench, where
  //    many destinations land on one checker).
  // 1: keyed on src only (16 entries). Valid only while cfg_check_dst is 1:
  //    every accepted packet then has dst == my node, so the dst bits of the
  //    key are constant and the per-{src, dst} check is unchanged.
  parameter KEY_SRC_ONLY = 0
) (
  input  wire        clk,
  input  wire        rst_n,

  input  wire [1:0]  my_x,
  input  wire [1:0]  my_y,
  input  wire        cfg_check_dst,   // 1 in the mesh; 0 in a many-to-one loopback
  input  wire [3:0]  cfg_stall_max,   // max extra cycles before a credit returns

  input  wire        in_valid,
  input  wire        in_last,
  input  wire [31:0] in_data,
  output reg         credit_out,

  output reg         err,             // sticky: any check tripped
  output reg         e_loss,
  output reg         e_dup,
  output reg         e_payload,
  output reg         e_dest,
  output reg         e_frame,
  output reg  [15:0] err_count,
  output reg  [31:0] rx_flits,
  output reg  [31:0] rx_pkts,

  // bench-visible strobe on the last flit of each packet
  output reg         rx_pkt_valid,
  output reg  [3:0]  rx_src,
  output reg  [3:0]  rx_dst,
  output reg  [15:0] rx_seq
);
`include "noc_payload.vh"

  localparam NSEQ = KEY_SRC_ONLY ? 16 : 256;
  reg [15:0] exp_seq [0:NSEQ-1];       // indexed by {src, dst}, or src if KEY_SRC_ONLY

  reg        in_pkt;
  reg [3:0]  cur_src, cur_dst;
  reg [15:0] cur_seq;
  reg [7:0]  cur_len, fidx;

  wire is_head = in_valid && !in_pkt;
  wire [3:0] h_dst = {in_data[29:28], in_data[31:30]};
  wire [3:0] h_src = {in_data[25:24], in_data[27:26]};
  wire [15:0] h_seq = in_data[15:0];
  wire [7:0]  h_len = in_data[23:16];

  wire [3:0]  a_src = is_head ? h_src : cur_src;
  wire [3:0]  a_dst = is_head ? h_dst : cur_dst;
  wire [15:0] a_seq = is_head ? h_seq : cur_seq;
  wire [7:0]  a_len = is_head ? h_len : cur_len;
  wire [7:0]  a_idx = is_head ? 8'd0 : fidx;

  wire [7:0]  h_key = KEY_SRC_ONLY ? {4'd0, h_src} : {h_src, h_dst};
  wire [15:0] exp_now = exp_seq[h_key[(KEY_SRC_ONLY ? 3 : 7):0]];
  wire        seq_loss = is_head && (h_seq > exp_now);
  wire        seq_dup  = is_head && (h_seq < exp_now);
  wire        bad_dest = is_head && cfg_check_dst && ({h_dst} != {my_y, my_x});
  wire        bad_pl   = in_valid && !is_head && (in_data != noc_payload(a_src, a_dst, a_seq, a_idx));
  wire        bad_frm  = in_valid && (a_len == 8'd0 ||
                         (in_last != (a_idx == a_len - 8'd1)));

  wire any_err = seq_loss | seq_dup | bad_dest | bad_pl | bad_frm;

  // ---- credit return -------------------------------------------------------
  reg [31:0] rng;
  reg [7:0]  pend;
  reg [3:0]  wait_cnt;
  wire [7:0] pend_now = pend + {7'd0, in_valid};
  wire       emit = (pend_now != 8'd0) && (wait_cnt == 4'd0);
  wire [31:0] r1 = rng ^ (rng << 13);
  wire [31:0] r2 = r1 ^ (r1 >> 17);
  wire [31:0] r3 = r2 ^ (r2 << 5);
  wire [7:0]  w_p = rng[3:0] * (cfg_stall_max + 4'd1);   // 0..cfg_stall_max
  wire [3:0]  w_next = w_p[7:4];

  integer i;
  always @(posedge clk) begin
    if (!rst_n) begin
      for (i = 0; i < NSEQ; i = i + 1) exp_seq[i] <= 16'd0;
      in_pkt <= 1'b0; cur_src <= 4'd0; cur_dst <= 4'd0; cur_seq <= 16'd0;
      cur_len <= 8'd0; fidx <= 8'd0;
      credit_out <= 1'b0; pend <= 8'd0; wait_cnt <= 4'd0;
      rng <= SEED;
      err <= 1'b0; e_loss <= 1'b0; e_dup <= 1'b0; e_payload <= 1'b0;
      e_dest <= 1'b0; e_frame <= 1'b0; err_count <= 16'd0;
      rx_flits <= 32'd0; rx_pkts <= 32'd0;
      rx_pkt_valid <= 1'b0; rx_src <= 4'd0; rx_dst <= 4'd0; rx_seq <= 16'd0;
    end else begin
      rng <= r3;
      credit_out <= emit;
      pend <= pend_now - {7'd0, emit};
      if (emit) wait_cnt <= w_next;
      else if (wait_cnt != 4'd0) wait_cnt <= wait_cnt - 4'd1;

      rx_pkt_valid <= 1'b0;
      if (in_valid) begin
        rx_flits <= rx_flits + 32'd1;
        if (is_head) begin
          cur_src <= h_src; cur_dst <= h_dst; cur_seq <= h_seq; cur_len <= h_len;
          exp_seq[h_key[(KEY_SRC_ONLY ? 3 : 7):0]] <= h_seq + 16'd1;
        end
        fidx <= (is_head ? 8'd0 : fidx) + 8'd1;
        in_pkt <= !in_last;
        if (in_last) begin
          rx_pkts <= rx_pkts + 32'd1;
          rx_pkt_valid <= 1'b1;
          rx_src <= a_src; rx_dst <= a_dst; rx_seq <= a_seq;
        end
        if (any_err) begin
          err <= 1'b1;
          err_count <= err_count + 16'd1;
        end
        if (seq_loss) e_loss <= 1'b1;
        if (seq_dup) e_dup <= 1'b1;
        if (bad_pl) e_payload <= 1'b1;
        if (bad_dest) e_dest <= 1'b1;
        if (bad_frm) e_frame <= 1'b1;
      end
    end
  end
endmodule
