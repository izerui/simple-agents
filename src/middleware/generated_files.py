"""文件路径提取 Middleware

在 Agent 执行完成后，从消息中提取生成的文件路径，
通过 custom 事件发送给客户端。
"""

import re
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState


class GeneratedFilesMiddleware(AgentMiddleware):
    """提取 Agent 生成的文件路径并通过 custom 事件发送"""

    # 测试模式：设置为 True 则总是发送测试文件
    TEST_MODE = True

    def after_agent(self, state: AgentState, runtime: Any) -> dict | None:
        """在 Agent 执行完成后提取文件路径"""
        messages = state.get("messages", [])
        if not messages:
            return None

        # 测试模式：总是发送测试文件
        if self.TEST_MODE:
            runtime.stream_writer({
                "type": "generated_files",
                "content": [
                    {"path": "deepthink/test_report.md", "type": "test"},
                    {"path": "deepthink/final_report.md", "type": "test"},
                    {"path": "output/summary.json", "type": "test"}
                ]
            })
            return None

        last_message = messages[-1]
        content = last_message.content if hasattr(last_message, 'content') else str(last_message)

        # 提取文件路径
        file_paths = extract_file_paths(content)

        if file_paths:
            # 发送 custom 事件
            runtime.stream_writer({
                "type": "generated_files",
                "content": file_paths
            })

        return None


def extract_file_paths(content: str) -> list[dict]:
    """从内容中提取生成的文件路径"""
    files = []

    # 模式1: "文件已保存到: /path/to/file.md"
    pattern1 = r"文件已保存到[:：]\s*(/[^\s]+)"
    for match in re.finditer(pattern1, content):
        files.append({
            "path": match.group(1),
            "type": "saved"
        })

    # 模式2: "报告路径: deepthink/final_report.md" 或 "报告已保存到 xxx"
    pattern2 = r"(?:报告|文件)(?:已保存到|路径)[:：]\s*([^\s]+\.(?:md|txt|pdf|json|docx))"
    for match in re.finditer(pattern2, content):
        files.append({
            "path": match.group(1),
            "type": "report"
        })

    # 模式3: 路径包含 deepthink/ 或 output/ 等目录
    pattern3 = r"(?:deepthink|output|data)/[^\s]+\.(?:md|txt|pdf|json|docx)"
    for match in re.finditer(pattern3, content):
        files.append({
            "path": match.group(0),
            "type": "auto"
        })

    # 模式4: 提取 write_todos 写入的文件
    # 需要从 structured_response 中获取，这里简化处理

    return files
