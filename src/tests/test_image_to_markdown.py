"""测试图片转 Markdown 功能。"""

import base64
import pytest
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage


class TestImageToMarkdown:
    """测试图片转 Markdown 功能的测试套件。"""

    @pytest.fixture
    def image_path(self):
        """获取测试图片的路径。"""
        return Path("/Users/liuyuhua/PycharmProjects/simple-agents/files/ScreenShot_2026-01-20_165056_749.png")

    @pytest.fixture
    def llm(self):
        """创建 ChatOpenAI 实例，配置为使用 GLM-4.6v 模型。"""
        return ChatOpenAI(
            openai_api_base="https://open.bigmodel.cn/api/coding/paas/v4",
            openai_api_key="59165a22c66342c7899bc17a4db39119.emOa7UmRheFdgLDu",
            model="glm-4.6v-flashx",
            max_tokens=8192,
            temperature=0.0,
            timeout=60.0,
        )
        # return ChatOpenAI(
        #     openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        #     openai_api_key="sk-3834e7c3cd41480e9f1c2aea2e8588dc",
        #     model="qwen3-vl-flash",
        #     max_tokens=8192,
        #     temperature=0.0,
        #     timeout=60.0,
        # )


    def test_image_to_markdown_with_streaming(self, llm, image_path):
        """测试流式输出图片解析为 Markdown。"""
        if not image_path.exists():
            pytest.skip(f"测试图片不存在: {image_path}")

        # 读取图片并转换为 base64
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        user_message = """请以结构化的 Markdown 格式描述这张图片的内容。"""

        message = HumanMessage(content=[
            {"type": "text", "text": user_message},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
        ])

        print(f"\n\n{'='*80}")
        print(f"📝 流式输出开始（图片: {image_path.name}）：")
        print(f"{'='*80}")

        # 使用流式输出
        full_content = ""
        for chunk in llm.stream([message]):
            if chunk.content:
                print(chunk.content, end="", flush=True)
                full_content += chunk.content

        print(f"\n{'='*80}")
        print(f"📝 流式输出完成")
        print(f"{'='*80}\n")

        # 验证响应不为空
        assert full_content is not None
        assert len(full_content) > 0