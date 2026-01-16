from pathlib import Path
from typing import override

from core.converters._pdfplumber_pymupdf import convert_pdf_to_markdown
from core.converters.base import BaseConverter
from deepagents.backends import BackendProtocol


class PDF2Markdown(BaseConverter):

    @override
    def support(self, suffix):
        return suffix.lower() == ".pdf"

    def convert(self, pdf_file: str, output_file: str, work_dir: str) -> str:
        """执行转换"""
        return convert_pdf_to_markdown(pdf_file, output_file)


# --- 使用示例 ---

if __name__ == "__main__":
    # 替换为你的 PDF 文件路径
    pdf_file = "1901180052张卓群毕业论文3.pdf"
    output_file = str(Path(pdf_file).with_suffix(".md"))
    work_dir = "/Users/liuyuhua/PycharmProjects/simple-agents/files"
    converter = PDF2Markdown()
    converter.convert(pdf_file, output_file, work_dir)

    print(f"转换完成！已保存为 {output_file}")
