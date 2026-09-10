module small_dp_top (
    input  wire             clk,
    input  wire             rst_n,
    input  wire             gate_en,
    input  wire [2:0]       opcode,
    input  wire [7:0]     op_a,
    input  wire [7:0]     op_b,
    output reg              valid_out,
    output reg  [7:0]     res_out
);
    wire [7:0] raw_res;

    // 原始设计：未采用数据门控，输入总线杂散翻转直通微型计算核
    small_dp_core u_core_raw (
        .opcode (opcode),
        .op_a   (op_a),
        .op_b   (op_b),
        .result (raw_res)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            res_out   <= {8{1'b0}};
        end else begin
            valid_out <= gate_en;
            if (gate_en)
                res_out <= raw_res;
            else
                res_out <= {8{1'b0}};
        end
    end
endmodule
