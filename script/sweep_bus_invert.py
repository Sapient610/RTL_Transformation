#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
总线反转编码 (Bus-Invert Coding, BI) 多维度参数化扫描 CLI 入口
script/sweep_bus_invert.py

调度 src/analysis/sweep_bus_invert.py 执行 Bus Scale × Toggle Rate 全物理后仿二维扫描。
===============================================================================
"""

import sys
import argparse
from pathlib import Path

# 动态将项目根目录加入 sys.path，确保无论在何处启动均可正确导入 src 模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 确保在导入依赖模块前完成 DevShell 环境自检与自启动
from src.common.env import ensure_devshell_environment
from src.analysis.sweep_bus_invert import run_bus_invert_sweep


def main():
    ensure_devshell_environment()

    parser = argparse.ArgumentParser(
        description="Sky130 总线反转编码 (Bus-Invert) 多维度物理扫描分析套件",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--workspace", type=str, default=str(PROJECT_ROOT / "eval_workspace" / "bus_invert"), help="扫描工作空间输出路径")
    parser.add_argument("--pdk-root", type=str, default=None, help="PDK 根目录 (默认自适应探测 ~/.ciel 或环境变量 PDK_ROOT)")
    parser.add_argument("--widths", nargs="+", type=int, default=[8, 16, 32, 64], help="要扫描的总线位宽列表 (e.g. 8 16 32 64)")
    parser.add_argument("--toggle-rates", nargs="+", type=int, default=[15, 35, 60, 85], help="要扫描的输入数据翻转率列表 (e.g. 15 35 60 85)")
    parser.add_argument("--force-pnr", action="store_true", help="强制重新执行 LibreLane PnR，忽略已有网表与寄生参数")

    args = parser.parse_args()

    run_bus_invert_sweep(
        workspace_dir=Path(args.workspace),
        pdk_root_arg=args.pdk_root,
        width_list=args.widths,
        toggle_rates=args.toggle_rates,
        force_pnr=args.force_pnr,
    )


if __name__ == "__main__":
    main()

