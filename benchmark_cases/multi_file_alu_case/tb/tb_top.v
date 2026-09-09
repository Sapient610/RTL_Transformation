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

    // 契约：DUT 例化名为 u_dut
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

    // 契约：转储 tb_top.u_dut 层次下的波形
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

    // 激励发生：模拟高密度数据流伴随稀疏有效信号场景
    initial begin
        clk      = 0;
        rst_n    = 0;
        valid_in = 0;
        opcode   = 0;
        op_a     = 0;
        op_b     = 0;

        #20;
        rst_n    = 1;

        repeat (200) begin
            @(posedge clk);
            valid_in <= ($urandom % 5 == 0); // 20% 有效周期，其余周期总线仍有杂散翻转
            opcode   <= $urandom % 8;
            op_a     <= $urandom;
            op_b     <= $urandom;
        end

        #50;
        $display("[TB] Simulation completed successfully.");
        $finish;
    end

endmodule

