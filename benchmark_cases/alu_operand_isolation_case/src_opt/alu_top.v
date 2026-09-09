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
    // 低功耗变换：操作数隔离（Operand Isolation）
    // 当 valid_in 无效时，通过前级门控逻辑切断 op_a、op_b、opcode 向组合运算模块的传播，
    // 使 alu_core 内部加法器/乘法移位器等高功耗网络在空闲周期保持静止，大幅降低组合逻辑翻转功耗。
    wire [15:0] iso_a  = valid_in ? op_a   : 16'h0000;
    wire [15:0] iso_b  = valid_in ? op_b   : 16'h0000;
    wire [2:0]  iso_op = valid_in ? opcode : 3'b000;
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
            res_out   <= 16'h0000;
        end else begin
            valid_out <= valid_in;
            if (valid_in)
                res_out <= iso_res;
            else
                res_out <= 16'h0000;
        end
    end

endmodule

