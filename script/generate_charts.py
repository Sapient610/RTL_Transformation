#!/usr/bin/env python3
"""
Generate publication-grade, beautifully styled SVG comparison charts for all
RTL Transformation study reports in doc/images/ organized by subcategory:
- doc/images/clock_gating/
- doc/images/operand_isolation/
- doc/images/data_gating/
"""

import os
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_IMG_DIR = Path(__file__).resolve().parent.parent / "doc" / "images"
CG_DIR = BASE_IMG_DIR / "clock_gating"
OI_DIR = BASE_IMG_DIR / "operand_isolation"
DG_DIR = BASE_IMG_DIR / "data_gating"

for d in [CG_DIR, OI_DIR, DG_DIR]:
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
    print("All charts generated and validated successfully!")


if __name__ == "__main__":
    main()
