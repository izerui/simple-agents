from pathlib import Path
from typing import Optional

import pypandoc

# 自定义最小化 HTML 模板（只提供基础结构，不添加任何默认样式）
MINIMAL_HTML_TEMPLATE = """<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="" xml:lang="">
<head>
  <meta charset="utf-8" />
  <meta name="generator" content="pandoc" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes" />
  $if(title)$<title>$title$</title>$endif$
  $if(highlighting-css)$<style>$highlighting-css$</style>$endif$
</head>
<body>
$for(include-before)$
  $include-before$
$endfor$
$body$
$for(include-after)$
  $include-after$
$endfor$
</body>
</html>
"""


def convert_docx_to_html(
        docx_file: str,
        output_file: Optional[str] = None,
        cworkdir: Optional[str] = None,
        extract_media: bool = True,
        media_dir: Optional[str] = None,
        math_format: str = "raw_tex",
        extra_args: Optional[list[str]] = None,
        standalone: bool = True,  # 改为 True 以输出完整 HTML 文件
        embed_css: bool = True,
        reference_doc: Optional[str] = None,
        track_changes: bool = False,
        highlight_code: bool = True,
        preserve_tabs: bool = True,
        tab_stop: int = 4,
) -> str:
    """使用 pypandoc 将 DOCX 转换为 HTML（高保真格式保留）

    HTML 转换相比 Markdown 具有以下优势：
    - 完整保留字体、颜色、大小等样式信息
    - 保留表格样式（边框、合并单元格、背景色）
    - 保留段落对齐、行距、缩进等排版信息
    - 适合论文格式检查和审核

    Args:
        docx_file: DOCX 文件路径
        output_file: 输出 HTML 文件路径，默认为同名 .html 文件
        extract_media: 是否提取媒体文件（图片等）
        media_dir: 媒体文件提取目录，默认为输出目录下的 media 子目录
        math_format: 数学公式格式，可选值：
            - "raw_tex": 保留原始 LaTeX（推荐）
            - "mathjax": 使用 MathJax 渲染公式
            - "katex": 使用 KaTeX 渲染公式
            - "webtex": 使用 WebTeX 服务渲染公式
            - "gladtex": 将公式转换为图片
        extra_args: 传递给 pandoc 的额外命令行参数
        standalone: 是否输出完整的独立 HTML 文件（包含 <html><head><body>），默认 True，使用最小化模板保留 DOCX 原始样式
        embed_css: 是否嵌入代码高亮 CSS（注意：此参数已弃用，代码高亮样式由 highlight_code 控制）
        reference_doc: 参考文档路径，用于精确控制输出样式
        track_changes: 是否保留 Word 文档的修订标记
        highlight_code: 是否高亮代码块语法
        preserve_tabs: 是否保留制表符
        tab_stop: 制表符宽度（空格数）

    Returns:
        转换后的 HTML 内容字符串

    Raises:
        FileNotFoundError: 当输入文件不存在时
        RuntimeError: 当 pandoc 未安装或转换失败时

    Example:
        >>> # 基本转换（1:1 还原原始样式）
        >>> html = convert_docx_to_html("thesis.docx", "thesis.html")
        >>> # 使用 KaTeX 渲染公式
        >>> html = convert_docx_to_html(
        ...     "thesis.docx",
        ...     math_format="katex",
        ...     highlight_code=True
        ... )
        >>> # 指定参考文档
        >>> html = convert_docx_to_html(
        ...     "thesis.docx",
        ...     reference_doc="template.docx"
        ... )
    """
    # 转换为 Path 对象
    docx_path = Path(docx_file)

    # 确定输出路径
    if output_file is None:
        output_path = docx_path.with_suffix(".html")
    else:
        output_path = Path(output_file)

    # 确定 media 目录
    if media_dir is None:
        media_path = output_path.parent / docx_path.stem
    else:
        media_path = Path(media_dir)

    # 构建 extra_args 列表
    args = []

    # 输入格式：纯 docx，让 pandoc 完全从 DOCX 读取样式
    args.append("--from=docx")

    # 输出格式：html + raw_tex（保留公式）
    to_format = "html"
    if math_format:
        to_format += f"+{math_format}"

    # 添加图片提取参数
    if extract_media:
        # 确保 media 目录存在
        args.append(f"--extract-media=images/{media_path}")

    # 添加 pandoc 选项
    if standalone:
        # 使用自定义最小化模板，不添加 pandoc 默认样式
        # 只保留基本的 HTML 结构
        args.append("--standalone")
        # 将模板写入临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(MINIMAL_HTML_TEMPLATE)
            template_path = f.name
        args.append(f"--template={template_path}")
        # 标记需要清理模板文件
        cleanup_template = True
    else:
        cleanup_template = False

    if highlight_code:
        args.append("--highlight-style=tango")  # 语法高亮样式：tango/pygments/kate/monochrome/zenburn/espresso/haddock

    if preserve_tabs:
        args.append("--preserve-tabs")
        args.append(f"--tab-stop={tab_stop}")

    # 不添加任何 --variable，完全依赖 DOCX 原始样式
    # 不使用 --embed-resources，避免添加默认 CSS
    # 不使用 --toc 或 --section-divs，避免额外结构干扰

    # 修订标记处理
    if track_changes:
        args.append("--track-changes=all")
    else:
        args.append("--track-changes=accept")

    # 参考文档
    if reference_doc:
        ref_doc_path = Path(reference_doc)
        if not ref_doc_path.exists():
            print(f"警告: 参考文档不存在: {reference_doc}")
        else:
            args.append(f"--reference-doc={ref_doc_path}")

    # 添加用户提供的额外参数
    if extra_args:
        args.extend(extra_args)

    try:
        # 执行转换
        html_content = pypandoc.convert_file(
            source_file=str(docx_path),
            to=to_format,
            format="docx",
            outputfile=str(output_path) if output_path else None,
            extra_args=args if args else None,
            cworkdir=cworkdir if cworkdir else None
        )

        return html_content

    except RuntimeError as e:
        if "pandoc is not installed" in str(e):
            raise RuntimeError(
                "pandoc 未安装。请先安装 pandoc：\n"
                "  macOS: brew install pandoc\n"
                "  Ubuntu: sudo apt-get install pandoc\n"
                "  Windows: 从 https://pandoc.org/installing.html 下载安装"
            ) from e
        else:
            raise RuntimeError(f"DOCX 转 HTML 失败: {e}") from e
    except Exception as e:
        raise RuntimeError(f"转换过程中发生错误: {e}") from e
    finally:
        # 清理临时模板文件
        if cleanup_template and 'template_path' in locals() and Path(template_path).exists():
            Path(template_path).unlink()


# --- 使用示例 ---

if __name__ == "__main__":
    import sys

    # 示例：单个文件转换（论文格式检查推荐）
    docx_file = "1901180052张卓群毕业论文.docx"
    output_html = str(Path(docx_file).with_suffix(".html"))
    cworkdir = "/Users/liuyuhua/PycharmProjects/DocsConvert/docx_to_html/files"
    try:
        print("开始转换 DOCX 到 HTML...")

        html_result = convert_docx_to_html(
            docx_file=docx_file,
            output_file=output_html,
            cworkdir=cworkdir,
            extract_media=True,
            math_format="raw_tex",  # 保留原始 LaTeX（灵活）
            embed_css=False,  # 不嵌入样式
            highlight_code=True,  # 代码高亮
            preserve_tabs=True,
            standalone=True,  # 使用 standalone 输出完整 HTML（带最小化模板）
        )

        print(f"✓ HTML 转换成功!")
        print(f"  输出文件: {output_html}")
        print(f"  HTML 长度: {len(html_result)} 字符")
        print(f"  格式保留: 字体、颜色、大小、表格样式、对齐、行距等")
        print(f"  适用于: 论文格式检查和审核")

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
