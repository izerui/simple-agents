#!/usr/bin/env python3
"""
测试路径处理规则

验证：
1. 相对路径：自动添加 root_dir 前缀
2. 绝对路径：
   - 在 root_dir 内可读写
   - 只读白名单内可读
   - 读写白名单内可读写
   - 其他绝对路径：自动添加 root_dir 前缀后可读写
"""

import sys
import os
import tempfile
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.sandbox.pycode_executor import CodeExecutor


def test_relative_path():
    """测试相对路径自动添加 root_dir 前缀"""
    print("\n[测试 1] 相对路径自动添加 root_dir 前缀")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        executor = CodeExecutor(root_dir=tmpdir)

        # 创建相对路径文件
        result = executor.execute('python -c "open(\'test.txt\', \'w\').write(\'content\'); print(\'Success\')"')

        if result.exit_code == 0:
            test_file = Path(tmpdir) / 'test.txt'
            if test_file.exists() and test_file.read_text() == 'content':
                print("✅ 相对路径正确添加 root_dir 前缀")
                return True
            else:
                print(f"❌ 文件未创建在正确位置: {test_file}")
                return False
        else:
            print(f"❌ 执行失败: {result.output}")
            return False


def test_absolute_path_in_root():
    """测试绝对路径在 root_dir 内可读写"""
    print("\n[测试 2] 绝对路径在 root_dir 内可读写")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        executor = CodeExecutor(root_dir=tmpdir)

        # 在 root_dir 内创建文件（使用绝对路径）
        test_file = Path(tmpdir) / 'test.txt'
        result = executor.execute(f'python -c "open(\'{test_file}\', \'w\').write(\'content\'); print(\'Success\')"')

        if result.exit_code == 0:
            if test_file.exists() and test_file.read_text() == 'content':
                print("✅ root_dir 内的绝对路径可读写")
                return True
            else:
                print(f"❌ 文件操作失败: {test_file}")
                return False
        else:
            print(f"❌ 执行失败: {result.output}")
            return False


def test_readable_paths():
    """测试只读白名单内可读"""
    print("\n[测试 3] 只读白名单内可读")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir_root:
        # 创建只读目录（在 root_dir 外）
        readonly_dir = Path(tmpdir_root) / 'readonly'
        readonly_dir.mkdir()
        readonly_file = readonly_dir / 'readonly.txt'
        readonly_file.write_text('readonly content')

        # root_dir 应该是 tmpdir_root 的子目录
        root_dir = Path(tmpdir_root) / 'sandbox'
        root_dir.mkdir()

        executor = CodeExecutor(
            root_dir=root_dir,
            readable_paths=[str(readonly_dir)]
        )

        # 读取应该成功
        result = executor.execute(f'python -c "content = open(\'{readonly_file}\', \'r\').read(); print(content)"')

        if result.exit_code == 0 and 'readonly content' in result.output:
            print("✅ 只读白名单内可读")
        else:
            print(f"❌ 读取失败: {result.output}")
            return False

        # 写入应该失败
        result = executor.execute(f'python -c "open(\'{readonly_file}\', \'w\').write(\'new\')"')

        if result.exit_code != 0 and ('PermissionError' in result.output or '只读' in result.output):
            print("✅ 只读白名单禁止写入")
            return True
        else:
            print(f"❌ 写入未被阻止: {result.output}")
            return False


def test_writable_paths():
    """测试读写白名单内可读写"""
    print("\n[测试 4] 读写白名单内可读写")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir_root:
        # 创建可写目录（在 root_dir 外）
        writable_dir = Path(tmpdir_root) / 'writable'
        writable_dir.mkdir()

        # root_dir 应该是 tmpdir_root 的子目录
        root_dir = Path(tmpdir_root) / 'sandbox'
        root_dir.mkdir()

        executor = CodeExecutor(
            root_dir=root_dir,
            writable_paths=[str(writable_dir)]
        )

        # 写入应该成功
        writable_file = writable_dir / 'writable.txt'
        result = executor.execute(f'python -c "open(\'{writable_file}\', \'w\').write(\'writable\'); print(\'Success\')"')

        if result.exit_code == 0:
            if writable_file.exists() and writable_file.read_text() == 'writable':
                print("✅ 读写白名单内可写")
            else:
                print(f"❌ 文件未创建: {writable_file}")
                return False
        else:
            print(f"❌ 写入失败: {result.output}")
            return False

        # 读取应该成功
        result = executor.execute(f'python -c "content = open(\'{writable_file}\', \'r\').read(); print(content)"')

        if result.exit_code == 0 and 'writable' in result.output:
            print("✅ 读写白名单内可读")
            return True
        else:
            print(f"❌ 读取失败: {result.output}")
            return False


def test_absolute_path_redirect():
    """测试其他绝对路径自动添加 root_dir 前缀"""
    print("\n[测试 5] 其他绝对路径自动添加 root_dir 前缀")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        executor = CodeExecutor(root_dir=tmpdir)

        # 尝试在根目录创建文件（应该被重定向到 root_dir）
        result = executor.execute('python -c "open(\'/redirected.txt\', \'w\').write(\'redirected\'); print(\'Success\')"')

        if result.exit_code == 0:
            # 检查文件是否创建在 root_dir 内
            redirected_file = Path(tmpdir) / 'redirected.txt'
            if redirected_file.exists() and redirected_file.read_text() == 'redirected':
                print("✅ 其他绝对路径正确重定向到 root_dir")
                return True
            else:
                print(f"❌ 文件未创建在 root_dir: {redirected_file}")
                return False
        else:
            print(f"❌ 执行失败: {result.output}")
            return False


def test_nested_path_redirect():
    """测试嵌套路径重定向"""
    print("\n[测试 6] 嵌套路径重定向")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        executor = CodeExecutor(root_dir=tmpdir)

        # 尝试创建嵌套目录（应该被重定向到 root_dir）
        result = executor.execute('python -c "import os; os.makedirs(\'/a/b/c\', exist_ok=True); open(\'/a/b/c/test.txt\', \'w\').write(\'nested\'); print(\'Success\')"')

        if result.exit_code == 0:
            # 检查文件是否创建在 root_dir 内
            nested_file = Path(tmpdir) / 'a' / 'b' / 'c' / 'test.txt'
            if nested_file.exists() and nested_file.read_text() == 'nested':
                print("✅ 嵌套路径正确重定向到 root_dir")
                return True
            else:
                print(f"❌ 文件未创建在正确位置: {nested_file}")
                return False
        else:
            print(f"❌ 执行失败: {result.output}")
            return False


def test_open_with_os_functions():
    """测试 os 函数也遵循路径重定向规则"""
    print("\n[测试 7] os 函数路径重定向")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        executor = CodeExecutor(root_dir=tmpdir)

        # os.makedirs 创建嵌套目录
        result = executor.execute('python -c "import os; os.makedirs(\'/os/test/dir\', exist_ok=True); print(\'Success\')"')

        if result.exit_code == 0:
            os_dir = Path(tmpdir) / 'os' / 'test' / 'dir'
            if os_dir.exists() and os_dir.is_dir():
                print("✅ os.makedirs 正确重定向")
            else:
                print(f"❌ 目录未创建: {os_dir}")
                return False
        else:
            print(f"❌ 执行失败: {result.output}")
            return False

        # os.rename 重命名文件
        (Path(tmpdir) / 'old.txt').write_text('test')
        result = executor.execute('python -c "import os; os.rename(\'/old.txt\', \'/new.txt\'); print(\'Success\')"')

        if result.exit_code == 0:
            if not (Path(tmpdir) / 'old.txt').exists() and (Path(tmpdir) / 'new.txt').exists():
                print("✅ os.rename 正确重定向")
                return True
            else:
                print(f"❌ 重命名失败")
                return False
        else:
            print(f"❌ 执行失败: {result.output}")
            return False


def main():
    """运行所有测试"""
    print("=" * 80)
    print("路径处理规则测试")
    print("=" * 80)

    tests = [
        test_relative_path,
        test_absolute_path_in_root,
        test_readable_paths,
        test_writable_paths,
        test_absolute_path_redirect,
        test_nested_path_redirect,
        test_open_with_os_functions,
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
    passed = sum(results)
    total = len(results)
    print(f"测试结果: {passed}/{total} 通过")

    if passed == total:
        print("✅ 所有路径处理规则验证通过！")
    else:
        print(f"❌ 有 {total - passed} 个测试失败")

    print("=" * 80)

    return all(results)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
