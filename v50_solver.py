# v50_solver.py

import os
import logging
import numpy as np
from scipy.optimize import curve_fit

# 从其他模块导入函数和配置
import config
import lsdyna_runner
import result_parser

def lambert_jonas_func(Vi, a, p, VBL):
    """
    Lambert-Jonas 弹道极限方程。

    Args:
        Vi (array-like): 入射速度数组。
        a, p, VBL (float): 方程的拟合参数。

    Returns:
        array-like: 计算出的剩余速度数组。
    """
    # Vi^p - VBL^p 必须为非负数
    term = Vi**p - VBL**p
    # 使用 np.where 来处理 term < 0 的情况，避免负数开根号
    return np.where(term > 0, a * (term)**(1/p), 0)

def find_v50_for_config(thickness_config, config_index):
    """
    为单个厚度配置执行完整的 V50 求解流程。

    Args:
        thickness_config (tuple): 当前的厚度组合 (t1, t2, t3, t4)。
        config_index (int): 当前厚度配置的索引号。

    Returns:
        dict: 包含该厚度配置所有计算结果的字典。
    """
    # --- 1. 初始化 ---
    work_dir = os.path.join(config.BASE_WORKDIR, f'config_{config_index:02d}')
    os.makedirs(work_dir, exist_ok=True)
    
    log_path = os.path.join(work_dir, 'solver.log')
    # 为每个配置设置单独的日志文件
    file_handler = logging.FileHandler(log_path, mode='w')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # 获取当前模块的 logger，并添加 handler
    logger = logging.getLogger(__name__)
    # 清除旧的 handlers (如果有的话)，避免日志重复
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

    logger.info(f"开始处理厚度配置 #{config_index}: {thickness_config}")

    # 初始化变量
    v_low = 0.0  # 已知的最快未穿透速度
    v_high = float('inf') # 已知的最慢穿透速度
    penetration_points = [] # 存储 (Vi, Vr) 对
    run_count = 0
    
    # --- 2. 乘法/指数扩步搜索，寻找 [v_low, v_high] 区间 ---
    # 我们采用乘法增长：current_v = INITIAL_VELOCITY * (GROWTH_FACTOR ** k)
    # 这样在 V50 很大时能更快找到穿透点。
    current_v = config.INITIAL_VELOCITY
    multiplier = config.GROWTH_FACTOR if getattr(config, 'GROWTH_FACTOR', 1.0) > 1.0 else None
    logger.info("--- 阶段 1: 扩步搜索 (乘法/线性混合) ---")
    expansion_iter = 0
    while run_count < config.MAX_TOTAL_RUNS:
        expansion_iter += 1
        run_count += 1
        k_file_path = os.path.join(work_dir, f'run_{run_count:02d}_{int(round(current_v))}mps.k')

        # 准备并运行仿真
        lsdyna_runner.prepare_k_file(config.TEMPLATE_FILE, k_file_path, current_v, thickness_config)
        sim_success = lsdyna_runner.run_simulation(config.LS_DYNA_PATH, k_file_path, work_dir)

        if not sim_success:
            logger.warning(f"速度 {current_v} m/s 的仿真运行失败。跳过此点。")
            # 如果初始速度就失败，尝试增加速度；否则停止
            if run_count == 1:
                # 回退到线性增加以避免无限循环
                current_v += config.EXPONENTIAL_STEP
                continue
            else:
                break

        # 解析结果
        is_penetrated, vr = result_parser.get_residual_velocity(work_dir, config.PROJECTILE_PART_ID)

        if is_penetrated:
            logger.info(f"找到穿透点: Vi={current_v:.2f}, Vr={vr:.2f}")
            v_high = current_v
            if 0 < vr <= config.VR_FILTER_THRESHOLD:
                penetration_points.append((current_v, vr))

            # 自动采样额外的穿透点，确保有足够的点用于拟合
            target_samples = getattr(config, 'EXTRA_PENETRATION_SAMPLES', 3)
            # 只统计满足 Vr 范围的穿透点
            samples_collected = len([p for p in penetration_points if (p[1] > 0 and p[1] <= config.VR_FILTER_THRESHOLD)])
            sample_step = max(1.0, config.EXPONENTIAL_STEP / 5.0)  # 默认小步长，安全

            # 双向采样：在 v_high 的两侧交替采样（向下靠近 v_low 与向上超过 v_high）
            up_v = v_high + sample_step
            down_v = v_high - sample_step
            tried = set([round(v_high, 6)])

            # 交替采样，直到收集到目标数量或达到运行次数上限
            direction_toggle = 0  # 0 -> try down first, 1 -> try up first
            while samples_collected < target_samples and run_count < config.MAX_TOTAL_RUNS:
                # 选择采样方向
                if direction_toggle % 2 == 0:
                    sample_v = down_v
                    direction = 'down'
                else:
                    sample_v = up_v
                    direction = 'up'

                direction_toggle += 1

                # 边界检查：下采样不得低于已知未穿透速度 v_low
                if direction == 'down' and sample_v <= v_low:
                    # 如果下方没有可采样点，则切换到上方
                    direction_toggle += 1
                    continue

                # 避免重复测试同一速度
                key = round(sample_v, 6)
                if key in tried:
                    # 该方向已经采样过，推进下一步
                    if direction == 'down':
                        down_v -= sample_step
                    else:
                        up_v += sample_step
                    continue

                tried.add(key)

                run_count += 1
                k_file_path = os.path.join(work_dir, f'run_{run_count:02d}_{int(round(sample_v))}mps.k')
                lsdyna_runner.prepare_k_file(config.TEMPLATE_FILE, k_file_path, sample_v, thickness_config)
                sim_success = lsdyna_runner.run_simulation(config.LS_DYNA_PATH, k_file_path, work_dir)
                if not sim_success:
                    logger.warning(f"额外采样速度 {sample_v} m/s 仿真失败，跳过。")
                    # 更新采样位置
                    if direction == 'down':
                        down_v -= sample_step
                    else:
                        up_v += sample_step
                    continue

                is_pen, vr = result_parser.get_residual_velocity(work_dir, config.PROJECTILE_PART_ID)
                if is_pen and 0 < vr <= config.VR_FILTER_THRESHOLD:
                    penetration_points.append((sample_v, vr))
                    samples_collected += 1
                    logger.info(f"额外采样到穿透点({direction}): Vi={sample_v:.2f}, Vr={vr:.2f} (已收集 {samples_collected}/{target_samples})")
                else:
                    logger.info(f"额外采样点未穿透或 Vr 无效 ({direction}): Vi={sample_v:.2f}")

                # 更新下一采样位置
                if direction == 'down':
                    down_v -= sample_step
                else:
                    up_v += sample_step

            # 结束扩步阶段（无论是否采集到足够点，进入后续二分/拟合流程）
            break
        else:
            logger.info(f"找到未穿透点: Vi={current_v:.2f}")
            v_low = current_v
            # 增加速度：优先使用乘法增长，否则退回到线性步长
            if multiplier and expansion_iter > 0:
                current_v = current_v * multiplier
            else:
                current_v += config.EXPONENTIAL_STEP
            
    if v_high == float('inf'):
        logger.error("在指数扩步阶段未找到任何穿透点。可能初始速度或步长设置不当。")
        return {'status': 'failed', 'reason': 'No penetration found in exponential search', 'runs': run_count}

    # --- 3. 二分法搜索，加密数据点并收敛 ---
    logger.info(f"--- 阶段 2: 二分法搜索，区间 [{v_low:.2f}, {v_high:.2f}] ---")
    bisection_iter = 0
    while bisection_iter < config.MAX_BISECTION_ITERATIONS and run_count < config.MAX_TOTAL_RUNS:
        if (v_high - v_low) < config.CONVERGENCE_TOLERANCE:
            logger.info("二分法搜索收敛。")
            break
            
        bisection_iter += 1
        run_count += 1
        
        # 取区间中点作为下一个测试速度
        mid_v = (v_low + v_high) / 2.0
        k_file_path = os.path.join(work_dir, f'run_{run_count:02d}_{int(mid_v)}mps.k')
        
        lsdyna_runner.prepare_k_file(config.TEMPLATE_FILE, k_file_path, mid_v, thickness_config)
        sim_success = lsdyna_runner.run_simulation(config.LS_DYNA_PATH, k_file_path, work_dir)
        
        if not sim_success:
            logger.warning(f"速度 {mid_v} m/s 的仿真运行失败。缩小区间并继续。")
            # 假设失败的运行是未知的，我们只能缩小区间
            if mid_v > (v_low + v_high) / 2:
                 v_high = mid_v
            else:
                 v_low = mid_v
            continue

        is_penetrated, vr = result_parser.get_residual_velocity(work_dir, config.PROJECTILE_PART_ID)
        
        if is_penetrated:
            logger.info(f"找到穿透点: Vi={mid_v:.2f}, Vr={vr:.2f}")
            v_high = mid_v
            if 0 < vr <= config.VR_FILTER_THRESHOLD:
                penetration_points.append((mid_v, vr))
        else:
            logger.info(f"找到未穿透点: Vi={mid_v:.2f}")
            v_low = mid_v
            
    logger.info(f"搜索结束。最终区间: [{v_low:.2f}, {v_high:.2f}]。总运行次数: {run_count}")

    # --- 4. Lambert-Jonas 拟合 ---
    logger.info("--- 阶段 3: Lambert-Jonas 拟合 ---")
    
    # 去重并排序
    penetration_points = sorted(list(set(penetration_points)))

    # 在拟合前严格筛选 Vr 范围：只保留 0 < Vr <= VR_FILTER_THRESHOLD 的点
    filtered_points = [p for p in penetration_points if (p[1] > 0 and p[1] <= config.VR_FILTER_THRESHOLD)]
    logger.info(f"筛选后用于拟合的点数: {len(filtered_points)} (原始 {len(penetration_points)})。")

    if len(filtered_points) < config.MIN_DATAPOINTS_FOR_FIT:
        logger.warning(f"有效穿透点不足 ({len(filtered_points)}个)，无法进行拟合。")
        return {
            'status': 'failed',
            'reason': 'Not enough data points for fitting',
            'v_low': v_low,
            'v_high': v_high,
            'runs': run_count,
            'points_used': penetration_points
        }
    Vi_data = np.array([p[0] for p in filtered_points])
    Vr_data = np.array([p[1] for p in filtered_points])
    
    logger.info(f"用于拟合的 {len(Vi_data)} 个点: Vi={Vi_data}, Vr={Vr_data}")

    # 动态调整 VBL 的上界
    vbl_upper_bound = min(config.FIT_BOUNDS['VBL'][1], Vi_data.min() * 0.99)
    bounds = (
        [config.FIT_BOUNDS['a'][0], config.FIT_BOUNDS['p'][0], config.FIT_BOUNDS['VBL'][0]],
        [config.FIT_BOUNDS['a'][1], config.FIT_BOUNDS['p'][1], vbl_upper_bound]
    )
    
    try:
        popt, pcov = curve_fit(
            lambert_jonas_func,
            Vi_data,
            Vr_data,
            p0=config.INITIAL_GUESS,
            bounds=bounds,
            maxfev=5000 # 增加最大函数评估次数
        )
        
        a, p, VBL = popt
        V50 = VBL # VBL 即为 V50
        
        # 计算拟合误差 (RMSE)
        Vr_fit = lambert_jonas_func(Vi_data, a, p, VBL)
        rmse = np.sqrt(np.mean((Vr_data - Vr_fit)**2))
        
        logger.info(f"拟合成功！V50 = {V50:.2f} m/s")
        logger.info(f"拟合参数: a={a:.4f}, p={p:.4f}")
        logger.info(f"拟合 RMSE: {rmse:.4f}")
        
        return {
            'status': 'success',
            'V50': V50,
            'param_a': a,
            'param_p': p,
            'rmse': rmse,
            'v_low': v_low,
            'v_high': v_high,
            'runs': run_count,
            'points_used': penetration_points
        }

    except RuntimeError:
        logger.error("Lambert-Jonas 拟合失败。无法找到最优参数。")
        return {
            'status': 'failed',
            'reason': 'Curve fitting failed',
            'v_low': v_low,
            'v_high': v_high,
            'runs': run_count,
            'points_used': penetration_points
        }
    except Exception as e:
        logger.error(f"拟合过程中发生未知错误: {e}")
        return {
            'status': 'failed',
            'reason': str(e),
            'v_low': v_low,
            'v_high': v_high,
            'runs': run_count,
            'points_used': penetration_points
        }
    finally:
        # 移除文件 handler，以免影响下一个配置的日志
        logging.getLogger(__name__).removeHandler(file_handler)
        file_handler.close()
