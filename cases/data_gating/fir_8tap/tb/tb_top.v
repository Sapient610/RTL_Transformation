`timescale 1ns / 1ps

module tb_top;
    localparam NUM_TAPS = 8;

    reg                  clk;
    reg                  rst_n;
    reg                  data_valid;
    reg  signed [7:0]    sample_in;
    wire                 valid_out;
    wire signed [15:0]   data_out;

    fir_top u_dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .data_valid (data_valid),
        .sample_in  (sample_in),
        .valid_out  (valid_out),
        .data_out   (data_out)
    );

    // 100MHz 主频时钟 (周期 10ns)
    initial clk = 0;
    always #5.0 clk = ~clk;

    reg [1023:0] vcd_file;
    integer valid_duty_pct = 20;
    integer data_activity_pct = 30;
    integer cycle_count;

    initial begin
        if (!$value$plusargs("VCD_FILE=%s", vcd_file)) begin
            vcd_file = "activity.vcd";
        end
        if (!$value$plusargs("VALID_DUTY=%d", valid_duty_pct)) begin
            valid_duty_pct = 20;
        end
        if (!$value$plusargs("DATA_ACTIVITY=%d", data_activity_pct)) begin
            data_activity_pct = 30;
        end

        $dumpfile(vcd_file);
        $dumpvars(0, tb_top);

        $display("[TB] FIR Dump: %0s | ValidDuty: %0d%% | DataActivity: %0d%% | Taps: %0d",
                 vcd_file, valid_duty_pct, data_activity_pct, NUM_TAPS);

        rst_n = 0;
        data_valid = 0;
        sample_in = 8'sd0;

        #25;
        rst_n = 1;
        #10;

        for (cycle_count = 0; cycle_count < 400; cycle_count = cycle_count + 1) begin
            @(posedge clk);
            #1;
            if (($urandom % 100) < valid_duty_pct) begin
                data_valid <= 1'b1;
                sample_in  <= $urandom % 256;
            end else begin
                data_valid <= 1'b0;
                if (($urandom % 100) < data_activity_pct) begin
                    sample_in <= $urandom % 256; // 外部总线杂散翻转
                end
            end
        end

        #50;
        $display("[TB] Simulation completed successfully for %0d-tap FIR filter.", NUM_TAPS);
        $finish;
    end
endmodule
