from pathlib import Path
from typing import override, Optional, Dict, Any, List

from core.converters.base import BaseConverter

# mammoth 需要先安装：pip install mammoth
try:
    import mammoth
    MAMMOTH_AVAILABLE = True
except ImportError:
    MAMMOTH_AVAILABLE = False
    print("警告: mammoth 未安装。请运行: pip install mammoth")

# html2text 需要先安装：pip install html2text
try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False
    print("警告: html2text 未安装。请运行: pip install html2text")


class DOCX2Markdown(BaseConverter):
    """DOCX 转 Markdown 工具类
    基于 mammoth 和 html2text 实现
    mammoth 将 DOCX 转换为 HTML，html2text 将 HTML 转换为 Markdown
    """

    def __init__(self, debug=False):
        """初始化转换器

        Args:
            debug: 是否开启调试模式
        """
        self.debug = debug

        # 默认 mammoth 配置
        self.mammoth_options = {
            "ignore_empty_paragraphs": False,
            "external_file_access": True,
            "ignore_empty_paragraphs": False,
        }

        # 默认 html2text 配置
        self.html2text_options = {
            'body_width': 0,  # 不自动换行
            'ignore_images': False,  # 保留图片
            'ignore_links': False,  # 保留链接
            'ignore_emphasis': False,  # 保留强调
            'code_snippets': False,  # 使用代码块
            'escape_snob': False,  # 不转义特殊字符
            'bypass_tables': False,  # 解析表格
            'google_doc': False,  # 不使用 Google Docs 模式
            'ul_item_mark': '-',  # 无序列表使用 -
            'emphasis_mark': '*',  # 强调使用 *
            'strong_mark': '**',  # 粗体使用 **
        }

        # 存储 mammoth 的转换消息
        self.messages: List[Dict[str, str]] = []

        # 图片计数器
        self._image_counter = 0
        # 当前输出路径（用于确定图片保存目录）
        self._current_output_path = None
        # 是否保存图片
        self._save_images = True

    @override
    def support(self, suffix):
        """检查是否支持该文件类型

        Args:
            suffix: 文件后缀名

        Returns:
            是否支持该文件类型
        """
        return suffix.lower() == ".docx"

    def _check_dependencies(self):
        """检查依赖包是否已安装"""
        if not MAMMOTH_AVAILABLE:
            raise ImportError("mammoth 未安装。请运行: pip install mammoth")

        if not HTML2TEXT_AVAILABLE:
            raise ImportError("html2text 未安装。请运行: pip install html2text")

    def convert_image(self, image):
        """处理图片并保存到 images 目录"""
        try:
            # 检查输出路径是否已设置
            if self._current_output_path is None:
                return {}
            # 使用 image.open() 获取文件对象
            with image.open() as image_file:
                content_type = image.content_type  # 获取 MIME 类型 (e.g., image/png)
                
                # 根据 content_type 获取扩展名
                ext = content_type.split('/')[-1]
                if ext == 'jpeg':
                    ext = 'jpg'  # 修正常见类型
                
                # 使用计数器生成文件名
                self._image_counter += 1
                filename = f"image_{self._image_counter}.{ext}"
                
                # 创建 images 目录（相对于输出目录）
                images_dir = self._current_output_path.parent / "images"
                images_dir.mkdir(parents=True, exist_ok=True)
                
                # 保存图片文件
                image_path = images_dir / filename
                with open(image_path, 'wb') as f:
                    f.write(image_file.read())
            
            # 返回相对路径，用于生成 HTML img 标签
            return {
                "src": f"images/{filename}"
            }
        except Exception as e:
            # 返回空字典，告诉 mammoth 不生成图片标签
            return {
                "src": "images/unknow-file.jpg"
            }





    def _convert_docx_to_html(self, docx_path: Path) -> str:
        """使用 mammoth 将 DOCX 转换为 HTML

        Args:
            docx_path: DOCX 文件路径

        Returns:
            HTML 内容字符串
        """
        try:
            with open(docx_path, "rb") as docx_file:
                # 如果需要保存图片，则传入图片处理器
                if self._save_images:
                    options = self.mammoth_options.copy()
                    options['convert_image'] = mammoth.images.img_element(self.convert_image)
                else:
                    options = self.mammoth_options
                
                html_result = mammoth.convert_to_html(docx_file, **options)
                html_content = html_result.value

                # 存储转换消息
                self.messages = [
                    {
                        "type": msg.type,
                        "message": msg.message
                    }
                    for msg in html_result.messages
                ]

                return html_content
        except Exception as e:
            raise Exception(f"DOCX 转 HTML 失败: {e}")

    def _convert_html_to_markdown(self, html_content: str) -> str:
        """使用 html2text 将 HTML 转换为 Markdown

        Args:
            html_content: HTML 内容字符串

        Returns:
            Markdown 内容字符串
        """
        try:
            # 创建 html2text 转换器
            h = html2text.HTML2Text()

            # 设置选项
            for key, value in self.html2text_options.items():
                setattr(h, key, value)

            # 转换 HTML 到 Markdown
            markdown_content = h.handle(html_content)

            return markdown_content
        except Exception as e:
            raise Exception(f"HTML 转 Markdown 失败: {e}")



    def set_style_map(self, style_map: str):
        """设置 mammoth 自定义样式映射

        Args:
            style_map: 样式映射字符串
        """
        self.mammoth_options["style_map"] = style_map

    def set_html2text_options(self, options: Dict[str, Any]):
        """设置 html2text 转换选项

        Args:
            options: html2text 选项字典
        """
        self.html2text_options.update(options)

    def convert(self, docx_file: str, output_file: str = None) -> str:
        """执行 DOCX 到 Markdown 的转换

        Args:
            docx_file: DOCX 文件路径
            output_file: 输出 Markdown 文件路径，默认为同名 .md 文件

        Returns:
            转换后的 Markdown 内容
        """
        # 检查依赖
        self._check_dependencies()

        # 转换为 Path 对象
        docx_path = Path(docx_file)

        # 检查文件是否存在
        if not docx_path.exists():
            raise FileNotFoundError(f"Word 文档不存在: {docx_path}")

        # 确定输出路径
        if output_file is None:
            output_path = docx_path.with_suffix('.md')
        else:
            output_path = Path(output_file)

        # 保存当前输出路径，用于图片保存
        self._current_output_path = output_path

        # 重置图片计数器
        self._image_counter = 0
        # 启用图片保存
        self._save_images = True

        # 步骤1: DOCX 转 HTML
        html_content = self._convert_docx_to_html(docx_path)

        # 步骤2: HTML 转 Markdown
        markdown_content = self._convert_html_to_markdown(html_content)

        # 自动创建父目录
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # 写入文件
        output_path.write_text(markdown_content, encoding='utf-8')

        return markdown_content


    def convert_to_content(self, docx_file: str) -> tuple[str, List[Dict[str, str]]]:
        """将 DOCX 转换为 Markdown 内容字符串（不写入文件）

        Args:
            docx_file: DOCX 文件路径

        Returns:
            (Markdown 字符串, 消息列表)
        """
        # 检查依赖
        self._check_dependencies()

        # 转换为 Path 对象
        docx_path = Path(docx_file)

        # 检查文件是否存在
        if not docx_path.exists():
            raise FileNotFoundError(f"Word 文档不存在: {docx_path}")

        # 设置临时输出路径（用于图片保存）
        self._current_output_path = docx_path.with_suffix('.md')
        
        # 重置图片计数器
        self._image_counter = 0
        # 启用图片保存
        self._save_images = True

        try:
            # 步骤1: DOCX 转 HTML
            html_content = self._convert_docx_to_html(docx_path)

            # 步骤2: HTML 转 Markdown
            markdown_content = self._convert_html_to_markdown(html_content)

            return markdown_content, self.messages

        except Exception as e:
            raise Exception(f"DOCX 转 Markdown 失败: {e}")

    def extract_all(self, docx_file: str) -> Dict[str, Any]:
        """提取 DOCX 的 HTML 和 Markdown 内容

        Args:
            docx_file: DOCX 文件路径

        Returns:
            包含 HTML、Markdown 和消息的字典
        """
        # 检查依赖
        self._check_dependencies()

        # 转换为 Path 对象
        docx_path = Path(docx_file)

        # 检查文件是否存在
        if not docx_path.exists():
            raise FileNotFoundError(f"Word 文档不存在: {docx_path}")

        # 设置临时输出路径（用于图片保存）
        self._current_output_path = docx_path.with_suffix('.md')
        
        # 重置图片计数器
        self._image_counter = 0
        # 启用图片保存
        self._save_images = True

        try:
            # 步骤1: DOCX 转 HTML
            html_content = self._convert_docx_to_html(docx_path)

            # 步骤2: HTML 转 Markdown
            markdown_content = self._convert_html_to_markdown(html_content)

            return {
                "file": str(docx_path),
                "html": html_content,
                "markdown": markdown_content,
                "html_length": len(html_content),
                "markdown_length": len(markdown_content),
                "messages": self.messages
            }

        except Exception as e:
            raise Exception(f"DOCX 内容提取失败: {e}")


# --- 使用示例 ---

if __name__ == "__main__":
    import sys

    # 替换为你的 DOCX 文件路径
    docx_file = "../../files/1901180052张卓群毕业论文3.docx"
    output_file = str(Path(docx_file).with_suffix(".md"))

    try:
        # 方式1：创建转换器并转换（默认输出到同名 .md 文件）
        converter = DOCX2Markdown(debug=False)
        result = converter.convert(docx_file, output_file)
        print(f"\n转换结果长度: {len(result)} 字符")

        # 方式2：指定输出文件路径
        # output_file = "../files/output.md"
        # converter = DOCX2Markdown()
        # result = converter.convert(docx_file, output_file)

        # 方式3：获取 Markdown 内容字符串（不写入文件）
        # converter = DOCX2Markdown()
        # markdown_content, messages = converter.convert_to_content(docx_file)
        # print(f"内容长度: {len(markdown_content)} 字符")
        # print(f"消息数: {len(messages)}")
        # print("\n--- 前500字符预览 ---")
        # print(markdown_content[:500])

        # 方式4：提取 HTML 和 Markdown
        # converter = DOCX2Markdown()
        # result = converter.extract_all(docx_file)
        # print(f"HTML 长度: {result['html_length']} 字符")
        # print(f"Markdown 长度: {result['markdown_length']} 字符")
        # print("\n--- HTML 预览 ---")
        # print(result['html'][:500])
        # print("\n--- Markdown 预览 ---")
        # print(result['markdown'][:500])

        # 方式5：使用自定义配置
        # converter = DOCX2Markdown()
        # converter.set_style_map("p[style-name='Title'] => h1:fresh")
        # converter.set_html2text_options({
        #     'ignore_images': True,
        #     'body_width': 80
        # })
        # result = converter.convert(docx_file)

    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"转换失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)