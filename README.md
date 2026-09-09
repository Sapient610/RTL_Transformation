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
  * **调用环境入口**：`~/libreline/librelane-devshell-x86_64.AppImage librelane <args>`
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

* **启动方式**：执行子进程时，需通过 `~/libreline/librelane-devshell-x86_64.AppImage librelane` 驱动。
* **动态 SDC 注入**：根据 `meta.json` 自动生成合规 `target.sdc`，并在 LibreLane 配置中显式传入 `"PNR_SDC_FILE"` 与 `"SIGNOFF_SDC_FILE"`，消除 OpenROAD 的 fallback 警告。
* **完整跑通依赖保护**：必须配置 `"RUN_KLAYOUT_STREAMOUT": True` 与 `"RUN_MAGIC_STREAMOUT": True`，**严禁使用 `--skip Magic.StreamOut**`。跳过 Magic 版图导出将破坏下游 `Magic.WriteLEF` 与天线检查步骤的输入链。
* **网表选型注意点**：
* `final/pnl/*.pnl.v` 包含 `.VPWR` 与 `.VGND`，仅用于 LVS/SPICE。
* **门级仿真与 OpenSTA 签核必须提取 `final/nl/*.nl.v`（No-Power 纯逻辑门级网表）**。



**Step 3: 案例仿真与活跃度波形提取 (Simulation & VCD)**

* `iverilog` 编译参数**仅传 `-g2012 -DFUNCTIONAL**`。
* **切勿手动传递 `-DUNIT_DELAY=0` 或 `-DUNIT_DELAY=""**`，避免与 Sky130 库自带的延迟修饰冲突产生语法解析错误。
* `tb_top.v` 需以固定例化名 `u_dut` 实例化顶层模块，并调用 `$dumpvars(0, tb_top.u_dut)` 输出 `<tag>_activity.vcd`。

**Step 4: 签核级功耗分析 (Signoff Power Evaluation)**

* **VCD 作用域反标**：OpenSTA 调用 `read_vcd -scope tb_top/u_dut <vcd>`，使用标准斜杠路径确保引脚活动数大于 0。
* **黑盒模块预载**：在读入网表前读入 `sky130_fd_sc_hd__blackbox.v`，防止物理 Filler/Tapcell 单元产生黑盒警告。
* **单角点直接分析**：通过 `read_liberty` 载入典型工艺角库（无需声明未定义的 `-corner` 标签），使用原生 `report_power` 输出功耗拆解。

---

## 5. 快速上手

运行指定用例目录的自动化评估：

```bash
python evaluate_case.py --case-dir ./benchmark_cases/reg_bank_case

```

执行完毕后，控制台及集中日志目录 `eval_workspace/logs/<timestamp>/overall_pipeline.log` 将生成最终签核对比表：

| Power Metric | Original RTL | Optimized RTL |
| --- | --- | --- |
| **Internal** | 2.75e-04 W | 1.78e-04 W |
| **Switching** | 5.91e-05 W | 2.87e-05 W |
| **Leakage** | 2.84e-09 W | 1.89e-09 W |
| **Total** | 3.34e-04 W | 2.06e-04 W |
