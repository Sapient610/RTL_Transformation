#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 2: 物理实现全流程 (Physical Implementation via LibreLane)
"""

import json
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any

from src.common.env import run_command_with_logging


def run_pnr_flow(
    run_tag: str,
    verilog_sources: List[Path],
    meta: Dict[str, Any],
    pdk_root: Path,
    pdk_name: str,
    scl_name: str,
    workspace: Path,
    log_dir: Path,
    logger: logging.Logger,
) -> Tuple[Path, Path, Path]:
    """
    配置并调用 LibreLane 80-Stage 物理实现全流程，
    输出纯逻辑网表 (*.nl.v)、典型角点 SPEF 寄生参数以及 PPA 结构化指标 metrics.json。
    """
    logger.info("=" * 70)
    logger.info(f">>> Step 2: Physical Implementation [{run_tag}] (LibreLane 80-Stage)")
    logger.info("=" * 70)

    top = meta["design_name"]
    clock_port = meta.get("clock_port", "clk")
    clock_period = float(meta.get("clock_period_ns", 10.0))
    clock_uncertainty = float(meta.get("clock_uncertainty_ns", 0.25))
    clock_transition = float(meta.get("clock_transition_ns", 0.15))
    input_delay = float(meta.get("input_delay_ns", 2.0))
    output_delay = float(meta.get("output_delay_ns", 2.0))
    output_load = float(meta.get("output_load_pf", 0.033442))
    pad_load = float(meta.get("pad_load_pf", 0.0))
    core_util = int(meta.get("core_utilization", 25))
    target_density = int(meta.get("target_density_pct", 35))

    tag_dir = workspace / run_tag
    tag_dir.mkdir(parents=True, exist_ok=True)

    sdc_file = tag_dir / "target.sdc"
    sdc_content = f"""
    create_clock [get_ports {clock_port}] -name {clock_port} -period {clock_period}
    set_clock_uncertainty {clock_uncertainty} [get_clocks {clock_port}]
    set_clock_transition {clock_transition} [get_clocks {clock_port}]

    set_input_delay -max {input_delay} -clock {clock_port} [all_inputs -no_clocks]
    set_output_delay -max {output_delay} -clock {clock_port} [all_outputs]
    set_load {output_load} [all_outputs]
    """
    if pad_load > 0.0:
        sdc_content += f"""
    catch {{set_load {pad_load} [get_ports pad_*]}}
    """
    sdc_file.write_text(sdc_content, encoding="utf-8")

    design_config = {
        "PDK": pdk_name,
        "STD_CELL_LIBRARY": scl_name,
        "DESIGN_NAME": top,
        "VERILOG_FILES": [str(p) for p in verilog_sources],
        "CLOCK_PORT": clock_port,
        "CLOCK_PERIOD": clock_period,
        "FP_SIZING": "relative",
        "FP_CORE_UTIL": core_util,
        "FP_ASPECT_RATIO": 1,
        "PL_TARGET_DENSITY_PCT": target_density,
        "RUN_POST_CTS_RESIZER_TIMING": meta.get("run_post_cts_resizer_timing", False),
        "HOLD_VIOLATION_CORNERS": meta.get("hold_violation_corners", [""]),
        "SETUP_VIOLATION_CORNERS": meta.get("setup_violation_corners", [""]),
        "MAX_CAP_VIOLATION_CORNERS": meta.get("max_cap_violation_corners", [""]),
        "MAX_SLEW_VIOLATION_CORNERS": meta.get("max_slew_violation_corners", [""]),
        "PNR_SDC_FILE": str(sdc_file),
        "SIGNOFF_SDC_FILE": str(sdc_file),
        "RUN_KLAYOUT_STREAMOUT": True,
        "RUN_MAGIC_STREAMOUT": True,
        "RUN_KLAYOUT_DRC": False,
        "RUN_MAGIC_DRC": False,
        "RUN_LVS": False,
    }

    config_file = tag_dir / "config.json"
    config_file.write_text(json.dumps(design_config, indent=2), encoding="utf-8")

    cmd = [
        "librelane",
        str(config_file),
        "--design-dir", str(tag_dir),
        "--pdk-root", str(pdk_root),
        "--pdk", pdk_name,
        "--scl", scl_name,
        "--run-tag", run_tag,
        "--overwrite",
    ]

    pnr_log = log_dir / f"pnr_{run_tag}.log"
    run_command_with_logging(cmd, pnr_log, cwd=tag_dir, logger=logger)

    run_dir = tag_dir / "runs" / run_tag
    final_dir = run_dir / "final"

    # 1. 纯逻辑网表 (No-Power Logic Netlist)
    netlist = final_dir / "nl" / f"{top}.nl.v"
    if not netlist.exists():
        fallback_nl = list(final_dir.glob(f"nl/**/{top}*.nl.v")) or list(final_dir.glob(f"**/{top}*.nl.v"))
        fallback_nl = [f for f in fallback_nl if ".pnl." not in f.name]
        if fallback_nl:
            netlist = fallback_nl[0]
        else:
            raise FileNotFoundError(f"Cannot find logic netlist (*.nl.v) in {final_dir}")

    # 2. 寄生参数 SPEF
    spef = final_dir / "spef" / "nom" / f"{top}.nom.spef"
    if not spef.exists():
        fallback_spef = list(final_dir.glob(f"spef/**/{top}*.spef")) or list(final_dir.glob(f"**/{top}*.spef"))
        if fallback_spef:
            spef = fallback_spef[0]
        else:
            raise FileNotFoundError(f"Cannot find parasitic SPEF file in {final_dir}")

    # 3. 提取 LibreLane 物理实现结构化指标 metrics.json
    metrics_json = final_dir / "metrics.json"
    if not metrics_json.exists():
        fallback_json = list(run_dir.glob("**/metrics.json"))
        if fallback_json:
            metrics_json = fallback_json[0]

    logger.info(f"[*] Post-PnR Logic Netlist: {netlist}")
    logger.info(f"[*] Post-PnR SPEF:          {spef}")
    if metrics_json and metrics_json.exists():
        logger.info(f"[*] Post-PnR Metrics:       {metrics_json}")

    return netlist, spef, metrics_json

