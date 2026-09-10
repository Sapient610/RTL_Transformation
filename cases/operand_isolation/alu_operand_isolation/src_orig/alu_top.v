module alu_top (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid_in,
    input  wire [2:0]  opcode,
    input  wire [15:0] op_a,
    input  wire [15:0] op_b,
    output reg         valid_out,
    output reg  [15:0] res_out
);
    wire [15:0] raw_res;

    // 原始设计：无论 valid_in 是否有效，未经隔离的原始操作数始终驱动 alu_core 进行高频翻转运算
    alu_core u_core_raw (
        .opcode (opcode),
        .op_a   (op_a),
        .op_b   (op_b),
        .result (raw_res)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            res_out   <= 16'h0000;
        end else begin
            valid_out <= valid_in;
            if (valid_in)
                res_out <= raw_res;
            else
                res_out <= 16'h0000;
        end
    end

endmodule

