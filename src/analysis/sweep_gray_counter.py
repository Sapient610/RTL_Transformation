#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
格雷码计数器 (Gray Code Counter) 多维度参数化扫描与物理签核分析模块
src/analysis/sweep_gray_counter.py

功能说明:
  针对计数器 (gray_counter) 在 Sky130 工艺下的格雷码低功耗 RTL 变换优化，
  在多维参数空间开展系统性全流程物理后仿与签核扫描：
    1. 计数器规模 (Bitwidth Scale): 4-bit, 8-bit, 16-bit, 32-bit
    2. 使能活跃度 (Enable Activity / Duty Cycle): 5%, 20%, 50%, 80%

  物理架构对比:
    - 原始版本 (Orig): Naive Dual-Register Binary-to-Gray 发生器 (2N 个 DFF)
    - 优化版本 (Opt): Native Single-Register Direct Gray 发生器 (N 个 DFF)
===============================================================================
"""

import os
import sys
import re
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from src.common.env import run_command_with_logging
from src.common.pdk import locate_pdk_files
from src.common.case_loader import load_and_validate_case
from src.core.formal import run_formal_lec
from src.core.pnr import run_pnr_flow


def setup_sweep_logger(log_dir: Path) -> logging.Logger:
    logger = logging.getLogger("GrayCounterSweep")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_h = logging.StreamHandler(sys.stdout)
    console_h.setLevel(logging.INFO)
    console_h.setFormatter(formatter)
    logger.addHandler(console_h)

    file_h = logging.FileHandler(log_dir / "sweep.log", encoding="utf-8")
    file_h.setLevel(logging.INFO)
    file_h.setFormatter(formatter)
    logger.addHandler(file_h)

    return logger


def run_activity_sim_and_sta(
    case_name: str,
    width: int,
    duty: int,
    tag: str,
    top_module: str,
    clock_port: str,
    clock_period: float,
    netlist: Path,
    spef: Path,
    tb_path: Path,
    prims_path: Path,
    verilog_lib_path: Path,
    lib_path: Path,
    blackbox_path: Path,
    metrics_json_path: Optional[Path],
    sim_dir: Path,
    reports_dir: Path,
    log_dir: Path,
    logger: logging.Logger,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """针对指定的使能活跃度运行门级后仿与 OpenSTA 签核"""
    sim_tag = f"{tag}_duty{duty}"
    sim_out = sim_dir / f"{sim_tag}.vvp"
    vcd_out = sim_dir / f"{sim_tag}_activity.vcd"

    # 1. 编译门级仿真器
    compile_cmd = [
        "iverilog",
        "-g2012",
        "-DFUNCTIONAL",
        "-o", str(sim_out),
        str(prims_path),
        str(verilog_lib_path),
        str(netlist),
        str(tb_path),
    ]
    sim_log = log_dir / f"sim_compile_{sim_tag}.log"
    run_command_with_logging(compile_cmd, sim_log, cwd=sim_dir, logger=logger)

    # 2. 注入动态 +EN_DUTY 运行仿真
    run_cmd = ["vvp", str(sim_out), f"+VCD_FILE={vcd_out}", f"+EN_DUTY={duty}"]
    vvp_log = log_dir / f"sim_run_{sim_tag}.log"
    run_command_with_logging(run_cmd, vvp_log, cwd=sim_dir, logger=logger)

    if not vcd_out.exists() or vcd_out.stat().st_size == 0:
        raise RuntimeError(f"VCD waveform not generated: {vcd_out}")

    # 3. OpenSTA 静态时序与翻转功耗签核
    power_rpt = reports_dir / f"{sim_tag}_power.rpt"
    timing_rpt = reports_dir / f"{sim_tag}_timing.rpt"
    activity_rpt = reports_dir / f"{sim_tag}_activity.rpt"
    activity_ann_rpt = reports_dir / f"{sim_tag}_activity_annotation.rpt"

    sta_script = f"""
    read_liberty {lib_path}
    read_verilog {blackbox_path}
    read_verilog {netlist}
    link_design {top_module}
    read_spef {spef}
    create_clock -name {clock_port} -period {clock_period} [get_ports {clock_port}]

    read_vcd -scope tb_top/u_dut {vcd_out}
    report_power > {power_rpt}

    report_checks -path_delay max -format full_clock_expanded -digits 3 > {timing_rpt}
    report_worst_slack -max
    report_worst_slack -min
    report_tns

    report_activity_annotation -report_annotated > {activity_ann_rpt}

    set act_file [open "{activity_rpt}" w]
    puts $act_file "================================================================================"
    puts $act_file "              OpenSTA Detailed Signal & Pin Activity Signoff Report             "
    puts $act_file "================================================================================"
    puts $act_file [format "%-35s | %-12s | %-18s | %-12s | %-8s" "Pin/Port Name" "Category" "Transition Density" "Static Prob" "Source"]
    puts $act_file [string repeat "-" 95]
    foreach port [get_ports *] {{
        set pname [get_full_name $port]
        set act [get_property $port activity]
        if {{$act != ""}} {{
            puts $act_file [format "%-35s | %-12s | %-18.4e | %-12.4f | %-8s" $pname "Port" [lindex $act 0] [lindex $act 1] [lindex $act 2]]
        }}
    }}
    foreach pin [get_pins *] {{
        set pname [get_full_name $pin]
        set act [get_property $pin activity]
        if {{$act != ""}} {{
            puts $act_file [format "%-35s | %-12s | %-18.4e | %-12.4f | %-8s" $pname "Internal Pin" [lindex $act 0] [lindex $act 1] [lindex $act 2]]
        }}
    }}
    close $act_file
    exit
    """
    sta_cmd_path = reports_dir / f"calc_signoff_{sim_tag}.tcl"
    sta_cmd_path.write_text(sta_script, encoding="utf-8")

    sta_log = log_dir / f"sta_signoff_{sim_tag}.log"
    run_command_with_logging(["sta", str(sta_cmd_path)], sta_log, cwd=reports_dir, logger=logger)

    # 4. 解析指标
    pwr_metrics: Dict[str, Any] = {}
    if power_rpt.exists():
        text = power_rpt.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            for group in ["Sequential", "Combinational", "Clock", "Total"]:
                if stripped.startswith(group) and any(unit in line for unit in ["W", "mW", "uW", "pW", "e-"]):
                    parts = stripped.split()
                    if len(parts) >= 5:
                        pwr_metrics[f"{group}_Internal"] = parts[1]
                        pwr_metrics[f"{group}_Switching"] = parts[2]
                        pwr_metrics[f"{group}_Leakage"] = parts[3]
                        pwr_metrics[f"{group}_Total"] = parts[4]
                        if group == "Total":
                            pwr_metrics["Internal"] = parts[1]
                            pwr_metrics["Switching"] = parts[2]
                            pwr_metrics["Leakage"] = parts[3]
                            pwr_metrics["Total"] = parts[4]

    timing_metrics: Dict[str, Any] = {
        "Clock_Period_ns": clock_period,
        "Setup_WS_ns": "N/A",
        "Critical_Path_Delay_ns": "N/A",
    }
    if timing_rpt.exists():
        t_text = timing_rpt.read_text(encoding="utf-8")
        for line in t_text.splitlines():
            if "data arrival time" in line:
                m = re.search(r"([\d\.\-]+)\s+data arrival time", line)
                if m:
                    timing_metrics["Critical_Path_Delay_ns"] = round(abs(float(m.group(1))), 3)
            if "slack (MET)" in line or "slack (VIOLATED)" in line:
                m = re.search(r"([\d\.\-]+)\s+slack", line)
                if m:
                    timing_metrics["Setup_WS_ns"] = float(m.group(1))

    area_metrics: Dict[str, Any] = {
        "Stdcell_Count": "N/A",
        "Stdcell_Area_um2": "N/A",
        "DFF_Count": "N/A",
    }
    if metrics_json_path and metrics_json_path.exists():
        try:
            m_data = json.loads(metrics_json_path.read_text(encoding="utf-8"))
            area_metrics["Stdcell_Count"] = m_data.get("design__instance__count__stdcell", "N/A")
            area_metrics["Stdcell_Area_um2"] = m_data.get("design__instance__area__stdcell", "N/A")
            area_metrics["DFF_Count"] = m_data.get("design__instance__count__class:sequential_cell", "N/A")
            ws = m_data.get("timing__setup__ws__corner:nom_tt_025C_1v80")
            if ws is None:
                ws = m_data.get("timing__setup__ws")
            if ws is not None and timing_metrics["Setup_WS_ns"] == "N/A":
                timing_metrics["Setup_WS_ns"] = round(float(ws), 3)
                timing_metrics["Critical_Path_Delay_ns"] = round(clock_period - float(ws), 3)
        except Exception:
            pass

    activity_metrics: Dict[str, Any] = {
        "Annotated_Pins": "N/A",
        "Enable_Static_Probability": "N/A",
        "Clock_Transition_Density": "N/A",
    }
    if activity_ann_rpt.exists():
        for line in activity_ann_rpt.read_text(encoding="utf-8").splitlines():
            line_s = line.strip()
            if line_s.startswith("vcd"):
                parts = line_s.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    activity_metrics["Annotated_Pins"] = int(parts[1])

    return pwr_metrics, timing_metrics, area_metrics, activity_metrics


def run_gray_counter_sweep(
    workspace_dir: Path,
    pdk_root_arg: Optional[str] = None,
    widths: Optional[List[int]] = None,
    duties: Optional[List[int]] = None,
    force_pnr: bool = False,
):
    if widths is None:
        widths = [4, 8, 16, 32]
    if duties is None:
        duties = [5, 20, 50, 80]

    project_root = Path(__file__).resolve().parent.parent.parent
    cases_dir = project_root / "cases" / "gray_counter"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    log_dir = workspace_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_sweep_logger(log_dir)

    logger.info("=" * 80)
    logger.info("      Sky130 Gray Code Counter Multi-Dimensional Physical Signoff Sweep")
    logger.info("=" * 80)
    logger.info(f"[*] Target Scales (Bitwidths): {widths}")
    logger.info(f"[*] Target Enable Duties (%):  {duties}")
    logger.info(f"[*] Workspace Directory:       {workspace_dir}")

    # 1. 定位 PDK
    pdk_root = Path(pdk_root_arg).expanduser().resolve() if pdk_root_arg else Path.home() / ".ciel"
    lib_path, verilog_lib_path, prims_path, blackbox_path = locate_pdk_files(pdk_root)
    logger.info(f"[*] PDK Root: {pdk_root}")
    logger.info(f"[*] Liberty:  {lib_path}")

    sweep_results: Dict[str, Any] = {}

    # 2. 遍历各规模
    for width in widths:
        case_name = f"gray_counter_{width}b"
        case_dir = cases_dir / case_name
        if not case_dir.exists():
            logger.warning(f"Case directory {case_dir} not found! Skipping...")
            continue

        logger.info("\n" + "#" * 80)
        logger.info(f"### Processing Scale: {width}-bit Gray Counter ({case_name})")
        logger.info("#" * 80)

        case_ws = workspace_dir / case_name
        case_ws.mkdir(parents=True, exist_ok=True)
        case_log_dir = case_ws / "logs"
        case_log_dir.mkdir(parents=True, exist_ok=True)
        sim_dir = case_ws / "sim"
        sim_dir.mkdir(parents=True, exist_ok=True)
        reports_dir = case_ws / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        formal_dir = case_ws / "formal"
        formal_dir.mkdir(parents=True, exist_ok=True)

        meta, sources_orig, sources_opt, tb_path = load_and_validate_case(case_dir, logger)
        top = meta["design_name"]
        clock_port = meta.get("clock_port", "clk")
        clock_period = float(meta.get("clock_period_ns", 10.0))

        # Step 1: Formal LEC
        run_formal_lec(sources_orig, sources_opt, top, formal_dir, case_log_dir, logger)

        # Step 2: Physical Implementation (LibreLane 80-Stage)
        def get_pnr_artifacts(tag: str) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
            nl = case_ws / tag / "runs" / tag / "final" / "nl" / f"{top}.nl.v"
            spef = case_ws / tag / "runs" / tag / "final" / "spef" / "nom" / f"{top}.nom.spef"
            met = case_ws / tag / "runs" / tag / "final" / "metrics.json"
            if nl.exists() and spef.exists():
                return nl, spef, met
            return None, None, None

        netlist_orig, spef_orig, metrics_orig = get_pnr_artifacts("orig") if not force_pnr else (None, None, None)
        if not netlist_orig or not spef_orig:
            logger.info(f"\n--- Running Full PnR for [{case_name} - Orig] ---")
            netlist_orig, spef_orig, metrics_orig = run_pnr_flow(
                "orig", sources_orig, meta, pdk_root, "sky130A", "sky130_fd_sc_hd", case_ws, case_log_dir, logger
            )
        else:
            logger.info(f"[REUSE] Reusing existing Post-PnR netlist & SPEF for [{case_name} - Orig]: {netlist_orig}")

        netlist_opt, spef_opt, metrics_opt = get_pnr_artifacts("opt") if not force_pnr else (None, None, None)
        if not netlist_opt or not spef_opt:
            logger.info(f"\n--- Running Full PnR for [{case_name} - Opt] ---")
            netlist_opt, spef_opt, metrics_opt = run_pnr_flow(
                "opt", sources_opt, meta, pdk_root, "sky130A", "sky130_fd_sc_hd", case_ws, case_log_dir, logger
            )
        else:
            logger.info(f"[REUSE] Reusing existing Post-PnR netlist & SPEF for [{case_name} - Opt]: {netlist_opt}")

        sweep_results[f"{width}b"] = {
            "width": width,
            "duties": {},
            "pnr_metrics": {},
        }

        # Step 3 & 4: 针对不同使能活跃度运行仿真与 OpenSTA 签核
        for duty in duties:
            logger.info(f"\n>>> Running Signoff Sweep for [{width}b] with Enable Duty = {duty}%")

            # 评估 Orig
            pwr_orig, tmg_orig, area_orig, act_orig = run_activity_sim_and_sta(
                case_name, width, duty, "orig", top, clock_port, clock_period,
                netlist_orig, spef_orig, tb_path, prims_path, verilog_lib_path,
                lib_path, blackbox_path, metrics_orig, sim_dir, reports_dir, case_log_dir, logger
            )

            # 评估 Opt
            pwr_opt, tmg_opt, area_opt, act_opt = run_activity_sim_and_sta(
                case_name, width, duty, "opt", top, clock_port, clock_period,
                netlist_opt, spef_opt, tb_path, prims_path, verilog_lib_path,
                lib_path, blackbox_path, metrics_opt, sim_dir, reports_dir, case_log_dir, logger
            )

            # 功耗计算解析
            def parse_val(s):
                if not s or s == "N/A": return 0.0
                try: return float(s)
                except ValueError:
                    unit_map = {"uW": 1e-6, "mW": 1e-3, "W": 1.0, "nW": 1e-9, "pW": 1e-12}
                    for u, mul in unit_map.items():
                        if s.endswith(u):
                            return float(s[:-len(u)]) * mul
                    return 0.0

            p_orig = parse_val(pwr_orig.get("Total", "0"))
            p_opt = parse_val(pwr_opt.get("Total", "0"))
            p_delta_pct = ((p_opt - p_orig) / p_orig * 100.0) if p_orig > 0 else 0.0

            clk_orig = parse_val(pwr_orig.get("Clock_Total", "0"))
            clk_opt = parse_val(pwr_opt.get("Clock_Total", "0"))

            seq_orig = parse_val(pwr_orig.get("Sequential_Total", "0"))
            seq_opt = parse_val(pwr_opt.get("Sequential_Total", "0"))

            comb_orig = parse_val(pwr_orig.get("Combinational_Total", "0"))
            comb_opt = parse_val(pwr_opt.get("Combinational_Total", "0"))

            sweep_results[f"{width}b"]["duties"][str(duty)] = {
                "orig_total_power_uW": round(p_orig * 1e6, 3),
                "opt_total_power_uW": round(p_opt * 1e6, 3),
                "power_delta_pct": round(p_delta_pct, 2),
                "orig_clock_power_uW": round(clk_orig * 1e6, 3),
                "opt_clock_power_uW": round(clk_opt * 1e6, 3),
                "orig_sequential_power_uW": round(seq_orig * 1e6, 3),
                "opt_sequential_power_uW": round(seq_opt * 1e6, 3),
                "orig_combinational_power_uW": round(comb_orig * 1e6, 3),
                "opt_combinational_power_uW": round(comb_opt * 1e6, 3),
                "orig_setup_ws_ns": tmg_orig.get("Setup_WS_ns", "N/A"),
                "opt_setup_ws_ns": tmg_opt.get("Setup_WS_ns", "N/A"),
                "orig_critical_path_delay_ns": tmg_orig.get("Critical_Path_Delay_ns", "N/A"),
                "opt_critical_path_delay_ns": tmg_opt.get("Critical_Path_Delay_ns", "N/A"),
            }

            logger.info(
                f"[{width}b | Duty={duty}%] Orig: {round(p_orig*1e6, 2)} uW -> Opt: {round(p_opt*1e6, 2)} uW "
                f"| Delta: {round(p_delta_pct, 2)}% | WS: {tmg_orig.get('Setup_WS_ns')}ns -> {tmg_opt.get('Setup_WS_ns')}ns"
            )

        # 记录通用物理指标
        sweep_results[f"{width}b"]["pnr_metrics"] = {
            "orig_stdcell_count": area_orig.get("Stdcell_Count", "N/A"),
            "opt_stdcell_count": area_opt.get("Stdcell_Count", "N/A"),
            "orig_stdcell_area_um2": area_orig.get("Stdcell_Area_um2", "N/A"),
            "opt_stdcell_area_um2": area_opt.get("Stdcell_Area_um2", "N/A"),
            "orig_dff_count": area_orig.get("DFF_Count", 2 * width),
            "opt_dff_count": area_opt.get("DFF_Count", width),
        }

    # 3. 结构化导出结果
    results_json = workspace_dir / "sweep_results.json"
    results_json.write_text(json.dumps(sweep_results, indent=2), encoding="utf-8")
    logger.info(f"\n[DONE] Sweep results successfully saved to: {results_json}")

    return sweep_results

