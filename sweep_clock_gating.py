#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
门控时钟 (Clock Gating) 多维度参数化扫描 CLI 入口
sweep_clock_gating.py

调度 src/analysis/sweep_clock_gating.py 执行 Scale × Activity 全物理后仿二维扫描。
===============================================================================
"""

import sys
import argparse
from pathlib import Path

# 确保在导入依赖模块前完成 DevShell 环境自检与自启动
from src.common.env import ensure_devshell_environment
from src.analysis.sweep_clock_gating import run_clock_gating_sweep


def main():
    ensure_devshell_environment()

    parser = argparse.ArgumentParser(
        description="Sky130 门控时钟多维度参数化全物理扫描分析套件",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--workspace", type=str, default="./eval_workspace/clock_gating", help="扫描工作空间输出路径")
    parser.add_argument("--pdk-root", type=str, default=None, help="PDK 根目录 (默认自适应探测 ~/.ciel 或环境变量 PDK_ROOT)")
    parser.add_argument("--widths", nargs="+", type=int, default=[8, 16, 32, 64], help="要扫描的寄存器位宽列表")
    parser.add_argument("--duties", nargs="+", type=int, default=[5, 20, 50, 80], help="要扫描的使能活跃度 (占空比 %%) 列表")

    args = parser.parse_args()

    run_clock_gating_sweep(
        workspace_dir=Path(args.workspace),
        pdk_root_arg=args.pdk_root,
        widths=args.widths,
        duties=args.duties,
    )


if __name__ == "__main__":
    main()
