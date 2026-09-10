// =============================================================================
// Transposed FIR Filter (Original Un-gated Baseline) - 4 Taps
// =============================================================================
module fir_top (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  data_valid,
    input  wire signed [7:0]     sample_in,
    output reg                   valid_out,
    output reg  signed [15:0]    data_out
);
    localparam NUM_TAPS = 4;

    // 滤波器常数系数表
    localparam signed [7:0] COEFF_0 = 8'sd12;
    localparam signed [7:0] COEFF_1 = 8'sd52;
    localparam signed [7:0] COEFF_2 = 8'sd52;
    localparam signed [7:0] COEFF_3 = 8'sd12;

    // 乘法器阵列 (未门控：sample_in 广播连接至所有乘法器)
    wire signed [15:0] raw_m_0 = sample_in * COEFF_0;
    wire signed [15:0] raw_m_1 = sample_in * COEFF_1;
    wire signed [15:0] raw_m_2 = sample_in * COEFF_2;
    wire signed [15:0] raw_m_3 = sample_in * COEFF_3;

    // 转置型抽头累加寄存器
    reg signed [15:0] r_tap_0;
    reg signed [15:0] r_tap_1;
    reg signed [15:0] r_tap_2;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            data_out  <= 16'sd0;
            r_tap_0 <= 16'sd0;
            r_tap_1 <= 16'sd0;
            r_tap_2 <= 16'sd0;
        end else begin
            valid_out <= data_valid;
            if (data_valid) begin
                data_out <= raw_m_0 + r_tap_0;
                r_tap_0 <= raw_m_1 + r_tap_1;
                r_tap_1 <= raw_m_2 + r_tap_2;
                r_tap_2 <= raw_m_3;
            end else begin
                data_out <= 16'sd0;
            end
        end
    end
endmodule
