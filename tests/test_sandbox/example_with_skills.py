#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
chroot 沙箱中使用外部文件的示例

问题：在 chroot 模式下，无法访问 root_dir 外的文件
解决：使用 setup_files() 预先复制需要的文件
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.sandbox.pycode_executor import CodeExecutor

def example_with_external_files():
    """示例：在沙箱中使用 find-skills 脚本"""

    print("=" * 60)
    print("chroot 沙箱中使用外部文件示例")
    print("=" * 60)
    print()

    # 检查 root 权限
    if os.geteuid() != 0:
        print("❌ 需要 root 权限运行")
        print("请使用: sudo python tests/test_sandbox/example_with_skills.py")
        return

    # 创建执行器
    executor = CodeExecutor(root_dir="/tmp/sandbox_example", timeout=30)

    # 设置文件映射：将项目文件复制到沙箱
    file_mappings = {
        # 沙箱内路径        # 实际文件路径
        '/skills/': 'src/skills/',
        '/skills/find-skills/': 'src/skills/find-skills/',
    }

    print("步骤 1: 复制文件到沙箱...")
    executor.setup_files(file_mappings)
    print()

    # 现在可以在沙箱内使用这些文件了
    print("步骤 2: 执行脚本...")
    result = executor.execute('python /skills/find-skills/scripts/install_skill.py -s "claude-code-review"')

    print("执行结果:")
    print(f"退出码: {result.exit_code}")
    print(f"输出:\n{result.output}")

    print()
    print("=" * 60)
    print("✅ 完成！")
    print("=" * 60)

if __name__ == '__main__':
    example_with_external_files()
