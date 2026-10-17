// SMOKE FIXTURE -- NOT DESIGN.
// Throwaway module used only to push one clocked block through the
// klt synthesize / place-and-route / drc / lvs / sta chain (issue #4).
// It decides nothing about routers, flits, links or the mesh, and is
// excluded from any design-source inventory.
//
// Plain Verilog-2005 on purpose: `klt synthesize` hands sources to Yosys
// without a SystemVerilog front end (see README.md, gap list).
module smoke_counter (
    input  wire       clk,
    input  wire       rst_n,
    output reg  [7:0] q
);
    reg [7:0] cnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) cnt <= 8'd0;
        else        cnt <= cnt + 8'd1;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) q <= 8'd0;
        else        q <= cnt;
    end
endmodule
