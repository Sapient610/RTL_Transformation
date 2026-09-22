module gray_counter #(
    parameter WIDTH = 32
)(
    input  wire             clk,
    input  wire             rst_n,
    input  wire             en,
    output wire [WIDTH-1:0] count_out
);

    reg [WIDTH-1:0] bin_cnt;

    wire [WIDTH-1:0] bin_next = en ? (bin_cnt + 1'b1) : bin_cnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bin_cnt <= {WIDTH{1'b0}};
        end else begin
            bin_cnt <= bin_next;
        end
    end

    assign count_out = bin_cnt;

endmodule
