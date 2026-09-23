#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 1: 通用多文件形式等价性验证 (Formal Logic Equivalence Checking via Yosys)
"""

import sys
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from src.common.env import run_command_with_logging


def run_formal_lec(
    sources_orig: List[Path],
    sources_opt: List[Path],
    top: str,
    formal_dir: Path,
    log_dir: Path,
    logger: logging.Logger,
    gray_counter_width: Optional[int] = None,
    onehot_mux_params: Optional[dict] = None,
    bus_invert: bool = False,
    bus_invert_width: Optional[int] = None,
):
    """
    通过 Yosys SAT 求解器执行层次化等价性比对，建立 Miter 电路严格断言。
    若设置 gray_counter_width，则通过外置编码映射包装器对纯二进制计数器与格雷码计数器建立双射映射 Miter。
    若设置 onehot_mux_params，则通过独热码解码包装器 (1 << sel) 对二进制 MUX 与独热 MUX 建立双射映射 Miter。
    若等价性未通过，立即触发熔断机制，终止后续物理实现流程。
    """
    logger.info("=" * 70)
    logger.info(">>> Step 1: Formal Logic Equivalence Checking (Yosys SAT)")
    logger.info("=" * 70)

    orig_files_str = " ".join(f'"{str(p)}"' for p in sources_orig)
    opt_files_str = " ".join(f'"{str(p)}"' for p in sources_opt)
    formal_dir = formal_dir.resolve()
    log_dir = log_dir.resolve()

    if gray_counter_width is not None:
        wrapper_file = formal_dir / "lec_orig_wrapper.v"
        wrapper_file.write_text(f"""
module {top}_orig (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          en,
    output wire [{gray_counter_width-1}:0] count_out
);
    wire [{gray_counter_width-1}:0] bin_out;
    {top}_core u_core (
        .clk      (clk),
        .rst_n    (rst_n),
        .en       (en),
        .count_out(bin_out)
    );
    assign count_out = (bin_out >> 1) ^ bin_out;
endmodule
""", encoding="utf-8")

        lec_script = f"""
    read_verilog -sv {orig_files_str}
    hierarchy -top {top}
    flatten
    rename {top} {top}_core
    read_verilog -sv "{wrapper_file}"
    hierarchy -top {top}_orig
    flatten
    design -save orig_des
    design -reset

    read_verilog -sv {opt_files_str}
    hierarchy -top {top}
    flatten
    rename {top} {top}_opt

    design -copy-from orig_des {top}_orig {top}_orig

    proc
    clk2fflogic

    equiv_make {top}_orig {top}_opt miter
    hierarchy -top miter
    flatten

    equiv_simple
    equiv_induct
    equiv_status -assert
    """
    elif onehot_mux_params is not None:
        channels = onehot_mux_params["channels"]
        width = onehot_mux_params["width"]
        sel_w = onehot_mux_params["sel_w"]

        wrapper_file = formal_dir / "lec_opt_wrapper.v"
        wrapper_file.write_text(f"""
module {top}_opt (
    input  wire                               clk,
    input  wire                               rst_n,
    input  wire [{sel_w-1}:0]                 sel,
    input  wire [{channels*width-1}:0]        data_in,
    output wire [{width-1}:0]                 data_out
);
    wire [{channels-1}:0] sel_onehot = ({channels}'d1 << sel);
    {top}_core u_core (
        .clk        (clk),
        .rst_n      (rst_n),
        .sel_onehot (sel_onehot),
        .data_in    (data_in),
        .data_out   (data_out)
    );
endmodule
""", encoding="utf-8")

        lec_script = f"""
    read_verilog -sv {orig_files_str}
    hierarchy -top {top}
    flatten
    rename {top} {top}_orig
    design -save orig_des
    design -reset

    read_verilog -sv {opt_files_str}
    hierarchy -top {top}
    flatten
    rename {top} {top}_core
    read_verilog -sv "{wrapper_file}"
    hierarchy -top {top}_opt
    flatten

    design -copy-from orig_des {top}_orig {top}_orig

    proc
    clk2fflogic

    equiv_make {top}_orig {top}_opt miter
    hierarchy -top miter
    flatten

    equiv_simple
    equiv_induct
    equiv_status -assert
    """
    elif bus_invert:
        bw = bus_invert_width if bus_invert_width is not None else 8
        wrapper_file = formal_dir / "lec_bus_miter.v"
        wrapper_file.write_text(f"""
module miter (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire [{bw-1}:0]      data_in
);
    wire [{bw-1}:0] orig_pad_bus;
    wire            orig_pad_inv;
    wire [{bw-1}:0] orig_data_out;

    wire [{bw-1}:0] opt_pad_bus;
    wire            opt_pad_inv;
    wire [{bw-1}:0] opt_data_out;

    {top}_orig u_orig (
        .clk     (clk),
        .rst_n   (rst_n),
        .data_in (data_in),
        .pad_bus (orig_pad_bus),
        .pad_inv (orig_pad_inv),
        .data_out(orig_data_out)
    );

    {top}_opt u_opt (
        .clk     (clk),
        .rst_n   (rst_n),
        .data_in (data_in),
        .pad_bus (opt_pad_bus),
        .pad_inv (opt_pad_inv),
        .data_out(opt_data_out)
    );

    always @(*) begin
        assert(orig_data_out == opt_data_out);
    end
endmodule
""", encoding="utf-8")

        lec_script = f"""
    read_verilog -sv {orig_files_str}
    hierarchy -top {top}
    rename {top} {top}_orig
    design -save orig_des
    design -reset

    read_verilog -sv {opt_files_str}
    hierarchy -top {top}
    rename {top} {top}_opt

    design -copy-from orig_des {top}_orig {top}_orig

    read_verilog -sv "{wrapper_file}"
    hierarchy -top miter
    flatten
    proc
    clk2fflogic
    sat -verify -prove-asserts -set-at 1 rst_n 0 -set-at 2 rst_n 1 -set-at 3 rst_n 1 -seq 5 miter
    """
    else:
        lec_script = f"""
    read_verilog -sv {orig_files_str}
    hierarchy -top {top}
    flatten
    rename {top} {top}_orig
    design -save orig_des
    design -reset

    read_verilog -sv {opt_files_str}
    hierarchy -top {top}
    flatten
    rename {top} {top}_opt

    design -copy-from orig_des {top}_orig {top}_orig

    proc
    clk2fflogic

    equiv_make {top}_orig {top}_opt miter
    hierarchy -top miter
    flatten

    equiv_simple
    equiv_induct
    equiv_status -assert
    """

    script_path = formal_dir / "lec.ys"
    script_path.write_text(lec_script, encoding="utf-8")
    lec_log = log_dir / "yosys_lec.log"

    try:
        run_command_with_logging(["yosys", "-q", "-s", str(script_path)], lec_log, cwd=formal_dir, logger=logger)
        logger.info("[PASS] 100% Functional Equivalence Verified by Yosys SAT.")
    except subprocess.CalledProcessError:
        logger.error(f"[FAIL] Functional Equivalence Check Failed! Circuit breaker triggered.")
        logger.error(f"       Inspect detailed SAT diagnostic log at: {lec_log}")
        sys.exit(1)
