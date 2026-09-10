# RTL 变换自动化物理评估基座（Evaluation Platform）架构与使用文档

## 1. 流水线设计目标与整体架构

本自动化物理评估基座旨在为数字 IC 设计与低功耗 RTL 变换研究提供**高保真度、模块化解耦、支持多源文件与全流程物理实现的无人工干预评估闭环**。

评估流水线通过 Yosys、LibreLane (OpenLane 2)、Icarus Verilog 与 OpenSTA 协同运作，依次完成：**形式逻辑等价性验证（LEC） -> 全流程物理实现（PnR） -> 门级真实波形仿真（Simulation） -> 寄生参数反标多维签核（STA Signoff: Power, Timing, Area, Activity） -> PPA 综合评估与权衡分析（Report）**。

```text
                  +-----------------------------------+
                  |  Original & Optimized Verilog Set  |
                  +-----------------+-----------------+
                                    |
                                    v
   [Step 1: Formal LEC]  --------> Yosys SAT 解算器 (功能不符立即熔断)
                                    |
                                    v
   [Step 2: Full PnR]    --------> LibreLane 80-Stage 物理实现 (Sky130 HD)
                                    |
                         +----------+----------+
                         |                     |
                         v                     v
                   Post-PnR Netlist       Parasitic SPEF
                    (nl.v 纯逻辑)         (nom_tt Corner)
                         |                     |
                         v                     |
   [Step 3: Gate-Sim]   Icarus Verilog + VVP   |
                         | (注入动态 +EN_DUTY)   |
                         v                     |
                 Switching Activity (VCD)      |
                         |                     |
                         +----------+----------+
                                    |
                                    v
   [Step 4: Signoff]    --------> OpenSTA 联合签核 (时序/功耗/面积/引脚翻转密度)
                                    |
                                    v
   [Step 5: Report]     --------> 结构化 JSON + 多维 PPA Trade-off 关系深度分析
```

---

## 2. 工程代码模块化分层架构

为提升平台的可维护性与扩展性，代码库划分为明确的职能层次：**顶层脚本存放在 `script/`**，**项目文档与研报归档于 `doc/`**，**核心物理实现引擎沉淀于 `src/`**：

```text
RTL_Transformation/
├── script/                     # 【命令行执行脚本】
│   ├── evaluate_case.py        # 单案例全流程自动化物理评估 CLI
│   ├── sweep_clock_gating.py   # 门控时钟 Scale × Activity 二维扫描 CLI
│   └── sweep_operand_isolation.py # 操作数隔离 Scale × Valid Duty × Activity 三维扫描 CLI
├── doc/                        # 【项目文档与研究报告】
│   ├── Evaluation_Platform.md  # 通用多文件 RTL 变换评估基座架构规范
│   ├── clock_gating_study_report.md # 门控时钟多维度敏感度与物理损益平衡研报
│   └── operand_isolation_study_report.md # 操作数隔离多维度影响因素与损益临界研报
├── src/                        # 【核心功能实现包】
│   ├── common/                 # 基础设施与通用辅助
│   │   ├── env.py              # AppImage DevShell 自托管环境探测与命令重定向
│   │   ├── logger.py           # 集中式日志配置与工作空间清理
│   │   ├── pdk.py              # Sky130 PDK 与标准单元库路径自适应定位
│   │   └── case_loader.py      # 用例元数据校验与多文件源码解析
│   ├── core/                   # 物理评估 5 大核心流水线阶段
│   │   ├── formal.py           # Step 1: Yosys 层次化形式等价性验证 (LEC)
│   │   ├── pnr.py              # Step 2: LibreLane 80-Stage 物理实现与网表/SPEF 提取
│   │   ├── sim.py              # Step 3: Icarus Verilog 门级仿真与动态 VCD 生成
│   │   ├── signoff.py          # Step 4: OpenSTA 静态时序、功耗与引脚翻转活动度签核
│   │   └── report.py           # Step 5: 全维度 PPA 报表生成与多维权衡深度分析
│   └── analysis/               # 高级研究实验与多维参数扫描
│       ├── sweep_clock_gating.py # 门控时钟全物理后仿扫描引擎与收支平衡模型构建
│       └── sweep_operand_isolation.py # 操作数隔离全物理后仿扫描引擎与收支平衡模型构建
├── cases/                      # 【规范化分类低功耗测试用例库】
│   ├── clock_gating/           # 门控时钟用例 (8b, 16b, 32b, 64b)
│   ├── operand_isolation/      # 操作数隔离用例 (alu_8b, alu_16b, alu_32b, alu_64b)
│   └── contrast_cases/         # 负优化与工程对照组 (multi_file_alu)
├── eval_workspace/             # 【物理运行与签核工作空间】(按用例与功能解耦)
├── templates/                  # 测试平台与约束参考模板
└── README.md                   # 项目总览文档
```

---

## 3. 工具链与依赖环境

* **物理后端（PnR）**：LibreLane / OpenLane（通过 AppImage 环境无侵入运行）
  * **入口**：`~/librelane/librelane-devshell-x86_64.AppImage`
* **形式验证（LEC）**：Yosys (0.62+) SAT 解算器
* **门级仿真引擎**：Icarus Verilog (`iverilog` 2012 标准) + `vvp`
* **静态时序与功耗签核引擎**：OpenSTA (2.7.0+)
* **目标 PDK**：SkyWater 130nm (`sky130A`)，标准单元库采用 `sky130_fd_sc_hd` (High Density)

---

## 4. 测试用例目录规范契约 (`cases/`)

所有待测用例统一按照分类组织在 `cases/<category>/<case_name>/` 下，每个案例保持完备自包含：

```text
cases/<category>/<case_name>/
├── meta.json             # 案例元数据配置（模块名、时钟周期、时序约束、源文件列表）
├── src_orig/             # 原始 RTL 源文件集合（支持多文件）
│   ├── top.v
│   └── sub_block.v
├── src_opt/              # 优化后 RTL 源文件集合（支持多文件）
│   ├── top.v
│   └── sub_block.v
└── tb/
    └── tb_top.v          # 专用测试平台（固定例化为 u_dut，支持 +EN_DUTY 传参并转储 VCD）
```

### `meta.json` 规范定义

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
  "sources_orig": ["reg_bank.v"],
  "sources_opt": ["reg_bank.v"]
}
```

*注：若 `sources_orig` 或 `sources_opt` 为空数组，平台将自动收集目录下所有 `*.v` 和 `*.sv` 文件。*

---

## 5. 核心执行流程与关键实现细节

### Step 1: 形式逻辑等价性验证 (Formal LEC)
* 脚本自动加载 `src_orig` 与 `src_opt` 的全部 Verilog，分别赋予 `<top>_orig` 与 `<top>_opt` 实体名。
* 将时钟展平为寄存器状态空间（`clk2fflogic`），利用 SAT 归纳法比对 Miter。若优化引入了功能性 Bug，流水线立即中断。

### Step 2: 物理实现全流程 (PnR Flow)
* **启动方式**：统一通过 AppImage 驱动，内部工具链自动识别并共享 devshell 环境。
* **动态 SDC 注入**：根据 `meta.json` 自动生成合规 `target.sdc`，并在 LibreLane 配置中显式传入 `"PNR_SDC_FILE"` 与 `"SIGNOFF_SDC_FILE"`，消除 OpenROAD 的 fallback 警告。
* **完整跑通依赖保护**：必须配置 `"RUN_KLAYOUT_STREAMOUT": True` 与 `"RUN_MAGIC_STREAMOUT": True`，**严禁使用 `--skip Magic.StreamOut`**。跳过 Magic 版图导出将破坏下游 `Magic.WriteLEF` 与天线检查步骤的输入链。
* **网表选型注意点**：
  * `final/pnl/*.pnl.v` 包含 `.VPWR` 与 `.VGND`，仅用于 LVS/SPICE。
  * **门级仿真与 OpenSTA 签核必须提取 `final/nl/*.nl.v`（No-Power 纯逻辑门级网表）**。
* **寄生参数提取**：提取 `final/spef/nom/*.spef` 用于下游时序功耗反标。

### Step 3: 案例仿真与活跃度波形提取 (Simulation & VCD)
* `iverilog` 编译参数**仅传 `-g2012 -DFUNCTIONAL`**。
* **切勿手动传递 `-DUNIT_DELAY=0` 或 `-DUNIT_DELAY=""`**，避免与 Sky130 库自带的延迟修饰冲突产生语法解析错误。
* `tb_top.v` 需以固定例化名 `u_dut` 实例化顶层模块，并调用 `$dumpvars(0, tb_top.u_dut)` 输出 `<tag>_activity.vcd`。提供标准模板样例：`templates/tb_top.v.template`。
* 支持 `$value$plusargs("EN_DUTY=%d", en_duty)` 动态参数注入，无需重编即可测试多种活跃度工况。

### Step 4: 多维签核级评估 (Signoff Power, Timing & Area)
* **VCD 作用域反标**：OpenSTA 调用 `read_vcd -scope tb_top/u_dut <vcd>`，使用标准斜杠路径确保引脚活动数大于 0。
* **黑盒模块预载**：在读入网表前读入 `sky130_fd_sc_hd__blackbox.v`，防止物理 Filler/Tapcell 单元产生黑盒警告。
* **单角点直接分析**：通过 `read_liberty` 载入典型工艺角库（无需声明未定义的 `-corner` 标签），使用原生 `report_power` 输出功耗拆解。
* **引脚/信号翻转活动度安全导出**：采用稳定、安全的 Tcl 属性内省脚本遍历实例 Pin，提取 `activity` 属性（翻转密度 `trans/s`、静态占空比 `Static Prob`），生成 `reports/{tag}_activity.rpt`。
* **物理面积与利用率提取**：从 LibreLane `runs/<tag>/final/metrics.json` 精准提取门级物理实现的实际面积数据，输出独立的物理复杂度报表 `*_area.rpt`。

### Step 5: 综合 PPA 报告与设计变换关系分析 (PPA Summary & Trade-off Analysis)
* 自动对比 Power（功耗）、Timing（时序）、Area（面积）与 Energy（能效 PDP）四大类核心指标。
* 深入分析“功耗-面积代价比”、“功耗-时序敏感度”以及“功耗延迟积（PDP）”，输出完整的 Markdown 与 JSON 综合报告。

---

## 6. 工作空间目录结构契约 (Workspace Layout)

运行生成的产物完全解耦分层存放在 `eval_workspace/<category>/<case_name>/` 下：

```text
eval_workspace/<category>/<case_name>/
├── sim/                          # 专用仿真目录 (.vvp 二进制与 .vcd 波形)
│   ├── sim_orig.vvp              # 原始网表仿真二进制
│   ├── orig_activity.vcd         # 原始设计活动波形
│   ├── sim_opt.vvp               # 优化网表仿真二进制
│   └── opt_activity.vcd          # 优化设计活动波形
├── reports/                      # 专用报告与签核目录
│   ├── orig_power.rpt            # 原始设计功耗详报 (含 Group 拆解)
│   ├── opt_power.rpt             # 优化设计功耗详报
│   ├── orig_timing.rpt           # 原始设计时序关键路径详报
│   ├── opt_timing.rpt            # 优化设计时序关键路径详报
│   ├── orig_area.rpt             # 原始设计物理面积与单元统计详报
│   ├── opt_area.rpt              # 优化设计物理面积与单元统计详报
│   ├── orig_activity.rpt         # 原始设计引脚级翻转密度详报
│   ├── opt_activity.rpt          # 优化设计引脚级翻转密度详报
│   ├── ppa_summary.json          # 全维度 PPA 结构化指标数据
│   └── ppa_summary.md            # 综合汇总报告（含功耗/时序/面积 Trade-off 关系深度分析）
├── formal/                       # 形式验证工程目录 (lec.ys)
├── orig/                         # 原始设计 LibreLane PnR 物理工程
├── opt/                          # 优化设计 LibreLane PnR 物理工程
└── logs/<timestamp>/             # 集中会话历史归档日志
    └── overall_pipeline.log
```

---

## 7. 快速上手

推荐直接运行 `script/` 目录下的 CLI 入口脚本（内建自适应环境探测机制，若在宿主系统直接运行，脚本将自动检测并自托管重定向至 AppImage devshell 执行）：

```bash
# 1. 评估 32 位宽寄存器时钟门控经典正收益案例
./script/evaluate_case.py --case-dir cases/clock_gating/reg_bank_32b

# 2. 评估 32 位组合逻辑操作数隔离案例
./script/evaluate_case.py --case-dir cases/operand_isolation/alu_operand_isolation

# 3. 评估 16 位 ALU 门控时钟开销倒挂对照案例 (负优化)
./script/evaluate_case.py --case-dir cases/contrast_cases/multi_file_alu

# 4. 运行门控时钟二维全物理参数化扫描与收支平衡研究 (Scale × Activity)
./script/sweep_clock_gating.py

# 5. 运行操作数隔离三维全物理参数化扫描与损益临界模型研究 (Scale × Valid Duty × Data Activity)
./script/sweep_operand_isolation.py
```

执行完毕后，控制台及集中日志目录 `eval_workspace/<case_path>/logs/<timestamp>/overall_pipeline.log` 将输出最终多维签核报告与 Trade-off 关系分析。

---

## 8. 代表性低功耗变换物理签核对比

| 测试案例 | 变换技术 | Total 功耗变化 | 面积变化 (Stdcell) | 时序裕量变化 (Setup WS) | 核心物理结论与 Trade-off 关系 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`reg_bank_32b`** | 32-bit 时钟门控 | **-28.57%** (336µW → 240µW) | **-7.35%** (2060µm² → 1909µm²) | -2.71 ns | 宽总线寄存器门控实现功耗与面积双重节省，裕量充裕完全合规 |
| **`alu_operand_isolation`** | 操作数隔离 (Operand Isolation) | **-38.76%** (725µW → 444µW) | **+3.52%** (4582µm² → 4743µm²) | **+1.83 ns** (关键路径改善) | 仅消耗 +3.5% 面积增量换取 -38.8% 功耗降低，解耦关键路径改善时序，PDP 提升 47.8% |
| **`multi_file_alu`** | 16-bit 窄位宽时钟门控 | **+4.17%** (696µW → 725µW) | **+3.55%** (4587µm² → 4750µm²) | +0.58 ns | *(负优化对照组)* 独立时钟树与门控逻辑开销反超 16-bit 收益，且未阻断前级 75% 组合杂散功耗 |

---

## 9. 门控时钟影响因素研究成果 (Breakeven Threshold)

通过 `script/sweep_clock_gating.py` 对 4 种位宽规模（8b/16b/32b/64b）与 4 种使能活跃度（5%/20%/50%/80%）共 16 组矩阵进行了全物理后仿扫描（完整技术研报详见 [`doc/clock_gating_study_report.md`](doc/clock_gating_study_report.md)）：

### 总功耗变化率二维矩阵 (Total Power Delta %)

| 寄存器规模 (Scale) | 使能 5% 活跃度 | 使能 20% 活跃度 | 使能 50% 活跃度 | 使能 80% 活跃度 | 面积变化 (Area Delta) | 时序裕量变化 (Setup WS) | 损益状态判定 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **8-bit 寄存器组** | <span style="color:red">**+26.13%** (负优化)</span> | <span style="color:red">**+33.61%** (负优化)</span> | <span style="color:red">**+51.52%** (负优化)</span> | <span style="color:red">**+70.50%** (负优化)</span> | **+14.19%** (膨胀) | **-3.68 ns** | **全活跃度区间净亏损** |
| **16-bit 寄存器组** | **-9.52%** (微弱收益) | **-1.06%** (临界平衡) | <span style="color:red">**+16.19%** (负优化)</span> | <span style="color:red">**+34.82%** (负优化)</span> | **0.00%** (持平) | **-3.66 ns** | **收支平衡临界过渡点** |
| **32-bit 寄存器组** | **-39.04%** (显著收益) | **-24.33%** (显著收益) | **-6.27%** (小幅收益) | <span style="color:red">**+11.34%** (负优化)</span> | **-7.35%** (缩小) | **-3.63 ns** | **实用正收益区（活跃度 <60%）** |
| **64-bit 寄存器组** | **-67.12%** (巨大收益) | **-53.09%** (巨大收益) | **-29.59%** (大幅收益) | **-5.87%** (仍有收益) | **-13.89%** (显著缩小) | **-3.45 ns** | **宽数据通路全活跃度净收益** |

### 定量临界结论
1. **损益平衡临界位宽 (Breakeven Bitwidth)**：在典型稀疏使能下，**临界位宽约为 16-bit**。8-bit 及以下小寄存器因时钟树分支与 ICG 开销反噬，物理门控必然导致负优化；
2. **使能活跃度临界点 (Activity Threshold)**：16-bit 临界活跃度约为 **20%**；32-bit 临界活跃度提升至 **60% ~ 70%**；64-bit 即使在 80% 高频更新下仍能保持正向收益；
3. **时序裕量代价 (Timing Penalty)**：插入全局 ICG 单元引入了时钟门控建立时间检查约束，使能到达 ICG 的延迟较 MUX 路径增加，各规模 Setup WS 恒定缩减约 **3.5 ns ~ 3.7 ns**，但各规模余量仍维持在 **+3.0 ns 以上**（周期 10.0ns），零时序违例；
4. **工程指导原则**：RTL 变换需设立门限过滤（$N \ge 16$），多路窄寄存器应在顶层聚合共享 ICG，并依据 VCD 反标实际活动度决定门控策略。

---

## 10. 操作数隔离多维度影响因素研究成果 (Scale × Duty × Activity)

通过 `script/sweep_operand_isolation.py` 对 4 种位宽（8b/16b/32b/64b）× 4 种有效概率（5%/20%/50%/80%）× 3 种总线活跃度（10%/30%/60%）共 **48 组三维全物理后仿矩阵** 进行了签核评估（完整技术研报详见 [`doc/operand_isolation_study_report.md`](doc/operand_isolation_study_report.md)）：

### 高活跃度 (Activity = 60%) 总功耗变化率与 PPA
| 运算规模 (Scale) | 有效计算 5% (95% 空闲) | 有效计算 20% (80% 空闲) | 有效计算 50% (50% 空闲) | 有效计算 80% (20% 空闲) | 面积增量 (Area Delta) | 时序裕量变化 (Setup WS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **8-bit ALU** | **-42.47%** | **-19.17%** | +3.64% | +7.23% | +3.11% | **-0.05 ns** |
| **16-bit ALU** | **-48.79%** | **-20.50%** | +6.92% | +10.30% | +3.52% | **+0.79 ns** |
| **32-bit ALU** | **-51.19%** | **-21.85%** | +6.92% | +10.69% | +4.27% | **-0.36 ns** |
| **64-bit ALU** | **-54.44%** | **-24.71%** | +4.04% | +7.66% | +3.03% | **+0.50 ns** |

### 定量临界模型与物理结论
1. **纯组合功耗削减率**：在空闲突发场景（Valid=5%）下，组合逻辑功耗最高可直接削减 **-56.9% ~ -71.9%**；
2. **临界空闲率判定**：只有当计算单元空闲时间占比超过 **25% ~ 30%**（即 Valid Duty $\le 70\%$）且总线具有中高频跳变（Activity $\ge 30\%$）时，操作数隔离方能体现净节能收益；
3. **物理面积与时序代价**：操作数隔离在前级输入端串联隔离门，带来 **+3.0% ~ +4.3%** 的额外标准单元面积；在 8b/32b 下产生 0.05~0.36ns 门级延时，而在 16b/64b 下因闲置状态全零钳位促使后端重构进位链与缓冲树，时序裕量反而逆势改善 **+0.50 ns ~ +0.79 ns**。

---

## 11. 详细技术文档与报告链接

- [通用多文件 RTL 变换自动化评估基座架构规范](doc/Evaluation_Platform.md)
- [门控时钟多维度敏感度与物理损益平衡定量分析报告](doc/clock_gating_study_report.md)
- [操作数隔离多维度影响因素与损益临界模型深度研报](doc/operand_isolation_study_report.md)
