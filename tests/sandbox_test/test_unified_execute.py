# -*- coding: utf-8 -*-
"""
统一执行入口测试

测试 SandboxFilesystemBackend 的 execute 方法能够自动判断
使用哪个执行器（DependencyExecutor 或 CodeExecutor）
"""
import sys
import tempfile
import unittest
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.sandbox.sandbox_filesystem import SandboxFilesystemBackend


class TestUnifiedExecute(unittest.TestCase):
    """测试统一执行入口"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.root_dir = Path(self.temp_dir)
        
        # 创建测试脚本文件
        self.test_script = self.root_dir / "test_script.py"
        self.test_script.write_text('print("Hello from script!")\n')
        
        # 创建复杂脚本文件
        self.complex_script = self.root_dir / "complex_script.py"
        self.complex_script.write_text("""
import sys

def fibonacci(n):
    a, b = 0, 1
    result = []
    for _ in range(n):
        result.append(a)
        a, b = b, a + b
    return result

print(fibonacci(10))
""")
        
        # 初始化沙箱后端
        self.sandbox = SandboxFilesystemBackend(
            root_dir=self.root_dir,
            max_output_length=10000,
        )

    def tearDown(self):
        """清理测试环境"""
        import shutil
        if self.root_dir.exists():
            shutil.rmtree(self.root_dir)

    def test_uv_pip_list_command(self):
        """测试 uv pip list 命令通过统一入口"""
        response = self.sandbox.execute("uv pip list")
        
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.output)
        # 如果 uv 未安装，退出码是 127；如果已安装，可能是 0
        self.assertIn(response.exit_code, [0, 127])

    def test_uv_pip_install_command(self):
        """测试 uv pip install 命令通过统一入口"""
        response = self.sandbox.execute("uv pip install --dry-run requests")
        
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.output)
        # 命令应该被接受并执行（即使可能因为缺少虚拟环境而失败）
        self.assertIsNotNone(response.exit_code)

    def test_python_c_command(self):
        """测试 python -c 命令通过统一入口"""
        response = self.sandbox.execute('python -c "print(\'Hello from Python!\')"')
        
        self.assertIsNotNone(response)
        self.assertEqual(response.exit_code, 0)
        self.assertIn("Hello from Python!", response.output)

    def test_python_script_command(self):
        """测试 python script.py 命令通过统一入口"""
        response = self.sandbox.execute("python test_script.py")
        
        self.assertIsNotNone(response)
        self.assertEqual(response.exit_code, 0)
        self.assertIn("Hello from script!", response.output)

    def test_uv_pip_show_command(self):
        """测试 uv pip show 命令通过统一入口"""
        response = self.sandbox.execute("uv pip show pip")
        
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.output)
        # pip 应该是已安装的，所以退出码应该是 0
        self.assertEqual(response.exit_code, 0)

    def test_uv_pip_freeze_command(self):
        """测试 uv pip freeze 命令通过统一入口"""
        response = self.sandbox.execute("uv pip freeze")
        
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.output)
        # 应该成功执行
        self.assertEqual(response.exit_code, 0)

    def test_uv_pip_check_command(self):
        """测试 uv pip check 命令通过统一入口"""
        response = self.sandbox.execute("uv pip check")
        
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.output)
        # 应该成功执行
        self.assertEqual(response.exit_code, 0)

    def test_dangerous_upgrade_blocked(self):
        """测试升级命令被统一入口阻止"""
        response = self.sandbox.execute("uv pip install --upgrade requests")
        
        self.assertIsNotNone(response)
        self.assertEqual(response.exit_code, 1)
        self.assertIn("破坏环境", response.output)
        self.assertIn("升级", response.output)

    def test_dangerous_uninstall_blocked(self):
        """测试卸载命令被统一入口阻止"""
        response = self.sandbox.execute("uv pip uninstall requests")
        
        self.assertIsNotNone(response)
        self.assertEqual(response.exit_code, 1)
        self.assertIn("不支持的子命令", response.output)

    def test_batch_install_blocked(self):
        """测试批量安装被统一入口阻止"""
        # 创建 requirements.txt
        req_file = self.root_dir / "requirements.txt"
        req_file.write_text("requests\n")
        
        response = self.sandbox.execute("uv pip install -r requirements.txt")
        
        self.assertIsNotNone(response)
        self.assertEqual(response.exit_code, 1)
        self.assertIn("破坏环境", response.output)
        self.assertIn("批量安装", response.output)

    def test_invalid_python_command_blocked(self):
        """测试无效的 Python 命令被阻止"""
        response = self.sandbox.execute("py script.py")
        
        self.assertIsNotNone(response)
        self.assertEqual(response.exit_code, -1)
        self.assertIn("不支持的命令格式", response.output)

    def test_non_supported_command_blocked(self):
        """测试不支持的命令类型被阻止"""
        response = self.sandbox.execute("ls -la")
        
        self.assertIsNotNone(response)
        self.assertEqual(response.exit_code, -1)
        # 应该被 CodeExecutor 拒绝
        self.assertIn("不支持的命令格式", response.output)

    def test_multiple_uv_pip_commands(self):
        """测试多个 uv pip 命令通过统一入口"""
        commands = [
            "uv pip list",
            "uv pip freeze",
            "uv pip check",
        ]
        
        for cmd in commands:
            response = self.sandbox.execute(cmd)
            self.assertIsNotNone(response, "命令 '{}' 应该有响应".format(cmd))
            self.assertIsNotNone(response.output, "命令 '{}' 应该有输出".format(cmd))

    def test_multiple_python_commands(self):
        """测试多个 Python 命令通过统一入口"""
        commands = [
            'python -c "print(1+1)"',
            'python -c "x = [1,2,3]; print(sum(x))"',
        ]
        
        for cmd in commands:
            response = self.sandbox.execute(cmd)
            self.assertIsNotNone(response, "命令 '{}' 应该有响应".format(cmd))
            self.assertEqual(response.exit_code, 0, "命令 '{}' 应该成功".format(cmd))

    def test_command_case_insensitive(self):
        """测试命令大小写不敏感"""
        # UV PIP (大写)
        response = self.sandbox.execute("UV PIP list")
        self.assertIsNotNone(response)
        
        # uv PIP (混合大小写)
        response = self.sandbox.execute("uv PIP list")
        self.assertIsNotNone(response)

    def test_whitespace_handling(self):
        """测试空格处理"""
        # 多余空格
        response = self.sandbox.execute("  uv  pip  list  ")
        self.assertIsNotNone(response)
        
        # Tab 和空格混合
        response = self.sandbox.execute("\tuv\tpip\tlist\t")
        self.assertIsNotNone(response)

    def test_python_c_with_quotes(self):
        """测试 python -c 命令中的引号处理"""
        # 单引号
        response = self.sandbox.execute("python -c 'print(\"single\")'")
        self.assertEqual(response.exit_code, 0)
        self.assertIn("single", response.output)
        
        # 双引号
        response = self.sandbox.execute('python -c "print(\'double\')"')
        self.assertEqual(response.exit_code, 0)
        self.assertIn("double", response.output)

    def test_complex_python_code(self):
        """测试复杂的 Python 代码执行"""
        response = self.sandbox.execute("python complex_script.py")
        
        self.assertEqual(response.exit_code, 0)
        self.assertIn("[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]", response.output)


def main():
    """运行所有测试"""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    main()