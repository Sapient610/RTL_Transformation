`timescale 1ns / 1ps

module tb_top;
    localparam WIDTH = 4;

    reg                  clk;
    reg                  rst_n;
    reg                  gate_en;
    reg  [2:0]           opcode;
    reg  [WIDTH-1:0]     op_a;
    reg  [WIDTH-1:0]     op_b;
    wire                 valid_out;
    wire [WIDTH-1:0]     res_out;

    small_dp_top u_dut (
        .clk       (clk),
        .rst_n     (rst_n),
        .gate_en   (gate_en),
        .opcode    (opcode),
        .op_a      (op_a),
        .op_b      (op_b),
        .valid_out (valid_out),
        .res_out   (res_out)
    );

    // 100MHz 时钟 (周期 10ns)
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

        $display("[TB] Dump: %0s | ValidDuty: %0d%% | DataActivity: %0d%% | Width: %0d",
                 vcd_file, valid_duty_pct, data_activity_pct, WIDTH);

        rst_n = 0;
        gate_en = 0;
        opcode = 0;
        op_a = 0;
        op_b = 0;

        #25;
        rst_n = 1;
        #10;

        for (cycle_count = 0; cycle_count < 400; cycle_count = cycle_count + 1) begin
            @(posedge clk);
            #1;
            if (($urandom % 100) < valid_duty_pct) begin
                gate_en <= 1'b1;
                opcode  <= $urandom % 8;
                op_a    <= $urandom;
                op_b    <= $urandom;
            end else begin
                gate_en <= 1'b0;
                opcode  <= opcode;
                if (($urandom % 100) < data_activity_pct) begin
                    op_a <= $urandom;
                    op_b <= $urandom;
                end
            end
        end

        #50;
        $display("[TB] Simulation completed successfully for %0d-bit small datapath.", WIDTH);
        $finish;
    end
endmodule
