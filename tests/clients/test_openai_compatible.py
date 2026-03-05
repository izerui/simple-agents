"""测试: 使用 OpenAI 兼容 API (阿里云 DashScope).

环境变量配置:
    - MODEL_PROVIDER=openai
    - MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
    - MODEL_API_KEY=sk-3834e7c3cd41480e9f1c2aea2e8588dc
    - MODEL_MODEL_ID=qwen3.5-plus
"""

import asyncio
import uuid

from langgraph_sdk.schema import Config

from src.clients import StreamingClient
from src.clients.handlers import SimpleStreamingEventHandlers


async def test_openai_compatible():
    """测试: 使用 OpenAI 兼容 API (DashScope)."""
    host = "http://localhost:2024"
    assistant_id = "research"

    user_message = "你是什么大模型?"

    # OpenAI 兼容 API 配置
    config = Config(
        configurable={
            "model_provider": "openai",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            # "api_key": "sk-xxxxx",
            # "model": "deepseek-v3.2",
            # "model": "glm-4.7",
            # "model": "MiniMax-M2.1",
            "model": "qwen3-max",
            "max_input_tokens": 3000,
        }
    )

    thread_id = str(uuid.uuid4())
    client = StreamingClient(url=host, assistant_id=assistant_id)
    handler = SimpleStreamingEventHandlers()

    print(f"用户输入: {user_message}")
    print(f"线程ID: {thread_id}")
    print("-" * 40)

    async for chunk in client.chat_stream(
            message=user_message,
            config=config,
            thread_id=thread_id,
            metadata={"user_id": "user001", "name": "测试动态模型切换"},
    ):
        await handler.receive_chunk(chunk)

    print("\n" + "=" * 40)
    print("✅ 任务执行完成！")
    print("=" * 40)


if __name__ == "__main__":
    asyncio.run(test_openai_compatible())
