// Example synthesized netlist for the flowgen regression.
// Cell names are placeholders; this is not a real library mapping.
module block (clk, en, d, q);
  input clk;
  input en;
  input [3:0] d;
  output [3:0] q;
  wire [3:0] n;

  MUX2X1 u_mux0 (.A(q[0]), .B(d[0]), .S(en), .Y(n[0]));
  MUX2X1 u_mux1 (.A(q[1]), .B(d[1]), .S(en), .Y(n[1]));
  MUX2X1 u_mux2 (.A(q[2]), .B(d[2]), .S(en), .Y(n[2]));
  MUX2X1 u_mux3 (.A(q[3]), .B(d[3]), .S(en), .Y(n[3]));
  DFFQX1 u_q0 (.CK(clk), .D(n[0]), .Q(q[0]));
  DFFQX1 u_q1 (.CK(clk), .D(n[1]), .Q(q[1]));
  DFFQX1 u_q2 (.CK(clk), .D(n[2]), .Q(q[2]));
  DFFQX1 u_q3 (.CK(clk), .D(n[3]), .Q(q[3]));
endmodule
