"""
Deno 路径查找工具

假设 Deno 已通过 uv tool install 安装，只提供查找功能。
"""
import shutil
import subprocess
import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def ensure_deno() -> Path:
    """
    确保 Deno 可用，返回 deno 可执行文件的路径
    
    假设 Deno 已通过 uv tool install deno 安装
    
    Returns:
        Path: deno 可执行文件的路径
        
    Raises:
        RuntimeError: 如果找不到 deno 可执行文件
    """
    logger.info("查找 Deno 可执行文件...")
    
    # 先尝试从 PATH 中找
    deno_in_path = shutil.which('deno')
    if deno_in_path:
        logger.info(f"从 PATH 中找到 Deno: {deno_in_path}")
        return Path(deno_in_path)
    
    # 检查 uv tool install 的常见安装位置
    possible_paths = [
        # uv 默认的 tools 安装位置
        Path.home() / ".local" / "bin" / "deno",
        # 其他可能的位置
        Path.home() / ".cargo" / "bin" / "deno",
        # uv 环境中的 bin 目录
        Path(sys.prefix) / "bin" / "deno",
        Path(sys.executable).parent / "deno",
    ]
    
    for path in possible_paths:
        if path.exists():
            logger.info(f"找到 Deno: {path}")
            return path
    
    # 如果还是找不到，尝试直接运行 deno --version 来触发查找
    try:
        result = subprocess.run(
            ["deno", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.split('\n')[0].split()[-1]
            logger.info(f"Deno 可用 (版本: {version})")
            return Path("deno")
    except Exception as e:
        logger.warning(f"无法运行 deno --version: {e}")
    
    raise RuntimeError(
        "找不到 Deno。请确保已运行: uv tool install deno\n"
        "或者手动安装 Deno: https://deno.land/"
    )


# 提供一个简单的命令行接口
def main():
    """命令行入口函数"""
    try:
        deno_path = ensure_deno()
        print(f"✓ Deno 已就绪: {deno_path}")
        
        # 获取版本
        result = subprocess.run(
            [str(deno_path), "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"  版本: {result.stdout.strip()}")
        sys.exit(0)
    except RuntimeError as e:
        print(f"✗ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()