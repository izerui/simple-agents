from converters.pdf import PDF2Markdown
from deepagents.backends.protocol import FileUploadResponse


class AdapterConverter:
    """
    适配器转换器
    """
    def __init__(self, adapter):
        self.adapter = {
            "pdf": PDF2Markdown()
        }

    def convert(self, file: FileUploadResponse):
        """
        将模型请求转换为适配器的输入
        """
        return self.adapter.convert(model_request)