# -*- coding: utf-8 -*-
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union

from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import SandboxBackendProtocol, ExecuteResponse, FileInfo
from src.sandbox.dependency_executor import DependencyExecutor
from src.sandbox.pycode_executor import CodeExecutor

# 无法直接读取需要转换的文件类型 PDF、DOCX、XLSX、PPTX、
CONVERT_FILE_TYPES = [
    '.pdf',
    '.doc',
    '.docx',
    '.ppt',
    '.pptx',
]


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
        1. python -m pip 命令 -> 使用 DependencyExecutor（依赖安装和查询）
        2. python 命令 -> 使用 CodeExecutor（Python 代码执行）

        DependencyExecutor 支持的命令：
        - python -m pip install <package>（安装新包，不允许升级或重装）
        - python -m pip list
        - python -m pip show <package>
        - python -m pip freeze
        - python -m pip check

        CodeExecutor 支持的命令：
        - python -c "code" - 执行代码字符串
        - python script.py - 执行脚本文件

        ⚠️ 重要说明：
        针对文件和目录相关操作，请使用以下内置工具方法，不要使用 execute：
        - ls          - 列出指定目录中的文件和子目录
        - read_file   - 读取文件内容，支持分页读取
        - write_file  - 将内容写入指定文件，覆盖现有内容
        - edit_file   - 编辑文件，支持字符串替换操作
        - glob        - 使用模式匹配查找文件（如 **/*.py）
        - grep        - 在文件中搜索文本模式（支持正则表达式）

        这些工具由 FilesystemMiddleware 自动注入，提供更安全、高效的文件操作方式。

        Args:
            command: 命令字符串

        Returns:
            ExecuteResponse 包含输出、退出码和截断标志
        """
        command = command.strip()

        # 判断是否是 python -m pip 命令
        if re.match(r'^python\s*-m\s+pip\s+', command, re.IGNORECASE):
            # 使用依赖安装执行器
            return self._dependency_executor.execute(command)
        else:
            # 使用 Python 代码执行器
            return self._pycode_executor.execute(command)

    def ls_info(self, path: str) -> list[FileInfo]:
        if path.startswith('/skills'):
            project_root = Path(__file__).parent.parent.parent
            src_skills_path = project_root / 'src' / 'skills'

            # 提取子技能目录名（如 /skills/paper-detector -> paper-detector）
            path_parts = path.rstrip('/').split('/')
            if len(path_parts) > 2:
                # 访问的是具体子技能目录
                skill_name = path_parts[2]
                src_skill_path = src_skills_path / skill_name
                sandbox_skill_path = self.root_dir / 'skills' / skill_name

                # 判断源子技能目录是否存在
                if src_skill_path.exists():
                    # 判断沙箱子技能目录是否存在
                    if not sandbox_skill_path.exists():
                        # 确保父目录存在
                        sandbox_skill_path.parent.mkdir(parents=True, exist_ok=True)
                        # 复制具体子技能目录到沙箱内
                        copytree_hardlink(str(src_skill_path), str(sandbox_skill_path))
            else:
                # 访问的是 /skills 根目录
                skills_pathlib = self.root_dir / 'skills'
                if not skills_pathlib.exists():
                    # 复制整个 src/skills 目录到沙箱内
                    copytree_hardlink(str(src_skills_path), str(skills_pathlib))
        return super().ls_info(path)

    # def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
    #     # 如果是pdf文件
    #     if file_path.lower().endswith('.pdf'):
    #         # 判断同名md文件是否存在
    #         _file_path = self._resolve_path(file_path)
    #         _markdown_path = _file_path.with_suffix(".md")
    #         if not _markdown_path.exists():
    #             # pdftotext -layout input.pdf output.txt
    #             try:
    #                 subprocess.run(['pdftotext', '-layout', str(_file_path), str(_markdown_path)], check=True)
    #             except Exception as e:
    #                 print(f"pdftotext pdf文件: {file_path} 失败: {e}")
    #         if _markdown_path.exists():
    #             return super().read(str(Path(file_path).with_suffix('.md')), offset, limit)
    #     return super().read(file_path, offset, limit)
