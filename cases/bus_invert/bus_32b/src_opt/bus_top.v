// ==============================================================================
// 优化设计：基于汉明距离统计的总线反转编码架构 (Bus-Invert Architecture, 32-bit)
// cases/bus_invert/bus_32b/src_opt/bus_top.v
//
// 核心微架构：
//   1. 编码器 (TX Encoder)：监测待发送数据与上一周期已发送总线电平的汉明翻转数；
//      若 H > WIDTH/2，则将总线数据按位取反，并置 inv=1；否则维持原码，置 inv=0；
//   2. 传输总线：实际总线由数据线与 1 根 inv 控制线构成，翻转数严格 <= WIDTH/2；
//   3. 解码器 (RX Decoder)：接收端通过并联异或门 (bus ^ {WIDTH{inv}}) 无损还原原始数据。
// ==============================================================================

module bus_top #(
    parameter WIDTH = 32
) (
    input  wire             clk,
    input  wire             rst_n,
    input  wire [WIDTH-1:0] data_in,
    output wire [WIDTH-1:0] pad_bus,
    output wire             pad_inv,
    output reg  [WIDTH-1:0] data_out
);
    // 第一级发送寄存器 (TX Stage)
    reg [WIDTH-1:0] tx_bus;
    reg             tx_inv;

    // 汉明距离统计函数 (PopCount)
    function automatic integer popcount(input [WIDTH-1:0] vec);
        integer idx;
        begin
            popcount = 0;
            for (idx = 0; idx < WIDTH; idx = idx + 1) begin
                popcount = popcount + vec[idx];
            end
        end
    endfunction

    // 比较当前待发送数据与已发送总线电平的差异
    wire [WIDTH-1:0] diff = data_in ^ tx_bus;
    wire [$clog2(WIDTH+1)-1:0] h_dist = popcount(diff);

    // 多数判决：翻转位数超过半数时触发反转
    wire do_invert = (h_dist > (WIDTH / 2));

    wire [WIDTH-1:0] next_tx_bus = do_invert ? ~data_in : data_in;
    wire             next_tx_inv = do_invert;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_bus <= {WIDTH{1'b0}};
            tx_inv <= 1'b0;
        end else begin
            tx_bus <= next_tx_bus;
            tx_inv <= next_tx_inv;
        end
    end

    // Pad 物理总线引出 (板级/封装外引脚，由高容抗负载驱动)
    assign pad_bus = tx_bus;
    assign pad_inv = tx_inv;

    // 接收端无损解码 (RX Decoder)
    wire [WIDTH-1:0] rx_decoded = tx_bus ^ {WIDTH{tx_inv}};

    // 第二级接收寄存器 (RX Stage)
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out <= {WIDTH{1'b0}};
        end else begin
            data_out <= rx_decoded;
        end
    end
endmodule
