// =============================================================================
// Transposed FIR Filter (Original Un-gated Baseline) - 16 Taps
// =============================================================================
module fir_top (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  data_valid,
    input  wire signed [7:0]     sample_in,
    output reg                   valid_out,
    output reg  signed [15:0]    data_out
);
    localparam NUM_TAPS = 16;

    // 滤波器常数系数表
    localparam signed [7:0] COEFF_0 = 8'sd1;
    localparam signed [7:0] COEFF_1 = 8'sd2;
    localparam signed [7:0] COEFF_2 = 8'sd5;
    localparam signed [7:0] COEFF_3 = 8'sd11;
    localparam signed [7:0] COEFF_4 = 8'sd21;
    localparam signed [7:0] COEFF_5 = 8'sd34;
    localparam signed [7:0] COEFF_6 = 8'sd47;
    localparam signed [7:0] COEFF_7 = 8'sd57;
    localparam signed [7:0] COEFF_8 = 8'sd57;
    localparam signed [7:0] COEFF_9 = 8'sd47;
    localparam signed [7:0] COEFF_10 = 8'sd34;
    localparam signed [7:0] COEFF_11 = 8'sd21;
    localparam signed [7:0] COEFF_12 = 8'sd11;
    localparam signed [7:0] COEFF_13 = 8'sd5;
    localparam signed [7:0] COEFF_14 = 8'sd2;
    localparam signed [7:0] COEFF_15 = 8'sd1;

    // 乘法器阵列 (未门控：sample_in 广播连接至所有乘法器)
    wire signed [15:0] raw_m_0 = sample_in * COEFF_0;
    wire signed [15:0] raw_m_1 = sample_in * COEFF_1;
    wire signed [15:0] raw_m_2 = sample_in * COEFF_2;
    wire signed [15:0] raw_m_3 = sample_in * COEFF_3;
    wire signed [15:0] raw_m_4 = sample_in * COEFF_4;
    wire signed [15:0] raw_m_5 = sample_in * COEFF_5;
    wire signed [15:0] raw_m_6 = sample_in * COEFF_6;
    wire signed [15:0] raw_m_7 = sample_in * COEFF_7;
    wire signed [15:0] raw_m_8 = sample_in * COEFF_8;
    wire signed [15:0] raw_m_9 = sample_in * COEFF_9;
    wire signed [15:0] raw_m_10 = sample_in * COEFF_10;
    wire signed [15:0] raw_m_11 = sample_in * COEFF_11;
    wire signed [15:0] raw_m_12 = sample_in * COEFF_12;
    wire signed [15:0] raw_m_13 = sample_in * COEFF_13;
    wire signed [15:0] raw_m_14 = sample_in * COEFF_14;
    wire signed [15:0] raw_m_15 = sample_in * COEFF_15;

    // 转置型抽头累加寄存器
    reg signed [15:0] r_tap_0;
    reg signed [15:0] r_tap_1;
    reg signed [15:0] r_tap_2;
    reg signed [15:0] r_tap_3;
    reg signed [15:0] r_tap_4;
    reg signed [15:0] r_tap_5;
    reg signed [15:0] r_tap_6;
    reg signed [15:0] r_tap_7;
    reg signed [15:0] r_tap_8;
    reg signed [15:0] r_tap_9;
    reg signed [15:0] r_tap_10;
    reg signed [15:0] r_tap_11;
    reg signed [15:0] r_tap_12;
    reg signed [15:0] r_tap_13;
    reg signed [15:0] r_tap_14;

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
            r_tap_7 <= 16'sd0;
            r_tap_8 <= 16'sd0;
            r_tap_9 <= 16'sd0;
            r_tap_10 <= 16'sd0;
            r_tap_11 <= 16'sd0;
            r_tap_12 <= 16'sd0;
            r_tap_13 <= 16'sd0;
            r_tap_14 <= 16'sd0;
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
                r_tap_6 <= raw_m_7 + r_tap_7;
                r_tap_7 <= raw_m_8 + r_tap_8;
                r_tap_8 <= raw_m_9 + r_tap_9;
                r_tap_9 <= raw_m_10 + r_tap_10;
                r_tap_10 <= raw_m_11 + r_tap_11;
                r_tap_11 <= raw_m_12 + r_tap_12;
                r_tap_12 <= raw_m_13 + r_tap_13;
                r_tap_13 <= raw_m_14 + r_tap_14;
                r_tap_14 <= raw_m_15;
            end else begin
                data_out <= 16'sd0;
            end
        end
    end
endmodule
