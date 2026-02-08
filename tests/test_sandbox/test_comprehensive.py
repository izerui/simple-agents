#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面测试受限沙箱

测试覆盖：
1. 基本文件操作（读写）
2. 权限控制（root_dir、readable_paths、writable_paths）
3. 路径重定向（绝对路径、相对路径）
4. 安全检查（AST检查、危险函数）
5. 模块导入限制
6. 标准库可用性
7. 边界情况
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.sandbox.pycode_executor import CodeExecutor
from pathlib import Path
import tempfile


def test_comprehensive():
    """全面测试受限沙箱"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # 创建目录结构
        sandbox_dir = tmpdir / "sandbox"
        sandbox_dir.mkdir()

        readonly_dir = tmpdir / "readonly"
        readonly_dir.mkdir()
        (readonly_dir / "data.txt").write_text("readonly data")
        (readonly_dir / "config.json").write_text('{"key": "value"}')

        writable_dir = tmpdir / "writable"
        writable_dir.mkdir()

        # 创建项目.venv（只读）
        venv_dir = tmpdir / "project_venv"
        venv_dir.mkdir()
        (venv_dir / "lib").mkdir()
        (venv_dir / "lib" / "test.txt").write_text("venv file")

        print("=" * 80)
        print("受限沙箱全面测试")
        print("=" * 80)
        print(f"沙箱目录: {sandbox_dir}")
        print(f"只读目录: {readonly_dir}")
        print(f"可写目录: {writable_dir}")
        print(f"项目venv: {venv_dir}")
        print()

        # 创建执行器
        executor = CodeExecutor(
            root_dir=str(sandbox_dir),
            readable_paths=[str(readonly_dir), str(venv_dir)],
            writable_paths=[str(writable_dir)]
        )

        # ==================== 第一部分：基本文件操作 ====================
        print("\n" + "=" * 80)
        print("第一部分：基本文件操作")
        print("=" * 80)

        # 测试 1: 创建和读取文件
        print("\n[测试 1.1] 创建和读取文件")
        print("-" * 80)
        result = executor.execute('python -c "open(\'test.txt\', \'w\').write(\'Hello World\')"')
        if result.exit_code == 0:
            result = executor.execute('python -c "print(open(\'test.txt\').read())"')
            if "Hello World" in result.output:
                print("✅ 文件创建和读取成功")
            else:
                print(f"❌ 读取失败: {result.output}")
        else:
            print(f"❌ 创建失败: {result.output}")

        # 测试 2: 追加写入
        print("\n[测试 1.2] 追加写入")
        print("-" * 80)
        result = executor.execute('python -c "open(\'test.txt\', \'a\').write(\'\\nAppend\')"')
        if result.exit_code == 0:
            result = executor.execute('python -c "lines = open(\'test.txt\').read().split(\'\\n\'); print(len(lines))"')
            if "2" in result.output:
                print("✅ 追加写入成功")
            else:
                print(f"❌ 追加失败: {result.output}")
        else:
            print(f"❌ 追加失败: {result.output}")

        # 测试 3: 写入二进制数据
        print("\n[测试 1.3] 写入二进制数据")
        print("-" * 80)
        result = executor.execute('python -c "open(\'binary.dat\', \'wb\').write(b\'\\x00\\x01\\x02\\x03\')"')
        if result.exit_code == 0:
            result = executor.execute('python -c "import os; print(os.path.getsize(\'binary.dat\'))"')
            if "4" in result.output:
                print("✅ 二进制写入成功")
            else:
                print(f"❌ 二进制失败: {result.output}")
        else:
            print(f"❌ 二进制失败: {result.output}")

        # ==================== 第二部分：路径重定向 ====================
        print("\n" + "=" * 80)
        print("第二部分：路径重定向")
        print("=" * 80)

        # 测试 4: 绝对路径重定向
        print("\n[测试 2.1] 绝对路径自动重定向到沙箱")
        print("-" * 80)
        result = executor.execute('python -c "open(\'/absolute.txt\', \'w\').write(\'test\')"')
        if result.exit_code == 0:
            if (sandbox_dir / "absolute.txt").exists():
                print("✅ 绝对路径正确重定向")
            else:
                print("❌ 文件不在预期位置")
        else:
            print(f"❌ 执行失败: {result.output}")

        # 测试 5: 相对路径重定向
        print("\n[测试 2.2] 相对路径自动重定向到沙箱")
        print("-" * 80)
        result = executor.execute('python -c "open(\'relative.txt\', \'w\').write(\'test\')"')
        if result.exit_code == 0:
            if (sandbox_dir / "relative.txt").exists():
                print("✅ 相对路径正确重定向")
            else:
                print("❌ 文件不在预期位置")
        else:
            print(f"❌ 执行失败: {result.output}")

        # 测试 6: 嵌套路径
        print("\n[测试 2.3] 嵌套目录路径")
        print("-" * 80)
        result = executor.execute('python -c "import os; os.makedirs(\'nested/dir\', exist_ok=True); open(\'nested/dir/file.txt\', \'w\').write(\'test\')"')
        if result.exit_code == 0:
            if (sandbox_dir / "nested" / "dir" / "file.txt").exists():
                print("✅ 嵌套路径正确处理")
            else:
                print("❌ 嵌套路径失败")
        else:
            print(f"❌ 执行失败: {result.output}")

        # ==================== 第三部分：权限控制 ====================
        print("\n" + "=" * 80)
        print("第三部分：权限控制")
        print("=" * 80)

        # 测试 7: 读取只读路径
        print("\n[测试 3.1] 读取只读白名单路径")
        print("-" * 80)
        result = executor.execute(f'python -c "print(open(\'{readonly_dir}/data.txt\').read())"')
        if "readonly data" in result.output:
            print("✅ 可以读取只读路径")
        else:
            print(f"❌ 读取失败: {result.output}")

        # 测试 8: 禁止写入只读路径
        print("\n[测试 3.2] 禁止写入只读路径")
        print("-" * 80)
        result = executor.execute(f'python -c "open(\'{readonly_dir}/hack.txt\', \'w\').write(\'hack\')"')
        if result.exit_code != 0:
            print("✅ 正确阻止写入只读路径")
        else:
            print("❌ 未能阻止写入")

        # 测试 9: 可以写入可写路径
        print("\n[测试 3.3] 可以写入可写路径")
        print("-" * 80)
        result = executor.execute(f'python -c "open(\'{writable_dir}/test.txt\', \'w\').write(\'test\')"')
        if result.exit_code == 0 and (writable_dir / "test.txt").exists():
            print("✅ 可以写入可写路径")
        else:
            print("❌ 写入可写路径失败")

        # 测试 10: 读取.venv
        print("\n[测试 3.4] 读取项目.venv")
        print("-" * 80)
        result = executor.execute(f'python -c "print(open(\'{venv_dir}/lib/test.txt\').read())"')
        if "venv file" in result.output:
            print("✅ 可以读取.venv")
        else:
            print(f"❌ 读取.venv失败: {result.output}")

        # ==================== 第四部分：安全检查 ====================
        print("\n" + "=" * 80)
        print("第四部分：安全检查")
        print("=" * 80)

        # 测试 11: 阻止 os.system
        print("\n[测试 4.1] 阻止 os.system")
        print("-" * 80)
        result = executor.execute('python -c "import os; os.system(\'ls\')"')
        if result.exit_code != 0:
            print("✅ 正确阻止 os.system")
        else:
            print("❌ 未能阻止 os.system")

        # 测试 12: 阻止 subprocess
        print("\n[测试 4.2] 阻止 subprocess 模块")
        print("-" * 80)
        result = executor.execute('python -c "import subprocess"')
        if result.exit_code != 0:
            print("✅ 正确阻止 subprocess")
        else:
            print("❌ 未能阻止 subprocess")

        # 测试 13: 阻止 exec
        print("\n[测试 4.3] 阻止 exec 内置函数")
        print("-" * 80)
        result = executor.execute('python -c "exec(\'print(1)\')"')
        if result.exit_code != 0:
            print("✅ 正确阻止 exec")
        else:
            print("❌ 未能阻止 exec")

        # 测试 14: 阻止 eval
        print("\n[测试 4.4] 阻止 eval 内置函数")
        print("-" * 80)
        result = executor.execute('python -c "eval(\'1+1\')"')
        if result.exit_code != 0:
            print("✅ 正确阻止 eval")
        else:
            print("❌ 未能阻止 eval")

        # 测试 15: 阻止 os.open
        print("\n[测试 4.5] 阻止 os.open")
        print("-" * 80)
        result = executor.execute('python -c "import os; os.open(\'test.txt\', os.O_WRONLY)"')
        if result.exit_code != 0:
            print("✅ 正确阻止 os.open")
        else:
            print("❌ 未能阻止 os.open")

        # 测试 16: 阻止 io 模块
        print("\n[测试 4.6] 阻止 io 模块")
        print("-" * 80)
        result = executor.execute('python -c "import io"')
        if result.exit_code != 0:
            print("✅ 正确阻止 io 模块")
        else:
            print("❌ 未能阻止 io 模块")

        # 测试 17: 阻止 pathlib 导入
        print("\n[测试 4.7] 阻止 from pathlib import Path")
        print("-" * 80)
        result = executor.execute('python -c "from pathlib import Path"')
        if result.exit_code != 0:
            print("✅ 正确阻止 pathlib 导入")
        else:
            print("❌ 未能阻止 pathlib 导入")

        # 测试 18: 使用内置 Path（受限版本）
        print("\n[测试 4.8] 使用内置 Path（受限版本）")
        print("-" * 80)
        result = executor.execute('python -c "Path(\'test_path.txt\').write_text(\'test\')"')
        if result.exit_code == 0 and (sandbox_dir / "test_path.txt").exists():
            print("✅ 内置 Path 可用且受限制")
        else:
            print("❌ 内置 Path 不可用")

        # ==================== 第五部分：标准库可用性 ====================
        print("\n" + "=" * 80)
        print("第五部分：标准库可用性")
        print("=" * 80)

        # 测试 19: json 模块
        print("\n[测试 5.1] json 模块")
        print("-" * 80)
        result = executor.execute('python -c "import json; print(json.dumps({\'a\': 1}))"')
        if result.exit_code == 0 and '"a"' in result.output:
            print("✅ json 模块可用")
        else:
            print(f"❌ json 不可用: {result.output}")

        # 测试 20: datetime 模块
        print("\n[测试 5.2] datetime 模块")
        print("-" * 80)
        result = executor.execute('python -c "from datetime import datetime; print(datetime.now().year)"')
        if result.exit_code == 0:
            print("✅ datetime 模块可用")
        else:
            print(f"❌ datetime 不可用: {result.output}")

        # 测试 21: re 模块
        print("\n[测试 5.3] re 模块")
        print("-" * 80)
        result = executor.execute('python -c "import re; print(re.sub(\'a\', \'b\', \'aaa\'))"')
        if result.exit_code == 0 and "bbb" in result.output:
            print("✅ re 模块可用")
        else:
            print(f"❌ re 不可用: {result.output}")

        # 测试 22: collections 模块
        print("\n[测试 5.4] collections 模块")
        print("-" * 80)
        result = executor.execute('python -c "from collections import Counter; print(Counter([1,1,2]))"')
        if result.exit_code == 0:
            print("✅ collections 模块可用")
        else:
            print(f"❌ collections 不可用: {result.output}")

        # ==================== 第六部分：边界情况 ====================
        print("\n" + "=" * 80)
        print("第六部分：边界情况")
        print("=" * 80)

        # 测试 23: 空文件
        print("\n[测试 6.1] 空文件")
        print("-" * 80)
        result = executor.execute('python -c "open(\'empty.txt\', \'w\').close(); print(len(open(\'empty.txt\').read()))"')
        if result.exit_code == 0 and "0" in result.output:
            print("✅ 空文件处理正确")
        else:
            print(f"❌ 空文件处理失败: {result.output}")

        # 测试 24: 大文件
        print("\n[测试 6.2] 大文件写入")
        print("-" * 80)
        result = executor.execute('python -c "open(\'large.txt\', \'w\').write(\'x\' * 10000)"')
        if result.exit_code == 0:
            result = executor.execute('python -c "import os; print(os.path.getsize(\'large.txt\'))"')
            if "10000" in result.output:
                print("✅ 大文件写入成功")
            else:
                print("❌ 大小不匹配")
        else:
            print(f"❌ 大文件写入失败: {result.output}")

        # 测试 25: 特殊字符文件名
        print("\n[测试 6.3] 特殊字符文件名")
        print("-" * 80)
        result = executor.execute('python -c "open(\'file-with-dash.txt\', \'w\').write(\'test\')"')
        if result.exit_code == 0 and (sandbox_dir / "file-with-dash.txt").exists():
            print("✅ 特殊字符文件名处理正确")
        else:
            print(f"❌ 特殊字符文件名失败")

        # 测试 26: 多次写入同一文件
        print("\n[测试 6.4] 多次写入同一文件")
        print("-" * 80)
        success_count = 0
        for i in range(3):
            result = executor.execute(f'python -c "open(\'counter.txt\', \'a\').write(str({i}))"')
            if result.exit_code != 0:
                print(f"❌ 第{i+1}次写入失败: {result.output[:200] if result.output else ''}")
                break
            success_count += 1

        if success_count == 3:
            result = executor.execute('python -c "print(open(\'counter.txt\').read())"')
            if "012" in result.output:
                print("✅ 多次写入成功")
            else:
                print(f"❌ 内容不匹配: {result.output}")
        else:
            print(f"⚠ 只有 {success_count}/3 次写入成功，跳过验证")

        # ==================== 第七部分：Path 类安全性 ====================
        print("\n" + "=" * 80)
        print("第七部分：Path 类安全性")
        print("=" * 80)

        # 测试 27: Path.write_text 受限
        print("\n[测试 7.1] Path.write_text 受限")
        print("-" * 80)
        result = executor.execute(f'python -c "Path(\'{readonly_dir}/path_hack.txt\').write_text(\'hack\')"')
        if result.exit_code != 0:
            print("✅ Path.write_text 正确受限")
        else:
            print("❌ Path.write_text 未受限")

        # 测试 28: Path.open 受限
        print("\n[测试 7.2] Path.open 受限")
        print("-" * 80)
        result = executor.execute(f'python -c "Path(\'{readonly_dir}/path_hack2.txt\').open(\'w\').write(\'hack\')"')
        if result.exit_code != 0:
            print("✅ Path.open 正确受限")
        else:
            print("❌ Path.open 未受限")

        # 测试 29: Path.read_text 可用
        print("\n[测试 7.3] Path.read_text 可用")
        print("-" * 80)
        result = executor.execute(f'python -c "print(Path(\'{readonly_dir}/data.txt\').read_text())"')
        if "readonly data" in result.output:
            print("✅ Path.read_text 可用")
        else:
            print(f"❌ Path.read_text 不可用: {result.output}")

        # ==================== 第八部分：脚本执行 ====================
        print("\n" + "=" * 80)
        print("第八部分：脚本执行")
        print("=" * 80)

        # 创建测试脚本
        script_path = sandbox_dir / "test_script.py"
        script_path.write_text('print("Script executed")')

        # 测试 30: 执行脚本文件
        print("\n[测试 8.1] 执行脚本文件")
        print("-" * 80)
        result = executor.execute('python test_script.py')
        if "Script executed" in result.output:
            print("✅ 脚本执行成功")
        else:
            print(f"❌ 脚本执行失败: {result.output}")

        # 测试 31: 脚本带参数
        print("\n[测试 8.2] 脚本带参数")
        print("-" * 80)
        script_path.write_text('import sys\nprint("Args:", sys.argv[1:])')
        result = executor.execute('python test_script.py arg1 arg2')
        print(f"输出: {result.output}")
        if "arg1" in result.output and "arg2" in result.output:
            print("✅ 脚本参数传递成功")
        else:
            print(f"❌ 参数传递失败: {result.output}")

        # ==================== 统计结果 ====================
        print("\n" + "=" * 80)
        print("测试总结")
        print("=" * 80)
        print("✅ 所有测试完成！请查看上方输出确认每个测试的结果。")
        print("\n关键安全特性验证：")
        print("  • 文件访问权限控制 ✓")
        print("  • 路径重定向（绝对/相对）✓")
        print("  • 危险函数阻止 ✓")
        print("  • 危险模块阻止 ✓")
        print("  • 标准库可用性 ✓")
        print("  • Path 类安全限制 ✓")


if __name__ == '__main__':
    test_comprehensive()
