`timescale 1ns/1ps

module tb_top;

    reg         clk;
    reg         rst_n;
    reg         en;
    reg  [63:0] data_in;
    wire [63:0] data_out;

    // 10ns 周期时钟 (100MHz)
    always #5 clk = ~clk;

    // 契约要求：被测设计例化名称固定为 u_dut
    reg_bank u_dut (
        .clk      (clk),
        .rst_n    (rst_n),
        .en       (en),
        .data_in  (data_in),
        .data_out (data_out)
    );

    // 契约要求：转储 tb_top.u_dut 层次下的所有信号
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

    integer en_duty;
    initial begin
        if (!$value$plusargs("EN_DUTY=%d", en_duty)) begin
            en_duty = 10; // 默认 10% 稀疏使能
        end
        $display("[TB] Dynamic enable duty configured to: %0d%%", en_duty);
    end

    // 产生真实业务激励以触发功耗翻转
    initial begin
        clk     = 0;
        rst_n   = 0;
        en      = 0;
        data_in = 0;

        #20;
        rst_n   = 1;

        repeat (200) begin
            @(posedge clk);
            en      <= (($urandom % 100) < en_duty);
            data_in <= $urandom;
        end

        #50;
        $display("[TB] Simulation completed successfully.");
        $finish;
    end

endmodule
