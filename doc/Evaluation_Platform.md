# 通用多文件 RTL 变换自动化物理评估基座架构规范 (Evaluation Platform Specification)

## 1. 流水线设计目标与整体架构

本自动化物理评估基座（Evaluation Platform）旨在为数字集成电路设计及低功耗 RTL 变换研究提供**模块化解耦、高鲁棒性、支持任意多源 Verilog 模块与全流程物理实现的高保真度无人工干预评估闭环**。

传统 RTL 阶段的功耗估算往往依赖理想线网模型或前仿逻辑翻转，无法真实反映物理布局布线后的寄生 RC 分布、时钟树缓冲器功耗、局部拥塞引起的走线绕行以及标准单元驱动选型变化。本评估基座将形式验证、80 阶段工业级物理实现、门级真实后仿与寄生反标签核紧密串联，形成严密的端到端物理验证与评估流水线：

```text
                  +-----------------------------------------+
                  |    Original & Optimized Verilog Set     |
                  +--------------------+--------------------+
                                       |
                                       v
   [Step 1: Formal LEC]  ----------> Yosys SAT 解算器 (功能等价性严格熔断)
                                       |
                                       v
   [Step 2: Full PnR]    ----------> LibreLane 80-Stage 物理实现全流程 (Sky130 HD)
                                       |
                          +------------+------------+
                          |                         |
                          v                         v
                   Post-PnR Netlist          Parasitic SPEF
                    (nl.v 纯逻辑网表)         (nom_tt Corner 典型角点)
                          |                         |
                          v                         |
   [Step 3: Gate-Sim]    Icarus Verilog + VVP       |
                          | (注入动态 +EN_DUTY)     |
                          v                         |
                  Switching Activity (VCD)          |
                          |                         |
                          +------------+------------+
                                       |
                                       v
   [Step 4: Signoff]     ----------> OpenSTA 联合签核 (时序/功耗/面积/引脚翻转密度)
                                       |
                                       v
   [Step 5: Report]      ----------> 结构化 JSON + 多维 PPA Trade-off 关系深度分析
```

---

## 2. 用例目录规范契约 (Case Structure)

评估基座与具体的电路设计、激励完全解耦。所有测试用例统一组织在 `cases/<category>/<case_name>/` 目录下，保持完备的自包含性：

```text
cases/<category>/<case_name>/
├── meta.json             # 案例元数据配置（顶层模块名、时钟周期、时序约束、源文件列表）
├── src_orig/             # 原始 RTL 源文件集合（支持多个 .v / .sv 文件）
│   ├── top.v
│   └── sub_blocks.v
├── src_opt/              # 优化后的 RTL 源文件集合（支持多个 .v / .sv 文件）
│   ├── top.v
│   └── sub_blocks.v
└── tb/
    └── tb_top.v          # 专用测试平台（固定例化为 u_dut，支持参数动态注入与 VCD 转储）
```

### `meta.json` 规范定义

每个案例必须在根目录下提供 `meta.json`，配置如下电气与实现参数：

```json
{
  "design_name": "top_module_name",
  "clock_port": "clk",
  "clock_period_ns": 10.0,
  "clock_uncertainty_ns": 0.25,
  "clock_transition_ns": 0.15,
  "output_load_pf": 0.033442,
  "input_delay_ns": 2.0,
  "output_delay_ns": 2.0,
  "core_utilization": 25,
  "target_density_pct": 35,
  "sources_orig": ["top.v", "sub_blocks.v"],
  "sources_opt": ["top.v", "sub_blocks.v"]
}
```

*说明：若 `sources_orig` 或 `sources_opt` 为空数组，评估基座将自动遍历加载对应目录下所有的 `*.v` 与 `*.sv` 文件。*

---

## 3. 代码模块化分层架构 (`src/`)

为保证平台具备工业级可扩展性，全部执行引擎与辅助模块严格解耦分层：

```text
src/
├── common/                     # 【基础设施支持】
│   ├── env.py                  # AppImage DevShell 自托管环境探测与命令执行包装
│   ├── logger.py               # 集中式时间戳日志管理与历史归档
│   ├── pdk.py                  # Sky130 PDK 与高密度标准单元库自适应路径探测
│   └── case_loader.py          # 用例元数据校验与多文件源码解析
├── core/                       # 【核心物理流水线 5 大阶段】
│   ├── formal.py               # Step 1: Yosys 层次化形式等价性验证 (Formal LEC)
│   ├── pnr.py                  # Step 2: LibreLane 80-Stage 物理实现与网表/SPEF 提取
│   ├── sim.py                  # Step 3: Icarus Verilog 门级仿真与动态翻转波形转储
│   ├── signoff.py              # Step 4: OpenSTA 静态时序、功耗与引脚翻转密度签核
│   └── report.py               # Step 5: 全维度 PPA 汇总报表与 Trade-off 关系深度分析
└── analysis/                   # 【高级研究实验与多维参数扫描】
    ├── sweep_clock_gating.py   # 门控时钟 Scale × Activity 二维全物理扫描引擎
    ├── sweep_operand_isolation.py # 操作数隔离 Scale × Valid Duty × Activity 三维全物理扫描引擎
    ├── sweep_data_gating.py    # FIR 滤波器数据门控多维参数化扫描引擎
    └── sweep_gray_counter.py   # 格雷码计数器 Scale × Activity 全物理扫描引擎
```

---

## 4. 后端 EDA 工具链默认模式、参数配置与约束规范矩阵

为确保跨用例、跨变换技术的评估结果具备客观一致性与绝对可比性，平台在各阶段预设了严密的默认工作模式与参数配置：

### 4.1 PDK 与物理库标准选型

| 配置项 | 默认配置值 | 规范说明与工程考量 |
| :--- | :--- | :--- |
| **目标 PDK 制程** | `sky130A` | SkyWater 130nm 混合信号 CMOS 典型制程 |
| **标准单元库** | `sky130_fd_sc_hd` | High-Density 高密度标准单元库（7-track 架构，高度 2.72µm，5 层金属） |
| **签核工艺角 (PVT)** | `nom_tt_025C_1v80` | 典型工艺角（TT 晶体管模型、1.80V 核心供电、25℃ 环境温度） |
| **时序/功耗 Liberty 库** | `sky130_fd_sc_hd__tt_025C_1v80.lib` | 提供标准单元非线性延迟模型 (NLDM)、引脚电容与纳瓦级动态/静态功耗查找表 |
| **动态仿真模型库** | `primitives.v` + `sky130_fd_sc_hd.v` | Icarus Verilog 门级仿真所必需的底层晶体管开关原语与标准单元功能行为模型 |
| **物理黑盒抑制网表** | `sky130_fd_sc_hd__blackbox.v` | 包含 Tapcell、Filler、Decap 等物理单元空壳定义，预载以规避 OpenSTA 黑盒告警 |

---

### 4.2 默认 SDC 时序约束与电气环境规范

所有用例统一注入基于 100MHz 标称工况的高保真数字系统时序与驱动负载约束：

| SDC 参数项 | 默认取值 | SDC 命令实现 | 规范说明与设计意图 |
| :--- | :---: | :--- | :--- |
| **时钟端口名 (`clock_port`)** | `"clk"` | `create_clock [get_ports clk] ...` | 顶层时钟网络输入主端口 |
| **时钟周期 (`clock_period_ns`)** | `10.0 ns` | `-period 10.0` | 标称目标主频 100 MHz |
| **时钟不确定度 (`clock_uncertainty_ns`)** | `0.25 ns` | `set_clock_uncertainty 0.25 [get_clocks clk]` | 时钟抖动 (Jitter) 与偏斜 (Skew) 预留预算（占周期 2.5%） |
| **时钟转换时间 (`clock_transition_ns`)** | `0.15 ns` | `set_clock_transition 0.15 [get_clocks clk]` | 标称时钟沿 Slew 速率 (150 ps) |
| **输入建立延迟 (`input_delay_ns`)** | `2.0 ns` | `set_input_delay -max 2.0 -clock clk [all_inputs -no_clocks]` | 外部输入路径延时上限预算（占周期 20%） |
| **输出下游延迟 (`output_delay_ns`)** | `2.0 ns` | `set_output_delay -max 2.0 -clock clk [all_outputs]` | 外部输出接口下游建立时间预算（占周期 20%） |
| **输出负载容抗 (`output_load_pf`)** | `0.033442 pF` | `set_load 0.033442 [all_outputs]` | 约 33.44 fF，等效于驱动 4 个标准负载单元 (`sky130_fd_sc_hd__inv_4` 输入电容) |
| **SDC 绑定机制** | 双向显式绑定 | `"PNR_SDC_FILE"`, `"SIGNOFF_SDC_FILE"` | 显式绑定本次生成的 `target.sdc`，规避 OpenROAD 默认降级回退告警 |

---

### 4.3 形式逻辑等价性验证默认工作模式 (Step 1: Yosys SAT)

* **执行引擎**：Yosys 0.62+ 原生内建 SAT-Solver。
* **语言前端**：`read_verilog -sv`（强制遵循 SystemVerilog 2012 前端语法规范，支持接口与多维数组）。
* **状态与时钟展平抽象**：
  * `proc`：将 RTL 级过程块（`always @`）展平转换为内部 RTLIL 布尔算子与锁存/触发结构；
  * `clk2fflogic`：将时钟边沿触发触发器（DFF）转为形式验证等效的状态转移方程网络。
* **Miter 结构与求解**：
  * 分别读取原始与优化源文件，重命名顶层为 `<top>_orig` 与 `<top>_opt`；
  * `equiv_make` 将两者同名输入并联、输出异或，生成比对 Miter 双端口网络；
  * `equiv_simple`：进行结构同构与组合逻辑直接规约；
  * `equiv_induct`：利用 K-归纳法（Temporal Induction）求解时序循环与状态机等价性。
* **熔断机制**：`equiv_status -assert` 遇单 bit 不匹配立即退出并抛出异常，强行熔断流水线以保护后端物理算力。

---

### 4.4 物理后端实现默认模式与参数矩阵 (Step 2: LibreLane / OpenLane)

LibreLane 驱动完整 80-Stage 物理设计全流程，各项关键阶段的默认模式与工程策略如下：

| 设计阶段 / 工具 | 核心控制参数 | 默认取值 | 工程策略与物理意义 |
| :--- | :--- | :---: | :--- |
| **逻辑综合与映射**<br>(Yosys + ABC) | `SYNTH_STRATEGY`<br>`ABC_AREA`<br>`ABC_SCRIPT` | `"AREA_0"`<br>`True`<br>标准优化流 | 面积优先技术映射。执行 `fx, mfs, strash, balance, drw, amap` 流程，平衡门数与延时 |
| **版图规划**<br>(OpenROAD Floorplan) | `FP_SIZING`<br>`FP_CORE_UTIL`<br>`FP_ASPECT_RATIO` | `"relative"`<br>`25` (%)<br>`1` (1:1) | 相对尺寸自动推导。设定核心利用率 25%（预留 75% 走线与缓冲器空间，避免拥塞），生成正方形 Die |
| **IO 引脚摆放**<br>(OpenROAD IO Place) | `FP_IO_MODE`<br>`FP_PIN_ORDER_CFG` | 自动周围分布<br>自适应分配 | 在芯片外围均匀间隔摆放引脚，规避引脚局部高密度交叉重叠导致的布线死锁 |
| **电源网络构建**<br>(OpenROAD PDN) | `PDN_CFG`<br>`FP_PDN_RAILS` | 标准网格<br>`met4 / met1` | 垂直电源条带走 `met4`，标准单元供电轨走 `met1`，满足 IR-Drop 压降与 EM 电迁移安全裕度 |
| **全局与详细布局**<br>(RePlAce & OpenDP) | `PL_TARGET_DENSITY_PCT`<br>`PL_BASIC_PLACEMENT` | `35` (%)<br>`False` | 目标布局密度限制在 35%，防止局部热点；OpenDP 强制进行 `unithd` site 对齐与合法化 (Legalization) |
| **时钟树综合**<br>(TritonCTS) | `CTS_CLK_BUFFERS`<br>`CTS_MAX_SLEW` | `clkbuf / clkinv`<br>`< 0.75 ns` | 选用 Sky130 专用平衡时钟缓冲器/反相器树，控制全芯片各叶子端最大转换时间与偏斜 |
| **后时钟时序重构**<br>(OpenROAD Resizer) | `RUN_POST_CTS_RESIZER_TIMING` | **`False` (强制关闭)** | **关键控制点**：CTS 后关闭逻辑重构与单元合并，严防工具拆解或破坏由 RTL 精心构建的数据门控与操作数隔离拓扑；保持时间修复 (`repair_design -hold`) 正常开启 |
| **全局与详细布线**<br>(FastRoute & TritonRoute) | `ROUTING_CORES`<br>`MIN_ROUTING_LAYER`<br>`MAX_ROUTING_LAYER` | `auto`<br>`met1`<br>`met5` | 利用 5 层全金属工艺自动收敛布线，多轮迭代消除 DRC 违例（短路/开路/最小线宽/最小间距） |
| **版图输出与完整性**<br>(KLayout & Magic) | `RUN_KLAYOUT_STREAMOUT`<br>`RUN_MAGIC_STREAMOUT` | **`True` (必须开启)**<br>**`True` (必须开启)** | **关键依赖保护**：生成 GDSII 与 LEF 产物，维持下游天线规则检查与版图抽取输入链完备，**严禁跳过** |
| **物理验证提速开关**<br>(DRC / LVS) | `RUN_KLAYOUT_DRC`<br>`RUN_MAGIC_DRC`<br>`RUN_LVS` | **`False`**<br>**`False`**<br>**`False`** | 在功能评估阶段默认旁路耗时的独立物理验证，将单次全流程耗时压缩 75% 以上 |
| **输出交付物规范** | `Netlist`<br>`SPEF`<br>`Metrics` | `final/nl/<top>.nl.v`<br>`final/spef/nom/*.spef`<br>`final/metrics.json` | 提取纯逻辑 No-Power 网表（严禁使用带 `VPWR/VGND` 的 `pnl.v` 供仿真使用）；提取典型角点 SPEF 与结构化物理指标 |

---

### 4.5 门级动态仿真默认模式与传参规范 (Step 3: Icarus Verilog)

* **编译参数**：`iverilog -g2012 -DFUNCTIONAL primitives.v sky130_fd_sc_hd.v <nl.v> tb_top.v -o <vvp_path>`
* **严禁传参**：切勿人为传递 `-DUNIT_DELAY=0` 或 `-DUNIT_DELAY=""`（会导致 Sky130 库内部宏语法解析错误引发 `syntax error`）。
* **运行与动态激励传参**：`vvp <vvp_path> +VCD_FILE=<vcd_path> [+EN_DUTY=<int>] [+DATA_ACT=<int>]`
* **波形转储契约**：用例的 `tb_top.v` 必须将 DUT 严格实例化为 `u_dut`，并在代码中执行：
  ```verilog
  $dumpfile(vcd_file);
  $dumpvars(0, tb_top.u_dut);
  ```
  严格限定转储层级，杜绝测试平台辅助信号与时钟发生器污染被测核心的翻转活动度。

---

### 4.6 签核级多维分析默认模式与命令规范 (Step 4: OpenSTA Signoff)

* **执行引擎**：原生 OpenSTA 2.7.0+。
* **层次作用域路径**：使用标准正斜杠层级 `read_vcd -scope tb_top/u_dut <vcd_file>`，确保反标引脚计数必须大于 0。
* **黑盒定义注入**：在 `read_verilog` 网表前，预先载入 PDK 官方提供的 `sky130_fd_sc_hd__blackbox.v`，消除物理单元 `Creating black box` 警告。
* **单角点直接签核**：通过 `read_liberty <SCL__tt_025C_1v80.lib>` 载入基准库（无需带未声明的 `-corner` 标签）。
* **高精度功耗拆解**：调用原生 `report_power` 输出 `Sequential`、`Combinational`、`Clock`、`Total` 四大类别的 `Internal`、`Switching`、`Leakage` 功耗。
* **最坏路径时序分析**：
  * `report_checks -path_delay max -format full_clock_expanded -digits 3` 输出建立时间最长路径、时钟偏斜、转换时间与关键数据到达时间；
  * `report_worst_slack -max` / `report_worst_slack -min` / `report_tns` 全面签核 Setup WS、Hold WS 与总负松弛度 TNS。
* **引脚/信号翻转密度内省**：
  * 采用 Tcl 脚本遍历 `[get_ports *]` 与 `[get_pins *]`，读取 `activity` 属性（翻转密度 `Transition Density (trans/s)`、静态高电平概率 `Static Prob`），生成完整的全芯片翻转分布详报 `reports/{tag}_activity.rpt`。

---

## 5. 关键工程机制与避坑准则

### 5.1 80-Stage 完整依赖链保护机制
* **问题现象**：若在运行 LibreLane 时试图通过 `--skip Magic.StreamOut` 或 `--skip Magic.WriteLEF` 节约时间，后续步骤会因找不到必需的物理 GDSII 版图而相继抛出：
  `WriteLEF: missing required input 'gds'` 以及 `CheckDesignAntennaProperties: missing required input 'lef'`。
* **工程准则**：必须完整保留全部 80 阶段流水线，在配置中强制声明 `"RUN_KLAYOUT_STREAMOUT": True` 与 `"RUN_MAGIC_STREAMOUT": True`。

### 5.2 纯逻辑网表 (`nl.v`) vs 物理电源网表 (`pnl.v`)
* **问题现象**：LibreLane 在 `final/pnl/` 目录下生成的网表包含电源引脚绑定（如 `.VPWR(VPWR), .VGND(VGND)`）。若将此网表传给 Icarus Verilog 进行门级仿真，仿真器将因缺少电源网络模型或供电未赋初值而崩溃或产生大面积 `x` 不定态。
* **工程准则**：下游门级仿真与 OpenSTA 签核必须严格使用 `final/nl/<top>.nl.v`（纯逻辑 No-Power 网表），将仿真与物理电源引脚解耦。

### 5.3 Sky130 延迟模型兼容性与 `UNIT_DELAY` 陷阱
* **问题现象**：在某些老旧教程中常建议使用 `-DUNIT_DELAY=0`。但在 SkyWater 130nm 库实现中，`sky130_fd_sc_hd.v` 内部大量使用了形如 `#UNIT_DELAY` 的宏延迟声明。传递 `0` 或空字符串会导致预编译器生成非法语法（如 `#0` 在特定原语块中报错或语法树解析异常）。
* **工程准则**：编译门级网表时仅传递 `-g2012 -DFUNCTIONAL`，由模型库自适应处理。

### 5.4 物理优化中保持 RTL 门控微架构的必要性
* **问题现象**：若在 CTS 之后开启激进的时序重重构（Resizer），综合器可能会将设计者精心设计的输入隔离与门或数据门控 MUX 视为冗余逻辑，或在平衡路径时将其打碎溶解入下游加法树/进位链中（如 8-Tap FIR 异常增生现象），从而彻底破坏 RTL 变换的低功耗初衷。
* **工程准则**：显式配置 `"RUN_POST_CTS_RESIZER_TIMING": False`，严格维持 RTL 级门控结构。

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

## 7. 运行与验证指令

平台支持直接在宿主环境或 AppImage 容器内调用：

```bash
# 1. 评估单案例全流程 (以 32-bit 寄存器时钟门控为例)
./script/evaluate_case.py --case-dir cases/clock_gating/reg_bank_32b

# 2. 评估操作数隔离案例
./script/evaluate_case.py --case-dir cases/operand_isolation/alu_operand_isolation

# 3. 运行门控时钟二维全物理参数化扫描与收支平衡研究 (Scale × Activity)
./script/sweep_clock_gating.py

# 4. 运行操作数隔离三维全物理参数化扫描与损益临界模型研究 (Scale × Valid Duty × Data Activity)
./script/sweep_operand_isolation.py

# 5. 运行 FIR 滤波器数据门控多维全物理参数化扫描与收支平衡研究 (4/8/12/16-Tap)
./script/sweep_data_gating.py

# 6. 运行格雷码计数器多维全物理参数化扫描与纯二进制计数器对比研究 (4/8/16/32-Bit)
./script/sweep_gray_counter.py
```
