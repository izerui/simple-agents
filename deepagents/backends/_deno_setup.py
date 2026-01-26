"""
Deno 自动安装工具

提供 Deno 运行时的自动检测和安装功能，支持 macOS/Linux 系统。
"""
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
import shutil


def check_deno_installed() -> tuple[bool, Optional[str]]:
    """
    检查 Deno 是否已安装
    
    Returns:
        tuple: (是否已安装, 版本号或错误信息)
    """
    try:
        result = subprocess.run(
            ["deno", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # 提取版本信息
            version_line = result.stdout.split('\n')[0]
            version = version_line.split()[-1]
            return True, version
        else:
            return False, f"Deno 命令返回错误: {result.stderr}"
            
    except FileNotFoundError:
        return False, "Deno 未找到"
    except subprocess.TimeoutExpired:
        return False, "Deno 版本检查超时"
    except Exception as e:
        return False, f"检查 Deno 时出错: {str(e)}"


def install_deno(force: bool = False) -> tuple[bool, str]:
    """
    自动安装 Deno
    
    Args:
        force: 是否强制重新安装（即使已安装）
    
    Returns:
        tuple: (是否成功, 结果消息)
    """
    # 检查是否已安装
    if not force:
        installed, info = check_deno_installed()
        if installed:
            print(f"✓ Deno 已安装 (版本: {info})")
            return True, f"Deno 已安装 (版本: {info})"
    
    print("开始安装 Deno...")
    
    # 检测操作系统
    system = os.uname().sysname.lower()
    
    if system not in ['darwin', 'linux']:
        return False, f"不支持的操作系统: {system}。仅支持 macOS 和 Linux。"
    
    # 检查是否有 curl 或 wget
    has_curl = shutil.which('curl') is not None
    has_wget = shutil.which('wget') is not None
    
    if not has_curl and not has_wget:
        return False, "需要 curl 或 wget 来下载 Deno，请先安装其中一个。"
    
    try:
        # 下载并执行安装脚本
        install_url = "https://deno.land/install.sh"
        
        if has_curl:
            download_cmd = ["curl", "-fsSL", install_url]
        else:
            download_cmd = ["wget", "-qO-", install_url]
        
        # 执行安装
        install_process = subprocess.Popen(
            download_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        sh_process = subprocess.Popen(
            ["sh"],
            stdin=install_process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        install_process.stdout.close()
        
        stdout, stderr = sh_process.communicate(timeout=300)  # 5分钟超时
        
        if sh_process.returncode != 0:
            return False, f"安装失败: {stderr}"
        
        # 检查安装后的 Deno
        # Deno 默认安装在 ~/.deno/bin/deno
        deno_bin = Path.home() / ".deno" / "bin" / "deno"
        
        if deno_bin.exists():
            # 检查是否在 PATH 中
            deno_dir = str(deno_bin.parent)
            current_path = os.environ.get('PATH', '')
            
            if deno_dir not in current_path:
                print(f"\n⚠️  注意: Deno 已安装到 {deno_bin}")
                print(f"但该目录不在 PATH 中。请将其添加到 PATH:")
                print(f"  export PATH=\"{deno_dir}:$PATH\"")
                
                # 临时添加到当前进程的 PATH
                os.environ['PATH'] = f"{deno_dir}:{current_path}"
            
            # 验证安装
            installed, version = check_deno_installed()
            if installed:
                print(f"✓ Deno 安装成功! (版本: {version})")
                return True, f"Deno 安装成功 (版本: {version})"
            else:
                return False, f"Deno 文件存在但无法执行: {version}"
        else:
            return False, "安装完成但找不到 deno 可执行文件"
            
    except subprocess.TimeoutExpired:
        return False, "安装超时（超过5分钟），请检查网络连接"
    except Exception as e:
        return False, f"安装过程中出错: {str(e)}"


def ensure_deno() -> Path:
    """
    确保 Deno 已安装，返回 deno 可执行文件的路径
    
    Returns:
        Path: deno 可执行文件的路径
        
    Raises:
        RuntimeError: 如果 Deno 安装失败
    """
    # 先尝试从 PATH 中找
    deno_in_path = shutil.which('deno')
    if deno_in_path:
        return Path(deno_in_path)
    
    # 检查默认安装位置
    deno_default = Path.home() / ".deno" / "bin" / "deno"
    if deno_default.exists():
        return deno_default
    
    # 尝试安装
    success, message = install_deno()
    if not success:
        raise RuntimeError(f"无法安装 Deno: {message}")
    
    # 再次检查
    if deno_default.exists():
        return deno_default
    
    # 最后尝试从 PATH 中找（安装后可能在 PATH 中了）
    deno_in_path = shutil.which('deno')
    if deno_in_path:
        return Path(deno_in_path)
    
    raise RuntimeError("Deno 安装成功但无法找到可执行文件")


# 提供一个简单的命令行接口
def main():
    """命令行入口函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deno 自动安装工具")
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="仅检查 Deno 是否已安装"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制重新安装 Deno"
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="显示当前 Deno 版本"
    )
    
    args = parser.parse_args()
    
    if args.version:
        installed, info = check_deno_installed()
        if installed:
            print(f"Deno 版本: {info}")
            sys.exit(0)
        else:
            print(f"Deno 未安装: {info}")
            sys.exit(1)
    
    if args.check:
        installed, info = check_deno_installed()
        if installed:
            print(f"✓ Deno 已安装 (版本: {info})")
            sys.exit(0)
        else:
            print(f"✗ Deno 未安装: {info}")
            sys.exit(1)
    
    # 默认行为：确保安装
    try:
        deno_path = ensure_deno()
        print(f"\n✓ Deno 已就绪: {deno_path}")
        print(f"  可执行路径: {deno_path}")
        sys.exit(0)
    except RuntimeError as e:
        print(f"\n✗ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()