#!/usr/bin/env python3
"""
Generate publication-grade, beautifully styled SVG comparison charts for all
RTL Transformation study reports in doc/images/ organized by subcategory:
- doc/images/clock_gating/
- doc/images/operand_isolation/
- doc/images/data_gating/
"""

import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_IMG_DIR = Path(__file__).resolve().parent.parent / "doc" / "images"
CG_DIR = BASE_IMG_DIR / "clock_gating"
OI_DIR = BASE_IMG_DIR / "operand_isolation"
DG_DIR = BASE_IMG_DIR / "data_gating"
GC_DIR = BASE_IMG_DIR / "gray_counter"
OHM_DIR = BASE_IMG_DIR / "onehot_mux"
BI_DIR = BASE_IMG_DIR / "bus_invert"
for d in [CG_DIR, OI_DIR, DG_DIR, GC_DIR, OHM_DIR, BI_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def svg_header(w, h):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<defs>
  <style>
    .title {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 16px; font-weight: 700; fill: #0f172a; }}
    .subtitle {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 12px; fill: #64748b; }}
    .axis-label {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 12px; font-weight: 600; fill: #334155; }}
    .tick-label {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 11px; fill: #64748b; }}
    .data-label {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 10px; font-weight: 700; }}
    .legend-text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 11px; font-weight: 500; fill: #334155; }}
    .grid-line {{ stroke: #f1f5f9; stroke-width: 1; }}
    .zero-line {{ stroke: #475569; stroke-width: 1.5; stroke-dasharray: 4,4; }}
    .axis-line {{ stroke: #cbd5e1; stroke-width: 1.5; }}
  </style>
  <linearGradient id="grad-green" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#10b981" />
    <stop offset="100%" stop-color="#059669" />
  </linearGradient>
  <linearGradient id="grad-blue" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#0ea5e9" />
    <stop offset="100%" stop-color="#0284c7" />
  </linearGradient>
  <linearGradient id="grad-amber" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#f59e0b" />
    <stop offset="100%" stop-color="#d97706" />
  </linearGradient>
  <linearGradient id="grad-red" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#f43f5e" />
    <stop offset="100%" stop-color="#e11d48" />
  </linearGradient>
</defs>
<rect width="{w}" height="{h}" rx="10" fill="#ffffff" stroke="#e2e8f0" stroke-width="1.5"/>
"""


def svg_footer():
    return "</svg>\n"


def write_svg_and_validate(path: Path, content: str):
    path.write_text(content, encoding="utf-8")
    try:
        ET.parse(str(path))
        print(f"  [OK] Valid XML: {path.relative_to(BASE_IMG_DIR.parent)}")
    except Exception as e:
        print(f"  [ERROR] Invalid XML in {path}: {e}")
        raise


# ==============================================================================
# Category 1: Clock Gating
# ==============================================================================
def gen_cg_total_power_delta():
    w, h = 840, 450
    out = [svg_header(w, h)]
    out.append('<text x="32" y="38" class="title">Sky130 寄存器组时钟门控：各规模在不同使能活跃度下的总功耗变化率</text>')
    out.append('<text x="32" y="58" class="subtitle">基准时钟: 100MHz | 负值向下为节能正收益，正值向上为 ICG/CTS 开销反噬</text>')

    x0, y0, cw, ch = 85, 85, 710, 275
    y_min, y_max = -80, 80
    zero_y = y0 + int(ch * (y_max - 0) / (y_max - y_min))

    for val in range(-80, 81, 20):
        y = y0 + int(ch * (y_max - val) / (y_max - y_min))
        if val == 0:
            out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="zero-line"/>')
            out.append(f'<text x="{x0+cw+8}" y="{y+4}" class="tick-label" fill="#475569" font-weight="600">0% 损益平衡线</text>')
        else:
            out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="grid-line"/>')
        out.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" class="tick-label">{val:+d}%</text>')

    groups = [
        ("8-bit 寄存器组", [+26.13, +33.61, +51.52, +70.50]),
        ("16-bit 寄存器组", [-9.52, -1.06, +16.19, +34.82]),
        ("32-bit 寄存器组", [-39.04, -24.33, -6.27, +11.34]),
        ("64-bit 寄存器组", [-67.12, -53.09, -29.59, -5.87]),
    ]
    bar_colors = ["url(#grad-green)", "url(#grad-blue)", "url(#grad-amber)", "url(#grad-red)"]
    text_colors = ["#059669", "#0284c7", "#d97706", "#e11d48"]

    gw = cw / len(groups)
    bw = 34
    gap = 6

    for gi, (gname, vals) in enumerate(groups):
        gx = x0 + gi * gw + (gw - (len(vals) * (bw + gap) - gap)) / 2
        for vi, v in enumerate(vals):
            bx = gx + vi * (bw + gap)
            bh = abs(int(ch * v / (y_max - y_min)))
            rect_y = zero_y if v < 0 else zero_y - bh
            fill = bar_colors[vi]
            tcol = text_colors[vi]

            out.append(f'<rect x="{bx}" y="{rect_y}" width="{bw}" height="{bh}" rx="3" fill="{fill}"/>')
            lbl_y = rect_y - 6 if v >= 0 else rect_y + bh + 13
            out.append(f'<text x="{bx+bw/2}" y="{lbl_y}" text-anchor="middle" class="data-label" fill="{tcol}">{v:+.1f}%</text>')

        out.append(f'<text x="{gx + (len(vals)*(bw+gap)-gap)/2}" y="{y0+ch+28}" text-anchor="middle" class="axis-label">{gname}</text>')

    lx, ly = x0 + 40, h - 22
    leg_info = [
        ("url(#grad-green)", "使能 5% 活跃度 (95%空闲)"),
        ("url(#grad-blue)", "使能 20% 活跃度 (80%空闲)"),
        ("url(#grad-amber)", "使能 50% 活跃度 (50%空闲)"),
        ("url(#grad-red)", "使能 80% 活跃度 (20%空闲)"),
    ]
    for li, (col, text) in enumerate(leg_info):
        out.append(f'<rect x="{lx+li*168}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*168+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(CG_DIR / "cg_total_power_delta.svg", "".join(out))


def gen_cg_power_breakdown():
    w, h = 840, 440
    out = [svg_header(w, h)]
    out.append('<text x="32" y="38" class="title">Sky130 寄存器组时钟门控：原始 vs 门控功耗成分拆解对比 (5% 活跃度工况)</text>')
    out.append('<text x="32" y="58" class="subtitle">单位: uW | 拆解: 时钟树功耗 (Clock Power) + 触发器时序功耗 (Sequential Power)</text>')

    x0, y0, cw, ch = 80, 85, 710, 265
    y_max = 750

    for val in range(0, y_max + 1, 150):
        y = y0 + ch - int(ch * val / y_max)
        cls = "zero-line" if val == 0 else "grid-line"
        out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="{cls}"/>')
        out.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" class="tick-label">{val}</text>')

    data = [
        ("8-bit", 63.6, 33.4, 111.0, 121.0, 5.2, 140.0),
        ("16-bit", 73.6, 66.8, 168.0, 118.0, 7.39, 152.0),
        ("32-bit", 133.0, 136.0, 333.0, 128.0, 18.5, 203.0),
        ("64-bit", 333.0, 266.0, 660.0, 147.0, 16.0, 217.0),
    ]

    gw = cw / len(data)
    bw = 50
    gap = 14

    for gi, (name, o_clk, o_seq, o_tot, p_clk, p_seq, p_tot) in enumerate(data):
        cx = x0 + gi * gw + gw / 2
        bx_o = cx - bw - gap / 2
        bh_o_clk = int(ch * o_clk / y_max)
        bh_o_seq = int(ch * o_seq / y_max)
        bh_o_tot = int(ch * o_tot / y_max)
        by_o_clk = y0 + ch - bh_o_clk
        by_o_seq = by_o_clk - bh_o_seq

        out.append(f'<rect x="{bx_o}" y="{by_o_clk}" width="{bw}" height="{bh_o_clk}" fill="#3b82f6" rx="2" opacity="0.9"/>')
        out.append(f'<rect x="{bx_o}" y="{by_o_seq}" width="{bw}" height="{bh_o_seq}" fill="#93c5fd" rx="2" opacity="0.9"/>')
        out.append(f'<text x="{bx_o+bw/2}" y="{y0+ch-bh_o_tot-6}" text-anchor="middle" class="data-label" fill="#1e293b">{o_tot:.0f}</text>')

        bx_p = cx + gap / 2
        bh_p_clk = int(ch * p_clk / y_max)
        bh_p_seq = int(ch * p_seq / y_max)
        bh_p_tot = int(ch * p_tot / y_max)
        by_p_clk = y0 + ch - bh_p_clk
        by_p_seq = by_p_clk - bh_p_seq

        pct = (p_tot - o_tot) / o_tot * 100
        p_col = "#059669" if pct < 0 else "#dc2626"

        out.append(f'<rect x="{bx_p}" y="{by_p_clk}" width="{bw}" height="{bh_p_clk}" fill="#0d9488" rx="2" opacity="0.9"/>')
        out.append(f'<rect x="{bx_p}" y="{by_p_seq}" width="{bw}" height="{bh_p_seq}" fill="#5eead4" rx="2" opacity="0.9"/>')
        out.append(f'<text x="{bx_p+bw/2}" y="{y0+ch-bh_p_tot-6}" text-anchor="middle" class="data-label" fill="{p_col}">{p_tot:.0f} ({pct:+.0f}%)</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+24}" text-anchor="middle" class="axis-label">{name}</text>')
        out.append(f'<text x="{bx_o+bw/2}" y="{y0+ch+38}" text-anchor="middle" class="tick-label">原始</text>')
        out.append(f'<text x="{bx_p+bw/2}" y="{y0+ch+38}" text-anchor="middle" class="tick-label">门控</text>')

    lx, ly = x0 + 100, h - 18
    legends = [
        ("#3b82f6", "原始-时钟树功耗"),
        ("#93c5fd", "原始-触发器时序功耗"),
        ("#0d9488", "门控-时钟树功耗"),
        ("#5eead4", "门控-触发器时序功耗"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*150}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*150+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(CG_DIR / "cg_power_breakdown.svg", "".join(out))


def gen_cg_area_breakdown():
    w, h = 840, 440
    out = [svg_header(w, h)]
    out.append('<text x="32" y="38" class="title">Sky130 寄存器组时钟门控：物理标准单元面积增减微观分解</text>')
    out.append('<text x="32" y="58" class="subtitle">单位: um² | MUX2 消除量（负值/绿色，带来面积缩减） vs ICG 与 CTS 缓冲器开销（正值/红色）</text>')

    x0, y0, cw, ch = 90, 85, 700, 265
    y_min, y_max = -750, 250
    zero_y = y0 + int(ch * (y_max - 0) / (y_max - y_min))

    for val in range(-700, 251, 150):
        y = y0 + int(ch * (y_max - val) / (y_max - y_min))
        cls = "zero-line" if val == 0 else "grid-line"
        out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="{cls}"/>')
        out.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" class="tick-label">{val:+d}</text>')

    data = [
        ("8-bit", -82.58, +15.01, +150.14, +81.33, "+14.19%"),
        ("16-bit", -172.67, +15.01, +163.91, 0.00, "0.00%"),
        ("32-bit", -352.84, +15.01, +177.67, -151.40, "-7.35%"),
        ("64-bit", -713.18, +15.01, +175.17, -584.31, "-13.89%"),
    ]

    gw = cw / len(data)
    bw = 36
    gap = 8

    for gi, (name, mux_d, icg_d, cts_d, net_d, net_str) in enumerate(data):
        cx = x0 + gi * gw + gw / 2

        bx1 = cx - 2 * bw - 1.5 * gap
        bh1 = int(ch * abs(mux_d) / (y_max - y_min))
        out.append(f'<rect x="{bx1}" y="{zero_y}" width="{bw}" height="{bh1}" rx="2" fill="#10b981" opacity="0.9"/>')
        out.append(f'<text x="{bx1+bw/2}" y="{zero_y+bh1+14}" text-anchor="middle" class="data-label" fill="#047857">{mux_d:.0f}</text>')

        bx2 = cx - bw - 0.5 * gap
        bh2 = int(ch * icg_d / (y_max - y_min))
        out.append(f'<rect x="{bx2}" y="{zero_y-bh2}" width="{bw}" height="{bh2}" rx="2" fill="#f59e0b" opacity="0.9"/>')
        out.append(f'<text x="{bx2+bw/2}" y="{zero_y-bh2-6}" text-anchor="middle" class="data-label" fill="#b45309">+{icg_d:.0f}</text>')

        bx3 = cx + 0.5 * gap
        bh3 = int(ch * cts_d / (y_max - y_min))
        out.append(f'<rect x="{bx3}" y="{zero_y-bh3}" width="{bw}" height="{bh3}" rx="2" fill="#ef4444" opacity="0.9"/>')
        out.append(f'<text x="{bx3+bw/2}" y="{zero_y-bh3-6}" text-anchor="middle" class="data-label" fill="#b91c1c">+{cts_d:.0f}</text>')

        bx4 = cx + bw + 1.5 * gap
        bh4 = int(ch * abs(net_d) / (y_max - y_min))
        col4 = "#1e293b"
        by4 = zero_y if net_d <= 0 else zero_y - bh4
        if bh4 == 0:
            out.append(f'<line x1="{bx4}" y1="{zero_y}" x2="{bx4+bw}" y2="{zero_y}" stroke="{col4}" stroke-width="3"/>')
        else:
            out.append(f'<rect x="{bx4}" y="{by4}" width="{bw}" height="{bh4}" rx="2" fill="{col4}" stroke="#0f172a" stroke-width="1"/>')
        lbl_y4 = zero_y + bh4 + 14 if net_d <= 0 else zero_y - bh4 - 6
        out.append(f'<text x="{bx4+bw/2}" y="{lbl_y4}" text-anchor="middle" class="data-label" fill="{col4}">{net_d:+.0f}</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+32}" text-anchor="middle" class="axis-label">{name} (净变化 {net_str})</text>')

    lx, ly = x0 + 40, h - 16
    legends = [
        ("#10b981", "省去 MUX2 面积 (负值)"),
        ("#f59e0b", "新增 ICG 锁存器面积"),
        ("#ef4444", "新增 CTS 时钟缓冲器面积"),
        ("#1e293b", "净面积变化 (Net Delta)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*170}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*170+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(CG_DIR / "cg_area_breakdown.svg", "".join(out))


# ==============================================================================
# Category 2: Operand Isolation
# ==============================================================================
def gen_oi_total_power_delta():
    w, h = 840, 450
    out = [svg_header(w, h)]
    out.append('<text x="32" y="38" class="title">Sky130 ALU 操作数隔离：各位宽在不同有效计算概率下的总功耗变化率</text>')
    out.append('<text x="32" y="58" class="subtitle">高总线噪声工况 (Data Activity = 60%) | 负值向下为节能正收益，正值向上为隔离门翻转开销</text>')

    x0, y0, cw, ch = 85, 85, 710, 275
    y_min, y_max = -60, 20
    zero_y = y0 + int(ch * (y_max - 0) / (y_max - y_min))

    for val in range(-60, 21, 10):
        y = y0 + int(ch * (y_max - val) / (y_max - y_min))
        if val == 0:
            out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="zero-line"/>')
            out.append(f'<text x="{x0+cw+8}" y="{y+4}" class="tick-label" fill="#475569" font-weight="600">0% 临界线</text>')
        else:
            out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="grid-line"/>')
        out.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" class="tick-label">{val:+d}%</text>')

    groups = [
        ("8-bit ALU", [-42.47, -19.17, +3.64, +7.23]),
        ("16-bit ALU", [-48.79, -20.50, +6.92, +10.30]),
        ("32-bit ALU", [-51.19, -21.85, +6.92, +10.69]),
        ("64-bit ALU", [-54.44, -24.71, +4.04, +7.66]),
    ]
    bar_colors = ["url(#grad-green)", "url(#grad-blue)", "url(#grad-amber)", "url(#grad-red)"]
    text_colors = ["#059669", "#0284c7", "#d97706", "#e11d48"]

    gw = cw / len(groups)
    bw = 34
    gap = 6

    for gi, (gname, vals) in enumerate(groups):
        gx = x0 + gi * gw + (gw - (len(vals) * (bw + gap) - gap)) / 2
        for vi, v in enumerate(vals):
            bx = gx + vi * (bw + gap)
            bh = abs(int(ch * v / (y_max - y_min)))
            fill = bar_colors[vi]
            tcol = text_colors[vi]
            rect_y = zero_y if v < 0 else zero_y - bh

            out.append(f'<rect x="{bx}" y="{rect_y}" width="{bw}" height="{bh}" rx="3" fill="{fill}"/>')
            lbl_y = rect_y - 6 if v >= 0 else rect_y + bh + 13
            out.append(f'<text x="{bx+bw/2}" y="{lbl_y}" text-anchor="middle" class="data-label" fill="{tcol}">{v:+.1f}%</text>')

        out.append(f'<text x="{gx + (len(vals)*(bw+gap)-gap)/2}" y="{y0+ch+28}" text-anchor="middle" class="axis-label">{gname}</text>')

    lx, ly = x0 + 40, h - 22
    legends = [
        ("url(#grad-green)", "有效计算 5% (95%空闲)"),
        ("url(#grad-blue)", "有效计算 20% (80%空闲)"),
        ("url(#grad-amber)", "有效计算 50% (50%空闲)"),
        ("url(#grad-red)", "有效计算 80% (20%空闲)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*168}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*168+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(OI_DIR / "oi_total_power_delta.svg", "".join(out))


def gen_oi_comb_power_reduction():
    w, h = 840, 440
    out = [svg_header(w, h)]
    out.append('<text x="32" y="38" class="title">Sky130 ALU 操作数隔离：纯组合逻辑功耗专项削减对比 (Valid=5%, Act=60%)</text>')
    out.append('<text x="32" y="58" class="subtitle">单位: uW | 展现操作数隔离切断深层加法树/逻辑阵列毛刺传播的压倒性节能（削减率 ~70%）</text>')

    x0, y0, cw, ch = 90, 85, 700, 265
    y_max = 2000

    for val in range(0, y_max + 1, 400):
        y = y0 + ch - int(ch * val / y_max)
        cls = "zero-line" if val == 0 else "grid-line"
        out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="{cls}"/>')
        out.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" class="tick-label">{val}</text>')

    data = [
        ("8-bit ALU", 189.0, 63.4, -66.46),
        ("16-bit ALU", 412.0, 127.0, -69.17),
        ("32-bit ALU", 874.0, 262.0, -70.02),
        ("64-bit ALU", 1840.0, 517.0, -71.90),
    ]

    gw = cw / len(data)
    bw = 54
    gap = 16

    for gi, (name, orig_c, opt_c, pct) in enumerate(data):
        cx = x0 + gi * gw + gw / 2
        bx1 = cx - bw - gap / 2
        bh1 = int(ch * orig_c / y_max)
        by1 = y0 + ch - bh1

        bx2 = cx + gap / 2
        bh2 = int(ch * opt_c / y_max)
        by2 = y0 + ch - bh2

        out.append(f'<rect x="{bx1}" y="{by1}" width="{bw}" height="{bh1}" rx="3" fill="#64748b" opacity="0.85"/>')
        out.append(f'<text x="{bx1+bw/2}" y="{by1-6}" text-anchor="middle" class="data-label" fill="#334155">{orig_c:.0f}</text>')

        out.append(f'<rect x="{bx2}" y="{by2}" width="{bw}" height="{bh2}" rx="3" fill="#10b981" opacity="0.9"/>')
        out.append(f'<text x="{bx2+bw/2}" y="{by2-6}" text-anchor="middle" class="data-label" fill="#047857">{opt_c:.0f}</text>')

        badge_y = min(by1, by2) - 22
        out.append(f'<rect x="{cx-38}" y="{badge_y-12}" width="76" height="18" rx="4" fill="#ecfdf5" stroke="#10b981" stroke-width="1"/>')
        out.append(f'<text x="{cx}" y="{badge_y+1}" text-anchor="middle" class="data-label" fill="#065f46">{pct:.1f}%</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+24}" text-anchor="middle" class="axis-label">{name}</text>')
        out.append(f'<text x="{bx1+bw/2}" y="{y0+ch+38}" text-anchor="middle" class="tick-label">原始组合</text>')
        out.append(f'<text x="{bx2+bw/2}" y="{y0+ch+38}" text-anchor="middle" class="tick-label">隔离组合</text>')

    lx, ly = x0 + 160, h - 18
    legends = [
        ("#64748b", "原始未隔离组合功耗"),
        ("#10b981", "操作数隔离后组合功耗"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*220}" y="{ly-10}" width="16" height="12" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*220+24}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(OI_DIR / "oi_comb_power_reduction.svg", "".join(out))


def gen_oi_activity_impact():
    w, h = 880, 480
    out = [svg_header(w, h)]
    out.append('<text x="32" y="38" class="title">Sky130 ALU 操作数隔离：不同数据总线翻转活跃度 (10% vs 30% vs 60%) 对总功耗变化率的影响</text>')
    out.append('<text x="32" y="58" class="subtitle">对比分析：(左) 稀疏计算工况 (Valid=20%) 下总线翻转率彻底扭转收支平衡 vs (右) 突发休眠工况 (Valid=5%) 下高翻转率放大超额节能</text>')

    panels = [
        {
            "title": "工况 A: 稀疏使能计算 (Valid Duty = 20% | 收支平衡临界翻转区)",
            "subtitle": "低活跃度(10%)导致开销反噬 (+5%)，高活跃度(60%)逆转为深度节能 (-25%)",
            "x0": 70, "cw": 345, "y_min": -30, "y_max": 10, "step": 10,
            "data": [
                ("8-bit", [+0.87, -8.40, -19.17]),
                ("16-bit", [+4.80, -8.84, -20.50]),
                ("32-bit", [+5.67, -9.03, -21.85]),
                ("64-bit", [+2.92, -12.89, -24.71]),
            ]
        },
        {
            "title": "工况 B: 突发休眠模式 (Valid Duty = 5% | 深度节电区)",
            "subtitle": "95% 周期阻断无效翻转，活跃度越高，截断的无用功耗越惊人",
            "x0": 485, "cw": 345, "y_min": -60, "y_max": 0, "step": 15,
            "data": [
                ("8-bit", [-28.24, -30.67, -42.47]),
                ("16-bit", [-32.82, -36.43, -48.79]),
                ("32-bit", [-35.22, -38.63, -51.19]),
                ("64-bit", [-38.76, -42.16, -54.44]),
            ]
        }
    ]

    y0, ch = 115, 265

    for p in panels:
        px0, pcw = p["x0"], p["cw"]
        py_min, py_max = p["y_min"], p["y_max"]
        pzero_y = y0 + int(ch * (py_max - 0) / (py_max - py_min))

        out.append(f'<text x="{px0}" y="{y0-28}" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="13px" font-weight="700" fill="#1e293b">{p["title"]}</text>')
        out.append(f'<text x="{px0}" y="{y0-12}" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="11px" fill="#64748b">{p["subtitle"]}</text>')

        for val in range(py_min, py_max + 1, p["step"]):
            y = y0 + int(ch * (py_max - val) / (py_max - py_min))
            if val == 0:
                out.append(f'<line x1="{px0}" y1="{y}" x2="{px0+pcw}" y2="{y}" class="zero-line"/>')
                out.append(f'<text x="{px0+pcw-4}" y="{y-5}" text-anchor="end" class="tick-label" fill="#475569" font-weight="700">0% 临界线</text>')
            else:
                out.append(f'<line x1="{px0}" y1="{y}" x2="{px0+pcw}" y2="{y}" class="grid-line"/>')
            out.append(f'<text x="{px0-8}" y="{y+4}" text-anchor="end" class="tick-label">{val:+d}%</text>')

        gw = pcw / len(p["data"])
        bw = 20
        gap = 4
        bar_colors = ["url(#grad-red)", "url(#grad-blue)", "url(#grad-green)"]
        text_colors = ["#e11d48", "#0284c7", "#059669"]

        for gi, (gname, vals) in enumerate(p["data"]):
            cx = px0 + gi * gw + gw / 2
            gx = cx - (len(vals) * (bw + gap) - gap) / 2

            for vi, v in enumerate(vals):
                bx = gx + vi * (bw + gap)
                bh = int(ch * abs(v) / (py_max - py_min))
                rect_y = pzero_y if v < 0 else pzero_y - bh

                if v < 0 and vi == 0:
                    fill = "url(#grad-amber)"
                    tcol = "#d97706"
                else:
                    fill = bar_colors[vi]
                    tcol = text_colors[vi]

                out.append(f'<rect x="{bx}" y="{rect_y}" width="{bw}" height="{bh}" rx="2" fill="{fill}"/>')
                lbl_y = rect_y - 5 if v >= 0 else rect_y + bh + 12
                out.append(f'<text x="{bx+bw/2}" y="{lbl_y}" text-anchor="middle" class="data-label" fill="{tcol}">{v:+.1f}%</text>')

            out.append(f'<text x="{cx}" y="{y0+ch+24}" text-anchor="middle" class="axis-label">{gname}</text>')

    lx, ly = 130, h - 18
    legends = [
        ("url(#grad-red)", "数据总线翻转率 10% (低噪声总线)"),
        ("url(#grad-blue)", "数据总线翻转率 30% (中噪声总线)"),
        ("url(#grad-green)", "数据总线翻转率 60% (高噪声总线)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*230}" y="{ly-10}" width="16" height="12" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*230+24}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(OI_DIR / "oi_activity_impact.svg", "".join(out))


# ==============================================================================
# Category 3: Data Gating (FIR Filter)
# ==============================================================================
def gen_dg_total_power_delta():
    w, h = 860, 460
    out = [svg_header(w, h)]
    out.append('<text x="32" y="38" class="title">Sky130 FIR 滤波器数据门控：抽头规模在不同有效率下的总功耗变化率 (Data Act = 60%)</text>')
    out.append('<text x="32" y="58" class="subtitle">实测非单调性排序：12-Tap (-29.6%) > 16-Tap (-28.0%) > 4-Tap (-23.8%) ≈ 8-Tap (-23.9%)</text>')

    x0, y0, cw, ch = 85, 85, 720, 280
    y_min, y_max = -35, 10
    zero_y = y0 + int(ch * (y_max - 0) / (y_max - y_min))

    for val in range(-35, 11, 5):
        y = y0 + int(ch * (y_max - val) / (y_max - y_min))
        if val == 0:
            out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="zero-line"/>')
            out.append(f'<text x="{x0+cw+8}" y="{y+4}" class="tick-label" fill="#475569" font-weight="600">0% 临界线</text>')
        else:
            out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="grid-line"/>')
        out.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" class="tick-label">{val:+d}%</text>')

    groups = [
        ("4-Tap FIR", [-23.76, -11.47, -1.25, +3.42]),
        ("8-Tap FIR", [-23.87, -10.23, +0.48, +5.24]),
        ("12-Tap FIR (🏆最优)", [-29.63, -15.32, -4.07, +1.23]),
        ("16-Tap FIR", [-27.99, -14.05, -3.24, +1.46]),
    ]
    bar_colors = ["url(#grad-green)", "url(#grad-blue)", "url(#grad-amber)", "url(#grad-red)"]
    text_colors = ["#059669", "#0284c7", "#d97706", "#e11d48"]

    gw = cw / len(groups)
    bw = 36
    gap = 6

    for gi, (gname, vals) in enumerate(groups):
        gx = x0 + gi * gw + (gw - (len(vals) * (bw + gap) - gap)) / 2
        if "12-Tap" in gname:
            out.append(f'<rect x="{gx-8}" y="{y0-5}" width="{len(vals)*(bw+gap)-gap+16}" height="{ch+10}" rx="6" fill="#f0fdf4" stroke="#86efac" stroke-dasharray="4,4"/>')

        for vi, v in enumerate(vals):
            bx = gx + vi * (bw + gap)
            bh = abs(int(ch * v / (y_max - y_min)))
            fill = bar_colors[vi]
            tcol = text_colors[vi]
            rect_y = zero_y if v < 0 else zero_y - bh

            out.append(f'<rect x="{bx}" y="{rect_y}" width="{bw}" height="{bh}" rx="3" fill="{fill}"/>')
            lbl_y = rect_y - 6 if v >= 0 else rect_y + bh + 13
            out.append(f'<text x="{bx+bw/2}" y="{lbl_y}" text-anchor="middle" class="data-label" fill="{tcol}">{v:+.1f}%</text>')

        out.append(f'<text x="{gx + (len(vals)*(bw+gap)-gap)/2}" y="{y0+ch+28}" text-anchor="middle" class="axis-label">{gname}</text>')

    lx, ly = x0 + 40, h - 22
    legends = [
        ("url(#grad-green)", "有效采样 5% (95%空闲)"),
        ("url(#grad-blue)", "有效采样 20% (80%空闲)"),
        ("url(#grad-amber)", "有效采样 50% (50%空闲)"),
        ("url(#grad-red)", "有效采样 80% (20%空闲)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*170}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*170+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(DG_DIR / "dg_total_power_delta.svg", "".join(out))


def gen_dg_area_overhead():
    w, h = 840, 440
    out = [svg_header(w, h)]
    # Escape & to &amp; for valid XML/SVG syntax
    out.append('<text x="32" y="38" class="title">Sky130 FIR 滤波器数据门控：物理实现开销对比 (标准单元数 &amp; 芯片面积变化)</text>')
    out.append('<text x="32" y="58" class="subtitle">单点广播门控仅插入 1 组 8-bit 与门 | 面积增量恒定微弱，控制在 +1.8% ~ +2.2% 区间</text>')

    x0, y0, cw, ch = 90, 85, 680, 260
    y_max_cells = 4000

    for val in range(0, y_max_cells + 1, 1000):
        y = y0 + ch - int(ch * val / y_max_cells)
        cls = "zero-line" if val == 0 else "grid-line"
        out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="{cls}"/>')
        out.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" class="tick-label">{val}</text>')

    for pct in [0, 1, 2, 3]:
        y = y0 + ch - int(ch * pct / 3.5)
        out.append(f'<text x="{x0+cw+12}" y="{y+4}" text-anchor="start" class="tick-label" fill="#dc2626">+{pct}%</text>')

    data = [
        ("4-Tap FIR", 681, 701, +20, 5266.3, 5380.2, 2.16),
        ("8-Tap FIR", 1610, 1691, +81, 12493.2, 12749.7, 2.05),
        ("12-Tap FIR", 2330, 2393, +63, 17905.9, 18227.5, 1.80),
        ("16-Tap FIR", 3370, 3437, +67, 25494.5, 25973.7, 1.88),
    ]

    gw = cw / len(data)
    bw = 48
    gap = 14
    line_points = []

    for gi, (name, o_cells, p_cells, d_cells, o_area, p_area, a_pct) in enumerate(data):
        cx = x0 + gi * gw + gw / 2
        bx1 = cx - bw - gap / 2
        bh1 = int(ch * o_cells / y_max_cells)
        by1 = y0 + ch - bh1

        bx2 = cx + gap / 2
        bh2 = int(ch * p_cells / y_max_cells)
        by2 = y0 + ch - bh2

        out.append(f'<rect x="{bx1}" y="{by1}" width="{bw}" height="{bh1}" rx="3" fill="#64748b" opacity="0.85"/>')
        out.append(f'<text x="{bx1+bw/2}" y="{by1-6}" text-anchor="middle" class="data-label" fill="#334155">{o_cells}</text>')

        out.append(f'<rect x="{bx2}" y="{by2}" width="{bw}" height="{bh2}" rx="3" fill="#0284c7" opacity="0.9"/>')
        out.append(f'<text x="{bx2+bw/2}" y="{by2-6}" text-anchor="middle" class="data-label" fill="#0369a1">{p_cells} (+{d_cells})</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+24}" text-anchor="middle" class="axis-label">{name}</text>')
        out.append(f'<text x="{bx1+bw/2}" y="{y0+ch+38}" text-anchor="middle" class="tick-label">原始单元</text>')
        out.append(f'<text x="{bx2+bw/2}" y="{y0+ch+38}" text-anchor="middle" class="tick-label">门控单元</text>')

        py = y0 + ch - int(ch * a_pct / 3.5)
        line_points.append((cx, py, a_pct))

    for i in range(len(line_points) - 1):
        x1, y1, _ = line_points[i]
        x2, y2, _ = line_points[i + 1]
        out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#dc2626" stroke-width="2.5"/>')

    for x, y, pct in line_points:
        out.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#ffffff" stroke="#dc2626" stroke-width="2.5"/>')
        out.append(f'<text x="{x}" y="{y-10}" text-anchor="middle" class="data-label" fill="#dc2626">面积 +{pct:.2f}%</text>')

    lx, ly = x0 + 80, h - 16
    legends = [
        ("#64748b", "原始标准单元数 (左轴)"),
        ("#0284c7", "门控后标准单元数 (左轴)"),
        ("#dc2626", "面积变化率 Area Delta % (右轴折线)"),
    ]
    for li, (col, text) in enumerate(legends):
        if "折线" in text:
            out.append(f'<line x1="{lx+li*210}" y1="{ly-5}" x2="{lx+li*210+16}" y2="{ly-5}" stroke="{col}" stroke-width="2.5"/>')
            out.append(f'<circle cx="{lx+li*210+8}" cy="{ly-5}" r="3" fill="#fff" stroke="{col}" stroke-width="2"/>')
        else:
            out.append(f'<rect x="{lx+li*210}" y="{ly-10}" width="16" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*210+24}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(DG_DIR / "dg_area_overhead.svg", "".join(out))


def gen_dg_comb_power_reduction():
    w, h = 840, 440
    out = [svg_header(w, h)]
    out.append('<text x="32" y="38" class="title">Sky130 FIR 滤波器数据门控：全并行乘法阵列组合功耗专项削减对比</text>')
    out.append('<text x="32" y="58" class="subtitle">典型突发工况 (Valid Duty = 5%, Data Activity = 60%) | 广播冻结切断乘法阵列毛刺，组合功耗骤降 ~72%</text>')

    x0, y0, cw, ch = 90, 85, 700, 265
    y_max = 1400

    for val in range(0, y_max + 1, 300):
        y = y0 + ch - int(ch * val / y_max)
        cls = "zero-line" if val == 0 else "grid-line"
        out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="{cls}"/>')
        out.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" class="tick-label">{val}</text>')

    data = [
        ("4-Tap FIR", 231.0, 71.3, -69.13),
        ("8-Tap FIR", 567.0, 156.0, -72.49),
        ("12-Tap FIR", 806.0, 216.0, -73.20),
        ("16-Tap FIR", 1170.0, 326.0, -72.14),
    ]

    gw = cw / len(data)
    bw = 54
    gap = 16

    for gi, (name, orig_c, opt_c, pct) in enumerate(data):
        cx = x0 + gi * gw + gw / 2
        bx1 = cx - bw - gap / 2
        bh1 = int(ch * orig_c / y_max)
        by1 = y0 + ch - bh1

        bx2 = cx + gap / 2
        bh2 = int(ch * opt_c / y_max)
        by2 = y0 + ch - bh2

        out.append(f'<rect x="{bx1}" y="{by1}" width="{bw}" height="{bh1}" rx="3" fill="#64748b" opacity="0.85"/>')
        out.append(f'<text x="{bx1+bw/2}" y="{by1-6}" text-anchor="middle" class="data-label" fill="#334155">{orig_c:.0f} uW</text>')

        out.append(f'<rect x="{bx2}" y="{by2}" width="{bw}" height="{bh2}" rx="3" fill="#10b981" opacity="0.9"/>')
        out.append(f'<text x="{bx2+bw/2}" y="{by2-6}" text-anchor="middle" class="data-label" fill="#047857">{opt_c:.0f} uW</text>')

        badge_y = min(by1, by2) - 22
        out.append(f'<rect x="{cx-38}" y="{badge_y-12}" width="76" height="18" rx="4" fill="#ecfdf5" stroke="#10b981" stroke-width="1"/>')
        out.append(f'<text x="{cx}" y="{badge_y+1}" text-anchor="middle" class="data-label" fill="#065f46">{pct:.1f}%</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+24}" text-anchor="middle" class="axis-label">{name}</text>')
        out.append(f'<text x="{bx1+bw/2}" y="{y0+ch+38}" text-anchor="middle" class="tick-label">原始乘法功耗</text>')
        out.append(f'<text x="{bx2+bw/2}" y="{y0+ch+38}" text-anchor="middle" class="tick-label">门控乘法功耗</text>')

    lx, ly = x0 + 160, h - 18
    legends = [
        ("#64748b", "原始未门控乘法阵列功耗"),
        ("#10b981", "门控后乘法阵列组合功耗"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*220}" y="{ly-10}" width="16" height="12" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*220+24}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(DG_DIR / "dg_comb_power_reduction.svg", "".join(out))


def gen_dg_tap_ranking_breakdown():
    w, h = 860, 470
    out = [svg_header(w, h)]
    out.append('<text x="32" y="38" class="title">Sky130 FIR 滤波器数据门控：微观功耗增减量分解（揭示 12>16>4>8 物理机制）</text>')
    out.append('<text x="32" y="58" class="subtitle">工况: Valid=5%, Act=60% | 组合逻辑乘法节电量 (绿色负值) vs 时钟树功耗增减量 (橙/红色) vs 净收益</text>')

    x0, y0, cw, ch = 90, 85, 710, 280
    y_min, y_max = -950, 100
    zero_y = y0 + int(ch * (y_max - 0) / (y_max - y_min))

    for val in range(-900, 101, 150):
        y = y0 + int(ch * (y_max - val) / (y_max - y_min))
        cls = "zero-line" if val == 0 else "grid-line"
        out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="{cls}"/>')
        out.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" class="tick-label">{val:+d}</text>')

    data = [
        ("4-Tap FIR", -159.7, +6.0, -153.0, "-23.76%", "28.57%"),
        ("8-Tap FIR", -411.0, +37.0, -370.0, "-23.87%", "30.52%"),
        ("12-Tap FIR (🏆Sweet Spot)", -590.0, -56.0, -640.0, "-29.63%", "27.78%"),
        ("16-Tap FIR", -844.0, -45.0, -890.0, "-27.99%", "30.82%"),
    ]

    gw = cw / len(data)
    bw = 44
    gap = 12

    for gi, (name, c_delta, clk_delta, net_delta, net_str, clk_share) in enumerate(data):
        cx = x0 + gi * gw + gw / 2

        if "12-Tap" in name:
            out.append(f'<rect x="{cx-80}" y="{y0-5}" width="160" height="{ch+10}" rx="6" fill="#f0fdf4" stroke="#86efac" stroke-dasharray="4,4"/>')

        bx1 = cx - bw - gap / 2
        bh1 = int(ch * abs(c_delta) / (y_max - y_min))
        out.append(f'<rect x="{bx1}" y="{zero_y}" width="{bw}" height="{bh1}" rx="3" fill="#10b981" opacity="0.9"/>')
        out.append(f'<text x="{bx1+bw/2}" y="{zero_y+bh1+14}" text-anchor="middle" class="data-label" fill="#047857">{c_delta:.0f}</text>')

        bx2 = cx + gap / 2
        bh2 = int(ch * abs(clk_delta) / (y_max - y_min))
        by2 = zero_y - bh2 if clk_delta > 0 else zero_y
        col2 = "#ef4444" if clk_delta > 0 else "#0d9488"
        out.append(f'<rect x="{bx2}" y="{by2}" width="{bw}" height="{bh2}" rx="3" fill="{col2}" opacity="0.9"/>')
        lbl_y2 = by2 - 6 if clk_delta > 0 else by2 + bh2 + 14
        out.append(f'<text x="{bx2+bw/2}" y="{lbl_y2}" text-anchor="middle" class="data-label" fill="{col2}">{clk_delta:+.0f}</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+30}" text-anchor="middle" class="axis-label">{name}</text>')
        out.append(f'<text x="{cx}" y="{y0+ch+46}" text-anchor="middle" class="tick-label" fill="#047857" font-weight="600">净降幅: {net_str}</text>')
        out.append(f'<text x="{bx1+bw/2}" y="{zero_y-8}" text-anchor="middle" class="tick-label">乘法节电</text>')
        out.append(f'<text x="{bx2+bw/2}" y="{zero_y-8 if clk_delta <= 0 else by2-16}" text-anchor="middle" class="tick-label">时钟变化</text>')

    lx, ly = x0 + 80, h - 14
    legends = [
        ("#10b981", "组合逻辑乘法节电量 (负值越大越优)"),
        ("#ef4444", "8-Tap CTS 时钟网络寄生反噬 (+37 uW)"),
        ("#0d9488", "12-Tap CTS 时钟网络良性缩减 (-56 uW)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*220}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*220+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(DG_DIR / "dg_tap_ranking_breakdown.svg", "".join(out))


# ==============================================================================
# Category 4: Gray Code Counter
# ==============================================================================
def gen_gc_total_power_delta():
    w, h = 840, 450
    out = [svg_header(w, h)]
    out.append('<text x="32" y="38" class="title">Sky130 格雷码计数器：各规模在不同使能活跃度下的总功耗变化率</text>')
    out.append('<text x="32" y="58" class="subtitle">基准时钟: 100MHz | 基准: 纯二进制累加计数器 (N DFF) | 负值向下为节能收益，正值向上为次态异或开销反噬</text>')

    x0, y0, cw, ch = 85, 85, 710, 275
    y_min, y_max = -15, 20

    zero_y = y0 + int(ch * (y_max - 0) / (y_max - y_min))

    for val in range(-15, 21, 5):
        y = y0 + int(ch * (y_max - val) / (y_max - y_min))
        if val == 0:
            out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="zero-line"/>')
            out.append(f'<text x="{x0+cw+8}" y="{y+4}" class="tick-label" fill="#475569" font-weight="600">0% 损益平衡线</text>')
        else:
            out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="grid-line"/>')
        out.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" class="tick-label">{val:+d}%</text>')

    groups = [
        ("4-bit 计数器", [-0.63, -3.12, -5.60, -7.47]),
        ("8-bit 计数器", [+0.99, +3.67, +7.63, +10.57]),
        ("16-bit 计数器", [-3.90, 0.00, +5.33, +8.62]),
        ("32-bit 计数器", [+4.59, +6.90, +10.74, +13.49]),
    ]
    bar_colors = ["url(#grad-green)", "url(#grad-blue)", "url(#grad-amber)", "url(#grad-red)"]

    gw = cw / len(groups)
    bw = 32
    gap = 6

    for gi, (name, vals) in enumerate(groups):
        cx = x0 + gi * gw + gw / 2
        total_w = len(vals) * bw + (len(vals) - 1) * gap
        start_x = cx - total_w / 2

        for vi, val in enumerate(vals):
            bx = start_x + vi * (bw + gap)
            bh = int(ch * abs(val) / (y_max - y_min))
            if val < 0:
                by = zero_y
                lbl_y = by + bh + 14
                lbl_col = "#047857"
            else:
                by = zero_y - bh
                lbl_y = by - 5
                lbl_col = "#dc2626"

            out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="{bar_colors[vi]}" rx="3" opacity="0.9"/>')
            out.append(f'<text x="{bx+bw/2}" y="{lbl_y}" text-anchor="middle" class="data-label" fill="{lbl_col}">{val:+.1f}%</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+35}" text-anchor="middle" class="axis-label">{name}</text>')

    lx, ly = x0 + 110, h - 14
    legends = [
        ("url(#grad-green)", "使能 5% 活跃度 (空闲突发)"),
        ("url(#grad-blue)", "使能 20% 活跃度 (常规工况)"),
        ("url(#grad-amber)", "使能 50% 活跃度 (平衡工况)"),
        ("url(#grad-red)", "使能 80% 活跃度 (高频计数)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*155}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*155+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(GC_DIR / "gc_total_power_delta.svg", "".join(out))


def gen_gc_power_breakdown():
    w, h = 860, 460
    out = [svg_header(w, h)]
    out.append('<text x="32" y="38" class="title">Sky130 格雷码计数器：四维内部微观功耗精细拆解对比 (Duty = 20%)</text>')
    out.append('<text x="32" y="58" class="subtitle">单位: µW | 纯二进制基准 (Binary N-DFF) vs 原生格雷码 (Gray N-DFF) 在时钟网络、时序单元与组合逻辑上的功耗重构</text>')

    x0, y0, cw, ch = 85, 85, 730, 275
    y_max = 350

    for val in range(0, y_max + 1, 50):
        y = y0 + int(ch * (y_max - val) / y_max)
        out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="grid-line"/>')
        out.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" class="tick-label">{val}</text>')

    # 数据格式: (Scale, Orig_Clock, Orig_Seq, Orig_Comb, Orig_Total, Opt_Clock, Opt_Seq, Opt_Comb, Opt_Total)
    data = [
        ("4-bit", 60.7, 18.8, 7.12, 86.6, 60.9, 17.7, 5.22, 83.9),
        ("8-bit", 66.1, 35.4, 7.26, 109.0, 65.8, 34.4, 13.0, 113.0),
        ("16-bit", 85.5, 68.5, 6.70, 161.0, 77.7, 67.3, 15.9, 161.0),
        ("32-bit", 149.0, 135.0, 6.78, 290.0, 160.0, 133.0, 17.2, 310.0),
    ]

    gw = cw / len(data)
    bw = 48
    gap = 14

    for gi, (name, o_clk, o_seq, o_comb, o_tot, p_clk, p_seq, p_comb, p_tot) in enumerate(data):
        cx = x0 + gi * gw + gw / 2

        # 原始架构柱体 (堆叠: Clock -> Sequential -> Combinational)
        bx_o = cx - bw - gap / 2
        bh_o_clk = int(ch * o_clk / y_max)
        bh_o_seq = int(ch * o_seq / y_max)
        bh_o_comb = int(ch * o_comb / y_max)
        bh_o_tot = int(ch * o_tot / y_max)

        by_o_clk = y0 + ch - bh_o_clk
        by_o_seq = by_o_clk - bh_o_seq
        by_o_comb = by_o_seq - bh_o_comb

        out.append(f'<rect x="{bx_o}" y="{by_o_clk}" width="{bw}" height="{bh_o_clk}" fill="#3b82f6" rx="2" opacity="0.9"/>')
        out.append(f'<rect x="{bx_o}" y="{by_o_seq}" width="{bw}" height="{bh_o_seq}" fill="#93c5fd" rx="2" opacity="0.9"/>')
        out.append(f'<rect x="{bx_o}" y="{by_o_comb}" width="{bw}" height="{bh_o_comb}" fill="#cbd5e1" rx="2" opacity="0.9"/>')
        out.append(f'<text x="{bx_o+bw/2}" y="{y0+ch-bh_o_tot-6}" text-anchor="middle" class="data-label" fill="#1e293b">{o_tot:.0f}</text>')

        # 优化架构柱体
        bx_p = cx + gap / 2
        bh_p_clk = int(ch * p_clk / y_max)
        bh_p_seq = int(ch * p_seq / y_max)
        bh_p_comb = int(ch * p_comb / y_max)
        bh_p_tot = int(ch * p_tot / y_max)

        by_p_clk = y0 + ch - bh_p_clk
        by_p_seq = by_p_clk - bh_p_seq
        by_p_comb = by_p_seq - bh_p_comb

        pct = (p_tot - o_tot) / o_tot * 100
        p_col = "#059669" if pct < 0 else ("#2563eb" if pct == 0 else "#dc2626")

        out.append(f'<rect x="{bx_p}" y="{by_p_clk}" width="{bw}" height="{bh_p_clk}" fill="#0d9488" rx="2" opacity="0.9"/>')
        out.append(f'<rect x="{bx_p}" y="{by_p_seq}" width="{bw}" height="{bh_p_seq}" fill="#5eead4" rx="2" opacity="0.9"/>')
        out.append(f'<rect x="{bx_p}" y="{by_p_comb}" width="{bw}" height="{bh_p_comb}" fill="#fed7aa" rx="2" opacity="0.9"/>')
        out.append(f'<text x="{bx_p+bw/2}" y="{y0+ch-bh_p_tot-6}" text-anchor="middle" class="data-label" fill="{p_col}">{p_tot:.0f} ({pct:+.1f}%)</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+22}" text-anchor="middle" class="axis-label">{name}</text>')
        out.append(f'<text x="{bx_o+bw/2}" y="{y0+ch+36}" text-anchor="middle" class="tick-label">二进制</text>')
        out.append(f'<text x="{bx_p+bw/2}" y="{y0+ch+36}" text-anchor="middle" class="tick-label">格雷码</text>')

    lx, ly = 55, h - 14
    legends = [
        ("#3b82f6", "二进制-时钟网络"),
        ("#93c5fd", "二进制-触发器时序"),
        ("#0d9488", "格雷码-时钟网络"),
        ("#5eead4", "格雷码-触发器时序"),
        ("#fed7aa", "格雷码-次态异或组合"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*155}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*155+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(GC_DIR / "gc_power_breakdown.svg", "".join(out))


def gen_gc_area_breakdown():
    w, h = 840, 440
    out = [svg_header(w, h)]
    out.append('<text x="32" y="38" class="title">Sky130 格雷码计数器：等量 DFF (N vs N) 与次态组合逻辑面积对比</text>')
    out.append('<text x="32" y="58" class="subtitle">单位: um² | 触发器严格等量 (N vs N)；柱体反映格雷码次态前缀异或网络带来的标准单元物理面积开销</text>')

    x0, y0, cw, ch = 85, 85, 710, 265
    y_max = 5000

    for val in range(0, y_max + 1, 1000):
        y = y0 + int(ch * (y_max - val) / y_max)
        out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="grid-line"/>')
        out.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" class="tick-label">{val}</text>')

    # 数据: (Name, Orig_Area, Opt_Area, Orig_DFF, Opt_DFF, Delta_Area_Pct)
    data = [
        ("4-bit", 327.81, 361.60, 4, 4, +10.31),
        ("8-bit", 578.05, 870.84, 8, 8, +50.65),
        ("16-bit", 1098.55, 1900.57, 16, 16, +73.01),
        ("32-bit", 2173.33, 4511.83, 32, 32, +107.59),
    ]

    gw = cw / len(data)
    bw = 45
    gap = 14

    for gi, (name, o_area, p_area, o_dff, p_dff, d_pct) in enumerate(data):
        cx = x0 + gi * gw + gw / 2

        bx_o = cx - bw - gap / 2
        bh_o = int(ch * o_area / y_max)
        by_o = y0 + ch - bh_o
        out.append(f'<rect x="{bx_o}" y="{by_o}" width="{bw}" height="{bh_o}" fill="#64748b" rx="2" opacity="0.85"/>')
        out.append(f'<text x="{bx_o+bw/2}" y="{by_o-6}" text-anchor="middle" class="data-label" fill="#334155">{o_area:.0f}</text>')

        bx_p = cx + gap / 2
        bh_p = int(ch * p_area / y_max)
        by_p = y0 + ch - bh_p
        p_col = "#2563eb"
        out.append(f'<rect x="{bx_p}" y="{by_p}" width="{bw}" height="{bh_p}" fill="{p_col}" rx="2" opacity="0.85"/>')
        out.append(f'<text x="{bx_p+bw/2}" y="{by_p-6}" text-anchor="middle" class="data-label" fill="{p_col}">{p_area:.0f} ({d_pct:+.1f}%)</text>')

        # 标注 DFF 等量
        out.append(f'<rect x="{cx-50}" y="{y0+ch+35}" width="100" height="20" rx="4" fill="#f8fafc" stroke="#cbd5e1"/>')
        out.append(f'<text x="{cx}" y="{y0+ch+49}" text-anchor="middle" class="data-label" fill="#0f172a">DFF: {o_dff} vs {p_dff} (等量)</text>')
        out.append(f'<text x="{cx}" y="{y0+ch+22}" text-anchor="middle" class="axis-label">{name}</text>')

    lx, ly = x0 + 130, h - 14
    legends = [
        ("#64748b", "二进制计数器面积 (进位半加链 um²)"),
        ("#2563eb", "格雷码计数器面积 (异或次态网络增生 um²)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*260}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*260+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(GC_DIR / "gc_area_breakdown.svg", "".join(out))


def gen_gc_timing_delay():
    w, h = 840, 440
    out = [svg_header(w, h)]
    out.append('<text x="32" y="38" class="title">Sky130 格雷码计数器：关键路径延迟与时序建立裕量 (Setup WS) 变化</text>')
    out.append('<text x="32" y="58" class="subtitle">时钟周期: 10.0ns (100MHz) | 次态异或树导致反馈路径延时增加，但 100MHz 下仍保持 4.91ns 以上充裕余量</text>')

    x0, y0, cw, ch = 85, 85, 710, 265
    y_max = 10.0

    for val in range(0, 11, 2):
        y = y0 + int(ch * (y_max - val) / y_max)
        out.append(f'<line x1="{x0}" y1="{y}" x2="{x0+cw}" y2="{y}" class="grid-line"/>')
        out.append(f'<text x="{x0-10}" y="{y+4}" text-anchor="end" class="tick-label">{val}.0ns</text>')

    # 数据: (Name, Orig_Delay, Opt_Delay, Orig_WS, Opt_WS)
    data = [
        ("4-bit", 0.889, 1.218, 8.988, 8.649),
        ("8-bit", 1.166, 2.122, 8.712, 7.747),
        ("16-bit", 1.515, 3.009, 8.360, 6.864),
        ("32-bit", 2.094, 4.956, 7.785, 4.914),
    ]

    gw = cw / len(data)
    bw = 36
    gap = 8

    for gi, (name, o_dly, p_dly, o_ws, p_ws) in enumerate(data):
        cx = x0 + gi * gw + gw / 2

        # 延时柱
        bx1 = cx - 2 * bw - gap
        bh1 = int(ch * o_dly / y_max)
        by1 = y0 + ch - bh1
        out.append(f'<rect x="{bx1}" y="{by1}" width="{bw}" height="{bh1}" fill="#94a3b8" rx="2"/>')
        out.append(f'<text x="{bx1+bw/2}" y="{by1-6}" text-anchor="middle" class="data-label" fill="#475569">{o_dly:.2f}</text>')

        bx2 = cx - bw - gap / 2
        bh2 = int(ch * p_dly / y_max)
        by2 = y0 + ch - bh2
        out.append(f'<rect x="{bx2}" y="{by2}" width="{bw}" height="{bh2}" fill="#f59e0b" rx="2"/>')
        out.append(f'<text x="{bx2+bw/2}" y="{by2-6}" text-anchor="middle" class="data-label" fill="#b45309">{p_dly:.2f}</text>')

        # 建立时间裕量 (WS) 柱
        bx3 = cx + gap / 2
        bh3 = int(ch * o_ws / y_max)
        by3 = y0 + ch - bh3
        out.append(f'<rect x="{bx3}" y="{by3}" width="{bw}" height="{bh3}" fill="#60a5fa" rx="2"/>')
        out.append(f'<text x="{bx3+bw/2}" y="{by3-6}" text-anchor="middle" class="data-label" fill="#1d4ed8">{o_ws:.2f}</text>')

        bx4 = cx + bw + gap
        bh4 = int(ch * p_ws / y_max)
        by4 = y0 + ch - bh4
        out.append(f'<rect x="{bx4}" y="{by4}" width="{bw}" height="{bh4}" fill="#10b981" rx="2"/>')
        out.append(f'<text x="{bx4+bw/2}" y="{by4-6}" text-anchor="middle" class="data-label" fill="#047857">{p_ws:.2f}</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+22}" text-anchor="middle" class="axis-label">{name}</text>')
        out.append(f'<text x="{cx-bw-gap/2}" y="{y0+ch+36}" text-anchor="middle" class="tick-label">延时 (Dly)</text>')
        out.append(f'<text x="{cx+bw+gap/2}" y="{y0+ch+36}" text-anchor="middle" class="tick-label">裕量 (WS)</text>')

    lx, ly = x0 + 60, h - 14
    legends = [
        ("#94a3b8", "二进制-关键路径延时 (ns)"),
        ("#f59e0b", "格雷码-关键路径延时 (ns)"),
        ("#60a5fa", "二进制-Setup Slack (ns)"),
        ("#10b981", "格雷码-Setup Slack (裕量 > 4.9ns, 零违例)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*170}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*170+18}" y="{ly}" class="legend-text" font-size="11px">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(GC_DIR / "gc_timing_delay.svg", "".join(out))


# ==============================================================================
# One-Hot vs Binary MUX Charts
# ==============================================================================

def gen_ohm_total_power_delta():
    """独热编码相较于二进制多路选择器各规模在不同通道切换率下的总功耗相对变化率柱状图"""
    w, h = 880, 480
    out = [svg_header(w, h)]
    out.append(f'<text x="{w/2}" y="36" text-anchor="middle" class="title">Sky130 独热编码相较于二进制多路选择器总功耗相对变化率 (Total Power Delta %)</text>')
    out.append(f'<text x="{w/2}" y="56" text-anchor="middle" class="subtitle">涵盖 4 种通道复用规模 (4/8/16/32-to-1) × 4 种通道切换活跃度 (5%/20%/50%/80%) 全物理后仿签核</text>')

    x0, y0, cw, ch = 80, 80, 740, 320
    # y 轴范围：-10% 到 +5%
    y_min, y_max = -10.0, 5.0
    y_range = y_max - y_min

    def get_y(val):
        return y0 + ch - int((val - y_min) / y_range * ch)

    # 网格线与刻度
    for tick in [-10, -8, -6, -4, -2, 0, 2, 4]:
        ty = get_y(tick)
        cls = "zero-line" if tick == 0 else "grid-line"
        out.append(f'<line x1="{x0}" y1="{ty}" x2="{x0+cw}" y2="{ty}" class="{cls}"/>')
        out.append(f'<text x="{x0-10}" y="{ty+4}" text-anchor="end" class="tick-label">{tick:+d}%</text>')

    # 绘制 0% 平衡线提示
    zero_y = get_y(0)
    out.append(f'<text x="{x0+cw-8}" y="{zero_y-6}" text-anchor="end" font-size="10px" font-weight="600" fill="#475569">0.0% 损益平衡线</text>')

    data = [
        ("4-to-1 MUX", [2.63, 0.00, -1.99, -3.30]),
        ("8-to-1 MUX", [0.00, -0.78, -3.68, -6.21]),
        ("16-to-1 MUX", [-0.54, -1.56, -4.01, -6.07]),
        ("32-to-1 MUX", [2.31, -0.32, -4.24, -8.47]),
    ]

    colors = ["#f59e0b", "#0ea5e9", "#10b981", "#6366f1"]
    gw = cw / len(data)
    bw = 32
    gap = 8

    for gi, (name, vals) in enumerate(data):
        cx = x0 + gi * gw + gw / 2
        for vi, (val, col) in enumerate(zip(vals, colors)):
            bx = cx - 2 * bw - 1.5 * gap + vi * (bw + gap)
            by = get_y(max(0, val))
            bh = abs(get_y(val) - zero_y)
            if bh < 2: bh = 2

            out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="{col}" rx="3"/>')
            ty_text = by - 6 if val >= 0 else by + bh + 12
            out.append(f'<text x="{bx+bw/2}" y="{ty_text}" text-anchor="middle" class="data-label" fill="{col}">{val:+.1f}%</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+22}" text-anchor="middle" class="axis-label">{name}</text>')

    lx, ly = x0 + 100, h - 18
    legends = [
        (colors[0], "通道切换 5% (准静态选通)"),
        (colors[1], "通道切换 20% (偶发轻载切换)"),
        (colors[2], "通道切换 50% (典型计算轮询)"),
        (colors[3], "通道切换 80% (高频突发跳变)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*160}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*160+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(OHM_DIR / "ohm_total_power_delta.svg", "".join(out))


def gen_ohm_power_breakdown():
    """独热编码 vs 二进制多路选择器内部微观功耗精细拆解对比图 (Duty=50%)"""
    w, h = 940, 520
    out = [svg_header(w, h)]
    out.append(f'<text x="{w/2}" y="34" text-anchor="middle" class="title">Sky130 二进制 MUX 树 vs 原生独热 MUX 内部微观功耗拆解对比 (Duty=50%)</text>')
    out.append(f'<text x="{w/2}" y="54" text-anchor="middle" class="subtitle">微观物理分量：时钟网络 (Clock)、触发器时序 (Sequential)、组合逻辑 (Combinational) 与各部分相对变化率</text>')

    x0, y0, cw, ch = 80, 95, 780, 310
    y_max = 750.0

    for tick in range(0, 800, 100):
        ty = y0 + ch - int(ch * tick / y_max)
        out.append(f'<line x1="{x0}" y1="{ty}" x2="{x0+cw}" y2="{ty}" class="grid-line"/>')
        out.append(f'<text x="{x0-10}" y="{ty+4}" text-anchor="end" class="tick-label">{tick} µW</text>')

    data = [
        ("4-to-1 MUX", (63.9, 44.5, 92.7), (64.8, 45.6, 86.7)),
        ("8-to-1 MUX", (65.3, 44.7, 162.0), (63.9, 44.6, 154.0)),
        ("16-to-1 MUX", (66.1, 45.2, 288.0), (64.8, 45.6, 272.0)),
        ("32-to-1 MUX", (66.6, 45.3, 549.0), (65.7, 44.5, 523.0)),
    ]

    gw = cw / len(data)
    bw = 44
    gap = 14

    for gi, (name, orig_parts, opt_parts) in enumerate(data):
        cx = x0 + gi * gw + gw / 2

        tot1 = sum(orig_parts)
        tot2 = sum(opt_parts)
        d_clk = (opt_parts[0] - orig_parts[0]) / orig_parts[0] * 100.0
        d_seq = (opt_parts[1] - orig_parts[1]) / orig_parts[1] * 100.0
        d_comb = (opt_parts[2] - orig_parts[2]) / orig_parts[2] * 100.0
        d_tot = (tot2 - tot1) / tot1 * 100.0

        # 各分量相对变化指标标签 (在每组顶部清晰标明)
        out.append(f'<rect x="{cx-95}" y="{y0-24}" width="190" height="18" rx="4" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1"/>')
        out.append(f'<text x="{cx}" y="{y0-11}" text-anchor="middle" font-size="9.5px" font-weight="600" fill="#334155">ΔComb: <tspan fill="#047857" font-weight="700">{d_comb:+.1f}%</tspan> | ΔSeq: {d_seq:+.1f}% | ΔClk: {d_clk:+.1f}%</text>')

        # 原始柱 (Orig)
        bx1 = cx - bw - gap / 2
        cy1 = y0 + ch
        for vi, (val, col) in enumerate(zip(orig_parts, ["#94a3b8", "#38bdf8", "#f43f5e"])):
            bh = int(ch * val / y_max)
            cy1 -= bh
            out.append(f'<rect x="{bx1}" y="{cy1}" width="{bw}" height="{bh}" fill="{col}"/>')
            if bh >= 16:
                out.append(f'<text x="{bx1+bw/2}" y="{cy1+bh/2+4}" text-anchor="middle" font-size="10px" font-weight="600" fill="#ffffff">{val:.0f}</text>')

        out.append(f'<text x="{bx1+bw/2}" y="{cy1-6}" text-anchor="middle" class="data-label" fill="#475569">{tot1:.1f}</text>')

        # 优化柱 (Opt)
        bx2 = cx + gap / 2
        cy2 = y0 + ch
        for vi, (val, col) in enumerate(zip(opt_parts, ["#64748b", "#0284c7", "#10b981"])):
            bh = int(ch * val / y_max)
            cy2 -= bh
            out.append(f'<rect x="{bx2}" y="{cy2}" width="{bw}" height="{bh}" fill="{col}"/>')
            if bh >= 16:
                out.append(f'<text x="{bx2+bw/2}" y="{cy2+bh/2+4}" text-anchor="middle" font-size="10px" font-weight="600" fill="#ffffff">{val:.0f}</text>')

        out.append(f'<text x="{bx2+bw/2}" y="{cy2-6}" text-anchor="middle" class="data-label" fill="#047857">{tot2:.1f} ({d_tot:+.1f}%)</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+20}" text-anchor="middle" class="axis-label">{name}</text>')
        out.append(f'<text x="{bx1+bw/2}" y="{y0+ch+34}" text-anchor="middle" class="tick-label">二进制</text>')
        out.append(f'<text x="{bx2+bw/2}" y="{y0+ch+34}" text-anchor="middle" class="tick-label" font-weight="600" fill="#047857">独热码</text>')

    lx, ly = x0 + 10, h - 14
    legends = [
        ("#94a3b8", "时钟树功耗 (Clock: ~0%)"),
        ("#38bdf8", "时序触发器功耗 (Seq: ~0%)"),
        ("#f43f5e", "二进制-组合逻辑 (Tree)"),
        ("#10b981", "独热码-组合逻辑 (AND-OR 净降 -4.7% ~ -6.5%)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*195}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*195+18}" y="{ly}" class="legend-text" font-size="11px">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(OHM_DIR / "ohm_power_breakdown.svg", "".join(out))


def gen_ohm_timing_delay():
    """独热编码 vs 二进制多路选择器关键路径延时与建立时间裕量 (Setup WS) 对比图"""
    w, h = 880, 480
    out = [svg_header(w, h)]
    out.append(f'<text x="{w/2}" y="36" text-anchor="middle" class="title">Sky130 独热编码多路选择器关键路径延迟与时序裕量对比</text>')
    out.append(f'<text x="{w/2}" y="56" text-anchor="middle" class="subtitle">打破对数级级联 MUX 树延时瓶颈：32-to-1 下关键路径延迟暴降 -23.6% (5.30ns → 4.05ns)</text>')

    x0, y0, cw, ch = 80, 80, 740, 320
    y_max = 8.0

    for tick in range(0, 9, 1):
        ty = y0 + ch - int(ch * tick / y_max)
        out.append(f'<line x1="{x0}" y1="{ty}" x2="{x0+cw}" y2="{ty}" class="grid-line"/>')
        out.append(f'<text x="{x0-10}" y="{ty+4}" text-anchor="end" class="tick-label">{tick} ns</text>')

    data = [
        ("4-to-1 MUX", 3.334, 2.930, 6.540, 6.937),
        ("8-to-1 MUX", 3.566, 3.350, 6.312, 6.496),
        ("16-to-1 MUX", 4.257, 3.829, 5.616, 6.025),
        ("32-to-1 MUX", 5.299, 4.050, 4.572, 5.813),
    ]

    gw = cw / len(data)
    bw = 34
    gap = 8

    for gi, (name, o_dly, p_dly, o_ws, p_ws) in enumerate(data):
        cx = x0 + gi * gw + gw / 2

        # 延时柱 (Dly)
        bx1 = cx - 2 * bw - gap
        bh1 = int(ch * o_dly / y_max)
        by1 = y0 + ch - bh1
        out.append(f'<rect x="{bx1}" y="{by1}" width="{bw}" height="{bh1}" fill="#94a3b8" rx="2"/>')
        out.append(f'<text x="{bx1+bw/2}" y="{by1-6}" text-anchor="middle" class="data-label" fill="#475569">{o_dly:.2f}</text>')

        bx2 = cx - bw - gap / 2
        bh2 = int(ch * p_dly / y_max)
        by2 = y0 + ch - bh2
        out.append(f'<rect x="{bx2}" y="{by2}" width="{bw}" height="{bh2}" fill="#f59e0b" rx="2"/>')
        out.append(f'<text x="{bx2+bw/2}" y="{by2-6}" text-anchor="middle" class="data-label" fill="#b45309">{p_dly:.2f}</text>')

        # 建立时间裕量 (WS) 柱
        bx3 = cx + gap / 2
        bh3 = int(ch * o_ws / y_max)
        by3 = y0 + ch - bh3
        out.append(f'<rect x="{bx3}" y="{by3}" width="{bw}" height="{bh3}" fill="#60a5fa" rx="2"/>')
        out.append(f'<text x="{bx3+bw/2}" y="{by3-6}" text-anchor="middle" class="data-label" fill="#1d4ed8">{o_ws:.2f}</text>')

        bx4 = cx + bw + gap
        bh4 = int(ch * p_ws / y_max)
        by4 = y0 + ch - bh4
        out.append(f'<rect x="{bx4}" y="{by4}" width="{bw}" height="{bh4}" fill="#10b981" rx="2"/>')
        out.append(f'<text x="{bx4+bw/2}" y="{by4-6}" text-anchor="middle" class="data-label" fill="#047857">{p_ws:.2f}</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+22}" text-anchor="middle" class="axis-label">{name}</text>')
        out.append(f'<text x="{cx-bw-gap/2}" y="{y0+ch+36}" text-anchor="middle" class="tick-label">延迟 (Delay)</text>')
        out.append(f'<text x="{cx+bw+gap/2}" y="{y0+ch+36}" text-anchor="middle" class="tick-label">裕量 (Setup WS)</text>')

    lx, ly = x0 + 40, h - 14
    legends = [
        ("#94a3b8", "二进制-关键路径延时 (ns)"),
        ("#f59e0b", "独热码-关键路径延时 (显著缩短)"),
        ("#60a5fa", "二进制-Setup Slack (ns)"),
        ("#10b981", "独热码-Setup Slack (裕量扩充 > 5.8ns)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*180}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*180+18}" y="{ly}" class="legend-text" font-size="11px">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(OHM_DIR / "ohm_timing_delay.svg", "".join(out))


def gen_ohm_area_breakdown():
    """独热编码 vs 二进制多路选择器物理面积与标准单元门数对比图"""
    w, h = 880, 480
    out = [svg_header(w, h)]
    out.append(f'<text x="{w/2}" y="36" text-anchor="middle" class="title">Sky130 独热编码多路选择器物理面积与标准单元门数对比</text>')
    out.append(f'<text x="{w/2}" y="56" text-anchor="middle" class="subtitle">与或门并行结构消除了多级 MUX 树的级联单元与多级驱动缓冲器，面积全面逆势精简 -3.6% ~ -14.1%</text>')

    x0, y0, cw, ch = 80, 80, 740, 320
    y_max = 6500.0

    for tick in range(0, 7000, 1000):
        ty = y0 + ch - int(ch * tick / y_max)
        out.append(f'<line x1="{x0}" y1="{ty}" x2="{x0+cw}" y2="{ty}" class="grid-line"/>')
        out.append(f'<text x="{x0-10}" y="{ty+4}" text-anchor="end" class="tick-label">{tick} µm²</text>')

    data = [
        ("4-to-1 MUX", 1032.24, 925.89, 113, 88, -10.3),
        ("8-to-1 MUX", 1581.52, 1523.96, 167, 162, -3.6),
        ("16-to-1 MUX", 2871.50, 2670.06, 332, 294, -7.0),
        ("32-to-1 MUX", 5838.10, 5014.81, 738, 624, -14.1),
    ]

    gw = cw / len(data)
    bw = 40
    gap = 14

    for gi, (name, o_area, p_area, o_cnt, p_cnt, delta) in enumerate(data):
        cx = x0 + gi * gw + gw / 2

        # 原始面积
        bx1 = cx - bw - gap / 2
        bh1 = int(ch * o_area / y_max)
        by1 = y0 + ch - bh1
        out.append(f'<rect x="{bx1}" y="{by1}" width="{bw}" height="{bh1}" fill="#94a3b8" rx="2"/>')
        out.append(f'<text x="{bx1+bw/2}" y="{by1-18}" text-anchor="middle" class="data-label" fill="#475569">{o_area:.0f}µm²</text>')
        out.append(f'<text x="{bx1+bw/2}" y="{by1-6}" text-anchor="middle" font-size="10px" fill="#64748b">({o_cnt}门)</text>')

        # 优化面积
        bx2 = cx + gap / 2
        bh2 = int(ch * p_area / y_max)
        by2 = y0 + ch - bh2
        out.append(f'<rect x="{bx2}" y="{by2}" width="{bw}" height="{bh2}" fill="#10b981" rx="2"/>')
        out.append(f'<text x="{bx2+bw/2}" y="{by2-18}" text-anchor="middle" class="data-label" fill="#047857">{p_area:.0f}µm²</text>')
        out.append(f'<text x="{bx2+bw/2}" y="{by2-6}" text-anchor="middle" font-size="10px" font-weight="700" fill="#047857">({delta:+.1f}%)</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+22}" text-anchor="middle" class="axis-label">{name}</text>')
        out.append(f'<text x="{bx1+bw/2}" y="{y0+ch+36}" text-anchor="middle" class="tick-label">二进制 MUX</text>')
        out.append(f'<text x="{bx2+bw/2}" y="{y0+ch+36}" text-anchor="middle" class="tick-label">独热 MUX</text>')

    lx, ly = x0 + 100, h - 14
    legends = [
        ("#94a3b8", "二进制 MUX 树物理标准单元面积 (µm²)"),
        ("#10b981", "独热并行与或 MUX 物理标准单元面积 (全面精简)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*300}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*300+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(OHM_DIR / "ohm_area_breakdown.svg", "".join(out))


# ==============================================================================
# Bus-Invert (BI) Coding Charts
# ==============================================================================

def load_bi_results():
    p = BASE_IMG_DIR.parent.parent / "eval_workspace" / "bus_invert" / "sweep_results.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def gen_bi_total_power_delta():
    """Sky130 总线反转编码 (Bus-Invert) 各规模在不同翻转活跃度下的总功耗相对变化率柱状图"""
    w, h = 880, 480
    out = [svg_header(w, h)]
    out.append(f'<text x="{w/2}" y="36" text-anchor="middle" class="title">Sky130 总线反转编码 (Bus-Invert) 各规模在不同翻转活跃度下的总功耗相对变化率</text>')
    out.append(f'<text x="{w/2}" y="56" text-anchor="middle" class="subtitle">涵盖 4 种总线位宽 (8b/16b/32b/64b) × 4 种翻转活跃度 (15%/35%/60%/85%) 全物理后仿签核</text>')

    x0, y0, cw, ch = 80, 80, 740, 320
    y_min, y_max = 0.0, 130.0
    y_range = y_max - y_min

    def get_y(val):
        return y0 + ch - int((val - y_min) / y_range * ch)

    # 网格线与刻度
    for tick in range(0, 140, 20):
        ty = get_y(tick)
        cls = "zero-line" if tick == 0 else "grid-line"
        out.append(f'<line x1="{x0}" y1="{ty}" x2="{x0+cw}" y2="{ty}" class="{cls}"/>')
        out.append(f'<text x="{x0-10}" y="{ty+4}" text-anchor="end" class="tick-label">+{tick}%</text>')

    zero_y = get_y(0)
    out.append(f'<text x="{x0+cw-8}" y="{zero_y-6}" text-anchor="end" font-size="10px" font-weight="600" fill="#475569">0.0% 损益基准线 (Raw Bus)</text>')

    data = [
        ("8-bit 总线", [35.06, 56.07, 67.51, 59.09]),
        ("16-bit 总线", [33.44, 59.45, 79.90, 67.39]),
        ("32-bit 总线", [43.25, 70.96, 92.08, 75.84]),
        ("64-bit 总线", [52.99, 86.47, 110.46, 88.37]),
    ]

    colors = ["#f59e0b", "#0ea5e9", "#10b981", "#6366f1"]
    gw = cw / len(data)
    bw = 32
    gap = 8

    for gi, (name, vals) in enumerate(data):
        cx = x0 + gi * gw + gw / 2
        for vi, (val, col) in enumerate(zip(vals, colors)):
            bx = cx - 2 * bw - 1.5 * gap + vi * (bw + gap)
            by = get_y(val)
            bh = zero_y - by
            if bh < 2: bh = 2

            out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="{col}" rx="3"/>')
            out.append(f'<text x="{bx+bw/2}" y="{by-6}" text-anchor="middle" class="data-label" fill="{col}">+{val:.1f}%</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+22}" text-anchor="middle" class="axis-label">{name}</text>')

    lx, ly = x0 + 80, h - 18
    legends = [
        (colors[0], "翻转率 15% (低频轻载传输)"),
        (colors[1], "翻转率 35% (典型随机数据流)"),
        (colors[2], "翻转率 60% (高频密集跳变)"),
        (colors[3], "翻转率 85% (反转拐点效应显著)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*170}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*170+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(BI_DIR / "bi_total_power_delta.svg", "".join(out))


def gen_bi_power_breakdown():
    """Sky130 原始总线 vs 总线反转 (Bus-Invert) 内部微观功耗拆解对比 (Toggle Rate=60%)"""
    w, h = 940, 520
    out = [svg_header(w, h)]
    out.append(f'<text x="{w/2}" y="34" text-anchor="middle" class="title">Sky130 原始总线 vs 总线反转 (Bus-Invert) 内部微观功耗拆解对比 (Toggle Rate=60%)</text>')
    out.append(f'<text x="{w/2}" y="54" text-anchor="middle" class="subtitle">微观物理分量：时钟网络 (Clock)、触发器时序 (Sequential)、组合逻辑编码/解码 (Combinational) 与各部分相对变化率</text>')

    x0, y0, cw, ch = 80, 95, 780, 310
    y_max = 3500.0

    for tick in range(0, 4000, 500):
        ty = y0 + ch - int(ch * tick / y_max)
        out.append(f'<line x1="{x0}" y1="{ty}" x2="{x0+cw}" y2="{ty}" class="grid-line"/>')
        out.append(f'<text x="{x0-10}" y="{ty+4}" text-anchor="end" class="tick-label">{tick} µW</text>')

    # 格式: (scale_name, (orig_clock, orig_seq, orig_comb), (opt_clock, opt_seq, opt_comb))
    data = [
        ("8-bit 总线", (73.4, 94.0, 29.2), (81.9, 111.0, 137.0)),
        ("16-bit 总线", (165.0, 190.0, 58.5), (151.0, 212.0, 379.0)),
        ("32-bit 总线", (337.0, 377.0, 119.0), (349.0, 421.0, 825.0)),
        ("64-bit 总线", (522.0, 762.0, 242.0), (497.0, 830.0, 1900.0)),
    ]

    gw = cw / len(data)
    bw = 44
    gap = 16

    for gi, (name, orig_parts, opt_parts) in enumerate(data):
        cx = x0 + gi * gw + gw / 2

        tot1 = sum(orig_parts)
        tot2 = sum(opt_parts)
        d_clk = (opt_parts[0] - orig_parts[0]) / orig_parts[0] * 100.0
        d_seq = (opt_parts[1] - orig_parts[1]) / orig_parts[1] * 100.0
        d_comb = (opt_parts[2] - orig_parts[2]) / orig_parts[2] * 100.0
        d_tot = (tot2 - tot1) / tot1 * 100.0

        # 各分量相对变化指标标签 (在每组顶部清晰标明)
        out.append(f'<rect x="{cx-95}" y="{y0-24}" width="190" height="18" rx="4" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1"/>')
        out.append(f'<text x="{cx}" y="{y0-11}" text-anchor="middle" font-size="9.5px" font-weight="600" fill="#334155">ΔComb: <tspan fill="#b45309" font-weight="700">+{d_comb:.0f}%</tspan> | ΔSeq: {d_seq:+.0f}% | ΔClk: {d_clk:+.0f}%</text>')

        # 原始柱 (Orig)
        bx1 = cx - bw - gap / 2
        cy1 = y0 + ch
        for vi, (val, col) in enumerate(zip(orig_parts, ["#94a3b8", "#38bdf8", "#f43f5e"])):
            bh = int(ch * val / y_max)
            cy1 -= bh
            out.append(f'<rect x="{bx1}" y="{cy1}" width="{bw}" height="{bh}" fill="{col}"/>')
            if bh >= 16:
                out.append(f'<text x="{bx1+bw/2}" y="{cy1+bh/2+4}" text-anchor="middle" font-size="10px" font-weight="600" fill="#ffffff">{val:.0f}</text>')

        out.append(f'<text x="{bx1+bw/2}" y="{cy1-6}" text-anchor="middle" class="data-label" fill="#475569">{tot1:.0f}</text>')

        # 优化柱 (Opt)
        bx2 = cx + gap / 2
        cy2 = y0 + ch
        for vi, (val, col) in enumerate(zip(opt_parts, ["#64748b", "#0284c7", "#f59e0b"])):
            bh = int(ch * val / y_max)
            cy2 -= bh
            out.append(f'<rect x="{bx2}" y="{cy2}" width="{bw}" height="{bh}" fill="{col}"/>')
            if bh >= 16:
                out.append(f'<text x="{bx2+bw/2}" y="{cy2+bh/2+4}" text-anchor="middle" font-size="10px" font-weight="600" fill="#ffffff">{val:.0f}</text>')

        out.append(f'<text x="{bx2+bw/2}" y="{cy2-6}" text-anchor="middle" class="data-label" fill="#b45309">{tot2:.0f} (+{d_tot:.1f}%)</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+20}" text-anchor="middle" class="axis-label">{name}</text>')
        out.append(f'<text x="{bx1+bw/2}" y="{y0+ch+34}" text-anchor="middle" class="tick-label">原始总线</text>')
        out.append(f'<text x="{bx2+bw/2}" y="{y0+ch+34}" text-anchor="middle" class="tick-label" font-weight="600" fill="#b45309">Bus-Invert</text>')

    lx, ly = x0 + 15, h - 14
    legends = [
        ("#94a3b8", "时钟网络 (Clock: ~0%)"),
        ("#38bdf8", "时序寄存器 (Seq: +9%~+18%)"),
        ("#f43f5e", "原始总线组合逻辑 (Comb)"),
        ("#f59e0b", "Bus-Invert 组合逻辑 (PopCount 加法树暴增 +369%~+685%)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*205}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*205+18}" y="{ly}" class="legend-text" font-size="11px">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(BI_DIR / "bi_power_breakdown.svg", "".join(out))


def gen_bi_switching_reduction():
    """Sky130 总线反转编码 (Bus-Invert) 动态翻转功耗相对变化率柱状图"""
    w, h = 880, 480
    out = [svg_header(w, h)]
    out.append(f'<text x="{w/2}" y="36" text-anchor="middle" class="title">Sky130 总线反转编码 (Bus-Invert) 动态翻转功耗相对变化率 (Switching Power Delta %)</text>')
    out.append(f'<text x="{w/2}" y="56" text-anchor="middle" class="subtitle">片上短线场景下编码器/解码器内部节点的高频翻转导致翻转功耗激增，85% 翻转率因反转截断呈现回落拐点</text>')

    x0, y0, cw, ch = 80, 80, 740, 320
    y_min, y_max = 0.0, 450.0
    y_range = y_max - y_min

    def get_y(val):
        return y0 + ch - int((val - y_min) / y_range * ch)

    for tick in range(0, 500, 50):
        ty = get_y(tick)
        cls = "zero-line" if tick == 0 else "grid-line"
        out.append(f'<line x1="{x0}" y1="{ty}" x2="{x0+cw}" y2="{ty}" class="{cls}"/>')
        out.append(f'<text x="{x0-10}" y="{ty+4}" text-anchor="end" class="tick-label">+{tick}%</text>')

    zero_y = get_y(0)
    out.append(f'<text x="{x0+cw-8}" y="{zero_y-6}" text-anchor="end" font-size="10px" font-weight="600" fill="#475569">0.0% 损益基准线</text>')

    data = [
        ("8-bit 总线", [110.0, 193.1, 264.0, 256.7]),
        ("16-bit 总线", [132.2, 224.9, 319.5, 291.4]),
        ("32-bit 总线", [134.5, 226.6, 321.7, 288.0]),
        ("64-bit 总线", [194.6, 294.4, 405.6, 345.2]),
    ]

    colors = ["#f59e0b", "#0ea5e9", "#10b981", "#6366f1"]
    gw = cw / len(data)
    bw = 32
    gap = 8

    for gi, (name, vals) in enumerate(data):
        cx = x0 + gi * gw + gw / 2
        for vi, (val, col) in enumerate(zip(vals, colors)):
            bx = cx - 2 * bw - 1.5 * gap + vi * (bw + gap)
            by = get_y(val)
            bh = zero_y - by
            if bh < 2: bh = 2

            out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="{col}" rx="3"/>')
            out.append(f'<text x="{bx+bw/2}" y="{by-6}" text-anchor="middle" class="data-label" fill="{col}">+{val:.0f}%</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+22}" text-anchor="middle" class="axis-label">{name}</text>')

    lx, ly = x0 + 80, h - 18
    legends = [
        (colors[0], "翻转率 15%"),
        (colors[1], "翻转率 35%"),
        (colors[2], "翻转率 60% (翻转功耗增量峰值)"),
        (colors[3], "翻转率 85% (反转机制触发，翻转率回落)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*170}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*170+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(BI_DIR / "bi_switching_reduction.svg", "".join(out))


def gen_bi_area_timing_tradeoff():
    """Sky130 总线反转架构物理标准单元面积与时序延迟/裕量权衡图"""
    w, h = 880, 480
    out = [svg_header(w, h)]
    out.append(f'<text x="{w/2}" y="36" text-anchor="middle" class="title">Sky130 总线反转架构物理面积开销与关键路径时序延迟对比</text>')
    out.append(f'<text x="{w/2}" y="56" text-anchor="middle" class="subtitle">汉明统计加法树与异或阵列导致面积激增 +90.5% ~ +122.8%，64b 下关键路径延迟逼近时钟周期 (8.79ns)</text>')

    x0, y0, cw, ch = 80, 80, 740, 320
    y_max = 14000.0

    for tick in range(0, 16000, 2000):
        ty = y0 + ch - int(ch * tick / y_max)
        out.append(f'<line x1="{x0}" y1="{ty}" x2="{x0+cw}" y2="{ty}" class="grid-line"/>')
        out.append(f'<text x="{x0-10}" y="{ty+4}" text-anchor="end" class="tick-label">{tick} µm²</text>')

    data = [
        ("8-bit 总线", 696.9, 1327.5, 61, 129, 0.605, 4.685, 90.5),
        ("16-bit 总线", 1391.3, 2854.0, 119, 307, 0.603, 5.201, 105.1),
        ("32-bit 总线", 2796.4, 5954.5, 242, 633, 0.630, 7.377, 112.9),
        ("64-bit 总线", 5469.0, 12182.9, 524, 1438, 0.627, 8.791, 122.8),
    ]

    gw = cw / len(data)
    bw = 42
    gap = 14

    for gi, (name, o_area, p_area, o_cnt, p_cnt, o_dly, p_dly, delta_pct) in enumerate(data):
        cx = x0 + gi * gw + gw / 2

        # 原始面积柱
        bx1 = cx - bw - gap / 2
        bh1 = int(ch * o_area / y_max)
        by1 = y0 + ch - bh1
        out.append(f'<rect x="{bx1}" y="{by1}" width="{bw}" height="{bh1}" fill="#94a3b8" rx="2"/>')
        out.append(f'<text x="{bx1+bw/2}" y="{by1-18}" text-anchor="middle" class="data-label" fill="#475569">{o_area:.0f}µm²</text>')
        out.append(f'<text x="{bx1+bw/2}" y="{by1-6}" text-anchor="middle" font-size="10px" fill="#64748b">({o_cnt}门/{o_dly:.2f}ns)</text>')

        # 优化面积柱
        bx2 = cx + gap / 2
        bh2 = int(ch * p_area / y_max)
        by2 = y0 + ch - bh2
        out.append(f'<rect x="{bx2}" y="{by2}" width="{bw}" height="{bh2}" fill="#f59e0b" rx="2"/>')
        out.append(f'<text x="{bx2+bw/2}" y="{by2-18}" text-anchor="middle" class="data-label" fill="#b45309">{p_area:.0f}µm²</text>')
        out.append(f'<text x="{bx2+bw/2}" y="{by2-6}" text-anchor="middle" font-size="10px" font-weight="700" fill="#b45309">(+{delta_pct:.1f}%/{p_dly:.2f}ns)</text>')

        out.append(f'<text x="{cx}" y="{y0+ch+22}" text-anchor="middle" class="axis-label">{name}</text>')
        out.append(f'<text x="{bx1+bw/2}" y="{y0+ch+36}" text-anchor="middle" class="tick-label">原始总线</text>')
        out.append(f'<text x="{bx2+bw/2}" y="{y0+ch+36}" text-anchor="middle" class="tick-label">Bus-Invert</text>')

    lx, ly = x0 + 80, h - 14
    legends = [
        ("#94a3b8", "原始总线物理标准单元面积 (µm²) 与延时 (ns)"),
        ("#f59e0b", "Bus-Invert 物理面积 (面积增量 +90%~+123% / 延时显著延长)"),
    ]
    for li, (col, text) in enumerate(legends):
        out.append(f'<rect x="{lx+li*330}" y="{ly-10}" width="14" height="10" rx="2" fill="{col}"/>')
        out.append(f'<text x="{lx+li*330+18}" y="{ly}" class="legend-text">{text}</text>')

    out.append(svg_footer())
    write_svg_and_validate(BI_DIR / "bi_area_timing_tradeoff.svg", "".join(out))


def main():
    print("Generating validated, categorized SVG comparison charts...")
    gen_cg_total_power_delta()
    gen_cg_power_breakdown()
    gen_cg_area_breakdown()
    gen_oi_total_power_delta()
    gen_oi_comb_power_reduction()
    gen_oi_activity_impact()
    gen_dg_total_power_delta()
    gen_dg_area_overhead()
    gen_dg_comb_power_reduction()
    gen_dg_tap_ranking_breakdown()
    gen_gc_total_power_delta()
    gen_gc_power_breakdown()
    gen_gc_area_breakdown()
    gen_gc_timing_delay()
    gen_ohm_total_power_delta()
    gen_ohm_power_breakdown()
    gen_ohm_timing_delay()
    gen_ohm_area_breakdown()
    gen_bi_total_power_delta()
    gen_bi_power_breakdown()
    gen_bi_switching_reduction()
    gen_bi_area_timing_tradeoff()
    print("All charts generated and validated successfully!")


if __name__ == "__main__":
    main()



