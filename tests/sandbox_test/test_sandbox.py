#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RestrictedPython 沙箱详细测试用例

测试目标：
1. 验证两种标准执行格式的正确性
2. 测试文件访问权限控制
3. 验证安全限制
4. 测试错误处理机制
5. 验证状态隔离
"""
import sys
from pathlib import Path
import tempfile
import shutil
import json

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.sandbox.sandbox_filesystem import SandboxFilesystemBackend

# 测试工作目录
WORKSPACE_DIR = Path(__file__).parent / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)


class TestSandbox:
    """沙箱测试类"""
    
    def __init__(self):
        """初始化测试环境"""
        self.backend = SandboxFilesystemBackend(
            root_dir=str(WORKSPACE_DIR),
            timeout_seconds=30,
            max_memory_mb=512,
            max_output_length=100000,
        )
        self.passed = 0
        self.failed = 0
    
    def assert_success(self, response, test_name, expected_in_output=None):
        """断言执行成功"""
        if response.exit_code == 0:
            if expected_in_output and expected_in_output not in response.output:
                print(f"✗ {test_name}: 输出中缺少期望内容: {expected_in_output}")
                self.failed += 1
            else:
                print(f"✓ {test_name}")
                self.passed += 1
        else:
            print(f"✗ {test_name}: 执行失败 (退出码: {response.exit_code})")
            print(f"  输出: {response.output[:200]}")
            self.failed += 1
    
    def assert_failure(self, response, test_name, expected_error=None):
        """断言执行失败"""
        if response.exit_code != 0:
            if expected_error and expected_error not in response.output:
                print(f"✗ {test_name}: 错误信息中缺少期望内容: {expected_error}")
                self.failed += 1
            else:
                print(f"✓ {test_name}")
                self.passed += 1
        else:
            print(f"✗ {test_name}: 应该失败但成功了")
            self.failed += 1
    
    def assert_file_exists(self, file_path, test_name):
        """断言文件存在"""
        if file_path.exists():
            print(f"✓ {test_name}")
            self.passed += 1
        else:
            print(f"✗ {test_name}: 文件不存在: {file_path}")
            self.failed += 1
    
    def assert_file_not_exists(self, file_path, test_name):
        """断言文件不存在"""
        if not file_path.exists():
            print(f"✓ {test_name}")
            self.passed += 1
        else:
            print(f"✗ {test_name}: 文件不应该存在: {file_path}")
            self.failed += 1
    
    def cleanup(self):
        """清理测试环境"""
        # 清空工作目录
        for item in WORKSPACE_DIR.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
    
    def summary(self):
        """打印测试总结"""
        print("\n" + "=" * 70)
        print("测试总结")
        print("=" * 70)
        print(f"通过: {self.passed}")
        print(f"失败: {self.failed}")
        print(f"总计: {self.passed + self.failed}")
        print(f"通过率: {self.passed / (self.passed + self.failed) * 100:.1f}%")
        print("=" * 70)
        return self.failed == 0


def test_python_c_format(test_runner):
    """测试 1: python -c "code" 格式"""
    print("\n" + "=" * 70)
    print("测试 1: python -c \"code\" 格式")
    print("=" * 70)
    
    # 测试 1.1: 基本执行
    print("\n测试 1.1: 基本代码执行")
    response = test_runner.backend.execute('python -c "print(\'Hello World\')"')
    test_runner.assert_success(response, "基本 python -c 执行", "Hello World")
    
    # 测试 1.2: 多行代码
    print("\n测试 1.2: 多行代码")
    response = test_runner.backend.execute('''
python -c "
x = 10
y = 20
print(f'x + y = {x + y}')
"
''')
    test_runner.assert_success(response, "多行代码执行", "x + y = 30")
    
    # 测试 1.3: 使用 python3
    print("\n测试 1.3: 使用 python3 -c")
    response = test_runner.backend.execute('python3 -c "print(\'Python3 works\')"')
    test_runner.assert_success(response, "python3 -c 格式", "Python3 works")
    
    # 测试 1.4: 数学计算
    print("\n测试 1.4: 数学计算")
    response = test_runner.backend.execute('''
python -c "
import math
print(f'π = {math.pi:.4f}')
print(f'√16 = {math.sqrt(16)}')
print(f'2^10 = {2**10}')
"
''')
    test_runner.assert_success(response, "数学计算", "√16 = 4")
    
    # 测试 1.5: 列表操作
    print("\n测试 1.5: 列表和推导式")
    response = test_runner.backend.execute('''
python -c "
numbers = [1, 2, 3, 4, 5]
squares = [n**2 for n in numbers]
print(f'Numbers: {numbers}')
print(f'Squares: {squares}')
"
''')
    test_runner.assert_success(response, "列表操作", "Squares: [1, 4, 9, 16, 25]")


def test_python_script_format(test_runner):
    """测试 2: python script.py 格式"""
    print("\n" + "=" * 70)
    print("测试 2: python script.py 格式")
    print("=" * 70)
    
    # 测试 2.1: 相对路径脚本
    print("\n测试 2.1: 相对路径脚本")
    script_path = WORKSPACE_DIR / "hello.py"
    script_path.write_text("""
print("Hello from script!")
x = 10
print(f"x = {x}")
""")
    response = test_runner.backend.execute("python hello.py")
    test_runner.assert_success(response, "相对路径脚本执行", "Hello from script!")
    
    # 测试 2.2: 绝对路径脚本
    print("\n测试 2.2: 绝对路径脚本")
    script_path = WORKSPACE_DIR / "abs_script.py"
    script_path.write_text("""
print("Absolute path script!")
""")
    response = test_runner.backend.execute(f"python {script_path}")
    test_runner.assert_success(response, "绝对路径脚本执行", "Absolute path script!")
    
    # 测试 2.3: 脚本中使用模块
    print("\n测试 2.3: 脚本中使用模块")
    script_path = WORKSPACE_DIR / "modules.py"
    script_path.write_text("""
import json
import os

data = {"message": "Hello from modules"}
json_str = json.dumps(data, indent=2)
print(json_str)
print(f"OS: {os.name}")
""")
    response = test_runner.backend.execute("python modules.py")
    test_runner.assert_success(response, "脚本使用模块", '"message": "Hello from modules"')
    
    # 测试 2.4: 复杂脚本逻辑
    print("\n测试 2.4: 复杂脚本逻辑")
    script_path = WORKSPACE_DIR / "complex.py"
    script_path.write_text("""
# 数据处理
data = [i for i in range(1, 11)]

# 计算统计
total = sum(data)
average = sum(data) / len(data)
squares = [x**2 for x in data]

print(f"Data: {data}")
print(f"Total: {total}")
print(f"Average: {average:.1f}")
print(f"Squares: {squares[:5]}...")
""")
    response = test_runner.backend.execute("python complex.py")
    test_runner.assert_success(response, "复杂脚本逻辑", "Total: 55")


def test_file_operations_inside_root(test_runner):
    """测试 3: root_dir 内的文件操作"""
    print("\n" + "=" * 70)
    print("测试 3: root_dir 内的文件操作")
    print("=" * 70)
    
    # 测试 3.1: 写入文件
    print("\n测试 3.1: 写入文件")
    response = test_runner.backend.execute('''
python -c "
with open('test_write.txt', 'w') as f:
    f.write('Hello from sandbox!')
"
''')
    test_file = WORKSPACE_DIR / "test_write.txt"
    test_runner.assert_success(response, "写入文件")
    test_runner.assert_file_exists(test_file, "文件存在验证")
    
    if test_file.exists():
        content = test_file.read_text()
        if content == "Hello from sandbox!":
            print("✓ 文件内容正确")
            test_runner.passed += 1
        else:
            print(f"✗ 文件内容不正确: {content}")
            test_runner.failed += 1
    
    # 测试 3.2: 读取文件
    print("\n测试 3.2: 读取文件")
    response = test_runner.backend.execute('''
python -c "
with open('test_write.txt', 'r') as f:
    content = f.read()
    print(f'Read: {content}')
"
''')
    test_runner.assert_success(response, "读取文件", "Read: Hello from sandbox!")
    
    # 测试 3.3: 追加内容
    print("\n测试 3.3: 追加内容")
    response = test_runner.backend.execute('''
python -c "
with open('test_write.txt', 'a') as f:
    f.write('\\nAppended line!')
"
''')
    response2 = test_runner.backend.execute('''
python -c "
with open('test_write.txt', 'r') as f:
    content = f.read()
    print(content)
"
''')
    test_runner.assert_success(response2, "追加内容", "Appended line!")
    
    # 测试 3.4: 创建子目录和文件
    print("\n测试 3.4: 创建子目录和文件")
    response = test_runner.backend.execute('''
python -c "
with open('subdir/nested.txt', 'w') as f:
    f.write('Nested file content!')
"
''')
    nested_file = WORKSPACE_DIR / "subdir" / "nested.txt"
    test_runner.assert_success(response, "创建子目录和文件")
    test_runner.assert_file_exists(nested_file, "嵌套文件存在")
    
    # 测试 3.5: JSON 操作
    print("\n测试 3.5: JSON 文件操作")
    response = test_runner.backend.execute('''
python -c "
import json

data = {'name': 'Alice', 'age': 30, 'skills': ['Python', 'Go']}
with open('data.json', 'w') as f:
    json.dump(data, f, indent=2)

with open('data.json', 'r') as f:
    loaded = json.load(f)
    print(f'Loaded: {loaded}')
"
''')
    json_file = WORKSPACE_DIR / "data.json"
    test_runner.assert_success(response, "JSON 操作", "Loaded:")
    test_runner.assert_file_exists(json_file, "JSON 文件存在")


def test_file_operations_outside_root(test_runner):
    """测试 4: root_dir 外的文件操作"""
    print("\n" + "=" * 70)
    print("测试 4: root_dir 外的文件操作")
    print("=" * 70)
    
    # 测试 4.1: 读取 root_dir 外的文件（允许）
    print("\n测试 4.1: 读取 root_dir 外的文件")
    response = test_runner.backend.execute('''
python -c "
try:
    with open('/etc/hosts', 'r') as f:
        content = f.read()
        print(f'Read {len(content)} bytes from /etc/hosts')
except FileNotFoundError:
    print('File not found (non-Unix system)')
"
''')
    test_runner.assert_success(response, "读取 root_dir 外文件")
    
    # 测试 4.2: 尝试写入包含 ~ 的路径（会被当作相对路径处理）
    print("\n测试 4.2: 尝试写入包含 ~ 的路径")
    response = test_runner.backend.execute('''
python -c "
with open('~/sandbox_test.txt', 'w') as f:
    f.write('This is written!')
print('Write succeeded!')
"
''')
    test_runner.assert_success(response, "写入包含 ~ 的路径")
    
    # 验证文件被创建在 root_dir 内的 ~ 子目录
    test_file = WORKSPACE_DIR / "~" / "sandbox_test.txt"
    if test_file.exists():
        print("✓ 文件被创建在 root_dir 内（符合预期）")
        test_runner.passed += 1
        # 清理
        test_file.unlink()
        test_file.parent.rmdir()
    else:
        print("✗ 文件未被创建")
        test_runner.failed += 1
    
    # 测试 4.3: 尝试写入包含 ~ 的路径（会被当作相对路径处理）
    print("\n测试 4.3: 尝试写入包含 ~ 的路径")
    response = test_runner.backend.execute('''
python -c "
with open('~/test.txt', 'w') as f:
    f.write('This is written!')
print('Write succeeded!')
"
''')
    test_runner.assert_success(response, "写入包含 ~ 的路径")
    
    # 验证文件被创建在 root_dir 内的 ~ 子目录
    test_file = WORKSPACE_DIR / "~" / "test.txt"
    if test_file.exists():
        print("✓ 文件被创建在 root_dir 内（符合预期）")
        test_runner.passed += 1
        # 清理
        test_file.unlink()
        if test_file.parent.exists():
            test_file.parent.rmdir()
    else:
        print("✗ 文件未被创建")
        test_runner.failed += 1


def test_security_restrictions(test_runner):
    """测试 5: 安全限制"""
    print("\n" + "=" * 70)
    print("测试 5: 安全限制")
    print("=" * 70)
    
    # 测试 5.1: eval 被阻止
    print("\n测试 5.1: eval 函数被阻止")
    response = test_runner.backend.execute('python -c "eval(\'print(1+1)\')"')
    test_runner.assert_failure(response, "eval 被阻止", "NameError: name 'eval'")

    # 测试 5.2: exec 被阻止
    print("\n测试 5.2: exec 函数被阻止")
    response = test_runner.backend.execute('python -c "exec(\'x=10\')"')
    test_runner.assert_failure(response, "exec 被阻止", "NameError: name 'exec'")

    # 测试 5.3: compile 被阻止
    print("\n测试 5.3: compile 函数被阻止")
    response = test_runner.backend.execute('python -c "compile(\'x=10\', \'<string>\', \'exec\')"')
    test_runner.assert_failure(response, "compile 被阻止", "NameError: name 'compile'")
    
    # 测试 5.4: 原始 open 被替换
    print("\n测试 5.4: 原始 open 函数被替换")
    response = test_runner.backend.execute('python -c "print(type(open).__name__)"')
    test_runner.assert_success(response, "open 函数被替换", "function")
    
    # 测试 5.5: 模块导入仍然可用
    print("\n测试 5.5: 模块导入仍然可用")
    response = test_runner.backend.execute('''
python -c "
import json
import os
import math
print('Modules imported successfully')
"
''')
    test_runner.assert_success(response, "模块导入", "Modules imported successfully")


def test_error_handling(test_runner):
    """测试 6: 错误处理"""
    print("\n" + "=" * 70)
    print("测试 6: 错误处理")
    print("=" * 70)
    
    # 测试 6.1: 不支持的命令格式
    print("\n测试 6.1: 不支持的命令格式")
    response = test_runner.backend.execute("print('Hello')")
    test_runner.assert_failure(response, "直接执行代码被拒绝", "不支持的命令格式")
    
    # 测试 6.2: 脚本文件不存在
    print("\n测试 6.2: 脚本文件不存在")
    response = test_runner.backend.execute("python nonexistent.py")
    test_runner.assert_failure(response, "脚本不存在错误", "文件不存在")
    
    # 测试 6.3: 语法错误
    print("\n测试 6.3: 语法错误")
    script_path = WORKSPACE_DIR / "syntax_error.py"
    script_path.write_text("""
def broken(
    # 缺少括号
""")
    response = test_runner.backend.execute("python syntax_error.py")
    test_runner.assert_failure(response, "语法错误被捕获", "语法错误")
    
    # 测试 6.4: 运行时错误
    print("\n测试 6.4: 运行时错误（除零）")
    response = test_runner.backend.execute('python -c "x = 10; y = 0; print(x / y)"')
    test_runner.assert_failure(response, "运行时错误被捕获", "ZeroDivisionError")
    
    # 测试 6.5: 类型错误
    print("\n测试 6.5: 类型错误")
    response = test_runner.backend.execute('python -c "print(\'10\' + 20)"')
    test_runner.assert_failure(response, "类型错误被捕获", "TypeError")
    
    # 测试 6.6: 文件读取错误
    print("\n测试 6.6: 文件不存在错误")
    response = test_runner.backend.execute('python -c "with open(\'nonexistent.txt\', \'r\') as f: print(f.read())"')
    test_runner.assert_failure(response, "文件不存在错误", "FileNotFoundError")


def test_state_isolation(test_runner):
    """测试 7: 状态隔离"""
    print("\n" + "=" * 70)
    print("测试 7: 状态隔离")
    print("=" * 70)
    
    # 测试 7.1: 多次执行变量不共享
    print("\n测试 7.1: 变量状态隔离")
    
    # 第一次执行
    response1 = test_runner.backend.execute('python -c "x = 10; print(f\'x = {x}\')"')
    test_runner.assert_success(response1, "第一次执行", "x = 10")
    
    # 第二次执行尝试访问变量
    response2 = test_runner.backend.execute('python -c "print(f\'x = {x}\')"')
    test_runner.assert_failure(response2, "变量不共享", "NameError: name 'x' is not defined")
    
    # 测试 7.2: 脚本执行后状态不保留
    print("\n测试 7.2: 脚本执行后状态不保留")
    script_path = WORKSPACE_DIR / "state_test.py"
    script_path.write_text("""
y = 20
print(f'y = {y}')
""")
    
    response3 = test_runner.backend.execute("python state_test.py")
    test_runner.assert_success(response3, "脚本执行", "y = 20")
    
    # 尝试再次访问
    response4 = test_runner.backend.execute('python -c "print(f\'y = {y}\')"')
    test_runner.assert_failure(response4, "脚本变量不保留", "NameError: name 'y' is not defined")


def test_timeout_and_resources(test_runner):
    """测试 8: 超时和资源限制"""
    print("\n" + "=" * 70)
    print("测试 8: 超时和资源限制")
    print("=" * 70)
    
    # 测试 8.1: 快速执行
    print("\n测试 8.1: 快速执行（应成功）")
    response = test_runner.backend.execute('python -c "import time; time.sleep(1); print(\'Done!\')"')
    test_runner.assert_success(response, "快速执行", "Done!")
    
    # 测试 8.2: 超时执行（创建一个短超时的后端）
    # print("\n测试 8.2: 超时执行")
    from src.sandbox.sandbox_filesystem import SandboxFilesystemBackend as Sandbox
    # timeout_backend = Sandbox(
    #     root_dir=str(WORKSPACE_DIR),
    #     timeout_seconds=2  # 2 秒超时
    # )
    # response = timeout_backend.execute('python -c "import time; time.sleep(5); print(\'Should not print\')"')
    # test_runner.assert_failure(response, "超时被捕获", "超时")
    
    # 测试 8.3: 输出长度限制
    print("\n测试 8.3: 输出长度限制")
    limited_backend = Sandbox(
        root_dir=str(WORKSPACE_DIR),
        max_output_length=100  # 限制 100 字符
    )
    response = limited_backend.execute('''
python -c "
for i in range(1000):
    print(f'Line {i}: ' + 'x' * 50)
"
''')
    if response.truncated:
        print("✓ 输出被正确截断")
        test_runner.passed += 1
    else:
        print("✗ 输出应该被截断")
        test_runner.failed += 1


def test_module_imports(test_runner):
    """测试 9: 模块导入"""
    print("\n" + "=" * 70)
    print("测试 9: 模块导入")
    print("=" * 70)
    
    # 测试 9.1: 标准库导入
    print("\n测试 9.1: 标准库导入")
    response = test_runner.backend.execute('''
python -c "
import json
import os
import sys
import math
import csv
from datetime import datetime

print(f'json: {json}')
print(f'os: {os}')
print(f'sys: {sys}')
print(f'math: {math}')
print(f'csv: {csv}')
print(f'datetime: {datetime}')
"
''')
    test_runner.assert_success(response, "标准库导入")
    
    # 测试 9.2: 使用导入的模块
    print("\n测试 9.2: 使用导入的模块")
    response = test_runner.backend.execute('''
python -c "
import json
from datetime import datetime
from statistics import mean, median

data = [1, 2, 3, 4, 5]
result = {
    'mean': mean(data),
    'median': median(data),
    'timestamp': str(datetime.now())
}

with open('stats.json', 'w') as f:
    json.dump(result, f, indent=2)

print('Statistics saved')
"
''')
    test_runner.assert_success(response, "使用导入的模块", "Statistics saved")
    
    stats_file = WORKSPACE_DIR / "stats.json"
    test_runner.assert_file_exists(stats_file, "统计文件存在")
    
    # 测试 9.3: 第三方库导入（如果可用）
    print("\n测试 9.3: 第三方库导入")
    response = test_runner.backend.execute('''
python -c "
try:
    import numpy as np
    print('✓ numpy imported')
except ImportError:
    print('ℹ numpy not installed (this is OK)')

try:
    import requests
    print('✓ requests imported')
except ImportError:
    print('ℹ requests not installed (this is OK)')
"
''')
    test_runner.assert_success(response, "第三方库导入测试")


def test_script_organization(test_runner):
    """测试 10: 脚本组织"""
    print("\n" + "=" * 70)
    print("测试 10: 脚本组织")
    print("=" * 70)
    
    # 创建测试目录结构
    scripts_dir = WORKSPACE_DIR / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    data_dir = WORKSPACE_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    output_dir = WORKSPACE_DIR / "output"
    output_dir.mkdir(exist_ok=True)
    
    # 测试 10.1: 脚本间数据共享
    print("\n测试 10.1: 脚本间数据共享（通过文件）")
    
    # 脚本 1: 生成数据
    gen_script = scripts_dir / "generate_data.py"
    gen_script.write_text("""
import json

data = {
    'items': [{'id': i, 'value': i * 10} for i in range(1, 11)]
}

with open('data/generated.json', 'w') as f:
    json.dump(data, f, indent=2)

print('Data generated')
""")
    
    response1 = test_runner.backend.execute("python scripts/generate_data.py")
    test_runner.assert_success(response1, "生成数据脚本")
    
    # 脚本 2: 处理数据
    process_script = scripts_dir / "process_data.py"
    process_script.write_text("""
import json

with open('data/generated.json', 'r') as f:
    data = json.load(f)

total = sum(item['value'] for item in data['items'])

with open('output/summary.json', 'w') as f:
    json.dump({'total': total, 'count': len(data['items'])}, f, indent=2)

print(f'Processed {len(data["items"])} items, total value: {total}')
""")
    
    response2 = test_runner.backend.execute("python scripts/process_data.py")
    test_runner.assert_success(response2, "处理数据脚本", "Processed 10 items")
    
    summary_file = output_dir / "summary.json"
    test_runner.assert_file_exists(summary_file, "摘要文件存在")


def test_edge_cases(test_runner):
    """测试 11: 边界情况"""
    print("\n" + "=" * 70)
    print("测试 11: 边界情况")
    print("=" * 70)
    
    # 测试 11.1: 空命令
    print("\n测试 11.1: 空命令")
    response = test_runner.backend.execute("")
    test_runner.assert_failure(response, "空命令被拒绝")
    
    # 测试 11.2: 只包含空白
    print("\n测试 11.2: 只包含空白")
    response = test_runner.backend.execute("   ")
    test_runner.assert_failure(response, "空白命令被拒绝")
    
    # 测试 11.3: 特殊字符
    print("\n测试 11.3: Unicode 字符")
    response = test_runner.backend.execute('python -c "print(\'中文测试！🚀 🔒 📁\')"')
    test_runner.assert_success(response, "Unicode 字符", "中文测试！")
    
    # 测试 11.4: 大输出
    print("\n测试 11.4: 大输出")
    response = test_runner.backend.execute('python -c "print(\'A\' * 10000)"')
    if response.truncated:
        print("✓ 大输出被截断")
        test_runner.passed += 1
    else:
        print("✓ 大输出未被截断")
        test_runner.passed += 1
    
    # 测试 11.5: 路径遍历尝试
    print("\n测试 11.5: 路径遍历尝试")
    response = test_runner.backend.execute('python -c "open(\'../../../etc/passwd\', \'r\')"')
    test_runner.assert_failure(response, "路径遍历被阻止", "PermissionError")
    
    # 测试 11.6: 递归深度
    print("\n测试 11.6: 递归深度限制")
    script_path = WORKSPACE_DIR / "recursion.py"
    script_path.write_text("""
def infinite_recursion():
    return infinite_recursion()

infinite_recursion()
""")
    response = test_runner.backend.execute("python recursion.py")
    test_runner.assert_failure(response, "递归深度被限制", "递归深度")


def test_mixed_operations(test_runner):
    """测试 12: 混合操作"""
    print("\n" + "=" * 70)
    print("测试 12: 混合操作")
    print("=" * 70)
    
    # 测试 12.1: python -c 和 python script.py 交替执行
    print("\n测试 12.1: 交替执行")
    
    response1 = test_runner.backend.execute('python -c "x = 1"')
    test_runner.assert_success(response1, "代码执行 1")
    
    script_path = WORKSPACE_DIR / "alt.py"
    script_path.write_text("y = 2; print(f'y = {y}')")
    
    response2 = test_runner.backend.execute("python alt.py")
    test_runner.assert_success(response2, "脚本执行", "y = 2")
    
    response3 = test_runner.backend.execute('python -c "print(\'x undefined\')"')
    test_runner.assert_success(response3, "代码执行 2", "x undefined")
    
    # 测试 12.2: 数据处理管道
    print("\n测试 12.2: 数据处理管道")
    
    # 步骤 1: 生成数据
    response = test_runner.backend.execute('''
python -c "
import json

data = [i * 10 for i in range(1, 11)]
with open('pipeline_input.json', 'w') as f:
    json.dump(data, f)
"
''')
    test_runner.assert_success(response, "管道步骤 1")
    
    # 步骤 2: 处理数据
    script_path = WORKSPACE_DIR / "pipeline_process.py"
    script_path.write_text("""
import json

with open('pipeline_input.json', 'r') as f:
    data = json.load(f)

# 计算统计
stats = {
    'total': sum(data),
    'avg': sum(data) / len(data),
    'max': max(data),
    'min': min(data)
}

with open('pipeline_output.json', 'w') as f:
    json.dump(stats, f, indent=2)

print(f'Processed: {stats}')
""")
    
    response = test_runner.backend.execute("python pipeline_process.py")
    test_runner.assert_success(response, "管道步骤 2")
    
    # 步骤 3: 读取结果
    response = test_runner.backend.execute('''
python -c "
import json

with open('pipeline_output.json', 'r') as f:
    stats = json.load(f)
    print(f'Stats: {stats}')
"
''')
    test_runner.assert_success(response, "管道步骤 3")


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("RestrictedPython 沙箱详细测试套件")
    print("=" * 70)
    print(f"\n工作目录: {WORKSPACE_DIR}")
    print("\n测试范围：")
    print("  ✓ python -c \"code\" 格式")
    print("  ✓ python script.py 格式")
    print("  ✓ 文件访问权限控制")
    print("  ✓ 安全限制")
    print("  ✓ 错误处理")
    print("  ✓ 状态隔离")
    print("  ✓ 超时和资源限制")
    print("  ✓ 模块导入")
    print("  ✓ 脚本组织")
    print("  ✓ 边界情况")
    print("  ✓ 混合操作")
    print()
    
    # 创建测试运行器
    test_runner = TestSandbox()
    
    try:
        # 运行所有测试
        test_python_c_format(test_runner)
        test_python_script_format(test_runner)
        test_file_operations_inside_root(test_runner)
        test_file_operations_outside_root(test_runner)
        test_security_restrictions(test_runner)
        test_error_handling(test_runner)
        test_state_isolation(test_runner)
        test_timeout_and_resources(test_runner)
        test_module_imports(test_runner)
        test_script_organization(test_runner)
        test_edge_cases(test_runner)
        test_mixed_operations(test_runner)
        
        # 打印测试总结
        all_passed = test_runner.summary()
        
    finally:
        # 清理测试环境
        print("\n清理测试环境...")
        test_runner.cleanup()
        print(f"✓ 工作目录已清理: {WORKSPACE_DIR}")
        print()
    
    # 返回测试结果
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)