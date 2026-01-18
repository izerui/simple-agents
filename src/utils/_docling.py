"""
基于 Docling 的 PDF 到 Markdown 转换器（优化版）

Docling 是一个先进的文档处理库，支持：
- 先进的 PDF 布局分析
- 自动表格识别和转换
- 图片提取和处理
- OCR 支持
- 多种文档格式支持

性能优化：
- 模型只加载一次（避免重复加载）
- 批量处理支持（复用模型实例）
- 默认禁用高成本功能（图片生成、高缩放）
- 支持并发处理（线程控制）

安装依赖：
    pip install docling

更多信息：
    https://github.com/docling-project/docling
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# 动态安装 docling（运行时安装）
def _ensure_docling_installed():
    """确保 docling 已安装，如果未安装则动态安装"""
    try:
        import docling
        logger.info("docling 已安装")
        return True
    except ImportError:
        logger.info("docling 未安装，开始动态安装...")
        try:
            # 直接使用 pip 安装 docling，使用清华镜像源加速
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'docling>=2.68.0', '-i', 'https://mirrors.aliyun.com/pypi/simple/'])
            
            # 清除导入缓存，使新安装的包生效
            import importlib
            importlib.invalidate_caches()
            
            logger.info("docling 安装成功")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"docling 安装失败: {e}")
            raise ImportError(
                "无法自动安装 docling。请手动安装: pip install docling"
            )

# 确保依赖已安装
_ensure_docling_installed()

# 导入 docling 相关模块
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc import ImageRefMode
from docling.datamodel.document import ConversionStatus

logger = logging.getLogger(__name__)


class DoclingConverter:
    """
    Docling 转换器（优化版）
    
    关键优化：
    1. 模型只加载一次（使用类变量）
    2. 支持批量处理
    3. 线程控制
    4. 及时释放资源
    """
    
    # 类变量：共享转换器实例（避免重复加载模型）
    _converter: Optional[DocumentConverter] = None
    _config_cache: Optional[Dict[str, Any]] = None
    
    @classmethod
    def get_converter(
        cls,
        *,
        ocr_enabled: bool = False,
        ocr_langs: Optional[List[str]] = None,
        do_table_structure: bool = True,
        do_code_enrichment: bool = False,
        do_formula_enrichment: bool = False,
        generate_picture_images: bool = False,
        images_scale: float = 1.0,
        model_path: Optional[str] = None,
        num_threads: Optional[int] = None,
    ) -> DocumentConverter:
        """
        获取或创建共享的 DocumentConverter 实例（模型只加载一次）
        
        Args:
            ocr_enabled: 是否启用 OCR
            ocr_langs: OCR 语言列表
            do_table_structure: 是否启用表格结构识别
            do_code_enrichment: 是否启用代码识别
            do_formula_enrichment: 是否启用公式识别
            generate_picture_images: 是否生成图片
            images_scale: 图片缩放比例
            model_path: 模型路径
            num_threads: CPU 线程数
            
        Returns:
            DocumentConverter 实例
        """
        # 设置线程数
        if num_threads is not None:
            os.environ["OMP_NUM_THREADS"] = str(num_threads)
        
        # 配置缓存键
        current_config = {
            'ocr_enabled': ocr_enabled,
            'ocr_langs': ocr_langs,
            'do_table_structure': do_table_structure,
            'do_code_enrichment': do_code_enrichment,
            'do_formula_enrichment': do_formula_enrichment,
            'generate_picture_images': generate_picture_images,
            'images_scale': images_scale,
            'model_path': model_path,
            'num_threads': num_threads,
        }
        
        # 如果配置变化或转换器不存在，重新创建
        if (cls._converter is None or 
            cls._config_cache != current_config):
            
            logger.info("初始化/重新初始化 DocumentConverter...")
            
            # 配置管道选项
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = ocr_enabled
            pipeline_options.do_table_structure = do_table_structure
            pipeline_options.do_code_enrichment = do_code_enrichment
            pipeline_options.do_formula_enrichment = do_formula_enrichment
            pipeline_options.generate_picture_images = generate_picture_images
            pipeline_options.generate_parsed_pages = False  # 节省内存
            pipeline_options.images_scale = images_scale
            pipeline_options.artifacts_path = model_path
            
            # 设置 OCR 语言
            if ocr_enabled:
                if ocr_langs is None:
                    ocr_langs = ["en"]
                if hasattr(pipeline_options, 'ocr_options'):
                    from docling.datamodel.pipeline_options import EasyOcrOptions
                    pipeline_options.ocr_options = EasyOcrOptions(lang=ocr_langs)
            
            # 创建转换器
            cls._converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
            cls._config_cache = current_config
            
            logger.info("DocumentConverter 初始化完成")
        
        return cls._converter
    
    @classmethod
    def reset_converter(cls):
        """重置转换器（释放模型内存）"""
        cls._converter = None
        cls._config_cache = None
        logger.info("DocumentConverter 已重置")
    
    def __init__(
        self,
        *,
        ocr_enabled: bool = False,
        ocr_langs: Optional[List[str]] = None,
        do_table_structure: bool = True,
        do_code_enrichment: bool = False,
        do_formula_enrichment: bool = False,
        generate_picture_images: bool = False,
        images_scale: float = 1.0,
        model_path: Optional[str] = None,
        num_threads: int = 4,
    ):
        """
        初始化 Docling 转换器
        
        Args:
            ocr_enabled: 是否启用 OCR（默认 False，加快速度）
            ocr_langs: OCR 语言列表，例如 ["en", "zh"]
            do_table_structure: 是否启用表格结构识别（默认 True）
            do_code_enrichment: 是否启用代码识别（默认 False）
            do_formula_enrichment: 是否启用公式识别（默认 False，加快速度）
            generate_picture_images: 是否生成图片（默认 False，加快速度）
            images_scale: 图片缩放比例（默认 1.0，降低内存使用）
            model_path: 模型路径（可选）
            num_threads: CPU 线程数（默认 4）
        """
        self.ocr_enabled = ocr_enabled
        self.ocr_langs = ocr_langs
        self.do_table_structure = do_table_structure
        self.do_code_enrichment = do_code_enrichment
        self.do_formula_enrichment = do_formula_enrichment
        self.generate_picture_images = generate_picture_images
        self.images_scale = images_scale
        self.model_path = model_path
        self.num_threads = num_threads
        
        # 获取共享转换器
        self.converter = self.get_converter(
            ocr_enabled=ocr_enabled,
            ocr_langs=ocr_langs,
            do_table_structure=do_table_structure,
            do_code_enrichment=do_code_enrichment,
            do_formula_enrichment=do_formula_enrichment,
            generate_picture_images=generate_picture_images,
            images_scale=images_scale,
            model_path=model_path,
            num_threads=num_threads,
        )
    
    def convert(
        self,
        working_dir: str,
        source_file: str,
        output_file: Optional[str] = None,
        debug: bool = False,
    ) -> str:
        """
        转换单个文件（线程安全，支持并发调用）
        
        Args:
            working_dir: 工作目录（必填），所有相对路径都基于此目录
            source_file: 源文件路径（相对于 working_dir 的相对路径，或 URL）
            output_file: 输出 Markdown 文件路径（相对于 working_dir 的相对路径）
            debug: 是否开启调试模式
            
        Returns:
            转换后的 Markdown 内容
        """
        try:
            # 将工作目录转换为绝对路径
            working_dir_path = Path(working_dir).resolve()
            
            # 处理源文件路径
            if source_file.startswith(('http://', 'https://')):
                # URL 不需要转换
                source_path = source_file
            else:
                # 将相对路径转换为绝对路径
                source_path = working_dir_path / source_file
                source_path = source_path.resolve()
            
            # 检查文件是否存在（仅对本地文件）
            if isinstance(source_path, Path):
                if not source_path.exists():
                    raise FileNotFoundError(f"文档不存在: {source_path}")
                source_file_for_docling = str(source_path)
            else:
                source_file_for_docling = source_path
            
            # 确定输出路径
            if output_file is None:
                # 如果是 URL，从 URL 中提取文件名
                if source_file.startswith(('http://', 'https://')):
                    from urllib.parse import urlparse
                    parsed = urlparse(source_file)
                    filename = Path(parsed.path).name
                    if not filename.endswith('.pdf'):
                        filename += '.pdf'
                    output_path = working_dir_path / "output" / Path(filename).with_suffix('.md')
                else:
                    output_path = working_dir_path / Path(source_file).with_suffix('.md')
            else:
                # 将输出路径转换为绝对路径
                output_path = working_dir_path / output_file
            
            output_path = output_path.resolve()
            
            # 自动创建父目录
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 确定图片保存目录：images/{output_file的basename}/
            images_dir = working_dir_path / "images" / output_path.stem
            
            if debug:
                print(f"docling - 工作目录: {working_dir_path}")
                print(f"docling - 开始转换: {source_file_for_docling}")
                print(f"docling - OCR: {'启用' if self.ocr_enabled else '禁用'}")
                if self.ocr_enabled:
                    print(f"docling - OCR 语言: {self.ocr_langs}")
                print(f"docling - 表格结构: {'启用' if self.do_table_structure else '禁用'}")
                print(f"docling - 代码富集: {'启用' if self.do_code_enrichment else '禁用'}")
                print(f"docling - 公式富集: {'启用' if self.do_formula_enrichment else '禁用'}")
                print(f"docling - 生成图片: {'启用' if self.generate_picture_images else '禁用'}")
                print(f"docling - 输出文件: {output_path}")
                print(f"docling - 图片目录: {images_dir}")
            
            # 执行转换（使用绝对路径）
            print(f"docling - 正在转换文档...")
            result = self.converter.convert(source_file_for_docling)
            
            # 保存为 Markdown 文件
            print(f"docling - 保存 Markdown 文件到: {output_path.parent}")
            if self.generate_picture_images:
                # 创建图片目录
                # images_dir.mkdir(parents=True, exist_ok=True)
                
                # REFERENCED 模式：图片保存为独立文件
                result.document.save_as_markdown(
                    output_path,
                    image_mode=ImageRefMode.REFERENCED,
                    artifacts_dir=images_dir
                )
            else:
                # PLACEHOLDER 模式：不生成图片
                result.document.save_as_markdown(
                    output_path,
                    image_mode=ImageRefMode.PLACEHOLDER
                )
            
            # 读取生成的 Markdown 内容
            md_text = output_path.read_text(encoding='utf-8')
            
            # 将图片链接从绝对路径替换为相对于工作目录的相对路径
            # 例如：/absolute/path/to/project/images/doc1/image.png -> images/doc1/image.png
            if self.generate_picture_images:
                import re
                working_dir_str = str(working_dir_path)
                # 移除工作目录前缀（确保不匹配部分路径）
                # 使用正向预查确保只匹配完整的工作目录路径
                md_text = re.sub(
                    rf'^{re.escape(working_dir_str)}/',
                    '',
                    md_text,
                    flags=re.MULTILINE
                )
                # 替换 Markdown 图片链接中的绝对路径
                # 格式：![alt](/absolute/path/to/project/images/...)
                md_text = re.sub(
                    rf'!\[([^\]]*)\]\({re.escape(working_dir_str)}/([^\)]+)\)',
                    r'![\1](\2)',
                    md_text
                )
                # 写回文件
                output_path.write_text(md_text, encoding='utf-8')
            
            print(f"docling - 转换完成，共 {len(md_text)} 字符")
            
            # 及时释放资源
            del result
            
        except Exception as e:
            print(f"docling - 转换失败: {str(e)}")
            raise
        
        return md_text
    
    def convert_multiple(
        self,
        working_dir: str,
        file_paths: List[str],
        output_dir: Optional[str] = None,
        continue_on_error: bool = True,
        max_num_pages: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        批量转换多个文件（复用模型，效率高，线程安全）
        
        Args:
            working_dir: 工作目录（必填），所有相对路径都基于此目录
            file_paths: 文件路径列表（相对于 working_dir 的相对路径）
            output_dir: 输出目录（相对于 working_dir 的相对路径）
            continue_on_error: 遇到错误是否继续
            max_num_pages: 每个文档最大页数限制
            
        Returns:
            处理结果统计
        """
        # 将工作目录转换为绝对路径
        working_dir_path = Path(working_dir).resolve()
        
        try:
            results = {
                "total": len(file_paths),
                "success": 0,
                "failed": 0,
                "errors": []
            }
            
            # 处理输出目录
            if output_dir:
                output_path = (working_dir_path / output_dir).resolve()
                output_path.mkdir(parents=True, exist_ok=True)
            else:
                output_path = working_dir_path
            
            # 将所有文件路径转换为绝对路径
            abs_file_paths = []
            for file_path in file_paths:
                if file_path.startswith(('http://', 'https://')):
                    # URL 不需要转换
                    abs_file_paths.append(file_path)
                else:
                    # 将相对路径转换为绝对路径
                    abs_file_paths.append(str((working_dir_path / file_path).resolve()))
            
            logger.info(f"开始批量处理 {len(file_paths)} 个文件...")
            
            # 使用 convert_all 方法批量处理（模型已加载，直接使用）
            import sys
            results_iter = self.converter.convert_all(
                source=abs_file_paths,
                raises_on_error=not continue_on_error,
                max_num_pages=max_num_pages or sys.maxsize,
            )
            
            for result in results_iter:
                file_name = result.input.file.name
                
                if result.status == ConversionStatus.SUCCESS:
                    results["success"] += 1
                    logger.info(f"✓ 已转换: {file_name}")
                        
                    # 导出为 Markdown
                    doc = result.document
                        
                    # 确定输出路径
                    file_stem = Path(file_name).stem
                    out_path = output_path / f"{file_stem}.md"
                        
                    # 确定图片保存目录：images/{output_file的basename}/
                    images_dir = working_dir_path / "images" / file_stem
                        
                    # 保存文件
                    if self.generate_picture_images:
                        # REFERENCED 模式：图片保存为独立文件
                        doc.save_as_markdown(out_path, image_mode=ImageRefMode.REFERENCED, artifacts_dir=images_dir)
                        
                        # 将图片链接从绝对路径替换为相对于工作目录的相对路径
                        # 例如：/absolute/path/to/project/images/doc1/image.png -> images/doc1/image.png
                        import re
                        working_dir_str = str(working_dir_path)
                        # 读取并替换图片链接
                        md_text = out_path.read_text(encoding='utf-8')
                        # 替换 Markdown 图片链接中的绝对路径
                        # 格式：![alt](/absolute/path/to/project/images/...)
                        md_text = re.sub(
                            rf'!\[([^\]]*)\]\({re.escape(working_dir_str)}/([^\)]+)\)',
                            r'![\1](\2)',
                            md_text
                        )
                        out_path.write_text(md_text, encoding='utf-8')
                    else:
                        doc.save_as_markdown(out_path, image_mode=ImageRefMode.PLACEHOLDER)
                    
                    logger.info(f"  已保存: {out_path}")
                        
                    # 及时释放资源
                    del doc
                    del result
                        
                else:
                    results["failed"] += 1
                    error_msg = f"{file_name}: {result.status}"
                    results["errors"].append(error_msg)
                    logger.error(f"✗ 转换失败: {error_msg}")
                    
                    if result.errors:
                        for err in result.errors:
                            logger.error(f"  错误: {err.error_message}")
            
        except Exception as e:
            logger.error(f"批量转换失败: {str(e)}")
            raise
        
        return results
# 快速转换 无图片、无公式
DOCLING_FAST_CONVERTER = DoclingConverter(
    generate_picture_images = False, # 生成图片
    do_formula_enrichment = False, # 是否启用公式识别
)

# 支持图片提取
DOCLING_IMAGE_CONVERTER = DoclingConverter(
    generate_picture_images = True, # 生成图片
    do_formula_enrichment = False, # 是否启用公式识别
    images_scale = 2.0
)

# 支持公式识别
DOCLING_FORMULA_CONVERTER = DoclingConverter(
    generate_picture_images = False, # 生成图片
    do_formula_enrichment = True, # 是否启用公式识别
)

# 同时支持图片提取和公式识别
DOCLING_FULL_CONVERTER = DoclingConverter(
    generate_picture_images = True, # 生成图片
    do_formula_enrichment = True, # 是否启用公式识别
    images_scale = 2.0
)

# --- 使用示例 ---

if __name__ == "__main__":
    import sys
    
    # 替换为你的 PDF 文件路径
    working_dir = "/Users/liuyuhua/PycharmProjects/simple-agents/files"
    pdf_file = "2023070101ZB203.docx"
    output_file = "2023070101ZB203-docling2.md"
    
    try:
        # 示例 3: 启用高级功能（较慢）
        print("\n" + "=" * 60)
        print("示例 3: 启用图片（注意：公式识别已禁用以避免依赖冲突）")
        print("=" * 60)
        result3 = DOCLING_IMAGE_CONVERTER.convert(
            working_dir=working_dir,
            source_file=pdf_file,
            output_file=output_file,
        )
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