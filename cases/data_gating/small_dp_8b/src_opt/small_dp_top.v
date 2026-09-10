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
    wire [7:0] gated_res;

    // 数据门控优化：在计算核输入端插入门控隔离逻辑
    wire [7:0] gated_op_a = gate_en ? op_a : {8{1'b0}};
    wire [7:0] gated_op_b = gate_en ? op_b : {8{1'b0}};
    wire [2:0]     gated_opc  = gate_en ? opcode : 3'b000;

    small_dp_core u_core_gated (
        .opcode (gated_opc),
        .op_a   (gated_op_a),
        .op_b   (gated_op_b),
        .result (gated_res)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            res_out   <= {8{1'b0}};
        end else begin
            valid_out <= gate_en;
            if (gate_en)
                res_out <= gated_res;
            else
                res_out <= {8{1'b0}};
        end
    end
endmodule
