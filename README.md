# RTL 变换自动化物理评估基座（Evaluation Platform）架构与使用文档

## 1. 流水线设计目标与架构

本自动化评估基座旨在提供一个**高保真度、解耦化、支持多 Verilog 源文件与任意 RTL 低功耗变换（如时钟门控、操作数隔离、状态机重编码等）的无人工干预评估闭环**。

流水线依次执行：形式逻辑等价性验证（LEC） -> 全流程物理实现（PnR） -> 门级波形仿真（Simulation） -> 签核级寄生功耗分析（STA Signoff），最终输出量化对比指标。

                +--------------------+
                |  Original RTL Set  |
                |  Optimized RTL Set |
                +---------+----------+
                          |
                          v
         [Step 1] Formal Logic Equivalence (LEC)  ---> [Yosys SAT] (失败立即熔断)
                          |
                          v
         [Step 2] Full Physical PnR (LibreLane)   ---> Sky130 HD (Classic 80-Stage)
                  (via AppImage DevShell)
                          |
                 +--------+--------+
                 |                 |
                 v                 v
           Post-PnR Netlist    Parasitic SPEF
             (nl.v / 纯逻辑)      (nom_tt Corner)
                 |                 |
                 v                 |
         [Step 3] Gate-Level Sim   |              ---> [Icarus Verilog + VVP]
                 |                 |
                 v                 |
          Switching Activity (VCD) |
                 |                 |
                 +--------+--------+
                          |
                          v
         [Step 4] Signoff Power Evaluation        ---> [OpenSTA + SPEF 反标]
                          |
                          v
         [Step 5] Metrics Diff Table Generation

---

## 2. 工具链与依赖环境

* **物理后端（PnR）**：LibreLane / OpenLane（通过 AppImage 环境启动）
  * **调用环境入口**：`~/librelane/librelane-devshell-x86_64.AppImage librelane <args>`
* **形式验证（LEC）**：Yosys (0.62+) SAT 解算器
* **门级仿真引擎**：Icarus Verilog (`iverilog` 2012 标准) + `vvp`
* **功耗签核引擎**：OpenSTA (2.7.0+)
* **目标 PDK**：SkyWater 130nm (`sky130A`)，标准单元库采用 `sky130_fd_sc_hd` (High Density)

---

## 3. 用例包目录结构契约

为实现评估基座与具体测试模块的解耦，所有待测用例存放在 `benchmark_cases/<case_name>/` 下：

```text
benchmark_cases/<case_name>/
├── meta.json             # 案例元数据配置（模块名、时钟、时序约束、源码列表）
├── src_orig/             # 原始 RTL 源文件集合（支持多文件）
│   ├── top.v
│   └── sub_block.v
├── src_opt/              # 优化后 RTL 源文件集合（支持多文件）
│   ├── top.v
│   └── sub_block.v
└── tb/
    └── tb_top.v          # 专用测试平台（实例化顶层为 u_dut 并导出 VCD）

```

### `meta.json` 格式规范

```json
{
  "design_name": "reg_bank",
  "clock_port": "clk",
  "clock_period_ns": 10.0,
  "clock_uncertainty_ns": 0.25,
  "clock_transition_ns": 0.15,
  "output_load_pf": 0.033442,
  "input_delay_ns": 2.0,
  "output_delay_ns": 2.0,
  "core_utilization": 25,
  "target_density_pct": 35,
  "sources_orig": [],
  "sources_opt": []
}

```

*提示：当 `sources_orig` 或 `sources_opt` 为空时，平台自动收集目录下所有 `*.v` 和 `*.sv` 文件。*

---

## 4. 核心执行机制与避坑准则

**Step 1: 多文件形式等价性验证 (Formal LEC)**

* 脚本自动加载 `src_orig` 与 `src_opt` 的全部 Verilog，分别赋予 `<top>_orig` 与 `<top>_opt` 实体名。
* 将时钟展平为寄存器状态空间（`clk2fflogic`），利用 SAT 归纳法比对 Miter。若优化引入了功能性 Bug，流水线立即中断。

**Step 2: 物理实现全流程 (PnR Flow)**

* **启动方式**：统一通过 `~/librelane/librelane-devshell-x86_64.AppImage python evaluate_case.py` 驱动评估，内部工具链自动识别并共享 devshell 环境。
* **动态 SDC 注入**：根据 `meta.json` 自动生成合规 `target.sdc`，并在 LibreLane 配置中显式传入 `"PNR_SDC_FILE"` 与 `"SIGNOFF_SDC_FILE"`，消除 OpenROAD 的 fallback 警告。
* **完整跑通依赖保护**：必须配置 `"RUN_KLAYOUT_STREAMOUT": True` 与 `"RUN_MAGIC_STREAMOUT": True`，**严禁使用 `--skip Magic.StreamOut`**。跳过 Magic 版图导出将破坏下游 `Magic.WriteLEF` 与天线检查步骤的输入链。
* **网表选型注意点**：
  * `final/pnl/*.pnl.v` 包含 `.VPWR` 与 `.VGND`，仅用于 LVS/SPICE。
  * **门级仿真与 OpenSTA 签核必须提取 `final/nl/*.nl.v`（No-Power 纯逻辑门级网表）**。

**Step 3: 案例仿真与活跃度波形提取 (Simulation & VCD)**

* `iverilog` 编译参数**仅传 `-g2012 -DFUNCTIONAL`**。
* **切勿手动传递 `-DUNIT_DELAY=0` 或 `-DUNIT_DELAY=""`**，避免与 Sky130 库自带的延迟修饰冲突产生语法解析错误。
* `tb_top.v` 需以固定例化名 `u_dut` 实例化顶层模块，并调用 `$dumpvars(0, tb_top.u_dut)` 输出 `<tag>_activity.vcd`。提供标准模板样例：`templates/tb_top.v.template`。

**Step 4: 签核级功耗分析 (Signoff Power Evaluation)**
**Step 4: 多维签核级评估 (Signoff Power, Timing & Area)**

* **VCD 作用域反标**：OpenSTA 调用 `read_vcd -scope tb_top/u_dut <vcd>`，使用标准斜杠路径确保引脚活动数大于 0。
* **黑盒模块预载**：在读入网表前读入 `sky130_fd_sc_hd__blackbox.v`，防止物理 Filler/Tapcell 单元产生黑盒警告。
* **单角点直接分析**：通过 `read_liberty` 载入典型工艺角库（无需声明未定义的 `-corner` 标签），使用原生 `report_power` 输出功耗拆解。
* **功耗与时序联合签核**：OpenSTA 加载纯逻辑网表与 SPEF，以标准斜杠路径反标 `tb_top/u_dut` 作用域，分别输出功耗报表 `*_power.rpt` 及最长关键路径时序报表 `*_timing.rpt`。
* **物理面积与利用率提取**：从 LibreLane `runs/<tag>/final/metrics.json` 精准提取门级物理实现的实际面积数据，输出独立的物理复杂度报表 `*_area.rpt`。

**Step 5: 综合 PPA 报告与设计变换关系分析 (PPA Summary & Trade-off Analysis)**

* 自动对比 Power（功耗）、Timing（时序）、Area（面积）与 Energy（能效 PDP）四大类核心指标。
* 深入分析“功耗-面积代价比”、“功耗-时序敏感度”以及“功耗延迟积（PDP）”，输出完整的 Markdown 与 JSON 综合报告。

---

## 5. 快速上手
## 5. 工作空间目录结构契约 (Workspace Layout)

评估基座生成的所有产物完全解耦分层存放，保持根目录整洁：

```text
eval_workspace/<case_name>/
├── sim/                          # 专用仿真目录
│   ├── sim_orig.vvp              # 原始网表仿真可执行二进制
│   ├── orig_activity.vcd         # 原始设计活动波形
│   ├── sim_opt.vvp               # 优化网表仿真可执行二进制
│   └── opt_activity.vcd          # 优化设计活动波形
├── reports/                      # 专用报告与签核汇总目录
│   ├── orig_power.rpt            # 原始设计功耗详报 (含 Group 拆解)
│   ├── opt_power.rpt             # 优化设计功耗详报
│   ├── orig_timing.rpt           # 原始设计时序关键路径详报
│   ├── opt_timing.rpt            # 优化设计时序关键路径详报
│   ├── orig_area.rpt             # 原始设计物理面积与单元统计详报
│   ├── opt_area.rpt              # 优化设计物理面积与单元统计详报
│   ├── ppa_summary.json          # 全维度 PPA 结构化指标数据
│   └── ppa_summary.md            # 综合汇总报告（含功耗/时序/面积 Trade-off 关系深度分析）
├── formal/                       # 形式等价性验证工程目录
│   └── lec.ys
├── orig/                         # 原始设计 LibreLane PnR 物理工程
├── opt/                          # 优化设计 LibreLane PnR 物理工程
└── logs/<timestamp>/             # 集中会话日志（保留历史时间戳归档）
    └── overall_pipeline.log
```

---

## 6. 快速上手

推荐使用 AppImage 启动环境后调用评估主脚本：

```bash
# 评估单模块时钟门控案例 (reg_bank)
# 案例 1：单模块宽总线时钟门控经典优化案例 (reg_bank)
~/librelane/librelane-devshell-x86_64.AppImage python evaluate_case.py --case-dir ./benchmark_cases/reg_bank_case

# 评估多源文件层次化低功耗案例 (multi_file_alu)
# 案例 2：多文件组合逻辑操作数隔离优化案例 (alu_operand_isolation)
~/librelane/librelane-devshell-x86_64.AppImage python evaluate_case.py --case-dir ./benchmark_cases/alu_operand_isolation_case

# 案例 3：【负优化对照组】窄位宽时钟门控开销倒挂案例 (multi_file_alu)
~/librelane/librelane-devshell-x86_64.AppImage python evaluate_case.py --case-dir ./benchmark_cases/multi_file_alu_case
```

> **提示**：主脚本内建自适应环境探测机制。若在宿主直接运行 `python evaluate_case.py --case-dir ...`，脚本将自动检测并自托管重定向至 AppImage devshell 执行。

执行完毕后，控制台及集中日志目录 `eval_workspace/<case_name>/logs/<timestamp>/overall_pipeline.log` 将生成最终签核对比表：
### 6. 基准案例签核功耗与效果对比
### 基准案例签核与效果对比

| Power Metric     | Original RTL     | Optimized RTL    | Delta (%)       |
| :--------------- | :--------------- | :--------------- | :-------------- |
| **Internal**     | 2.73e-04 W       | 1.81e-04 W       | -33.70%         |
| **Switching**    | 5.84e-05 W       | 3.05e-05 W       | -47.77%         |
| **Leakage**      | 2.89e-09 W       | 1.88e-09 W       | -34.95%         |
| **Total**        | 3.32e-04 W       | 2.12e-04 W       | -36.14%         |
| 测试案例 | 变换技术 | 主要收益来源 | Total 功耗变化 | 核心结论 |
| :--- | :--- | :--- | :--- | :--- |
| **`reg_bank_case`** | 32-bit 时钟门控 | 时序逻辑时钟树关断 | **-36.14%** (332µW → 212µW) | 纯寄存器宽总线场景下门控收益显著 |
| **`alu_operand_isolation_case`** | 操作数隔离 (Operand Isolation) | 组合逻辑杂散翻转阻断 | **-38.76%** (725µW → 444µW) | 针对深层组合逻辑 (占比 76%) 的最优低功耗架构 |
| **`multi_file_alu_case`** | 16-bit 窄位宽时钟门控 | *(负优化对照组)* | **+4.17%** (696µW → 725µW) | 独立生成的时钟树开销超过 16-bit 节省量，演示平衡位宽未达标现象 |
| 测试案例 | 变换技术 | Total 功耗变化 | 面积变化 (Stdcell) | 时序裕量变化 (Setup WS) | 核心结论与 Trade-off 关系 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`reg_bank_case`** | 32-bit 时钟门控 | **-36.14%** (332µW → 212µW) | **-7.35%** (2060µm² → 1909µm²) | -2.71 ns | 宽总线寄存器门控实现功耗与面积双重节省，裕量仍满足约束 |
| **`alu_operand_isolation_case`** | 操作数隔离 (Operand Isolation) | **-38.76%** (725µW → 444µW) | +3.52% (4582µm² → 4743µm²) | **+1.83 ns** (关键路径改善) | 仅消耗 +3.5% 面积增量换取 -38.8% 功耗降低，且解耦关键路径改善时序，PDP 提升 47.8% |
| **`multi_file_alu_case`** | 16-bit 窄位宽时钟门控 | **+4.17%** (696µW → 725µW) | +3.55% (4587µm² → 4750µm²) | +0.58 ns | *(负优化对照组)* 独立时钟树与门控逻辑开销超过 16-bit 收益，且未阻断前级 75% 组合功耗 |



