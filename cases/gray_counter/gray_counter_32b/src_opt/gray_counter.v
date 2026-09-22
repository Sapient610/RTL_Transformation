module gray_counter #(
    parameter WIDTH = 32
)(
    input  wire             clk,
    input  wire             rst_n,
    input  wire             en,
    output wire [WIDTH-1:0] count_out
);

    reg [WIDTH-1:0] gray_cnt;
    reg [WIDTH-1:0] bin_curr;
    integer i;

    // 组合逻辑：由当前的格雷码状态恢复瞬时二进制值
    always @(*) begin
        for (i = 0; i < WIDTH; i = i + 1) begin
            bin_curr[i] = ^(gray_cnt >> i);
        end
    end

    wire [WIDTH-1:0] bin_next = en ? (bin_curr + 1'b1) : bin_curr;
    wire [WIDTH-1:0] gray_next = (bin_next >> 1) ^ bin_next;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            gray_cnt <= {WIDTH{1'b0}};
        end else begin
            gray_cnt <= gray_next;
        end
    end

    assign count_out = gray_cnt;

endmodule
