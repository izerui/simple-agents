"""Research Agent - Standalone script for LangGraph deployment.

This module creates a deep research agent with custom tools and prompts
for conducting web research with strategic thinking and context management.

Supports per-conversation sandbox isolation using BackendFactory.
"""
import logging
import os

from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.stores import InMemoryStore
from langgraph_sdk import Auth

from deepagents import create_deep_agent, SubAgent
from src.middleware.attachment_extract import AttachmentExtractMiddleware
from src.prompts import CONVERT_AGENT_INSTRUCTIONS, RESEARCH_AGENT_INSTRUCTIONS, MAIN_AGENT_INSTRUCTIONS
from src.tools.converts import convert_to_markdown
from src.tools.fetch import fetch_markdown
from src.tools.think import think_tool
from src.utils.util import get_backend_per_thread


# Model Claude 4.5
chat_model = init_chat_model(
    model=os.getenv('MODEL_MODEL_ID'),
    model_provider=os.getenv('MODEL_PROVIDER'),
    base_url=os.getenv('MODEL_BASE_URL'),
    api_key=os.getenv('MODEL_API_KEY'),
    temperature=0.0)


# 创建自定义工具限制中间件
def cus_tool_limiter(tool_name: str, run_limit: int) -> ToolCallLimitMiddleware:
    return ToolCallLimitMiddleware(
        tool_name=tool_name,
        run_limit=run_limit,
        exit_behavior="continue"  # 强制终止并返回当前结果
    )


upload_files = AttachmentExtractMiddleware(backend_factory=get_backend_per_thread)

# thread_id 内工具限制中间件
tool_limiter = ToolCallLimitMiddleware(
    run_limit=50,
    exit_behavior="continue"  # 达到 50 次后，强制终止并返回当前结果
)

# 创建文件处理子智能体
convert_agent = SubAgent(
    name="文件转换子代理",
    description="用于将用户的源文件 PDF, DOCX, XLSX, PPTX, AsciiDoc 文件转换为 Markdown 格式以便研究，每次仅限一个文件。",
    system_prompt=CONVERT_AGENT_INSTRUCTIONS,
    tools=[convert_to_markdown],
    middleware=[
        tool_limiter,
        # create_duplicate_call_prevention(get_backend_per_thread),
    ],  # 完整的中间件配置
)

# 创建研究子智能体
research_agent = SubAgent(
    name="研究子代理",
    description="用于研究委托任务的研究员，每次仅限一个主题。",
    system_prompt=RESEARCH_AGENT_INSTRUCTIONS,
    tools=[fetch_markdown],
    middleware=[
        tool_limiter,
        # create_duplicate_call_prevention(get_backend_per_thread),
    ],  # 完整的中间件配置
)

my_store = InMemoryStore()

# Create the agent
# 每个对话会获得独立的沙箱路径（./data/sandbox_sessions/{thread_id}/）
agent = create_deep_agent(
    name="任务代理",
    model=chat_model,  # 使用模型实例
    tools=[think_tool, fetch_markdown],
    store=my_store,
    backend=get_backend_per_thread,
    system_prompt=MAIN_AGENT_INSTRUCTIONS,
    subagents=[convert_agent, research_agent],
    skills=[
        'skills/xlsx'
    ],
    middleware=[
        upload_files,
        tool_limiter,
        # create_duplicate_call_prevention(get_backend_per_thread),
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
