// =============================================================================
// Transposed FIR Filter (Data Gated Architecture) - 8 Taps
// =============================================================================
module fir_top (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  data_valid,
    input  wire signed [7:0]     sample_in,
    output reg                   valid_out,
    output reg  signed [15:0]    data_out
);
    localparam NUM_TAPS = 8;

    // 滤波器常数系数表
    localparam signed [7:0] COEFF_0 = 8'sd3;
    localparam signed [7:0] COEFF_1 = 8'sd11;
    localparam signed [7:0] COEFF_2 = 8'sd28;
    localparam signed [7:0] COEFF_3 = 8'sd54;
    localparam signed [7:0] COEFF_4 = 8'sd54;
    localparam signed [7:0] COEFF_5 = 8'sd28;
    localparam signed [7:0] COEFF_6 = 8'sd11;
    localparam signed [7:0] COEFF_7 = 8'sd3;

    // 数据门控逻辑：在采样无效 (data_valid == 0) 时将输入总线钳位为 0
    // 从而切断 sample_in 翻转广播向所有 8 个并行乘法器的传播
    wire signed [7:0] gated_sample = data_valid ? sample_in : 8'sd0;

    // 门控乘法器阵列
    wire signed [15:0] gated_m_0 = gated_sample * COEFF_0;
    wire signed [15:0] gated_m_1 = gated_sample * COEFF_1;
    wire signed [15:0] gated_m_2 = gated_sample * COEFF_2;
    wire signed [15:0] gated_m_3 = gated_sample * COEFF_3;
    wire signed [15:0] gated_m_4 = gated_sample * COEFF_4;
    wire signed [15:0] gated_m_5 = gated_sample * COEFF_5;
    wire signed [15:0] gated_m_6 = gated_sample * COEFF_6;
    wire signed [15:0] gated_m_7 = gated_sample * COEFF_7;

    // 转置型抽头累加寄存器
    reg signed [15:0] r_tap_0;
    reg signed [15:0] r_tap_1;
    reg signed [15:0] r_tap_2;
    reg signed [15:0] r_tap_3;
    reg signed [15:0] r_tap_4;
    reg signed [15:0] r_tap_5;
    reg signed [15:0] r_tap_6;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            data_out  <= 16'sd0;
            r_tap_0 <= 16'sd0;
            r_tap_1 <= 16'sd0;
            r_tap_2 <= 16'sd0;
            r_tap_3 <= 16'sd0;
            r_tap_4 <= 16'sd0;
            r_tap_5 <= 16'sd0;
            r_tap_6 <= 16'sd0;
        end else begin
            valid_out <= data_valid;
            if (data_valid) begin
                data_out <= gated_m_0 + r_tap_0;
                r_tap_0 <= gated_m_1 + r_tap_1;
                r_tap_1 <= gated_m_2 + r_tap_2;
                r_tap_2 <= gated_m_3 + r_tap_3;
                r_tap_3 <= gated_m_4 + r_tap_4;
                r_tap_4 <= gated_m_5 + r_tap_5;
                r_tap_5 <= gated_m_6 + r_tap_6;
                r_tap_6 <= gated_m_7;
            end else begin
                data_out <= 16'sd0;
            end
        end
    end
endmodule
