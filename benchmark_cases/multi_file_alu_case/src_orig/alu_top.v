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
    wire [15:0] core_res;

    // 实例化算术核心子模块
    alu_core u_core (
        .opcode (opcode),
        .op_a   (op_a),
        .op_b   (op_b),
        .result (core_res)
    );

    // 原始设计：常规数据使能控制（MUX-based 寄存器加载控制）
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            res_out   <= 16'h0000;
        end else begin
            valid_out <= valid_in;
            if (valid_in)
                res_out <= core_res;
        end
    end

endmodule
