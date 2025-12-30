"""沙箱后端管理器 - 为每个对话创建独立的沙箱路径并自动清理

这个模块提供了 SandboxBackendManager 类，用于管理多个对话的独立沙箱目录。
每个对话（由 thread_id 标识）都会获得自己的临时文件系统，对话结束后可以自动清理。

所有操作都是纯异步的，使用 aiofiles 避免 blockbuster 的阻塞检测。
"""

import contextvars
import asyncio
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from aiofiles import os as aiofiles_os
from aiofiles import open as aiofiles_open
from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import BackendProtocol, BackendFactory
from rich.console import Console
from rich.tree import Tree

# 全局 ContextVar，用于在整个调用链中传递 thread_id
_current_thread_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "_current_thread_id", default=None
)


class SandboxBackendManager:
    """
    沙箱后端管理器 - 为每个线程/对话创建独立的临时目录
    所有操作都是异步的，避免 blockbuster 的阻塞检测
    """

    def __init__(self, base_dir: str = "./sandbox_sessions/"):
        """
        初始化沙箱管理器

        Args:
            base_dir: 沙箱会话的基础目录
        """
        self.base_dir = Path(base_dir)
        # 同步初始化，仅在模块启动时执行一次
        if not self.base_dir.exists():
            self.base_dir.mkdir(parents=True, exist_ok=True)
        self._session_dirs = {}  # thread_id -> temp_dir_path

    async def create_session_dir(self, thread_id: str) -> Path:
        """
        为指定的 thread_id 创建临时目录（异步）

        Args:
            thread_id: 对话的唯一标识符

        Returns:
            临时目录的 Path 对象
        """
        if thread_id not in self._session_dirs:
            session_dir = self.base_dir / thread_id
            # 使用 aiofiles.os.mkdir 避免阻塞
            try:
                await aiofiles_os.makedirs(session_dir, exist_ok=True)
            except Exception:
                # 如果已经存在，忽略错误
                pass
            self._session_dirs[thread_id] = session_dir
        return self._session_dirs[thread_id]

    async def _acopy_directory_recursively(
        self, 
        source_dir: Path, 
        session_dir: Path, 
        relative_to: Path
    ) -> int:
        """
        递归复制目录结构到沙箱（纯异步）

        Args:
            source_dir: 当前要复制的源目录
            session_dir: 沙箱会话目录
            relative_to: 原始根目录，用于计算相对路径

        Returns:
            复制的文件数量
        """
        # 计算相对路径
        relative_path = source_dir.relative_to(relative_to)
        dest_dir = session_dir / relative_path
        
        # 创建目标目录（异步）
        try:
            await aiofiles_os.makedirs(dest_dir, exist_ok=True)
        except Exception:
            pass
        
        file_count = 0
        
        # 异步遍历目录
        try:
            entries = await aiofiles_os.scandir(source_dir)
            for entry in entries:
                if entry.is_dir():
                    # 递归处理子目录
                    file_count += await self._acopy_directory_recursively(
                        Path(entry.path), 
                        session_dir, 
                        relative_to
                    )
                elif entry.is_file():
                    dest_file = dest_dir / entry.name
                    # 异步复制文件
                    await self._acopy_file(Path(entry.path), dest_file)
                    file_count += 1
        except (FileNotFoundError, PermissionError):
            pass
        
        return file_count

    async def _acopy_file(self, source: Path, dest: Path) -> None:
        """
        异步复制单个文件
        
        Args:
            source: 源文件路径
            dest: 目标文件路径
        """
        # 确保目标目录存在
        dest_parent = dest.parent
        try:
            await aiofiles_os.makedirs(dest_parent, exist_ok=True)
        except Exception:
            pass
        
        # 异步读取和写入
        async with aiofiles_open(source, 'rb') as src_file:
            content = await src_file.read()
            async with aiofiles_open(dest, 'wb') as dest_file:
                await dest_file.write(content)
        
        # 尝试复制元数据（这部分可能需要同步，但只在复制完成后执行）
        try:
            stat_info = await aiofiles_os.stat(source)
            await aiofiles_os.utime(
                dest, 
                (stat_info.st_atime, stat_info.st_mtime)
            )
        except Exception:
            pass

    def _print_tree_structure(self, directory: Path, prefix: str = "", is_last: bool = True):
        """
        打印目录的树状结构（同步，仅在打印时使用）
        """
        if not directory.exists():
            return

        items = sorted(directory.iterdir(), key=lambda x: (not x.is_file(), x.name))
        
        for i, item in enumerate(items):
            is_item_last = i == len(items) - 1
            current_prefix = "└── " if is_item_last else "├── "
            item_name = item.name
            print(f"{prefix}{current_prefix}{item_name}")
            
            if item.is_dir():
                next_prefix = prefix + ("    " if is_item_last else "│   ")
                self._print_tree_structure(item, next_prefix, is_item_last)

    def _build_rich_tree(self, directory: Path, parent_tree: Tree) -> None:
        """
        递归构建 rich 树状结构（同步，仅在打印时使用）
        """
        if not directory.exists():
            return

        items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))

        for item in items:
            if item.is_dir():
                branch = parent_tree.add(f"📁 [bold cyan]{item.name}[/bold cyan]")
                self._build_rich_tree(item, branch)
            else:
                file_size = item.stat().st_size
                size_str = self._format_file_size(file_size)
                parent_tree.add(f"📄 {item.name} [dim]({size_str})[/dim]")

    def _format_file_size(self, size_bytes: int) -> str:
        """
        格式化文件大小为人类可读的形式
        """
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}TB"

    def print_file_tree(self, directory: Path | None = None, title: str | None = None) -> None:
        """
        使用 rich 库打印精美的文件树结构（同步，仅在打印时使用）

        Args:
            directory: 要打印的目录路径，如果为 None 则打印沙箱根目录
            title: 树的标题，如果为 None 则使用目录名称
        """
        console = Console()

        if directory is None:
            directory = self.base_dir

        if not directory.exists():
            console.print(f"[red]⚠️  目录不存在: {directory}[/red]")
            return

        if title is None:
            title = f"📁 [bold]{directory.name}[/bold]"

        tree = Tree(title)
        self._build_rich_tree(directory, tree)
        console.print(tree)

    async def print_session_file_tree(self, thread_id: str, title: str | None = None) -> None:
        """
        打印指定会话的沙箱文件树（异步）
        """
        session_dir = self._session_dirs.get(thread_id)

        if not session_dir or not session_dir.exists():
            console = Console()
            console.print(f"[red]⚠️  会话 {thread_id} 不存在或已被清理[/red]")
            return

        if title is None:
            title = f"📦 [bold green]会话沙箱[/bold green] [dim]({thread_id[:8]}...)[/dim]"

        # 打印是同步的，但整个方法标记为异步以避免混淆
        self.print_file_tree(session_dir, title)

    async def upload_files_to_sandbox(self, thread_id: str, source_dir: str = "./files/") -> None:
        """
        将源目录的文件复制到沙箱目录中，保留原始目录结构（纯异步）

        Args:
            thread_id: 对话的唯一标识符
            source_dir: 源目录路径，默认为 ./files/
        """
        source_path = Path(source_dir)

        # 异步检查源目录是否存在
        try:
            exists = await aiofiles_os.path.exists(source_path)
        except Exception:
            exists = False
            
        if not exists:
            print(f"⚠️  源目录不存在: {source_path}")
            return

        # 确保沙箱目录已创建（异步）
        session_dir = await self.create_session_dir(thread_id)

        # 异步遍历并复制
        file_count = 0
        try:
            entries = await aiofiles_os.scandir(source_path)
            for entry in entries:
                if entry.is_dir():
                    file_count += await self._acopy_directory_recursively(
                        Path(entry.path), 
                        session_dir, 
                        source_path
                    )
                elif entry.is_file():
                    dest_file = session_dir / entry.name
                    await self._acopy_file(Path(entry.path), dest_file)
                    file_count += 1
        except (FileNotFoundError, PermissionError):
            pass

        # 使用 rich 库打印文件树
        print('\n')
        console = Console()
        console.print(f"[bold green]📂 沙箱目录: {session_dir}[/bold green]")
        self.print_file_tree(session_dir)
        print('\n')

    async def _aremove_directory(self, directory: Path) -> None:
        """
        异步递归删除目录
        
        Args:
            directory: 要删除的目录路径
        """
        if not directory.exists():
            return
        
        try:
            # 先递归删除所有内容
            entries = await aiofiles_os.scandir(directory)
            for entry in entries:
                if entry.is_dir():
                    await self._aremove_directory(Path(entry.path))
                elif entry.is_file():
                    await aiofiles_os.remove(entry.path)
            
            # 删除空目录
            try:
                await aiofiles_os.rmdir(directory)
            except OSError:
                pass
        except (FileNotFoundError, PermissionError):
            pass

    async def cleanup_session(self, thread_id: str) -> None:
        """
        清理指定 thread_id 的沙箱目录（纯异步）

        Args:
            thread_id: 对话的唯一标识符
        """
        if thread_id in self._session_dirs:
            session_dir = self._session_dirs[thread_id]
            await self._aremove_directory(session_dir)
            print(f"🗑️  清理沙箱目录: {session_dir}")
            del self._session_dirs[thread_id]

    async def cleanup_all(self) -> None:
        """清理所有沙箱目录（并发异步）"""
        tasks = [self.cleanup_session(thread_id) for thread_id in list(self._session_dirs.keys())]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def create_backend_factory(self) -> BackendFactory:
        """
        创建一个 BackendFactory，它会根据运行时的 thread_id 动态创建 backend

        Returns:
            一个函数，接受 Runtime 对象并返回 BackendProtocol 实例
        """

        # 预先解析基础目录，避免在 factory 中调用 resolve()
        # 这只在模块加载时执行一次，不会在异步上下文中
        try:
            resolved_base_dir = str(self.base_dir.resolve())
        except Exception:
            # 如果 resolve 失败，使用绝对路径
            resolved_base_dir = str(self.base_dir.absolute())

        def backend_factory(runtime) -> BackendProtocol:
            """
            根据运行时配置的 thread_id 创建对应的 backend

            Args:
                runtime: LangGraph 的 Runtime 或 ToolRuntime 对象

            Returns:
                配置好独立沙箱路径的 FilesystemBackend
            
            Note:
                backend_factory 在不同时机被调用：
                - 模型调用时：runtime 是 langgraph.runtime.Runtime（无 config 属性）
                - 工具调用时：runtime 是 langchain.prebuilt.tool_node.ToolRuntime（有 config 属性）
                实际文件操作发生在工具调用时，此时可正确获取 thread_id
            """
            # 优先从 ContextVar 获取 thread_id（这是最可靠的方式）
            thread_id = _current_thread_id.get()

            # 如果 ContextVar 中没有，尝试从 runtime 获取（兼容性后备）
            if thread_id is None:
                if hasattr(runtime, 'config'):
                    config = runtime.config
                    if config is not None and isinstance(config, dict):
                        configurable = config.get('configurable', {})
                        thread_id = configurable.get('thread_id')

            # 如果还是没有 thread_id，生成 UUID 作为后备
            if thread_id is None:
                thread_id = str(uuid.uuid4())

            # 获取会话目录路径（不调用 resolve）
            if thread_id not in self._session_dirs:
                session_dir = self.base_dir / thread_id
                self._session_dirs[thread_id] = session_dir
            else:
                session_dir = self._session_dirs[thread_id]
            
            # 直接拼接字符串而不是使用 Path 操作
            full_path = os.path.join(resolved_base_dir, thread_id)

            # 创建 FilesystemBackend 并手动设置属性，避免触发 resolve()
            backend = FilesystemBackend.__new__(FilesystemBackend)
            backend.cwd = Path(full_path)
            backend.root_dir = str(backend.cwd)
            backend.virtual_mode = True
            
            # 设置其他必要的属性
            backend._files = {}
            backend._initialized = True

            return backend

        return backend_factory

    async def get_session_info(self, thread_id: str) -> dict:
        """
        获取指定会话的信息（纯异步）

        Args:
            thread_id: 对话的唯一标识符

        Returns:
            包含会话信息的字典：
            {
                "thread_id": "...",
                "session_dir": "...",
                "exists": bool,
                "file_count": int
            }
        """
        session_dir = self._session_dirs.get(thread_id)
        if not session_dir:
            return {
                "thread_id": thread_id,
                "session_dir": None,
                "exists": False,
                "file_count": 0
            }

        exists = await aiofiles_os.path.exists(session_dir)
        file_count = 0
        
        if exists:
            # 异步统计文件数量
            try:
                entries = await aiofiles_os.scandir(session_dir)
                for entry in entries:
                    if entry.is_file():
                        file_count += 1
                    elif entry.is_dir():
                        # 递归统计子目录
                        sub_entries = await aiofiles_os.scandir(entry.path)
                        for sub_entry in sub_entries:
                            if sub_entry.is_file():
                                file_count += 1
            except Exception:
                pass

        return {
            "thread_id": thread_id,
            "session_dir": str(session_dir),
            "exists": exists,
            "file_count": file_count
        }

    async def list_all_sessions(self) -> list:
        """
        列出所有活动的会话（并发异步）

        Returns:
            会话信息列表
        """
        tasks = [self.get_session_info(thread_id) for thread_id in self._session_dirs.keys()]
        if tasks:
            return await asyncio.gather(*tasks)
        return []

    def __len__(self) -> int:
        """返回当前活动的会话数量"""
        return len(self._session_dirs)

    def __contains__(self, thread_id: str) -> bool:
        """检查指定的 thread_id 是否有活动的会话"""
        return thread_id in self._session_dirs


# 全局沙箱管理器实例
sandbox_manager = SandboxBackendManager()