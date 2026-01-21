import os
import sys
import subprocess
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# 动态安装 docling（运行时安装）
def ensure_docling_installed():
    """确保 docling 已安装，如果未安装则动态安装"""
    try:
        import docling
        logger.info("docling 已安装")
        return True
    except ImportError:
        logger.info("docling 未安装，开始动态安装...")
        try:
            # uv pip install docling
            # 直接使用 pip 安装 docling，使用清华镜像源加速
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'docling>=2.68.0', '-i',
                                   'https://mirrors.aliyun.com/pypi/simple/'])

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


# 动态下载docling模型
def download_docling_models():
    # 设置环境变量
    default_home = os.path.join(os.path.expanduser("~"), ".cache")
    HF_HOME = os.path.expandvars(
        os.path.expanduser(
            os.getenv(
                "HF_HOME",
                os.path.join(os.getenv("XDG_CACHE_HOME", default_home), "huggingface"),
            )
        )
    )
    default_cache_path = os.path.join(HF_HOME, "hub")
    HF_HUB_CACHE = os.path.expandvars(
        os.path.expanduser(
            os.getenv(
                "HF_HUB_CACHE",
                default_cache_path,
            )
        )
    )
    cache_dir = HF_HUB_CACHE
    endpoint = "https://hf-mirror.com"

    cache_path = Path(cache_dir)

    # 判断该目录下是否有子目录， 如果有就直接返回
    if any(cache_path.iterdir()):
        print("模型已下载，跳过...")
        return

    from huggingface_hub import snapshot_download

    # 要下载的模型仓库
    REPOS = [
        "docling-project/CodeFormulaV2",
        "docling-project/docling-layout-heron",
        "docling-project/docling-models",
        "docling-project/SmolDocling-256M-preview",
    ]

    print("=" * 60)
    print("开始下载模型...")
    print("=" * 60)
    print()

    for repo_id in REPOS:
        print(f"下载: {repo_id}")

        try:
            download_path = snapshot_download(
                repo_id=repo_id,
                endpoint=endpoint,
                cache_dir=cache_dir,
            )

            # 统计文件
            file_count = sum(1 for _ in Path(download_path).rglob("*") if _.is_file())
            total_size = sum(f.stat().st_size for f in Path(download_path).rglob("*") if f.is_file())
            size_mb = total_size / (1024 * 1024)

            print(f"  ✓ 下载完成 ({file_count} 个文件, {size_mb:.1f} MB)")
            print()
        except Exception as e:
            print(f"  ✗ 下载失败: {e}")
            print()

    print("=" * 60)
    print("所有模型下载完成！")
    print("=" * 60)
    print(f"位置: {cache_dir}")
    print()

if __name__ == '__main__':
    download_docling_models()