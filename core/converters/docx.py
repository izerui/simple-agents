from pathlib import Path
from typing import override

from core.converters._html2text import convert_docx_to_markdown
from core.converters.base import BaseConverter


class DOCX2Markdown(BaseConverter):
    """
    DOCX 转 Markdown 工具类
    """

    @override
    def support(self, suffix):
        """检查是否支持该文件类型

        Args:
            suffix: 文件后缀名

        Returns:
            是否支持该文件类型
        """
        return suffix.lower() == ".docx"

    def convert(self, docx_file: str, output_file: str = None) -> str:
        """执行 DOCX 到 Markdown 的转换

        Args:
            docx_file: DOCX 文件路径
            output_file: 输出 Markdown 文件路径，默认为同名 .md 文件

        Returns:
            转换后的 Markdown 内容
        """
        return convert_docx_to_markdown(docx_file, output_file)


# --- 使用示例 ---

if __name__ == "__main__":
    import sys

    # 替换为你的 DOCX 文件路径
    docx_file = "../../files/3-数列的极限测试.docx"
    output_file = str(Path(docx_file).with_suffix(".md"))

    try:
        # 方式1：创建转换器并转换（默认输出到同名 .md 文件）
        converter = DOCX2Markdown()
        result = converter.convert(docx_file, output_file)
        print(f"\n转换结果长度: {len(result)} 字符")

    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"转换失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
