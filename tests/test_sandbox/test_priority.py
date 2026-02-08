#!/usr/bin/env python3
"""
测试路径检查优先级顺序

验证严格按照以下顺序执行：
1. 相对路径：自动添加 root_dir 前缀
2. 绝对路径：
   - 在root_dir内：可读写
   - 只读白名单内：只读
   - 读写白名单内：可读写
   - 其他：自动添加 root_dir 前缀后可读写
"""

import sys
import os
import tempfile
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.sandbox.pycode_executor import CodeExecutor


def test_priority_order():
    """测试路径检查优先级"""
    print("\n[测试] 路径检查优先级顺序")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir_root:
        # 创建目录结构
        root_dir = Path(tmpdir_root) / 'root'
        root_dir.mkdir()

        readonly_dir = Path(tmpdir_root) / 'readonly'
        readonly_dir.mkdir()

        writable_dir = Path(tmpdir_root) / 'writable'
        writable_dir.mkdir()

        # 在 root_dir 内创建文件
        (root_dir / 'in_root.txt').write_text('in root')

        # 在 readonly_dir 内创建文件
        (readonly_dir / 'in_readonly.txt').write_text('in readonly')

        # 在 writable_dir 内创建文件
        (writable_dir / 'in_writable.txt').write_text('in writable')

        executor = CodeExecutor(
            root_dir=root_dir,
            readable_paths=[str(readonly_dir)],
            writable_paths=[str(writable_dir)]
        )

        all_passed = True

        # 测试 1: 相对路径
        print("\n1. 相对路径应该重定向到 root_dir")
        result = executor.execute('python -c "open(\'relative.txt\', \'w\').write(\'relative\')"')
        relative_file = root_dir / 'relative.txt'
        if relative_file.exists() and relative_file.read_text() == 'relative':
            print("   ✅ 相对路径正确重定向到 root_dir")
        else:
            print(f"   ❌ 相对路径未正确重定向: {relative_file}")
            all_passed = False

        # 测试 2: root_dir 内的文件可读写
        print("\n2. root_dir 内的文件应该可读写")
        result = executor.execute(f'python -c "content = open(\'{root_dir}/in_root.txt\', \'r\').read(); print(content)"')
        if 'in root' in result.output:
            print("   ✅ root_dir 内可读")
        else:
            print(f"   ❌ root_dir 内读取失败: {result.output}")
            all_passed = False

        result = executor.execute(f'python -c "open(\'{root_dir}/in_root.txt\', \'w\').write(\'modified\')"')
        if (root_dir / 'in_root.txt').read_text() == 'modified':
            print("   ✅ root_dir 内可写")
        else:
            print(f"   ❌ root_dir 内写入失败")
            all_passed = False

        # 测试 3: readonly 内的文件只读
        print("\n3. readonly 白名单内的文件应该只读")
        result = executor.execute(f'python -c "content = open(\'{readonly_dir}/in_readonly.txt\', \'r\').read(); print(content)"')
        if 'in readonly' in result.output:
            print("   ✅ readonly 白名单内可读")
        else:
            print(f"   ❌ readonly 白名单内读取失败: {result.output}")
            all_passed = False

        result = executor.execute(f'python -c "open(\'{readonly_dir}/in_readonly.txt\', \'w\').write(\'hack\')"')
        if result.exit_code != 0 and ('PermissionError' in result.output or '只读' in result.output):
            print("   ✅ readonly 白名单禁止写入")
        else:
            print(f"   ❌ readonly 白名单写入未被阻止: {result.output}")
            all_passed = False

        # 测试 4: writable 内的文件可读写
        print("\n4. writable 白名单内的文件应该可读写")
        result = executor.execute(f'python -c "content = open(\'{writable_dir}/in_writable.txt\', \'r\').read(); print(content)"')
        if 'in writable' in result.output:
            print("   ✅ writable 白名单内可读")
        else:
            print(f"   ❌ writable 白名单内读取失败: {result.output}")
            all_passed = False

        result = executor.execute(f'python -c "open(\'{writable_dir}/in_writable.txt\', \'w\').write(\'written\')"')
        if (writable_dir / 'in_writable.txt').read_text() == 'written':
            print("   ✅ writable 白名单内可写")
        else:
            print(f"   ❌ writable 白名单内写入失败")
            all_passed = False

        # 测试 5: 其他绝对路径重定向到 root_dir
        print("\n5. 其他绝对路径应该重定向到 root_dir")
        result = executor.execute('python -c "open(\'/redirected.txt\', \'w\').write(\'redirected\')"')
        redirected_file = root_dir / 'redirected.txt'
        if redirected_file.exists() and redirected_file.read_text() == 'redirected':
            print("   ✅ 其他绝对路径正确重定向到 root_dir")
        else:
            print(f"   ❌ 其他绝对路径未正确重定向: {redirected_file}")
            all_passed = False

        return all_passed


def main():
    """运行测试"""
    print("=" * 80)
    print("路径检查优先级顺序测试")
    print("=" * 80)

    try:
        result = test_priority_order()
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        result = False

    print("\n" + "=" * 80)
    if result:
        print("✅ 优先级顺序验证通过！")
    else:
        print("❌ 优先级顺序验证失败")
    print("=" * 80)

    return result


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
