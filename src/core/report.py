#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 5: 全维度 PPA 报表生成与 Trade-off 关系深度分析
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, Optional


def generate_ppa_summary_report(
    case_name: str,
    top_module: str,
    all_data: Dict[str, Dict[str, Any]],
    reports_dir: Path,
    log_dir: Path,
    logger: logging.Logger,
) -> str:
    """
    汇总体积、时序、功耗与翻转活动度数据，
    输出结构化 JSON 并生成多维深度权衡分析的 Markdown 汇总报告。
    """
    orig = all_data["orig"]
    opt = all_data["opt"]

    orig_pwr = orig["power"]
    opt_pwr = opt["power"]
    orig_time = orig["timing"]
    opt_time = opt["timing"]
    orig_area = orig["area"]
    opt_area = opt["area"]

    def calc_delta(o_val: Any, m_val: Any, is_slack: bool = False) -> Tuple[str, Optional[float]]:
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
                f"这通常发生在门控或低功耗逻辑引入的固定开销（如时钟树分支、隔离锁存器）超过了触发器或组合逻辑节省量的情况（如窄数据通路或使能高频翻转），属于设计权衡中的反向惩罚。"
            )
    else:
        md_lines.append("- 功耗与面积数据如上表所示。")

    md_lines.extend([
        "\n### 2.2 功耗与时序性能的敏感度关系 (Power vs. Timing Slack)",
    ])

    if slack_diff is not None:
        if slack_diff >= 0:
            md_lines.append(
                f"- **时序保持/改善**: 优化设计使建立时间裕量变动了 **{slack_delta_str}**。"
                f"表明该低功耗变换不仅没有恶化关键路径时序，甚至通过解耦杂散翻转前级逻辑带来了轻微的时序改善，实现了性能与功耗的双重优化。"
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

    # 3. 信号翻转活动度签核分析
    orig_act = orig.get("activity", {})
    opt_act = opt.get("activity", {})
    act_rows = [
        ("Annotated Pins (VCD反标引脚数)", orig_act.get("Annotated_Pins", "N/A"), opt_act.get("Annotated_Pins", "N/A"), "", False),
        ("Unannotated Pins (未反标引脚数)", orig_act.get("Unannotated_Pins", "N/A"), opt_act.get("Unannotated_Pins", "N/A"), "", False),
        ("Clock Transition Density (时钟翻转密度)", orig_act.get("Clock_Transition_Density", "N/A"), opt_act.get("Clock_Transition_Density", "N/A"), "trans/s", False),
        ("Enable Static Probability (使能静态概率/占空比)", orig_act.get("Enable_Static_Probability", "N/A"), opt_act.get("Enable_Static_Probability", "N/A"), "", False),
        ("Avg Data In Transition Density (数据输入平均翻转)", orig_act.get("Avg_Data_In_Transition_Density", "N/A"), opt_act.get("Avg_Data_In_Transition_Density", "N/A"), "trans/s", False),
        ("Avg Data Out Transition Density (数据输出平均翻转)", orig_act.get("Avg_Data_Out_Transition_Density", "N/A"), opt_act.get("Avg_Data_Out_Transition_Density", "N/A"), "trans/s", False),
    ]
    md_lines.extend([
        "\n---",
        "## 3. 信号翻转活动度签核报告 (Signal & Pin Activity Signoff)\n",
        "| 分析维度 (Category) | 信号/引脚指标 (Signal Metric) | 原始设计 (Original) | 优化设计 (Optimized) | 变化量 (Delta) |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ])
    for idx, (label, o, m, unit, is_s) in enumerate(act_rows):
        delta_str, _ = calc_delta(o, m, is_s)
        u_o = f"{o} {unit}".strip() if o != "N/A" else "N/A"
        u_m = f"{m} {unit}".strip() if m != "N/A" else "N/A"
        cat_header = "**Activity (翻转活动度)**" if idx == 0 else ""
        md_lines.append(f"| {cat_header} | {label} | {u_o} | {u_m} | **{delta_str}** |")

    md_lines.extend([
        "\n> [!TIP]",
        f"> 详细引脚级翻转统计已分别导出至:  ",
        f"> - 原始设计活动度报告: [`orig_activity.rpt`](file://{reports_dir / 'orig_activity.rpt'})  ",
        f"> - 优化设计活动度报告: [`opt_activity.rpt`](file://{reports_dir / 'opt_activity.rpt'})  ",
        f"> - 反标覆盖率详表: [`orig_activity_annotation.rpt`](file://{reports_dir / 'orig_activity_annotation.rpt'}), [`opt_activity_annotation.rpt`](file://{reports_dir / 'opt_activity_annotation.rpt'})"
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

