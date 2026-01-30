from datetime import datetime
from pathlib import Path
from typing import Any

# Limits
max_concurrent_research_units = "3"
max_researcher_iterations = "3"

# Get current date
current_date = datetime.now().strftime("%Y-%m-%d")


def load_prompt_from_file(filename: str, **kwargs: Any) -> str:
    """
    从文件加载提示词内容并执行变量替换
    
    Args:
        filename: 提示词文件名（相对于当前文件所在目录）
        **kwargs: 用于格式化字符串的变量
        
    Returns:
        加载并格式化后的提示词内容
    """
    file_path = Path(__file__).parent / filename
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if kwargs:
        content = content.format(**kwargs)

    return content


# ============ 工具使用规则 ============
COMMON_TOOL_USAGE_RULE = load_prompt_from_file("prompt/common_tool_prompt.md")

# ============ 主协调者提示词 ============
MAIN_AGENT_INSTRUCTIONS = load_prompt_from_file(
    "prompt/main_agent_prompt.md",
    date=current_date,
    max_concurrent_research_units=max_concurrent_research_units,
    max_researcher_iterations=max_researcher_iterations,
    COMMON_TOOL_USAGE_RULE=COMMON_TOOL_USAGE_RULE,
)

# ============ 研究子代理提示词 ============
RESEARCH_AGENT_INSTRUCTIONS = load_prompt_from_file(
    "prompt/research_agent_prompt.md",
    date=current_date,
    COMMON_TOOL_USAGE_RULE=COMMON_TOOL_USAGE_RULE
)

# ============ 文件转换子代理提示词 ============
CONVERT_AGENT_INSTRUCTIONS = load_prompt_from_file("prompt/convert_agent_prompt.md")

# ============ VLLM提示词 ============
VLLM_INSTRUCTIONS = load_prompt_from_file("prompt/vllm_prompt.md")
