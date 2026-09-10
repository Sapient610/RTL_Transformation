#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDK 基准库与模型定位模块
"""

from pathlib import Path
from typing import Tuple


def locate_pdk_files(
    pdk_root: Path,
    pdk_name: str = "sky130A",
    scl_name: str = "sky130_fd_sc_hd",
) -> Tuple[Path, Path, Path, Path]:
    """定位目标 PDK 与标准单元库的关键文件路径"""
    candidates = []
    for p in sorted(pdk_root.glob("ciel/sky130/versions/*")):
        if (p / pdk_name).exists():
            candidates.append(p / pdk_name)

    if (pdk_root / pdk_name).exists():
        candidates.append(pdk_root / pdk_name)

    if not candidates:
        raise FileNotFoundError(f"Cannot locate PDK '{pdk_name}' inside '{pdk_root}'. Searched {candidates}")

    real_pdk = candidates[0]
    lib_path = real_pdk / "libs.ref" / scl_name / "lib" / f"{scl_name}__tt_025C_1v80.lib"
    verilog_path = real_pdk / "libs.ref" / scl_name / "verilog" / f"{scl_name}.v"
    prims_path = real_pdk / "libs.ref" / scl_name / "verilog" / "primitives.v"
    blackbox_path = real_pdk / "libs.ref" / scl_name / "verilog" / f"{scl_name}__blackbox.v"

    for file_path, desc in [
        (lib_path, "Standard Cell Liberty"),
        (verilog_path, "Standard Cell Functional Verilog"),
        (prims_path, "Sky130 Primitives Verilog"),
        (blackbox_path, "Sky130 Blackbox Verilog"),
    ]:
        if not file_path.exists():
            raise FileNotFoundError(f"PDK dependency [{desc}] not found at: {file_path}")

    return lib_path, verilog_path, prims_path, blackbox_path

