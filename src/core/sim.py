#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 3: 测试平台门级仿真与翻转活跃度转储 (Simulation & VCD Generation)
"""

import logging
from pathlib import Path

from src.common.env import run_command_with_logging


def generate_vcd_activity(
    run_tag: str,
    netlist: Path,
    tb_path: Path,
    prims_path: Path,
    verilog_lib_path: Path,
    sim_dir: Path,
    log_dir: Path,
    logger: logging.Logger,
) -> Path:
    """
    调用 Icarus Verilog 编译门级纯逻辑网表与 PDK 原语库，
    驱动真实业务激励运行门级后仿，并转储带层级作用域的活动度波形 VCD。
    """
    logger.info("=" * 70)
    logger.info(f">>> Step 3: Simulation & Activity Profile Extraction [{run_tag}]")
    logger.info("=" * 70)

    vvp_path = sim_dir / f"sim_{run_tag}.vvp"
    vcd_path = sim_dir / f"{run_tag}_activity.vcd"

    compile_cmd = [
        "iverilog",
        "-g2012",
        "-DFUNCTIONAL",
        "-o", str(vvp_path),
        str(prims_path),
        str(verilog_lib_path),
        str(netlist),
        str(tb_path),
    ]

    compile_log = log_dir / f"sim_{run_tag}_compile.log"
    run_command_with_logging(compile_cmd, compile_log, cwd=sim_dir, logger=logger)

    run_cmd = ["vvp", str(vvp_path), f"+VCD_FILE={vcd_path}"]
    run_log = log_dir / f"sim_{run_tag}_exec.log"
    run_command_with_logging(run_cmd, run_log, cwd=sim_dir, logger=logger)

    if not vcd_path.exists():
        for fallback_vcd_name in ["activity.vcd", f"{run_tag}.vcd"]:
            cand = sim_dir / fallback_vcd_name
            if cand.exists():
                cand.rename(vcd_path)
                break

    if not vcd_path.exists() or vcd_path.stat().st_size == 0:
        raise RuntimeError(f"Simulation failed to generate non-empty VCD file at: {vcd_path}")

    logger.info(f"[*] Generated Activity VCD: {vcd_path} ({vcd_path.stat().st_size} bytes)")
    return vcd_path

