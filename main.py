# main.py

import os
import sys
import logging
import pandas as pd
from datetime import datetime

# 导入自定义模块
import config
from v50_solver import find_v50_for_config

def setup_global_logging():
    """配置全局日志，同时输出到控制台和文件。"""
    log_dir = config.BASE_WORKDIR
    os.makedirs(log_dir, exist_ok=True)
    
    log_filename = os.path.join(log_dir, 'main_process.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, mode='w'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    """
    主执行函数，调度整个 V50 批量计算流程。
    """
    start_time = datetime.now()
    setup_global_logging()
    
    logging.info("=================================================")
    logging.info("===      V50 自动求解程序启动      ===")
    logging.info("=================================================")
    
    # 检查 LS-DYNA 路径是否已配置
    if "path/to/your" in config.LS_DYNA_PATH:
        logging.error("错误：请在 config.py 文件中正确设置 LS_DYNA_PATH！")
        return

    # 初始化结果存储
    results_list = []
    
    # 定义结果 DataFrame 的列
    columns = [
        'config_index', 't1', 't2', 't3', 't4', 'status', 'V50',
        'param_a', 'param_p', 'rmse', 'v_low', 'v_high', 'runs',
        'points_used', 'reason'
    ]

    # 遍历所有厚度配置
    num_configs = len(config.THICKNESS_CONFIGS)
    for i, thickness in enumerate(config.THICKNESS_CONFIGS):
        logging.info(f"\n--- 开始处理配置 {i+1}/{num_configs}: {thickness} mm ---")
        
        try:
            # 调用核心求解器
            result = find_v50_for_config(thickness, i + 1)
            
            # 准备要保存到 CSV 的数据
            row = {
                'config_index': i + 1,
                't1': thickness[0],
                't2': thickness[1],
                't3': thickness[2],
                't4': thickness[3],
                **result  # 合并求解器返回的字典
            }
            results_list.append(row)
            
            logging.info(f"--- 配置 {i+1} 处理完成，状态: {result.get('status', 'unknown')} ---")

        except Exception as e:
            logging.error(f"处理配置 {i+1} 时发生严重错误: {e}", exc_info=True)
            # 记录失败信息
            row = {
                'config_index': i + 1,
                't1': thickness[0], 't2': thickness[1], 't3': thickness[2], 't4': thickness[3],
                'status': 'critical_failure',
                'reason': str(e)
            }
            results_list.append(row)

        # --- 定期保存结果 ---
        # 每处理完一个配置就保存一次，避免数据丢失
        temp_df = pd.DataFrame(results_list)
        # 确保所有列都存在
        for col in columns:
            if col not in temp_df.columns:
                temp_df[col] = None
        temp_df = temp_df[columns] # 保证列的顺序
        temp_df.to_csv(config.RESULTS_CSV_FILE, index=False, encoding='utf-8-sig')
        logging.info(f"结果已实时保存到: {config.RESULTS_CSV_FILE}")

    # --- 流程结束 ---
    end_time = datetime.now()
    total_duration = end_time - start_time
    
    logging.info("\n=================================================")
    logging.info("===         所有配置处理完毕         ===")
    logging.info(f"总计用时: {total_duration}")
    logging.info(f"最终结果文件: {config.RESULTS_CSV_FILE}")
    logging.info("=================================================")

if __name__ == "__main__":
    main()
