#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 4: 签核级功耗、时序、物理面积与翻转活动度多维分析 (Signoff Analysis via OpenSTA)
"""

import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from src.common.env import run_command_with_logging


def run_signoff_evaluation(
    run_tag: str,
    top: str,
    clock_port: str,
    clock_period: float,
    netlist: Path,
    spef: Path,
    vcd: Path,
    metrics_json_path: Optional[Path],
    lib_path: Path,
    blackbox_path: Path,
    reports_dir: Path,
    log_dir: Path,
    logger: logging.Logger,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    配置并执行 OpenSTA 签核分析，反标寄生参数 SPEF 与仿真波形 VCD，
    输出高精度功耗报表、建立时间最坏路径时序报表、物理面积报表与引脚翻转活动度报表。
    """
    logger.info("=" * 70)
    logger.info(f">>> Step 4: Multi-Dimensional Signoff Analysis [{run_tag}] (Power, Timing, Area, Activity)")
    logger.info("=" * 70)

    power_rpt = reports_dir / f"{run_tag}_power.rpt"
    timing_rpt = reports_dir / f"{run_tag}_timing.rpt"
    area_rpt = reports_dir / f"{run_tag}_area.rpt"
    activity_rpt = reports_dir / f"{run_tag}_activity.rpt"
    activity_ann_rpt = reports_dir / f"{run_tag}_activity_annotation.rpt"

    sta_script = f"""
    read_liberty {lib_path}
    read_verilog {blackbox_path}
    read_verilog {netlist}
    link_design {top}
    read_spef {spef}
    create_clock -name {clock_port} -period {clock_period} [get_ports {clock_port}]

    read_vcd -scope tb_top/u_dut {vcd}
    report_power > {power_rpt}

    report_checks -path_delay max -format full_clock_expanded -digits 3 > {timing_rpt}
    report_worst_slack -max
    report_worst_slack -min
    report_tns

    report_activity_annotation -report_annotated > {activity_ann_rpt}

    # 导出详细信号与引脚翻转活动度报告
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
    sta_cmd_path = reports_dir / f"calc_signoff_{run_tag}.tcl"
    sta_cmd_path.write_text(sta_script, encoding="utf-8")

    sta_log = log_dir / f"sta_signoff_{run_tag}.log"
    run_command_with_logging(["sta", str(sta_cmd_path)], sta_log, cwd=reports_dir, logger=logger)

    # 1. 解析功耗指标
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

    # 2. 解析时序指标 (结合 OpenSTA 与 LibreLane metrics.json)
    timing_metrics: Dict[str, Any] = {
        "Clock_Period_ns": clock_period,
        "Setup_WS_ns": "N/A",
        "Setup_WNS_ns": 0.0,
        "Setup_TNS_ns": 0.0,
        "Hold_WS_ns": "N/A",
        "Critical_Path_Delay_ns": "N/A",
        "Fmax_MHz": "N/A",
    }

    if timing_rpt.exists():
        t_text = timing_rpt.read_text(encoding="utf-8")
        for line in t_text.splitlines():
            if "data arrival time" in line:
                m = re.search(r"([\d\.\-]+)\s+data arrival time", line)
                if m:
                    timing_metrics["Critical_Path_Delay_ns"] = float(m.group(1))
            if "slack (MET)" in line or "slack (VIOLATED)" in line:
                m = re.search(r"([\d\.\-]+)\s+slack", line)
                if m:
                    timing_metrics["Setup_WS_ns"] = float(m.group(1))

    # 3. 解析物理面积与布线复杂度 (从 LibreLane metrics.json 提取)
    area_metrics: Dict[str, Any] = {
        "Stdcell_Count": "N/A",
        "Stdcell_Area_um2": "N/A",
        "Sequential_Cell_Count": "N/A",
        "Sequential_Cell_Area_um2": "N/A",
        "Combinational_Cell_Count": "N/A",
        "Combinational_Cell_Area_um2": "N/A",
        "Core_Area_um2": "N/A",
        "Die_Area_um2": "N/A",
        "Utilization_pct": "N/A",
        "Routed_Wirelength_um": "N/A",
        "Routed_Vias": "N/A",
    }

    if metrics_json_path and metrics_json_path.exists():
        try:
            m_data = json.loads(metrics_json_path.read_text(encoding="utf-8"))
            area_metrics["Stdcell_Count"] = m_data.get("design__instance__count__stdcell", "N/A")
            area_metrics["Stdcell_Area_um2"] = m_data.get("design__instance__area__stdcell", "N/A")
            area_metrics["Sequential_Cell_Count"] = m_data.get("design__instance__count__class:sequential_cell", "N/A")
            area_metrics["Sequential_Cell_Area_um2"] = m_data.get("design__instance__area__class:sequential_cell", "N/A")
            area_metrics["Combinational_Cell_Count"] = m_data.get("design__instance__count__class:multi_input_combinational_cell", "N/A")
            area_metrics["Combinational_Cell_Area_um2"] = m_data.get("design__instance__area__class:multi_input_combinational_cell", "N/A")
            area_metrics["Core_Area_um2"] = m_data.get("design__core__area", "N/A")
            area_metrics["Die_Area_um2"] = m_data.get("design__die__area", "N/A")
            util = m_data.get("design__instance__utilization__stdcell")
            if util is not None:
                area_metrics["Utilization_pct"] = round(float(util) * 100.0, 2)
            area_metrics["Routed_Wirelength_um"] = m_data.get("route__wirelength", "N/A")
            area_metrics["Routed_Vias"] = m_data.get("route__vias", "N/A")

            if m_data.get("timing__setup__ws") is not None:
                timing_metrics["Setup_WS_ns"] = round(float(m_data["timing__setup__ws"]), 3)
            if m_data.get("timing__setup__wns") is not None:
                timing_metrics["Setup_WNS_ns"] = round(float(m_data["timing__setup__wns"]), 3)
            if m_data.get("timing__setup__tns") is not None:
                timing_metrics["Setup_TNS_ns"] = round(float(m_data["timing__setup__tns"]), 3)
            if m_data.get("timing__hold__ws") is not None:
                timing_metrics["Hold_WS_ns"] = round(float(m_data["timing__hold__ws"]), 3)
        except Exception as e:
            logger.warning(f"Error parsing metrics.json: {e}")

    try:
        ws_val = float(timing_metrics["Setup_WS_ns"])
        crit_delay = clock_period - ws_val
        timing_metrics["Critical_Path_Delay_ns"] = round(crit_delay, 3)
        if crit_delay > 0:
            timing_metrics["Fmax_MHz"] = round(1000.0 / crit_delay, 2)
    except (ValueError, TypeError):
        pass

    area_report_content = f"""===============================================================================
Physical Area & Complexity Report: [{run_tag}] (Design: {top})
===============================================================================
Standard Cell Instances:     {area_metrics['Stdcell_Count']}
Total Standard Cell Area:    {area_metrics['Stdcell_Area_um2']} um^2
  - Sequential Cells:        {area_metrics['Sequential_Cell_Count']} ({area_metrics['Sequential_Cell_Area_um2']} um^2)
  - Combinational Cells:     {area_metrics['Combinational_Cell_Count']} ({area_metrics['Combinational_Cell_Area_um2']} um^2)
Core Area:                   {area_metrics['Core_Area_um2']} um^2
Die Area:                    {area_metrics['Die_Area_um2']} um^2
Placement Utilization:       {area_metrics['Utilization_pct']} %
Total Routed Wirelength:     {area_metrics['Routed_Wirelength_um']} um
Total Routed Vias:           {area_metrics['Routed_Vias']}
===============================================================================
"""
    area_rpt.write_text(area_report_content, encoding="utf-8")

    # 4. 解析信号与引脚翻转活动度指标
    activity_metrics: Dict[str, Any] = {
        "Annotated_Pins": "N/A",
        "Unannotated_Pins": "N/A",
        "Clock_Transition_Density": "N/A",
        "Enable_Static_Probability": "N/A",
        "Avg_Data_In_Transition_Density": "N/A",
        "Avg_Data_Out_Transition_Density": "N/A",
    }
    if activity_ann_rpt.exists():
        ann_text = activity_ann_rpt.read_text(encoding="utf-8")
        for line in ann_text.splitlines():
            line_s = line.strip()
            if line_s.startswith("vcd") or line_s.startswith("saif"):
                parts = line_s.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    activity_metrics["Annotated_Pins"] = int(parts[1])
            elif line_s.startswith("unannotated"):
                parts = line_s.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    activity_metrics["Unannotated_Pins"] = int(parts[1])

    if activity_rpt.exists():
        act_text = activity_rpt.read_text(encoding="utf-8")
        din_densities = []
        dout_densities = []
        for line in act_text.splitlines():
            if "|" not in line or "Pin/Port Name" in line or "---" in line:
                continue
            cols = [c.strip() for c in line.split("|")]
            if len(cols) >= 5:
                pname = cols[0]
                try:
                    tdens = float(cols[2])
                    sprob = float(cols[3])
                except ValueError:
                    continue
                if pname == clock_port:
                    activity_metrics["Clock_Transition_Density"] = tdens
                elif pname == "en" or pname.endswith("/en"):
                    activity_metrics["Enable_Static_Probability"] = sprob
                elif "data_in" in pname or "din" in pname:
                    din_densities.append(tdens)
                elif "data_out" in pname or "dout" in pname:
                    dout_densities.append(tdens)
        if din_densities:
            activity_metrics["Avg_Data_In_Transition_Density"] = round(sum(din_densities) / len(din_densities), 4)
        if dout_densities:
            activity_metrics["Avg_Data_Out_Transition_Density"] = round(sum(dout_densities) / len(dout_densities), 4)

    logger.info(f"[*] Signoff Power Report:    {power_rpt}")
    logger.info(f"[*] Signoff Timing Report:   {timing_rpt}")
    logger.info(f"[*] Signoff Area Report:     {area_rpt}")
    logger.info(f"[*] Signoff Activity Report: {activity_rpt}")

    return pwr_metrics, timing_metrics, area_metrics, activity_metrics

