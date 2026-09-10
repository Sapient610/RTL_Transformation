#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
通用多文件 RTL 变换自动化物理评估基座 (Evaluation Platform CLI Entry Point)
evaluate_case.py

本入口脚本负责解析命令行参数并调度 src/ 模块执行全流程闭环：
  Step 1: Yosys 层次化形式等价性验证 (Formal LEC) - 熔断保护
  Step 2: LibreLane 80-Stage 全物理实现 (PnR) -> Sky130 标准单元
  Step 3: Icarus Verilog 门级网表后仿与真实业务波形提取 (Simulation & VCD)
  Step 4: OpenSTA 寄生参数反标时序、功耗与引脚翻转活动度签核 (Signoff STA)
  Step 5: 全维度 PPA 报表生成与多维 Trade-off 关系量化分析 (Report)
===============================================================================
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from src.common.env import ensure_devshell_environment
from src.common.logger import setup_logging, cleanup_legacy_root_files
from src.common.pdk import locate_pdk_files
from src.common.case_loader import load_and_validate_case
from src.core.formal import run_formal_lec
from src.core.pnr import run_pnr_flow
from src.core.sim import generate_vcd_activity
from src.core.signoff import run_signoff_evaluation
from src.core.report import generate_ppa_summary_report


def evaluate_case(
    case_dir: Path,
    workspace_arg: Optional[str] = None,
    pdk_root_arg: Optional[str] = None,
    pdk_name: str = "sky130A",
    scl_name: str = "sky130_fd_sc_hd",
    devshell_arg: Optional[str] = None,
):
    """主评估流程执行器"""
    ensure_devshell_environment(devshell_arg)

    case_dir = case_dir.resolve()
    if not case_dir.is_dir():
        sys.stderr.write(f"[ERROR] Case directory not found: {case_dir}\n")
        sys.exit(1)

    case_name = case_dir.name
    if workspace_arg:
        workspace = Path(workspace_arg).resolve()
    else:
        cwd = Path.cwd().resolve()
        try:
            rel = case_dir.relative_to(cwd / "cases")
            workspace = cwd / "eval_workspace" / rel
        except ValueError:
            workspace = cwd / "eval_workspace" / case_name
    workspace.mkdir(parents=True, exist_ok=True)

    sim_dir = workspace / "sim"
    reports_dir = workspace / "reports"
    formal_dir = workspace / "formal"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = workspace / "logs" / timestamp

    sim_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    formal_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(log_dir)
    cleanup_legacy_root_files(workspace, logger)

    logger.info("Evaluation Platform initialized with decoupled directory structure.")
    logger.info(f"Target Case:    {case_dir}")
    logger.info(f"Workspace:      {workspace}")
    logger.info(f"  Simulation:   {sim_dir}")
    logger.info(f"  Reports:      {reports_dir}")
    logger.info(f"  Formal (LEC): {formal_dir}")
    logger.info(f"  Session Logs: {log_dir}")

    # 2. 探测并校验 PDK 文件
    pdk_root_base = Path(pdk_root_arg).expanduser().resolve() if pdk_root_arg else Path(os.environ.get("PDK_ROOT", Path.home() / ".ciel")).resolve()
    lib_path, verilog_lib_path, prims_path, blackbox_path = locate_pdk_files(pdk_root_base, pdk_name, scl_name)
    logger.info(f"PDK environment resolved from: {pdk_root_base}")

    # 3. 解析用例元数据与源文件列表
    meta, sources_orig, sources_opt, tb_path = load_and_validate_case(case_dir, logger)
    top_module = meta["design_name"]
    clock_port = meta.get("clock_port", "clk")
    clock_period = float(meta.get("clock_period_ns", 10.0))

    # 4. Step 1: 形式逻辑等价性验证 (LEC) - 熔断机制
    run_formal_lec(sources_orig, sources_opt, top_module, formal_dir, log_dir, logger)

    # 5. Step 2 ~ Step 4: 物理实现全流程与多维签核评估
    run_configs = {
        "orig": sources_orig,
        "opt": sources_opt,
    }
    all_eval_data: Dict[str, Dict[str, Any]] = {}

    for tag, srcs in run_configs.items():
        # Step 2: 物理实现
        netlist, spef, metrics_json_path = run_pnr_flow(
            tag, srcs, meta, pdk_root_base, pdk_name, scl_name, workspace, log_dir, logger
        )

        # Step 3: 仿真活跃度提取 (输出至 sim/)
        vcd = generate_vcd_activity(
            tag, netlist, tb_path, prims_path, verilog_lib_path, sim_dir, log_dir, logger
        )

        # Step 4: 功耗、时序与物理面积签核分析 (输出至 reports/)
        pwr_m, timing_m, area_m, act_m = run_signoff_evaluation(
            tag, top_module, clock_port, clock_period, netlist, spef, vcd, metrics_json_path, lib_path, blackbox_path, reports_dir, log_dir, logger
        )

        all_eval_data[tag] = {
            "power": pwr_m,
            "timing": timing_m,
            "area": area_m,
            "activity": act_m,
        }

    # 6. Step 5: 综合 PPA 报告与 Trade-off 关系分析 (输出至 reports/ppa_summary.md)
    generate_ppa_summary_report(
        case_name, top_module, all_eval_data, reports_dir, log_dir, logger
    )

    logger.info("Evaluation pipeline completed successfully.")
    logger.info(f"Artifacts organized in: Simulation -> {sim_dir}, Reports -> {reports_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="通用多文件 RTL 变换自动化物理评估基座 (Evaluation Platform)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--case-dir", type=str, required=True, help="待评估案例目录路径 (包含 meta.json, src_orig, src_opt, tb)")
    parser.add_argument("--workspace", type=str, default=None, help="工作空间输出路径 (默认: ./eval_workspace/<case_path>)")
    parser.add_argument("--pdk-root", type=str, default=None, help="PDK 根目录 (默认自适应探测 ~/.ciel 或环境变量 PDK_ROOT)")
    parser.add_argument("--pdk", type=str, default="sky130A", help="目标 PDK 名称")
    parser.add_argument("--scl", type=str, default="sky130_fd_sc_hd", help="目标标准单元库名称")
    parser.add_argument("--devshell", type=str, default=None, help="指定 LibreLane AppImage 路径")

    args = parser.parse_args()

    evaluate_case(
        case_dir=Path(args.case_dir),
        workspace_arg=args.workspace,
        pdk_root_arg=args.pdk_root,
        pdk_name=args.pdk,
        scl_name=args.scl,
        devshell_arg=args.devshell,
    )


if __name__ == "__main__":
    main()
