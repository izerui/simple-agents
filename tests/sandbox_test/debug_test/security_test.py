#!/usr/bin/env python3
"""
安全测试脚本：演示当前沙箱的潜在安全漏洞

本脚本测试当前沙箱允许读取 root_dir 外的文件所带来的安全风险。
"""
import sys
from pathlib import Path
import tempfile
import platform
import os

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.backends.sandbox import SandboxFilesystemBackend

print("=" * 70)
print("安全漏洞演示测试")
print("=" * 70)
print(f"\n操作系统: {platform.system()} {platform.release()}")
print(f"Python 版本: {sys.version}")
print()

# 创建测试实例
backend = SandboxFilesystemBackend(root_dir=str(tempfile.mkdtemp()))

# 漏洞 1: 读取系统文件
print("【漏洞 1】读取系统敏感文件")
print("-" * 70)

system_files_to_test = [
    ("/etc/passwd", "系统用户列表"),
    ("/etc/hosts", "主机文件"),
    ("/etc/os-release", "操作系统信息"),
    ("/etc/hostname", "主机名"),
]

for filepath, description in system_files_to_test:
    print(f"\n尝试读取: {filepath} ({description})")
    if Path(filepath).exists():
        response = backend.execute(f'python -c "with open(\'{filepath}\', \'r\') as f: print(f.read()[:500])"')
        if response.exit_code == 0:
            print("✓ 成功读取！内容如下：")
            print("-" * 50)
            print(response.output)
            print("-" * 50)
        else:
            print(f"✗ 读取失败: {response.output[:200]}")
    else:
        print(f"  文件不存在，跳过")

# 漏洞 2: 读取用户配置文件
print("\n\n【漏洞 2】读取用户敏感配置文件")
print("-" * 70)

home = Path.home()
user_files_to_test = [
    (home / ".ssh" / "id_rsa", "SSH 私钥"),
    (home / ".ssh" / "authorized_keys", "SSH 授权密钥"),
    (home / ".aws" / "credentials", "AWS 凭证"),
    (home / ".netrc", "FTP/CVS 凭证"),
    (home / ".bash_history", "命令历史"),
]

for filepath, description in user_files_to_test:
    print(f"\n尝试读取: {filepath} ({description})")
    if filepath.exists():
        response = backend.execute(f'python -c "with open(\'{filepath}\', \'r\') as f: print(f.read()[:500])"')
        if response.exit_code == 0:
            print("✓ 成功读取！内容如下：")
            print("-" * 50)
            print(response.output)
            print("-" * 50)
        else:
            print(f"✗ 读取失败: {response.output[:200]}")
    else:
        print(f"  文件不存在，跳过")

# 漏洞 3: 读取环境变量
print("\n\n【漏洞 3】读取环境变量泄露敏感信息")
print("-" * 70)

env_vars_to_test = [
    ("HOME", "用户主目录"),
    ("USER", "用户名"),
    ("PATH", "系统路径"),
    ("PWD", "当前工作目录"),
    ("SHELL", "默认 shell"),
]

response = backend.execute('python -c "import os; print(\'HOME=\', os.environ.get(\'HOME\', \'N/A\')); print(\'USER=\', os.environ.get(\'USER\', \'N/A\')); print(\'PATH=\', os.environ.get(\'PATH\', \'N/A\')[:100])"')
if response.exit_code == 0:
    print("✓ 成功读取环境变量：")
    print(response.output)
else:
    print(f"✗ 读取失败: {response.output}")

# 漏洞 4: 列出目录结构
print("\n\n【漏洞 4】扫描系统目录结构")
print("-" * 70)

dirs_to_scan = [
    "/",
    "/etc",
    "/var",
    "/tmp",
    str(home),
]

for dirpath in dirs_to_scan:
    print(f"\n尝试列出目录: {dirpath}")
    response = backend.execute(f'python -c "import os; print(os.listdir(\'{dirpath}\')[:20])"')
    if response.exit_code == 0:
        print("✓ 成功列出目录内容：")
        print(response.output)
    else:
        print(f"✗ 列出失败: {response.output[:200]}")

# 漏洞 5: 读取应用配置
print("\n\n【漏洞 5】读取应用程序配置文件")
print("-" * 70)

app_configs_to_test = [
    ("~/.config", "用户配置目录"),
    ("~/Library/Application Support", "macOS 应用配置"),
]

for config_path, description in app_configs_to_test:
    full_path = Path(config_path).expanduser()
    print(f"\n尝试列出: {full_path} ({description})")
    if full_path.exists():
        response = backend.execute(f'python -c "import os; print(os.listdir(\'{full_path}\')[:20])"')
        if response.exit_code == 0:
            print("✓ 成功列出配置：")
            print(response.output)
        else:
            print(f"✗ 列出失败: {response.output[:200]}")
    else:
        print("  目录不存在，跳过")

# 漏洞 6: 路径遍历攻击
print("\n\n【漏洞 6】路径遍历攻击验证")
print("-" * 70)

# 使用相对路径尝试访问系统文件
traversal_attempts = [
    ("../../etc/passwd", "简单的相对路径"),
    ("../../../../etc/passwd", "更深的相对路径"),
    ("../../../..//etc/passwd", "带有斜杠的相对路径"),
]

for traversal_path, description in traversal_attempts:
    print(f"\n尝试路径遍历: {traversal_path} ({description})")
    response = backend.execute(f'python -c "import os; print(os.path.abspath(os.path.join(\'{tempfile.gettempdir()}\', \'{traversal_path}\')))"')
    if response.exit_code == 0:
        print(f"  解析后的路径: {response.output.strip()}")
        # 尝试读取
        abs_path = response.output.strip()
        if Path(abs_path).exists():
            read_response = backend.execute(f'python -c "with open(\'{abs_path}\', \'r\') as f: print(f.read()[:200])"')
            if read_response.exit_code == 0:
                print("  ✓ 读取成功！存在安全风险")
            else:
                print(f"  ✗ 读取失败: {read_response.output[:100]}")
        else:
            print("  文件不存在")

print("\n" + "=" * 70)
print("安全漏洞测试完成")
print("=" * 70)
print("\n【总结】")
print("当前沙箱设计允许读取 root_dir 外的文件，这可能导致：")
print("  1. 系统敏感信息泄露（/etc/passwd, /etc/hosts 等）")
print("  2. 用户隐私泄露（.ssh, .aws 等配置文件）")
print("  3. 环境变量泄露")
print("  4. 系统架构信息泄露")
print("  5. 应用配置泄露")
print("  6. 路径遍历攻击风险")
print("\n建议：完全禁止 root_dir 外的文件访问，或使用严格的白名单机制。")
print("=" * 70)