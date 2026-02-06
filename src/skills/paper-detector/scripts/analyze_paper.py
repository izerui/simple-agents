#!/usr/bin/env python3
"""
Paper Detector - 论文相似度和AIGC检测脚本

注意：论文文件应先通过文件转换服务转换为markdown格式后再进行检测分析
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json

# 支持的文件格式（论文应先通过文件转换服务转换为markdown）
SUPPORTED_FORMATS = ['.md', '.txt']


def read_document(file_path: str) -> Dict:
    """
    读取已转换为markdown的论文内容，提取文本和基本信息

    注意：docx、pdf等格式应先通过文件转换服务转换为markdown格式

    Args:
        file_path: markdown文档路径

    Returns:
        包含文本内容和元数据的字典
    """
    path = Path(file_path)

    if not path.exists():
        return {"error": f"文件不存在: {file_path}"}

    suffix = path.suffix.lower()

    if suffix in ['.md', '.txt']:
        return _read_markdown(path)
    else:
        return {"error": f"不支持的文件格式: {suffix}。请先使用文件转换服务将论文转换为markdown格式。"}


def _read_markdown(path: Path) -> Dict:
    """读取markdown文件（由文件转换服务生成）"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        return {
            "content": content,
            "word_count": len(content),
            "format": "markdown"
        }
    except Exception as e:
        return {"error": f"读取文件失败: {str(e)}"}


def extract_sections(content: str) -> Dict[str, str]:
    """
    从论文内容中提取主要章节

    Args:
        content: 论文全文

    Returns:
        章节字典
    """
    sections = {}

    # 常见章节标题模式
    section_patterns = [
        r'摘\s*要',
        r'关\s*键\s*词',
        r'Abstract',
        r'引\s*言',
        r'绪\s*论',
        r'文\s*献\s*综\s*述',
        r'研\s*究\s*方\s*法',
        r'实\s*验\s*设\s*计',
        r'结\s*果\s*与\s*讨\s*论',
        r'结\s*论',
        r'参\s*考\s*文\s*献',
        r'致\s*谢'
    ]

    lines = content.split('\n')
    current_section = "正文"
    current_content = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检查是否是章节标题
        is_section = False
        for pattern in section_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                # 保存上一个章节
                if current_content:
                    sections[current_section] = "\n".join(current_content)
                current_section = line
                current_content = []
                is_section = True
                break

        if not is_section:
            current_content.append(line)

    # 保存最后一个章节
    if current_content:
        sections[current_section] = "\n".join(current_content)

    return sections


def segment_text(content: str, max_length: int = 500) -> List[str]:
    """
    将文本分割成段落或片段

    Args:
        content: 文本内容
        max_length: 每段最大长度

    Returns:
        段落列表
    """
    # 先按段落分割
    paragraphs = content.split('\n')

    segments = []
    current_segment = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            if current_segment:
                segments.append(current_segment)
                current_segment = ""
            continue

        if len(current_segment) + len(para) <= max_length:
            current_segment += para + "\n"
        else:
            if current_segment:
                segments.append(current_segment)
            current_segment = para + "\n"

    if current_segment:
        segments.append(current_segment)

    return segments


def detect_citations(content: str) -> Tuple[List[str], str]:
    """
    识别文本中的引用

    Args:
        content: 文本内容

    Returns:
        (引用列表, 去除引用后的文本)
    """
    citations = []
    cleaned_content = content

    # 匹配 [1], [1-2], [1,2,3] 等格式
    citation_pattern = r'\[(\d+([,-]\d+)*)\]'
    matches = re.findall(citation_pattern, content)
    for match in matches:
        citations.append(match[0])

    # 匹配 (作者, 年份) 格式
    author_pattern = r'\(([A-Za-z\u4e00-\u9fa5]+,\s*\d{4})\)'
    author_matches = re.findall(author_pattern, content)
    citations.extend(author_matches)

    # 去除引用标记（简单处理，实际可能更复杂）
    cleaned_content = re.sub(citation_pattern, '', content)
    cleaned_content = re.sub(author_pattern, '', cleaned_content)

    return citations, cleaned_content


def generate_detection_id() -> str:
    """生成检测编号"""
    import datetime
    import random
    now = datetime.datetime.now()
    return f"PD{now.strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"


def print_detection_result(result: Dict):
    """打印检测结果"""
    if "error" in result:
        print(f"错误: {result['error']}")
        return

    print("=" * 60)
    print("论文检测结果")
    print("=" * 60)
    print(f"文件格式: {result.get('format', 'unknown')}")
    print(f"字符数: {result.get('word_count', 0)}")
    if 'title' in result:
        print(f"标题: {result['title']}")
    if 'author' in result and result['author']:
        print(f"作者: {result['author']}")
    print("=" * 60)


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python analyze_paper.py <论文文件路径>")
        sys.exit(1)

    file_path = sys.argv[1]

    result = read_document(file_path)
    print_detection_result(result)

    if "error" not in result:
        # 如果成功读取，可以进一步分析
        content = result.get("content", "")
        sections = extract_sections(content)
        print(f"\n检测到 {len(sections)} 个章节")
        for section_name, section_content in sections.items():
            print(f"  - {section_name}: {len(section_content)} 字符")


if __name__ == "__main__":
    main()
