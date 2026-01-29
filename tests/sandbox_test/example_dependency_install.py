# -*- coding: utf-8 -*-
"""
依赖安装执行器使用示例

演示如何使用 DependencyExecutor 来执行各种依赖管理命令。
注意：此执行器只支持安全的包安装和查询命令，不支持以下破坏环境的操作：
  - 批量安装（-r, --requirement）
  - 卸载操作（uninstall）
  - 升级已安装包（--upgrade, -U）
  - 强制重新安装（--force-reinstall, --reinstall）
  - 升级策略（--upgrade-strategy）
  - 忽略已安装版本（--ignore-installed）
这些限制确保环境的稳定性和安全性。
"""
import sys
import tempfile
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.sandbox.dependency_executor import DependencyExecutor


def main():
    """主函数：演示 DependencyExecutor 的使用"""
    print("=" * 60)
    print("依赖安装执行器使用示例")
    print("=" * 60)
    print()
    
    # 创建临时工作目录
    temp_dir = tempfile.mkdtemp()
    root_dir = Path(temp_dir)
    print("工作目录: {}".format(root_dir))
    print()
    
    # 初始化依赖安装执行器
    print()
    
    # 初始化依赖安装执行器
    executor = DependencyExecutor(
        root_dir=root_dir,
        max_output_length=50000,  # 50KB
        timeout=300,  # 5分钟
    )
    print("已初始化 DependencyExecutor")
    print()
    
    # 示例 1: 列出已安装的包
    print("-" * 60)
    print("示例 1: 列出已安装的包")
    print("-" * 60)
    print("命令: uv pip list")
    print()
    
    response = executor.execute("uv pip list")
    print("退出码: {}".format(response.exit_code))
    print("输出:")
    print(response.output)
    print()
    
    # 示例 2: 显示特定包的信息
    print("-" * 60)
    print("示例 2: 显示特定包的信息")
    print("-" * 60)
    print("命令: uv pip show requests")
    print()
    
    response = executor.execute("uv pip show requests")
    print("退出码: {}".format(response.exit_code))
    print("输出:")
    print(response.output)
    print()
    
    # 示例 3: 冻结依赖列表
    print("-" * 60)
    print("示例 3: 冻结依赖列表")
    print("-" * 60)
    print("命令: uv pip freeze")
    print()
    
    response = executor.execute("uv pip freeze")
    print("退出码: {}".format(response.exit_code))
    print("输出:")
    print(response.output)
    print()
    
    # 示例 4: 安装多个包
    print("-" * 60)
    print("示例 4: 安装多个包")
    print("-" * 60)
    print("命令: uv pip install requests numpy")
    print("注意: 这可能会实际安装包，请确认后再执行")
    print()
    
    # 取消注释下面这行来实际执行安装
    # response = executor.execute("uv pip install requests numpy")
    # print("退出码: {}".format(response.exit_code))
    # print("输出:")
    # print(response.output)
    # print()
    
    # 示例 5: 使用 dry-run 模式测试安装
    print("-" * 60)
    print("示例 5: 使用 dry-run 模式测试安装")
    print("-" * 60)
    print("命令: uv pip install --dry-run requests")
    print()
    
    response = executor.execute("uv pip install --dry-run requests")
    print("退出码: {}".format(response.exit_code))
    print("输出:")
    print(response.output)
    print()
    
    # 示例 6: 检查依赖冲突
    print("-" * 60)
    print("示例 6: 检查依赖冲突")
    print("-" * 60)
    print("命令: uv pip check")
    print()
    
    response = executor.execute("uv pip check")
    print("退出码: {}".format(response.exit_code))
    print("输出:")
    print(response.output)
    print()
    
    # 示例 7: 验证命令格式（不执行）
    print("-" * 60)
    print("示例 7: 验证命令格式")
    print("-" * 60)
    
    valid_commands = [
        "uv pip install requests",
        "uv pip install numpy pandas",
        "uv pip list",
        "uv pip show numpy",
    ]
    
    invalid_commands = [
        "python -c 'print(1)'",
        "pip install requests",
        "ls -la",
    ]
    
    print("有效的命令:")
    for cmd in valid_commands:
        is_valid, error_msg = executor._parse_command(cmd)
        status = "✓ 有效" if is_valid else "✗ 无效"
        print("  {} - {}".format(status, cmd))
    
    print()
    print("无效的命令:")
    for cmd in invalid_commands:
        is_valid, error_msg = executor._parse_command(cmd)
        status = "✓ 有效" if is_valid else "✗ 无效"
        print("  {} - {}".format(status, cmd))
        if error_msg:
            print("    原因: {}".format(error_msg.split('\n')[0]))
    print()
    
    # 示例 8: 处理错误情况
    print("-" * 60)
    print("示例 8: 处理错误情况")
    print("-" * 60)
    print("尝试执行不支持的命令: python -c 'print(1)'")
    print()
    
    response = executor.execute("python -c 'print(1)'")
    print("退出码: {}".format(response.exit_code))
    print("输出:")
    print(response.output)
    print()
    
    # 清理
    print("-" * 60)
    print("清理临时目录")
    import shutil
    shutil.rmtree(root_dir)
    print("已删除: {}".format(root_dir))
    print()
    
    print("=" * 60)
    print("示例演示完成")
    print("=" * 60)


def advanced_example():
    """高级示例：使用 SandboxFilesystemBackend 的 install_dependencies 方法"""
    print()
    print("=" * 60)
    print("高级示例：通过 SandboxFilesystemBackend 使用")
    print("=" * 60)
    print()
    
    from src.sandbox.sandbox_filesystem import SandboxFilesystemBackend
    
    # 创建沙箱后端
    sandbox = SandboxFilesystemBackend(
        root_dir=tempfile.mkdtemp(),
        max_output_length=50000,
    )
    
    print("已创建 SandboxFilesystemBackend")
    print("根目录: {}".format(sandbox.root_dir))
    print()
    
    # 对比 execute 方法（用于执行 Python 代码）
    print("-" * 60)
    print("对比: execute 方法用于 Python 代码")
    print("-" * 60)
    print("执行: python -c 'print(\"Hello from Python!\")'")
    print()
    
    response = sandbox.execute('python -c "print(\'Hello from Python!\')"')
    print("退出码: {}".format(response.exit_code))
    print("输出:")
    print(response.output)
    print()


if __name__ == '__main__':
    # 运行基础示例
    main()
    
    # 运行高级示例
    advanced_example()