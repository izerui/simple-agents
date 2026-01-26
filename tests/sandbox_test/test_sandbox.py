# -*- coding: utf-8 -*-
"""
测试沙箱后端的文件挂载、读取和写入功能

使用固定目录: tests/sandbox_test/workspace
测试完成后可以查看实际文件
"""
import os
import shutil
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.backends.sandbox import SandboxFilesystemBackend


def get_workspace():
    """获取固定的 workspace 目录"""
    workspace = Path(__file__).parent / "workspace"
    return workspace


def print_test_header(test_name):
    """打印测试标题"""
    print("\n" + "="*70)
    print(f"测试: {test_name}")
    print("="*70)


def test_basic_command():
    """测试基本命令执行"""
    print_test_header("基本命令执行")
    
    # 使用固定工作目录
    workspace = get_workspace()
    backend = SandboxFilesystemBackend(root_dir=str(workspace))
    
    # 测试 1: 简单的 uvx 命令
    command = "uvx python -c 'print(\"Hello from uvx!\")'"
    result = backend.execute(command)
    print(f"命令: {command}")
    print(f"输出: {result.output}")
    print(f"退出码: {result.exit_code}")
    assert result.exit_code == 0, "命令执行失败"
    assert "Hello from uvx!" in result.output, "输出不匹配"


def test_file_read():
    """测试文件读取"""
    print_test_header("文件读取")
    
    # 使用固定工作目录
    workspace = get_workspace()
    workspace.mkdir(exist_ok=True)
    
    # 清理旧文件
    if (workspace / "test.txt").exists():
        (workspace / "test.txt").unlink()
    
    # 创建测试文件
    test_file = workspace / "test.txt"
    test_file.write_text("Hello from test file!")
    
    backend = SandboxFilesystemBackend(root_dir=str(workspace))
    
    # 测试读取文件
    command = "uvx python -c 'import os; print(os.listdir(\".\")); print(open(\"test.txt\").read())'"
    result = backend.execute(command)
    print(f"命令: {command}")
    print(f"输出: {result.output}")
    print(f"退出码: {result.exit_code}")
    assert result.exit_code == 0, "命令执行失败"
    assert "test.txt" in result.output, "文件未列出"
    assert "Hello from test file!" in result.output, "文件内容不正确"
    
    print(f"\n📁 查看 test.txt: {workspace / 'test.txt'}")


def test_file_write():
    """测试文件写入"""
    print_test_header("文件写入")
    
    # 使用固定工作目录
    workspace = get_workspace()
    workspace.mkdir(exist_ok=True)
    
    # 清理旧文件
    if (workspace / "output.txt").exists():
        (workspace / "output.txt").unlink()
    
    backend = SandboxFilesystemBackend(root_dir=str(workspace))
    
    # 测试写入文件
    command = """uvx python -c '
with open("output.txt", "w") as f:
    f.write("This is written from sandbox!")
print("File written successfully!")
'"""
    result = backend.execute(command)
    print(f"命令: {command}")
    print(f"输出: {result.output}")
    print(f"退出码: {result.exit_code}")
    assert result.exit_code == 0, "命令执行失败"
    assert "File written successfully!" in result.output, "写入失败"
    
    # 验证文件是否真的被写入
    output_file = workspace / "output.txt"
    assert output_file.exists(), "文件未创建"
    content = output_file.read_text()
    print(f"验证文件内容: {content}")
    assert content == "This is written from sandbox!", "文件内容不正确"
    
    print(f"\n📁 查看 output.txt: {workspace / 'output.txt'}")


def test_file_modify():
    """测试文件修改"""
    print_test_header("文件修改")
    
    # 使用固定工作目录
    workspace = get_workspace()
    workspace.mkdir(exist_ok=True)
    
    # 创建初始文件
    test_file = workspace / "data.txt"
    test_file.write_text("Original content")
    
    backend = SandboxFilesystemBackend(root_dir=str(workspace))
    
    # 读取并修改文件
    command = """uvx python -c '
with open("data.txt", "r") as f:
    content = f.read()
    print(f"Original: {content}")
    
new_content = content.upper()
with open("data.txt", "w") as f:
    f.write(new_content)
    print(f"Modified: {new_content}")
'"""
    result = backend.execute(command)
    print(f"命令: {command}")
    print(f"输出: {result.output}")
    print(f"退出码: {result.exit_code}")
    assert result.exit_code == 0, "命令执行失败"
    assert "Original: Original content" in result.output, "原内容未正确读取"
    assert "Modified: ORIGINAL CONTENT" in result.output, "修改失败"
    
    # 验证文件修改
    modified_content = test_file.read_text()
    print(f"验证文件内容: {modified_content}")
    assert modified_content == "ORIGINAL CONTENT", "文件未正确修改"
    
    print(f"\n📁 查看 data.txt: {workspace / 'data.txt'}")


def test_directory_operations():
    """测试目录操作"""
    print_test_header("目录操作")
    
    # 使用固定工作目录
    workspace = get_workspace()
    workspace.mkdir(exist_ok=True)
    
    # 清理旧的 subdir
    subdir = workspace / "subdir"
    if subdir.exists():
        shutil.rmtree(subdir)
    
    backend = SandboxFilesystemBackend(root_dir=str(workspace))
    
    # 创建目录和文件
    command = """uvx python -c '
import os

# 创建目录
os.makedirs("subdir/nested", exist_ok=True)
print("Directory created")

# 创建多个文件
for i in range(3):
    with open(f"subdir/file_{i}.txt", "w") as f:
        f.write(f"File {i}")

# 遍历目录结构
for root, dirs, files in os.walk("."):
    level = root.replace(".", "").count(os.sep)
    indent = " " * 2 * level
    print(f"{indent}{os.path.basename(root)}/")
    subindent = " " * 2 * (level + 1)
    for file in files:
        print(f"{subindent}{file}")
'"""
    result = backend.execute(command)
    print(f"输出: {result.output}")
    print(f"退出码: {result.exit_code}")
    assert result.exit_code == 0, "命令执行失败"
    assert "Directory created" in result.output, "目录创建失败"
    
    # 验证目录结构
    subdir = workspace / "subdir" / "nested"
    assert subdir.exists(), "子目录未创建"
    for i in range(3):
        file_path = workspace / "subdir" / f"file_{i}.txt"
        assert file_path.exists(), f"文件 {file_path} 未创建"
    
    print(f"\n📁 查看目录结构:")
    print(f"   {workspace}")
    print(f"   └── subdir/")
    print(f"       ├── nested/")
    print(f"       ├── file_0.txt")
    print(f"       ├── file_1.txt")
    print(f"       └── file_2.txt")


def test_dependencies():
    """测试依赖包"""
    print_test_header("依赖包管理")
    
    # 使用固定工作目录
    workspace = get_workspace()
    workspace.mkdir(exist_ok=True)
    backend = SandboxFilesystemBackend(root_dir=str(workspace))
    
    # 使用 requests 包
    command = "uvx --with requests python -c 'import requests; print(f\"requests version: {requests.__version__}\")'"
    result = backend.execute(command)
    print(f"命令: {command}")
    print(f"输出: {result.output}")
    print(f"退出码: {result.exit_code}")
    assert result.exit_code == 0, "命令执行失败"
    assert "requests version" in result.output, "requests 包未正确加载"


def run_all_tests():
    """运行所有测试"""
    tests = [
        test_basic_command,
        test_file_read,
        test_file_write,
        test_file_modify,
        test_directory_operations,
        test_dependencies,
    ]
    
    workspace = get_workspace()
    workspace.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "#"*70)
    print("# 开始沙箱后端测试")
    print("#"*70)
    print(f"# 工作目录: {workspace.absolute()}")
    print(f"# 测试完成后请查看该目录中的文件")
    print("#"*70)
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            print(f"✅ 测试通过: {test_func.__name__}")
            passed += 1
        except Exception as e:
            print(f"❌ 测试失败: {test_func.__name__}")
            print(f"   错误: {e}")
            failed += 1
    
    # 打印总结
    print("\n" + "#"*70)
    print("# 测试总结")
    print("#"*70)
    print(f"总计: {len(tests)} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    print("#"*70)
    print(f"\n📁 查看测试文件:")
    print(f"   cd {workspace}")
    print(f"   ls -la")
    print("#"*70 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)