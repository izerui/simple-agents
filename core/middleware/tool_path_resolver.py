"""用于解析工具调用中的虚拟文件系统路径的中间件。"""
import copy
import logging
from typing import Awaitable, Callable, List, Optional

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

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

            tool_call = copy.deepcopy(request.tool_call)
            tool_call['args']['_backend'] = backend
            # 创建包含解析后参数的新请求
            modified_request = ToolCallRequest(
                tool=request.tool,
                tool_call=tool_call,
                runtime=request.runtime,
                state=request.state,
            )

            return await handler(modified_request)

        except Exception as e:
            # 出错时,继续使用原始请求
            return await handler(request)
