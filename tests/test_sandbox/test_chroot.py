#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 chroot 是否可用
"""
import os
import sys
from pathlib import Path

def test_chroot_permission():
    """测试是否有权限使用 chroot"""

    root_dir = Path("/tmp/sandbox_test_chroot")
    root_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("测试 chroot 权限")
    print("=" * 60)
    print(f"当前用户: {os.getenv('USER')}")
    print(f"UID: {os.getuid()}")
    print(f"有效 UID: {os.geteuid()}")
    print()

    try:
        print(f"尝试 chroot 到 {root_dir}")
        os.chroot(root_dir)
        print("✅ chroot 成功！")

        # 测试是否能访问外部文件
        print("\n尝试访问 /etc/passwd:")
        try:
            with open('/etc/passwd', 'r') as f:
                content = f.read()
            print(f"✅ 能读取 /etc/passwd (长度: {len(content)})")
            if 'root' in content:
                print("⚠️  这说明 chroot 没有生效，读取的是系统的 /etc/passwd")
            else:
                print("✅ chroot 生效，读取的是沙箱内的 /etc/passwd")
        except FileNotFoundError:
            print("✅ chroot 生效，无法访问系统的 /etc/passwd")

    except PermissionError as e:
        print(f"❌ 权限错误: {e}")
        print("\n需要 root 权限才能使用 chroot")
        print("尝试使用 sudo 运行此脚本")
    except Exception as e:
        print(f"❌ 其他错误: {type(e).__name__}: {e}")

    # 清理
    original_root = Path("/")
    # 注意：chroot 后无法清理，需要在外部清理

if __name__ == '__main__':
    test_chroot_permission()
