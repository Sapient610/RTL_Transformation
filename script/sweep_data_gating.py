#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
小型数据通路数据门控 (Data Gating) 多维度参数化扫描 CLI 入口
script/sweep_data_gating.py

调度 src/analysis/sweep_data_gating.py 执行 Scale × Valid Duty × Data Activity
三维全物理后仿扫描。
===============================================================================
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.env import ensure_devshell_environment
from src.analysis.sweep_data_gating import run_data_gating_sweep


def main():
    ensure_devshell_environment()

    parser = argparse.ArgumentParser(
        description="Sky130 小型数据通路数据门控多维度参数化全物理扫描分析套件",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--workspace", type=str, default=str(PROJECT_ROOT / "eval_workspace" / "data_gating"), help="扫描工作空间输出路径")
    parser.add_argument("--pdk-root", type=str, default=None, help="PDK 根目录 (默认自适应探测 ~/.ciel 或环境变量 PDK_ROOT)")
    parser.add_argument("--widths", nargs="+", type=int, default=[4, 8, 12, 16], help="要扫描的数据通路位宽列表")
    parser.add_argument("--duties", nargs="+", type=int, default=[5, 20, 50, 80], help="要扫描的控制信号有效概率 (Valid Duty %) 列表")
    parser.add_argument("--activities", nargs="+", type=int, default=[10, 30, 60], help="要扫描的数据总线翻转活跃度 (%) 列表")
    parser.add_argument("--duties", nargs="+", type=int, default=[5, 20, 50, 80], help="要扫描的控制信号有效概率 (Valid Duty %%) 列表")
    parser.add_argument("--activities", nargs="+", type=int, default=[10, 30, 60], help="要扫描的数据总线翻转活跃度 (%%) 列表")

    args = parser.parse_args()

    run_data_gating_sweep(
        workspace_dir=Path(args.workspace),
        pdk_root_arg=args.pdk_root,
        widths=args.widths,
        valid_duties=args.duties,
        data_activities=args.activities,
    )


if __name__ == "__main__":
    main()
