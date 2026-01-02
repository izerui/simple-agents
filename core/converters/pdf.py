from pathlib import Path
from typing import override

import pdfplumber
import pymupdf
import os
import re


class PDF2Markdown:
    def __init__(self, debug=False):
        self.debug = debug

        # 配置参数
        self.base_font_size_threshold = 12  # 小于此值的视为正文
        self.heading_multiplier = 1.2  # 标题字号至少是正文的几倍
        self.small_font_size = 9  # 页眉页脚字号阈值

    @override
    def support(self, suffix):
        return suffix == ".pdf"

    def _is_bold(self, char):
        """判断字符是否加粗"""
        # pdfplumber 的字体名称通常包含 "Bold"
        if 'fontname' in char:
            name = char['fontname'].lower()
            return 'bold' in name or 'black' in name
        return False

    def _get_median_font_size(self, chars):
        """获取页面中最常见的字体大小，作为正文基准"""
        if not chars:
            return 12
        sizes = [c['size'] for c in chars]
        # 统计出现频率最高的字体大小
        return max(set(sizes), key=sizes.count)

    def _get_image_positions(self, pdf_file, page_num):
        """使用 pymupdf 获取页面中所有图片的位置信息"""
        positions = []
        try:
            doc = pymupdf.open(pdf_file)
            page = doc[page_num]
            image_list = page.get_images(full=True)

            if image_list:
                for img_index, img in enumerate(image_list, 1):
                    xref = img[0]
                    # 获取图片的实例（位置）信息
                    rects = page.get_image_rects(xref)
                    if rects:
                        rect = rects[0]  # 直接取第一个 Rect 对象
                        # 计算图片中心点的 y 坐标
                        center_y = (rect.y0 + rect.y1) / 2
                        positions.append({
                            'y': center_y,
                            'page': page_num,
                            'index': img_index,
                            'xref': xref
                        })

            # 按 y 坐标排序（从上到下）
            positions.sort(key=lambda x: x['y'])
            doc.close()
        except Exception as e:
            print(f"  - 获取图片位置时出错: {str(e)}")

        return positions

    def _extract_and_save_image(self, pdf_file, images_dir, page_num, img_index, xref):
        """使用 pymupdf 提取并保存单个图片"""
        try:
            doc = pymupdf.open(pdf_file)
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            pdf_base_name = Path(pdf_file).stem

            # 生成图片文件名
            image_filename = f"{pdf_base_name}_page{page_num + 1}_img{img_index}.{image_ext}"
            image_path = os.path.join(images_dir, image_filename)

            # 保存图片
            with open(image_path, "wb") as img_file:
                img_file.write(image_bytes)

            doc.close()
            return f"images/{image_filename}"
        except Exception as e:
            print(f"  - 提取图片时出错: {str(e)}")
            return None

    def process_page(self, pdf_file, images_dir, page_num, placeholders):
        """处理单个页面，使用 pdfplumber 提取文本，使用 pymupdf 确定图片位置"""
        page_md = ""

        # 1. 使用 pdfplumber 提取文本
        try:
            with pdfplumber.open(pdf_file) as pdf:
                page = pdf.pages[page_num]

                chars = page.chars
                if not chars:
                    return ""

                lines = page.extract_text_lines()

                # 确定正文的基准字号
                median_size = self._get_median_font_size(chars)

                # 2. 使用 pymupdf 获取该页面的图片位置
                image_positions = self._get_image_positions(pdf_file, page_num)

                # 创建图片占位符
                placeholder_key = f"__PAGE{page_num}_IMAGES__"
                placeholders[placeholder_key] = image_positions

                # 3. 遍历每一行文本，根据行高插入图片占位符
                current_img_index = 0

                for i, line in enumerate(lines):
                    text = line['text'].strip()
                    if not text:
                        continue

                    # 获取行的顶部 y 坐标
                    line_y = line['top']  # pdfplumber 的 top 坐标

                    # 检查是否需要插入图片占位符
                    while current_img_index < len(image_positions):
                        img = image_positions[current_img_index]
                        # 如果图片的中心点在当前行的下方，插入占位符
                        if img['y'] <= line_y:
                            # 生成占位符
                            placeholder = f"__IMAGE_PLACEHOLDER_{img['page']}_{img['index']}__"
                            page_md += f"\n\n{placeholder}\n\n"

                            # 提取并保存图片
                            img_path = self._extract_and_save_image(pdf_file, images_dir, img['page'], img['index'],
                                                                    img['xref'])
                            if img_path:
                                # 存储占位符和图片路径的映射
                                placeholders[placeholder] = img_path

                            current_img_index += 1
                        else:
                            break

                    # 处理文本行
                    first_char = line['chars'][0] if line['chars'] else {}
                    font_size = first_char.get('size', median_size)
                    is_bold = self._is_bold(first_char)

                    # 识别标题
                    if font_size > median_size * 1.1 and is_bold:
                        level = 3 if font_size < median_size * 1.5 else 2
                        page_md += f"{'#' * level} {text}\n\n"
                    else:
                        # 识别正文
                        if text[-1] in ['。', '！', '？', '…', '"', '”', '.', '?', '!']:
                            page_md += text + "\n\n"
                        elif text[-1] in [',', '，', ';', '；', ':', '：']:
                            page_md += text + " "
                        else:
                            page_md += text + "  \n"

                # 处理页面底部剩余的图片
                while current_img_index < len(image_positions):
                    img = image_positions[current_img_index]
                    placeholder = f"__IMAGE_PLACEHOLDER_{img['page']}_{img['index']}__"
                    page_md += f"\n\n{placeholder}\n\n"

                    img_path = self._extract_and_save_image(pdf_file, images_dir, img['page'], img['index'],
                                                            img['xref'])
                    if img_path:
                        placeholders[placeholder] = img_path

                    current_img_index += 1

        except Exception as e:
            print(f"  - 处理页面时出错: {str(e)}")

        return page_md

    def _replace_placeholders(self, content, placeholders):
        """替换所有占位符为实际的图片 Markdown 语法"""

        # 使用正则表达式替换所有占位符
        def replace_match(match):
            placeholder = match.group(0)
            if placeholder in placeholders:
                img_path = placeholders[placeholder]
                return f"\n\n![图片]({img_path})\n\n"
            return placeholder

        # 匹配 __IMAGE_PLACEHOLDER_PAGE_INDEX__ 格式的占位符
        pattern = r'__IMAGE_PLACEHOLDER_\d+_\d+__'
        return re.sub(pattern, replace_match, content)

    def convert(self, pdf_file: str, output_file: str) -> str:
        """执行转换"""

        # 转换为 Path 对象
        pdf_path = Path(pdf_file)

        # 检查文件是否存在
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文档不存在: {pdf_file}")


        full_text = ""
        
        # 占位符列表，存储待替换的信息（局部变量，避免线程安全问题）
        placeholders = {}

        # 图片目录
        images_dir = Path(pdf_file).parent / "images"

        # 创建 images 目录
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)

        # 先用 pdfplumber 获取总页数
        with pdfplumber.open(pdf_file) as pdf:
            total_pages = len(pdf.pages)

        # 处理每一页
        for i in range(total_pages):
            print(f"pdf2markdown - {i + 1}/{total_pages} 页...")
            page_text = self.process_page(pdf_file, images_dir, i, placeholders)
            full_text += page_text + "\n\n"

        # 替换所有占位符
        full_text = self._replace_placeholders(full_text, placeholders)

        # 确定输出路径
        if output_file is None:
            output_path = pdf_path.with_suffix('.md')
        else:
            output_path = Path(output_file)

        # 自动创建父目录
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # 写入文件
        output_path.write_text(full_text, encoding='utf-8')

        return full_text


# --- 使用示例 ---

if __name__ == "__main__":
    # 替换为你的 PDF 文件路径
    pdf_file = "../../files/论文.pdf"
    output_file = str(Path(pdf_file).with_suffix(".md"))

    converter = PDF2Markdown()
    converter.convert(pdf_file, output_file)

    print(f"转换完成！已保存为 {output_file}")
