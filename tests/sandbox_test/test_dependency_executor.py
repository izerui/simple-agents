# -*- coding: utf-8 -*-
"""
依赖安装执行器测试

测试 DependencyExecutor 的功能，包括：
1. 支持的命令格式验证
2. 不支持的命令格式拒绝
3. 相对路径文件处理
4. 输出截断
5. 错误处理
"""
import tempfile
import unittest
from pathlib import Path

import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.sandbox.dependency_executor import DependencyExecutor


class TestDependencyExecutor(unittest.TestCase):
    """测试 DependencyExecutor 类"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.root_dir = Path(self.temp_dir)
        
        # 创建测试用的 requirements.txt
        # 初始化执行器
        self.executor = DependencyExecutor(
            root_dir=self.root_dir,
            max_output_length=1000,
            timeout=30,
        )

    def tearDown(self):
        """清理测试环境"""
        import shutil
        if self.root_dir.exists():
            shutil.rmtree(self.root_dir)

    def test_parse_command_valid_install(self):
        """测试有效的安装命令解析"""
        valid_commands = [
            "uv pip install requests",
            "uv pip install numpy pandas",
            "uv pip list",
            "uv pip show requests",
            "uv pip freeze",
            "uv pip check",
            "uv pip install --index-url https://pypi.org/simple/ requests",
            "uv pip install --verbose requests",
            "uv pip install --quiet requests",
            "uv pip install --dry-run requests",
        ]
        
        for cmd in valid_commands:
            is_valid, error_msg = self.executor._parse_command(cmd)
            self.assertTrue(is_valid, "命令 '{}' 应该有效，但返回错误: {}".format(cmd, error_msg))
            self.assertIsNone(error_msg)

    def test_parse_command_invalid_commands(self):
        """测试无效的命令格式"""
        invalid_commands = [
            "python -c 'print(1)'",  # Python 代码执行
            "ls -la",  # Shell 命令
            "pip install requests",  # 没有 uv 前缀
            "uv pip",  # 不完整的命令
            "npm install",  # 包管理器不匹配
            "",  # 空命令
        ]
        
        for cmd in invalid_commands:
            is_valid, error_msg = self.executor._parse_command(cmd)
            self.assertFalse(is_valid, "命令 '{}' 应该无效".format(cmd))
            self.assertIsNotNone(error_msg)

    def test_dangerous_upgrade_commands(self):
        """测试升级命令被拒绝"""
        dangerous_commands = [
            "uv pip install --upgrade requests",
            "uv pip install -U requests",
            "uv pip install requests --upgrade",
            "uv pip install --upgrade numpy pandas",
        ]
        
        for cmd in dangerous_commands:
            is_valid, error_msg = self.executor._parse_command(cmd)
            self.assertFalse(is_valid, "命令 '{}' 应该被拒绝（升级操作）".format(cmd))
            self.assertIn("破坏环境", error_msg)
            self.assertIn("升级", error_msg)

    def test_dangerous_reinstall_commands(self):
        """测试重装命令被拒绝"""
        dangerous_commands = [
            "uv pip install --force-reinstall requests",
            "uv pip install --reinstall requests",
            "uv pip install requests --force-reinstall",
        ]
        
        for cmd in dangerous_commands:
            is_valid, error_msg = self.executor._parse_command(cmd)
            self.assertFalse(is_valid, "命令 '{}' 应该被拒绝（重装操作）".format(cmd))
            self.assertIn("破坏环境", error_msg)
            self.assertIn("重新安装", error_msg)

    def test_dangerous_upgrade_strategy_commands(self):
        """测试升级策略命令被拒绝"""
        dangerous_commands = [
            "uv pip install --upgrade-strategy eager requests",
            "uv pip install --upgrade-strategy only-if-needed requests",
            "uv pip install requests --upgrade-strategy eager",
        ]
        
        for cmd in dangerous_commands:
            is_valid, error_msg = self.executor._parse_command(cmd)
            self.assertFalse(is_valid, "命令 '{}' 应该被拒绝（升级策略）".format(cmd))
            self.assertIn("破坏环境", error_msg)

    def test_dangerous_ignore_installed_commands(self):
        """测试忽略已安装版本命令被拒绝"""
        dangerous_commands = [
            "uv pip install --ignore-installed requests",
            "uv pip install requests --ignore-installed",
        ]
        
        for cmd in dangerous_commands:
            is_valid, error_msg = self.executor._parse_command(cmd)
            self.assertFalse(is_valid, "命令 '{}' 应该被拒绝（忽略已安装）".format(cmd))
            self.assertIn("破坏环境", error_msg)
            self.assertIn("忽略已安装", error_msg)

    def test_truncate_output(self):
        """测试输出截断功能"""
        # 创建一个超过限制的长输出
        long_output = "A" * 2000
        truncated = self.executor._truncate_output(long_output)
        
        self.assertEqual(len(truncated), 1000 + len("\n\n... (输出已截断，超过 1000 字符限制)"))
        self.assertTrue(truncated.endswith("... (输出已截断，超过 1000 字符限制)"))
        
        # 测试不需要截断的情况
        short_output = "B" * 500
        not_truncated = self.executor._truncate_output(short_output)
        self.assertEqual(not_truncated, short_output)

    def test_execute_invalid_command(self):
        """测试执行无效命令"""
        response = self.executor.execute("python -c 'print(1)'")
        
        self.assertEqual(response.exit_code, 1)
        self.assertIn("不支持的命令格式", response.output)

    def test_execute_list_command(self):
        """测试执行 list 命令（不需要实际安装包）"""
        # 注意：这个测试需要系统中安装了 uv
        # 如果没有安装 uv，会返回 FileNotFoundError
        response = self.executor.execute("uv pip list")
        
        # 检查响应结构
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.output)
        
        # 如果 uv 存在，退出码可能是 0；如果不存在，则是 127
        self.assertIn(response.exit_code, [0, 127])



    def test_max_output_length(self):
        """测试最大输出长度限制"""
        # 创建一个会产生大量输出的命令（假设有包列表）
        executor = DependencyExecutor(
            root_dir=self.root_dir,
            max_output_length=100,  # 很小的限制
        )
        
        response = executor.execute("uv pip list")
        
        # 输出应该被截断（如果有输出）
        if len(response.output) > 100:
            self.assertTrue("输出已截断" in response.output)

    def test_timeout_simulation(self):
        """测试超时处理"""
        # 创建一个很短的超时
        executor = DependencyExecutor(
            root_dir=self.root_dir,
            timeout=0.1,  # 0.1 秒超时
        )
        
        # 执行一个可能需要较长时间的命令
        response = executor.execute("uv pip list")
        
        # 如果命令执行时间超过超时，应该返回超时错误
        # 注意：这取决于系统中 uv 的响应速度
        # 如果响应很快，可能不会超时
        if response.exit_code == 124:
            self.assertIn("执行超时", response.output)

    def test_command_with_flags(self):
        """测试带有安全标志的命令"""
        commands_with_flags = [
            "uv pip install --verbose requests",
            "uv pip install --quiet requests",
            "uv pip install --dry-run requests",
            "uv pip install --no-deps requests",
            "uv pip install --no-cache-dir requests",
            "uv pip list --format=json",
            "uv pip list --not-required",
            "uv pip freeze --all",
            "uv pip show --files requests",
        ]
        
        for cmd in commands_with_flags:
            is_valid, _ = self.executor._parse_command(cmd)
            self.assertTrue(is_valid, "命令 '{}' 应该有效".format(cmd))

    def test_install_multiple_packages(self):
        """测试安装多个包"""
        command = "uv pip install requests numpy pandas"
        is_valid, _ = self.executor._parse_command(command)
        self.assertTrue(is_valid)



    def test_show_command(self):
        """测试 show 命令"""
        command = "uv pip show requests"
        is_valid, _ = self.executor._parse_command(command)
        self.assertTrue(is_valid)

    def test_freeze_command(self):
        """测试 freeze 命令"""
        command = "uv pip freeze"
        is_valid, _ = self.executor._parse_command(command)
        self.assertTrue(is_valid)

    def test_check_command(self):
        """测试 check 命令"""
        command = "uv pip check"
        is_valid, _ = self.executor._parse_command(command)
        self.assertTrue(is_valid)




def main():
    """运行所有测试"""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    main()