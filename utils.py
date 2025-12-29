"""用于在 Jupyter notebooks 中显示消息和提示词的工具函数。"""

import json

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def format_message_content(message):
    """将消息内容转换为可显示的字符串。"""
    parts = []
    tool_calls_processed = False

    # 处理主要内容
    if isinstance(message.content, str):
        parts.append(message.content)
    elif isinstance(message.content, list):
        # 处理复杂内容，如工具调用（Anthropic 格式）
        for item in message.content:
            if item.get("type") == "text":
                parts.append(item["text"])
            elif item.get("type") == "tool_use":
                parts.append(f"\n🔧 Tool Call: {item['name']}")
                parts.append(f"   Args: {json.dumps(item['input'], indent=2)}")
                parts.append(f"   ID: {item.get('id', 'N/A')}")
                tool_calls_processed = True
    else:
        parts.append(str(message.content))

    # 处理附加到消息的工具调用（OpenAI 格式）- 仅当尚未处理时
    if (
        not tool_calls_processed
        and hasattr(message, "tool_calls")
        and message.tool_calls
    ):
        for tool_call in message.tool_calls:
            parts.append(f"\n🔧 Tool Call: {tool_call['name']}")
            parts.append(f"   Args: {json.dumps(tool_call['args'], indent=2)}")
            parts.append(f"   ID: {tool_call['id']}")

    return "\n".join(parts)


def format_messages(messages):
    """使用 Rich 格式化并显示消息列表。"""
    for m in messages:
        msg_type = m.__class__.__name__.replace("Message", "")
        content = format_message_content(m)

        if msg_type == "Human":
            console.print(Panel(content, title="🧑 Human", border_style="blue"))
        elif msg_type == "Ai":
            console.print(Panel(content, title="🤖 Assistant", border_style="green"))
        elif msg_type == "Tool":
            console.print(Panel(content, title="🔧 Tool Output", border_style="yellow"))
        else:
            console.print(Panel(content, title=f"📝 {msg_type}", border_style="white"))


def format_message(messages):
    """format_messages 的别名，用于向后兼容。"""
    return format_messages(messages)


def show_prompt(prompt_text: str, title: str = "Prompt", border_style: str = "blue"):
    """使用丰富的格式和 XML 标签高亮显示提示词。

    Args:
        prompt_text: 要显示的提示词字符串
        title: 面板标题（默认："Prompt"）
        border_style: 边框颜色样式（默认："blue"）
    """
    # 创建提示词的格式化显示
    formatted_text = Text(prompt_text)
    formatted_text.highlight_regex(r"<[^>]+>", style="bold blue")  # 高亮 XML 标签
    formatted_text.highlight_regex(
        r"##[^#\n]+", style="bold magenta"
    )  # 高亮标题
    formatted_text.highlight_regex(
        r"###[^#\n]+", style="bold cyan"
    )  # 高亮子标题

    # 在面板中显示以获得更好的呈现效果
    console.print(
        Panel(
            formatted_text,
            title=f"[bold green]{title}[/bold green]",
            border_style=border_style,
            padding=(1, 2),
        )
    )
