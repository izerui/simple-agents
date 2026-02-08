#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试纯 chroot 沙箱模式

运行方式：
  sudo python tests/test_sandbox/test_chroot_only.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.sandbox.pycode_executor import CodeExecutor

def test_chroot_isolation():
    """测试 chroot 隔离效果"""

    print("=" * 60)
    print("测试 chroot 沙箱隔离")
    print("=" * 60)
    print(f"当前用户: {os.getenv('USER')}")
    print(f"UID: {os.getuid()}")
    print(f"有效 UID: {os.geteuid()}")
    print()

    if os.geteuid() != 0:
        print("❌ 需要 root 权限运行")
        print("请使用: sudo python tests/test_sandbox/test_chroot_only.py")
        return

    # 创建执行器
    executor = CodeExecutor(root_dir="/tmp/sandbox_chroot_only", timeout=5)

    # 测试 1: 无法访问外部文件
    print("测试 1: 尝试访问 /etc/passwd")
    print("-" * 60)
    result = executor.execute('python -c "with open(\'/etc/passwd\', \'r\') as f: print(f.read()[:100])"')
    print(f"退出码: {result.exit_code}")
    if result.exit_code != 0:
        print("✅ 正确：无法访问系统的 /etc/passwd")
    else:
        print("❌ 异常：可以访问系统的 /etc/passwd")
        print(f"输出: {result.output[:100]}")

    # 测试 2: 无法写入外部文件
    print("\n测试 2: 尝试写入 /tmp/")
    print("-" * 60)
    result = executor.execute('python -c "open(\'/tmp/chroot_test.txt\', \'w\').write(\'hacked!\')"')
    print(f"退出码: {result.exit_code}")
    if os.path.exists('/tmp/chroot_test.txt'):
        print("❌ 异常：成功写入 /tmp/")
        os.remove('/tmp/chroot_test.txt')
    else:
        print("✅ 正确：无法写入 /tmp/")

    # 测试 3: 可以在 sandbox 内正常操作
    print("\n测试 3: 在 sandbox 内读写文件")
    print("-" * 60)
    result = executor.execute('python -c "open(\'test.txt\', \'w\').write(\'Hello, chroot!\'); print(open(\'test.txt\').read())"')
    print(f"退出码: {result.exit_code}")
    print(f"输出: {result.output.strip()}")
    if os.path.exists('/tmp/sandbox_chroot_only/test.txt'):
        print("✅ 正确：可以在 sandbox 内读写文件")
    else:
        print("❌ 异常：无法在 sandbox 内操作")

    # 测试 4: import pathlib 可以使用（chroot 已隔离）
    print("\n测试 4: 使用 pathlib 模块")
    print("-" * 60)
    result = executor.execute('python -c "from pathlib import Path; Path(\'test2.txt\').write_text(\'pathlib works!\'); print(Path(\'test2.txt\').read_text())"')
    print(f"退出码: {result.exit_code}")
    print(f"输出: {result.output.strip()}")
    if os.path.exists('/tmp/sandbox_chroot_only/test2.txt'):
        print("✅ 正确：pathlib 在 sandbox 内正常工作")
    else:
        print("❌ 异常：pathlib 无法正常工作")

    # 测试 5: 使用 os 模块
    print("\n测试 5: 使用 os 模块")
    print("-" * 60)
    result = executor.execute('python -c "import os; print(os.getcwd()); print(os.listdir(\'/\'))"')
    print(f"退出码: {result.exit_code}")
    print(f"输出:\n{result.output}")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == '__main__':
    test_chroot_isolation()
