`timescale 1ns/1ps

module tb_top;

    reg         clk;
    reg         rst_n;
    reg         valid_in;
    reg  [2:0]  opcode;
    reg  [15:0] op_a;
    reg  [15:0] op_b;
    wire        valid_out;
    wire [15:0] res_out;

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

    // 契约要求：转储 tb_top.u_dut 层次下的信号
    reg [1023:0] vcd_file;
    initial begin
        if (!$value$plusargs("VCD_FILE=%s", vcd_file)) begin
            `ifdef DEFAULT_VCD_FILE
                vcd_file = `DEFAULT_VCD_FILE;
            `else
                vcd_file = "activity.vcd";
            `endif
        end
        $dumpfile(vcd_file);
        $dumpvars(0, tb_top.u_dut);
        $display("[TB] Activity dump initialized to: %0s", vcd_file);
    end

    // 激励模拟真实总线：总线上持续有杂散翻转数据，但仅在 20% 周期内有效
    initial begin
        clk      = 0;
        rst_n    = 0;
        valid_in = 0;
        opcode   = 0;
        op_a     = 0;
        op_b     = 0;

        #20;
        rst_n    = 1;

        repeat (300) begin
            @(posedge clk);
            valid_in <= ($urandom % 5 == 0); // 20% 占空比有效
            opcode   <= $urandom % 8;
            op_a     <= $urandom;
            op_b     <= $urandom;
        end

        #50;
        $display("[TB] Simulation completed successfully.");
        $finish;
    end

endmodule

