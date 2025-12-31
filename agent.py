"""Research Agent - Standalone script for LangGraph deployment.

This module creates a deep research agent with custom tools and prompts
for conducting web research with strategic thinking and context management.

Supports per-conversation sandbox isolation using BackendFactory.
"""
import os
# # === 只有在开发调试时才打开这段代码 ===
# if os.getenv("DEBUG_ENABLE"): # 设置个开关，防止上线后还跑这段
#     try:
#         import pydevd_pycharm
#         pydevd_pycharm.settrace('localhost', port=5678, stdout_to_server=True, stderr_to_server=True)
#     except Exception as e:
#         print(f"Debugger error: {e}")
# # ======================================
from datetime import datetime

from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.chat_models import init_chat_model
from langchain_anthropic import ChatAnthropic

from deepagents import create_deep_agent, SubAgent
from langgraph.prebuilt import ToolRuntime

from deepagents.backends import FilesystemBackend
from deepagents.backends.filesystem_async import AsyncFilesystemBackend
from tools import think_tool, fetch_url
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
        AGENT_WORKFLOW_INSTRUCTIONS
        + "\n\n"
        + "=" * 80
        + "\n\n"
        + SUBAGENT_DELEGATION_INSTRUCTIONS.format(
        max_concurrent_research_units=max_concurrent_research_units,
        max_researcher_iterations=max_researcher_iterations,
    )
)

# 1. 创建限制器：例如单次运行最多允许 5 次工具调用
limiter = ToolCallLimitMiddleware(
    run_limit=50,
    exit_behavior="continue"  # 达到 50 次后，强制终止并返回当前结果
)

# 创建研究子代理
research_sub_agent = SubAgent(
    name= "子代理研究员",
    description = "将研究委托给子代理研究员，每次仅限一个主题。",
    system_prompt = SUBAGENT_INSTRUCTIONS.format(date=current_date),
    tools = [think_tool, fetch_url],
    middleware= [limiter],
)

# Model Claude 4.5
chat_model = init_chat_model(
    model=os.getenv('MODEL_MODEL_ID'),
    model_provider=os.getenv('MODEL_PROVIDER'),
    base_url=os.getenv('MODEL_BASE_URL'),
    api_key=os.getenv('MODEL_API_KEY'),
    temperature=0.0)

# chat_model = ChatAnthropic(
#     model_name=os.getenv('MODEL_MODEL_ID'),
#     base_url=os.getenv('MODEL_BASE_URL'),
#     api_key=os.getenv('MODEL_API_KEY'),
#     max_tokens=20000,
#     temperature=0.0,
# )

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
    # 结果示例：./sandbox_sessions/thread_abc/
    user_root_dir = f"./sandbox_sessions/{thread_id}"

    # 3. 创建新的 Backend 实例并缓存
    # 注意：不预先转换为绝对路径，让 FilesystemBackend.__init__ 处理
    backend = AsyncFilesystemBackend(
        root_dir=user_root_dir,
        virtual_mode=True,
        max_file_size_mb=50,
    )
    return backend

# Create the agent
# 每个对话会获得独立的沙箱路径（sandbox_sessions/{thread_id}/）
agent = create_deep_agent(
    model=chat_model,  # 使用模型实例
    tools=[think_tool, fetch_url],
    backend=get_backend_per_thread,
    system_prompt=INSTRUCTIONS,
    subagents=[research_sub_agent],
)