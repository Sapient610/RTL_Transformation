#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境检测与命令执行模块
负责 AppImage DevShell 自托管环境探测、子进程日志重定向与错误处理
"""

import os
import sys
import shutil
import logging
import subprocess
from pathlib import Path
from typing import List, Optional


def ensure_devshell_environment(devshell_arg: Optional[str] = None):
    """
    检查当前环境是否包含必须的 EDA 工具（yosys, librelane, iverilog, vvp, sta）。
    若缺失，则自动寻找 AppImage 并通过 AppImage devshell 重新托管启动本脚本。
    """
    required_tools = ["yosys", "librelane", "iverilog", "vvp", "sta"]
    missing_tools = [tool for tool in required_tools if shutil.which(tool) is None]

    if not missing_tools:
        return  # 所有工具已就绪

    candidates = []
    if devshell_arg:
        candidates.append(Path(devshell_arg).expanduser().resolve())
    if "DEVSHELL_APPIMAGE" in os.environ:
        candidates.append(Path(os.environ["DEVSHELL_APPIMAGE"]).expanduser().resolve())

    candidates.extend([
        Path.home() / "librelane" / "librelane-devshell-x86_64.AppImage",
        Path.home() / "libreline" / "librelane-devshell-x86_64.AppImage",
    ])

    appimage_path = None
    for cand in candidates:
        if cand.exists() and os.access(cand, os.X_OK):
            appimage_path = cand
            break

    if not appimage_path:
        sys.stderr.write(
            f"[CRITICAL ERROR] Required EDA tools {missing_tools} are not in PATH, "
            f"and AppImage was not found at standard locations: {candidates}.\n"
            f"Please run within devshell or specify --devshell <path_to_appimage>.\n"
        )
        sys.exit(1)

    sys.stderr.write(
        f"[INFO] EDA tools not directly in PATH. Re-executing inside devshell AppImage:\n"
        f"       {appimage_path} python3 {' '.join(sys.argv)}\n\n"
    )
    cmd = [str(appimage_path), "python3"] + sys.argv
    res = subprocess.call(cmd)
    sys.exit(res)


def run_command_with_logging(
    cmd: List[str],
    log_file: Path,
    cwd: Optional[Path] = None,
    logger: Optional[logging.Logger] = None,
):
    """以流式输出并追加至独立日志文件的方式执行外部命令"""
    cmd_str = " ".join(str(c) for c in cmd)
    if logger:
        logger.info(f"Executing: {cmd_str}")

    with open(log_file, "w", encoding="utf-8") as f_out:
        f_out.write(f"=== Command: {cmd_str} ===\n\n")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            text=True,
            bufsize=1,
        )

        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            f_out.write(line)

        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)

