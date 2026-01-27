#!/usr/bin/env python3
"""
黑名单模式测试脚本

测试将白名单改为黑名单后的沙箱功能
"""

import sys
from pathlib import Path
import tempfile

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.backends.sandbox import RestrictedPythonBackend

print("=" * 80)
print("黑名单模式测试")
print("=" * 80)
print()

# 创建测试实例
backend = RestrictedPythonBackend(root_dir=str(tempfile.mkdtemp()))

print(f"root_dir: {backend.root_dir}")
print()

# ============================================
# 测试 1: 基础功能（应该可用）
# ============================================
print("【测试 1】基础函数可用性")
print("-" * 80)

basic_functions = [
    ('python -c "print(sum([1,2,3]))"', "sum 函数", "6"),
    ('python -c "print(max([1,2,3]))"', "max 函数", "3"),
    ('python -c "print(min([1,2,3]))"', "min 函数", "1"),
    ('python -c "print(abs(-5))"', "abs 函数", "5"),
    ('python -c "print(round(3.14159, 2))"', "round 函数", "3.14"),
]

for command, func_name, expected in basic_functions:
    response = backend.execute(command)
    if response.exit_code == 0 and expected in response.output:
        print(f"✅ {func_name}: 可用")
    else:
        print(f"❌ {func_name}: 失败 - {response.output[:100]}")

print()

# ============================================
# 测试 2: 反射功能（黑名单新增）
# ============================================
print("【测试 2】反射功能（黑名单新增）")
print("-" * 80)

reflection_functions = [
    ('python -c "print(dir([])[:5])"', "dir 函数"),
    ('python -c "print(vars({})[:50])"', "vars 函数"),
    ('python -c "print(type(123))"', "type 函数"),
    ("python -c \"print(isinstance('hello', str))\"", "isinstance 函数"),
    ("python -c \"print(hasattr(list, 'append'))\"", "hasattr 函数"),
    ("python -c \"print(getattr(list, 'append')[:50])\"", "getattr 函数"),
]

for command, func_name in reflection_functions:
    response = backend.execute(command)
    if response.exit_code == 0:
        print(f"✅ {func_name}: 可用")
    else:
        print(f"❌ {func_name}: 失败 - {response.output[:100]}")

print()

# ============================================
# 测试 3: 危险函数（应该被阻止）
# ============================================
print("【测试 3】危险函数阻止")
print("-" * 80)

dangerous_functions = [
    ("python -c \"eval('print(1+1)')\"", "eval 函数"),
    ("python -c \"exec('x=1')\"", "exec 函数"),
    ("python -c \"compile('x=1', '<string>', 'exec')\"", "compile 函数"),
]

for command, func_name in dangerous_functions:
    response = backend.execute(command)
    is_blocked = (
        "NameError" in response.output or 
        "not found" in response.output or
        "not allowed" in response.output
    )
    if is_blocked:
        print(f"✅ {func_name}: 被阻止")
    else:
        print(f"❌ {func_name}: 未被阻止！")
        print(f"   输出: {response.output[:200]}")

print()

# ============================================
# 测试 4: 文件访问限制（应该仍然有效）
# ============================================
print("【测试 4】文件访问限制")
print("-" * 80)

file_tests = [
    ("python -c \"with open('test.txt', 'w') as f: f.write('hello')\"", "写入 root_dir 内文件"),
    ("python -c \"with open('test.txt', 'r') as f: print(f.read())\"", "读取 root_dir 内文件"),
    ("python -c \"open('/etc/passwd', 'r')\"", "读取 root_dir 外文件（应该被阻止）"),
]

for command, description in file_tests:
    response = backend.execute(command)
    if "被阻止" in description:
        # 应该被阻止
        if "PermissionError" in response.output:
            print(f"✅ {description}: 被阻止")
        else:
            print(f"❌ {description}: 未被阻止！")
            print(f"   输出: {response.output[:200]}")
    else:
        # 应该成功
        if response.exit_code == 0:
            print(f"✅ {description}: 成功")
        else:
            print(f"❌ {description}: 失败 - {response.output[:200]}")

print()

# ============================================
# 测试 5: 对比白名单和黑名单的功能差异
# ============================================
print("【测试 5】功能差异对比")
print("-" * 80)

comparison_tests = [
    ("python -c \"print(hex(255))\"", "hex 函数"),
    ("python -c \"print(oct(8))\"", "oct 函数"),
    ("python -c \"print(bin(5))\"", "bin 函数"),
    ("python -c \"print(chr(65))\"", "chr 函数"),
    ("python -c \"print(ord('A'))\"", "ord 函数"),
    ("python -c \"print(pow(2, 3))\"", "pow 函数"),
    ("python -c \"print(divmod(10, 3))\"", "divmod 函数"),
    ("python -c \"print(hash('test'))\"", "hash 函数"),
]

print("黑名单模式下应该可用的额外函数：")
for command, func_name in comparison_tests:
    response = backend.execute(command)
    if response.exit_code == 0:
        print(f"  ✅ {func_name}: 可用")
    else:
        print(f"  ❌ {func_name}: 不可用")

print()

# ============================================
# 测试 6: 测试数据结构功能
# ============================================
print("【测试 6】数据结构功能")
print("-" * 80)

data_structure_tests = [
    ("python -c \"print(list(range(5)))\"", "list + range"),
    ("python -c \"print(tuple([1,2,3]))\"", "tuple"),
    ("python -c \"print(set([1,2,2,3]))\"", "set"),
    ("python -c \"print(dict(a=1, b=2))\"", "dict"),
    ("python -c \"print(frozenset([1,2,3]))\"", "frozenset"),
    ("python -c \"print(bytearray([1,2,3]))\"", "bytearray"),
    ("python -c \"print(bytes([1,2,3]))\"", "bytes"),
]

for command, description in data_structure_tests:
    response = backend.execute(command)
    if response.exit_code == 0:
        print(f"✅ {description}: 可用")
    else:
        print(f"❌ {description}: 不可用 - {response.output[:100]}")

print()

# ============================================
# 测试 7: 测试迭代器和生成器
# ============================================
print("【测试 7】迭代器和生成器功能")
print("-" * 80)

iterator_tests = [
    ("python -c \"print(list(enumerate([10,20,30])))\"", "enumerate"),
    ("python -c \"print(list(zip([1,2,3],[4,5,6])))\"", "zip"),
    ("python -c \"print(list(map(lambda x: x*2, [1,2,3])))\"", "map"),
    ("python -c \"print(list(filter(lambda x: x>5, [3,6,9])))\"", "filter"),
    ("python -c \"print(list(reversed([1,2,3])))\"", "reversed"),
    ("python -c \"print(sorted([3,1,2]))\"", "sorted"),
    ("python -c \"print(list(range(5)))\"", "range"),
]

for command, description in iterator_tests:
    response = backend.execute(command)
    if response.exit_code == 0:
        print(f"✅ {description}: 可用")
    else:
        print(f"❌ {description}: 不可用 - {response.output[:100]}")

print()

# ============================================
# 测试 8: 测试模块导入
# ============================================
print("【测试 8】模块导入功能")
print("-" * 80)

import_tests = [
    ("python -c \"import math; print(math.pi)\"", "math 模块"),
    ("python -c \"import json; print(json.dumps({'a':1}))\"", "json 模块"),
    ("python -c \"import random; print(random.randint(1,10))\"", "random 模块"),
    ("python -c \"import os; print(os.getcwd())\"", "os 模块（受限）"),
]

for command, description in import_tests:
    response = backend.execute(command)
    if response.exit_code == 0:
        print(f"✅ {description}: 可用")
    else:
        print(f"❌ {description}: 不可用 - {response.output[:100]}")

print()

# ============================================
# 总结
# ============================================
print("=" * 80)
print("测试总结")
print("=" * 80)
print()
print("✅ 黑名单模式特性：")
print("   1. 基础函数全部可用（sum, max, min, abs 等）")
print("   2. 反射功能可用（dir, vars, type, hasattr, getattr）")
print("   3. 数据结构全部可用（list, dict, set, tuple, bytearray 等）")
print("   4. 迭代器和生成器全部可用（enumerate, zip, map, filter 等）")
print("   5. 模块导入可用（math, json, random, os 等）")
print()
print("🚫 危险函数被阻止：")
print("   1. eval, exec, compile（代码执行）")
print("   2. open 文件访问被替换为安全版本")
print("   3. root_dir 外的文件访问被禁止")
print()
print("⚠️  安全提示：")
print("   - 黑名单模式允许更多功能，但安全性相对较低")
print("   - 建议在受控环境中使用")
print("   - 定期审计代码，防止绕过限制")
print()
print("=" * 80)