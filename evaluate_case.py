#!/usr/bin/env python3
"""
===============================================================================
通用多文件 RTL 变换自动化评估基座（Evaluation Platform）
-------------------------------------------------------------------------------
执行流水线：
  Step 1: 形式逻辑等价性验证 (Formal Logic Equivalence Checking via Yosys SAT)
  Step 2: 物理实现全流程 (Physical Implementation via LibreLane 80-Stage)
  Step 3: 测试平台门级仿真与翻转波形转储 (Simulation & Activity via Icarus Verilog)
  Step 4: 签核级寄生功耗分析 (Signoff Power Evaluation via OpenSTA + SPEF)
  Step 5: 最终指标对比表格生成与多维度报告输出
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
from typing import Dict, List, Optional, Tuple

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

    # 寻找 candidate AppImage 路径
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

    # 通过 AppImage 启动 python 重新调用
    sys.stderr.write(
        f"[INFO] EDA tools not directly in PATH. Re-executing inside devshell AppImage:\n"
        f"       {appimage_path} python3 {' '.join(sys.argv)}\n\n"
    )
    cmd = [str(appimage_path), "python3"] + sys.argv
    res = subprocess.call(cmd)
    sys.exit(res)


# -----------------------------------------------------------------------------
# 日志系统配置
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
    # 优先支持 ~/.ciel 根目录层级版本自适应
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

    # 自动遍历或读取指定的源文件集合
    def resolve_sources(src_dir: Path, source_list: Optional[List[str]]) -> List[Path]:
        if source_list and len(source_list) > 0:
            resolved = []
            for s in source_list:
                f = src_dir / s
                if not f.exists():
                    raise FileNotFoundError(f"Declared source file not found: {f}")
                resolved.append(f.resolve())
            return resolved
        # 若 sources 为空，自动收集目录下所有 *.v 和 *.sv
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
def run_formal_lec(sources_orig: List[Path], sources_opt: List[Path], top: str, workspace: Path, log_dir: Path, logger: logging.Logger):
    logger.info("=" * 70)
    logger.info(">>> Step 1: Formal Logic Equivalence Checking (Yosys SAT)")
    logger.info("=" * 70)

    orig_files_str = " ".join(f'"{str(p)}"' for p in sources_orig)
    opt_files_str = " ".join(f'"{str(p)}"' for p in sources_opt)

    # 关键机制：通过 design -save / design -reset / design -copy-from
    # 彻底杜绝多文件同名子模块 (Re-definition of module) 冲突
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
    script_path = workspace / "lec.ys"
    script_path.write_text(lec_script, encoding="utf-8")
    lec_log = log_dir / "yosys_lec.log"

    try:
        run_command_with_logging(["yosys", "-q", "-s", str(script_path)], lec_log, cwd=workspace, logger=logger)
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
) -> Tuple[Path, Path]:
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

    # 动态 SDC 注入：消除 OpenROAD fallback SDC 警告
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

    # LibreLane 配置契约与避坑准则
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

        # 显式 SDC 消除 OpenROAD 告警
        "PNR_SDC_FILE": str(sdc_file),
        "SIGNOFF_SDC_FILE": str(sdc_file),

        # 保持完整 80-Stage 流水线，严禁跳过 Magic 导致下游断链
        "RUN_KLAYOUT_STREAMOUT": True,
        "RUN_MAGIC_STREAMOUT": True,

        # 关闭耗时物理检查以提速
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

    # 1. 纯逻辑网表提取（必须为 final/nl/<top>.nl.v，严禁提取含电源引脚的 final/pnl/）
    netlist = final_dir / "nl" / f"{top}.nl.v"
    if not netlist.exists():
        fallback_nl = list(final_dir.glob(f"nl/**/{top}*.nl.v")) or list(final_dir.glob(f"**/{top}*.nl.v"))
        fallback_nl = [f for f in fallback_nl if ".pnl." not in f.name]
        if fallback_nl:
            netlist = fallback_nl[0]
        else:
            raise FileNotFoundError(f"Cannot find logic netlist (*.nl.v) in {final_dir}")

    # 2. 寄生参数 SPEF 提取
    spef = final_dir / "spef" / "nom" / f"{top}.nom.spef"
    if not spef.exists():
        fallback_spef = list(final_dir.glob(f"spef/**/{top}*.spef")) or list(final_dir.glob(f"**/{top}*.spef"))
        if fallback_spef:
            spef = fallback_spef[0]
        else:
            raise FileNotFoundError(f"Cannot find parasitic SPEF file in {final_dir}")

    logger.info(f"[*] Post-PnR Logic Netlist: {netlist}")
    logger.info(f"[*] Post-PnR SPEF:          {spef}")

    return netlist, spef


# -----------------------------------------------------------------------------
# Step 3: 测试平台门级仿真与翻转活跃度转储 (Simulation & VCD Generation)
# -----------------------------------------------------------------------------
def generate_vcd_activity(
    run_tag: str,
    netlist: Path,
    tb_path: Path,
    prims_path: Path,
    verilog_lib_path: Path,
    workspace: Path,
    log_dir: Path,
    logger: logging.Logger,
) -> Path:
    logger.info("=" * 70)
    logger.info(f">>> Step 3: Simulation & Activity Profile Extraction [{run_tag}]")
    logger.info("=" * 70)

    vvp_path = workspace / f"sim_{run_tag}.vvp"
    vcd_path = workspace / f"{run_tag}_activity.vcd"

    # iverilog 编译：参数严格仅传 -g2012 -DFUNCTIONAL，切勿传入 -DUNIT_DELAY
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
    run_command_with_logging(compile_cmd, compile_log, cwd=workspace, logger=logger)

    # 仿真执行：通过 plusargs 传入 VCD_FILE
    run_cmd = ["vvp", str(vvp_path), f"+VCD_FILE={vcd_path}"]
    run_log = log_dir / f"sim_{run_tag}_exec.log"
    run_command_with_logging(run_cmd, run_log, cwd=workspace, logger=logger)

    # 若测试平台使用了固定 activity.vcd，则进行重命名对齐
    if not vcd_path.exists():
        for fallback_vcd_name in ["activity.vcd", f"{run_tag}.vcd"]:
            cand = workspace / fallback_vcd_name
            if cand.exists():
                cand.rename(vcd_path)
                break

    if not vcd_path.exists() or vcd_path.stat().st_size == 0:
        raise RuntimeError(f"Simulation failed to generate non-empty VCD file at: {vcd_path}")

    logger.info(f"[*] Generated Activity VCD: {vcd_path} ({vcd_path.stat().st_size} bytes)")
    return vcd_path


# -----------------------------------------------------------------------------
# Step 4: 签核级寄生功耗分析 (Signoff Power Evaluation via OpenSTA)
# -----------------------------------------------------------------------------
def run_power_signoff(
    run_tag: str,
    top: str,
    clock_port: str,
    clock_period: float,
    netlist: Path,
    spef: Path,
    vcd: Path,
    lib_path: Path,
    blackbox_path: Path,
    workspace: Path,
    log_dir: Path,
    logger: logging.Logger,
) -> Dict[str, str]:
    logger.info("=" * 70)
    logger.info(f">>> Step 4: OpenSTA Signoff Power Evaluation [{run_tag}]")
    logger.info("=" * 70)

    report_file = workspace / f"{run_tag}_power.rpt"

    # OpenSTA 签核脚本：预载 blackbox，以标准斜杠路径反标 tb_top/u_dut
    sta_script = f"""
    read_liberty {lib_path}
    read_verilog {blackbox_path}
    read_verilog {netlist}
    link_design {top}
    read_spef {spef}
    create_clock -name {clock_port} -period {clock_period} [get_ports {clock_port}]

    read_vcd -scope tb_top/u_dut {vcd}
    report_power > {report_file}
    exit
    """
    sta_cmd_path = workspace / f"calc_pwr_{run_tag}.tcl"
    sta_cmd_path.write_text(sta_script, encoding="utf-8")

    sta_log = log_dir / f"sta_power_{run_tag}.log"
    run_command_with_logging(["sta", str(sta_cmd_path)], sta_log, cwd=workspace, logger=logger)

    if not report_file.exists():
        raise FileNotFoundError(f"OpenSTA failed to write power report to: {report_file}")

    text = report_file.read_text(encoding="utf-8")
    pwr_metrics = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Total") and any(unit in line for unit in ["W", "mW", "uW", "pW", "e-"]):
            parts = stripped.split()
            if len(parts) >= 5:
                pwr_metrics["Internal"] = parts[1]
                pwr_metrics["Switching"] = parts[2]
                pwr_metrics["Leakage"] = parts[3]
                pwr_metrics["Total"] = parts[4]
                break

    # 检查反标日志，提示用户引脚翻转情况
    sta_log_text = sta_log.read_text(encoding="utf-8", errors="ignore")
    if "0 transition" in sta_log_text or "0 pin" in sta_log_text:
        logger.warning(f"[{run_tag}] Potential low activity warning in OpenSTA VCD back-annotation. Inspect {sta_log}")

    return pwr_metrics


# -----------------------------------------------------------------------------
# Step 5: 最终报告与对比分析
# -----------------------------------------------------------------------------
def format_summary_table(results: Dict[str, Dict[str, str]]) -> str:
    categories = ["Internal", "Switching", "Leakage", "Total"]
    orig_res = results.get("orig", {})
    opt_res = results.get("opt", {})

    lines = []
    lines.append("\n" + "=" * 78)
    lines.append(f"{'Power Metric':<16} | {'Original RTL':<16} | {'Optimized RTL':<16} | {'Delta (%)':<16}")
    lines.append("-" * 78)

    for cat in categories:
        val_orig_raw = orig_res.get(cat, "N/A")
        val_opt_raw = opt_res.get(cat, "N/A")

        delta_str = "N/A"
        try:
            val_o = float(val_orig_raw)
            val_m = float(val_opt_raw)
            if val_o > 0:
                pct = ((val_m - val_o) / val_o) * 100.0
                sign = "+" if pct > 0 else ""
                delta_str = f"{sign}{pct:.2f}%"
        except (ValueError, TypeError):
            pass

        v_o = f"{val_orig_raw} W" if val_orig_raw != "N/A" else "N/A"
        v_m = f"{val_opt_raw} W" if val_opt_raw != "N/A" else "N/A"
        lines.append(f"{cat:<16} | {v_o:<16} | {v_m:<16} | {delta_str:<16}")

    lines.append("=" * 78)
    return "\n".join(lines)


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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = workspace / "logs" / timestamp
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(log_dir)
    logger.info("Evaluation Platform initialized.")
    logger.info(f"Target Case: {case_dir}")
    logger.info(f"Workspace:   {workspace}")
    logger.info(f"Session Log: {log_dir / 'overall_pipeline.log'}")

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
    run_formal_lec(sources_orig, sources_opt, top_module, workspace, log_dir, logger)

    # 5. Step 2 ~ Step 4: 物理实现与功耗签核
    run_configs = {
        "orig": sources_orig,
        "opt": sources_opt,
    }
    results = {}

    for tag, srcs in run_configs.items():
        # Step 2: 物理实现
        netlist, spef = run_pnr_flow(
            tag, srcs, meta, pdk_root_base, args.pdk, args.scl, workspace, log_dir, logger
        )

        # Step 3: 仿真活跃度提取
        vcd = generate_vcd_activity(
            tag, netlist, tb_path, prims_path, verilog_lib_path, workspace, log_dir, logger
        )

        # Step 4: 功耗精确签核
        results[tag] = run_power_signoff(
            tag, top_module, clock_port, clock_period, netlist, spef, vcd, lib_path, blackbox_path, workspace, log_dir, logger
        )

    # 6. Step 5: 输出四维对比表格与持久化
    summary_text = format_summary_table(results)
    logger.info(summary_text)

    # 保存 JSON 与 Markdown 格式汇总
    summary_json = log_dir / "power_summary.json"
    summary_json.write_text(json.dumps(results, indent=2), encoding="utf-8")

    summary_md = log_dir / "power_summary.md"
    summary_md.write_text(summary_text, encoding="utf-8")

    logger.info(f"Evaluation pipeline completed successfully.")
    logger.info(f"Artifacts and full diagnostic logs preserved in: {log_dir}")


if __name__ == "__main__":
    main()

