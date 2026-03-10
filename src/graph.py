"""Research Agent - Standalone script for LangGraph deployment.

This module creates a deep research agent with custom tools and prompts
for conducting web research with strategic thinking and context management.

Supports per-conversation sandbox isolation using BackendFactory.
"""
import logging
import os

logger = logging.getLogger(__name__)

from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.stores import InMemoryStore
from langgraph_sdk import Auth

from deepagents import create_deep_agent, SubAgent
from src.middleware.attachment_extract import AttachmentExtractMiddleware
from src.middleware.streaming_tool_call_fix import StreamingToolCallFixMiddleware
from src.middleware.generated_files import GeneratedFilesMiddleware
from src.middleware.fix_dangling_tool_messages import FixDanglingToolMessagesMiddleware
from src.middleware.system_prompt import SystemPromptMiddleware
from src.prompts import RESEARCH_AGENT_INSTRUCTIONS, MAIN_AGENT_INSTRUCTIONS
from src.tools.converts import convert_to_markdown
from src.tools.fetch import fetch_url
from src.tools.think import think_tool
from src.utils._library_download import install_pip_if_needed
from src.utils.util import get_backend_per_thread

# Model - 使用环境变量配置
# 支持的 providers: openai, anthropic, qwq, qwen, deepseek 等
# 可通过 configurable_fields 运行时切换模型
chat_model = init_chat_model(
    model=os.getenv('MODEL_MODEL_ID'),
    model_provider=os.getenv('MODEL_PROVIDER'),
    base_url=os.getenv('MODEL_BASE_URL'),
    api_key=os.getenv('MODEL_API_KEY'),
    temperature=0.0,
    streaming=True,  # 必须流式输出
    timeout=300,  # 超时 5 分钟
    max_retries=3,  # 最多重试 3 次
    configurable_fields=("model", "model_provider", "base_url", "api_key"),  # 支持运行时切换
)

# 设置 model profile，作为 MODEL_MAX_TOKENS 映射表之外模型的 fallback
max_input_tokens = int(os.getenv('MODEL_MAX_INPUT_TOKENS', '80000'))
chat_model.profile = {"max_input_tokens": max_input_tokens}  # type: ignore[assignment]

# 创建自定义工具限制中间件
def cus_tool_limiter(tool_name: str, run_limit: int) -> ToolCallLimitMiddleware:
    return ToolCallLimitMiddleware(
        tool_name=tool_name,
        run_limit=run_limit,
        exit_behavior="continue"  # 强制终止并返回当前结果
    )


# skills_copier = SkillsToSandboxMiddleware(backend_factory=get_backend_per_thread)

upload_files = AttachmentExtractMiddleware(backend_factory=get_backend_per_thread)

# thread_id 内工具限制中间件
tool_limiter = ToolCallLimitMiddleware(
    run_limit=500,
    exit_behavior="continue"  # 达到 500 次后，强制终止并返回当前结果
)

# 创建研究子智能体
research_agent = SubAgent(
    name="研究子代理",
    description="用于研究委托任务的研究员，每次仅限一个主题。",
    system_prompt=RESEARCH_AGENT_INSTRUCTIONS,
    tools=[fetch_url],
    middleware=[
        tool_limiter,
        # create_duplicate_call_prevention(get_backend_per_thread),
    ],  # 完整的中间件配置
)

# my_store = InMemoryStore()

# 配置哪些工具需要中断
# 决策类型
# approve: 批准并执行工具调用
# edit: 修改工具参数后执行
# reject: 拒绝执行该工具调用
interrupt_config = {
    # "convert_to_markdown": True,  # 简单模式：默认允许 approve/edit/reject
    # "fetch_markdown": {"allowed_decisions": ["approve", "reject"]},  # 自定义允许的决策
    # "some_tool": False  # False 表示不中断
}

# Create the agent
# 每个对话会获得独立的沙箱路径（./data/sandbox_sessions/{thread_id}/）
agent = create_deep_agent(
    name="主代理",
    model=chat_model,  # 使用模型实例
    tools=[think_tool, fetch_url, convert_to_markdown],
    backend=get_backend_per_thread,
    system_prompt=MAIN_AGENT_INSTRUCTIONS,
    subagents=[research_agent],
    skills=[
        '/skills'
    ],
    interrupt_on=interrupt_config,
    middleware=[
        SystemPromptMiddleware(default_system_prompt=MAIN_AGENT_INSTRUCTIONS),  # 从输入中提取 system message
        upload_files,
        StreamingToolCallFixMiddleware(),  # 修复流式输出工具调用问题，必须放在第一个
        FixDanglingToolMessagesMiddleware(),  # 修复手动停止工具调用后遗留的孤立 ToolMessage
        tool_limiter,
        GeneratedFilesMiddleware(),  # 提取生成的文件路径并发送 custom 事件
        # create_duplicate_call_prevention(get_backend_per_thread),
        cus_tool_limiter('glob', 5),
    ],  # 完整的中间件配置
    debug=int(os.getenv('ENABLED_AGENT_DEBUG', 0)) == 1,
)

# 打印 model profile 确认设置正确
logger.info(f"chat_model.profile = {chat_model.profile}")

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


install_pip_if_needed()
