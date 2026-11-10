// Example design for the flowgen regression: a register with enable.
`include "block_defines.svh"

module block
  import block_pkg::*;
(
  input  logic             clk,
  input  logic             en,
  input  logic [WIDTH-1:0] d,
  output logic [WIDTH-1:0] q
);
  always_ff @(posedge clk) begin
    if (en) q <= d;
  end
endmodule
