// =============================================================================
// Transposed FIR Filter (Original Un-gated Baseline) - 8 Taps
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

    // 乘法器阵列 (未门控：sample_in 广播连接至所有乘法器)
    wire signed [15:0] raw_m_0 = sample_in * COEFF_0;
    wire signed [15:0] raw_m_1 = sample_in * COEFF_1;
    wire signed [15:0] raw_m_2 = sample_in * COEFF_2;
    wire signed [15:0] raw_m_3 = sample_in * COEFF_3;
    wire signed [15:0] raw_m_4 = sample_in * COEFF_4;
    wire signed [15:0] raw_m_5 = sample_in * COEFF_5;
    wire signed [15:0] raw_m_6 = sample_in * COEFF_6;
    wire signed [15:0] raw_m_7 = sample_in * COEFF_7;

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
                data_out <= raw_m_0 + r_tap_0;
                r_tap_0 <= raw_m_1 + r_tap_1;
                r_tap_1 <= raw_m_2 + r_tap_2;
                r_tap_2 <= raw_m_3 + r_tap_3;
                r_tap_3 <= raw_m_4 + r_tap_4;
                r_tap_4 <= raw_m_5 + r_tap_5;
                r_tap_5 <= raw_m_6 + r_tap_6;
                r_tap_6 <= raw_m_7;
            end else begin
                data_out <= 16'sd0;
            end
        end
    end
endmodule
