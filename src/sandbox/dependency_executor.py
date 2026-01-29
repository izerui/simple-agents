# -*- coding: utf-8 -*-
import re
import subprocess
import threading
from pathlib import Path
from typing import Optional, Union

from deepagents.backends.protocol import ExecuteResponse


class DependencyExecutor:
    """
    依赖安装执行器

    专门用于执行安全的依赖安装和查询命令，支持：
    - uv pip install <package>（只安装新包）
    - uv pip list
    - uv pip show <package>

    特性：
    - 超时控制
    - 输出捕获
    - 安全的命令验证
    """

    def __init__(
            self,
            root_dir: Optional[Union[str, Path]] = None,
            max_output_length: int = 100000,  # 100KB
            timeout: int = 300,  # 5分钟
            **kwargs
    ) -> None:
        """初始化依赖安装执行器

        Args:
            root_dir: 工作目录（用于相对路径）
            max_output_length: 最大输出长度
            timeout: 命令执行超时时间（秒）
        """
        # 设置根目录
        self.root_dir = Path(root_dir) if root_dir else Path.cwd()
        self.root_dir = self.root_dir.resolve()

        self.max_output_length = max_output_length
        self.timeout = timeout

    def _parse_command(self, command: str) -> tuple[bool, Optional[str]]:
        """解析并验证依赖安装命令

        支持的格式：
        1. uv pip install <package>（只能安装新包，不能升级或重装）
        2. uv pip list
        3. uv pip show <package>
        4. uv pip freeze
        5. uv pip check

        安全限制（禁止破坏环境的操作）：
        - 不支持：uv pip install -r requirements.txt（批量安装）
        - 不支持：uv pip uninstall <package>（卸载操作）
        - 不支持：--upgrade, -U（升级已安装的包）
        - 不支持：--force-reinstall, --reinstall（强制重新安装）
        - 不支持：--upgrade-strategy（升级策略）
        - 不支持：--ignore-installed（忽略已安装版本）

        Args:
            command: 命令字符串

        Returns:
            (is_valid, error_message) 元组
            - 如果有效：is_valid=True, error_message=None
            - 如果无效：is_valid=False, error_message=错误描述
        """
        command = command.strip()
        
        # 必须以 uv pip 开头
        if not re.match(r'^uv\s+pip\s+', command, re.IGNORECASE):
            return False, (
                f"不支持的命令格式: '{command}'\n"
                f"命令必须以 'uv pip' 开头"
            )
        
        # 提取子命令部分
        rest = re.sub(r'^uv\s+pip\s+', '', command, flags=re.IGNORECASE)
        parts = rest.split()
        
        if not parts:
            return False, (
                f"不完整的命令: '{command}'\n"
                f"请指定子命令"
            )
        
        subcommand = parts[0].lower()
        
        # 验证子命令
        allowed_subcommands = ['install', 'list', 'show', 'freeze', 'check']
        if subcommand not in allowed_subcommands:
            return False, (
                f"不支持的子命令: '{subcommand}'\n"
                "只支持以下子命令: {}".format(', '.join(allowed_subcommands))
            )
        
        # 对于 install 命令，检查是否使用了破坏性选项
        if subcommand == 'install':
            # 将命令分割成部分来精确匹配选项
            cmd_parts = command.split()
            dangerous_options = {
                '-r': '批量安装',
                '--requirement': '批量安装',
                '--upgrade': '升级已安装的包',
                '-u': '升级已安装的包',
                '--force-reinstall': '强制重新安装',
                '--reinstall': '强制重新安装',
                '--upgrade-strategy': '升级策略',
                '--ignore-installed': '忽略已安装版本',
            }
            
            for part in cmd_parts:
                part_lower = part.lower()
                # 检查是否有危险的选项（精确匹配）
                if part_lower in dangerous_options:
                    return False, (
                        f"不允许破坏环境的操作: '{command}'\n"
                        f"选项 '{part}' 可能导致环境变更（{dangerous_options[part_lower]}）\n"
                        f"为了环境安全，此操作被禁止"
                    )
                # 检查 --upgrade-strategy 的变体
                if part_lower.startswith('--upgrade-strategy'):
                    return False, (
                        f"不允许破坏环境的操作: '{command}'\n"
                        f"选项 '{part}' 可能导致环境变更（升级策略）\n"
                        f"为了环境安全，此操作被禁止"
                    )
        
        # 确保没有 uninstall
        if 'uninstall' in command.lower():
            return False, (
                f"不允许卸载操作: '{command}'\n"
                f"只支持安装和查询操作"
            )
        
        return True, None

    def _truncate_output(self, output: str) -> str:
        """截断输出到最大长度

        Args:
            output: 原始输出

        Returns:
            截断后的输出
        """
        if len(output) <= self.max_output_length:
            return output

        truncated = output[:self.max_output_length]
        truncated += f"\n\n... (输出已截断，超过 {self.max_output_length} 字符限制)"
        return truncated

    def execute(self, command: str) -> ExecuteResponse:
        """执行依赖安装命令

        Args:
            command: 依赖安装命令字符串

        Returns:
            ExecuteResponse 包含输出、退出码和截断标志
        """
        # 验证命令
        is_valid, error_msg = self._parse_command(command)
        if not is_valid:
            return ExecuteResponse(
                output=error_msg,
                exit_code=1,
            )

        try:
            # 准备命令参数
            cmd_parts = command.split()

            # 处理命令参数
            processed_parts = cmd_parts

            # 执行命令
            result = subprocess.run(
                processed_parts,
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=False,
            )

            # 合并 stdout 和 stderr
            output = result.stdout
            if result.stderr:
                if output:
                    output += "\n" + result.stderr
                else:
                    output = result.stderr

            # 截断输出
            truncated_output = self._truncate_output(output)

            # 检查是否被截断
            is_truncated = len(output) > self.max_output_length

            return ExecuteResponse(
                output=truncated_output,
                exit_code=result.returncode,
            )

        except subprocess.TimeoutExpired:
            return ExecuteResponse(
                output=f"命令执行超时（超过 {self.timeout} 秒）：{command}",
                exit_code=124,  # 类似于 timeout 命令的退出码
            )
        except FileNotFoundError as e:
            return ExecuteResponse(
                output=f"命令未找到，请确保 uv 已安装：{e}",
                exit_code=127,
            )
        except Exception as e:
            return ExecuteResponse(
                output=f"执行命令时出错：{type(e).__name__}: {e}",
                exit_code=1,
            )