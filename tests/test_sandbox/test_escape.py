#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试沙箱逃逸漏洞 - 调试版本
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.sandbox.pycode_executor import CodeExecutor

def test_sandbox_escape():
    """测试各种沙箱逃逸方法"""

    executor = CodeExecutor(root_dir="/tmp/sandbox_test", timeout=5)

    print("=" * 60)
    print("测试 3: 使用 Path 类写入系统目录")
    print("=" * 60)
    result = executor.execute('python -c "from pathlib import Path; Path(\'/tmp/escape_test_3.txt\').write_text(\'hacked!\')"')
    print("输出:", repr(result.output))
    print("退出码:", result.exit_code)
    if os.path.exists('/tmp/escape_test_3.txt'):
        print("❌ 漏洞: 文件被创建")
        os.remove('/tmp/escape_test_3.txt')
    else:
        print("✅ 安全: 文件未被创建")

    print("\n" + "=" * 60)
    print("测试 4: 使用 os.open 写入")
    print("=" * 60)
    result = executor.execute('python -c "import os; os.open(\'/tmp/escape_test_4.txt\', os.O_WRONLY | os.O_CREAT, 0o644)"')
    print("输出:", repr(result.output))
    print("退出码:", result.exit_code)
    if os.path.exists('/tmp/escape_test_4.txt'):
        print("❌ 漏洞: 文件被创建")
        os.remove('/tmp/escape_test_4.txt')
    else:
        print("✅ 安全: 文件未被创建")

    print("\n" + "=" * 60)
    print("测试 6: 读取 root_dir 外的文件（应该允许）")
    print("=" * 60)
    result = executor.execute('python -c "content = open(\'/etc/hostname\', \'r\').read(); print(repr(content[:100]))"')
    print("输出:", repr(result.output))
    print("退出码:", result.exit_code)

if __name__ == '__main__':
    test_sandbox_escape()
