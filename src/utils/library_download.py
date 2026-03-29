import os
import sys
import subprocess
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def install_pip_if_needed():
    """确保 pip 可用"""
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', '--version'],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
        print('pip 已安装')
    except subprocess.CalledProcessError:
        print('pip 未安装，正在安装 pip...')
        try:
            # 方法1: 使用 ensurepip
            subprocess.check_call([sys.executable, '-m', 'ensurepip', '--upgrade', '--default-pip'])
        except subprocess.CalledProcessError:
            # 方法2: 下载 get-pip.py
            import urllib.request
            urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', 'get-pip.py')
            subprocess.check_call([sys.executable, 'get-pip.py'])
            os.remove('get-pip.py')

# 动态安装 docling（运行时安装）
def ensure_docling_installed():
    """确保 docling 已安装，如果未安装则动态安装"""

    install_pip_if_needed()

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

if __name__ == '__main__':
    ensure_docling_installed()