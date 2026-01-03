"""Research Agent - Standalone script for LangGraph deployment.

This module creates a deep research agent with custom tools and prompts
for conducting web research with strategic thinking and context management.

Supports per-conversation sandbox isolation using BackendFactory.
"""
import os
from datetime import datetime

from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.chat_models import init_chat_model
from langchain_anthropic import ChatAnthropic

from core.tools.converts import convert_pdf_to_markdown, convert_docx_to_markdown
from core.tools.fetch import fetch_markdown
from core.tools.think import think_tool
from deepagents import create_deep_agent, SubAgent
from langgraph.prebuilt import ToolRuntime

from deepagents.backends import FilesystemBackend
from deepagents.backends.filesystem_async import AsyncFilesystemBackend
from core.middleware.attachment_extract import AttachmentExtractMiddleware
from core.middleware.tool_path_resolver import ToolPathResolverMiddleware
from prompts import (
    AGENT_WORKFLOW_INSTRUCTIONS,
    SUBAGENT_INSTRUCTIONS,
    SUBAGENT_DELEGATION_INSTRUCTIONS,
)

# Limits
max_concurrent_research_units = 3
max_researcher_iterations = 3

# Get current date
current_date = datetime.now().strftime("%Y-%m-%d")

# 组合编排指令（仅限子代理的 RESEARCHER_INSTRUCTIONS）
INSTRUCTIONS = (
        AGENT_WORKFLOW_INSTRUCTIONS.format(date=current_date)
        + "\n\n"
        + "=" * 80
        + "\n\n"
        + SUBAGENT_DELEGATION_INSTRUCTIONS.format(
        max_concurrent_research_units=max_concurrent_research_units,
        max_researcher_iterations=max_researcher_iterations,
    )
)

# Model Claude 4.5
chat_model = init_chat_model(
    model=os.getenv('MODEL_MODEL_ID'),
    model_provider=os.getenv('MODEL_PROVIDER'),
    base_url=os.getenv('MODEL_BASE_URL'),
    api_key=os.getenv('MODEL_API_KEY'),
    temperature=0.0)


# 定义一个工厂函数
def get_backend_per_thread(runtime: ToolRuntime):
    """
    根据当前对话的 thread_id 创建一个 FilesystemBackend 实例。
    
    这个函数处理以下情况：
    1. runtime 可能是 ToolRuntime 或 Runtime 类型
    2. config 可能为空或不包含 configurable
    3. thread_id 可能为 None 或包含非法字符
    4. 路径可能无法解析

    Args:
        runtime: LangGraph 的 Runtime 对象（ToolRuntime 或 Runtime）

    Returns:
        FilesystemBackend 实例，配置了独立的沙箱路径
    """
    # 1. 从配置中获取当前对话的 thread_id
    # 使用 .get() 方法避免 KeyError
    if hasattr(runtime, 'config'):
        config = runtime.config
    else:
        config = {}
    thread_id = config.get('configurable', {}).get('thread_id')

    # 如果没有 thread_id，使用默认值防止路径异常
    if thread_id is None:
        thread_id = "default"

    # 2. 动态构造该用户专属的目录
    # 结果示例：./data/sandbox_sessions/thread_abc/
    user_root_dir = f"./data/sandbox_sessions/{thread_id}"

    # 3. 创建新的 Backend 实例并缓存
    # 注意：不预先转换为绝对路径，让 FilesystemBackend.__init__ 处理
    backend = AsyncFilesystemBackend(
        root_dir=user_root_dir,
        virtual_mode=True,
        max_file_size_mb=50,
        thread_id=thread_id,
    )
    return backend

# thread_id 内工具限制中间件
tool_limiter = ToolCallLimitMiddleware(
    run_limit=50,
    exit_behavior="continue"  # 达到 30 次后，强制终止并返回当前结果
)

# 创建自定义工具限制中间件
def cus_tool_limiter(tool_name: str, run_limit:int) -> ToolCallLimitMiddleware:
    return ToolCallLimitMiddleware(
        tool_name=tool_name,
        run_limit=run_limit,
        exit_behavior="continue"  # 强制终止并返回当前结果
    )

upload_files = AttachmentExtractMiddleware(backend_factory= get_backend_per_thread)

# 创建路径解析中间件
path_resolver = ToolPathResolverMiddleware(
    backend_factory=get_backend_per_thread,
    tools_to_resolve=['convert_pdf_to_markdown', 'convert_docx_to_markdown']
)

# 创建研究子代理
sub_agent = SubAgent(
    name= "子智能体",
    description = "将研究委托给子代理研究员，每次仅限一个主题。",
    system_prompt = SUBAGENT_INSTRUCTIONS.format(date=current_date),
    tools = [think_tool, fetch_markdown],
    middleware=[
        path_resolver,
        tool_limiter
    ],  # 完整的中间件配置
)

# Create the agent
# 每个对话会获得独立的沙箱路径（./data/sandbox_sessions/{thread_id}/）
agent = create_deep_agent(
    name="协调者",
    model=chat_model,  # 使用模型实例
    tools=[think_tool, fetch_markdown, convert_pdf_to_markdown, convert_docx_to_markdown],
    backend=get_backend_per_thread,
    system_prompt=INSTRUCTIONS,
    subagents=[sub_agent],
    middleware=[
        upload_files,
        path_resolver,
        tool_limiter,
        cus_tool_limiter('glob', 5)
    ],  # 完整的中间件配置
    debug=int(os.getenv('ENABLED_AGENT_DEBUG', 0)) == 1,
)