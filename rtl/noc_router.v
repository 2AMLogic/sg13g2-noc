// noc_router: 5-port wormhole XY router, credit-based flow control.
// Plain Verilog-2001 so Icarus and Yosys both take it (see rtl/README.md).
//
// Ports are numbered N=0 (+Y), E=1 (+X), S=2 (-Y), W=3 (-X), L=4 (local).
// Vectors are flattened: port p occupies bits [p*32 +: 32] of a data bus and
// bit p of a one-bit-per-port bus.
//
// Link, per port (spec/noc.md section 2, decision 0002):
//   in_valid/in_last/in_data   flit arriving from the neighbour
//   in_credit                  one-cycle pulse: a flit left this input FIFO
//   out_valid/out_last/out_data  flit leaving towards the neighbour (registered)
//   out_credit                 one-cycle pulse from the neighbour: a slot freed
// The 1-cycle link register per direction lives at the tile edge, outside this
// module (decision 0003).
//
// Pipeline: a flit seen on in_* in cycle t is written to the input FIFO at the
// end of t; in cycle t+1 it is routed, arbitrated and switched into the output
// register; it is on out_* in cycle t+2. That is the 2 cycles/hop in the router
// of spec/noc.md section 1.
module noc_router #(
    parameter       DEPTH = 4       // input FIFO flits per port; downstream DEPTH too
) (
    input  wire         clk,
    input  wire         rst_n,      // active low, synchronous
    input  wire [1:0]   my_x,       // this router's coordinates; constant after reset
    input  wire [1:0]   my_y,

    input  wire [4:0]   in_valid,
    input  wire [4:0]   in_last,
    input  wire [159:0] in_data,
    output wire [4:0]   in_credit,

    output wire [4:0]   out_valid,
    output wire [4:0]   out_last,
    output wire [159:0] out_data,
    input  wire [4:0]   out_credit,

    // Observability for the credit-conservation check; leave open in a tile.
    output wire [14:0]  dbg_occ,    // input FIFO occupancy, 3 bits per port
    output wire [14:0]  dbg_credits // output credit counter, 3 bits per port
);
    localparam PW = (DEPTH < 2) ? 1 : $clog2(DEPTH);   // FIFO pointer width
    localparam CW = 3;                                   // counter width; DEPTH <= 7
    localparam [CW-1:0] DEPTH_C = DEPTH;

    // ---------------------------------------------------------------- inputs
    wire [4:0]   head_valid;
    wire [4:0]   head_last;
    wire [159:0] head_data;
    wire [4:0]   pop;                  // head flit of input i leaves this cycle
    reg  [4:0]   in_busy;              // mid-packet: head sent, tail not yet
    reg  [24:0]  in_route;             // locked one-hot route, 5 bits per input
    reg  [24:0]  route_comb;           // route of the head flit, 5 bits per input

    genvar gi;
    generate
        for (gi = 0; gi < 5; gi = gi + 1) begin : g_in
            reg [32:0]   mem [0:DEPTH-1];
            reg [PW-1:0] wr_ptr, rd_ptr;
            reg [CW-1:0] occ;

            wire push = in_valid[gi];
            wire [32:0] head = mem[rd_ptr];

            assign head_valid[gi]            = (occ != 0);
            assign head_last[gi]             = head[32];
            assign head_data[gi*32 +: 32]    = head[31:0];
            assign dbg_occ[gi*3 +: 3]        = occ;

            always @(posedge clk) begin
                if (!rst_n) begin
                    wr_ptr <= 0;
                    rd_ptr <= 0;
                    occ    <= 0;
                end else begin
                    if (push) begin
                        mem[wr_ptr] <= {in_last[gi], in_data[gi*32 +: 32]};
                        wr_ptr <= (wr_ptr == DEPTH-1) ? 0 : wr_ptr + 1'b1;
                    end
                    if (pop[gi])
                        rd_ptr <= (rd_ptr == DEPTH-1) ? 0 : rd_ptr + 1'b1;
                    occ <= occ + push - pop[gi];
                end
            end
        end
    endgenerate

    // XY route compute on the head flit: X first, then Y, then local.
    integer ri;
    reg [1:0] dx, dy;
    always @* begin
        route_comb = 25'd0;
        dx = 2'd0;
        dy = 2'd0;
        for (ri = 0; ri < 5; ri = ri + 1) begin
            dx = head_data[ri*32 + 30 +: 2];
            dy = head_data[ri*32 + 28 +: 2];
            if      (dx > my_x) route_comb[ri*5 + 1] = 1'b1;   // E
            else if (dx < my_x) route_comb[ri*5 + 3] = 1'b1;   // W
            else if (dy > my_y) route_comb[ri*5 + 0] = 1'b1;   // N
            else if (dy < my_y) route_comb[ri*5 + 2] = 1'b1;   // S
            else             route_comb[ri*5 + 4] = 1'b1;   // L
`ifdef NEG_YX_TURN
            // Negative control: a packet entering from N or S that should keep
            // going in Y is turned back into X (a Y-to-X turn, spec 3 item 1).
            if ((ri == 0 || ri == 2) && (route_comb[ri*5 + 0] || route_comb[ri*5 + 2])) begin
                route_comb[ri*5 + 0] = 1'b0;
                route_comb[ri*5 + 2] = 1'b0;
                route_comb[ri*5 + 1] = 1'b1;
            end
`endif
        end
    end

    // ------------------------------------------------------------ arbitration
    reg  [CW-1:0] credits [0:4];       // output credit counters
    reg  [2:0]    rr_ptr  [0:4];       // round-robin priority pointer per output
    reg  [24:0]   grant;               // grant[i*5 + o]: input i sends to output o
    reg  [24:0]   wants;
    reg  [4:0]    busy_out;            // output held by a mid-packet input
    reg  [4:0]    can_send;            // output has a credit (this cycle's, incl. arriving)
    reg  [2:0]    rr_pick [0:4];
    reg           rr_any  [0:4];
    integer ai, ao;

    integer wi, wo;
    always @* begin
        wants    = 25'd0;
        busy_out = 5'd0;
        for (wo = 0; wo < 5; wo = wo + 1)
            can_send[wo] = (credits[wo] != 0) || out_credit[wo];
        for (wi = 0; wi < 5; wi = wi + 1)
            for (wo = 0; wo < 5; wo = wo + 1) begin
                wants[wi*5 + wo] = head_valid[wi] &&
                    (in_busy[wi] ? in_route[wi*5 + wo] : route_comb[wi*5 + wo]);
                if (in_busy[wi] && in_route[wi*5 + wo])
                    busy_out[wo] = 1'b1;
            end
    end

    always @* begin
        grant = 25'd0;
        ai = 0;
        ao = 0;
        for (ao = 0; ao < 5; ao = ao + 1) begin
            // grant is held until `last` leaves: only the owner may go
            for (ai = 0; ai < 5; ai = ai + 1)
                if (can_send[ao] && busy_out[ao] && in_busy[ai] && wants[ai*5 + ao])
                    grant[ai*5 + ao] = 1'b1;
            if (can_send[ao] && !busy_out[ao] && rr_any[ao])
                grant[rr_pick[ao]*5 + ao] = 1'b1;
        end
    end

    // Round-robin pick per output: first requester at or after rr_ptr.
    integer pa, pk;
    reg [2:0] cand;
    always @* begin
        for (pa = 0; pa < 5; pa = pa + 1) begin
            rr_pick[pa] = 3'd0;
            rr_any[pa]  = 1'b0;
            for (pk = 4; pk >= 0; pk = pk - 1) begin
                cand = (rr_ptr[pa] + pk) % 5;
                if (wants[cand*5 + pa]) begin
                    rr_pick[pa] = cand;
                    rr_any[pa]  = 1'b1;
                end
            end
        end
    end

    // Crossbar: output o takes the flit of the (at most one) input granted it.
    reg [4:0]   sw_valid;
    reg [4:0]   sw_last;
    reg [159:0] sw_data;
    reg [2:0]   sw_src [0:4];
    integer si, so;
    always @* begin
        sw_valid = 5'd0;
        sw_last  = 5'd0;
        sw_data  = 160'd0;
        for (so = 0; so < 5; so = so + 1) begin
            sw_src[so] = 3'd0;
            for (si = 0; si < 5; si = si + 1)
                if (grant[si*5 + so]) begin
                    sw_valid[so]          = 1'b1;
                    sw_last[so]           = head_last[si];
                    sw_data[so*32 +: 32]  = head_data[si*32 +: 32];
                    sw_src[so]            = si;
                end
        end
    end

    genvar gp;
    generate
        for (gp = 0; gp < 5; gp = gp + 1) begin : g_pop
            assign pop[gp] = |grant[gp*5 +: 5];
        end
    endgenerate

    // ---------------------------------------------------------------- credits
    // Credit goes back upstream in the cycle the flit leaves the input FIFO.
    reg [4:0] credit_comb;
    always @* credit_comb = pop;

`ifdef NEG_DROP_CREDIT
    // Negative control: swallow the first credit return on input port 0.
    reg dropped;
    always @(posedge clk)
        if (!rst_n)                       dropped <= 1'b0;
        else if (pop[0] && !dropped)      dropped <= 1'b1;
    assign in_credit = {credit_comb[4:1], credit_comb[0] & dropped};
`else
    assign in_credit = credit_comb;
`endif

    // ------------------------------------------------------------ state update
    reg [4:0]   ov;
    reg [4:0]   ol;
    reg [159:0] od;
    assign out_valid = ov;
    assign out_last  = ol;
    assign out_data  = od;

    integer ui, uo;
    always @(posedge clk) begin
        if (!rst_n) begin
            ov      <= 5'd0;
            ol      <= 5'd0;
            od      <= 160'd0;
            in_busy <= 5'd0;
            in_route <= 25'd0;
            for (uo = 0; uo < 5; uo = uo + 1) begin
                credits[uo] <= DEPTH_C;
                rr_ptr[uo]  <= 3'd0;
            end
        end else begin
            ov <= sw_valid;
            ol <= sw_last;
            od <= sw_data;
            for (uo = 0; uo < 5; uo = uo + 1) begin
                credits[uo] <= credits[uo] + out_credit[uo] - sw_valid[uo];
                // advance the priority pointer past a freshly granted head
                if (sw_valid[uo] && !busy_out[uo])
                    rr_ptr[uo] <= (sw_src[uo] == 3'd4) ? 3'd0 : sw_src[uo] + 3'd1;
            end
            for (ui = 0; ui < 5; ui = ui + 1) begin
                if (pop[ui]) begin
                    if (head_last[ui]) begin
                        in_busy[ui] <= 1'b0;
                    end else if (!in_busy[ui]) begin
                        in_busy[ui]                <= 1'b1;
                        in_route[ui*5 +: 5]        <= route_comb[ui*5 +: 5];
                    end
                end
            end
        end
    end

    genvar gc;
    generate
        for (gc = 0; gc < 5; gc = gc + 1) begin : g_dbg
            assign dbg_credits[gc*3 +: 3] = credits[gc];
        end
    endgenerate
endmodule
