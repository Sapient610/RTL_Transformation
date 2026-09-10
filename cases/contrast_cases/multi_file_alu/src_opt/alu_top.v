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

    // 低功耗变换：无毛刺时钟门控（Glitch-Free Integrated Clock Gating）
    // =========================================================================
    // 【负优化对照案例说明】：
    // 本用例特意用于展示“门控时钟损益平衡点 (Breakeven Bitwidth)”未达标时的现象。
    // 此处仅对 16-bit 输出寄存器进行门控，Sequential 功耗确实下降了 66%，
    // 但后端为生成的 gated_clk 建立了独立分支时钟树，引入的时钟网络开销 (~69 uW)
    // 超过了 16-bit 寄存器节省的收益 (~50 uW)；加之前级纯组合逻辑 alu_core 仍满负荷
    // 翻转（占总功耗 75%），最终导致设计总功耗净增 +4.17%。
    // =========================================================================
    reg en_latch;
    always @(clk or valid_in) begin
        if (!clk)
            en_latch <= valid_in;
    end
    wire gated_clk = clk & en_latch;

    // 控制通道寄存器保持主时钟触发
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            valid_out <= 1'b0;
        else
            valid_out <= valid_in;
    end

    // 数据通道高位宽寄存器由门控时钟直接驱动，节省翻转功耗
    always @(posedge gated_clk or negedge rst_n) begin
        if (!rst_n)
            res_out <= 16'h0000;
        else
            res_out <= core_res;
    end

endmodule
