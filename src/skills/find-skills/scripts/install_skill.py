#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skills Installation Script - npx-like Implementation

This script implements npx-like functionality to download and install agent skills
directly via HTTP to your sandbox's /skills/ directory.

Installation Workflow:
1. Download tarball to /tmp/skill_install/
2. Extract in /tmp/skill_install/
3. Install to /skills/ (copy from /tmp/)
4. Cleanup /tmp/ directory

Features:
- Download from npm registry (like npx)
- Download from GitHub repositories
- Download from direct URLs
- NEVER overwrites existing installations
- Supports multiple package formats

Usage:
    python3 /skills/find-skills/scripts/install_skill.py <package_name>
    python3 /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills@vercel-react-best-practices
    python3 /skills/find-skills/scripts/install_skill.py -s "react performance"
    python3 /skills/find-skills/scripts/install_skill.py -l
"""

import argparse
import gzip
import hashlib
import json
import os
import re
import ssl
import sys
import tarfile
import tempfile
import urllib.request
from typing import Optional, Dict, List
from urllib.parse import urlparse
import urllib.error


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")


def print_error(msg: str):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")


def print_header(msg: str):
    print(f"\n{Colors.BOLD}{msg}{Colors.RESET}\n")


# 保存原始的 builtins.open（用于在沙箱中读取源文件）
try:
    _original_builtins_open_for_copy = builtins.open
except:
    _original_builtins_open_for_copy = open


def copytree_with_open(src: str, dst: str) -> bool:
    """
    手动复制目录树，使用 open() 确保被沙箱拦截和重定向

    Args:
        src: 源目录路径
        dst: 目标目录路径

    Returns:
        bool: 是否成功
    """
    try:
        # 确保目标目录存在 - 使用 os.mkdir 会被沙箱处理
        try:
            os.makedirs(dst, exist_ok=True)
        except FileExistsError:
            # 目录已被其他进程创建，忽略错误
            pass
        except OSError as e:
            # 如果创建失败，可能是父目录不存在，尝试创建父目录
            if e.errno == 2:  # No such file or directory
                parent_dir = os.path.dirname(dst)
                if parent_dir and parent_dir != dst:
                    try:
                        os.makedirs(parent_dir, exist_ok=True)
                        os.makedirs(dst, exist_ok=True)
                    except:
                        pass

        # 遍历源目录 - 使用 os.listdir
        for item in os.listdir(src):
            src_item = os.path.join(src, item)
            dst_item = os.path.join(dst, item)

            if os.path.isdir(src_item):
                # 递归复制子目录
                if not copytree_with_open(src_item, dst_item):
                    return False
            else:
                # 复制文件
                # 🔧 关键修复：源文件使用原始 open（读取源，可能在 /tmp/ 等白名单目录）
                # 目标文件使用沙箱 open（会被 safe_open 拦截，写入到沙箱目录）
                try:
                    # 先尝试使用原始 open 读取源文件
                    with _original_builtins_open_for_copy(src_item, 'rb') as f_src:
                        with open(dst_item, 'wb') as f_dst:
                            # 分块复制，避免大文件内存问题
                            while True:
                                chunk = f_src.read(8192)
                                if not chunk:
                                    break
                                f_dst.write(chunk)
                except (FileNotFoundError, PermissionError, OSError):
                    # 如果原始 open 失败，尝试使用被沙箱拦截的 open
                    with open(src_item, 'rb') as f_src:
                        with open(dst_item, 'wb') as f_dst:
                            # 分块复制，避免大文件内存问题
                            while True:
                                chunk = f_src.read(8192)
                                if not chunk:
                                    break
                                f_dst.write(chunk)
        return True
    except Exception as e:
        print_error(f"复制失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def rmtree_with_os(path: str) -> bool:
    """
    手动删除目录树，使用 os 操作确保被沙箱处理

    Args:
        path: 要删除的目录路径

    Returns:
        bool: 是否成功
    """
    try:
        if not os.path.exists(path):
            return True

        # 先删除所有子项
        for item in os.listdir(path):
            item_path = os.path.join(path, item)

            if os.path.isdir(item_path):
                rmtree_with_os(item_path)
            else:
                os.remove(item_path)

        # 最后删除目录本身
        os.rmdir(path)
        return True
    except Exception as e:
        # 忽略错误，清理失败不影响主流程
        return False


class NPXStyleInstaller:
    """
    npx-style package installer

    Implements npx-like download functionality:
    - Downloads from npm registry via HTTP
    - Downloads from GitHub repositories
    - NEVER overwrites existing installations
    """

    def __init__(self, skills_dir: str = "/skills/"):
        """
        初始化安装器

        Args:
            skills_dir: 技能目标目录（默认: /skills/）
        """
        self.skills_dir = skills_dir
        # 使用 /tmp/ 进行下载和解压
        self.temp_dir = "/tmp/skill_install"
        # 临时目录在 /tmp/ 白名单中，不需要创建
        # 如果已存在会被复用，不存在会在下载时自动创建

        # npm registry 配置
        self.npm_registry = "https://registry.npmjs.org"

        # 常用 CDN 镜像加速下载
        self.npm_mirrors = [
            "https://registry.npmjs.org",
            "https://registry.npmmirror.com",  # 中国镜像
        ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 清理临时目录 - 使用 os 操作
        temp_path = "/tmp/skill_install"
        rmtree_with_os(temp_path)

    def _download_file(self, url: str, dest_path: str, timeout: int = 30) -> bool:
        """
        从 URL 下载文件到目标路径

        Args:
            url: 源 URL
            dest_path: 目标文件路径（字符串）
            timeout: 下载超时时间（秒）

        Returns:
            bool: 是否成功
        """
        try:
            print_info(f"Downloading from: {url}")
            # 创建不验证 SSL 的上下文
            ssl_context = ssl._create_unverified_context()

            # 确保目标目录存在
            dest_dir = os.path.dirname(dest_path)
            if dest_dir:
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                except FileExistsError:
                    pass

            with urllib.request.urlopen(url, timeout=timeout, context=ssl_context) as response:
                # 使用 open() 写入，会被沙箱拦截
                with open(dest_path, 'wb') as f:
                    # 分块写入，避免大文件内存问题
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            return True
        except urllib.error.HTTPError as e:
            print_error(f"HTTP Error {e.code}: {e.reason}")
            return False
        except urllib.error.URLError as e:
            print_error(f"URL Error: {e.reason}")
            return False
        except Exception as e:
            print_error(f"Download failed: {e}")
            return False

    def _extract_tarball(self, tarball_path: str, dest_dir: str) -> bool:
        """
        解压 .tgz tarball 到目标目录

        Args:
            tarball_path: tarball 文件路径（字符串）
            dest_dir: 目标目录（字符串）

        Returns:
            bool: 是否成功
        """
        try:
            # 确保目标目录存在
            try:
                os.makedirs(dest_dir, exist_ok=True)
            except FileExistsError:
                pass

            # 使用 tarfile.open() 自动检测压缩格式
            # r:* 模式会自动检测 gzip、bzip2 等格式
            with tarfile.open(tarball_path, 'r:*') as tar:
                tar.extractall(path=dest_dir)

            return True
        except Exception as e:
            print_error(f"Extraction failed: {e}")
            return False

    def _get_npm_package_info(self, package_name: str) -> Optional[Dict]:
        """
        Fetch package metadata from npm registry

        Args:
            package_name: npm package name

        Returns:
            Package metadata dict or None
        """
        # 创建不验证 SSL 的上下文
        ssl_context = ssl._create_unverified_context()

        for registry in self.npm_mirrors:
            try:
                url = f"{registry}/{package_name}"
                print_info(f"Querying registry: {registry}")

                with urllib.request.urlopen(url, timeout=10, context=ssl_context) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    return data
            except Exception as e:
                print_warning(f"Registry {registry} failed: {e}")
                continue

        return None

    def _install_from_npm(self, package_name: str, version: Optional[str] = None) -> bool:
        """
        从 npm registry 下载并安装包

        Args:
            package_name: npm 包名（如 'create-react-app'）
            version: 特定版本（默认: latest）

        Returns:
            bool: 是否成功
        """
        print_header(f"📦 Installing from npm registry: {package_name}")

        # 获取包元数据
        pkg_info = self._get_npm_package_info(package_name)
        if not pkg_info:
            print_error("Package not found in npm registry")
            return False

        # 确定要安装的版本
        if version:
            if version not in pkg_info.get('versions', {}):
                print_error(f"Version {version} not found")
                return False
            dist_tags = {'version': version}
        else:
            dist_tags = pkg_info.get('dist-tags', {})
            version = dist_tags.get('latest', 'latest')

        print_info(f"Version: {version}")

        # 获取 tarball URL 和元数据
        versions_data = pkg_info.get('versions', {})
        version_data = versions_data.get(version, {})
        dist_data = version_data.get('dist', {})
        tarball_url = dist_data.get('tarball')

        if not tarball_url:
            print_error("No tarball URL found in package metadata")
            return False

        # 下载 tarball
        tarball_filename = f"{package_name}-{version}.tgz"
        tarball_path = os.path.join(self.temp_dir, tarball_filename)

        if not self._download_file(tarball_url, tarball_path):
            return False

        # 解压到临时目录
        extract_dir = os.path.join(self.temp_dir, "extracted")
        try:
            os.makedirs(extract_dir, exist_ok=True)
        except FileExistsError:
            pass

        if not self._extract_tarball(tarball_path, extract_dir):
            return False

        # 找到包目录（通常在 'package/' 子目录中）
        extracted_items = os.listdir(extract_dir)
        if len(extracted_items) == 1:
            item_path = os.path.join(extract_dir, extracted_items[0])
            if os.path.isdir(item_path):
                package_source = item_path
            else:
                package_source = extract_dir
        else:
            package_source = extract_dir

        # 确定目标目录名
        skill_name = package_name.replace('/', '-')
        target_dir = os.path.join(self.skills_dir, skill_name)

        # 检查是否已安装（绝不覆盖）
        if os.path.exists(target_dir):
            print_warning(f"Skill already exists: {target_dir}")
            print_warning("Skipping installation (NEVER overwrites existing files)")
            return True

        # 安装到 skills 目录
        try:
            # 确保父目录存在
            parent_dir = os.path.dirname(target_dir)
            try:
                os.makedirs(parent_dir, exist_ok=True)
            except FileExistsError:
                pass

            # 使用自定义的 copytree，通过 open() 被沙箱拦截
            if copytree_with_open(package_source, target_dir):
                print_success(f"Installed to: {target_dir}")
                return True
            return False
        except Exception as e:
            print_error(f"Installation failed: {e}")
            return False

    def _install_from_github(self, repo_spec: str, skill_path: Optional[str] = None) -> bool:
        """
        从 GitHub 仓库下载并安装

        Args:
            repo_spec: 仓库规格（如 'owner/repo' 或 'owner/repo@tag'）
            skill_path: 仓库中技能子目录的路径（如 'skills/my-skill'）

        Returns:
            bool: 是否成功
        """
        print_header(f"📦 Installing from GitHub: {repo_spec}")

        # 解析仓库规格
        # 格式: owner/repo[@tag][/path/to/skill]
        parts = repo_spec.split('@')
        repo = parts[0]

        if '/' not in repo:
            print_error("Invalid GitHub repo format. Use: owner/repo")
            return False

        owner, repo_name = repo.split('/')[:2]

        # 解析 tag/branch
        tag = parts[1] if len(parts) > 1 else 'main'

        # 如果是默认值，尝试 'main' 和 'master'
        if tag in ['main', 'master']:
            tag = 'main'  # 默认使用 main

        # 构建下载 URL
        # GitHub tarball URL: https://github.com/owner/repo/archive/refs/tags/tag.tar.gz
        # 或 branch: https://github.com/owner/repo/archive/refs/heads/branch.tar.gz
        tarball_url = f"https://github.com/{owner}/{repo_name}/archive/refs/tags/{tag}.tar.gz"

        # 如果 tag 不存在，回退到 branch
        fallback_url = f"https://github.com/{owner}/{repo_name}/archive/refs/heads/{tag}.tar.gz"

        tarball_filename = f"{repo_name}-{tag}.tar.gz"
        tarball_path = os.path.join(self.temp_dir, tarball_filename)

        # 尝试下载
        if not self._download_file(tarball_url, tarball_path):
            print_warning("Tag download failed, trying branch...")
            if not self._download_file(fallback_url, tarball_path):
                print_error("Failed to download from GitHub")
                return False

        # 解压
        extract_dir = os.path.join(self.temp_dir, "extracted")
        try:
            os.makedirs(extract_dir, exist_ok=True)
        except FileExistsError:
            pass

        if not self._extract_tarball(tarball_path, extract_dir):
            return False

        # 找到解压后的目录
        extracted_items = os.listdir(extract_dir)
        if not extracted_items:
            print_error("No files extracted")
            return False

        package_source = os.path.join(extract_dir, extracted_items[0])

        # 如果指定了技能子目录，导航到该目录
        if skill_path:
            package_source = os.path.join(package_source, skill_path)
            if not os.path.exists(package_source):
                print_error(f"Skill path not found: {skill_path}")
                return False

        # 确定目标目录
        skill_name = f"{owner}-{repo_name}"
        if skill_path:
            skill_name = skill_path.replace('/', '-')

        target_dir = os.path.join(self.skills_dir, skill_name)

        # 检查是否已安装（绝不覆盖）
        if os.path.exists(target_dir):
            print_warning(f"Skill already exists: {target_dir}")
            print_warning("Skipping installation (NEVER overwrites existing files)")
            return True

        # 安装
        try:
            # 确保父目录存在
            parent_dir = os.path.dirname(target_dir)
            try:
                os.makedirs(parent_dir, exist_ok=True)
            except FileExistsError:
                pass

            # 使用自定义的 copytree，通过 open() 被沙箱拦截
            if copytree_with_open(package_source, target_dir):
                print_success(f"Installed to: {target_dir}")
                return True
            return False
        except Exception as e:
            print_error(f"Installation failed: {e}")
            return False

    def _install_from_url(self, url: str) -> bool:
        """
        从直接 URL 下载并安装

        Args:
            url: tarball 或文件的直接 URL

        Returns:
            bool: 是否成功
        """
        print_header(f"📦 Installing from URL: {url}")

        # 从 URL 确定文件类型
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path) or "downloaded_file"

        download_path = os.path.join(self.temp_dir, filename)

        # 下载
        if not self._download_file(url, download_path):
            return False

        # 解压并安装
        return self._install_from_tarball(download_path, filename)

    def _install_from_local_file(self, file_path: str) -> bool:
        """
        从本地 tarball 文件安装

        Args:
            file_path: 本地 tarball 文件路径

        Returns:
            bool: 是否成功
        """
        print_header(f"📦 Installing from local file: {file_path}")

        # 验证文件存在
        if not os.path.exists(file_path):
            print_error(f"File not found: {file_path}")
            return False

        # 解压并安装
        filename = os.path.basename(file_path)
        return self._install_from_tarball(file_path, filename)

    def _install_from_tarball(self, tarball_path: str, fallback_name: str) -> bool:
        """
        从 tarball 解压并安装

        Args:
            tarball_path: tarball 文件路径
            fallback_name: 技能的备用名称

        Returns:
            bool: 是否成功
        """
        # 如果是 tarball，解压它
        if tarfile.is_tarfile(tarball_path):
            extract_dir = os.path.join(self.temp_dir, "extracted")
            try:
                os.makedirs(extract_dir, exist_ok=True)
            except FileExistsError:
                pass

            print_info(f"Extracting: {os.path.basename(tarball_path)}")
            if not self._extract_tarball(tarball_path, extract_dir):
                return False

            # 找到解压后的目录
            extracted_items = os.listdir(extract_dir)
            if len(extracted_items) == 1:
                package_source = os.path.join(extract_dir, extracted_items[0])
            else:
                package_source = extract_dir
        else:
            print_error(f"Not a tarball file: {tarball_path}")
            return False

        # 确定目标名称 - 使用字符串操作而不是 Path 方法
        filename = os.path.basename(fallback_name)
        # 使用字符串 replace 移除扩展名
        skill_name = filename.replace('.tar.gz', '').replace('.tgz', '').replace('.tar.bz2', '').replace('.tar', '')
        target_dir = os.path.join(self.skills_dir, skill_name)

        # 检查是否已安装
        if os.path.exists(target_dir):
            print_warning(f"Skill already exists: {target_dir}")
            print_warning("Skipping installation (NEVER overwrites existing files)")
            return True

        # 安装
        print_info(f"Installing to: {target_dir}")
        try:
            if copytree_with_open(package_source, target_dir):
                print_success(f"Installed successfully: {target_dir}")
                return True
            return False
        except Exception as e:
            print_error(f"Installation failed: {e}")
            return False

    def install(self, package_spec: str) -> bool:
        """
        从各种来源安装包

        包格式:
        - npm package: 'package-name' 或 'package-name@version'
        - GitHub: 'owner/repo' 或 'owner/repo@tag' 或 'owner/repo@tag/path/to/skill'
        - 直接 URL: 'https://example.com/package.tar.gz'
        - 本地文件: '/path/to/file.tar.gz' 或 'file.tar.gz'

        Args:
            package_spec: 包规格字符串

        Returns:
            bool: 是否成功
        """
        # 确保 skills 目录存在
        try:
            os.makedirs(self.skills_dir, exist_ok=True)
        except FileExistsError:
            pass
        print_info(f"Skills directory: {self.skills_dir}")

        # 检测包类型并相应安装
        # 1. 检查是否是 URL
        if package_spec.startswith('http://') or package_spec.startswith('https://'):
            return self._install_from_url(package_spec)

        # 2. 检查是否是本地文件（存在且以 .tgz 或 .tar.gz 结尾）
        if package_spec.endswith(('.tgz', '.tar.gz', '.tar.bz2', '.tar')):
            return self._install_from_local_file(package_spec)

        # 3. 检查是否是 GitHub repo（包含 /）
        if '/' in package_spec and not package_spec.startswith('@'):
            # 解析格式: owner/repo[@tag][/skill/path]
            parts = package_spec.split('/')
            if len(parts) >= 2:
                repo_part = f"{parts[0]}/{parts[1]}"
                skill_path = '/'.join(parts[2:]) if len(parts) > 2 else None
                return self._install_from_github(repo_part, skill_path)

        # 4. 视为 npm 包
        # 解析版本: package@version
        if '@' in package_spec and not package_spec.startswith('@'):
            pkg_name, version = package_spec.rsplit('@', 1)
            return self._install_from_npm(pkg_name, version)

        return self._install_from_npm(package_spec)

    def list_installed(self) -> None:
        """列出所有已安装的技能"""
        if not os.path.exists(self.skills_dir):
            print_error(f"Skills directory does not exist: {self.skills_dir}")
            return

        # 使用 os.listdir 获取所有目录
        try:
            items = os.listdir(self.skills_dir)
            skills = [item for item in items if os.path.isdir(os.path.join(self.skills_dir, item))]
        except Exception as e:
            print_error(f"Failed to list skills: {e}")
            return

        if not skills:
            print_warning(f"No skills installed in {self.skills_dir}")
            return

        print_header(f"📚 Installed Skills ({len(skills)})")
        for skill in sorted(skills):
            # 尝试读取技能元数据
            skill_md = os.path.join(self.skills_dir, skill, "SKILL.md")
            if os.path.exists(skill_md):
                try:
                    with open(skill_md, 'r', encoding='utf-8') as f:
                        first_line = f.readline().strip()
                        if first_line.startswith('name:'):
                            name = first_line.split(':', 1)[1].strip()
                            print(f"  {Colors.GREEN}•{Colors.RESET} {skill} - {name}")
                            continue
                except:
                    pass

            print(f"  {Colors.GREEN}•{Colors.RESET} {skill}")

    def _search_github(self, query: str) -> bool:
        """
        Search GitHub for agent skills

        Args:
            query: Search query

        Returns:
            bool: True if successful
        """
        print_header(f"🔍 Searching GitHub for: {query}")

        # Build GitHub search query
        search_terms = [
            f"{query} agent skill",
            f"{query} claude skill",
            f"{query} AI assistant",
        ]

        # Popular skill repositories
        popular_repos = [
            ("vercel-labs", "agent-skills", "Vercel's collection of agent skills"),
            ("ComposioHQ", "awesome-claude-skills", "Community-maintained list"),
            ("anthropics", "anthropic-quickstarts", "Official Anthropic quickstarts"),
        ]

        print_info("Popular skill repositories:\n")
        for owner, repo, description in popular_repos:
            print(f"  {Colors.GREEN}•{Colors.RESET} {owner}/{repo}")
            print(f"    {description}")
            print(f"    📦 Install: python3 install_skill.py {owner}/{repo}")
            print()

        print_info(f"🔗 Search GitHub manually:")
        print(f"   https://github.com/search?q={query.replace(' ', '+')+ '+agent+skill'}")
        print()

        return True

    def _search_npm(self, query: str) -> bool:
        """
        搜索 npm registry 中的包

        Args:
            query: 搜索关键词

        Returns:
            bool: 是否成功
        """
        print_header(f"🔍 Searching npm registry for: {query}")

        try:
            # 使用 npm registry 的搜索 API
            url = f"https://registry.npmjs.org/-/v1/search?text={urllib.parse.quote(query)}&size=10"

            print_info(f"Querying: {url}\n")

            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

                if data.get('objects'):
                    print_info(f"Found {len(data['objects'])} packages:\n")
                    for pkg in data['objects'][:10]:
                        name = pkg['package']['name']
                        version = pkg['package'].get('version', 'N/A')
                        desc = pkg['package'].get('description', 'No description')
                        desc_short = (desc[:80] + '...') if len(desc) > 80 else desc

                        print(f"  {Colors.GREEN}•{Colors.RESET} {name}@{version}")
                        print(f"    {desc_short}")
                        print(f"    📦 Install: python3 install_skill.py {name}")
                        print()
                else:
                    print_warning("No packages found")
                    return True

            # 提供手动搜索链接
            print_info(f"🔗 Search npm registry manually:")
            print(f"   https://www.npmjs.com/search?q={urllib.parse.quote(query)}")
            print()

            return True

        except urllib.error.HTTPError as e:
            print_error(f"HTTP Error {e.code}: {e.reason}")
            return False
        except urllib.error.URLError as e:
            print_error(f"URL Error: {e.reason}")
            return False
        except Exception as e:
            print_error(f"npm search failed: {e}")
            return False

    def search_skills(self, query: str) -> bool:
        """
        Search for skills without npx

        Args:
            query: Search query

        Returns:
            bool: True if search succeeded
        """
        print_header(f"🔍 Skill Search: {query}")
        print_info("Searching multiple sources...\n")

        # Search GitHub
        github_success = self._search_github(query)

        # Search npm
        npm_success = self._search_npm(query)

        # Provide manual search options
        print_header("📚 Manual Search Options")
        print_info("Browse these websites for skills:")
        print()
        print(f"  • https://skills.sh/          - Official skills directory")
        print(f"  • https://github.com/topics/agent-skills  - GitHub topic")
        print(f"  • https://github.com/topics/claude-skills  - Claude skills")
        print(f"  • https://www.npmjs.com/search?q=agent+skill  - npm packages")
        print()

        return github_success or npm_success


def main():
    parser = argparse.ArgumentParser(
        description="npx-style skill installer - Download and install agent skills via HTTP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Install from npm registry
  python3 /skills/find-skills/scripts/install_skill.py create-react-app

  # Install specific version from npm
  python3 /skills/find-skills/scripts/install_skill.py create-react-app@5.0.1

  # Install from GitHub
  python3 /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills

  # Install from GitHub with specific tag
  python3 /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills@v1.0.0

  # Install skill subdirectory from GitHub
  python3 /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills@vercel-react-best-practices

  # Install from direct URL
  python3 /skills/find-skills/scripts/install_skill.py https://example.com/skill.tar.gz

  # Install from local tarball file
  python3 /skills/find-skills/scripts/install_skill.py /path/to/skill.tar.gz
  python3 /skills/find-skills/scripts/install_skill.py ./my-skill.tgz

  # Search for skills
  python3 /skills/find-skills/scripts/install_skill.py -s "react performance"

  # List installed skills
  python3 /skills/find-skills/scripts/install_skill.py -l

  # Install to custom directory
  python3 /skills/find-skills/scripts/install_skill.py -d /path/to/skills <package>
        """
    )

    parser.add_argument(
        "package",
        nargs="?",
        help="Package to install (npm package, GitHub repo, URL, or local .tgz file)"
    )
    parser.add_argument(
        "-s", "--search",
        metavar="QUERY",
        help="Search for available skills"
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List installed skills"
    )
    parser.add_argument(
        "-d", "--dir",
        default="/skills/",
        help="Target directory for skills (default: /skills/)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    # Create installer
    with NPXStyleInstaller(skills_dir=args.dir) as installer:
        # List installed skills
        if args.list:
            installer.list_installed()
            return 0

        # Search for skills
        if args.search:
            success = installer.search_skills(args.search)
            return 0 if success else 1

        # Install a package
        if args.package:
            success = installer.install(args.package)
            return 0 if success else 1

        # No action specified
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
