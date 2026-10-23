// Body-flit payload shared by noc_tgen (producer) and noc_tchk (verifier).
// A pure function of (src, dst, seq, flit index), so the checker verifies
// payload integrity with no help from the bench. Plain Verilog-2005.
// src/dst are node ids {y[1:0], x[1:0]}. xorshift32 is a bijection, so two
// different tuples never alias to the same payload word.
function [31:0] noc_payload;
  input [3:0]  src;
  input [3:0]  dst;
  input [15:0] seq;
  input [7:0]  idx;
  reg [31:0] t;
  begin
    t = {src, dst, seq, idx};
    t = t ^ (t << 13);
    t = t ^ (t >> 17);
    t = t ^ (t << 5);
    noc_payload = t ^ 32'h5A5AC3C3;
  end
endfunction
