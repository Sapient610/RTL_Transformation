module reg_bank (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        en,
    input  wire [31:0] data_in,
    output reg  [31:0] data_out
);
    wire gated_clk;

    // 采用无毛刺 (Glitch-Free) 锁存器门控结构（Sky130 对应 sky130_fd_sc_hd__dlclkp_1）
    // 此处写行为级模型，便于验证与综合映射
    reg en_latched;
    always @(clk or en) begin
        if (!clk)
            en_latched <= en;
    end
    assign gated_clk = clk & en_latched;

    // 寄存器直接受控于门控时钟
    always @(posedge gated_clk or negedge rst_n) begin
        if (!rst_n)
            data_out <= 32'd0;
        else
            data_out <= data_in;
    end
endmodule

