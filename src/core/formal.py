#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 1: 通用多文件形式等价性验证 (Formal Logic Equivalence Checking via Yosys)
"""

import sys
import logging
import subprocess
from pathlib import Path
from typing import List

from src.common.env import run_command_with_logging


def run_formal_lec(
    sources_orig: List[Path],
    sources_opt: List[Path],
    top: str,
    formal_dir: Path,
    log_dir: Path,
    logger: logging.Logger,
):
    """
    通过 Yosys SAT 求解器执行层次化等价性比对，建立 Miter 电路严格断言。
    若等价性未通过，立即触发熔断机制，终止后续物理实现流程。
    """
    logger.info("=" * 70)
    logger.info(">>> Step 1: Formal Logic Equivalence Checking (Yosys SAT)")
    logger.info("=" * 70)

    orig_files_str = " ".join(f'"{str(p)}"' for p in sources_orig)
    opt_files_str = " ".join(f'"{str(p)}"' for p in sources_opt)

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
    formal_dir = formal_dir.resolve()
    log_dir = log_dir.resolve()
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

