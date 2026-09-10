module alu_top (
    input  wire             clk,
    input  wire             rst_n,
    input  wire             valid_in,
    input  wire [2:0]       opcode,
    input  wire [15:0]   op_a,
    input  wire [15:0]   op_b,
    output reg              valid_out,
    output reg  [15:0]   res_out
);
    // 操作数隔离 (Operand Isolation):
    // 当 valid_in 无效时，通过前级门控将 op_a, op_b 锁定为 0，阻断杂散翻转向组合逻辑云传播
    wire [15:0] iso_a  = valid_in ? op_a   : 16'd0;
    wire [15:0] iso_b  = valid_in ? op_b   : 16'd0;
    wire [2:0]     iso_op = valid_in ? opcode : 3'b000;
    wire [15:0] iso_res;

    alu_core u_core_iso (
        .opcode (iso_op),
        .op_a   (iso_a),
        .op_b   (iso_b),
        .result (iso_res)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            res_out   <= 16'd0;
        end else begin
            valid_out <= valid_in;
            if (valid_in)
                res_out <= iso_res;
            else
                res_out <= 16'd0;
        end
    end
endmodule
