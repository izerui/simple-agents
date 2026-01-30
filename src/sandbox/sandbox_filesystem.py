# -*- coding: utf-8 -*-
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union

from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import SandboxBackendProtocol, ExecuteResponse, FileInfo
from src.sandbox.pycode_executor import CodeExecutor
from src.sandbox.dependency_executor import DependencyExecutor
import re
import platform
import os

def copytree_hardlink(src, dst):
    """跨平台硬链接复制"""
    # 如果目标已存在，跳过
    if os.path.exists(dst):
        print(f"⏭️ skills 已存在，跳过: {dst}")
        return

    system = platform.system()
    success = False
    if system == "Linux":
        # Linux 使用 cp -al
        try:
            subprocess.run(['cp', '-al', str(src), str(dst)], check=True)
            success = True
        except Exception as e:
            print(f"⚠️ linux 创建 skills 硬链接 失败: {e}")
    else:
        # 其他系统使用普通复制
        shutil.copytree(src, dst, dirs_exist_ok=True)
        success = True

    # 如果都失败，使用普通复制
    if not success:
        print("⚠️ 硬链接方法失败，使用普通复制 skills ")
        shutil.copytree(src, dst)

class SandboxFilesystemBackend(FilesystemBackend, SandboxBackendProtocol):
    """
    安全沙箱后端

    实现文件操作权限控制：
    - root_dir 内：允许读写
    - root_dir 外：只允许临时目录读写

    只支持两种标准执行格式：
    1. python -c "code" - 直接执行代码字符串
    2. python script.py - 执行脚本文件
    """

    def __init__(
            self,
            root_dir: Optional[Union[str, Path]] = None,
            virtual_mode: bool = False,
            max_file_size_mb: int = 10,
            max_output_length: int = 100000,  # 100KB
            **kwargs
    ) -> None:
        """初始化安全沙箱

        Args:
            root_dir: 允许读写的根目录
            virtual_mode: 虚拟模式（由父类 FilesystemBackend 使用）
            max_file_size_mb: 最大文件大小限制（MB）
            max_output_length: 最大输出长度
        """
        # 设置根目录
        self.root_dir = Path(root_dir) if root_dir else Path(tempfile.mkdtemp())
        self.root_dir = self.root_dir.resolve()

        self.max_output_length = max_output_length

        # 调用父类初始化
        super().__init__(
            root_dir=str(self.root_dir),
            virtual_mode=virtual_mode,
            max_file_size_mb=max_file_size_mb,
        )

        self._pycode_executor = CodeExecutor(
            root_dir=self.root_dir,
            max_output_length=self.max_output_length,
        )

        # 初始化依赖安装执行器
        self._dependency_executor = DependencyExecutor(
            root_dir=self.root_dir,
            max_output_length=self.max_output_length,
        )

    def execute(self, command: str) -> ExecuteResponse:
        """执行命令（统一入口）

        根据命令类型自动选择执行器：
        1. uv pip 命令 -> 使用 DependencyExecutor（依赖安装和查询）
        2. python 命令 -> 使用 CodeExecutor（Python 代码执行）

        DependencyExecutor 支持的命令：
        - uv pip install <package>（安装新包，不允许升级或重装）
        - uv pip list
        - uv pip show <package>
        - uv pip freeze
        - uv pip check

        CodeExecutor 支持的命令：
        - python -c "code" - 执行代码字符串
        - python script.py - 执行脚本文件

        Args:
            command: 命令字符串

        Returns:
            ExecuteResponse 包含输出、退出码和截断标志
        """
        command = command.strip()
        
        # 判断是否是 uv pip 命令
        if re.match(r'^uv\s+pip\s+', command, re.IGNORECASE):
            # 使用依赖安装执行器
            return self._dependency_executor.execute(command)
        else:
            # 使用 Python 代码执行器
            return self._pycode_executor.execute(command)

    def ls_info(self, path: str) -> list[FileInfo]:
        if path.startswith('/skills'):
            # 判断沙箱内 /skills 目录是否存在
            skills_pathlib = self.root_dir / 'skills'
            if not skills_pathlib.exists():
                project_root = Path(__file__).parent.parent.parent
                src_skills_path = project_root / 'src' / 'skills'
                # 复制src_skills_path 目录到沙箱内
                # shutil.copytree(src_skills_path, skills_pathlib, dirs_exist_ok=True)
                # subprocess.run(['cp', '-al', str(src_skills_path), str(skills_pathlib)], check=True)
                copytree_hardlink(str(src_skills_path), str(skills_pathlib))
        return super().ls_info(path)
