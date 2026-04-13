"""clients 文件输入单元测试.

这个文件只测输入归一化，不依赖真实后端。
"""

import asyncio

from src.clients import StreamingClient


class TestFileInputNormalizationUnit:
    """文件输入归一化维度.

    关注：
    - URL 是否透传为 file_url
    - 不在 SDK 侧提前下载 URL
    """

    def test_string_url_file_is_passthrough_file_url(self):
        client = StreamingClient()

        file_payload = asyncio.run(
            client._load_file("https://example.com/files/demo.pdf?download=1")
        )

        assert file_payload == {
            "type": "file_url",
            "url": "https://example.com/files/demo.pdf?download=1",
            "metadata": {"filename": "demo.pdf"},
        }
