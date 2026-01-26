"""
重复工具调用防护中间件

该中间件防止 AI 智能体在同一对话中重复调用相同的工具和参数，从而避免无限循环。

功能：
- 基于 thread_id 跟踪工具调用
- 检测同一对话中的重复调用
- 为重复调用提供有意义的错误消息
- 支持不同工具类型的差异化配置
"""

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, StateT
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_config
from langgraph.prebuilt.tool_node import ToolRuntime

from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol


class DuplicateCallPreventionMiddleware(AgentMiddleware):
    """
    防止重复工具调用的中间件

    工作原理：
    1. 在每次工具调用前，通过 awrap_tool_call 拦截调用
    2. 获取当前 thread_id，并结合工具名称和参数生成唯一签名
    3. 检查 request.state 中的 latest_tool_call 是否与当前签名相同
    4. 如果相同，表示重复调用，返回错误消息
    5. 如果不同，允许调用并更新 latest_tool_call

    配置选项：
    - max_repeats: 允许的最大重复次数（默认1，即不允许连续重复）
    - strict_tools: 严格检查的工具列表，这些工具完全不允许重复
    """

    def __init__(
        self,
        *,
        backend_factory: BACKEND_TYPES | None = None,
        max_repeats: int = 1,
        strict_tools: list[str] | None = None,
    ):
        """
        初始化重复调用防护中间件

        Args:
            backend_factory: 后端工厂函数或后端实例
            max_repeats: 允许的最大重复次数（默认1，即不允许连续重复）
            strict_tools: 严格检查的工具列表，这些工具完全不允许连续重复
        """
        super().__init__()
        self.backend_factory = backend_factory
        self.max_repeats = max_repeats
        self.strict_tools = strict_tools or []

    def name(self) -> str:
        return "DuplicateCallPreventionMiddleware"

    def _get_backend(self, runtime: ToolRuntime | RunnableConfig | dict) -> BackendProtocol:
        """从后端工厂获取后端实例"""
        if self.backend_factory is None:
            raise ValueError("backend_factory must be provided")
        if callable(self.backend_factory):
            backend = self.backend_factory(runtime)
        else:
            backend = self.backend_factory
        if backend is None:
            raise ValueError("Backend factory returned None")
        return backend

    def _get_thread_id(self, runtime: ToolRuntime | dict) -> str:
        """获取当前对话的 thread_id

        优先从 runtime.config 中获取，如果不存在则尝试从 langgraph.config.get_config() 获取
        """
        # 尝试从 runtime 中获取 config
        if hasattr(runtime, 'config'):
            config = runtime.config
            if config and 'configurable' in config and 'thread_id' in config['configurable']:
                return config['configurable']['thread_id']

        # 尝试从 langgraph.config.get_config() 获取
        try:
            config: RunnableConfig = get_config()
            if config and 'configurable' in config and 'thread_id' in config['configurable']:
                return config['configurable']['thread_id']
        except Exception:
            pass

        # 如果无法获取 thread_id，返回空字符串
        return ""

    def _get_call_signature(self, tool_call: dict, thread_id: str) -> str:
        """
        生成工具调用的唯一签名

        结合 thread_id、工具名称和参数生成唯一标识

        Args:
            tool_call: 工具调用信息
            thread_id: 对话线程ID

        Returns:
            唯一签名字符串
        """
        tool_name = tool_call["name"]
        args = tool_call["args"]

        # 根据不同的工具类型使用不同的关键参数
        if tool_name == "ls":
            # ls 工具使用 path 参数
            path = args.get("path", "/")
            return f"{thread_id}:ls:{path}"

        elif tool_name == "fetch_markdown":
            # fetch_markdown 工具使用 url 参数
            url = args.get("url", "")
            return f"{thread_id}:fetch_markdown:{url}"

        elif tool_name == "read_file":
            # read_file 工具使用 file_path 参数
            file_path = args.get("file_path", args.get("path", "/"))
            return f"{thread_id}:read_file:{file_path}"

        elif tool_name == "glob":
            # glob 工具使用 pattern 和 path 参数组合
            pattern = args.get("pattern", "*")
            path = args.get("path", "/")
            return f"{thread_id}:glob:{path}:{pattern}"

        elif tool_name == "grep":
            # grep 工具使用 pattern 和 path 参数组合
            pattern = args.get("pattern", "")
            path = args.get("path", "/")
            return f"{thread_id}:grep:{path}:{pattern}"

        # 对于其他工具，使用参数字典的哈希
        args_str = "&".join(f"{k}={v}" for k, v in sorted(args.items()))
        return f"{thread_id}:{tool_name}:{args_str}"

    def _get_state_key(self) -> str:
        """获取存储在 state 中的键名"""
        return "latest_tool_call"

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | dict[str, Any]]],
    ) -> ToolMessage | dict[str, Any]:
        """
        拦截工具调用，防止连续重复调用

        Args:
            request: 工具调用请求
            handler: 原始的工具调用处理函数

        Returns:
            工具调用结果或错误消息
        """
        tool_call = request.tool_call
        tool_name = tool_call["name"]

        # 获取 thread_id
        thread_id = self._get_thread_id(request.runtime)

        # 生成当前调用的签名
        current_signature = self._get_call_signature(tool_call, thread_id)

        # 从 request.state 获取上一次的调用签名
        state_key = self._get_state_key()
        latest_signature = request.state.get(state_key, None)

        # 如果存在上一次的调用签名，检查是否与当前签名相同
        if latest_signature is not None:
            # 提取上一次调用的工具名称
            last_tool_name = latest_signature.split(":", 2)[1] if ":" in latest_signature else ""

            # 检查是否是严格工具
            is_strict = tool_name in self.strict_tools

            # 如果当前签名与上一次相同，表示重复调用
            if current_signature == latest_signature:
                # 构建错误消息
                error_msg = self._build_error_message(tool_name, tool_call["args"], is_strict)

                # 创建错误 ToolMessage
                return ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_call.get("id", ""),
                    name=tool_name,
                    status="error",
                )

        # 允许调用，执行原始的处理函数
        result = await handler(request)

        # 如果调用成功，更新 state 中的 latest_tool_call
        # 注意：state 是每个 thread 独立的，所以不需要担心跨 thread 的问题
        request.state[state_key] = current_signature

        return result

    def _build_error_message(
        self,
        tool_name: str,
        args: dict[str, Any],
        is_strict: bool,
    ) -> str:
        """
        构建有意义的错误消息

        Args:
            tool_name: 工具名称
            args: 工具参数
            is_strict: 是否是严格工具

        Returns:
            错误消息字符串
        """
        if tool_name == "ls":
            path = args.get("path", "/")
            if is_strict:
                return (
                    f"错误：你刚刚已经调用了 ls 查看目录 '{path}'。"
                    f"不要重复调用 ls 查看同一目录。请使用已获取的目录信息继续下一步任务。"
                )
            else:
                return (
                    f"警告：你刚刚已经调用了 ls 查看目录 '{path}'。"
                    f"避免重复调用 ls。如果需要查看其他目录，请指定不同的路径。"
                )

        elif tool_name == "read_file":
            file_path = args.get("file_path", args.get("path", "/"))
            if is_strict:
                return (
                    f"错误：你刚刚已经读取了文件 '{file_path}'。"
                    f"不要重复读取同一文件。请使用已读取的内容继续工作。"
                )
            else:
                return (
                    f"警告：你刚刚已经读取了文件 '{file_path}'。"
                    f"避免重复读取。如果需要再次查看，请使用之前读取的内容。"
                )

        elif tool_name == "glob":
            pattern = args.get("pattern", "*")
            path = args.get("path", "/")
            return (
                f"错误：你刚刚已经使用 glob 在 '{path}' 搜索了模式 '{pattern}'。"
                f"不要重复使用相同的搜索模式。请尝试其他模式或继续下一步。"
            )

        elif tool_name == "grep":
            pattern = args.get("pattern", "")
            path = args.get("path", "/")
            return (
                f"错误：你刚刚已经在 '{path}' 中搜索了模式 '{pattern}'。"
                f"不要重复使用相同的搜索。请尝试其他搜索词或继续下一步。"
            )

        elif tool_name == "fetch_markdown":
            url = args.get("url", "")
            if is_strict:
                return (
                    f"错误：你刚刚已经获取了 URL '{url}' 的内容。"
                    f"不要重复获取相同网页。请使用已获取的内容继续工作。"
                )
            else:
                return (
                    f"警告：你刚刚已经获取了 URL '{url}' 的内容。"
                    f"避免重复获取相同网页。如果需要再次查看，请使用之前获取的内容。"
                )

        else:
            return (
                f"错误：你刚刚已经调用了工具 '{tool_name}'。"
                f"避免重复调用相同的工具。请继续进行下一步任务。"
            )


# 创建默认的中间件实例，ls、read_file、glob、grep 严格不允许连续重复
def create_duplicate_call_prevention(
    backend_factory: BACKEND_TYPES,
) -> DuplicateCallPreventionMiddleware:
    """
    创建重复调用防护中间件的工厂函数

    Args:
        backend_factory: 后端工厂函数或后端实例

    Returns:
        配置好的重复调用防护中间件
    """
    return DuplicateCallPreventionMiddleware(
        backend_factory=backend_factory,
        strict_tools=["ls", "read_file", "glob", "grep", "fetch_markdown"],
        max_repeats=1,
    )