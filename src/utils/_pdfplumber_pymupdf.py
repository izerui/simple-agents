from pathlib import Path
from typing import Optional, Dict, List
import os
import re
import pdfplumber
import pymupdf


def _is_bold(char: Dict) -> bool:
    """判断字符是否加粗

    Args:
        char: 字符信息字典

    Returns:
        是否加粗
    """
    if 'fontname' in char:
        name = char['fontname'].lower()
        return 'bold' in name or 'black' in name
    return False


def _get_median_font_size(chars: List[Dict], default_size: int = 12) -> float:
    """获取页面中最常见的字体大小，作为正文基准

    Args:
        chars: 字符列表
        default_size: 默认字体大小

    Returns:
        中位数字体大小
    """
    if not chars:
        return default_size
    sizes = [c['size'] for c in chars]
    # 统计出现频率最高的字体大小
    return max(set(sizes), key=sizes.count)


def _get_all_image_positions(pymupdf_doc) -> Dict[int, List[Dict]]:
    """一次性获取所有页面的图片位置信息

    Args:
        pymupdf_doc: pymupdf 文档对象

    Returns:
        按页码索引的图片位置字典
    """
    all_positions = {}
    try:
        for page_num in range(len(pymupdf_doc)):
            page = pymupdf_doc[page_num]
            image_list = page.get_images(full=True)

            positions = []
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
            all_positions[page_num] = positions
    except Exception as e:
        print(f"  - 获取图片位置时出错: {str(e)}")

    return all_positions


def _extract_and_save_all_images(
    pymupdf_doc,
    all_positions: Dict[int, List[Dict]],
    images_dir: Path,
    pdf_base_name: str
) -> Dict[str, str]:
    """一次性提取并保存所有图片

    Args:
        pymupdf_doc: pymupdf 文档对象
        all_positions: 所有图片位置信息
        images_dir: 图片保存目录
        pdf_base_name: PDF 基础文件名

    Returns:
        占位符到图片路径的映射字典
    """
    placeholder_to_path = {}

    try:
        for page_num, positions in all_positions.items():
            for img in positions:
                base_image = pymupdf_doc.extract_image(img['xref'])
                if not base_image:
                    continue

                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                # 生成图片文件名
                image_filename = f"{pdf_base_name}_page{page_num + 1}_img{img['index']}.{image_ext}"
                image_path = images_dir / image_filename

                # 保存图片
                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)

                # 存储占位符和图片路径的映射
                placeholder = f"__IMAGE_PLACEHOLDER_{img['page']}_{img['index']}__"
                placeholder_to_path[placeholder] = f"images/{image_filename}"
    except Exception as e:
        print(f"  - 批量提取图片时出错: {str(e)}")

    return placeholder_to_path


def _process_page(
    pdfplumber_page,
    image_positions: List[Dict],
    page_num: int,
    base_font_size_threshold: int = 12,
    heading_multiplier: float = 1.2
) -> str:
    """处理单个页面，使用 pdfplumber 提取文本，插入图片占位符

    Args:
        pdfplumber_page: pdfplumber 页面对象
        image_positions: 当前页的图片位置列表
        page_num: 页码
        base_font_size_threshold: 正文字号阈值
        heading_multiplier: 标题字号倍数

    Returns:
        页面的 Markdown 文本
    """
    page_md = ""

    try:
        chars = pdfplumber_page.chars
        if not chars:
            return ""

        lines = pdfplumber_page.extract_text_lines()

        # 确定正文的基准字号
        median_size = _get_median_font_size(chars, base_font_size_threshold)

        # 遍历每一行文本，根据行高插入图片占位符
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
                    current_img_index += 1
                else:
                    break

            # 处理文本行
            first_char = line['chars'][0] if line['chars'] else {}
            font_size = first_char.get('size', median_size)
            is_bold = _is_bold(first_char)

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
            current_img_index += 1

    except Exception as e:
        print(f"  - 处理页面 {page_num} 时出错: {str(e)}")

    return page_md


def _replace_placeholders(content: str, placeholders: Dict[str, str]) -> str:
    """替换所有占位符为实际的图片 Markdown 语法

    Args:
        content: 包含占位符的文本内容
        placeholders: 占位符到路径的映射

    Returns:
        替换后的内容
    """
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


def convert_pdf_to_markdown(
    pdf_file: str,
    output_file: Optional[str] = None,
    debug: bool = False,
    base_font_size_threshold: int = 12,
    heading_multiplier: float = 1.2,
    small_font_size: int = 9
) -> str:
    """执行 PDF 到 Markdown 的转换

    Args:
        pdf_file: PDF 文件路径
        output_file: 输出 Markdown 文件路径，默认为同名 .md 文件
        debug: 是否开启调试模式
        base_font_size_threshold: 小于此值的视为正文
        heading_multiplier: 标题字号至少是正文的几倍
        small_font_size: 页眉页脚字号阈值

    Returns:
        转换后的 Markdown 内容
    """
    # 转换为 Path 对象
    pdf_path = Path(pdf_file)

    # 检查文件是否存在
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文档不存在: {pdf_file}")

    full_text = ""

    # 图片目录
    images_dir = pdf_path.parent / "images"

    # 创建 images 目录（使用 exist_ok=True 避免并发冲突）
    os.makedirs(images_dir, exist_ok=True)

    pdf_base_name = pdf_path.stem

    # 优化：只打开 PDF 文件一次
    print(f"pdf2markdown - 开始打开 PDF 文件...")

    # 使用 pdfplumber 打开 PDF（用于文本提取）
    pdfplumber_doc = pdfplumber.open(pdf_file)
    total_pages = len(pdfplumber_doc.pages)

    # 使用 pymupdf 打开 PDF（用于图片提取）
    pymupdf_doc = pymupdf.open(pdf_file)

    print(f"pdf2markdown - PDF 共 {total_pages} 页，开始提取图片位置...")

    try:
        # 1. 一次性获取所有页面的图片位置
        all_image_positions = _get_all_image_positions(pymupdf_doc)
        print(f"pdf2markdown - 图片位置提取完成，开始批量提取图片...")

        # 2. 一次性提取并保存所有图片
        placeholder_to_path = _extract_and_save_all_images(
            pymupdf_doc, all_image_positions, images_dir, pdf_base_name
        )
        print(f"pdf2markdown - 图片提取完成，共 {len(placeholder_to_path)} 张图片")

        # 3. 处理每一页的文本（复用已打开的 pdfplumber_doc）
        for i in range(total_pages):
            print(f"pdf2markdown - [{pdf_base_name}] 处理第 {i + 1}/{total_pages} 页...")
            page = pdfplumber_doc.pages[i]
            image_positions = all_image_positions.get(i, [])
            page_text = _process_page(
                page, image_positions, i,
                base_font_size_threshold, heading_multiplier
            )
            full_text += page_text + "\n\n"

        # 4. 替换所有占位符
        print(f"pdf2markdown - 替换占位符...")
        full_text = _replace_placeholders(full_text, placeholder_to_path)

    finally:
        # 确保关闭 PDF 文件
        pdfplumber_doc.close()
        pymupdf_doc.close()

    # 确定输出路径
    output_path = Path(output_file) if output_file is not None else pdf_path.with_suffix('.md')

    # 自动创建父目录
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入文件
    print(f"pdf2markdown - 写入输出文件...")
    output_path.write_text(full_text, encoding='utf-8')

    return full_text



# --- 使用示例 ---

if __name__ == "__main__":
    import sys

    # 替换为你的 PDF 文件路径
    pdf_file = "files/20210701012009-王怡入-拉格朗日中值定理在考研数学中的应用.pdf"
    output_file = str(Path(pdf_file).with_suffix(".md"))

    try:
        # 直接调用 convert 函数
        result = convert_pdf_to_markdown(pdf_file)
        print(f"\n转换结果长度: {len(result)} 字符")

    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"转换失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)