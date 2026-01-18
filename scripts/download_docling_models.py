#!/usr/bin/env python3
"""
独立的 Docling 模型下载脚本

支持指定 HuggingFace 镜像地址，用于国内环境加速下载。

使用方法:
    # 下载所有默认模型
    python scripts/download_docling_models.py

    # 指定镜像地址
    python scripts/download_docling_models.py --endpoint https://hf-mirror.com

    # 指定下载目录
    python scripts/download_docling_models.py --output-dir ./models

    # 只下载特定模型
    python scripts/download_docling_models.py --models layout table_structure

    # 显示所有可用模型
    python scripts/download_docling_models.py --list-models
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from huggingface_hub import snapshot_download
from huggingface_hub.utils import disable_progress_bars

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Docling 模型配置
DOCLING_MODELS: Dict[str, Dict] = {
    "layout_model": {
        "repo_id": "docling-project/docling-layout-old",
        "revision": "v1.0.1",
        "folder": "layout-model",
        "description": "文档布局分析模型"
    },
    "table_structure": {
        "repo_id": "docling-project/docling-models",
        "revision": None,
        "folder": "table-structure-model",
        "description": "表格结构识别模型"
    },
    "code_formula": {
        "repo_id": "docling-project/docling-models",
        "revision": None,
        "folder": "code-formula-model",
        "description": "代码和公式识别模型"
    },
    "picture_classifier": {
        "repo_id": "docling-project/docling-models",
        "revision": None,
        "folder": "picture-classifier",
        "description": "图片分类模型"
    },
    "rapidocr_torch": {
        "repo_id": "RapidAI/RapidOCR",
        "revision": None,
        "folder": "rapidocr-torch",
        "description": "RapidOCR PyTorch 版本"
    },
    "rapidocr_onnx": {
        "repo_id": "RapidAI/RapidOCR",
        "revision": None,
        "folder": "rapidocr-onnx",
        "description": "RapidOCR ONNX 版本"
    },
    # 可选的 VLM 模型（默认不下载）
    "granite_docling": {
        "repo_id": "ibm-granite/granite-docling-258M",
        "revision": None,
        "folder": "granite-docling",
        "description": "Granite Docling VLM 模型",
        "optional": True
    },
    "granite_vision": {
        "repo_id": "ibm-granite/granite-vision-3b-8bit",
        "revision": None,
        "folder": "granite-vision",
        "description": "Granite Vision 模型",
        "optional": True
    },
    "smolvlm": {
        "repo_id": "HuggingFaceTB/SmolVLM-Instruct",
        "revision": None,
        "folder": "smolvlm",
        "description": "SmolVLM 模型",
        "optional": True
    },
}


def download_model(
    repo_id: str,
    output_dir: Path,
    endpoint: Optional[str] = None,
    revision: Optional[str] = None,
    force_download: bool = False,
    progress: bool = True,
) -> Path:
    """
    下载单个模型
    
    Args:
        repo_id: HuggingFace 模型 ID
        output_dir: 输出目录
        endpoint: 镜像地址（如 https://hf-mirror.com）
        revision: 模型版本
        force_download: 强制重新下载
        progress: 显示进度条
    
    Returns:
        下载的模型路径
    """
    if not progress:
        disable_progress_bars()
    
    logger.info(f"从 {endpoint or '官方 HuggingFace'} 下载模型: {repo_id}")
    
    download_path = snapshot_download(
        repo_id=repo_id,
        revision=revision,
        local_dir=output_dir,
        endpoint=endpoint,
        force_download=force_download,
    )
    
    logger.info(f"✓ 下载完成: {download_path}")
    return Path(download_path)


def download_docling_models(
    models: List[str],
    output_dir: Path,
    endpoint: Optional[str] = None,
    force_download: bool = False,
    progress: bool = True,
) -> None:
    """
    下载 Docling 模型
    
    Args:
        models: 模型名称列表
        output_dir: 输出目录
        endpoint: 镜像地址
        force_download: 强制重新下载
        progress: 显示进度条
    """
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"下载目录: {output_dir}")
    if endpoint:
        logger.info(f"镜像地址: {endpoint}")
    
    for model_name in models:
        if model_name not in DOCLING_MODELS:
            logger.warning(f"未知模型: {model_name}，跳过")
            continue
        
        model_config = DOCLING_MODELS[model_name]
        model_output_dir = output_dir / model_config["folder"]
        
        try:
            download_model(
                repo_id=model_config["repo_id"],
                output_dir=model_output_dir,
                endpoint=endpoint,
                revision=model_config.get("revision"),
                force_download=force_download,
                progress=progress,
            )
        except Exception as e:
            logger.error(f"下载 {model_name} 失败: {e}")
            raise
    
    logger.info("=" * 60)
    logger.info("所有模型下载完成!")
    logger.info(f"下载位置: {output_dir}")
    logger.info("=" * 60)


def list_models() -> None:
    """列出所有可用的模型"""
    print("\n可用的 Docling 模型:\n")
    print(f"{'模型名称':<25} {'模型 ID':<45} {'描述':<30} {'可选':<6}")
    print("-" * 110)
    
    for model_name, config in DOCLING_MODELS.items():
        optional = "是" if config.get("optional") else "否"
        print(f"{model_name:<25} {config['repo_id']:<45} {config['description']:<30} {optional:<6}")
    
    print("\n默认下载的模型: layout_model, table_structure, code_formula, picture_classifier, rapidocr_torch, rapidocr_onnx")
    print("\n可选模型需要通过 --models 参数明确指定")


def main():
    parser = argparse.ArgumentParser(
        description="下载 Docling 所需的模型",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 下载默认模型（使用国内镜像）
  python download_docling_models.py --endpoint https://hf-mirror.com
  
  # 指定下载目录
  python download_docling_models.py --output-dir ./my_models --endpoint https://hf-mirror.com
  
  # 下载特定模型
  python download_docling_models.py --models layout table_structure --endpoint https://hf-mirror.com
  
  # 下载所有模型（包括可选的）
  python download_docling_models.py --all --endpoint https://hf-mirror.com
  
  # 列出所有可用模型
  python download_docling_models.py --list-models
        """
    )
    
    parser.add_argument(
        "--endpoint",
        type=str,
        default=None,
        help="HuggingFace 镜像地址（如 https://hf-mirror.com），默认使用官方地址"
    )
    
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / ".cache" / "docling" / "models",
        help="模型下载目录（默认: ~/.cache/docling/models）"
    )
    
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(DOCLING_MODELS.keys()),
        help="指定要下载的模型，默认下载核心模型"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="下载所有模型（包括可选的 VLM 模型）"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新下载已存在的模型"
    )
    
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="不显示下载进度条"
    )
    
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="列出所有可用的模型"
    )
    
    args = parser.parse_args()
    
    # 如果只是列出模型
    if args.list_models:
        list_models()
        return
    
    # 确定要下载的模型
    if args.all:
        models_to_download = list(DOCLING_MODELS.keys())
    elif args.models:
        models_to_download = args.models
    else:
        # 默认下载核心模型（排除 optional）
        models_to_download = [
            name for name, config in DOCLING_MODELS.items()
            if not config.get("optional")
        ]
    
    logger.info(f"准备下载 {len(models_to_download)} 个模型")
    for model in models_to_download:
        logger.info(f"  - {model}")
    
    # 下载模型
    try:
        download_docling_models(
            models=models_to_download,
            output_dir=args.output_dir,
            endpoint=args.endpoint,
            force_download=args.force,
            progress=not args.no_progress,
        )
    except KeyboardInterrupt:
        logger.warning("\n下载被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"下载失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()