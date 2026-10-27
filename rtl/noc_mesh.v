// noc_mesh: 2 x 2 mesh of noc_tile. Node id is {y[1:0], x[1:0]}; node n = 2*y + x.
// Per-node endpoint outputs are flattened: node n occupies bits [n*W +: W].
// Tiles abut: tile (x,y) N output feeds tile (x,y+1) S input, E feeds (x+1,y) W.
// Edge links with no neighbour are tied off (inputs 0; outputs and credit
// returns unused). Direction order is N0 E1 S2 W3 as in noc_tile.
module noc_mesh #(
    parameter DEPTH = 4,
    parameter QAW   = 7,
    parameter HOT_X = 1,
    parameter HOT_Y = 1
) (
    input  wire         clk,
    input  wire         rst_n,

    input  wire         cfg_run,
    input  wire [1:0]   cfg_pattern,
    input  wire [16:0]  cfg_thresh,
    input  wire [7:0]   cfg_len,
    input  wire [7:0]   cfg_npkts,
    input  wire         cfg_check_dst,
    input  wire [3:0]   cfg_stall_max,

    output wire [3:0] gen_valid,
    output wire [15:0] gen_dst,
    output wire [63:0] gen_seq,
    output wire [63:0] gen_count,
    output wire [63:0] sent_pkts,
    output wire [3:0] done,
    output wire [3:0] err,
    output wire [3:0] e_loss,
    output wire [3:0] e_dup,
    output wire [3:0] e_payload,
    output wire [3:0] e_dest,
    output wire [3:0] e_frame,
    output wire [63:0] err_count,
    output wire [127:0] rx_flits,
    output wire [127:0] rx_pkts,
    output wire [3:0] rx_pkt_valid,
    output wire [15:0] rx_src,
    output wire [15:0] rx_dst,
    output wire [63:0] rx_seq
);
    // inter-tile link nets, one set per tile (node n = 2*y + x)
    wire [3:0]   t_ov  [0:3];
    wire [3:0]   t_ol  [0:3];
    wire [127:0] t_od  [0:3];
    wire [3:0]   t_cr  [0:3];
    wire [3:0]   t_iv  [0:3];
    wire [3:0]   t_il  [0:3];
    wire [127:0] t_id  [0:3];
    wire [3:0]   t_ci  [0:3];

    assign t_iv[0][0] = t_ov[2][2];
    assign t_il[0][0] = t_ol[2][2];
    assign t_id[0][0*32 +: 32] = t_od[2][2*32 +: 32];
    assign t_ci[0][0] = t_cr[2][2];
    assign t_iv[0][1] = t_ov[1][3];
    assign t_il[0][1] = t_ol[1][3];
    assign t_id[0][1*32 +: 32] = t_od[1][3*32 +: 32];
    assign t_ci[0][1] = t_cr[1][3];
    assign t_iv[0][2] = 1'b0;
    assign t_il[0][2] = 1'b0;
    assign t_id[0][2*32 +: 32] = 32'b0;
    assign t_ci[0][2] = 1'b0;
    assign t_iv[0][3] = 1'b0;
    assign t_il[0][3] = 1'b0;
    assign t_id[0][3*32 +: 32] = 32'b0;
    assign t_ci[0][3] = 1'b0;
    assign t_iv[1][0] = t_ov[3][2];
    assign t_il[1][0] = t_ol[3][2];
    assign t_id[1][0*32 +: 32] = t_od[3][2*32 +: 32];
    assign t_ci[1][0] = t_cr[3][2];
    assign t_iv[1][1] = 1'b0;
    assign t_il[1][1] = 1'b0;
    assign t_id[1][1*32 +: 32] = 32'b0;
    assign t_ci[1][1] = 1'b0;
    assign t_iv[1][2] = 1'b0;
    assign t_il[1][2] = 1'b0;
    assign t_id[1][2*32 +: 32] = 32'b0;
    assign t_ci[1][2] = 1'b0;
    assign t_iv[1][3] = t_ov[0][1];
    assign t_il[1][3] = t_ol[0][1];
    assign t_id[1][3*32 +: 32] = t_od[0][1*32 +: 32];
    assign t_ci[1][3] = t_cr[0][1];
    assign t_iv[2][0] = 1'b0;
    assign t_il[2][0] = 1'b0;
    assign t_id[2][0*32 +: 32] = 32'b0;
    assign t_ci[2][0] = 1'b0;
    assign t_iv[2][1] = t_ov[3][3];
    assign t_il[2][1] = t_ol[3][3];
    assign t_id[2][1*32 +: 32] = t_od[3][3*32 +: 32];
    assign t_ci[2][1] = t_cr[3][3];
    assign t_iv[2][2] = t_ov[0][0];
    assign t_il[2][2] = t_ol[0][0];
    assign t_id[2][2*32 +: 32] = t_od[0][0*32 +: 32];
    assign t_ci[2][2] = t_cr[0][0];
    assign t_iv[2][3] = 1'b0;
    assign t_il[2][3] = 1'b0;
    assign t_id[2][3*32 +: 32] = 32'b0;
    assign t_ci[2][3] = 1'b0;
    assign t_iv[3][0] = 1'b0;
    assign t_il[3][0] = 1'b0;
    assign t_id[3][0*32 +: 32] = 32'b0;
    assign t_ci[3][0] = 1'b0;
    assign t_iv[3][1] = 1'b0;
    assign t_il[3][1] = 1'b0;
    assign t_id[3][1*32 +: 32] = 32'b0;
    assign t_ci[3][1] = 1'b0;
    assign t_iv[3][2] = t_ov[1][0];
    assign t_il[3][2] = t_ol[1][0];
    assign t_id[3][2*32 +: 32] = t_od[1][0*32 +: 32];
    assign t_ci[3][2] = t_cr[1][0];
    assign t_iv[3][3] = t_ov[2][1];
    assign t_il[3][3] = t_ol[2][1];
    assign t_id[3][3*32 +: 32] = t_od[2][1*32 +: 32];
    assign t_ci[3][3] = t_cr[2][1];

    noc_tile #(.X(2'd0), .Y(2'd0), .DEPTH(DEPTH), .QAW(QAW), .MESH_XW(1), .MESH_YW(1),
               .HOT_X(HOT_X), .HOT_Y(HOT_Y)) u_tile0 (
        .clk(clk), .rst_n(rst_n),
        .lk_in_valid(t_iv[0]), .lk_in_last(t_il[0]), .lk_in_data(t_id[0]), .cr_out(t_cr[0]),
        .lk_out_valid(t_ov[0]), .lk_out_last(t_ol[0]), .lk_out_data(t_od[0]), .cr_in(t_ci[0]),
        .cfg_run(cfg_run), .cfg_pattern(cfg_pattern), .cfg_thresh(cfg_thresh), .cfg_len(cfg_len),
        .cfg_npkts(cfg_npkts), .cfg_check_dst(cfg_check_dst), .cfg_stall_max(cfg_stall_max),
        .gen_valid(gen_valid[0]), .gen_dst(gen_dst[0*4 +: 4]), .gen_seq(gen_seq[0*16 +: 16]), .gen_count(gen_count[0*16 +: 16]), .sent_pkts(sent_pkts[0*16 +: 16]), .done(done[0]), .err(err[0]), .e_loss(e_loss[0]), .e_dup(e_dup[0]), .e_payload(e_payload[0]), .e_dest(e_dest[0]), .e_frame(e_frame[0]), .err_count(err_count[0*16 +: 16]), .rx_flits(rx_flits[0*32 +: 32]), .rx_pkts(rx_pkts[0*32 +: 32]), .rx_pkt_valid(rx_pkt_valid[0]), .rx_src(rx_src[0*4 +: 4]), .rx_dst(rx_dst[0*4 +: 4]), .rx_seq(rx_seq[0*16 +: 16])
    );

    noc_tile #(.X(2'd1), .Y(2'd0), .DEPTH(DEPTH), .QAW(QAW), .MESH_XW(1), .MESH_YW(1),
               .HOT_X(HOT_X), .HOT_Y(HOT_Y)) u_tile1 (
        .clk(clk), .rst_n(rst_n),
        .lk_in_valid(t_iv[1]), .lk_in_last(t_il[1]), .lk_in_data(t_id[1]), .cr_out(t_cr[1]),
        .lk_out_valid(t_ov[1]), .lk_out_last(t_ol[1]), .lk_out_data(t_od[1]), .cr_in(t_ci[1]),
        .cfg_run(cfg_run), .cfg_pattern(cfg_pattern), .cfg_thresh(cfg_thresh), .cfg_len(cfg_len),
        .cfg_npkts(cfg_npkts), .cfg_check_dst(cfg_check_dst), .cfg_stall_max(cfg_stall_max),
        .gen_valid(gen_valid[1]), .gen_dst(gen_dst[1*4 +: 4]), .gen_seq(gen_seq[1*16 +: 16]), .gen_count(gen_count[1*16 +: 16]), .sent_pkts(sent_pkts[1*16 +: 16]), .done(done[1]), .err(err[1]), .e_loss(e_loss[1]), .e_dup(e_dup[1]), .e_payload(e_payload[1]), .e_dest(e_dest[1]), .e_frame(e_frame[1]), .err_count(err_count[1*16 +: 16]), .rx_flits(rx_flits[1*32 +: 32]), .rx_pkts(rx_pkts[1*32 +: 32]), .rx_pkt_valid(rx_pkt_valid[1]), .rx_src(rx_src[1*4 +: 4]), .rx_dst(rx_dst[1*4 +: 4]), .rx_seq(rx_seq[1*16 +: 16])
    );

    noc_tile #(.X(2'd0), .Y(2'd1), .DEPTH(DEPTH), .QAW(QAW), .MESH_XW(1), .MESH_YW(1),
               .HOT_X(HOT_X), .HOT_Y(HOT_Y)) u_tile2 (
        .clk(clk), .rst_n(rst_n),
        .lk_in_valid(t_iv[2]), .lk_in_last(t_il[2]), .lk_in_data(t_id[2]), .cr_out(t_cr[2]),
        .lk_out_valid(t_ov[2]), .lk_out_last(t_ol[2]), .lk_out_data(t_od[2]), .cr_in(t_ci[2]),
        .cfg_run(cfg_run), .cfg_pattern(cfg_pattern), .cfg_thresh(cfg_thresh), .cfg_len(cfg_len),
        .cfg_npkts(cfg_npkts), .cfg_check_dst(cfg_check_dst), .cfg_stall_max(cfg_stall_max),
        .gen_valid(gen_valid[2]), .gen_dst(gen_dst[2*4 +: 4]), .gen_seq(gen_seq[2*16 +: 16]), .gen_count(gen_count[2*16 +: 16]), .sent_pkts(sent_pkts[2*16 +: 16]), .done(done[2]), .err(err[2]), .e_loss(e_loss[2]), .e_dup(e_dup[2]), .e_payload(e_payload[2]), .e_dest(e_dest[2]), .e_frame(e_frame[2]), .err_count(err_count[2*16 +: 16]), .rx_flits(rx_flits[2*32 +: 32]), .rx_pkts(rx_pkts[2*32 +: 32]), .rx_pkt_valid(rx_pkt_valid[2]), .rx_src(rx_src[2*4 +: 4]), .rx_dst(rx_dst[2*4 +: 4]), .rx_seq(rx_seq[2*16 +: 16])
    );

    noc_tile #(.X(2'd1), .Y(2'd1), .DEPTH(DEPTH), .QAW(QAW), .MESH_XW(1), .MESH_YW(1),
               .HOT_X(HOT_X), .HOT_Y(HOT_Y)) u_tile3 (
        .clk(clk), .rst_n(rst_n),
        .lk_in_valid(t_iv[3]), .lk_in_last(t_il[3]), .lk_in_data(t_id[3]), .cr_out(t_cr[3]),
        .lk_out_valid(t_ov[3]), .lk_out_last(t_ol[3]), .lk_out_data(t_od[3]), .cr_in(t_ci[3]),
        .cfg_run(cfg_run), .cfg_pattern(cfg_pattern), .cfg_thresh(cfg_thresh), .cfg_len(cfg_len),
        .cfg_npkts(cfg_npkts), .cfg_check_dst(cfg_check_dst), .cfg_stall_max(cfg_stall_max),
        .gen_valid(gen_valid[3]), .gen_dst(gen_dst[3*4 +: 4]), .gen_seq(gen_seq[3*16 +: 16]), .gen_count(gen_count[3*16 +: 16]), .sent_pkts(sent_pkts[3*16 +: 16]), .done(done[3]), .err(err[3]), .e_loss(e_loss[3]), .e_dup(e_dup[3]), .e_payload(e_payload[3]), .e_dest(e_dest[3]), .e_frame(e_frame[3]), .err_count(err_count[3*16 +: 16]), .rx_flits(rx_flits[3*32 +: 32]), .rx_pkts(rx_pkts[3*32 +: 32]), .rx_pkt_valid(rx_pkt_valid[3]), .rx_src(rx_src[3*4 +: 4]), .rx_dst(rx_dst[3*4 +: 4]), .rx_seq(rx_seq[3*16 +: 16])
    );

endmodule
