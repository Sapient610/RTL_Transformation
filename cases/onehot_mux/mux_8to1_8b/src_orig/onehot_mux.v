// ==============================================================================
// 纯二进制编码多路选择器 (Pure Binary-Coded Multiplexer) - 8-to-1 / 8-bit
// cases/onehot_mux/mux_8to1_8b/src_orig/onehot_mux.v
//
// 原始架构：
//   - 选择信号为标准 3-bit 二进制码 (sel[2:0])
//   - 综合工具自动构建 3 级级联平衡 MUX 树
//   - 输出级挂载标准 D 触发器构成单级流水线时序边界
// ==============================================================================

module onehot_mux #(
    parameter CHANNELS = 8,
    parameter WIDTH    = 8,
    parameter SEL_W    = 3
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire [SEL_W-1:0]         sel,
    input  wire [CHANNELS*WIDTH-1:0] data_in,
    output reg  [WIDTH-1:0]         data_out
);
    wire [WIDTH-1:0] ch_data [0:CHANNELS-1];
    genvar i;
    generate
        for (i = 0; i < CHANNELS; i = i + 1) begin : gen_ch
            assign ch_data[i] = data_in[i*WIDTH +: WIDTH];
        end
    endgenerate

    // 纯二进制多路选择 (典型 MUX 树)
    wire [WIDTH-1:0] mux_wire = ch_data[sel];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out <= {WIDTH{1'b0}};
        end else begin
            data_out <= mux_wire;
        end
    end
endmodule

