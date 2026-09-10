`timescale 1ns/1ps

module tb_top;

    localparam WIDTH = 32;

    reg             clk;
    reg             rst_n;
    reg             valid_in;
    reg  [2:0]      opcode;
    reg  [WIDTH-1:0] op_a;
    reg  [WIDTH-1:0] op_b;
    wire            valid_out;
    wire [WIDTH-1:0] res_out;

    // 10ns 周期时钟 (100MHz)
    always #5 clk = ~clk;

    // 契约要求：DUT 例化名固定为 u_dut
    alu_top u_dut (
        .clk       (clk),
        .rst_n     (rst_n),
        .valid_in  (valid_in),
        .opcode    (opcode),
        .op_a      (op_a),
        .op_b      (op_b),
        .valid_out (valid_out),
        .res_out   (res_out)
    );

    reg [1023:0] vcd_file;
    integer valid_duty;
    integer data_activity;

    initial begin
        if (!$value$plusargs("VCD_FILE=%s", vcd_file)) begin
            `ifdef DEFAULT_VCD_FILE
                vcd_file = `DEFAULT_VCD_FILE;
            `else
                vcd_file = "activity.vcd";
            `endif
        end
        if (!$value$plusargs("VALID_DUTY=%d", valid_duty)) begin
            if (!$value$plusargs("EN_DUTY=%d", valid_duty)) begin
                valid_duty = 20;
            end
        end
        if (!$value$plusargs("DATA_ACTIVITY=%d", data_activity)) begin
            data_activity = 50;
        end
        $dumpfile(vcd_file);
        $dumpvars(0, tb_top.u_dut);
        $display("[TB] Dump: %0s | ValidDuty: %0d%% | DataActivity: %0d%%", vcd_file, valid_duty, data_activity);
    end

    initial begin
        clk      = 0;
        rst_n    = 0;
        valid_in = 0;
        opcode   = 0;
        op_a     = 0;
        op_b     = 0;

        #20;
        rst_n    = 1;

        repeat (400) begin
            @(posedge clk);
            valid_in <= ($urandom % 100 < valid_duty);
            opcode   <= $urandom % 8;

            if ($urandom % 100 < data_activity) begin
                op_a <= { $urandom, $urandom, $urandom, $urandom };
                op_b <= { $urandom, $urandom, $urandom, $urandom };
            end
        end

        #50;
        $display("[TB] Simulation completed successfully.");
        $finish;
    end

endmodule
