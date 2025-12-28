"""沙箱后端管理器 - 为每个对话创建独立的沙箱路径并自动清理

这个模块提供了 SandboxBackendManager 类，用于管理多个对话的独立沙箱目录。
每个对话（由 thread_id 标识）都会获得自己的临时文件系统，对话结束后可以自动清理。
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import Callable

from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import BackendProtocol, BackendFactory


class SandboxBackendManager:
    """
    沙箱后端管理器 - 为每个线程/对话创建独立的临时目录
    """

    def __init__(self, base_dir: str = "./sandbox_sessions/"):
        """
        初始化沙箱管理器

        Args:
            base_dir: 沙箱会话的基础目录
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._session_dirs = {}  # thread_id -> temp_dir_path

    def create_session_dir(self, thread_id: str) -> Path:
        """
        为指定的 thread_id 创建临时目录

        Args:
            thread_id: 对话的唯一标识符

        Returns:
            临时目录的 Path 对象
        """
        if thread_id not in self._session_dirs:
            session_dir = self.base_dir / thread_id
            session_dir.mkdir(parents=True, exist_ok=True)
            self._session_dirs[thread_id] = session_dir
            print(f"📁 创建沙箱目录: {session_dir}")
        return self._session_dirs[thread_id]

    def cleanup_session(self, thread_id: str):
        """
        清理指定 thread_id 的沙箱目录

        Args:
            thread_id: 对话的唯一标识符
        """
        if thread_id in self._session_dirs:
            session_dir = self._session_dirs[thread_id]
            if session_dir.exists():
                shutil.rmtree(session_dir)
                print(f"🗑️  清理沙箱目录: {session_dir}")
            del self._session_dirs[thread_id]

    def cleanup_all(self):
        """清理所有沙箱目录"""
        for thread_id in list(self._session_dirs.keys()):
            self.cleanup_session(thread_id)

    def create_backend_factory(self) -> BackendFactory:
        """
        创建一个 BackendFactory，它会根据运行时的 thread_id 动态创建 backend

        Returns:
            一个函数，接受 Runtime 对象并返回 BackendProtocol 实例
        """

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
            # 从运行时配置中获取 thread_id
            thread_id = None

            # 情况 1: ToolRuntime 类型 - 在工具调用时传入，有 config 属性
            if hasattr(runtime, 'config'):
                config = runtime.config
                if config is not None and isinstance(config, dict):
                    configurable = config.get('configurable', {})
                    thread_id = configurable.get('thread_id')

            # 情况 2: Runtime 类型 - 在模型调用时传入，尝试从 state 获取
            if thread_id is None and hasattr(runtime, 'state'):
                state = runtime.state
                if isinstance(state, dict) and 'config' in state:
                    config = state['config']
                    if isinstance(config, dict):
                        configurable = config.get('configurable', {})
                        thread_id = configurable.get('thread_id')

            # 如果还是没有 thread_id，生成一个新的 UUID 作为后备
            # 这通常发生在模型调用阶段（不进行实际文件操作）
            if thread_id is None:
                thread_id = str(uuid.uuid4())

            # 为这个对话创建独立目录
            session_dir = self.create_session_dir(thread_id)

            # 创建使用该目录的 backend
            return FilesystemBackend(
                root_dir=str(session_dir),
                virtual_mode=True
            )

        return backend_factory

    def get_session_info(self, thread_id: str) -> dict:
        """
        获取指定会话的信息

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

        file_count = 0
        if session_dir.exists():
            file_count = sum(1 for _ in session_dir.rglob("*") if _.is_file())

        return {
            "thread_id": thread_id,
            "session_dir": str(session_dir),
            "exists": session_dir.exists(),
            "file_count": file_count
        }

    def list_all_sessions(self) -> list:
        """
        列出所有活动的会话

        Returns:
            会话信息列表
        """
        return [self.get_session_info(thread_id) for thread_id in self._session_dirs.keys()]

    def __len__(self) -> int:
        """返回当前活动的会话数量"""
        return len(self._session_dirs)

    def __contains__(self, thread_id: str) -> bool:
        """检查指定的 thread_id 是否有活动的会话"""
        return thread_id in self._session_dirs


# 全局沙箱管理器实例
# 可以在应用中使用这个全局实例，也可以创建多个独立的管理器
sandbox_manager = SandboxBackendManager()