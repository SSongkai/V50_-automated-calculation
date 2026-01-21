# result_parser.py

import os
import sys
import subprocess
import logging
import tempfile
import time
import numpy as np
import config

class LSPrePostExtractor:
    """
    使用LS-PrePost Python接口提取剩余速度的类
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.lspp = None
        self._setup_lsprepost_path()
    
    def _setup_lsprepost_path(self):
        """设置LS-PrePost Python路径"""
        try:
            # 添加LS-PrePost Python接口路径
            if config.LSPREPOST_PYTHON_PATH not in sys.path:
                sys.path.insert(0, config.LSPREPOST_PYTHON_PATH)
            
            # 尝试导入lsprepost模块
            import lsprepost as lspp
            self.lspp = lspp
            self.logger.debug("LS-PrePost Python接口导入成功")
            
        except ImportError as e:
            self.logger.warning(f"无法导入LS-PrePost Python接口: {e}")
            self.lspp = None
    
    def extract_residual_velocity_python(self, run_dir):
        """
        使用LS-PrePost Python接口提取剩余速度
        
        Args:
            run_dir (str): 运行目录
        
        Returns:
            dict: 提取结果
        """
        if self.lspp is None:
            return self.extract_residual_velocity_batch(run_dir)
        
        d3plot_file = os.path.join(run_dir, 'd3plot')
        if not os.path.exists(d3plot_file):
            self.logger.error("d3plot文件不存在")
            return {
                'success': False,
                'reason': 'no_d3plot_file',
                'residual_velocity': None,
                'is_penetration': None
            }
        
        try:
            self.logger.info("开始使用Python接口提取剩余速度")
            
            # 打开d3plot数据库
            ret_code = self.lspp.open_database(d3plot_file)
            if ret_code != 0:
                raise Exception(f"无法打开d3plot文件，错误码: {ret_code}")
            
            # 获取时间步信息
            time_steps = self.lspp.get_time_array()
            if len(time_steps) == 0:
                raise Exception("没有找到时间步数据")
            
            self.logger.debug(f"找到 {len(time_steps)} 个时间步")
            
            # 设置到最后时间步
            last_time = time_steps[-1]
            self.lspp.set_current_time(last_time)
            
            # 获取弹丸部件的节点
            projectile_nodes = self._get_projectile_nodes()
            if not projectile_nodes:
                raise Exception("未找到弹丸节点")
            
            # 提取速度数据
            velocities = []
            for node_id in projectile_nodes:
                try:
                    # 获取节点速度 [vx, vy, vz]
                    velocity_vector = self.lspp.get_node_velocity(node_id)
                    if velocity_vector and len(velocity_vector) >= 3:
                        # 计算速度幅值
                        v_magnitude = np.sqrt(
                            velocity_vector[0]**2 + 
                            velocity_vector[1]**2 + 
                            velocity_vector[2]**2
                        )
                        velocities.append({
                            'node_id': node_id,
                            'vx': velocity_vector[0],
                            'vy': velocity_vector[1],
                            'vz': velocity_vector[2],
                            'magnitude': v_magnitude
                        })
                except Exception as e:
                    self.logger.debug(f"获取节点 {node_id} 速度失败: {e}")
                    continue
            
            # 关闭数据库
            self.lspp.close_database()
            
            if not velocities:
                raise Exception("未能提取任何速度数据")
            
            # 计算平均剩余速度
            avg_residual_velocity = np.mean([v['magnitude'] for v in velocities])
            max_residual_velocity = np.max([v['magnitude'] for v in velocities])
            
            # 判断是否穿透
            is_penetration = avg_residual_velocity > config.LSPREPOST_CONFIG['velocity_threshold']
            
            self.logger.info(f"成功提取剩余速度: 平均={avg_residual_velocity:.2f} m/s, 最大={max_residual_velocity:.2f} m/s")
            
            return {
                'success': True,
                'residual_velocity': avg_residual_velocity,
                'max_residual_velocity': max_residual_velocity,
                'is_penetration': is_penetration,
                'node_count': len(velocities),
                'velocity_data': velocities,
                'source': 'lsprepost_python'
            }
            
        except Exception as e:
            self.logger.error(f"使用Python接口提取速度失败: {e}")
            # 尝试备选方法
            return self.extract_residual_velocity_batch(run_dir)
    
    def _get_projectile_nodes(self):
        """获取弹丸部件的所有节点"""
        try:
            # 方法1: 通过部件ID获取
            part_nodes = self.lspp.get_part_nodes(config.PROJECTILE_PART_ID)
            if part_nodes:
                self.logger.debug(f"通过部件ID {config.PROJECTILE_PART_ID} 找到 {len(part_nodes)} 个节点")
                return part_nodes
            
            # 方法2: 通过材料ID获取
            material_parts = self.lspp.get_parts_by_material(config.PROJECTILE_MATERIAL_ID)
            if material_parts:
                all_nodes = []
                for part_id in material_parts:
                    nodes = self.lspp.get_part_nodes(part_id)
                    if nodes:
                        all_nodes.extend(nodes)
                if all_nodes:
                    self.logger.debug(f"通过材料ID {config.PROJECTILE_MATERIAL_ID} 找到 {len(all_nodes)} 个节点")
                    return all_nodes
            
            # 方法3: 获取所有节点（最后的备选方案）
            all_nodes = self.lspp.get_node_ids()
            if all_nodes:
                self.logger.warning("使用所有节点作为备选方案")
                return all_nodes[:100]  # 限制数量避免过度计算
            
            return []
            
        except Exception as e:
            self.logger.error(f"获取弹丸节点失败: {e}")
            return []
    
    def extract_residual_velocity_batch(self, run_dir):
        """
        使用LS-PrePost批处理模式提取剩余速度（备选方法）
        
        Args:
            run_dir (str): 运行目录
        
        Returns:
            dict: 提取结果
        """
        self.logger.info("使用批处理模式提取剩余速度")
        
        d3plot_file = os.path.join(run_dir, 'd3plot')
        if not os.path.exists(d3plot_file):
            return {
                'success': False,
                'reason': 'no_d3plot_file',
                'residual_velocity': None,
                'is_penetration': None
            }
        
        try:
            # 创建LS-PrePost命令文件
            cmd_file = self._create_lsprepost_command_file(run_dir)
            output_file = os.path.join(run_dir, 'velocity_output.txt')
            
            # 运行LS-PrePost批处理
            success = self._run_lsprepost_batch(cmd_file, run_dir)
            
            if success and os.path.exists(output_file):
                # 解析输出文件
                return self._parse_velocity_output_file(output_file)
            else:
                return {
                    'success': False,
                    'reason': 'lsprepost_batch_failed',
                    'residual_velocity': None,
                    'is_penetration': None
                }
                
        except Exception as e:
            self.logger.error(f"批处理模式提取速度失败: {e}")
            return {
                'success': False,
                'reason': f'batch_error: {str(e)}',
                'residual_velocity': None,
                'is_penetration': None
            }
    
    def _create_lsprepost_command_file(self, run_dir):
        """创建LS-PrePost命令文件"""
        cmd_file = os.path.join(run_dir, 'extract_velocity.cfile')
        output_file = os.path.join(run_dir, 'velocity_output.txt')
        
        cmd_content = f"""*OPEN_D3PLOT d3plot
*SET_CURRENT_BINARY_TIME_STEP -1
*OUTPUT_NODAL_VELOCITY "{output_file}" 1 0 0 0
*QUIT_AND_SAVE
"""
        
        with open(cmd_file, 'w') as f:
            f.write(cmd_content)
        
        return cmd_file
    
    def _run_lsprepost_batch(self, cmd_file, run_dir):
        """运行LS-PrePost批处理命令"""
        try:
            cmd = [
                config.LSPREPOST_PATH,
                "-nographics",
                "-c", cmd_file
            ]
            
            self.logger.debug(f"运行命令: {' '.join(cmd)}")
            
            # 切换到运行目录
            original_dir = os.getcwd()
            os.chdir(run_dir)
            
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=config.LSPREPOST_CONFIG['timeout']
                )
                
                stdout, stderr = process.communicate()
                return_code = process.returncode
                
                if return_code == 0:
                    self.logger.debug("LS-PrePost批处理执行成功")
                    return True
                else:
                    self.logger.error(f"LS-PrePost批处理失败，返回码: {return_code}")
                    if stderr:
                        self.logger.error(f"错误信息: {stderr}")
                    return False
                    
            finally:
                os.chdir(original_dir)
                
        except subprocess.TimeoutExpired:
            self.logger.error("LS-PrePost批处理超时")
            return False
        except Exception as e:
            self.logger.error(f"运行LS-PrePost批处理时出错: {e}")
            return False
    
    def _parse_velocity_output_file(self, output_file):
        """解析LS-PrePost输出的速度文件"""
        try:
            with open(output_file, 'r') as f:
                lines = f.readlines()
            
            velocities = []
            for line in lines[1:]:  # 跳过表头
                parts = line.strip().split()
                if len(parts) >= 4:
                    try:
                        node_id = int(parts[0])
                        vx = float(parts[1])
                        vy = float(parts[2]) 
                        vz = float(parts[3])
                        v_mag = np.sqrt(vx**2 + vy**2 + vz**2)
                        velocities.append(v_mag)
                    except ValueError:
                        continue
            
            if velocities:
                avg_velocity = np.mean(velocities)
                is_penetration = avg_velocity > config.LSPREPOST_CONFIG['velocity_threshold']
                
                return {
                    'success': True,
                    'residual_velocity': avg_velocity,
                    'is_penetration': is_penetration,
                    'node_count': len(velocities),
                    'source': 'lsprepost_batch'
                }
            else:
                return {
                    'success': False,
                    'reason': 'no_velocity_data',
                    'residual_velocity': None,
                    'is_penetration': None
                }
                
        except Exception as e:
            self.logger.error(f"解析速度输出文件失败: {e}")
            return {
                'success': False,
                'reason': f'parse_error: {str(e)}',
                'residual_velocity': None,
                'is_penetration': None
            }

# 全局提取器实例
_extractor = None

def get_residual_velocity(run_dir, projectile_part_id=1):
    """
    主要的剩余速度提取函数
    
    Args:
        run_dir (str): 运行目录
        projectile_part_id (int): 弹丸部件ID（保持接口兼容性）
    
    Returns:
        dict: 包含剩余速度和穿透状态的字典
    """
    global _extractor
    
    # 创建提取器实例（单例模式）
    if _extractor is None:
        _extractor = LSPrePostExtractor()
    
    # 使用LS-PrePost提取速度
    if config.LSPREPOST_CONFIG['extract_method'] == 'python':
        return _extractor.extract_residual_velocity_python(run_dir)
    else:
        return _extractor.extract_residual_velocity_batch(run_dir)

def validate_simulation_result(run_dir, expected_velocity_range=None):
    """
    验证仿真结果的合理性（保持原接口）
    """
    logger = logging.getLogger(__name__)
    
    issues = []
    warnings = []
    
    # 检查d3plot文件
    d3plot_file = os.path.join(run_dir, 'd3plot')
    if os.path.exists(d3plot_file):
        file_size = os.path.getsize(d3plot_file)
        if file_size < 1024:  # 小于1KB可能有问题
            issues.append(f"d3plot文件过小 ({file_size} bytes)")
    else:
        issues.append("d3plot文件不存在")
    
    # 检查messag文件
    messag_file = os.path.join(run_dir, 'messag')
    if os.path.exists(messag_file):
        try:
            with open(messag_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if "WARNING" in content.upper():
                    warning_count = content.upper().count("WARNING")
                    warnings.append(f"发现 {warning_count} 个警告")
                if "ERROR" in content.upper():
                    error_count = content.upper().count("ERROR") 
                    issues.append(f"发现 {error_count} 个错误")
        except:
            pass
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings
    }
