#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试受限沙箱（非 chroot 模式）

测试权限控制：
1. root_dir 内：可读写
2. readable_paths：只读
3. writable_paths：可读写
4. 其他绝对路径：自动加 root_dir 前缀
5. 相对路径：自动加 root_dir 前缀
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.sandbox.pycode_executor import CodeExecutor
from pathlib import Path


def test_restricted_sandbox():
    """测试受限沙箱的权限控制"""
    import tempfile

    # 创建临时测试目录
    with tempfile.TemporaryDirectory() as tmpdir:
        sandbox_dir = Path(tmpdir) / "sandbox"
        sandbox_dir.mkdir()

        readable_dir = Path(tmpdir) / "readonly"
        readable_dir.mkdir()
        (readable_dir / "test.txt").write_text("readonly content")

        writable_dir = Path(tmpdir) / "writable"
        writable_dir.mkdir()

        print("=" * 60)
        print("受限沙箱权限测试")
        print("=" * 60)
        print(f"沙箱目录: {sandbox_dir}")
        print(f"只读目录: {readable_dir}")
        print(f"可写目录: {writable_dir}")
        print()

        # 创建执行器
        executor = CodeExecutor(
            root_dir=str(sandbox_dir),
            readable_paths=[str(readable_dir)],
            writable_paths=[str(writable_dir)]
        )

        # 测试 1: root_dir 内可读写
        print("测试 1: root_dir 内可读写")
        print("-" * 60)
        result = executor.execute('python -c "open(\'test.txt\', \'w\').write(\'hello from sandbox\')"')
        if result.exit_code == 0:
            test_file = sandbox_dir / "test.txt"
            if test_file.exists() and test_file.read_text() == "hello from sandbox":
                print("✅ 正确：可以在 root_dir 内写入文件")
            else:
                print("❌ 异常：文件写入失败")
        else:
            print("❌ 异常：无法在 root_dir 内写入")
            print(f"错误: {result.output}")

        print()

        # 测试 2: 读取只读路径
        print("测试 2: 读取只读白名单路径")
        print("-" * 60)
        result = executor.execute(f'python -c "print(open(\'{readable_dir}/test.txt\').read())"')
        if "readonly content" in result.output:
            print("✅ 正确：可以读取 readable_paths 中的文件")
        else:
            print("❌ 异常：无法读取 readable_paths")
            print(f"输出: {result.output}")

        print()

        # 测试 3: 不能写入只读路径
        print("测试 3: 禁止写入只读路径")
        print("-" * 60)
        result = executor.execute(f'python -c "open(\'{readable_dir}/hack.txt\', \'w\').write(\'hack\')"')
        if result.exit_code != 0 and ("PermissionError" in result.output or "只读" in result.output):
            print("✅ 正确：无法写入只读路径")
        else:
            print("❌ 异常：应该无法写入只读路径")
            print(f"退出码: {result.exit_code}")
            print(f"输出: {result.output}")

        print()

        # 测试 4: 可以写入 writable_paths
        print("测试 4: 可以写入 writable_paths")
        print("-" * 60)
        result = executor.execute(f'python -c "open(\'{writable_dir}/test.txt\', \'w\').write(\'writable\')"')
        if result.exit_code == 0:
            test_file = writable_dir / "test.txt"
            if test_file.exists():
                print("✅ 正确：可以写入 writable_paths")
            else:
                print("❌ 异常：文件未创建")
        else:
            print("❌ 异常：无法写入 writable_paths")
            print(f"输出: {result.output}")

        print()

        # 测试 5: 绝对路径自动加 root_dir 前缀
        print("测试 5: 绝对路径自动加 root_dir 前缀")
        print("-" * 60)
        result = executor.execute('python -c "open(\'/auto_test.txt\', \'w\').write(\'auto\')"')
        if result.exit_code == 0:
            test_file = sandbox_dir / "auto_test.txt"
            if test_file.exists():
                print("✅ 正确：绝对路径自动加 root_dir 前缀")
            else:
                print("❌ 异常：文件未在正确位置")
        else:
            print("❌ 异常：执行失败")
            print(f"输出: {result.output}")

        print()

        # 测试 6: 相对路径自动加 root_dir 前缀
        print("测试 6: 相对路径自动加 root_dir 前缀")
        print("-" * 60)
        result = executor.execute('python -c "open(\'relative_test.txt\', \'w\').write(\'relative\')"')
        if result.exit_code == 0:
            test_file = sandbox_dir / "relative_test.txt"
            if test_file.exists():
                print("✅ 正确：相对路径自动加 root_dir 前缀")
            else:
                print("❌ 异常：文件未在正确位置")
        else:
            print("❌ 异常：执行失败")
            print(f"输出: {result.output}")

        print()

        # 测试 7: Path.write_text 也受限制
        print("测试 7: Path.write_text 受限")
        print("-" * 60)
        result = executor.execute(f'python -c "Path(\'{readable_dir}/path_hack.txt\').write_text(\'hack\')"')
        if result.exit_code != 0 and ("PermissionError" in result.output or "只读" in result.output or "危险模块" in result.output):
            print("✅ 正确：Path.write_text 也受权限控制")
        else:
            print("❌ 异常：Path.write_text 未受限制")
            print(f"退出码: {result.exit_code}")
            print(f"输出: {result.output}")

        print()

        # 测试 8: 不能使用 os.open
        print("测试 8: os.open 被禁用")
        print("-" * 60)
        result = executor.execute('python -c "import os; os.open(\'test.txt\', os.O_WRONLY)"')
        # os.open 在 AST 检查阶段被阻止，退出码为 -1
        if result.exit_code != 0 and ("危险函数" in result.output or "os.open" in result.output):
            print("✅ 正确：os.open 被禁用（AST检查）")
        else:
            print("❌ 异常：os.open 未被禁用")
            print(f"退出码: {result.exit_code}")
            print(f"输出: {result.output}")

        print()

        # 测试 9: 不能导入 io 模块
        print("测试 9: io 模块被阻止")
        print("-" * 60)
        result = executor.execute('python -c "import io"')
        if result.exit_code != 0 and ("危险模块" in result.output or "io" in result.output):
            print("✅ 正确：io 模块被阻止")
        else:
            print("❌ 异常：io 模块未被阻止")
            print(f"退出码: {result.exit_code}")
            print(f"输出: {result.output}")

        print()

        # 测试 10: Python 标准库可用
        print("测试 10: Python 标准库可用")
        print("-" * 60)
        result = executor.execute('python -c "import json; print(json.dumps({\'test\': \'success\'}))"')
        if result.exit_code == 0 and "success" in result.output:
            print("✅ 正确：Python 标准库可用")
        else:
            print("❌ 异常：Python 标准库不可用")
            print(f"输出: {result.output}")

        print()
        print("=" * 60)
        print("测试完成")
        print("=" * 60)


if __name__ == '__main__':
    test_restricted_sandbox()
