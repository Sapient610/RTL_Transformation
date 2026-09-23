#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
总线反转编码 (Bus-Invert Coding, BI) 多维度物理签核扫描模块
src/analysis/sweep_bus_invert.py

功能说明:
  针对总线传输架构 (bus_top) 在 Sky130 工艺下的 Bus-Invert 低功耗 RTL 变换优化，
  在多维参数空间开展系统性全流程物理后仿与签核扫描：
    1. 总线位宽规模 (Bus Bitwidth Scale): 8-bit, 16-bit, 32-bit, 64-bit
    2. 输入翻转活跃度 (Toggle Rate / Activity %): 15%, 35%, 60%, 85%

  物理架构对比:
    - 原始版本 (Orig): 原始非反转双级流水线总线 (Raw Bus, N-bit)
    - 优化版本 (Opt):  总线反转编码双级流水线总线 (Bus-Invert, N+1 bit)
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
    logger = logging.getLogger("BusInvertSweep")
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


def parse_power_rpt_file(power_rpt: Path) -> Dict[str, Any]:
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
    return pwr_metrics


def run_activity_sim_and_sta(
    case_name: str,
    width: int,
    toggle_rate: int,
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
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """针对指定的输入数据翻转率运行门级后仿与 OpenSTA 签核"""
    sim_tag = f"{tag}_tr{toggle_rate}"
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

    # 2. 运行仿真并生成包含精确翻转率的真实波形 VCD
    sim_run_cmd = [
        "vvp",
        str(sim_out),
        f"+VCD_FILE={str(vcd_out)}",
        f"+TOGGLE_RATE={toggle_rate}",
    ]
    sim_run_log = log_dir / f"sim_run_{sim_tag}.log"
    run_command_with_logging(sim_run_cmd, sim_run_log, cwd=sim_dir, logger=logger)

    if not vcd_out.exists() or vcd_out.stat().st_size == 0:
        logger.error(f"VCD output {vcd_out} was not generated or is empty!")
        raise RuntimeError("VCD generation failed during gate-level simulation.")

    # 3. 运行带有反标 VCD 的高精度 OpenSTA 签核分析
    timing_rpt = reports_dir / f"sta_timing_{sim_tag}.rpt"
    power_rpt = reports_dir / f"sta_power_{sim_tag}.rpt"
    activity_ann_rpt = reports_dir / f"sta_activity_{sim_tag}.rpt"

    sta_script = f"""
    read_liberty {str(lib_path)}
    read_verilog {str(netlist)}
    link_design {top_module}
    read_spef {str(spef)}

    create_clock -name {clock_port} -period {clock_period} [get_ports {clock_port}]
    set_input_delay -clock {clock_port} 2.0 [all_inputs]
    set_output_delay -clock {clock_port} 2.0 [all_outputs]
    set_load 0.05 [all_outputs]

    # 单次初始反标提取时序与活跃度 (基准 0.05 pF 片上连线)
    read_vcd -scope tb_top/u_dut {str(vcd_out)}
    report_checks -path_delay max -fields {{slew cap input nets fanout}} -format full_clock_expanded -digits 4 > {str(timing_rpt)}
    report_worst_slack -max
    report_worst_slack -min
    report_tns
    report_activity_annotation -report_annotated > {str(activity_ann_rpt)}

    # 电容敏感度单调递增扫描 (0.05 pF ~ 15.0 pF)
    foreach cap {{0.05 0.2 0.5 1.0 2.0 5.0 10.0 15.0}} {{
        catch {{set_load $cap [get_ports pad_*]}}
        read_vcd -scope tb_top/u_dut {str(vcd_out)}
        report_power > "{str(reports_dir / f'sta_power_{sim_tag}_cap')}${{cap}}.rpt"
    }}
    exit
    """
    sta_cmd_path = reports_dir / f"calc_signoff_{sim_tag}.tcl"
    sta_cmd_path.write_text(sta_script, encoding="utf-8")

    sta_log = log_dir / f"sta_signoff_{sim_tag}.log"
    run_command_with_logging(["sta", str(sta_cmd_path)], sta_log, cwd=reports_dir, logger=logger)

    # 4. 解析指标
    cap_pwr_map: Dict[str, Any] = {}
    for cap_v in [0.05, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0]:
        cap_rpt = reports_dir / f"sta_power_{sim_tag}_cap{cap_v}.rpt"
        cap_pwr_map[str(cap_v)] = parse_power_rpt_file(cap_rpt)

    pwr_metrics = cap_pwr_map.get("10.0", {})
    # 拷贝 10.0 pF 标称报告至主 power_rpt 方便查阅
    nom_cap_rpt = reports_dir / f"sta_power_{sim_tag}_cap10.0.rpt"
    if nom_cap_rpt.exists():
        power_rpt.write_text(nom_cap_rpt.read_text(encoding="utf-8"), encoding="utf-8")

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
    }
    if activity_ann_rpt.exists():
        for line in activity_ann_rpt.read_text(encoding="utf-8").splitlines():
            line_s = line.strip()
            if line_s.startswith("vcd"):
                parts = line_s.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    activity_metrics["Annotated_Pins"] = int(parts[1])

    return pwr_metrics, timing_metrics, area_metrics, activity_metrics, cap_pwr_map


def run_bus_invert_sweep(
    workspace_dir: Path,
    pdk_root_arg: Optional[str] = None,
    width_list: Optional[List[int]] = None,
    toggle_rates: Optional[List[int]] = None,
    force_pnr: bool = False,
):
    if width_list is None:
        width_list = [8, 16, 32, 64]
    if toggle_rates is None:
        toggle_rates = [15, 35, 60, 85]

    project_root = Path(__file__).resolve().parent.parent.parent
    cases_dir = project_root / "cases" / "bus_invert"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    log_dir = workspace_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_sweep_logger(log_dir)

    logger.info("=" * 80)
    logger.info("      Sky130 Bus-Invert Coding (BI) Multi-Dimensional Signoff Sweep")
    logger.info("=" * 80)
    logger.info(f"[*] Target Bus Widths:         {width_list}")
    logger.info(f"[*] Target Toggle Rates (%):   {toggle_rates}")
    logger.info(f"[*] Workspace Directory:       {workspace_dir}")

    # 1. 定位 PDK
    pdk_root = Path(pdk_root_arg).expanduser().resolve() if pdk_root_arg else Path.home() / ".ciel"
    lib_path, verilog_lib_path, prims_path, blackbox_path = locate_pdk_files(pdk_root)
    logger.info(f"[*] PDK Root: {pdk_root}")
    logger.info(f"[*] Liberty:  {lib_path}")

    sweep_results: Dict[str, Any] = {}

    # 2. 遍历各总线位宽规模
    for width in width_list:
        case_name = f"bus_{width}b"
        case_dir = cases_dir / case_name
        if not case_dir.exists():
            logger.warning(f"Case directory {case_dir} not found! Skipping...")
            continue

        logger.info("\n" + "#" * 80)
        logger.info(f"### Processing Scale: {width}-bit Bus ({case_name})")
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

        # Step 1: Formal LEC (基于端到端 Miter 与 SAT 归纳证明)
        run_formal_lec(sources_orig, sources_opt, top, formal_dir, case_log_dir, logger, bus_invert=True)
        run_formal_lec(sources_orig, sources_opt, top, formal_dir, case_log_dir, logger, bus_invert=True, bus_invert_width=width)

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
            "toggle_rates": {},
            "pnr_metrics": {},
        }

        # Step 3 & 4: 针对不同输入数据翻转率运行门级后仿与 OpenSTA 签核
        for tr in toggle_rates:
            logger.info(f"\n>>> Running Signoff Sweep for [{width}b] with Toggle Rate = {tr}%")

            # 评估 Orig
            pwr_orig, tmg_orig, area_orig, act_orig, cap_orig = run_activity_sim_and_sta(
                case_name, width, tr, "orig", top, clock_port, clock_period,
                netlist_orig, spef_orig, tb_path, prims_path, verilog_lib_path,
                lib_path, blackbox_path, metrics_orig, sim_dir, reports_dir, case_log_dir, logger
            )

            # 评估 Opt
            pwr_opt, tmg_opt, area_opt, act_opt, cap_opt = run_activity_sim_and_sta(
                case_name, width, tr, "opt", top, clock_port, clock_period,
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

            sw_orig = parse_val(pwr_orig.get("Switching", "0"))
            sw_opt = parse_val(pwr_opt.get("Switching", "0"))
            sw_delta_pct = ((sw_opt - sw_orig) / sw_orig * 100.0) if sw_orig > 0 else 0.0

            int_orig = parse_val(pwr_orig.get("Internal", "0"))
            int_opt = parse_val(pwr_opt.get("Internal", "0"))

            # 计算电容敏感度与黄金损益平衡点 (Breakeven Capacitance)
            cap_sweep_dict = {}
            breakeven_cap = None
            prev_cap = None
            prev_delta = None
            for cap_val in [0.05, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0]:
                p_c_orig = parse_val(cap_orig.get(str(cap_val), {}).get("Total", "0"))
                p_c_opt = parse_val(cap_opt.get(str(cap_val), {}).get("Total", "0"))
                delta_c = ((p_c_opt - p_c_orig) / p_c_orig * 100.0) if p_c_orig > 0 else 0.0
                sw_c_orig = parse_val(cap_orig.get(str(cap_val), {}).get("Switching", "0"))
                sw_c_opt = parse_val(cap_opt.get(str(cap_val), {}).get("Switching", "0"))

                cap_sweep_dict[str(cap_val)] = {
                    "cap_pf": cap_val,
                    "orig_total_power_uW": round(p_c_orig * 1e6, 3),
                    "opt_total_power_uW": round(p_c_opt * 1e6, 3),
                    "power_delta_pct": round(delta_c, 2),
                    "orig_switching_power_uW": round(sw_c_orig * 1e6, 3),
                    "opt_switching_power_uW": round(sw_c_opt * 1e6, 3),
                }

                if prev_delta is not None and breakeven_cap is None:
                    if prev_delta > 0 and delta_c <= 0:
                        fraction = (0.0 - prev_delta) / (delta_c - prev_delta)
                        breakeven_cap = round(prev_cap + fraction * (cap_val - prev_cap), 3)
                    elif prev_delta <= 0 and delta_c > 0:
                        fraction = (0.0 - prev_delta) / (delta_c - prev_delta)
                        breakeven_cap = round(prev_cap + fraction * (cap_val - prev_cap), 3)
                prev_cap = cap_val
                prev_delta = delta_c

            if breakeven_cap is None:
                first_delta = cap_sweep_dict["0.05"]["power_delta_pct"]
                if first_delta <= 0:
                    breakeven_cap = "<= 0.05"
                else:
                    breakeven_cap = "> 15.0"

            sweep_results[f"{width}b"]["toggle_rates"][str(tr)] = {
                "orig_total_power_uW": round(p_orig * 1e6, 3),
                "opt_total_power_uW": round(p_opt * 1e6, 3),
                "power_delta_pct": round(p_delta_pct, 2),
                "orig_switching_power_uW": round(sw_orig * 1e6, 3),
                "opt_switching_power_uW": round(sw_opt * 1e6, 3),
                "switching_delta_pct": round(sw_delta_pct, 2),
                "orig_clock_power_uW": round(clk_orig * 1e6, 3),
                "opt_clock_power_uW": round(clk_opt * 1e6, 3),
                "orig_sequential_power_uW": round(seq_orig * 1e6, 3),
                "opt_sequential_power_uW": round(seq_opt * 1e6, 3),
                "orig_combinational_power_uW": round(comb_orig * 1e6, 3),
                "opt_combinational_power_uW": round(comb_opt * 1e6, 3),
                "orig_internal_power_uW": round(int_orig * 1e6, 3),
                "opt_internal_power_uW": round(int_opt * 1e6, 3),
                "orig_setup_ws_ns": tmg_orig.get("Setup_WS_ns", "N/A"),
                "opt_setup_ws_ns": tmg_opt.get("Setup_WS_ns", "N/A"),
                "orig_critical_path_delay_ns": tmg_orig.get("Critical_Path_Delay_ns", "N/A"),
                "opt_critical_path_delay_ns": tmg_opt.get("Critical_Path_Delay_ns", "N/A"),
                "cap_sweep": cap_sweep_dict,
                "breakeven_cap_pf": breakeven_cap,
            }

            logger.info(
                f"[{width}b | ToggleRate={tr}%] Orig: {round(p_orig*1e6, 2)} uW -> Opt: {round(p_opt*1e6, 2)} uW "
                f"| Delta: {round(p_delta_pct, 2)}% | Switching: {round(sw_orig*1e6, 2)}uW -> {round(sw_opt*1e6, 2)}uW ({round(sw_delta_pct, 1)}%)"
                f"| Delta: {round(p_delta_pct, 2)}% | Breakeven Cap: {breakeven_cap} pF"
            )

        # 记录通用物理指标
        sweep_results[f"{width}b"]["pnr_metrics"] = {
            "orig_stdcell_count": area_orig.get("Stdcell_Count", "N/A"),
            "opt_stdcell_count": area_opt.get("Stdcell_Count", "N/A"),
            "orig_stdcell_area_um2": area_orig.get("Stdcell_Area_um2", "N/A"),
            "opt_stdcell_area_um2": area_opt.get("Stdcell_Area_um2", "N/A"),
            "orig_dff_count": area_orig.get("DFF_Count", 2 * width),
            "opt_dff_count": area_opt.get("DFF_Count", 2 * width + 1),
        }

    # 3. 结构化导出结果
    results_json = workspace_dir / "sweep_results.json"
    results_json.write_text(json.dumps(sweep_results, indent=2), encoding="utf-8")
    logger.info(f"\n[DONE] Sweep results successfully saved to: {results_json}")

    return sweep_results
