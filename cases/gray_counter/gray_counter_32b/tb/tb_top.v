`timescale 1ns / 1ps

module tb_top;
    localparam WIDTH = 32;

    reg              clk;
    reg              rst_n;
    reg              en;
    wire [WIDTH-1:0] gray_out;

    gray_counter u_dut (
        .clk     (clk),
        .rst_n   (rst_n),
        .en      (en),
        .gray_out(gray_out)
    );

    // 100MHz 主频时钟 (周期 10ns)
    initial clk = 0;
    always #5.0 clk = ~clk;

    reg [1023:0] vcd_file;
    integer en_duty_pct = 20;
    integer cycle_count;

    initial begin
        if (!$value$plusargs("VCD_FILE=%s", vcd_file)) begin
            vcd_file = "activity.vcd";
        end
        if (!$value$plusargs("EN_DUTY=%d", en_duty_pct)) begin
            en_duty_pct = 20;
        end

        $dumpfile(vcd_file);
        $dumpvars(0, tb_top.u_dut);

        $display("[TB] Gray Counter Dump: %0s | EnDuty: %0d%% | Width: %0d",
                 vcd_file, en_duty_pct, WIDTH);

        rst_n = 0;
        en = 0;

        #25;
        rst_n = 1;
        #10;

        for (cycle_count = 0; cycle_count < 400; cycle_count = cycle_count + 1) begin
            @(posedge clk);
            #1;
            if (($urandom % 100) < en_duty_pct) begin
                en <= 1'b1;
            end else begin
                en <= 1'b0;
            end
        end

        #50;
        $display("[TB] Simulation completed successfully for %0d-bit Gray counter.", WIDTH);
        $finish;
    end
endmodule

