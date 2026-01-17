"""Research Agent - Standalone script for LangGraph deployment.

This module creates a deep research agent with custom tools and prompts
for conducting web research with strategic thinking and context management.

Supports per-conversation sandbox isolation using BackendFactory.
"""
import logging
import os
from datetime import datetime

from dotenv import load_dotenv

from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph_sdk import Auth

from deepagents import create_deep_agent, SubAgent
from src.core.middleware.attachment_extract import AttachmentExtractMiddleware
from src.core.tools.converts import convert_to_markdown
from src.core.tools.fetch import fetch_markdown
from src.core.tools.think import think_tool
from src.core.utils import get_backend_per_thread
from src.prompts import (
    AGENT_WORKFLOW_INSTRUCTIONS,
    CONVERT_AGENT_INSTRUCTIONS,
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

# thread_id 内工具限制中间件
tool_limiter = ToolCallLimitMiddleware(
    run_limit=50,
    exit_behavior="continue"  # 达到 30 次后，强制终止并返回当前结果
)


# 创建自定义工具限制中间件
def cus_tool_limiter(tool_name: str, run_limit: int) -> ToolCallLimitMiddleware:
    return ToolCallLimitMiddleware(
        tool_name=tool_name,
        run_limit=run_limit,
        exit_behavior="continue"  # 强制终止并返回当前结果
    )


upload_files = AttachmentExtractMiddleware(backend_factory=get_backend_per_thread)

# 创建文件处理子智能体
convert_agent = SubAgent(
    name="文件转换服务",
    description="用于将用户的源文件 PDF, DOCX, XLSX, PPTX, AsciiDoc 文件转换为 Markdown 格式以便研究",
    system_prompt=CONVERT_AGENT_INSTRUCTIONS,
    tools=[convert_to_markdown],
    middleware=[
        tool_limiter
    ],  # 完整的中间件配置
)

# 创建研究子智能体
research_agent = SubAgent(
    name="研究员",
    description="用于研究委托任务的研究员，每次仅限一个主题。",
    system_prompt=SUBAGENT_INSTRUCTIONS.format(date=current_date),
    tools=[think_tool, fetch_markdown],
    middleware=[
        tool_limiter
    ],  # 完整的中间件配置
)

# Create the agent
# 每个对话会获得独立的沙箱路径（./data/sandbox_sessions/{thread_id}/）
agent = create_deep_agent(
    name="协调者",
    model=chat_model,  # 使用模型实例
    tools=[think_tool, fetch_markdown],
    backend=get_backend_per_thread,
    system_prompt=INSTRUCTIONS,
    subagents=[convert_agent, research_agent],
    middleware=[
        upload_files,
        tool_limiter,
        cus_tool_limiter('glob', 5),
    ],  # 完整的中间件配置
    debug=int(os.getenv('ENABLED_AGENT_DEBUG', 0)) == 1,
)

agent.with_config(
    config=RunnableConfig(
        configurable={
            "tool_timeout": 300.0
        },
        recursion_limit=500,
    )
)

auth = Auth()


def is_valid_key(api_key: bytes) -> bool:
    # Implement your own key validation logic here
    # For example, you can check if the key exists in a database or a file
    return api_key == os.getenv('LANGGRAPH_API_KEY')


@auth.authenticate
async def authenticate(headers: dict) -> Auth.types.MinimalUserDict:
    # Validate credentials (e.g., API key, JWT token)
    api_key = headers.get(b"x-api-key")
    logging.info(f"API key: {api_key}")
    if not api_key or not is_valid_key(api_key):
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    # Return user info - only identity and is_authenticated are required
    # Add any additional fields you need for authorization
    return {
        "identity": "operator",  # Required: unique user identifier
        "is_authenticated": True,  # Optional: assumed True by default
        "permissions": ["read", "write"],  # Optional: for permission-based auth
        # You can add more custom fields if you want to implement other auth patterns
        "role": "admin",
        "org_id": "feike"

    }
