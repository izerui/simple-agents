"""用于解析工具调用中的虚拟文件系统路径的中间件。"""
import copy
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, List, Optional

from langchain.agents.middleware.types import AgentMiddleware, StateT
from langgraph.prebuilt.tool_node import ToolCallRequest, ToolRuntime
from langgraph.types import Command
from langchain_core.messages import ToolMessage

from deepagents.backends.filesystem_async import AsyncFilesystemBackend

logger = logging.getLogger(__name__)


class ToolPathResolverMiddleware(AgentMiddleware):
    """用于解析工具调用中的虚拟文件系统路径的中间件。

    此中间件拦截工具调用,在工具执行之前将虚拟文件系统路径解析为
    真实文件系统路径。当使用虚拟文件系统后端且工具需要真实文件系统路径时,
    这非常有用。

    中间件的工作流程:
    1. 在执行前拦截工具调用
    2. 使用后端的路径解析逻辑解析虚拟路径
    3. 修改工具参数以使用解析后的路径
    4. 将修改后的请求传递给原始处理程序
    """

    def __init__(self, backend_factory, tools_to_resolve: Optional[List[str]] = None):
        """初始化路径解析中间件。

        Args:
            backend_factory: 工厂函数,接收 ToolRuntime 并返回后端实例
            tools_to_resolve: 要应用路径解析的工具名称列表。
                            如果为 None,则应用于所有具有路径参数的工具。
        """
        self.backend_factory = backend_factory
        self.tools_to_resolve = tools_to_resolve
        logger.info("已初始化 ToolPathResolverMiddleware")

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """包装工具调用以解析虚拟路径。

        此方法拦截工具调用,解析参数中的任何虚拟路径,然后将修改后的请求
        传递给原始处理程序。工具执行后,它将响应中的真实路径转换回虚拟路径。

        Args:
            request: 工具调用请求
            handler: 路径解析后要调用的原始处理程序

        Returns:
            原始处理程序的结果,路径已转换为虚拟格式
        """
        tool_name = request.tool.name

        # 检查是否应该解析此工具的路径
        if self.tools_to_resolve is not None and tool_name not in self.tools_to_resolve:
            return await handler(request)

        try:
            # 获取后端实例
            backend: AsyncFilesystemBackend = self.backend_factory(request.runtime)

            # 检查后端是否具有虚拟模式和路径解析功能
            if not hasattr(backend, 'virtual_mode') or not backend.get_virtual_mode():
                # 不在虚拟模式下,无需解析路径
                return await handler(request)

            # 使用异步解析器解析工具参数中的路径
            resolved_args = await self._resolve_paths_in_args(
                request.tool_call['args'],
                backend.aresolve_path
            )

            # 如果没有解析任何路径,继续使用原始请求
            if resolved_args == request.tool_call['args']:
                return await handler(request)

            tool_call = copy.deepcopy(request.tool_call)
            tool_call['args'] = resolved_args
            # 创建包含解析后参数的新请求
            modified_request = ToolCallRequest(
                tool=request.tool,
                tool_call=tool_call,
                runtime=request.runtime,
                state=request.state,
            )

            logger.info(f"已为工具 {tool_name} 解析虚拟路径: {request.tool_call['args']} -> {resolved_args}")

            # 使用解析后的参数执行工具
            # 工具负责使用 sandbox_sessions_dir 参数将真实路径转换回虚拟路径
            return await handler(modified_request)

        except Exception as e:
            logger.error(f"为工具 {tool_name} 解析路径时出错: {e}", exc_info=True)
            # 出错时,继续使用原始请求
            return await handler(request)

    async def _resolve_paths_in_args(self, args: dict[str, Any], resolve_func: Callable[[str], Awaitable[Path]]) -> dict[str, Any]:
        """解析工具参数中的路径。

        此方法查找类似路径的参数,并使用提供的异步解析函数解析它们。

        Args:
            args: 原始工具参数
            resolve_func: 用于解析路径的异步函数(返回 Awaitable[Path])

        Returns:
            包含已解析路径的新参数
        """
        resolved = {}

        for key, value in args.items():
            # 检查这是否是类似路径的参数
            if isinstance(value, str) and self._is_path_arg(key):
                try:
                    resolved_path = await resolve_func(value)
                    resolved[key] = str(resolved_path)
                except Exception:
                    # 如果解析失败,保留原始值
                    resolved[key] = value
            else:
                resolved[key] = value

        # 在处理完所有参数后始终设置 sandbox_sessions_dir
        # 这确保即使没有解析路径参数,该参数也存在
        try:
            resolved['sandbox_sessions_dir'] = str(await resolve_func('/'))
        except Exception:
            # 如果根路径解析失败,不添加该参数
            pass

        return resolved

    def _is_path_arg(self, arg_name: str) -> bool:
        """检查参数名称是否表明它是一个路径。

        Args:
            arg_name: 要检查的参数名称

        Returns:
            如果参数名称表明它是路径,则返回 True
        """
        path_keywords = ['path', 'file', 'dir', 'directory', 'folder', 'filename']
        arg_lower = arg_name.lower()
        return any(keyword in arg_lower for keyword in path_keywords)