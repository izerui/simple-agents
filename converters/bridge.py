from pathlib import Path

from converters.base import BaseConverter
from converters.pdf import PDF2Markdown
from deepagents.backends.protocol import FileUploadResponse


class AdapterConverter:
    """
    适配器转换器
    """
    def __init__(self):
        self.adapters: list[BaseConverter] = [PDF2Markdown()]

    def convert(self, file_path: str):
        """
        将模型请求转换为适配器的输入
        """
        source_path = Path(file_path).resolve()
        # 获取后缀名
        suffix = source_path.suffix
        output_path = source_path.with_suffix(".md")

        adapter = next((adapter for adapter in self.adapters if adapter.support(suffix)), None)
        if adapter:
            adapter.convert(file_path, output_path)