# 任务目标：构建通用多文件 RTL 变换自动化评估基座（Evaluation Platform）
# 通用多文件 RTL 变换自动化物理评估基座架构规范 (Evaluation Platform Specification)

你是一位资深的数字 IC 设计与 EDA 自动化工具链专家。我们需要将原本硬编码针对单一模块（`reg_bank`）的单文件评估脚本重构成一套**高鲁棒性、通用化、支持多 Verilog 源文件与任意可 LEC 等价验证之低功耗 RTL 变换**的自动化评估框架。
本项目已实现一套**高鲁棒性、高解耦、支持任意多源 Verilog 模块与可 LEC 等价验证之低功耗 RTL 变换**的自动化物理评估基座。

请根据以下架构规范与避坑准则，完成全套评估基座代码与用例目录结构的重构。

---

## 1. 核心架构与用例目录契约（Case Structure）
## 1. 核心架构与用例目录契约 (Case Structure)

评估基座必须与具体的电路设计和测试激励完全解耦。每个被测案例作为一个独立的用例包管理：
评估基座与具体的电路设计、激励完全解耦。所有被测案例统一分类存放在 `cases/<category>/<case_name>/` 下：

```text
benchmark_cases/
└── <case_name>/
    ├── meta.json             # 案例元数据配置
    ├── src_orig/             # 原始 RTL 源文件集合（支持多个 .v / .sv）
    │   ├── top.v
    │   └── sub_blocks.v
    ├── src_opt/              # 优化后的 RTL 源文件集合（多文件）
    │   ├── top.v
    │   └── sub_blocks.v
    └── tb/
        └── tb_top.v          # 针对该案例的专用测试平台（负责产生真实翻转并转储 VCD）
cases/
├── clock_gating/                       # 门控时钟变换案例集
│   ├── reg_bank_8b/                    # 8 位寄存器（负优化开销反噬样本）
│   ├── reg_bank_16b/                   # 16 位寄存器（收支平衡临界过渡样本）
│   ├── reg_bank_32b/                   # 32 位寄存器（经典正收益基准）
│   └── reg_bank_64b/                   # 64 位寄存器（宽数据通路大幅正收益）
├── operand_isolation/                  # 操作数隔离变换案例集
│   └── alu_operand_isolation/          # 32 位多操作数 ALU 隔离案例
└── contrast_cases/                     # 负优化与工程对照样本集
    └── multi_file_alu/                 # 16 位 ALU 窄位宽门控时钟反噬案例
```

### 用例目录结构规范

```text
cases/<category>/<case_name>/
├── meta.json             # 案例元数据配置（顶层名、时钟周期、时序约束、源文件列表）
├── src_orig/             # 原始 RTL 源文件集合（支持多个 .v / .sv）
│   ├── top.v
│   └── sub_blocks.v
├── src_opt/              # 优化后的 RTL 源文件集合（多文件）
│   ├── top.v
│   └── sub_blocks.v
└── tb/
    └── tb_top.v          # 专用测试平台（固定例化为 u_dut，支持 +EN_DUTY 动态传参）
```

### `meta.json` 规范定义

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

*注：若 `sources_orig` 或 `sources_opt` 为空数组，脚本需自动遍历收集对应目录下的所有 `*.v` 与 `*.sv` 文件。*
*注：若 `sources_orig` 或 `sources_opt` 为空数组，评估基座将自动遍历加载目录下所有的 `*.v` 与 `*.sv` 文件。*

---

## 2. 核心执行流程与关键实现细节
## 2. 核心模块化分层实现 (`src/`)

重构后的自动化主脚本 `evaluate_case.py` 必须严格遵循我们在物理实现与签核中踩坑总结的工程准则：
评估基座的核心逻辑已全面重构至 `src/` 包下：

### Step 1: 通用多文件形式等价性验证（Formal Logic Equivalence Checking）

* **引擎**：Yosys SAT-Solver。
* **通用多文件读取策略**：
* 读取 `src_orig` 中所有文件，将顶层重命名为 `<top>_orig`；读取 `src_opt` 中所有文件，将顶层重命名为 `<top>_opt`。
* 依次执行 `proc` 与 `clk2fflogic`，通过 `equiv_make <top>_orig <top>_opt miter` 构造比对 Miter。
* 执行 `hierarchy -top miter`、`flatten`、`equiv_simple`、`equiv_induct`，最后以 `equiv_status -assert` 严格断言。


* **熔断机制**：形式验证失败时立即终止后续流程，避免浪费物理实现算力。

### Step 2: 物理实现全流程（Physical Implementation via LibreLane）

* **运行环境兼容**：
* 系统中 LibreLane 通过 AppImage 启动，调用命令格式统一采用：
`~/librelane/librelane-devshell-x86_64.AppImage python evaluate_case.py ...` (或执行内部工具链)


* **动态 SDC 注入**：
* 脚本必须依据 `meta.json` 中配置的时钟端口名、周期及延时，在本次运行目录生成标准 `target.sdc`：
```tcl
create_clock [get_ports <clock_port>] -name <clock_port> -period <clock_period_ns>
set_clock_uncertainty <clock_uncertainty_ns> [get_clocks <clock_port>]
set_clock_transition <clock_transition_ns> [get_clocks <clock_port>]
set_input_delay -max <input_delay_ns> -clock <clock_port> [all_inputs -no_clocks]
set_output_delay -max <output_delay_ns> -clock <clock_port> [all_outputs]
set_load <output_load_pf> [all_outputs]

```text
src/
├── common/                     # 基础设施支持
│   ├── env.py                  # AppImage DevShell 自托管环境探测与命令执行包装
│   ├── logger.py               # 集中式时间戳日志与工作空间清理
│   ├── pdk.py                  # Sky130 PDK 与标准单元库路径自适应定位
│   └── case_loader.py          # 用例元数据校验与多文件源码解析
├── core/                       # 核心流水线 5 大执行阶段
│   ├── formal.py               # Step 1: Yosys 层次化形式逻辑等价性验证 (LEC)
│   ├── pnr.py                  # Step 2: LibreLane 80-Stage 物理实现与网表/SPEF 提取
│   ├── sim.py                  # Step 3: Icarus Verilog 门级仿真与动态活动度波形转储
│   ├── signoff.py              # Step 4: OpenSTA 静态时序、功耗与引脚翻转密度签核
│   └── report.py               # Step 5: 全维度 PPA 汇总报表与 Trade-off 关系深度分析
└── analysis/                   # 高级实验与多维参数扫描
    └── sweep_clock_gating.py   # 门控时钟 Scale × Activity 二维全物理扫描引擎
```

---

* 在 LibreLane 的 `config.json` 中显式指定 `"PNR_SDC_FILE"` 与 `"SIGNOFF_SDC_FILE"` 指向该文件，消除 OpenROAD fallback SDC 告警。
## 3. 关键执行机制与避坑准则

### Step 1: 通用多文件形式等价性验证 (Formal LEC)
* **引擎**：Yosys SAT-Solver。
* **隔离策略**：读取 `src_orig` 将顶层重命名为 `<top>_orig`，保存后读取 `src_opt` 并重命名为 `<top>_opt`；
* **时序展平**：依次执行 `proc` 与 `clk2fflogic`，通过 `equiv_make` 生成比对 Miter；
* **严格熔断**：执行 `equiv_simple`、`equiv_induct`，最后以 `equiv_status -assert` 断言。任何逻辑差异立即中断流水线，保护物理实现算力。

* **多源文件挂载**：
* `VERILOG_FILES` 需接受由脚本拼装的完整绝对路径列表。
### Step 2: 物理实现全流程 (Physical Implementation via LibreLane)
* **动态 SDC 注入**：根据 `meta.json` 自动生成合规 `target.sdc`，并在配置中显式绑定 `"PNR_SDC_FILE"` 与 `"SIGNOFF_SDC_FILE"`；
* **80-Stage 完整依赖**：必须设置 `"RUN_KLAYOUT_STREAMOUT": True` 与 `"RUN_MAGIC_STREAMOUT": True`，严禁使用 `--skip Magic.StreamOut`；
* **网表选型**：必须严格提取 `final/nl/<top>.nl.v`（纯逻辑无电源引脚网表），严禁使用包含 `VPWR/VGND` 的 `pnl.v`；
* **寄生参数提取**：提取 `final/spef/nom/<top>.nom.spef` 用于下游静态时序与功耗反标。

### Step 3: 门级仿真与动态翻转波形转储 (Simulation & VCD)
* **编译调用**：Icarus Verilog 参数传递 `-g2012 -DFUNCTIONAL -DUNIT_DELAY=#1`，挂载 PDK 原语库与纯逻辑网表；
* **动态参数化注入**：`tb_top.v` 支持 `$value$plusargs("EN_DUTY=%d", en_duty)` 动态占空比调节；
* **转储规范**：被测模块固定例化为 `u_dut`，通过 `$dumpvars(0, tb_top.u_dut)` 导出带层级作用域的标准活动波形。

* **依赖保护与全流程跑通**：
* 必须保持 80-Stage 完整流水线。设置 `"RUN_KLAYOUT_STREAMOUT": True` 以及 `"RUN_MAGIC_STREAMOUT": True`。
* **禁止使用 `--skip Magic.StreamOut` 或 `--skip Magic.WriteLEF**`，防止后续 `WriteLEF: missing required input 'gds'` 和 `CheckDesignAntennaProperties: missing required input 'lef'` 的断链报错。
* 使用 `"RUN_POST_CTS_RESIZER_TIMING": False` 关闭激进修整（严禁使用已废弃的 `PL_RESIZER_TIMING_OPTIMIZATIONS`）。
### Step 4: 签核级多维分析 (Signoff Analysis via OpenSTA)
* **层次作用域反标**：通过 `read_vcd -scope tb_top/u_dut <vcd>` 确保反标引脚数大于 0；
* **翻转活动度签核导出**：调用 `report_activity_annotation` 统计反标覆盖率（达到 100%），遍历端口与内部引脚提取 `activity` 属性（Transition Density 翻转密度、Static Probability 占空比），导出至 `reports/{tag}_activity.rpt`；
* **物理面积与时序提取**：结合 LibreLane `metrics.json` 与 OpenSTA 最长路径报表，输出详尽功耗、时序与物理复杂度报告。

### Step 5: 综合 PPA 报告与 Trade-off 关系深度分析 (Report)
* 全面横向比对 Power、Timing、Area、Energy (PDP) 与 Activity 五大维度；
* 深入计算“面积惩罚代价比”、“时序敏感度”与“功耗延迟积（PDP）”，输出 JSON 结构化数据与 Markdown 汇总分析。

* **产物提取**：
* **网表提取**：必须严格提取 `final/nl/<top>.nl.v`（纯逻辑无电源引脚网表）。**切勿提取 `final/pnl/*.pnl.v**`（避免 Icarus Verilog 因缺少 `VPWR`/`VGND` 引脚模型崩溃）。
* **寄生参数**：提取 `final/spef/nom/<top>.nom.spef`（或自动降级匹配典型角点 SPEF）。
---

## 4. 运行与验证指令

```bash
# 1. 评估单案例
~/librelane/librelane-devshell-x86_64.AppImage python evaluate_case.py --case-dir cases/clock_gating/reg_bank_32b

### Step 3: 案例专用测试平台仿真与活跃度转储（Simulation & VCD Generation）

* **编译调用**：
* 使用 Icarus Verilog，命令参数中**只传 `-g2012 -DFUNCTIONAL**`，包含 PDK 原语库 `primitives.v`、功能模型 `sky130_fd_sc_hd.v`、综合门级网表 `nl.v` 以及该用例专属的 `tb/tb_top.v`。
* **严禁传参**：切勿人为传递 `-DUNIT_DELAY=0` 或 `-DUNIT_DELAY=""`（会导致 Sky130 库内部宏语法解析错误引发 `syntax error`）。


* **波形转储契约**：用例的 `tb_top.v` 负责实例化 DUT（固定例化名为 `u_dut`），并在仿真中执行：
```verilog
$dumpfile("<tag>_activity.vcd");
$dumpvars(0, tb_top.u_dut);

# 2. 运行二维门控时钟全物理扫描与临界模型分析 (Scale × Activity)
~/librelane/librelane-devshell-x86_64.AppImage python sweep_clock_gating.py
```



### Step 4: 签核级功耗分析（Signoff Power Evaluation via OpenSTA）

* **层次作用域路径**：使用标准正斜杠层级 `read_vcd -scope tb_top/u_dut <vcd_file>`，确保 OpenSTA 成功反标（日志中引脚活动计数必须大于 0）。
* **黑盒定义注入**：在 `read_verilog` 网表前，预先载入 PDK 官方提供的 `sky130_fd_sc_hd__blackbox.v`，消除物理单元 `Creating black box` 警告。
* **单角点直接签核**：通过 `read_liberty <SCL__tt_025C_1v80.lib>` 载入基准库（无需带未声明的 `-corner` 标签）。直接调用原生 `report_power` 输出四维指标。

---

## 3. 交付要求

1. **`evaluate_case.py` 主脚本**：
* 支持通过命令行参数传入用例目录：`python evaluate_case.py --case-dir ./benchmark_cases/<case_name>`。
* 自动探测 PDK 环境（优先支持 `~/.ciel` 根目录层级版本自适应）。
* 包含独立的时间戳集中日志归档。
* 控制台和汇总日志末尾输出格式化的四维功耗对比报告表格（`Internal`、`Switching`、`Leakage`、`Total`）。


2. **测试平台（Testbench）模板样例**：提供一个通用的 `tb_top.v` 书写模板，标明端口驱动、波形转储作用域与时序边界规范。
3. **代码健壮性**：针对文件缺失、LEC 失败、子进程非零返回等情况提供清晰的 Exception Handling 与精准日志引导。

