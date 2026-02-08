#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 chroot 沙箱模式
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.sandbox.pycode_executor import CodeExecutor

def test_chroot_mode():
    """测试 chroot 模式"""

    print("=" * 60)
    print("测试 chroot 沙箱模式")
    print("=" * 60)
    print(f"当前用户: {os.getenv('USER')}")
    print(f"UID: {os.getuid()}")
    print()

    # 使用 chroot 模式（需要 root 权限）
    executor = CodeExecutor(root_dir="/tmp/sandbox_chroot_test", timeout=5, use_chroot=True)

    print("测试 1: 尝试访问 root_dir 外的文件")
    result = executor.execute('python -c "open(\'/etc/passwd\', \'r\').read()"')
    print(f"输出: {result.output[:200] if result.output else '(空)'}")
    print(f"退出码: {result.exit_code}")
    if result.exit_code != 0:
        print("✅ chroot 生效：无法访问 /etc/passwd")
    else:
        print("❌ chroot 未生效：可以访问 /etc/passwd")

    print("\n测试 2: 尝试写入 root_dir 外的文件")
    result = executor.execute('python -c "open(\'/tmp/chroot_escape.txt\', \'w\').write(\'hacked!\')"')
    print(f"输出: {result.output[:200] if result.output else '(空)'}")
    print(f"退出码: {result.exit_code}")
    if os.path.exists('/tmp/chroot_escape.txt'):
        print("❌ chroot 未生效：文件被创建")
        os.remove('/tmp/chroot_escape.txt')
    else:
        print("✅ chroot 生效：无法在外部创建文件")

    print("\n测试 3: 在 root_dir 内正常写入")
    result = executor.execute('python -c "open(\'test.txt\', \'w\').write(\'hello!\')"')
    print(f"输出: {result.output[:200] if result.output else '(空)'}")
    print(f"退出码: {result.exit_code}")
    if os.path.exists('/tmp/sandbox_chroot_test/test.txt'):
        print("✅ 正常工作：可以在 root_dir 内写入文件")
        with open('/tmp/sandbox_chroot_test/test.txt', 'r') as f:
            print(f"文件内容: {f.read()}")
    else:
        print("❌ 异常：无法在 root_dir 内写入文件")

def test_compatibility_mode():
    """测试兼容模式（不需要 root）"""

    print("\n" + "=" * 60)
    print("测试兼容模式（不需要 root）")
    print("=" * 60)

    # 不使用 chroot
    executor = CodeExecutor(root_dir="/tmp/sandbox_compat_test", timeout=5, use_chroot=False)

    print("测试 1: 读取 root_dir 外的文件（应该允许）")
    result = executor.execute('python -c "content = open(\'/etc/hosts\', \'r\').read(); print(len(content))"')
    print(f"输出: {result.output[:200] if result.output else '(空)'}")
    print(f"退出码: {result.exit_code}")
    if result.exit_code == 0 and "len(content)" not in result.output:
        print("✅ 兼容模式生效：可以读取外部文件")
    else:
        print("⚠️  可能有问题")

    print("\n测试 2: 尝试写入 root_dir 外的文件（应该被拒绝）")
    result = executor.execute('python -c "open(\'/tmp/compat_escape.txt\', \'w\').write(\'hacked!\')"')
    print(f"输出: {result.output[:300] if result.output else '(空)'}")
    print(f"退出码: {result.exit_code}")
    if os.path.exists('/tmp/compat_escape.txt'):
        print("❌ 函数级限制未生效")
        os.remove('/tmp/compat_escape.txt')
    else:
        print("✅ 函数级限制生效：无法写入外部文件")

    print("\n测试 3: 在 root_dir 内写入（应该成功）")
    result = executor.execute('python -c "open(\'test.txt\', \'w\').write(\'hello!\')"')
    print(f"输出: {result.output[:200] if result.output else '(空)'}")
    print(f"退出码: {result.exit_code}")
    if os.path.exists('/tmp/sandbox_compat_test/test.txt'):
        print("✅ 正常：可以在 root_dir 内写入")
        with open('/tmp/sandbox_compat_test/test.txt', 'r') as f:
            print(f"文件内容: {f.read()}")
    else:
        print("❌ 异常：无法在 root_dir 内写入")

if __name__ == '__main__':
    # 先测试兼容模式（不需要 root）
    test_compatibility_mode()

    # 如果有 root 权限，测试 chroot 模式
    if os.geteuid() == 0:
        print("\n" + "=" * 60)
        print("检测到 root 权限，测试 chroot 模式")
        print("=" * 60)
        test_chroot_mode()
    else:
        print("\n" + "=" * 60)
        print("未检测到 root 权限，跳过 chroot 模式测试")
        print("请使用 sudo 运行此脚本以测试 chroot 模式：")
        print("  sudo python tests/test_sandbox/test_chroot_mode.py")
        print("=" * 60)
