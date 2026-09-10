module small_dp_core (
    input  wire [2:0]       opcode,
    input  wire [15:0]     op_a,
    input  wire [15:0]     op_b,
    output reg  [15:0]     result
);
    always @(*) begin
        case (opcode)
            3'b000: result = op_a + op_b;
            3'b001: result = op_a - op_b;
            3'b010: result = op_a & op_b;
            3'b011: result = op_a | op_b;
            3'b100: result = op_a ^ op_b;
            3'b101: result = (op_a < op_b) ? op_a : op_b;
            3'b110: result = (op_a > op_b) ? (op_a - op_b) : (op_b - op_a);
            3'b111: result = (op_a << op_b[1:0]);
            default: result = {16{1'b0}};
        endcase
    end
endmodule
