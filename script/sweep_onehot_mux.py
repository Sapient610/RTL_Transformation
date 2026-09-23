#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
独热编码多路选择器 (One-Hot vs Binary MUX) 多维度参数化扫描 CLI 入口
script/sweep_onehot_mux.py

调度 src/analysis/sweep_onehot_mux.py 执行 Channel Scale × Switch Duty 全物理后仿二维扫描。
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
from src.analysis.sweep_onehot_mux import run_onehot_mux_sweep


def main():
    ensure_devshell_environment()

    parser = argparse.ArgumentParser(
        description="Sky130 独热编码相较于二进制码多路器多维度物理扫描分析套件",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--workspace", type=str, default=str(PROJECT_ROOT / "eval_workspace" / "onehot_mux"), help="扫描工作空间输出路径")
    parser.add_argument("--pdk-root", type=str, default=None, help="PDK 根目录 (默认自适应探测 ~/.ciel 或环境变量 PDK_ROOT)")
    parser.add_argument("--channels", nargs="+", type=int, default=[4, 8, 16, 32], help="要扫描的多路器通道规模列表 (e.g. 4 8 16 32)")
    parser.add_argument("--duties", nargs="+", type=int, default=[5, 20, 50, 80], help="要扫描的通道切换活跃度 (Switch Duty %) 列表")
    parser.add_argument("--force-pnr", action="store_true", help="强制重新执行 LibreLane PnR，忽略已有网表与寄生参数")

    args = parser.parse_args()

    run_onehot_mux_sweep(
        workspace_dir=Path(args.workspace),
        pdk_root_arg=args.pdk_root,
        channel_list=args.channels,
        duties=args.duties,
        force_pnr=args.force_pnr,
    )


if __name__ == "__main__":
    main()

