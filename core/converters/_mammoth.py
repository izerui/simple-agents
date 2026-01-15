from pathlib import Path
from typing import Optional, Dict, Any, List
import time
import random
import mammoth
from lxml import html as lxml_html


def _format_html(html_content: str) -> str:
    """格式化 HTML，添加缩进和换行

    Args:
        html_content: 原始 HTML 内容

    Returns:
        格式化后的 HTML 内容
    """
    try:
        # 使用 lxml.html 解析并格式化
        tree = lxml_html.fromstring(html_content)

        # 格式化输出
        formatted = lxml_html.tostring(
            tree,
            encoding='unicode',
            pretty_print=True,
            method='html'
        )

        # 添加 DOCTYPE
        if not formatted.startswith('<!DOCTYPE'):
            formatted = '<!DOCTYPE html>\n' + formatted

        return formatted
    except Exception:
        # 如果格式化失败，返回原始 HTML
        return html_content


def convert_docx_to_html(
        docx_file: str,
        output_file: str = None,
        format_html: bool = True,
        save_images: bool = True,
        ignore_empty_paragraphs: bool = False,
        external_file_access: bool = True,
        style_map: Optional[str] = None
) -> str:
    """执行 DOCX 到 HTML 的转换

    Args:
        docx_file: DOCX 文件路径
        output_file: 输出 HTML 文件路径，默认为同名 .html 文件
        format_html: 是否格式化 HTML 输出
        save_images: 是否保存图片
        ignore_empty_paragraphs: 是否忽略空段落
        external_file_access: 是否允许外部文件访问
        style_map: mammoth 自定义样式映射字符串

    Returns:
        转换后的 HTML 内容
    """
    # 转换为 Path 对象
    docx_path = Path(docx_file)

    # 检查文件是否存在
    if not docx_path.exists():
        raise FileNotFoundError(f"Word 文档不存在: {docx_path}")

    # 确定输出路径
    output_path = Path(output_file) if output_file is not None else None

    # 定义图片处理函数
    def convert_image(image):
        """处理图片并保存到 images 目录"""
        try:
            # 使用 image.open() 获取文件对象
            with image.open() as image_file:
                content_type = image.content_type  # 获取 MIME 类型 (e.g., image/png)

                # 根据 content_type 获取扩展名
                ext = content_type.split('/')[-1]
                if ext == 'jpeg':
                    ext = 'jpg'  # 修正常见类型

                # 使用时间戳 + 随机数生成唯一文件名，避免重复
                timestamp = int(time.time() * 1000)
                random_num = random.randint(1000, 9999)
                filename = f"image_{timestamp}_{random_num}.{ext}"

                # 创建 images 目录（相对于输出目录 否则就是 docx源文件目录）
                images_dir = (output_path.parent if output_path else docx_path.parent) / "images"
                images_dir.mkdir(parents=True, exist_ok=True)

                # 保存图片文件
                image_path = images_dir / filename
                with open(image_path, 'wb') as f:
                    f.write(image_file.read())

            # 返回相对路径，用于生成 HTML img 标签
            return {
                "src": f"images/{filename}"
            }
        except Exception:
            # 返回空字典，告诉 mammoth 不生成图片标签
            return {
                "src": "images/unknow-file.jpg"
            }

    # 配置 mammoth 选项
    mammoth_options = {
        "ignore_empty_paragraphs": ignore_empty_paragraphs,
        "external_file_access": external_file_access,
    }

    # 设置样式映射
    if style_map:
        mammoth_options["style_map"] = style_map

    # 如果需要保存图片，则传入图片处理器
    if save_images:
        mammoth_options['convert_image'] = mammoth.images.img_element(convert_image)

    # 执行转换
    try:
        with open(docx_path, "rb") as docx_file:
            html_result = mammoth.convert_to_html(docx_file, **mammoth_options)
            html_fragment = html_result.value

            # 存储转换消息
            # messages = [
            #     {
            #         "type": msg.type,
            #         "message": msg.message
            #     }
            #     for msg in html_result.messages
            # ]

            # 将 HTML 片段包装成完整的 HTML 文档，并指定 UTF-8 编码
            html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{docx_path.stem}</title>
</head>
<body>
{html_fragment}
</body>
</html>"""

            # 格式化 HTML
            if format_html:
                html_content = _format_html(html_content)

            # 只有指定了输出文件时才写入
            if output_path is not None:
                # 自动创建父目录
                output_path.parent.mkdir(parents=True, exist_ok=True)
                # 写入文件
                output_path.write_text(html_content, encoding='utf-8')

            return html_content
    except Exception as e:
        raise Exception(f"DOCX 转 HTML 失败: {e}")


# --- 使用示例 ---

if __name__ == "__main__":
    import sys

    # 替换为你的 DOCX 文件路径
    docx_file = "files/1901180052张卓群毕业论文.docx"
    output_file = str(Path(docx_file).with_suffix(".html"))

    try:
        # 直接调用 convert 函数
        result = convert_docx_to_html(docx_file)
        print(f"\n转换结果长度: {len(result)} 字符")

    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"转换失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
