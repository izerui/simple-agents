#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')
from sandbox.pycode_executor import CodeExecutor
from pathlib import Path
import tempfile

with tempfile.TemporaryDirectory() as tmpdir:
    executor = CodeExecutor(root_dir=tmpdir)

    # 测试 tarfile.open 是否被重定向
    print('测试: tarfile.open() 路径重定向')

    # 使用单行代码避免语法问题
    result = executor.execute('python -c "import tarfile; import os; os.makedirs(\'/tmp/test_tar\', exist_ok=True); open(\'/tmp/test_tar/test.txt\', \'w\').write(\'hello\'); tarfile.open(\'/tmp/test.tar.gz\', \'w:gz\').add(\'/tmp/test_tar/test.txt\'); print(\'Success\')"')

    print(f'退出码: {result.exit_code}')
    print(f'输出: {result.output[:300]}')

    # 检查 tar 文件是否在 root_dir 内
    tar_file = Path(tmpdir) / 'tmp' / 'test.tar.gz'
    print(f'\n检查文件: {tar_file}')
    print(f'文件存在: {tar_file.exists()}')
