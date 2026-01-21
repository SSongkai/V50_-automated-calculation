# V50 自动求解与复现代码（LS-DYNA）  

本仓库包含用于在 LS‑DYNA 中自动求解 V50（弹道极限）并提取剩余速度的 Python 脚本。代码组织为：生成并参数化 K 文件、提交 LS‑DYNA 运行、使用 LS‑PrePost 提取速度、以及基于 Lambert‑Jonas 模型拟合 V50。该 README 描述如何在本地复现论文/实验结果、依赖项与配置要点。

---

## 目录（摘要）
- 说明：目的与背景  
- 快速开始（Quick start）  
- 依赖与环境  
- 配置（config.py 说明与示例）  
- 运行说明（最小示例与完整批量运行）  
- 输出与结果文件  
- 仓库结构说明  
- 日志与调试  
- 常见问题（Troubleshooting）  
- 许可证与引用  

---

## 说明
这些脚本用于自动化 V50 求解流程（多配置批量运行）：
- 生成并处理 LS‑DYNA 的 K 文件 模板（`lsdyna_runner.py`）  
- 调度/批量执行所有厚度配置并保存结果（`main.py`）  
- 从 LS‑PrePost（Python 接口或批处理）提取剩余速度（`result_parser.py`）  
- V50 求解器：搜索速度区间并用 Lambert‑Jonas 拟合得到 V50（`v50_solver.py`）  
- 测试/示例运行脚本（`try.py`）  

注意：LS‑DYNA 与 LS‑PrePost 为专有软件，必须在运行环境中已安装并正确配置路径。

---

## 快速开始（在本机复现最小示例）

1. 克隆仓库（或把代码放到某目录）：
   ```bash
   git clone https://github.com/<your_account>/smo-replication.git
   cd smo-replication
   ```

2. 建议创建虚拟环境并安装 Python 依赖：
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. 编辑 `config.py`（见下节“配置示例”），至少配置 LS‑DYNA 可执行路径、模板目录、工作目录等。

4. 运行最小示例（若已准备好最小 K 模板和示例数据）：
   ```bash
   python main.py
   ```
   或使用 `try.py` 执行单一 bat（Windows 环境下）：
   ```bash
   python try.py
   ```

---

## 依赖与环境

Python 包（示例，可在 `requirements.txt` 中列出）：
- Python >= 3.8
- numpy
- scipy
- pandas
- matplotlib (可选，用于绘图)
- meshio (若需要读写网格)
- 其它按需扩展

外部依赖（必须单独安装）：
- LS‑DYNA 可执行程序（config.LS_DYNA_PATH）
- LS‑PrePost（用于后处理，config.LSPREPOST_PATH）
- 若使用 LS‑PrePost Python 接口，需配置 `LSPREPOST_PYTHON_PATH`

---

## 配置（config.py — 必填项说明与示例）

请在仓库根目录添加或更新 `config.py`，以下是最小必要项与示例值（请根据你的环境调整）：

```python
# config.py (示例，需按实际环境修改)
import os

# LS-DYNA 可执行（可为绝对路径或可执行名）
LS_DYNA_PATH = r"C:\Program Files\LSDYNA\ls-dyna_smp_d.exe"

# LS-PrePost
LSPREPOST_PATH = r"C:\LS-PrePost\lsprepost.exe"
LSPREPOST_PYTHON_PATH = r"C:\LS-PrePost\python"  # 如果使用 Python 接口

# 模板及 K 文件相关
TEMPLATE_DIR = "templates"
K_FILE_TEMPLATES = ["main.k", "TimeAndVel.k", "target.k"]  # 根据实际模板名修改
TEMPLATE_FILE = "main.k"

# 参数化规则示例（正则 pattern 与 replacement）
PARAMETRIC_CONFIG = {
    "velocity": {
        "pattern": r"VZ\s*=\s*[-+]?\d+\.?\d*",   # 仅示例，请按模板真实格式修改
        "replacement": "VZ = {velocity:.2f}"
    },
    "sim_time": {
        "pattern": r"SIM_TIME\s*=\s*[-+]?\d+\.?\d*",
        "replacement": "SIM_TIME = {sim_time:.2f}"
    }
}
SIMULATION_TIME = 0.002  # 示例

# LS-DYNA 运行资源
LSDYNA_NCPU = 8
LSDYNA_MEMORY = 4096  # MB

# LS-PrePost 后处理设置
LSPREPOST_CONFIG = {
    "extract_method": "python",  # 'python' 或 'batch'
    "velocity_threshold": 1.0,   # 判断穿透的阈值 (m/s)
    "timeout": 300  # seconds
}

# 项目相关
PROJECTILE_PART_ID = 1
PROJECTILE_MATERIAL_ID = 1

# 工作目录与结果文件
BASE_WORKDIR = os.path.abspath("workdir")
RESULTS_CSV_FILE = os.path.join(BASE_WORKDIR, "results.csv")

# 求解器参数（示例）
THICKNESS_CONFIGS = [(2.0,2.0,2.0,2.0)]  # 列表：每个元素为 (t1,t2,t3,t4)
INITIAL_VELOCITY = 200.0  # m/s
GROWTH_FACTOR = 1.2
EXPONENTIAL_STEP = 5.0
MAX_TOTAL_RUNS = 200
VR_FILTER_THRESHOLD = 50.0  # m/s
EXTRA_PENETRATION_SAMPLES = 3
MAX_BISECTION_ITERATIONS = 20
CONVERGENCE_TOLERANCE = 0.5
MIN_DATAPOINTS_FOR_FIT = 3

FIT_BOUNDS = {
    'a': (1e-6, 1e3),
    'p': (0.1, 10.0),
    'VBL': (0.0, 1e4)
}
INITIAL_GUESS = [1.0, 2.0, 300.0]
```

请务必按你 K 模板的实际内容调整 `PARAMETRIC_CONFIG` 中的正则表达式与替换字符串；`lsdyna_runner`、`v50_solver` 等模块依赖这些设置。

---

## 运行说明（完整批量流程）

- 使用 `main.py` 启动整个批量计算流程。`main.py` 会：
  1. 遍历 `config.THICKNESS_CONFIGS` 中的所有厚度组合；
  2. 对每个配置调用 `v50_solver.find_v50_for_config`，该函数内部会调用 `lsdyna_runner` 和 `result_parser`；
  3. 每完成一个配置即保存到 `config.RESULTS_CSV_FILE`（实时备份，避免中断时丢失数据）。

- 日志：
  - `main.py` 在 `config.BASE_WORKDIR` 下写主日志 `main_process.log`；
  - 每个配置在其 `work_dir` 下会有 `solver.log`（由 `v50_solver` 创建）及 LS‑DYNA/LS‑PrePost 输出文件（如 `messag`, `d3plot`, `rbdout` 等）。

---

## 输出（重要文件）
- `config.RESULTS_CSV_FILE` : 最终汇总结果（每个厚度配置一行，包含 V50、拟合参数、运行次数、状态等）。
- 每个配置目录（示例：`workdir/config_01/`）：
  - 运行子目录：`run_001_v200/`（包含本次仿真生成的文件：K 文件、messag、d3plot 等）
  - `solver.log`：该配置求解器日志
  - `velocity_output.txt`：若使用 LS‑PrePost 批处理输出（备选）
- `results/`（建议）: 可配置为保存图/处理后结果的目录

---

## 日志与调试
- 增加 `logging` 级别为 DEBUG（临时）以得到更多运行细节。
- 如果 LS‑DYNA 未启动，请先在终端手动运行配置的 LS‑DYNA 命令以确认可执行文件与参数是否正确。
- 若 `result_parser` 无法通过 Python 接口读取 d3plot，请确认 `LSPREPOST_PYTHON_PATH` 与 LS‑PrePost 版本兼容，或切换到 `extract_method='batch'`。

---

## 常见问题（FAQ）

Q: 为什么没有生成 d3plot 或 messag？  
A: 检查 LS‑DYNA 是否成功启动（`lsdyna_runner.run_simulation` 的返回信息），检查 `messag` 文件内容以诊断错误。

Q: 单次输出文件很大，如何节省空间？  
A: 可在 `lsdyna_runner.clean_run_directory` 中调整 `delete_patterns` 或在 LS‑DYNA 中修改输出控制选项；也可以启用 Git LFS 或将大型数据单独存储到数据仓库。

Q: 如何在审稿期间给审稿人看代码但保留匿名？  
A: 可将代码打包为 zip 上传为投稿系统的补充材料，或使用私有仓库并邀请编辑/审稿人访问（需他们的 GitHub 用户名）。

---

---


---

