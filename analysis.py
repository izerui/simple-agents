"""Research Agent - Standalone script for LangGraph deployment.

This module creates a deep research agent with custom tools and prompts
for conducting web research with strategic thinking and context management.

Supports per-conversation sandbox isolation using BackendFactory.
"""
import os
import uuid
from datetime import datetime

from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.chat_models import init_chat_model
# from langchain_google_genai import ChatGoogleGenerativeAI
from deepagents import create_deep_agent, FilesystemMiddleware, SubAgent
from langchain_core.messages import HumanMessage
from sandbox_backend import sandbox_manager  # 导入全局沙箱管理器

from tools import think_tool
from prompts import (
    RESEARCHER_INSTRUCTIONS,
    RESEARCH_WORKFLOW_INSTRUCTIONS,
    SUBAGENT_DELEGATION_INSTRUCTIONS,
)

# Limits
max_concurrent_research_units = 3
max_researcher_iterations = 3

# Get current date
current_date = datetime.now().strftime("%Y-%m-%d")

# Combine orchestrator instructions (RESEARCHER_INSTRUCTIONS only for sub-agents)
INSTRUCTIONS = (
    RESEARCH_WORKFLOW_INSTRUCTIONS
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
    run_limit=3,
    exit_behavior="continue"  # 达到 3 次后，强制终止并返回当前结果
)

# Create research sub-agent
research_sub_agent = SubAgent(
    name= "research-agent",
    description = "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
    system_prompt = RESEARCHER_INSTRUCTIONS.format(date=current_date),
    tools = [think_tool],
    middleware= [limiter]
)

# Model Claude 4.5
model = init_chat_model(model=os.getenv('MODEL_MODEL_ID'), base_url=os.getenv('MODEL_BASE_URL'), api_key=os.getenv('MODEL_API_KEY'), temperature=0.0)

# Create the agent
# 使用 BackendFactory 实现每个对话独立的沙箱路径
# 每个 thread_id 会在调用时自动获得独立的临时目录
agent = create_deep_agent(
    model=model,
    tools=[think_tool],
    system_prompt=INSTRUCTIONS,
    backend=sandbox_manager.create_backend_factory(),  # 使用沙箱工厂函数
    subagents=[research_sub_agent],
)

