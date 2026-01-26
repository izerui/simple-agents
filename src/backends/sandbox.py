"""
Deno + uvx Python 沙箱后端

使用 Deno + uvx 管理依赖，在隔离环境中执行 uvx 命令。
"""
from pathlib import Path
import os
import subprocess
import tempfile
from typing import Optional, Union

from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import SandboxBackendProtocol, ExecuteResponse
from src.utils._deno_setup import ensure_deno




class SandboxFilesystemBackend(FilesystemBackend, SandboxBackendProtocol):
    """
    `SandboxFilesystemBackend`: 为 Linux/macOS 提供严格路径限制的文件系统后端。
    使用 Deno + uvx 管理依赖，在隔离环境中执行 uvx 命令。

    特性：
    - 直接执行 uvx 命令：uvx 自己管理依赖
    - 工作目录隔离：通过 -m 参数设置工作目录
    - 环境变量隔离：清空敏感环境变量
    - 快速执行：依赖缓存后，后续执行非常快

    注意：root_dir 应该在初始化时设置为对应 thread 的专属目录。
    """

    def __init__(
        self,
        root_dir: Optional[Union[str, Path]] = None,
        virtual_mode: bool = False,
        max_file_size_mb: int = 10,
        max_output_length: int = 100000,  # 100KB
        timeout_seconds: int = 300,
        cache_dir: Optional[str] = None,
        **kwargs
    ) -> None:
        # 设置根目录（应该是 thread 专属目录）
        self.root_dir = Path(root_dir) if root_dir else Path(tempfile.mkdtemp())
        self.root_dir = self.root_dir.resolve()

        self.max_output_length = max_output_length
        self.timeout_seconds = timeout_seconds
        self.cache_dir = cache_dir

        # 调用父类初始化
        super().__init__(
            root_dir=str(self.root_dir),
            virtual_mode=virtual_mode,
            max_file_size_mb=max_file_size_mb,
        )

    def execute(
        self,
        command: str,
    ) -> ExecuteResponse:
        """在沙箱环境中执行 uvx 命令

        直接执行标准的 uvx 命令，uvx 自己会管理依赖。
        
        Args:
            command: 要执行的 uvx 命令（例如 "uvx --with requests python script.py"）

        Returns:
            ExecuteResponse包含输出、退出码和截断标志
        """
        try:
            # 确保 Deno 已安装，获取 deno 路径
            deno_path = ensure_deno()

            # 构造 Deno 命令
            # --allow-read: 允许读取文件（需要访问 runner 脚本）
            # --allow-write: 允许写入文件
            # --allow-run: 允许运行 uvx
            # --allow-env: 允许访问 PATH、HOME 等必要环境变量
            script_path = Path.cwd() / "scripts" / "uvx_runner" / "mod.ts"
            
            # 使用 deno 可执行文件
            deno_command = [
                str(deno_path), "run",
                "--allow-read",
                "--allow-write",
                "--allow-run",
                # "--allow-env",
                str(script_path),
                "-m", str(self.root_dir),  # 设置工作目录
                "-c", command,  # 直接传递 uvx 命令
            ]

            # 添加缓存目录
            if self.cache_dir:
                deno_command.extend(["--cache-dir", str(self.cache_dir)])

            # 执行沙箱进程
            # 保留必要的环境变量（PATH、HOME、USER）以支持 uvx
            env_vars = {
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", ""),
                "USER": os.environ.get("USER", ""),
            }
            process = subprocess.Popen(
                deno_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.root_dir),
                env=env_vars,  # 只保留必要的环境变量
                text=True
            )

            try:
                # 添加超时控制
                stdout, stderr = process.communicate(
                    timeout=self.timeout_seconds
                )
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                return ExecuteResponse(
                    output=f"错误: 脚本执行超时（超过 {self.timeout_seconds} 秒），已强制终止。",
                    exit_code=-1,
                    truncated=False
                )

            # 步骤 6: 解析 JSON 输出（Deno + uvx runner 输出 JSON 格式）
            import json
            try:
                result = json.loads(stdout)
                stdout_content = result.get("stdout", "")
                stderr_content = result.get("stderr", "")
                success = result.get("success", False)

                # 合并 stdout 和 stderr
                output = stdout_content
                if stderr_content:
                    output += f"\n[错误输出]\n{stderr_content}"

                # 根据成功状态设置退出码
                exit_code = result.get("exitCode", 0 if success else 1)
            except json.JSONDecodeError:
                # 如果输出不是 JSON，可能是错误信息
                output = stdout
                if stderr:
                    output += f"\n[错误输出]\n{stderr}"
                exit_code = process.returncode

            # 步骤 7: 如果输出太大则截断
            truncated = False
            if len(output) > self.max_output_length:
                output = output[:self.max_output_length]
                truncated = True
                output += "\n\n... [输出被截断，超过最大长度限制] ..."

            return ExecuteResponse(
                output=output,
                exit_code=exit_code,
                truncated=truncated
            )

        except Exception as e:
            return ExecuteResponse(
                output=f"系统异常: {str(e)}",
                exit_code=-1,
                truncated=False
            )