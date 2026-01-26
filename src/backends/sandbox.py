from pathlib import Path
import os
import subprocess
import tempfile
import re
from typing import Optional, Union

from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import SandboxBackendProtocol, ExecuteResponse


class SandboxFilesystemBackend(FilesystemBackend, SandboxBackendProtocol):
    """
    `SandboxFilesystemBackend`: 为 Linux/macOS 提供严格路径限制的文件系统后端。
    仅允许通过 execute 方法运行 uvx 命令。
    """

    def __init__(
            self,
            root_dir: Optional[Union[str, Path]] = None,
            virtual_mode: bool = False,
            max_file_size_mb: int = 10,
            max_output_length: int = 100000,  # 100KB
            timeout_seconds: int = 300,
            **kwargs
    ) -> None:
        # 设置根目录
        self.root_dir = Path(root_dir) if root_dir else Path(tempfile.mkdtemp())
        self.root_dir = self.root_dir.resolve()

        self.max_output_length = max_output_length
        self.timeout_seconds = timeout_seconds

        # 调用父类初始化
        super().__init__(
            root_dir=str(self.root_dir),
            virtual_mode=virtual_mode,
            max_file_size_mb=max_file_size_mb,
        )

    def _validate_uvx_command(self, command: str) -> bool:
        """验证命令是否是合法的 uvx 命令
        
        规则：只要以 uvx 开头的命令都允许
        """
        command = command.strip()

        # 检查是否以 uvx 开头（允许前面有空格）
        pattern = r'^\s*uvx'
        return bool(re.match(pattern, command))

    def execute(
            self,
            command: str,
    ) -> ExecuteResponse:
        """在沙箱环境中执行uvx命令，仅允许运行 uvx 命令

        Args:
            command: 要执行的完整uvx命令字符串

        Returns:
            ExecuteResponse包含输出、退出码和截断标志
        """
        try:
            # 验证命令是否是合法的 uvx 命令
            if not self._validate_uvx_command(command):
                return ExecuteResponse(
                    output=f"错误: 只允许执行 uvx 命令。命令: {command}",
                    exit_code=-1,
                    truncated=False
                )

            # 构建安全的执行命令
            safe_command = f'cd "{self.root_dir}" && {command}'

            # 设置受限的环境变量
            env = {
                'PATH': f'/usr/bin:/bin:/usr/local/bin:{os.path.expanduser("~/.local/bin")}:/opt/homebrew/bin',
                'HOME': str(self.root_dir),
                'PWD': str(self.root_dir),
                'TMPDIR': str(self.root_dir),  # 限制临时目录
            }

            # 继承一些安全的环境变量
            for key in ['LANG', 'LC_ALL', 'TERM']:
                if key in os.environ:
                    env[key] = os.environ[key]

            # 执行命令
            result = subprocess.run(
                safe_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
                cwd=str(self.root_dir)
            )

            # 合并stdout和stderr
            output = result.stdout
            if result.stderr:
                output += result.stderr

            # 如果输出太大则截断
            truncated = False
            if len(output) > self.max_output_length:
                output = output[:self.max_output_length]
                truncated = True
                output += "\n\n... [输出被截断，超过最大长度限制] ..."

            return ExecuteResponse(
                output=output,
                exit_code=result.returncode,
                truncated=truncated
            )

        except subprocess.TimeoutExpired:
            return ExecuteResponse(
                output=f"错误: 命令执行超时 (超过 {self.timeout_seconds} 秒)",
                exit_code=-1,
                truncated=False
            )
        except Exception as e:
            return ExecuteResponse(
                output=f"执行命令时出错: {str(e)}",
                exit_code=-1,
                truncated=False
            )
