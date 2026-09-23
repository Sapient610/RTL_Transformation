// ==============================================================================
// 原始基准设计：无总线反转编码的标准双级流水线总线传输架构 (8-bit)
// cases/bus_invert/bus_8b/src_orig/bus_top.v
// ==============================================================================

module bus_top #(
    parameter WIDTH = 8
) (
    input  wire             clk,
    input  wire             rst_n,
    input  wire [WIDTH-1:0] data_in,
    output reg  [WIDTH-1:0] data_out
);
    // 第一级发送寄存器 (TX Stage)
    reg [WIDTH-1:0] tx_bus;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_bus <= {WIDTH{1'b0}};
        end else begin
            tx_bus <= data_in;
        end
    end

    // 第二级接收寄存器 (RX Stage)
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out <= {WIDTH{1'b0}};
        end else begin
            data_out <= tx_bus;
        end
    end
endmodule

