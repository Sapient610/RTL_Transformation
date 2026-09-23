`timescale 1ns / 1ps

module tb_top;
    localparam CHANNELS = 16;
    localparam WIDTH    = 8;
    localparam SEL_W    = 4;

    reg                          clk;
    reg                          rst_n;
    reg  [SEL_W-1:0]             sel;
    reg  [CHANNELS-1:0]          sel_onehot;
    reg  [CHANNELS*WIDTH-1:0]    data_in;
    wire [WIDTH-1:0]             data_out;

`ifdef MUX_OPT
    // 实例化优化版本 (原生独热码)
    onehot_mux u_dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .sel_onehot (sel_onehot),
        .data_in    (data_in),
        .data_out   (data_out)
    );
`else
    // 实例化原始基准 (纯二进制码)
    onehot_mux u_dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .sel        (sel),
        .data_in    (data_in),
        .data_out   (data_out)
    );
`endif

    // 100MHz 主频时钟 (周期 10.0ns)
    initial clk = 0;
    always #5.0 clk = ~clk;

    reg [1023:0] vcd_file;
    integer switch_duty_pct = 20;
    integer cycle_count;
    integer curr_channel;
    integer ch_idx;

    initial begin
        if (!$value$plusargs("VCD_FILE=%s", vcd_file)) begin
            vcd_file = "activity.vcd";
        end
        if (!$value$plusargs("SWITCH_DUTY=%d", switch_duty_pct)) begin
            switch_duty_pct = 20;
        end

        $dumpfile(vcd_file);
        $dumpvars(0, tb_top.u_dut);

        $display("[TB] OneHot vs Binary MUX Dump: %0s | SwitchDuty: %0d%% | Channels: %0d",
                 vcd_file, switch_duty_pct, CHANNELS);

        rst_n = 0;
        sel = 0;
        sel_onehot = {{(CHANNELS-1){1'b0}}, 1'b1};
        data_in = 0;
        curr_channel = 0;

        #25;
        rst_n = 1;
        #10;

        for (cycle_count = 0; cycle_count < 400; cycle_count = cycle_count + 1) begin
            @(posedge clk);
            #1;

            // 1. 根据通道切换概率决定本周期是否更换选择通道
            if (($urandom % 100) < switch_duty_pct) begin
                curr_channel = $urandom % CHANNELS;
            end

            sel = curr_channel[SEL_W-1:0];
            sel_onehot = ({{(CHANNELS-1){1'b0}}, 1'b1} << curr_channel);

            // 2. 为所有输入通道生成动态随机数据 (模拟总线高频翻转与杂散噪声)
            for (ch_idx = 0; ch_idx < CHANNELS; ch_idx = ch_idx + 1) begin
                data_in[ch_idx*WIDTH +: WIDTH] <= $urandom;
            end
        end

        #50;
        $display("[TB] Simulation completed successfully for %0d-to-1 MUX.", CHANNELS);
        $finish;
    end
endmodule

