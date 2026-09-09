import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# -----------------------------------------------------------------------------
# 0. 工作空间、日志系统与 PDK 环境配置
# -----------------------------------------------------------------------------
WORKSPACE = Path("./eval_workspace").resolve()
WORKSPACE.mkdir(exist_ok=True)

# 每次执行创建一个带时间戳的集中日志目录
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR = WORKSPACE / "logs" / TIMESTAMP
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 配置主流程 Python Logger：同时输出至控制台和文件
logger = logging.getLogger("eval_pipeline")
logger.setLevel(logging.INFO)

c_handler = logging.StreamHandler(sys.stdout)
f_handler = logging.FileHandler(LOG_DIR / "overall_pipeline.log", encoding="utf-8")
formatter = logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s", datefmt="%H:%M:%S")
c_handler.setFormatter(formatter)
f_handler.setFormatter(formatter)

logger.addHandler(c_handler)
logger.addHandler(f_handler)

TOP_MODULE = "reg_bank"
ORIG_SRC = Path("./orig.v").resolve()
OPT_SRC = Path("./opt.v").resolve()

# PDK 路径锁定
PDK_ROOT = Path(os.environ.get("PDK_ROOT", Path.home() / ".ciel")).resolve()
PDK_NAME = "sky130A"
SCL_NAME = "sky130_fd_sc_hd"

# 物理仿真与签核所需的基准库定位
def locate_pdk_files(pdk_root: Path):
    ciel_versions = list(pdk_root.glob("ciel/sky130/versions/*"))
    if ciel_versions and (ciel_versions[0] / PDK_NAME).exists():
        real_pdk = ciel_versions[0] / PDK_NAME
    elif (pdk_root / PDK_NAME).exists():
        real_pdk = pdk_root / PDK_NAME
    else:
        raise FileNotFoundError(f"Cannot locate {PDK_NAME} inside {pdk_root}")
    
    lib = real_pdk / "libs.ref" / SCL_NAME / "lib" / f"{SCL_NAME}__tt_025C_1v80.lib"
    verilog = real_pdk / "libs.ref" / SCL_NAME / "verilog" / f"{SCL_NAME}.v"
    prims = real_pdk / "libs.ref" / SCL_NAME / "verilog" / "primitives.v"
    blackbox = real_pdk / "libs.ref" / SCL_NAME / "verilog" / f"{SCL_NAME}__blackbox.v"
    return lib, verilog, prims, blackbox

LIB_PATH, PDK_VERILOG, PDK_PRIMITIVES, PDK_BLACKBOX = locate_pdk_files(PDK_ROOT)

# -----------------------------------------------------------------------------
# 辅助函数：执行命令并同时输出到控制台与专用日志文件
# -----------------------------------------------------------------------------
def run_command_with_logging(cmd, log_file_path: Path, cwd=None):
    logger.info(f"Executing: {' '.join(str(c) for c in cmd)}")
    with open(log_file_path, "w", encoding="utf-8") as f_out:
        f_out.write(f"=== Command: {' '.join(str(c) for c in cmd)} ===\n\n")
        
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
# 1. 形式等价性验证 (LEC via Yosys)
# -----------------------------------------------------------------------------
def run_formal_lec(orig_path: Path, opt_path: Path, top: str):
    logger.info("=" * 60)
    logger.info(">>> Step 1: Formal Logic Equivalence Checking (Yosys)")
    logger.info("=" * 60)

    lec_script = f"""
    read_verilog -sv {orig_path}
    rename {top} {top}_orig

    read_verilog -sv {opt_path}
    rename {top} {top}_opt

    proc
    clk2fflogic

    equiv_make {top}_orig {top}_opt miter
    hierarchy -top miter
    flatten

    equiv_simple
    equiv_induct
    equiv_status -assert
    """
    script_path = WORKSPACE / "lec.ys"
    script_path.write_text(lec_script)
    lec_log = LOG_DIR / "yosys_lec.log"

    try:
        run_command_with_logging(["yosys", "-q", "-s", str(script_path)], lec_log)
        logger.info("[PASS] 100% Functional Equivalence Verified by SAT.")
    except subprocess.CalledProcessError:
        logger.error(f"[FAIL] Functional Equivalence Check Failed! Please inspect: {lec_log}")
        sys.exit(1)

# -----------------------------------------------------------------------------
# 2. 物理实现流程 (带显式 SDC 约束文件，消除 fallback 警告)
# -----------------------------------------------------------------------------
def run_pnr_flow(run_tag: str, verilog_src: Path, top: str):
    logger.info("=" * 60)
    logger.info(f">>> Step 2: Physical Implementation [{run_tag}] (LibreLane)")
    logger.info("=" * 60)

    tag_dir = WORKSPACE / run_tag
    tag_dir.mkdir(parents=True, exist_ok=True)

    # 优化点 2：自动生成显式约束文件，消除 fallback SDC 警告
    sdc_file = tag_dir / "design.sdc"
    sdc_content = f"""
    create_clock [get_ports clk] -name clk -period 10.0
    set_clock_uncertainty 0.25 [get_clocks clk]
    set_clock_transition 0.15 [get_clocks clk]

    set_input_delay -max 2.0 -clock clk [all_inputs -no_clocks]
    set_output_delay -max 2.0 -clock clk [all_outputs]
    set_load 0.033442 [all_outputs]
    """
    sdc_file.write_text(sdc_content)

    design_config = {
        "PDK": PDK_NAME,
        "STD_CELL_LIBRARY": SCL_NAME,
        "DESIGN_NAME": top,
        "VERILOG_FILES": [str(verilog_src)],
        "CLOCK_PORT": "clk",
        "CLOCK_PERIOD": 10.0,
        "FP_SIZING": "relative",
        "FP_CORE_UTIL": 25,
        "FP_ASPECT_RATIO": 1,
        "PL_TARGET_DENSITY_PCT": 35,
        "RUN_POST_CTS_RESIZER_TIMING": False,

        # 显式指定 SDC 路径，避免 OpenROAD 提示 fallback SDC
        "PNR_SDC_FILE": str(sdc_file),
        "SIGNOFF_SDC_FILE": str(sdc_file),

        # 保持双版图生成以通过下游检查
        "RUN_KLAYOUT_STREAMOUT": True,
        "RUN_MAGIC_STREAMOUT": True,

        # 关闭耗时物理检查
        "RUN_KLAYOUT_DRC": False,
        "RUN_MAGIC_DRC": False,
        "RUN_LVS": False,
    }

    config_file = tag_dir / "config.json"
    config_file.write_text(json.dumps(design_config, indent=2))

    cmd = [
        "librelane",
        str(config_file),
        "--design-dir", str(tag_dir),
        "--pdk-root", str(PDK_ROOT),
        "--pdk", PDK_NAME,
        "--scl", SCL_NAME,
        "--run-tag", run_tag,
        "--overwrite"
    ]

    pnr_log = LOG_DIR / f"pnr_{run_tag}.log"
    run_command_with_logging(cmd, pnr_log)

    run_dir = tag_dir / "runs" / run_tag
    final_dir = run_dir / "final"

    # 1. 门级仿真与分析提取纯逻辑网表 (nl.v)
    netlist = final_dir / "nl" / f"{top}.nl.v"
    if not netlist.exists():
        fallback_nl = list(final_dir.glob(f"**/{top}*.nl.v"))
        if fallback_nl:
            netlist = fallback_nl[0]
        else:
            raise FileNotFoundError(f"Cannot find logic netlist in {final_dir}")

    # 2. 寄生参数 SPEF
    spef = final_dir / "spef" / "nom" / f"{top}.nom.spef"
    if not spef.exists():
        fallback_spef = list(final_dir.glob(f"spef/**/{top}*.spef"))
        spef = fallback_spef[0]

    logger.info(f"[*] Post-PnR Netlist: {netlist}")
    logger.info(f"[*] Post-PnR SPEF:    {spef}")

    return netlist, spef

# -----------------------------------------------------------------------------
# 3. 门级仿真生成活跃度波形 (修复 UNIT_DELAY 警告)
# -----------------------------------------------------------------------------
def generate_vcd_activity(run_tag: str, netlist: Path, top: str):
    logger.info("=" * 60)
    logger.info(f">>> Step 3: Simulation & Activity Profile Extraction [{run_tag}]")
    logger.info("=" * 60)

    tb_content = f"""
    `timescale 1ns/1ps
    module tb;
        reg clk = 0;
        reg rst_n = 0;
        reg en = 0;
        reg [31:0] data_in = 0;
        wire [31:0] data_out;

        always #5 clk = ~clk;

        {top} u_dut (
            .clk(clk), .rst_n(rst_n), .en(en),
            .data_in(data_in), .data_out(data_out)
        );

        initial begin
            $dumpfile("{run_tag}_activity.vcd");
            $dumpvars(0, tb.u_dut);
            #20 rst_n = 1;

            repeat (200) begin
                @(posedge clk);
                en <= ($urandom % 10 == 0);
                data_in <= $urandom;
            end
            #50 $finish;
        end
    endmodule
    """
    tb_path = WORKSPACE / f"tb_{run_tag}.v"
    tb_path.write_text(tb_content)
    vvp_path = WORKSPACE / f"sim_{run_tag}.vvp"
    vcd_path = WORKSPACE / f"{run_tag}_activity.vcd"

    sim_compile_log = LOG_DIR / f"sim_{run_tag}_compile.log"

    run_command_with_logging([
        "iverilog", "-g2012", "-DFUNCTIONAL", "-o", str(vvp_path),
        str(PDK_PRIMITIVES), str(PDK_VERILOG), str(netlist), str(tb_path)
    ], sim_compile_log)

    sim_run_log = LOG_DIR / f"sim_{run_tag}_exec.log"
    run_command_with_logging(["vvp", str(vvp_path)], sim_run_log, cwd=WORKSPACE)
    return vcd_path

# -----------------------------------------------------------------------------
# 4. OpenSTA 功耗精确签核
# -----------------------------------------------------------------------------
def run_power_signoff(run_tag: str, netlist: Path, spef: Path, vcd: Path, top: str):
    logger.info("=" * 60)
    logger.info(f">>> Step 4: OpenSTA Signoff Power Evaluation [{run_tag}]")
    logger.info("=" * 60)

    report_file = WORKSPACE / f"{run_tag}_power.rpt"

    sta_script = f"""
    read_liberty {LIB_PATH}
    read_verilog {PDK_BLACKBOX}
    read_verilog {netlist}
    link_design {top}
    read_spef {spef}
    create_clock -name clk -period 10.0 [get_ports clk]

    read_vcd -scope tb/u_dut {vcd}
    report_power > {report_file}
    exit
    """
    sta_cmd_path = WORKSPACE / f"calc_pwr_{run_tag}.tcl"
    sta_cmd_path.write_text(sta_script)

    sta_log = LOG_DIR / f"sta_power_{run_tag}.log"
    run_command_with_logging(["sta", str(sta_cmd_path)], sta_log)

    text = report_file.read_text()
    pwr_metrics = {}
    for line in text.splitlines():
        if line.strip().startswith("Total") and any(unit in line for unit in ["W", "mW", "uW", "pW", "e-"]):
            parts = line.split()
            if len(parts) >= 5:
                pwr_metrics["Internal"] = parts[1]
                pwr_metrics["Switching"] = parts[2]
                pwr_metrics["Leakage"] = parts[3]
                pwr_metrics["Total"] = parts[4]
                break

    return pwr_metrics

# -----------------------------------------------------------------------------
# 5. 主入口
# -----------------------------------------------------------------------------
def main():
    logger.info(f"Pipeline started. Full session logs saved to: {LOG_DIR}")

    # 1. 形式等价性验证
    run_formal_lec(ORIG_SRC, OPT_SRC, TOP_MODULE)

    runs = {"orig": ORIG_SRC, "opt": OPT_SRC}
    results = {}

    # 2. 依次物理跑通与分析
    for tag, src in runs.items():
        netlist, spef = run_pnr_flow(tag, src, TOP_MODULE)
        vcd = generate_vcd_activity(tag, netlist, TOP_MODULE)
        results[tag] = run_power_signoff(tag, netlist, spef, vcd, TOP_MODULE)

    # 3. 最终对比表格输出
    summary = "\n" + "=" * 65 + "\n"
    summary += f"{'Power Metric':<20} | {'Original RTL':<18} | {'Optimized RTL':<18}\n"
    summary += "-" * 65 + "\n"
    for category in ["Internal", "Switching", "Leakage", "Total"]:
        orig_val = results.get("orig", {}).get(category, "N/A")
        opt_val = results.get("opt", {}).get(category, "N/A")
        summary += f"{category:<20} | {orig_val:<18} | {opt_val:<18}\n"
    summary += "=" * 65

    logger.info(summary)
    logger.info(f"Pipeline finished successfully. All log files archived in: {LOG_DIR}")

if __name__ == "__main__":
    main()