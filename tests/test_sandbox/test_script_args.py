#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调试脚本参数传递"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.sandbox.pycode_executor import CodeExecutor
from pathlib import Path
import tempfile

with tempfile.TemporaryDirectory() as tmpdir:
    sandbox_dir = Path(tmpdir) / 'sandbox'
    sandbox_dir.mkdir()

    executor = CodeExecutor(root_dir=str(sandbox_dir))

    # 创建测试脚本
    script_path = sandbox_dir / 'test.py'
    script_path.write_text('import sys\nprint("All args:", sys.argv)\nprint("Args[1:]:", sys.argv[1:])')

    # 测试参数传递
    print("=" * 60)
    print("测试脚本参数传递")
    print("=" * 60)
    print(f"脚本内容: {script_path.read_text()}")
    print()

    # 执行脚本
    result = executor.execute('python test.py arg1 arg2 arg3')

    print(f"退出码: {result.exit_code}")
    print(f"完整输出:\n{result.output}")
    print()

    if 'arg1' in result.output and 'arg2' in result.output and 'arg3' in result.output:
        print("✅ 所有参数都正确传递")
    elif 'arg2' in result.output and 'arg3' in result.output and 'arg1' not in result.output:
        print("❌ 缺少 arg1 - 这是问题所在")
    else:
        print("❌ 参数传递有问题")
