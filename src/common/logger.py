#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志管理与工作空间清理模块
"""

import sys
import logging
from pathlib import Path


def setup_logging(log_dir: Path, name: str = "evaluation_platform") -> logging.Logger:
    """初始化并配置标准终端输出与带时间戳的集中流水线日志"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    c_handler = logging.StreamHandler(sys.stdout)
    f_handler = logging.FileHandler(log_dir / "overall_pipeline.log", encoding="utf-8")
    formatter = logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    c_handler.setFormatter(formatter)
    f_handler.setFormatter(formatter)

    logger.addHandler(c_handler)
    logger.addHandler(f_handler)
    return logger


def cleanup_legacy_root_files(workspace: Path, logger: logging.Logger):
    """
    清理先前版本散落在 workspace 根目录的旧临时文件，保持工作空间目录整洁。
    """
    patterns = ["*.vvp", "*.vcd", "*.rpt", "*.tcl", "lec.ys"]
    migrated_cnt = 0
    for pat in patterns:
        for p in workspace.glob(pat):
            if p.is_file():
                try:
                    p.unlink()
                    migrated_cnt += 1
                except Exception:
                    pass
    if migrated_cnt > 0:
        logger.info(f"Cleaned up {migrated_cnt} legacy flat files in workspace root.")

