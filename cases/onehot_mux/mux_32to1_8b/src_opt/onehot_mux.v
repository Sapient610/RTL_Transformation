// ==============================================================================
// 原生独热编码并行与或多路选择器 (Native One-Hot AND-OR Multiplexer) - 32-to-1 / 8-bit
// cases/onehot_mux/mux_32to1_8b/src_opt/onehot_mux.v
//
// 优化架构：
//   - 选择信号为 32-bit 原生独热码 (sel_onehot[31:0]，单有效高电平)
//   - 数据位通过并行与门阵列实现自然输入门控阻断：未选中通道数据直接被 0 屏蔽
//   - 单级宽或门树直接归约输出，打破二进制 MUX 树的级联延时瓶颈
//   - 输出级挂载标准 D 触发器构成单级流水线时序边界
// ==============================================================================

module onehot_mux #(
    parameter CHANNELS = 32,
    parameter WIDTH    = 8
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire [CHANNELS-1:0]      sel_onehot,
    input  wire [CHANNELS*WIDTH-1:0] data_in,
    output reg  [WIDTH-1:0]         data_out
);
    wire [WIDTH-1:0] ch_data [0:CHANNELS-1];
    genvar i, b;
    generate
        for (i = 0; i < CHANNELS; i = i + 1) begin : gen_ch
            assign ch_data[i] = data_in[i*WIDTH +: WIDTH];
        end
    endgenerate

    // 并行与或阵列 (AND-OR Multiplexer)
    wire [WIDTH-1:0] onehot_wire;
    generate
        for (b = 0; b < WIDTH; b = b + 1) begin : gen_bit
            wire [CHANNELS-1:0] bit_gated;
            for (i = 0; i < CHANNELS; i = i + 1) begin : gen_and
                assign bit_gated[i] = ch_data[i][b] & sel_onehot[i];
            end
            assign onehot_wire[b] = |bit_gated;
        end
    endgenerate

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out <= {WIDTH{1'b0}};
        end else begin
            data_out <= onehot_wire;
        end
    end
endmodule

