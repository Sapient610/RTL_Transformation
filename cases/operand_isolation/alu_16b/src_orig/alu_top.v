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
    wire [15:0] raw_res;

    // 原始设计：无操作数隔离，外部总线杂散翻转始终直接驱动深层组合逻辑阵列
    alu_core u_core_raw (
        .opcode (opcode),
        .op_a   (op_a),
        .op_b   (op_b),
        .result (raw_res)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            res_out   <= 16'd0;
        end else begin
            valid_out <= valid_in;
            if (valid_in)
                res_out <= raw_res;
            else
                res_out <= 16'd0;
        end
    end
endmodule
