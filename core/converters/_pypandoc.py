from pathlib import Path
from typing import Optional, List
import pypandoc


def convert_docx_to_markdown(
    docx_file: str,
    output_file: Optional[str] = None,
    cworkdir: Optional[str] = None,
    extract_media: bool = True,
    media_dir: Optional[str] = None,
    math_format: str = "tex_math_dollars",
    extra_args: Optional[List[str]] = None
) -> str:
    """使用 pypandoc 将 DOCX 直接转换为 Markdown

    支持以下功能：
    - 公式识别：自动将 Word 中的公式转换为 LaTeX 格式
    - 图片提取：自动提取图片并保存到指定目录
    - 基本结构：保留表格、列表、脚注等基本结构
    - 不添加样式：完全依赖 Word 原始样式，不自行添加额外格式

    Args:
        docx_file: DOCX 文件路径
        output_file: 输出 Markdown 文件路径，默认为同名 .md 文件
        extract_media: 是否提取媒体文件（图片等）
        media_dir: 媒体文件提取目录，默认为输出目录下的 media 子目录
        math_format: 公式格式选项，可选值：
            - "tex_math_dollars": 使用 $...$ 行内公式，$$...$$ 块级公式（默认）
            - "tex_math_single_backslash": 使用 \\(...\\) 行内公式，\\[...\\] 块级公式
            - "tex_math_double_backslash": 使用 \\\\...\\\\ 行内公式，\\\\[...\\\\] 块级公式
            - "raw_tex": 保持原始 TeX 格式
            - "mathjax": 使用 MathJax 兼容格式
        cworkdir: pandoc 工作目录，用于指定相对路径的基准目录
        extra_args: 传递给 pandoc 的额外命令行参数

    Returns:
        转换后的 Markdown 内容字符串

    Raises:
        FileNotFoundError: 当输入文件不存在时
        RuntimeError: 当 pandoc 未安装或转换失败时

    Example:
        >>> # 基本转换
        >>> md = convert_docx_to_markdown("input.docx", "output.md")
        >>> # 不提取图片，使用 LaTeX 单斜杠公式格式
        >>> md = convert_docx_to_markdown(
        ...     "input.docx",
        ...     extract_media=False,
        ...     math_format="tex_math_single_backslash"
        ... )
        >>> # 指定图片提取目录
        >>> md = convert_docx_to_markdown(
        ...     "input.docx",
        ...     media_dir="custom_media_dir"
        ... )
        >>> # 论文格式保留模式
        >>> md = convert_docx_to_markdown(
        ...     "thesis.docx",
        ...     wrap_none=True,
        ...     preserve_formatting=True,
        ...     tab_stop=4
        ... )
    """
    # 转换为 Path 对象
    docx_path = Path(docx_file)

    # 确定输出路径
    if output_file is None:
        output_path = docx_path.with_suffix(".md")
    else:
        output_path = Path(output_file)

    # 确定 media 目录
    if media_dir is None:
        media_path = output_path.parent / docx_path.stem
    else:
        media_path = Path(media_dir)

    # 构建 extra_args 列表
    args = []

    # 输入格式：docx
    args.append("--from=docx")
    
    # 输出格式：markdown + 多种扩展
    to_format = "markdown"
    
    # 公式扩展（重要：正确识别 Word 中的公式）
    if math_format:
        to_format += f"+{math_format}"
    
    # 基本结构扩展（不添加样式，只保留结构）
    # 表格格式
    to_format += "+pipe_tables+simple_tables+multiline_tables+grid_tables"
    # 列表格式
    to_format += "+definition_lists+task_lists"
    # 脚注
    to_format += "+footnotes"
    # 下标上标
    to_format += "+subscript+superscript"

    # 添加图片提取参数
    if extract_media:
        # 确保 media 目录存在
        args.append(f"--extract-media=images/{media_path}")

    # 接受所有修订（不保留 Word 修订标记）
    args.append("--track-changes=accept")

    # 添加用户提供的额外参数
    if extra_args:
        args.extend(extra_args)

    try:
        # 执行转换
        markdown_content = pypandoc.convert_file(
            source_file=str(docx_path),
            to=to_format,
            format="docx",
            outputfile=str(output_path) if output_path else None,
            extra_args=args if args else None,
            cworkdir=cworkdir if cworkdir else None
        )

        return markdown_content

    except RuntimeError as e:
        if "pandoc is not installed" in str(e):
            raise RuntimeError(
                "pandoc 未安装。请先安装 pandoc：\n"
                "  macOS: brew install pandoc\n"
                "  Ubuntu: sudo apt-get install pandoc\n"
                "  Windows: 从 https://pandoc.org/installing.html 下载安装"
            ) from e
        else:
            raise RuntimeError(f"DOCX 转 Markdown 失败: {e}") from e
    except Exception as e:
        raise RuntimeError(f"转换过程中发生错误: {e}") from e


# HTML 转换功能已移至 docx_to_html/_pypandoc.py




# --- 使用示例 ---

if __name__ == "__main__":
    import sys

    # 示例1：单个文件转换（论文格式保留模式）
    docx_file = "2023070101ZB203.docx"
    output_file = str(Path(docx_file).with_suffix(".md"))
    cworkdir = "/Users/liuyuhua/PycharmProjects/DocsConvert/docx_to_markdown/files"
    try:
        print("开始转换 DOCX 到 Markdown...")

        # 纯净转换（不添加样式，只保留结构和公式）
        result = convert_docx_to_markdown(
            docx_file=docx_file,
            output_file=output_file,
            cworkdir=cworkdir,
            extract_media=True,
            math_format="tex_math_dollars"
        )

        print(f"✓ 转换成功!")
        print(f"  输出文件: {output_file}")
        print(f"  Markdown 长度: {len(result)} 字符")
        print(f"  功能: 公式识别、图片提取、表格和列表结构保留")
        print(f"  说明: 完全依赖 Word 原始样式，不添加额外格式")
        
        # 提示：如需 HTML 转换（高保真格式），请使用 docx_to_html/_pypandoc.py
        print(f"\n提示: HTML 高保真转换功能已移至 docx_to_html/_pypandoc.py")



    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"转换失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)