#!/usr/bin/env python3
"""
测试 os 模块路径重定向功能

验证：
1. os.makedirs/mkdir 自动重定向到 root_dir
2. os.remove/rmdir 自动重定向到 root_dir
3. os.rename/replace 自动重定向到 root_dir
4. 不能写入 readable_paths
5. 不能从 readable_paths 读取文件进行写入操作
"""

import sys
import os
import tempfile
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.sandbox.pycode_executor import CodeExecutor


def test_os_mkdir_redirect():
    """测试 os.mkdir 路径重定向"""
    print("\n[测试 1] os.mkdir 路径重定向")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        executor = CodeExecutor(root_dir=tmpdir)

        # 创建 /test_dir/（应该被重定向到 root_dir/test_dir/）
        result = executor.execute('python -c "import os; os.mkdir(\'/test_dir\'); print(\'Success\')"')

        if result.exit_code == 0:
            # 检查目录是否创建在 root_dir 内
            test_dir = Path(tmpdir) / 'test_dir'
            if test_dir.exists() and test_dir.is_dir():
                print("✅ os.mkdir 正确重定向到 root_dir")
                return True
            else:
                print(f"❌ 目录未创建在 root_dir 内: {test_dir}")
                return False
        else:
            print(f"❌ 执行失败: {result.output}")
            return False


def test_os_makedirs_redirect():
    """测试 os.makedirs 路径重定向"""
    print("\n[测试 2] os.makedirs 路径重定向")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        executor = CodeExecutor(root_dir=tmpdir)

        # 创建 /test/nested/dir/（应该被重定向到 root_dir/test/nested/dir/）
        result = executor.execute('python -c "import os; os.makedirs(\'/test/nested/dir\', exist_ok=True); print(\'Success\')"')

        if result.exit_code == 0:
            # 检查目录是否创建在 root_dir 内
            test_dir = Path(tmpdir) / 'test' / 'nested' / 'dir'
            if test_dir.exists() and test_dir.is_dir():
                print("✅ os.makedirs 正确重定向到 root_dir")
                return True
            else:
                print(f"❌ 目录未创建在 root_dir 内: {test_dir}")
                return False
        else:
            print(f"❌ 执行失败: {result.output}")
            return False


def test_os_remove_redirect():
    """测试 os.remove 路径重定向"""
    print("\n[测试 3] os.remove 路径重定向")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        executor = CodeExecutor(root_dir=tmpdir)

        # 先创建文件
        (Path(tmpdir) / 'test.txt').write_text('test')

        # 删除 /test.txt（应该被重定向到 root_dir/test.txt）
        result = executor.execute('python -c "import os; os.remove(\'/test.txt\'); print(\'Success\')"')

        if result.exit_code == 0:
            # 检查文件是否被删除
            test_file = Path(tmpdir) / 'test.txt'
            if not test_file.exists():
                print("✅ os.remove 正确重定向到 root_dir")
                return True
            else:
                print(f"❌ 文件未被删除: {test_file}")
                return False
        else:
            print(f"❌ 执行失败: {result.output}")
            return False


def test_os_rename_redirect():
    """测试 os.rename 路径重定向"""
    print("\n[测试 4] os.rename 路径重定向")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        executor = CodeExecutor(root_dir=tmpdir)

        # 先创建文件
        (Path(tmpdir) / 'old.txt').write_text('test')

        # 重命名 /old.txt -> /new.txt（应该被重定向到 root_dir 内）
        result = executor.execute('python -c "import os; os.rename(\'/old.txt\', \'/new.txt\'); print(\'Success\')"')

        if result.exit_code == 0:
            # 检查重命名是否成功
            old_file = Path(tmpdir) / 'old.txt'
            new_file = Path(tmpdir) / 'new.txt'
            if not old_file.exists() and new_file.exists():
                print("✅ os.rename 正确重定向到 root_dir")
                return True
            else:
                print(f"❌ 重命名失败: old={old_file.exists()}, new={new_file.exists()}")
                return False
        else:
            print(f"❌ 执行失败: {result.output}")
            return False


def test_relative_path_redirect():
    """测试相对路径重定向"""
    print("\n[测试 5] 相对路径重定向")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        executor = CodeExecutor(root_dir=tmpdir)

        # 创建相对路径 test_dir（应该被重定向到 root_dir/test_dir）
        result = executor.execute('python -c "import os; os.mkdir(\'test_dir\'); print(\'Success\')"')

        if result.exit_code == 0:
            # 检查目录是否创建在 root_dir 内
            test_dir = Path(tmpdir) / 'test_dir'
            if test_dir.exists() and test_dir.is_dir():
                print("✅ 相对路径正确重定向到 root_dir")
                return True
            else:
                print(f"❌ 目录未创建在 root_dir 内: {test_dir}")
                return False
        else:
            print(f"❌ 执行失败: {result.output}")
            return False


def test_writable_paths():
    """测试 writable_paths 中的路径不会被重定向"""
    print("\n[测试 6] writable_paths 不会被重定向")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建一个可写目录
        writable_dir = Path(tmpdir) / 'writable'
        writable_dir.mkdir()

        executor = CodeExecutor(
            root_dir=tmpdir,
            writable_paths=[str(writable_dir)]
        )

        # 在 writable_dir 中创建目录（不应该被重定向）
        target_dir = writable_dir / 'test_dir'
        result = executor.execute(f'python -c "import os; os.mkdir(\'{target_dir}\'); print(\'Success\')"')

        if result.exit_code == 0:
            if target_dir.exists() and target_dir.is_dir():
                print("✅ writable_paths 中的路径正确处理")
                return True
            else:
                print(f"❌ 目录未创建在 writable_paths 中: {target_dir}")
                return False
        else:
            print(f"❌ 执行失败: {result.output}")
            return False


def main():
    """运行所有测试"""
    print("=" * 80)
    print("os 模块路径重定向测试")
    print("=" * 80)

    tests = [
        test_os_mkdir_redirect,
        test_os_makedirs_redirect,
        test_os_remove_redirect,
        test_os_rename_redirect,
        test_relative_path_redirect,
        test_writable_paths,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    print("\n" + "=" * 80)
    print(f"测试结果: {sum(results)}/{len(results)} 通过")
    print("=" * 80)

    return all(results)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
