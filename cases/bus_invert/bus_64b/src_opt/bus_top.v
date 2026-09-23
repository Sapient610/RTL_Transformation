// ==============================================================================
// 优化设计：基于汉明距离统计的总线反转编码架构 (Bus-Invert Architecture, 64-bit)
// cases/bus_invert/bus_64b/src_opt/bus_top.v
// ==============================================================================

module bus_top #(
    parameter WIDTH = 64
) (
    input  wire             clk,
    input  wire             rst_n,
    input  wire [WIDTH-1:0] data_in,
    output reg  [WIDTH-1:0] data_out
);
    reg [WIDTH-1:0] tx_bus;
    reg             tx_inv;

    function automatic integer popcount(input [WIDTH-1:0] vec);
        integer idx;
        begin
            popcount = 0;
            for (idx = 0; idx < WIDTH; idx = idx + 1) begin
                popcount = popcount + vec[idx];
            end
        end
    endfunction

    wire [WIDTH-1:0] diff = data_in ^ tx_bus;
    wire [$clog2(WIDTH+1)-1:0] h_dist = popcount(diff);

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

    wire [WIDTH-1:0] rx_decoded = tx_bus ^ {WIDTH{tx_inv}};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out <= {WIDTH{1'b0}};
        end else begin
            data_out <= rx_decoded;
        end
    end
endmodule

