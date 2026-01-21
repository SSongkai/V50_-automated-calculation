# config.py

import os

# --- 核心路径配置 ---

# LS-DYNA 和 LS-PrePost 配置
LS_DYNA_PATH = r"C:\Application\lspp\dyna\program\ls-dyna_smp_d_R13_1_0_x64.exe"  # 求解器路径
LSPREPOST_PATH = r"C:\Application\lspp\LS-PrePost 4.8\lsprepost4.8_x64.exe"      # LS-PrePost路径
LSPREPOST_PYTHON_PATH = r"C:\Application\lspp\LS-PrePost 4.8"                    # LS-PrePost Python接口路径

# LS-DYNA 模板文件 (.k 文件) 的路径
# 模板中应包含占位符 $VEL, $T1, $T2, $T3, $T4
TEMPLATE_DIR = r"C:\songkai\1"  # K文件模板目录

# --- 工作目录与输出配置 ---

# 所有计算任务的基础工作目录
# 每个厚度组合的计算都会在此目录下创建一个独立的子文件夹
BASE_WORKDIR = r"C:\songkai\V50求解_results"

# 最终结果输出的 CSV 文件名
RESULTS_CSV_FILE = os.path.join(BASE_WORKDIR, 'v50_results.csv')

# --- K文件模板配置 ---

# K文件模板列表（按main.k中的include顺序）
K_FILE_TEMPLATES = [
    "main.k",           # 主文件
    "rigid.k",          # 刚体材料（弹丸）
    "TC4.k",            # TC4钛合金材料
    "ball-127.k",       # 弹丸几何
    "contact.k",        # 接触定义
    "hourglass.k",      # 沙漏控制
    "match.k",          # 部件匹配
    "pe.k",             # PE复合材料
    "section.k",        # 截面定义
    "solution.k",       # 求解器控制
    "target.k",         # 靶板几何
    "TimeAndVel.k",     # 时间和速度控制
]

# 参数化配置
PARAMETRIC_CONFIG = {
    # 速度参数在TimeAndVel.k中的位置
    "velocity": {
        "file": "TimeAndVel.k",
        "pattern": r"(\s+1\s+2\s+0\.0\s+0\.0\s+0\.0\s+)([-+]?\d+\.?\d*)(\s+0\s+0)",
        "replacement": r"\1{velocity}\3"
    },
    # 仿真时间参数
    "sim_time": {
        "file": "TimeAndVel.k", 
        "pattern": r"(\s*)([\d\.]+)(\s+0\s+0\.0\s+0\.0\s*1\.000000E8\s+0)",
        "replacement": r"\1{sim_time}\3"
    }
}

# --- 仿真参数配置 ---

# 仿真时间 (s)
SIMULATION_TIME = 0.00015

# 输出间隔
OUTPUT_INTERVAL = 1e-6

# CPU核心数
LSDYNA_NCPU = 4

# 内存设置
LSDYNA_MEMORY = "500m"

# --- 速度搜索参数 ---

# 初始测试速度 (m/s)
INITIAL_VELOCITY = 300.0

# 速度步长
VELOCITY_STEP = 50.0

# 最大搜索速度
MAX_VELOCITY = 2000.0

# 最小搜索速度
MIN_VELOCITY = 100.0

# V50收敛容差 (m/s)
CONVERGENCE_TOLERANCE = 5.0

# --- 层合板厚度配置 ---

# 定义层合板的厚度组合 (单位: mm)
# 格式为: [(t1, t2, t3, t4), (t1, t2, t3, t4), ...]
THICKNESS_CONFIGS = [
    (2.0, 2.0, 2.0, 2.0),
    (2.5, 2.5, 2.5, 2.5),
    (3.0, 3.0, 3.0, 3.0),
    (3.5, 3.5, 3.5, 3.5),
    (4.0, 4.0, 4.0, 4.0),
]

# --- 弹丸识别参数 ---

PROJECTILE_PART_ID = 1  # 弹丸的部件ID
PROJECTILE_MATERIAL_ID = 4  # 弹丸的材料ID（刚体材料）

# --- Lambert-Jonas 拟合参数 ---

# Lambert-Jonas 方程: Vr = a * (Vi^p - VBL^p)^(1/p)
# 参数 a, p, VBL 的边界
LAMBERT_JONAS_BOUNDS = {
    'a': (0.1, 2.0),
    'p': (1.1, 5.0), 
    'VBL': (50.0, 800.0)
}

# --- LS-PrePost 后处理配置 ---

LSPREPOST_CONFIG = {
    'use_graphics': False,       # 使用无图形模式
    'timeout': 300,              # 后处理超时时间(秒)
    'extract_method': 'python',  # 提取方法：'python' 或 'cfile'
    'velocity_threshold': 10.0   # 穿透判断的速度阈值(m/s)
}

# --- 输出文件配置 ---

OUTPUT_FILES = {
    'd3plot': 'd3plot',
    'rbdout': 'rbdout',
    'messag': 'messag',
    'd3hsp': 'd3hsp'
}

# --- 算法参数 ---

BINARY_SEARCH_MAX_ITER = 20    # 二分法最大迭代次数
MIN_DATA_POINTS = 5            # 拟合所需最小数据点数
MAX_SIMULATION_FAILURES = 3    # 允许的最大仿真失败次数
