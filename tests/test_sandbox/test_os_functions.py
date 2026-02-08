#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 os 函数是否可用"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.sandbox.pycode_executor import CodeExecutor
from pathlib import Path
import tempfile

with tempfile.TemporaryDirectory() as tmpdir:
    sandbox_dir = Path(tmpdir) / 'sandbox'
    sandbox_dir.mkdir()

    executor = CodeExecutor(root_dir=str(sandbox_dir))

    # 测试 os.remove
    print("测试 os.remove:")
    result = executor.execute('python -c "import os; open(\'test.txt\', \'w\').write(\'test\'); os.remove(\'test.txt\'); print(\'removed\')"')
    print(f"  Exit code: {result.exit_code}")
    print(f"  Output: {result.output[:200]}")

    if 'removed' in result.output:
        print("  ✅ os.remove 可用")
    else:
        print("  ❌ os.remove 被阻止")

    # 测试 os.mkdir
    print("\n测试 os.mkdir:")
    result = executor.execute('python -c "import os; os.mkdir(\'testdir\'); print(\'created\')"')
    print(f"  Exit code: {result.exit_code}")
    print(f"  Output: {result.output[:200]}")

    if 'created' in result.output:
        print("  ✅ os.mkdir 可用")
    else:
        print("  ❌ os.mkdir 被阻止")

    # 测试 os.rmdir
    print("\n测试 os.rmdir:")
    result = executor.execute('python -c "import os; os.rmdir(\'testdir\'); print(\'removed\')"')
    print(f"  Exit code: {result.exit_code}")
    print(f"  Output: {result.output[:200]}")

    if 'removed' in result.output:
        print("  ✅ os.rmdir 可用")
    else:
        print("  ❌ os.rmdir 被阻止")

