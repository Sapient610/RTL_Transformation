`timescale 1ns / 1ps

module tb_top;
    localparam WIDTH = 64;

    reg              clk;
    reg              rst_n;
    reg  [WIDTH-1:0] data_in;
    wire [WIDTH-1:0] data_out;

    bus_top u_dut (
        .clk      (clk),
        .rst_n    (rst_n),
        .data_in  (data_in),
        .data_out (data_out)
    );

    initial clk = 0;
    always #5.0 clk = ~clk;

    reg [1023:0] vcd_file;
    integer toggle_rate_pct = 35;
    integer cycle_count;
    integer b;

    initial begin
        if (!$value$plusargs("VCD_FILE=%s", vcd_file)) begin
            vcd_file = "activity.vcd";
        end
        if (!$value$plusargs("TOGGLE_RATE=%d", toggle_rate_pct)) begin
            toggle_rate_pct = 35;
        end

        $dumpfile(vcd_file);
        $dumpvars(0, tb_top.u_dut);

        $display("[TB] Bus-Invert Dump: %0s | ToggleRate: %0d%% | Width: %0d",
                 vcd_file, toggle_rate_pct, WIDTH);

        rst_n = 0;
        data_in = {WIDTH{1'b0}};

        #25;
        rst_n = 1;
        #10;

        for (cycle_count = 0; cycle_count < 400; cycle_count = cycle_count + 1) begin
            @(posedge clk);
            #1;

            for (b = 0; b < WIDTH; b = b + 1) begin
                if (($urandom % 100) < toggle_rate_pct) begin
                    data_in[b] <= ~data_in[b];
                end
            end
        end

        #50;
        $display("[TB] Simulation completed successfully for %0d-bit bus.", WIDTH);
        $finish;
    end
endmodule

