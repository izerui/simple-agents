"""Research Agent - Standalone script for LangGraph deployment.

This module creates a deep research agent with custom tools and prompts
for conducting web research with strategic thinking and context management.

Supports per-conversation sandbox isolation using BackendFactory.
"""
import os
from datetime import datetime

from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent, SubAgent

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
model = init_chat_model(
    model_provider=os.getenv('MODEL_PROVIDER'),
    model=os.getenv('MODEL_MODEL_ID'),
    base_url=os.getenv('MODEL_BASE_URL'),
    api_key=os.getenv('MODEL_API_KEY'),
    temperature=0.0)

# Create the agent
# 每个对话会获得独立的沙箱路径（sandbox_sessions/{thread_id}/）
agent = create_deep_agent(
    model=model,  # 使用模型实例
    tools=[think_tool, fetch_url],
    system_prompt=INSTRUCTIONS,
    subagents=[research_sub_agent],
)

