# lsdyna_runner.py

import os
import re
import subprocess
import logging
import time
import shutil
import glob
import config

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def prepare_k_files(thickness_config, velocity, work_dir, run_index):
    """
    准备完整的LS-DYNA输入文件组。
    
    Args:
        thickness_config (tuple): 厚度配置 (t1, t2, t3, t4)
        velocity (float): 弹丸初速度 (m/s)
        work_dir (str): 工作目录
        run_index (int): 运行序号
    
    Returns:
        str: 主K文件路径
    """
    logger = logging.getLogger(__name__)
    
    # 创建运行目录
    run_dir = os.path.join(work_dir, f'run_{run_index:03d}_v{velocity:.0f}')
    os.makedirs(run_dir, exist_ok=True)
    
    try:
        # 复制并处理所有K文件
        for k_file in config.K_FILE_TEMPLATES:
            src_file = os.path.join(config.TEMPLATE_DIR, k_file)
            dst_file = os.path.join(run_dir, k_file)
            
            if not os.path.exists(src_file):
                logger.warning(f"模板文件不存在: {src_file}")
                continue
            
            # 读取模板内容
            with open(src_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 处理参数化替换
            if k_file in ["TimeAndVel.k"]:
                content = process_parametric_content(
                    content, k_file, thickness_config, velocity
                )
            
            # 写入处理后的文件
            with open(dst_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.debug(f"已处理K文件: {k_file}")
        
        main_k_file = os.path.join(run_dir, 'main.k')
        
        logger.info(f"K文件准备完成:")
        logger.info(f"  - 运行目录: {os.path.basename(run_dir)}")
        logger.info(f"  - 厚度配置: {thickness_config}")
        logger.info(f"  - 初速度: {velocity:.1f} m/s")
        
        return main_k_file
        
    except Exception as e:
        logger.error(f"准备K文件时出错: {e}")
        raise

def process_parametric_content(content, filename, thickness_config, velocity):
    """
    处理K文件中的参数化内容。
    """
    logger = logging.getLogger(__name__)
    
    if filename == "TimeAndVel.k":
        original_content = content
        
        # 替换初速度 (vz值)
        velocity_pattern = config.PARAMETRIC_CONFIG["velocity"]["pattern"]
        velocity_replacement = config.PARAMETRIC_CONFIG["velocity"]["replacement"]
        
        content = re.sub(
            velocity_pattern,
            velocity_replacement.format(velocity=velocity),
            content
        )
        
        # 替换仿真时间
        time_pattern = config.PARAMETRIC_CONFIG["sim_time"]["pattern"]  
        time_replacement = config.PARAMETRIC_CONFIG["sim_time"]["replacement"]
        
        content = re.sub(
            time_pattern,
            time_replacement.format(sim_time=config.SIMULATION_TIME),
            content
        )
        
        if content != original_content:
            logger.debug(f"已更新 {filename}: 速度={velocity} m/s, 时间={config.SIMULATION_TIME} s")
        else:
            logger.warning(f"未能更新 {filename} 中的参数，请检查正则表达式")
    
    return content

def process_thickness_parameters(content, thickness_config):
    """
    处理target.k中的厚度参数。
    注意: 这个函数需要根据target.k的具体结构来实现
    """
    logger = logging.getLogger(__name__)
    
    # 这里需要根据您的target.k文件的具体结构来实现
    # 例如，如果厚度参数在特定的SECTION定义中，需要找到对应的模式进行替换
    
    # 示例实现（需要根据实际情况修改）:
    t1, t2, t3, t4 = thickness_config
    
    # 假设target.k中有厚度参数需要替换，这里是示例代码
    # 实际实现需要分析target.k的具体格式
    
    logger.debug(f"处理厚度参数: {thickness_config}")
    
    return content

def run_simulation(k_file_path, work_dir, timeout=3600):
    """
    运行LS-DYNA仿真。
    
    Args:
        k_file_path (str): K文件路径
        work_dir (str): 工作目录  
        timeout (int): 超时时间（秒）
    
    Returns:
        dict: 运行结果信息
    """
    logger = logging.getLogger(__name__)
    
    # 检查LS-DYNA可执行文件是否存在
    if not os.path.exists(config.LS_DYNA_PATH):
        logger.error(f"LS-DYNA可执行文件不存在: {config.LS_DYNA_PATH}")
        logger.error("请检查config.py中的LS_DYNA_PATH设置")
        return {
            'success': False,
            'reason': 'lsdyna_not_found',
            'duration': 0
        }
    
    # 构建LS-DYNA命令
    run_dir = os.path.dirname(k_file_path)
    cmd = [
        config.LS_DYNA_PATH,
        f"i={os.path.basename(k_file_path)}",
        f"ncpu={config.LSDYNA_NCPU}",
        f"memory={config.LSDYNA_MEMORY}"
    ]
    
    logger.info(f"开始LS-DYNA仿真:")
    logger.info(f"  - 输入文件: {os.path.basename(k_file_path)}")
    logger.info(f"  - 工作目录: {os.path.basename(run_dir)}")
    logger.debug(f"完整命令: {' '.join(cmd)}")
    
    try:
        # 保存当前目录并切换到运行目录
        original_dir = os.getcwd()
        os.chdir(run_dir)
        
        # 启动LS-DYNA进程
        start_time = time.time()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        logger.info(f"LS-DYNA进程已启动 (PID: {process.pid})")
        
        # 等待完成或超时
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            return_code = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            elapsed_time = time.time() - start_time
            logger.error(f"LS-DYNA运行超时 ({timeout}秒)")
            return {
                'success': False, 
                'reason': 'timeout',
                'duration': elapsed_time
            }
        finally:
            os.chdir(original_dir)
        
        elapsed_time = time.time() - start_time
        
        # 检查运行结果
        if return_code == 0:
            # 检查输出文件
            output_status = check_output_files(run_dir)
            if output_status['complete']:
                logger.info(f"LS-DYNA运行成功，用时: {elapsed_time:.1f}秒")
                return {
                    'success': True,
                    'duration': elapsed_time,
                    'return_code': return_code,
                    'output_files': output_status['files']
                }
            else:
                logger.warning("LS-DYNA进程成功，但输出文件不完整")
                logger.warning(f"缺少文件: {output_status['missing']}")
                return {
                    'success': False,
                    'reason': 'incomplete_output',
                    'duration': elapsed_time,
                    'missing_files': output_status['missing']
                }
        else:
            logger.error(f"LS-DYNA运行失败，返回码: {return_code}")
            if stderr:
                logger.error(f"标准错误: {stderr[:500]}...")  # 限制输出长度
            return {
                'success': False,
                'reason': f'exit_code_{return_code}',
                'duration': elapsed_time,
                'stderr': stderr
            }
            
    except Exception as e:
        logger.error(f"运行LS-DYNA时出错: {e}")
        return {
            'success': False,
            'reason': f'exception: {str(e)}',
            'duration': 0
        }

def check_output_files(run_dir):
    """
    检查LS-DYNA输出文件是否存在且完整。
    
    Returns:
        dict: 包含检查结果的字典
    """
    logger = logging.getLogger(__name__)
    
    # 检查各种输出文件
    required_files = ['messag']  # 最基本的输出文件
    important_files = ['rbdout', 'd3hsp']  # 重要的数据文件
    optional_files = ['matsum']  # 可选文件
    
    found_files = []
    missing_required = []
    missing_important = []
    
    # 检查必需文件
    for filename in required_files:
        file_path = os.path.join(run_dir, filename)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            found_files.append(filename)
        else:
            missing_required.append(filename)
    
    # 检查重要文件
    for filename in important_files:
        file_path = os.path.join(run_dir, filename)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            found_files.append(filename)
        else:
            missing_important.append(filename)
    
    # 检查可选文件
    for filename in optional_files:
        file_path = os.path.join(run_dir, filename)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            found_files.append(filename)
    
    # 检查messag文件中的终止状态
    normal_termination = False
    try:
        messag_file = os.path.join(run_dir, 'messag')
        if os.path.exists(messag_file):
            with open(messag_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if "NORMAL TERMINATION" in content.upper():
                    normal_termination = True
                    logger.debug("检测到正常终止信息")
                elif "ERROR" in content.upper():
                    logger.warning("messag文件中检测到错误信息")
    except Exception as e:
        logger.error(f"检查messag文件时出错: {e}")
    
    # 判断完整性
    is_complete = (
        len(missing_required) == 0 and 
        len(missing_important) == 0 and
        normal_termination
    )
    
    if missing_required:
        logger.error(f"缺少必需文件: {missing_required}")
    if missing_important:
        logger.warning(f"缺少重要文件: {missing_important}")
    
    return {
        'complete': is_complete,
        'files': found_files,
        'missing': missing_required + missing_important,
        'normal_termination': normal_termination
    }

def clean_run_directory(run_dir, keep_essential=True):
    """
    清理运行目录，删除不必要的文件以节省空间。
    
    Args:
        run_dir (str): 运行目录
        keep_essential (bool): 是否保留关键文件
    """
    logger = logging.getLogger(__name__)
    
    if not keep_essential:
        return
    
    try:
        # 定义要保留的文件模式
        keep_patterns = ['*.k', 'rbdout', 'd3hsp', 'messag', '*.log']
        
        # 定义要删除的文件模式  
        delete_patterns = ['d3plot*', '*.tmp', '*.scratch', 'fort.*', 'adapt*']
        
        deleted_count = 0
        saved_space = 0
        
        for pattern in delete_patterns:
            files_to_delete = glob.glob(os.path.join(run_dir, pattern))
            for file_path in files_to_delete:
                try:
                    file_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    deleted_count += 1
                    saved_space += file_size
                    logger.debug(f"已删除: {os.path.basename(file_path)} ({file_size/1024:.1f} KB)")
                except Exception as e:
                    logger.warning(f"删除文件失败 {file_path}: {e}")
        
        if deleted_count > 0:
            logger.info(f"清理完成: 删除 {deleted_count} 个文件，节省 {saved_space/1024/1024:.1f} MB 空间")
                    
    except Exception as e:
        logger.error(f"清理运行目录时出错: {e}")
