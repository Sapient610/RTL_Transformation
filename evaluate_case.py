#!/usr/bin/env python3
"""
===============================================================================
通用多文件 RTL 变换自动化评估基座（Evaluation Platform）
-------------------------------------------------------------------------------
执行流水线：
  Step 1: 形式逻辑等价性验证 (Formal LEC via Yosys SAT)
  Step 2: 物理实现全流程 (Physical Implementation via LibreLane 80-Stage)
  Step 3: 测试平台门级仿真与翻转活跃度转储 (Simulation & Activity via Icarus Verilog)
  Step 4: 签核级功耗、时序与物理面积多维分析 (Signoff Power, Timing & Area via OpenSTA + LibreLane)
  Step 5: 综合 PPA 指标对比与 Trade-off 关系深度分析报告生成
===============================================================================
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------------------------------------------------------
# 环境兼容自适应引导：优先通过 AppImage devshell 启动
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# 日志系统配置与工作空间清理
# -----------------------------------------------------------------------------
def setup_logging(log_dir: Path) -> logging.Logger:
    logger = logging.getLogger("evaluation_platform")
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
    清理或迁移先前版本散落在 workspace 根目录的旧临时文件，保持工作空间目录整洁。
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


def run_command_with_logging(cmd: List[str], log_file: Path, cwd: Optional[Path] = None, logger: Optional[logging.Logger] = None):
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


# -----------------------------------------------------------------------------
# PDK 基准库与模型定位
# -----------------------------------------------------------------------------
def locate_pdk_files(pdk_root: Path, pdk_name="sky130A", scl_name="sky130_fd_sc_hd") -> Tuple[Path, Path, Path, Path]:
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


# -----------------------------------------------------------------------------
# 用例目录扫描与元数据加载
# -----------------------------------------------------------------------------
def load_and_validate_case(case_dir: Path, logger: logging.Logger) -> Tuple[dict, List[Path], List[Path], Path]:
    meta_path = case_dir / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing metadata configuration file: {meta_path}")

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in {meta_path}: {e}")

    top_name = meta.get("design_name")
    if not top_name:
        raise ValueError(f"'design_name' must be specified in {meta_path}")

    src_orig_dir = case_dir / "src_orig"
    src_opt_dir = case_dir / "src_opt"
    tb_path = case_dir / "tb" / "tb_top.v"

    if not src_orig_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src_orig_dir}")
    if not src_opt_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src_opt_dir}")
    if not tb_path.exists():
        raise FileNotFoundError(f"Dedicated testbench not found: {tb_path}")

    def resolve_sources(src_dir: Path, source_list: Optional[List[str]]) -> List[Path]:
        if source_list and len(source_list) > 0:
            resolved = []
            for s in source_list:
                f = src_dir / s
                if not f.exists():
                    raise FileNotFoundError(f"Declared source file not found: {f}")
                resolved.append(f.resolve())
            return resolved
        all_sources = sorted(list(src_dir.glob("*.v")) + list(src_dir.glob("*.sv")))
        if not all_sources:
            raise FileNotFoundError(f"No .v or .sv files found in {src_dir}")
        return [p.resolve() for p in all_sources]

    sources_orig = resolve_sources(src_orig_dir, meta.get("sources_orig"))
    sources_opt = resolve_sources(src_opt_dir, meta.get("sources_opt"))

    logger.info(f"Loaded Benchmark Case: {case_dir.name}")
    logger.info(f"  Top Module:       {top_name}")
    logger.info(f"  Orig Sources ({len(sources_orig)}): {[f.name for f in sources_orig]}")
    logger.info(f"  Opt Sources  ({len(sources_opt)}): {[f.name for f in sources_opt]}")
    logger.info(f"  Testbench:        {tb_path}")

    return meta, sources_orig, sources_opt, tb_path.resolve()


# -----------------------------------------------------------------------------
# Step 1: 通用多文件形式等价性验证 (Formal Logic Equivalence Checking via Yosys)
# -----------------------------------------------------------------------------
def run_formal_lec(
    sources_orig: List[Path],
    sources_opt: List[Path],
    top: str,
    formal_dir: Path,
    log_dir: Path,
    logger: logging.Logger,
):
    logger.info("=" * 70)
    logger.info(">>> Step 1: Formal Logic Equivalence Checking (Yosys SAT)")
    logger.info("=" * 70)

    orig_files_str = " ".join(f'"{str(p)}"' for p in sources_orig)
    opt_files_str = " ".join(f'"{str(p)}"' for p in sources_opt)

    lec_script = f"""
    read_verilog -sv {orig_files_str}
    hierarchy -top {top}
    flatten
    rename {top} {top}_orig
    design -save orig_des
    design -reset

    read_verilog -sv {opt_files_str}
    hierarchy -top {top}
    flatten
    rename {top} {top}_opt

    design -copy-from orig_des {top}_orig {top}_orig

    proc
    clk2fflogic

    equiv_make {top}_orig {top}_opt miter
    hierarchy -top miter
    flatten

    equiv_simple
    equiv_induct
    equiv_status -assert
    """
    script_path = formal_dir / "lec.ys"
    script_path.write_text(lec_script, encoding="utf-8")
    lec_log = log_dir / "yosys_lec.log"

    try:
        run_command_with_logging(["yosys", "-q", "-s", str(script_path)], lec_log, cwd=formal_dir, logger=logger)
        logger.info("[PASS] 100% Functional Equivalence Verified by Yosys SAT.")
    except subprocess.CalledProcessError:
        logger.error(f"[FAIL] Functional Equivalence Check Failed! Circuit breaker triggered.")
        logger.error(f"       Inspect detailed SAT diagnostic log at: {lec_log}")
        sys.exit(1)


# -----------------------------------------------------------------------------
# Step 2: 物理实现全流程 (Physical Implementation via LibreLane)
# -----------------------------------------------------------------------------
def run_pnr_flow(
    run_tag: str,
    verilog_sources: List[Path],
    meta: dict,
    pdk_root: Path,
    pdk_name: str,
    scl_name: str,
    workspace: Path,
    log_dir: Path,
    logger: logging.Logger,
) -> Tuple[Path, Path, Path]:
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
        "RUN_POST_CTS_RESIZER_TIMING": False,
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
        "--overwrite"
    ]

    pnr_log = log_dir / f"pnr_{run_tag}.log"
    run_command_with_logging(cmd, pnr_log, cwd=tag_dir, logger=logger)

    run_dir = tag_dir / "runs" / run_tag
    final_dir = run_dir / "final"

    # 1. 纯逻辑网表
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


# -----------------------------------------------------------------------------
# Step 3: 测试平台门级仿真与翻转活跃度转储 (Simulation & VCD Generation)
# -----------------------------------------------------------------------------
def generate_vcd_activity(
    run_tag: str,
    netlist: Path,
    tb_path: Path,
    prims_path: Path,
    verilog_lib_path: Path,
    sim_dir: Path,
    log_dir: Path,
    logger: logging.Logger,
) -> Path:
    logger.info("=" * 70)
    logger.info(f">>> Step 3: Simulation & Activity Profile Extraction [{run_tag}]")
    logger.info("=" * 70)

    vvp_path = sim_dir / f"sim_{run_tag}.vvp"
    vcd_path = sim_dir / f"{run_tag}_activity.vcd"

    compile_cmd = [
        "iverilog",
        "-g2012",
        "-DFUNCTIONAL",
        "-o", str(vvp_path),
        str(prims_path),
        str(verilog_lib_path),
        str(netlist),
        str(tb_path)
    ]

    compile_log = log_dir / f"sim_{run_tag}_compile.log"
    run_command_with_logging(compile_cmd, compile_log, cwd=sim_dir, logger=logger)

    run_cmd = ["vvp", str(vvp_path), f"+VCD_FILE={vcd_path}"]
    run_log = log_dir / f"sim_{run_tag}_exec.log"
    run_command_with_logging(run_cmd, run_log, cwd=sim_dir, logger=logger)

    if not vcd_path.exists():
        for fallback_vcd_name in ["activity.vcd", f"{run_tag}.vcd"]:
            cand = sim_dir / fallback_vcd_name
            if cand.exists():
                cand.rename(vcd_path)
                break

    if not vcd_path.exists() or vcd_path.stat().st_size == 0:
        raise RuntimeError(f"Simulation failed to generate non-empty VCD file at: {vcd_path}")

    logger.info(f"[*] Generated Activity VCD: {vcd_path} ({vcd_path.stat().st_size} bytes)")
    return vcd_path


# -----------------------------------------------------------------------------
# Step 4: 签核级功耗、时序与物理面积多维分析 (Signoff Power, Timing & Area)
# -----------------------------------------------------------------------------
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
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    logger.info("=" * 70)
    logger.info(f">>> Step 4: Multi-Dimensional Signoff Analysis [{run_tag}] (Power, Timing, Area)")
    logger.info("=" * 70)

    power_rpt = reports_dir / f"{run_tag}_power.rpt"
    timing_rpt = reports_dir / f"{run_tag}_timing.rpt"
    area_rpt = reports_dir / f"{run_tag}_area.rpt"

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

    logger.info(f"[*] Signoff Power Report:  {power_rpt}")
    logger.info(f"[*] Signoff Timing Report: {timing_rpt}")
    logger.info(f"[*] Signoff Area Report:   {area_rpt}")

    return pwr_metrics, timing_metrics, area_metrics


# -----------------------------------------------------------------------------
# Step 5: 综合 PPA 报表生成与 Trade-off 关系深度分析
# -----------------------------------------------------------------------------
def generate_ppa_summary_report(
    case_name: str,
    top_module: str,
    all_data: Dict[str, Dict[str, Any]],
    reports_dir: Path,
    log_dir: Path,
    logger: logging.Logger,
) -> str:
    orig = all_data["orig"]
    opt = all_data["opt"]

    orig_pwr = orig["power"]
    opt_pwr = opt["power"]
    orig_time = orig["timing"]
    opt_time = opt["timing"]
    orig_area = orig["area"]
    opt_area = opt["area"]

    def calc_delta(o_val: Any, m_val: Any, is_slack=False) -> Tuple[str, Optional[float]]:
        try:
            o_num = float(o_val)
            m_num = float(m_val)
            if is_slack:
                diff = m_num - o_num
                sign = "+" if diff > 0 else ""
                return f"{sign}{diff:.3f} ns", diff
            if o_num != 0:
                pct = ((m_num - o_num) / abs(o_num)) * 100.0
                sign = "+" if pct > 0 else ""
                return f"{sign}{pct:.2f}%", pct
        except (ValueError, TypeError):
            pass
        return "N/A", None

    pdp_orig_fj, pdp_opt_fj, pdp_delta_str = "N/A", "N/A", "N/A"
    try:
        p_o = float(orig_pwr.get("Total", 0))
        d_o = float(orig_time.get("Critical_Path_Delay_ns", 0))
        p_m = float(opt_pwr.get("Total", 0))
        d_m = float(opt_time.get("Critical_Path_Delay_ns", 0))
        if p_o > 0 and d_o > 0 and p_m > 0 and d_m > 0:
            val_pdp_o = p_o * d_o * 1e6
            val_pdp_m = p_m * d_m * 1e6
            pdp_orig_fj = f"{val_pdp_o:.2f} fJ"
            pdp_opt_fj = f"{val_pdp_m:.2f} fJ"
            pdp_delta_str, _ = calc_delta(val_pdp_o, val_pdp_m)
    except Exception:
        pass

    md_lines = [
        f"# PPA (Power-Performance-Area) 综合评估与设计变换关系分析报告",
        f"\n**被测案例**: `{case_name}` | **顶层模块**: `{top_module}` | **评估时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n",
        "---",
        "## 1. PPA 全维度指标对比总表\n",
        "| 指标大类 (Category) | 详细设计指标 (Metric) | 原始设计 (Original) | 优化设计 (Optimized) | 变化量 (Delta) |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    # Power
    power_rows = [
        ("Total Power (总功耗)", orig_pwr.get("Total", "N/A"), opt_pwr.get("Total", "N/A"), "W", False),
        ("Internal Power (内部功耗)", orig_pwr.get("Internal", "N/A"), opt_pwr.get("Internal", "N/A"), "W", False),
        ("Switching Power (翻转功耗)", orig_pwr.get("Switching", "N/A"), opt_pwr.get("Switching", "N/A"), "W", False),
        ("Leakage Power (静态漏电)", orig_pwr.get("Leakage", "N/A"), opt_pwr.get("Leakage", "N/A"), "W", False),
        ("Combinational Power (组合功耗)", orig_pwr.get("Combinational_Total", "N/A"), opt_pwr.get("Combinational_Total", "N/A"), "W", False),
        ("Sequential Power (时序功耗)", orig_pwr.get("Sequential_Total", "N/A"), opt_pwr.get("Sequential_Total", "N/A"), "W", False),
        ("Clock Power (时钟树功耗)", orig_pwr.get("Clock_Total", "N/A"), opt_pwr.get("Clock_Total", "N/A"), "W", False),
    ]
    for idx, (label, o, m, unit, is_s) in enumerate(power_rows):
        delta_str, _ = calc_delta(o, m, is_s)
        u_o = f"{o} {unit}" if o != "N/A" else "N/A"
        u_m = f"{m} {unit}" if m != "N/A" else "N/A"
        cat_header = "**Power (功耗)**" if idx == 0 else ""
        md_lines.append(f"| {cat_header} | {label} | {u_o} | {u_m} | **{delta_str}** |")

    # Timing
    timing_rows = [
        ("Clock Period (时钟周期)", orig_time.get("Clock_Period_ns", "N/A"), opt_time.get("Clock_Period_ns", "N/A"), "ns", False),
        ("Critical Path Delay (关键路径延迟)", orig_time.get("Critical_Path_Delay_ns", "N/A"), opt_time.get("Critical_Path_Delay_ns", "N/A"), "ns", False),
        ("Setup Worst Slack (建立时间裕量)", orig_time.get("Setup_WS_ns", "N/A"), opt_time.get("Setup_WS_ns", "N/A"), "ns", True),
        ("Setup WNS (最坏违例裕量)", orig_time.get("Setup_WNS_ns", "N/A"), opt_time.get("Setup_WNS_ns", "N/A"), "ns", True),
        ("Setup TNS (总违例累加裕量)", orig_time.get("Setup_TNS_ns", "N/A"), opt_time.get("Setup_TNS_ns", "N/A"), "ns", True),
        ("Fmax (最高理论主频)", orig_time.get("Fmax_MHz", "N/A"), opt_time.get("Fmax_MHz", "N/A"), "MHz", False),
    ]
    for idx, (label, o, m, unit, is_s) in enumerate(timing_rows):
        delta_str, _ = calc_delta(o, m, is_s)
        u_o = f"{o} {unit}" if o != "N/A" else "N/A"
        u_m = f"{m} {unit}" if m != "N/A" else "N/A"
        cat_header = "**Timing (时序/性能)**" if idx == 0 else ""
        md_lines.append(f"| {cat_header} | {label} | {u_o} | {u_m} | **{delta_str}** |")

    # Area
    area_rows = [
        ("Stdcell Count (标准单元总数)", orig_area.get("Stdcell_Count", "N/A"), opt_area.get("Stdcell_Count", "N/A"), "gates", False),
        ("Stdcell Area (标准单元总面积)", orig_area.get("Stdcell_Area_um2", "N/A"), opt_area.get("Stdcell_Area_um2", "N/A"), "um^2", False),
        ("Combinational Area (组合逻辑面积)", orig_area.get("Combinational_Cell_Area_um2", "N/A"), opt_area.get("Combinational_Cell_Area_um2", "N/A"), "um^2", False),
        ("Sequential Area (时序逻辑面积)", orig_area.get("Sequential_Cell_Area_um2", "N/A"), opt_area.get("Sequential_Cell_Area_um2", "N/A"), "um^2", False),
        ("Core Area (核心区域面积)", orig_area.get("Core_Area_um2", "N/A"), opt_area.get("Core_Area_um2", "N/A"), "um^2", False),
        ("Core Placement Density (布局利用率)", orig_area.get("Utilization_pct", "N/A"), opt_area.get("Utilization_pct", "N/A"), "%", False),
        ("Total Routed Wirelength (总走线长)", orig_area.get("Routed_Wirelength_um", "N/A"), opt_area.get("Routed_Wirelength_um", "N/A"), "um", False),
    ]
    for idx, (label, o, m, unit, is_s) in enumerate(area_rows):
        delta_str, _ = calc_delta(o, m, is_s)
        u_o = f"{o} {unit}" if o != "N/A" else "N/A"
        u_m = f"{m} {unit}" if m != "N/A" else "N/A"
        cat_header = "**Area (物理面积)**" if idx == 0 else ""
        md_lines.append(f"| {cat_header} | {label} | {u_o} | {u_m} | **{delta_str}** |")

    # Energy-Delay
    md_lines.append(f"| **Energy (能效指标)** | PDP (功耗延迟积, Power-Delay Product) | {pdp_orig_fj} | {pdp_opt_fj} | **{pdp_delta_str}** |")

    # Trade-off Analysis
    pwr_delta_str, pwr_pct = calc_delta(orig_pwr.get("Total"), opt_pwr.get("Total"))
    area_delta_str, area_pct = calc_delta(orig_area.get("Stdcell_Area_um2"), opt_area.get("Stdcell_Area_um2"))
    slack_delta_str, slack_diff = calc_delta(orig_time.get("Setup_WS_ns"), opt_time.get("Setup_WS_ns"), is_slack=True)

    md_lines.extend([
        "\n---",
        "## 2. 功耗与其他设计指标的变换关系分析 (PPA Trade-off Analysis)\n",
        "### 2.1 功耗与物理面积的代价关系 (Power vs. Area Overhead)",
    ])

    if pwr_pct is not None and area_pct is not None:
        if pwr_pct < 0 and area_pct > 0:
            ratio = abs(area_pct / pwr_pct)
            md_lines.append(
                f"- **面积惩罚代价比**: 本设计变换使总功耗下降了 **{abs(pwr_pct):.2f}%**，"
                f"付出的标准单元面积膨胀代价为 **+{area_pct:.2f}%**（每节省 1% 功耗仅消耗 **{ratio:.2f}%** 面积增量）。"
                f"在现代深亚微米集成电路物理实现中，这属于极为划算且高效的正向优化收益。"
            )
        elif pwr_pct < 0 and area_pct <= 0:
            md_lines.append(
                f"- **双赢收益**: 本设计变换在削减总功耗 **{abs(pwr_pct):.2f}%** 的同时，"
                f"标准单元面积同步缩减了 **{abs(area_pct):.2f}%**，实现了功耗与芯片成本的双重优化。"
            )
        elif pwr_pct > 0:
            md_lines.append(
                f"- **负收益预警 (Overhead Penalty)**: 本设计变换导致总功耗增加了 **+{pwr_pct:.2f}%**。"
                f"由于门控/辅助电路自身消耗的静态漏电、时钟树缓冲器功耗超过了所关断逻辑节省的翻转收益，出现设计开销倒挂现象。"
            )
    else:
        md_lines.append("- 物理面积指标已完整记录于上表。")

    md_lines.extend([
        "\n### 2.2 功耗与时序性能的敏感度关系 (Power vs. Timing Slack)",
    ])

    if slack_diff is not None:
        if slack_diff >= 0:
            md_lines.append(
                f"- **时序保持/改善**: 优化设计在时钟建立时间裕量上相比原始设计变化了 **{slack_delta_str}**。"
                f"说明引入的低功耗控制逻辑并未恶化关键数据路径延迟，甚至因布局优化或关键路径解耦获得了时序收益。"
            )
        else:
            md_lines.append(
                f"- **时序折损 (Timing Cost)**: 优化设计使建立时间裕量下降了 **{slack_delta_str}**。"
                f"表明低功耗逻辑（如操作数隔离与门或门控锁存器）串接在关键时序路径上，引入了额外的门延迟。"
            )
    else:
        md_lines.append("- 时序裕量数据如上表所示。")

    md_lines.extend([
        "\n### 2.3 综合能量效率评估 (Power-Delay Product, PDP)",
        f"- **PDP 变化**: 从 `{pdp_orig_fj}` 变动至 `{pdp_opt_fj}` (**{pdp_delta_str}**)。",
        "- **物理意义**: PDP（功耗延迟积）衡量了电路完成单次逻辑操作所需的能量损耗。PDP 下降代表芯片在全局能量利用效率上获得了本质提升，而非单纯牺牲时钟性能换取低功耗。",
    ])

    summary_text = "\n".join(md_lines)

    (reports_dir / "ppa_summary.md").write_text(summary_text, encoding="utf-8")
    (reports_dir / "ppa_summary.json").write_text(json.dumps(all_data, indent=2), encoding="utf-8")

    (log_dir / "ppa_summary.md").write_text(summary_text, encoding="utf-8")
    (log_dir / "power_summary.md").write_text(summary_text, encoding="utf-8")
    (log_dir / "power_summary.json").write_text(json.dumps(all_data, indent=2), encoding="utf-8")

    console_summary = "\n" + "=" * 80 + "\n"
    console_summary += f"{'PPA Category':<16} | {'Key Metric':<24} | {'Original':<14} | {'Optimized':<14} | {'Delta':<10}\n"
    console_summary += "-" * 80 + "\n"
    console_summary += f"{'Power':<16} | {'Total Power':<24} | {orig_pwr.get('Total', 'N/A'):<14} | {opt_pwr.get('Total', 'N/A'):<14} | {pwr_delta_str:<10}\n"
    console_summary += f"{'Timing':<16} | {'Critical Path Delay':<24} | {str(orig_time.get('Critical_Path_Delay_ns')) + ' ns':<14} | {str(opt_time.get('Critical_Path_Delay_ns')) + ' ns':<14} | {calc_delta(orig_time.get('Critical_Path_Delay_ns'), opt_time.get('Critical_Path_Delay_ns'))[0]:<10}\n"
    console_summary += f"{'Timing':<16} | {'Setup Worst Slack':<24} | {str(orig_time.get('Setup_WS_ns')) + ' ns':<14} | {str(opt_time.get('Setup_WS_ns')) + ' ns':<14} | {slack_delta_str:<10}\n"
    console_summary += f"{'Area':<16} | {'Stdcell Area':<24} | {str(orig_area.get('Stdcell_Area_um2')) + ' um2':<14} | {str(opt_area.get('Stdcell_Area_um2')) + ' um2':<14} | {area_delta_str:<10}\n"
    console_summary += f"{'Energy':<16} | {'Power-Delay Product':<24} | {pdp_orig_fj:<14} | {pdp_opt_fj:<14} | {pdp_delta_str:<10}\n"
    console_summary += "=" * 80 + "\n"

    logger.info(console_summary)
    logger.info(f"Comprehensive PPA summary written to: {reports_dir / 'ppa_summary.md'}")
    return summary_text


# -----------------------------------------------------------------------------
# 主控制入口
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="通用多文件 RTL 变换自动化物理评估基座 (Evaluation Platform)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--case-dir", type=str, required=True, help="待评估案例目录路径 (包含 meta.json, src_orig, src_opt, tb)")
    parser.add_argument("--workspace", type=str, default=None, help="工作空间输出路径 (默认: ./eval_workspace/<case_name>)")
    parser.add_argument("--pdk-root", type=str, default=None, help="PDK 根目录 (默认自适应探测 ~/.ciel 或环境变量 PDK_ROOT)")
    parser.add_argument("--pdk", type=str, default="sky130A", help="目标 PDK 名称")
    parser.add_argument("--scl", type=str, default="sky130_fd_sc_hd", help="目标标准单元库名称")
    parser.add_argument("--devshell", type=str, default=None, help="指定 LibreLane AppImage 路径")

    args = parser.parse_args()

    # 1. 确保 EDA 运行环境就绪
    ensure_devshell_environment(args.devshell)

    case_dir = Path(args.case_dir).resolve()
    if not case_dir.is_dir():
        sys.stderr.write(f"[ERROR] Case directory not found: {case_dir}\n")
        sys.exit(1)

    case_name = case_dir.name
    workspace = Path(args.workspace).resolve() if args.workspace else Path("./eval_workspace").resolve() / case_name
    workspace.mkdir(parents=True, exist_ok=True)

    # 创建清晰解耦的功能子目录
    sim_dir = workspace / "sim"
    reports_dir = workspace / "reports"
    formal_dir = workspace / "formal"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = workspace / "logs" / timestamp

    sim_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    formal_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(log_dir)
    cleanup_legacy_root_files(workspace, logger)

    logger.info("Evaluation Platform initialized with decoupled directory structure.")
    logger.info(f"Target Case:    {case_dir}")
    logger.info(f"Workspace:      {workspace}")
    logger.info(f"  Simulation:   {sim_dir}")
    logger.info(f"  Reports:      {reports_dir}")
    logger.info(f"  Formal (LEC): {formal_dir}")
    logger.info(f"  Session Logs: {log_dir}")

    # 2. 探测并校验 PDK 文件
    pdk_root_base = Path(args.pdk_root).expanduser().resolve() if args.pdk_root else Path(os.environ.get("PDK_ROOT", Path.home() / ".ciel")).resolve()
    lib_path, verilog_lib_path, prims_path, blackbox_path = locate_pdk_files(pdk_root_base, args.pdk, args.scl)
    logger.info(f"PDK environment resolved from: {pdk_root_base}")

    # 3. 解析用例元数据与源文件列表
    meta, sources_orig, sources_opt, tb_path = load_and_validate_case(case_dir, logger)
    top_module = meta["design_name"]
    clock_port = meta.get("clock_port", "clk")
    clock_period = float(meta.get("clock_period_ns", 10.0))

    # 4. Step 1: 形式逻辑等价性验证 (LEC) - 熔断机制
    run_formal_lec(sources_orig, sources_opt, top_module, formal_dir, log_dir, logger)

    # 5. Step 2 ~ Step 4: 物理实现全流程与多维签核评估
    run_configs = {
        "orig": sources_orig,
        "opt": sources_opt,
    }
    all_eval_data: Dict[str, Dict[str, Any]] = {}

    for tag, srcs in run_configs.items():
        # Step 2: 物理实现
        netlist, spef, metrics_json_path = run_pnr_flow(
            tag, srcs, meta, pdk_root_base, args.pdk, args.scl, workspace, log_dir, logger
        )

        # Step 3: 仿真活跃度提取 (输出至 sim/)
        vcd = generate_vcd_activity(
            tag, netlist, tb_path, prims_path, verilog_lib_path, sim_dir, log_dir, logger
        )

        # Step 4: 功耗、时序与物理面积签核分析 (输出至 reports/)
        pwr_m, timing_m, area_m = run_signoff_evaluation(
            tag, top_module, clock_port, clock_period, netlist, spef, vcd, metrics_json_path, lib_path, blackbox_path, reports_dir, log_dir, logger
        )

        all_eval_data[tag] = {
            "power": pwr_m,
            "timing": timing_m,
            "area": area_m,
        }

    # 6. Step 5: 综合 PPA 报告与 Trade-off 关系分析 (输出至 reports/ppa_summary.md)
    generate_ppa_summary_report(
        case_name, top_module, all_eval_data, reports_dir, log_dir, logger
    )

    logger.info("Evaluation pipeline completed successfully.")
    logger.info(f"Artifacts organized in: Simulation -> {sim_dir}, Reports -> {reports_dir}")


if __name__ == "__main__":
    main()
