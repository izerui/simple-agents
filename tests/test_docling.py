import sys
from pathlib import Path

from dotenv import load_dotenv

# 加载环境变量并添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(dotenv_path=project_root / '.env')

# --- 使用示例 ---

if __name__ == "__main__":

    from src.utils._docling import DOCLING_LLM_CONVERTER, DOCLING_FAST_CONVERTER, DOCLING_IMAGE_CONVERTER

    # 替换为你的 PDF 文件路径
    working_dir = "/Users/liuyuhua/PycharmProjects/simple-agents/files"
    pdf_file = "7历年考研真题-向量.pdf"
    output_file = "7历年考研真题-向量-docling.md"

    try:
        # 示例 3: 启用高级功能（较慢）
        print("\n" + "=" * 60)
        print("示例 3: 启用图片")
        print("=" * 60)
        result3 = DOCLING_IMAGE_CONVERTER.convert(
            working_dir=working_dir,
            source_file=pdf_file,
            output_file=output_file,
        )
        print(result3)
        print(f"\n转换结果长度: {len(result3)} 字符")

        # 示例 4: 调试模式
        # print("\n" + "=" * 60)
        # print("示例 4: 调试模式")
        # print("=" * 60)
        # result4 = convert_pdf_to_markdown(
        #     pdf_file,
        #     output_file=output_file,
        #     debug=True,
        # )

    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"转换失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
