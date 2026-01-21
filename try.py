import subprocess
import sys

def run_batch_file():
    try:
        # 执行start.bat文件
        result = subprocess.run(
            "start.bat",        # 批处理文件名
            check=True,          # 如果返回非零退出码则抛出异常
            shell=True,         # 通过shell执行
            stdout=subprocess.PIPE,  # 捕获标准输出
            stderr=subprocess.PIPE,  # 捕获错误输出
            text=True           # 以文本形式返回输出
        )
        
        # 如果执行成功（返回码为0）
        print("start.bat 执行成功！")
        print("输出内容：")
        print(result.stdout)
        return True
        
    except subprocess.CalledProcessError as e:
        # 如果批处理返回非零退出码
        print(f"start1.bat 执行失败，退出码：{e.returncode}")
        print("错误信息：")
        print(e.stderr)
        return False
        
    except Exception as e:
        # 其他异常处理（如文件不存在）
        print(f"执行过程中发生错误：{str(e)}")
        return False

if __name__ == "__main__":
    # 执行批处理并获取结果
    success = run_batch_file()
    
    # 根据判定结果执行下一步操作
    if success:
        print("\n判定结果：成功 ✅")
        # 此处添加成功后的操作
        # 例如：执行下一步脚本、继续程序逻辑等
        print("正在执行下一步操作...")
        # next_step()
    else:
        print("\n判定结果：失败 ❌")
        # 此处添加失败后的处理
        # 例如：记录日志、发送警报、退出程序等
        print("正在处理失败情况...")
        # handle_failure()
        sys.exit(1)  # 非正常退出