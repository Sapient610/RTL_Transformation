module gray_counter #(
    parameter WIDTH = 4
)(
    input  wire             clk,
    input  wire             rst_n,
    input  wire             en,
    output wire [WIDTH-1:0] gray_out
);

    reg [WIDTH-1:0] bin_cnt;
    reg [WIDTH-1:0] gray_cnt;

    wire [WIDTH-1:0] bin_next = en ? (bin_cnt + 1'b1) : bin_cnt;
    wire [WIDTH-1:0] gray_next = (bin_next >> 1) ^ bin_next;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bin_cnt  <= {WIDTH{1'b0}};
            gray_cnt <= {WIDTH{1'b0}};
        end else begin
            bin_cnt  <= bin_next;
            gray_cnt <= gray_next;
        end
    end

    assign gray_out = gray_cnt;

endmodule

