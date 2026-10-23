// Loopback bench top: noc_tgen -> link register -> noc_tchk, credit back
// through its own link register (spec/noc.md s1: one register per direction).
// Test-only; not part of the design. Plain Verilog-2005.
`timescale 1ns/1ps
module loopback #(
  parameter DEPTH   = 4,
  parameter MESH_XW = 1,
  parameter MESH_YW = 1,
  parameter HOT_X   = 1,
  parameter HOT_Y   = 1
) (
  input  wire        clk,
  input  wire        rst_n,
  input  wire [1:0]  my_x,
  input  wire [1:0]  my_y,
  input  wire        cfg_run,
  input  wire [1:0]  cfg_pattern,
  input  wire [16:0] cfg_thresh,
  input  wire [7:0]  cfg_len,
  input  wire [7:0]  cfg_npkts,
  input  wire [3:0]  cfg_stall_max,

  output wire        gen_valid,
  output wire [3:0]  gen_dst,
  output wire [15:0] gen_seq,
  output wire [15:0] gen_count,
  output wire [15:0] sent_pkts,
  output wire        done,

  output wire        lnk_valid,       // the link as the checker sees it
  output wire        lnk_last,
  output wire [31:0] lnk_data,

  output wire        err,
  output wire        e_loss,
  output wire        e_dup,
  output wire        e_payload,
  output wire        e_dest,
  output wire        e_frame,
  output wire [15:0] err_count,
  output wire [31:0] rx_flits,
  output wire [31:0] rx_pkts,
  output wire        rx_pkt_valid,
  output wire [3:0]  rx_src,
  output wire [3:0]  rx_dst,
  output wire [15:0] rx_seq
);
  wire        t_valid, t_last;
  wire [31:0] t_data;
  wire        t_credit, c_credit;

  reg         l_valid, l_last;
  reg  [31:0] l_data;
  reg         l_credit;
  always @(posedge clk) begin
    if (!rst_n) begin
      l_valid <= 1'b0; l_last <= 1'b0; l_data <= 32'd0; l_credit <= 1'b0;
    end else begin
      l_valid <= t_valid; l_last <= t_last; l_data <= t_data;
      l_credit <= c_credit;
    end
  end
  assign t_credit = l_credit;
  assign lnk_valid = l_valid;
  assign lnk_last = l_last;
  assign lnk_data = l_data;

  noc_tgen #(.DEPTH(DEPTH), .MESH_XW(MESH_XW), .MESH_YW(MESH_YW),
             .HOT_X(HOT_X), .HOT_Y(HOT_Y)) u_gen (
    .clk(clk), .rst_n(rst_n), .my_x(my_x), .my_y(my_y),
    .cfg_run(cfg_run), .cfg_pattern(cfg_pattern), .cfg_thresh(cfg_thresh),
    .cfg_len(cfg_len), .cfg_npkts(cfg_npkts),
    .out_valid(t_valid), .out_last(t_last), .out_data(t_data),
    .credit_in(t_credit),
    .gen_valid(gen_valid), .gen_dst(gen_dst), .gen_seq(gen_seq),
    .gen_count(gen_count), .sent_pkts(sent_pkts), .done(done));

  noc_tchk u_chk (
    .clk(clk), .rst_n(rst_n), .my_x(my_x), .my_y(my_y),
    .cfg_check_dst(1'b0), .cfg_stall_max(cfg_stall_max),
    .in_valid(l_valid), .in_last(l_last), .in_data(l_data),
    .credit_out(c_credit),
    .err(err), .e_loss(e_loss), .e_dup(e_dup), .e_payload(e_payload),
    .e_dest(e_dest), .e_frame(e_frame), .err_count(err_count),
    .rx_flits(rx_flits), .rx_pkts(rx_pkts),
    .rx_pkt_valid(rx_pkt_valid), .rx_src(rx_src), .rx_dst(rx_dst),
    .rx_seq(rx_seq));
endmodule
