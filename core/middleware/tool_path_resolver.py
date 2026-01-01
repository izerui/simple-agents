"""Middleware for resolving virtual filesystem paths in tool calls."""
import copy
import logging
from typing import Any, Awaitable, Callable, List, Optional

from langchain.agents.middleware.types import AgentMiddleware, StateT
from langgraph.prebuilt.tool_node import ToolCallRequest, ToolRuntime
from langgraph.types import Command
from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)


class ToolPathResolverMiddleware(AgentMiddleware):
    """Middleware for resolving virtual filesystem paths in tool calls.
    
    This middleware intercepts tool calls and resolves virtual filesystem paths
    to real filesystem paths before the tool is executed. This is useful when
    using a virtual filesystem backend where tools expect real filesystem paths.
    
    The middleware:
    1. Intercepts tool calls before execution
    2. Resolves virtual paths using the backend's path resolution logic
    3. Modifies the tool arguments to use resolved paths
    4. Passes the modified request to the original handler
    """

    def __init__(self, backend_factory, tools_to_resolve: Optional[List[str]] = None):
        """Initialize the path resolver middleware.
        
        Args:
            backend_factory: Factory function that returns a backend instance
                           given a ToolRuntime
            tools_to_resolve: List of tool names to apply path resolution to.
                            If None, applies to all tools with path-like arguments.
        """
        self.backend_factory = backend_factory
        self.tools_to_resolve = tools_to_resolve
        logger.info("Initialized ToolPathResolverMiddleware")

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Wrap tool calls to resolve virtual paths.
        
        This method intercepts tool calls, resolves any virtual paths in the
        arguments, and then passes the modified request to the original handler.
        
        Args:
            request: The tool call request
            handler: The original handler to call after path resolution
            
        Returns:
            The result from the original handler
        """
        tool_name = request.tool.name
        
        # Check if we should resolve paths for this tool
        if self.tools_to_resolve is not None and tool_name not in self.tools_to_resolve:
            return await handler(request)
        
        try:
            # Get the backend instance
            backend = self.backend_factory(request.runtime)
            
            # Check if backend has virtual mode and path resolution
            if not hasattr(backend, 'virtual_mode') or not backend.virtual_mode:
                # Not in virtual mode, no need to resolve paths
                return await handler(request)
            
            # Resolve paths in the tool arguments
            resolved_args = self._resolve_paths_in_args(
                request.tool_call['args'],
                backend._resolve_path
            )
            
            # If no paths were resolved, proceed with original request
            if resolved_args == request.tool_call['args']:
                return await handler(request)

            tool_call = copy.deepcopy(request.tool_call)
            tool_call['args'] = resolved_args
            # Create a new request with resolved arguments
            modified_request = ToolCallRequest(
                tool=request.tool,
                tool_call=tool_call,
                runtime=request.runtime,
                state=request.state,
            )
            
            logger.info(f"Resolved virtual paths for tool {tool_name}: {request.tool_call['args']} -> {resolved_args}")
            
            return await handler(modified_request)
            
        except Exception as e:
            logger.error(f"Error resolving paths for tool {tool_name}: {e}", exc_info=True)
            # On error, proceed with original request
            return await handler(request)
    
    def _resolve_paths_in_args(self, args: dict[str, Any], resolve_func: Callable[[str], Any]) -> dict[str, Any]:
        """Resolve paths in tool arguments.
        
        This method looks for path-like arguments and resolves them using
        the provided resolve function.
        
        Args:
            args: The original tool arguments
            resolve_func: Function to resolve paths
            
        Returns:
            New arguments with resolved paths
        """
        resolved = {}
        
        for key, value in args.items():
            # Check if this is a path-like argument
            if isinstance(value, str) and self._is_path_arg(key):
                try:
                    resolved_path = resolve_func(value)
                    resolved[key] = str(resolved_path)
                except Exception:
                    # If resolution fails, keep original value
                    resolved[key] = value
            else:
                resolved[key] = value
        
        return resolved
    
    def _is_path_arg(self, arg_name: str) -> bool:
        """Check if an argument name suggests it's a path.
        
        Args:
            arg_name: The argument name to check
            
        Returns:
            True if the argument name suggests it's a path
        """
        path_keywords = ['path', 'file', 'dir', 'directory', 'folder', 'filename']
        arg_lower = arg_name.lower()
        return any(keyword in arg_lower for keyword in path_keywords)