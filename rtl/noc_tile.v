// noc_tile: one mesh tile = router + traffic generator + checker, with one
// link register per direction (N/E/S/W) at the tile edge (decisions 0002, 0003).
// Plain Verilog-2005.
//
// Link buses are flattened per direction, d = N0 E1 S2 W3 (same numbering as
// noc_router): direction d occupies bit d of a one-bit bus and bits [d*32 +: 32]
// of a data bus.
//   lk_out_*   flit leaving towards the neighbour in direction d, registered
//   lk_in_*    flit arriving from the neighbour in direction d
//   cr_out[d]  credit returned to the neighbour in direction d (registered)
//   cr_in[d]   credit arriving from the neighbour in direction d
// Credit return is registered at the edge like the forward link, so every
// link signal crossing a tile boundary is a plain flop output on the sender's
// side. The local port (4) is tile-internal and unregistered.
module noc_tile #(
    parameter [1:0] X       = 2'd0,
    parameter [1:0] Y       = 2'd0,
    parameter       DEPTH   = 4,
    parameter       QAW     = 7,
    parameter       MESH_XW = 1,
    parameter       MESH_YW = 1,
    parameter       HOT_X   = 1,
    parameter       HOT_Y   = 1,
    parameter [31:0] GSEED  = 32'h1badc0de,
    parameter [31:0] CSEED  = 32'h0c0ffee1
) (
    input  wire         clk,
    input  wire         rst_n,

    // tile-edge links
    input  wire [3:0]   lk_in_valid,
    input  wire [3:0]   lk_in_last,
    input  wire [127:0] lk_in_data,
    output wire [3:0]   cr_out,
    output wire [3:0]   lk_out_valid,
    output wire [3:0]   lk_out_last,
    output wire [127:0] lk_out_data,
    input  wire [3:0]   cr_in,

    // endpoint configuration (see noc_tgen / noc_tchk)
    input  wire         cfg_run,
    input  wire [1:0]   cfg_pattern,
    input  wire [16:0]  cfg_thresh,
    input  wire [7:0]   cfg_len,
    input  wire [7:0]   cfg_npkts,
    input  wire         cfg_check_dst,
    input  wire [3:0]   cfg_stall_max,

    // endpoint observability
    output wire         gen_valid,
    output wire [3:0]   gen_dst,
    output wire [15:0]  gen_seq,
    output wire [15:0]  gen_count,
    output wire [15:0]  sent_pkts,
    output wire         done,
    output wire         err,
    output wire         e_loss,
    output wire         e_dup,
    output wire         e_payload,
    output wire         e_dest,
    output wire         e_frame,
    output wire [15:0]  err_count,
    output wire [31:0]  rx_flits,
    output wire [31:0]  rx_pkts,
    output wire         rx_pkt_valid,
    output wire [3:0]   rx_src,
    output wire [3:0]   rx_dst,
    output wire [15:0]  rx_seq
);
    // router <-> endpoint (port 4) and router edge ports (0..3)
    wire [4:0]   r_in_valid, r_in_last, r_in_credit;
    wire [159:0] r_in_data;
    wire [4:0]   r_out_valid, r_out_last, r_out_credit;
    wire [159:0] r_out_data;

    wire         g_valid, g_last, g_credit;
    wire [31:0]  g_data;
    wire         c_credit;

    noc_router #(.X(X), .Y(Y), .DEPTH(DEPTH)) u_router (
        .clk(clk), .rst_n(rst_n),
        .in_valid(r_in_valid), .in_last(r_in_last), .in_data(r_in_data),
        .in_credit(r_in_credit),
        .out_valid(r_out_valid), .out_last(r_out_last), .out_data(r_out_data),
        .out_credit(r_out_credit),
        .dbg_occ(), .dbg_credits()
    );

    noc_tgen #(.DEPTH(DEPTH), .QAW(QAW), .MESH_XW(MESH_XW), .MESH_YW(MESH_YW),
               .HOT_X(HOT_X), .HOT_Y(HOT_Y), .SEED(GSEED)) u_tgen (
        .clk(clk), .rst_n(rst_n), .my_x(X), .my_y(Y),
        .cfg_run(cfg_run), .cfg_pattern(cfg_pattern), .cfg_thresh(cfg_thresh),
        .cfg_len(cfg_len), .cfg_npkts(cfg_npkts),
        .out_valid(g_valid), .out_last(g_last), .out_data(g_data),
        .credit_in(g_credit),
        .gen_valid(gen_valid), .gen_dst(gen_dst), .gen_seq(gen_seq),
        .gen_count(gen_count), .sent_pkts(sent_pkts), .done(done)
    );

    noc_tchk #(.SEED(CSEED)) u_tchk (
        .clk(clk), .rst_n(rst_n), .my_x(X), .my_y(Y),
        .cfg_check_dst(cfg_check_dst), .cfg_stall_max(cfg_stall_max),
        .in_valid(r_out_valid[4]), .in_last(r_out_last[4]),
        .in_data(r_out_data[4*32 +: 32]),
        .credit_out(c_credit),
        .err(err), .e_loss(e_loss), .e_dup(e_dup), .e_payload(e_payload),
        .e_dest(e_dest), .e_frame(e_frame), .err_count(err_count),
        .rx_flits(rx_flits), .rx_pkts(rx_pkts),
        .rx_pkt_valid(rx_pkt_valid), .rx_src(rx_src), .rx_dst(rx_dst),
        .rx_seq(rx_seq)
    );

    // local port wiring
    assign r_in_valid[4]        = g_valid;
    assign r_in_last[4]         = g_last;
    assign r_in_data[4*32 +: 32] = g_data;
    assign g_credit             = r_in_credit[4];
    assign r_out_credit[4]      = c_credit;

    // edge: inputs straight into the router, outputs and credit returns registered
    reg [3:0]   q_valid, q_last, q_cr;
    reg [127:0] q_data;

    assign r_in_valid[3:0]    = lk_in_valid;
    assign r_in_last[3:0]     = lk_in_last;
    assign r_in_data[127:0]   = lk_in_data;
    assign r_out_credit[3:0]  = cr_in;

    always @(posedge clk) begin
        if (!rst_n) begin
            q_valid <= 4'b0;
            q_last  <= 4'b0;
            q_cr    <= 4'b0;
        end else begin
            q_valid <= r_out_valid[3:0];
            q_last  <= r_out_last[3:0];
            q_cr    <= r_in_credit[3:0];
        end
        q_data <= r_out_data[127:0];
    end

    assign lk_out_valid = q_valid;
    assign lk_out_last  = q_last;
    assign lk_out_data  = q_data;
    assign cr_out       = q_cr;
endmodule
