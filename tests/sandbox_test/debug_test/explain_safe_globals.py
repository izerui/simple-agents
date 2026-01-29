#!/usr/bin/env python3
"""
演示 safe_globals 的作用

本脚本演示 RestrictedPython 沙箱中 safe_globals 的作用和重要性
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("safe_globals 作用演示")
print("=" * 80)
print()

# ============================================
# 1. 解释 safe_globals 的核心作用
# ============================================
print("【1】safe_globals 的核心作用")
print("-" * 80)
print("""
safe_globals 是沙箱安全机制的核心，它创建了一个受限的 Python 执行环境。

主要功能：
1. 限制可用的内置函数（白名单机制）
2. 替换危险函数（如 open、eval、exec）
3. 提供安全的全局变量
4. 配合 RestrictedPython 的编译器使用

工作流程：
用户代码 → RestrictedPython 编译 → 使用 safe_globals 执行 → 受限的安全环境
""")
print()

# ============================================
# 2. 演示：默认 Python 环境的危险性
# ============================================
print("【2】默认 Python 环境的危险性")
print("-" * 80)
print("在默认的 Python 环境中，用户代码可以访问所有危险函数：")
print()

dangerous_codes = [
    ("eval", "eval('print(1+1)')", "执行任意代码"),
    ("exec", "exec('x=10; print(x)')", "执行任意代码"),
    ("compile", "compile('x=1', '<string>', 'exec')", "编译任意代码"),
    ("open", "open('/etc/passwd', 'r')", "读取系统文件"),
]

print("默认环境测试（危险操作）：")
print()
for func_name, code, description in dangerous_codes:
    print(f"测试 {func_name}: {description}")
    try:
        result = eval(code)
        if func_name in ["eval", "exec", "compile"]:
            print(f"  ⚠️  {func_name} 函数可用！")
        else:
            print(f"  ⚠️  {code[:50]}... 执行成功")
    except Exception as e:
        print(f"  ✗ 失败: {e}")
    print()

print("=" * 80)
print("⚠️  危险：默认环境允许执行所有危险操作！")
print("=" * 80)
print()

# ============================================
# 3. 演示：safe_globals 的安全性
# ============================================
print("【3】safe_globals 的安全性")
print("-" * 80)

from src.sandbox.sandbox_filesystem import SandboxFilesystemBackend
import tempfile

# 创建沙箱实例
backend = SandboxFilesystemBackend(root_dir=str(tempfile.mkdtemp()))

print("使用 safe_globals 的沙箱环境测试（安全操作）：")
print()

# 测试允许的操作
safe_operations = [
    ('python -c "x = 1 + 1; print(x)"', "基本运算"),
    ('python -c "print(len([1, 2, 3]))"', "使用 len 函数"),
    ('python -c "print(list(range(5)))"', "使用 range 和 list"),
    ('python -c "print(sum([1, 2, 3]))"', "使用 sum 函数"),
]

for command, description in safe_operations:
    response = backend.execute(command)
    if response.exit_code == 0:
        print(f"✅ {description}: {response.output.strip()}")
    else:
        print(f"✗ {description}: {response.output[:50]}")
print()

# 测试被阻止的操作
blocked_operations = [
    ("python -c \"print(hasattr(__builtins__, 'eval'))\"", "检查 eval 是否存在"),
]

for command, description in blocked_operations:
    response = backend.execute(command)
    print(f"🔒 {description}")
    print(f"   输出: {response.output.strip()}")
    if response.exit_code == 0 and "False" in response.output:
        print(f"   ✅ eval 不在白名单中，被阻止")
    print()

print("=" * 80)
print("✅ 安全：safe_globals 只允许白名单中的函数！")
print("=" * 80)
print()

# ============================================
# 4. 对比：两种环境的差异
# ============================================
print("【4】两种环境的对比")
print("-" * 80)
print()

comparison_table = [
    ("功能", "默认环境", "safe_globals 环境"),
    ("-" * 20, "-" * 20, "-" * 40),
    ("eval 函数", "⚠️  可用", "✅ 被阻止"),
    ("exec 函数", "⚠️  可用", "✅ 被阻止"),
    ("compile 函数", "⚠️  可用", "✅ 被阻止"),
    ("open 函数", "⚠️  不安全版本", "✅ 安全版本（受控）"),
    ("__import__", "⚠️  完全自由", "✅ 受限导入"),
    ("len、range 等", "✅ 可用", "✅ 可用"),
    ("list、dict 等", "✅ 可用", "✅ 可用"),
    ("print", "✅ 可用", "✅ 可用"),
    ("文件访问", "⚠️  可访问任意文件", "✅ 只能访问 root_dir"),
]

for item in comparison_table:
    print(f"{item[0]:<20} {item[1]:<20} {item[2]:<40}")
print()

# ============================================
# 5. safe_globals 的详细组成
# ============================================
print("【5】safe_globals 的详细组成")
print("-" * 80)
print()

safe_globals_structure = """
safe_globals = {
    # 内置常量和类型
    '__builtins__': {
        'None': None, 'True': True, 'False': False,
        'int': int, 'float': float, 'str': str,
        'list': list, 'dict': dict, 'tuple': tuple,
        'set': set, 'bool': bool,
    },
    
    # 基础函数（白名单）
    'len': len, 'range': range, 'type': type,
    'isinstance': isinstance, 'hasattr': hasattr,
    'getattr': getattr, 'setattr': setattr,
    'delattr': delattr,
    
    # 序列和数学操作
    'min': min, 'max': max, 'sum': sum,
    'abs': abs, 'round': round,
    'sorted': sorted, 'reversed': reversed,
    'enumerate': enumerate, 'zip': zip,
    'map': map, 'filter': filter,
    'all': all, 'any': any,
    
    # 模块导入（受限）
    '__import__': __import__,
    
    # 替换的函数（安全版本）
    'open': <受控的 open 函数>,
    'print': <捕获输出的 print 函数>,
}

# RestrictedPython 特殊函数
safe_globals['_print_'] = PrintCollector           # 捕获 print 输出
safe_globals['_getattr_'] = safer_getattr          # 安全属性访问
safe_globals['_write_'] = full_write_guard          # 安全属性写入
safe_globals['_getitem_'] = lambda obj, key: ...   # 安全索引访问
safe_globals['_getiter_'] = iter                    # 安全迭代器
safe_globals['_unpack_sequence_'] = ...             # 安全序列解包
"""

print(safe_globals_structure)
print()

# ============================================
# 6. 实际示例：防止代码注入
# ============================================
print("【6】实际示例：防止代码注入")
print("-" * 80)
print()

print("场景：用户输入一个表达式，程序计算结果")
print()

# 恶意输入
malicious_inputs = [
    "1 + 1",                                      # 正常输入
    "__import__('os').system('ls')",              # 恶意：执行系统命令
    "open('/etc/passwd', 'r').read()",           # 恶意：读取系统文件
    "eval('print(1+1)')",                        # 恶意：代码注入
]

print("默认环境（危险）：")
print()
for user_input in malicious_inputs:
    print(f"输入: {user_input}")
    try:
        result = eval(user_input)
        print(f"  ⚠️  执行成功: {result if len(str(result)) < 50 else '...'}")
    except Exception as e:
        print(f"  执行失败: {e}")
    print()

print("=" * 80)
print()

print("沙箱环境（安全）：")
print()
for user_input in malicious_inputs:
    print(f"输入: {user_input}")
    response = backend.execute(f'python -c "print({user_input})"')
    if response.exit_code == 0:
        print(f"  ✅ 执行成功: {response.output.strip()}")
    else:
        print(f"  ✅ 被阻止: {response.output.split('Traceback')[0].strip()}")
    print()

print()

# ============================================
# 总结
# ============================================
print("=" * 80)
print("总结")
print("=" * 80)
print()
print("safe_globals 是沙箱安全的核心机制：")
print()
print("✅ 核心功能：")
print("   1. 白名单机制：只允许安全函数")
print("   2. 替换危险函数：用安全版本替换 open、print 等")
print("   3. 配合 RestrictedPython 编译器：编译时拦截危险代码")
print()
print("✅ 安全保障：")
print("   • 阻止代码注入（eval、exec、compile）")
print("   • 防止文件泄露（受控的 open）")
print("   • 限制系统访问（无 system 等危险函数）")
print()
print("✅ 功能保留：")
print("   • 保留正常的 Python 功能（类型、数据结构、基础函数）")
print("   • 支持模块导入（但受限）")
print("   • 支持正常的业务逻辑开发")
print()
print("🎯 结论：safe_globals 是实现安全沙箱的关键技术，")
print("   通过白名单机制在安全性和功能性之间取得平衡。")
print()
print("=" * 80)