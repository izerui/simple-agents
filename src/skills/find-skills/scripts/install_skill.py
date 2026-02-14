#!/usr/bin/env python
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
    python /skills/find-skills/scripts/install_skill.py <package_name>
    python /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills@vercel-react-best-practices
    python /skills/find-skills/scripts/install_skill.py -s "react performance"
    python /skills/find-skills/scripts/install_skill.py -l
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


def find_skill_folders(root_dir: str, skill_name_filter: Optional[str] = None) -> list:
    """
    递归查找包含 SKILL.md 文件的文件夹

    规则：
    - 如果文件夹包含 SKILL.md，则该文件夹是一个技能，不再递归其子文件夹
    - 如果文件夹不包含 SKILL.md，则继续递归查找子文件夹
    - 可能找到多个技能文件夹
    - 如果指定了 skill_name_filter，只返回 SKILL.md 中 name 字段匹配的技能

    Args:
        root_dir: 要搜索的根目录
        skill_name_filter: 可选的技能名称过滤器（匹配 SKILL.md 中的 name 字段）

    Returns:
        list: 包含 SKILL.md 的文件夹路径列表，每项为 (文件夹路径, 技能名称)
    """
    skill_folders = []

    def scan_directory(dir_path: str):
        """递归扫描目录"""
        try:
            items = os.listdir(dir_path)
        except (PermissionError, OSError):
            return

        # 检查当前目录是否包含 SKILL.md
        skill_md_path = os.path.join(dir_path, "SKILL.md")
        if os.path.isfile(skill_md_path):
            # 找到技能文件夹
            skill_name = os.path.basename(dir_path)

            # 如果指定了过滤器，检查 SKILL.md 中的 name 字段是否匹配
            if skill_name_filter:
                if _matches_skill_info(dir_path, skill_name_filter):
                    skill_folders.append((dir_path, skill_name))
            else:
                skill_folders.append((dir_path, skill_name))
            return

        # 当前目录不是技能，递归扫描子目录
        for item in items:
            item_path = os.path.join(dir_path, item)
            if os.path.isdir(item_path):
                scan_directory(item_path)

    scan_directory(root_dir)
    return skill_folders


def _matches_skill_name(folder_name: str, query_name: str) -> bool:
    """
    检查文件夹名是否匹配查询的技能名称

    支持的匹配方式：
    - 精确匹配：error-handling-patterns == error-handling-patterns
    - 大小写不敏感：Error-Handling-Patterns == error-handling-patterns
    - 下划线/横线转换：error_handling_patterns == error-handling-patterns

    Args:
        folder_name: 文件夹名称
        query_name: 查询的技能名称

    Returns:
        bool: 是否匹配
    """
    # 统一转换为小写并替换分隔符
    def normalize(name):
        return name.lower().replace('_', '-').replace(' ', '-')

    return normalize(folder_name) == normalize(query_name)


def _matches_skill_info(skill_dir: str, query_name: str) -> bool:
    """
    检查 SKILL.md 中的 name 字段是否匹配查询的技能名称

    匹配方式：
    - 读取 SKILL.md 中的 name: 字段
    - 大小写不敏感
    - 支持 -, _, 空格 的互通

    Args:
        skill_dir: 技能文件夹路径
        query_name: 查询的技能名称

    Returns:
        bool: 是否匹配
    """
    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    try:
        with open(skill_md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析 name: 字段
        lines = content.strip().split('\n')
        for line in lines[:20]:
            line = line.strip()
            if line.startswith('name:'):
                skill_name = line.split(':', 1)[1].strip()
                # 使用与 _matches_skill_name 相同的匹配逻辑
                def normalize(name):
                    return name.lower().replace('_', '-').replace(' ', '-')
                return normalize(skill_name) == normalize(query_name)
            elif line.startswith('# '):
                # Markdown 标题作为备用
                skill_name = line[2:].strip()
                def normalize(name):
                    return name.lower().replace('_', '-').replace(' ', '-')
                return normalize(skill_name) == normalize(query_name)
    except:
        pass

    # 如果读取失败，回退到文件夹名匹配
    return _matches_skill_name(os.path.basename(skill_dir), query_name)


def get_skill_info(skill_dir: str) -> dict:
    """
    从 SKILL.md 文件中提取技能信息

    Args:
        skill_dir: 技能文件夹路径

    Returns:
        dict: 包含 name, description 等信息
    """
    info = {"name": os.path.basename(skill_dir), "description": ""}

    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    try:
        with open(skill_md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 尝试解析 YAML frontmatter 或开头的 name: 字段
        lines = content.strip().split('\n')
        for line in lines[:20]:  # 只检查前20行
            line = line.strip()
            if line.startswith('name:'):
                info["name"] = line.split(':', 1)[1].strip()
            elif line.startswith('description:'):
                info["description"] = line.split(':', 1)[1].strip()
            elif line.startswith('# '):
                # Markdown 标题作为备用名称
                if info["name"] == os.path.basename(skill_dir):
                    info["name"] = line[2:].strip()
    except:
        pass

    return info


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

        # 使用统一的安装方法（会查找 SKILL.md），传递包名作为过滤器
        # npm 包名可能包含 @scope/，需要提取实际的技能名
        filter_name = package_name.split('/')[-1] if '/' in package_name else package_name
        return self._install_from_tarball(tarball_path, tarball_filename, skill_name_filter=filter_name)

    def _install_from_github(self, repo_spec: str, skill_path: Optional[str] = None) -> bool:
        """
        从 GitHub 仓库下载并安装

        支持格式：
        - owner/repo/skill-name - 仓库是 owner/repo，技能名是 skill-name
        - owner/repo/path/skill-name - 仓库是 owner/repo，路径是 path，技能名是 skill-name

        Args:
            repo_spec: 仓库规格（如 'owner/repo'）
            skill_path: 技能路径或技能名（如 'skills/my-skill' 或 'my-skill'）

        Returns:
            bool: 是否成功
        """
        print_header(f"📦 Installing from GitHub: {repo_spec}")

        # 解析仓库规格
        parts = repo_spec.split('@')
        repo = parts[0]

        if '/' not in repo:
            print_error("Invalid GitHub repo format. Use: owner/repo")
            return False

        owner, repo_name = repo.split('/')[:2]

        # @ 后面是技能名过滤器（如果有的话）
        skill_name_from_at = parts[1] if len(parts) > 1 else None

        # 始终使用 main 分支
        tag = 'main'

        # 构建下载 URL
        tarball_url = f"https://github.com/{owner}/{repo_name}/archive/refs/tags/{tag}.tar.gz"
        fallback_url = f"https://github.com/{owner}/{repo_name}/archive/refs/heads/{tag}.tar.gz"

        tarball_filename = f"{repo_name}-{tag}.tar.gz"
        tarball_path = os.path.join(self.temp_dir, tarball_filename)

        # 尝试下载
        if not self._download_file(tarball_url, tarball_path):
            print_warning("Tag download failed, trying branch...")
            if not self._download_file(fallback_url, tarball_path):
                print_error("Failed to download from GitHub")
                return False

        # 确定技能名过滤器
        skill_name_filter = skill_name_from_at

        # 处理 skill_path：
        # - 如果包含 "/"，说明是目录路径，最后一部分是技能名
        # - 如果不包含 "/"，说明是技能名，用于过滤
        if skill_path:
            if '/' in skill_path:
                # 是目录路径，导航到该目录，最后一部分是技能名
                skill_name_from_path = skill_path.split('/')[-1]
                return self._install_from_tarball_with_path(tarball_path, tarball_filename, skill_path, skill_name_from_path)
            else:
                # 是技能名，用作过滤器
                skill_name_filter = skill_path

        # 使用统一的安装方法（会查找 SKILL.md），传递技能名过滤器
        return self._install_from_tarball(tarball_path, tarball_filename, skill_name_filter=skill_name_filter)

    def _install_from_tarball_with_path(self, tarball_path: str, fallback_name: str, skill_path: str, skill_name_filter: Optional[str] = None) -> bool:
        """
        从 tarball 安装指定的子目录技能

        Args:
            tarball_path: tarball 文件路径
            fallback_name: 备用名称
            skill_path: 技能子目录路径
            skill_name_filter: 可选的技能名称过滤器

        Returns:
            bool: 是否成功
        """
        # 解压
        extract_dir = os.path.join(self.temp_dir, "extracted")
        try:
            os.makedirs(extract_dir, exist_ok=True)
        except FileExistsError:
            pass

        if not self._extract_tarball(tarball_path, extract_dir):
            return False

        # 找到解压后的根目录
        extracted_items = os.listdir(extract_dir)
        if not extracted_items:
            print_error("No files extracted")
            return False

        package_source = os.path.join(extract_dir, extracted_items[0])

        # 导航到指定的技能子目录
        package_source = os.path.join(package_source, skill_path)
        if not os.path.exists(package_source):
            print_error(f"Skill path not found: {skill_path}")
            return False

        # 查找技能（可过滤）
        print_info("Scanning for skills (folders with SKILL.md)...")
        if skill_name_filter:
            print_info(f"Filtering by skill name: {skill_name_filter}")
        skill_folders = find_skill_folders(package_source, skill_name_filter)

        if not skill_folders:
            print_error("No valid skills found (no SKILL.md files detected)")
            print_info("A valid skill must contain a SKILL.md file")
            return False

        # 安装找到的技能
        installed_skills = []
        skipped_skills = []

        print_info(f"Found {len(skill_folders)} skill(s)")

        for skill_dir, skill_name in skill_folders:
            skill_info = get_skill_info(skill_dir)
            display_name = skill_info.get("name", skill_name)
            description = skill_info.get("description", "")

            target_dir = os.path.join(self.skills_dir, skill_name)

            if os.path.exists(target_dir):
                print_warning(f"Skill already exists: {skill_name}")
                skipped_skills.append((skill_name, display_name, "already exists"))
                continue

            try:
                parent_dir = os.path.dirname(target_dir)
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                except FileExistsError:
                    pass

                print_info(f"Installing skill: {skill_name}")
                if copytree_with_open(skill_dir, target_dir):
                    installed_skills.append((skill_name, display_name, description))
                    print_success(f"Installed: {skill_name}")
                else:
                    print_error(f"Failed to install: {skill_name}")
            except Exception as e:
                print_error(f"Installation failed for {skill_name}: {e}")

        # 输出安装摘要
        self._print_install_summary(installed_skills, skipped_skills)

        return len(installed_skills) > 0 or len(skipped_skills) > 0

    def _print_install_summary(self, installed_skills: list, skipped_skills: list) -> None:
        """输出安装摘要"""
        print_header("📋 Installation Summary")
        if installed_skills:
            print_success(f"Successfully installed {len(installed_skills)} skill(s):")
            for skill_name, display_name, description in installed_skills:
                if display_name != skill_name:
                    print(f"  • {skill_name} ({display_name})")
                else:
                    print(f"  • {skill_name}")
                if description:
                    print(f"    {description}")
        else:
            print_warning("No skills were installed")

        if skipped_skills:
            print()
            print_warning(f"Skipped {len(skipped_skills)} skill(s) (already exist):")
            for skill_name, display_name, _ in skipped_skills:
                print(f"  • {skill_name}")

    def _install_from_url(self, url: str) -> bool:
        """
        从直接 URL 下载并安装

        支持格式：
        - tarball URL: https://example.com/package.tar.gz
        - GitHub tree URL: https://github.com/owner/repo/tree/branch/path/to/skill

        Args:
            url: tarball 或文件的直接 URL

        Returns:
            bool: 是否成功
        """
        print_header(f"📦 Installing from URL: {url}")

        # 检查是否是 GitHub tree URL
        # https://github.com/owner/repo/tree/branch/path -> 转换为 tarball 下载
        github_tree_match = re.match(
            r'https?://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)',
            url
        )
        if github_tree_match:
            owner = github_tree_match.group(1)
            repo = github_tree_match.group(2)
            branch = github_tree_match.group(3)
            skill_path = github_tree_match.group(4)

            # 构建 tarball URL
            tarball_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.tar.gz"
            print_info(f"Converting GitHub tree URL to tarball: {tarball_url}")

            tarball_filename = f"{repo}-{branch}.tar.gz"
            tarball_path = os.path.join(self.temp_dir, tarball_filename)

            if not self._download_file(tarball_url, tarball_path):
                return False

            # 使用带路径的安装方法
            skill_name = skill_path.split('/')[-1]
            return self._install_from_tarball_with_path(tarball_path, tarball_filename, skill_path, skill_name)

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

    def _install_from_tarball(self, tarball_path: str, fallback_name: str, skill_name_filter: Optional[str] = None) -> bool:
        """
        从 tarball 解压并安装

        安装逻辑：
        1. 解压 tarball 到临时目录
        2. 查找所有包含 SKILL.md 的文件夹（每个是一个独立技能）
        3. 如果指定了 skill_name_filter，只安装匹配的技能
        4. 将每个技能文件夹复制到 /skills/<skill_name>/
        5. 输出安装的技能列表

        Args:
            tarball_path: tarball 文件路径
            fallback_name: 技能的备用名称
            skill_name_filter: 可选的技能名称过滤器（只安装匹配的技能）

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

            # 找到解压后的根目录
            extracted_items = os.listdir(extract_dir)
            if len(extracted_items) == 1:
                package_source = os.path.join(extract_dir, extracted_items[0])
            else:
                package_source = extract_dir
        else:
            print_error(f"Not a tarball file: {tarball_path}")
            return False

        # 查找所有包含 SKILL.md 的技能文件夹（可过滤）
        print_info("Scanning for skills (folders with SKILL.md)...")
        if skill_name_filter:
            print_info(f"Filtering by skill name: {skill_name_filter}")
        skill_folders = find_skill_folders(package_source, skill_name_filter)

        installed_skills = []
        skipped_skills = []

        if skill_folders:
            # 找到了技能文件夹，逐个安装
            print_info(f"Found {len(skill_folders)} skill(s)")

            for skill_dir, skill_name in skill_folders:
                skill_info = get_skill_info(skill_dir)
                display_name = skill_info.get("name", skill_name)
                description = skill_info.get("description", "")

                target_dir = os.path.join(self.skills_dir, skill_name)

                # 检查是否已安装
                if os.path.exists(target_dir):
                    print_warning(f"Skill already exists: {skill_name}")
                    skipped_skills.append((skill_name, display_name, "already exists"))
                    continue

                # 安装技能
                try:
                    # 确保父目录存在
                    parent_dir = os.path.dirname(target_dir)
                    try:
                        os.makedirs(parent_dir, exist_ok=True)
                    except FileExistsError:
                        pass

                    print_info(f"Installing skill: {skill_name}")
                    if copytree_with_open(skill_dir, target_dir):
                        installed_skills.append((skill_name, display_name, description))
                        print_success(f"Installed: {skill_name}")
                    else:
                        print_error(f"Failed to install: {skill_name}")
                except Exception as e:
                    print_error(f"Installation failed for {skill_name}: {e}")
        else:
            # 没有找到 SKILL.md，认为没有可用技能
            print_error("No valid skills found (no SKILL.md files detected)")
            print_info("A valid skill must contain a SKILL.md file")
            return False

        # 输出安装摘要
        self._print_install_summary(installed_skills, skipped_skills)

        return len(installed_skills) > 0 or len(skipped_skills) > 0

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
            print(f"    📦 Install: python install_skill.py {owner}/{repo}")
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
                        print(f"    📦 Install: python install_skill.py {name}")
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

    def _search_skills_sh(self, query: str) -> bool:
        """
        从 skills.sh 搜索技能

        Args:
            query: 搜索关键词

        Returns:
            bool: 是否成功
        """
        print_header(f"🔍 Searching skills.sh for: {query}")

        try:
            # skills.sh API
            url = f"https://skills.sh/api/search?q={urllib.parse.quote(query)}"

            print_info(f"Querying: {url}\n")

            ssl_context = ssl._create_unverified_context()
            with urllib.request.urlopen(url, timeout=10, context=ssl_context) as response:
                data = json.loads(response.read().decode('utf-8'))

                skills = data.get('skills', [])
                if skills:
                    print_info(f"Found {len(skills)} skill(s):\n")
                    for skill in skills[:10]:  # 最多显示10个
                        skill_id = skill.get('id', '')
                        name = skill.get('name', skill_id)
                        source = skill.get('source', '')
                        installs = skill.get('installs', 0)

                        print(f"  {Colors.GREEN}•{Colors.RESET} {name}")
                        print(f"    Source: {source}")
                        print(f"    Installs: {installs}")
                        print(f"    📦 Install: python install_skill.py {skill_id}")
                        print()
                else:
                    print_warning("No skills found")
                    return True

            return True

        except urllib.error.HTTPError as e:
            print_error(f"HTTP Error {e.code}: {e.reason}")
            return False
        except urllib.error.URLError as e:
            print_error(f"URL Error: {e.reason}")
            return False
        except Exception as e:
            print_error(f"skills.sh search failed: {e}")
            return False

    def _search_skillsmp_keyword(self, query: str) -> bool:
        """
        从 SkillsMP 关键词搜索技能

        API: /api/v1/skills/search

        Args:
            query: 搜索关键词

        Returns:
            bool: 是否成功
        """
        print_header(f"🔍 Searching SkillsMP for: {query}")

        api_token = "sk_live_skillsmp_EYZZIK2d-mZJ2d7PzC7LHBrJx6X2CbjWILeala6LQUs"

        try:
            url = f"https://skillsmp.com/api/v1/skills/search?q={urllib.parse.quote(query)}&limit=10&sortBy=stars"
            print_info(f"Querying SkillsMP API...\n")

            ssl_context = ssl._create_unverified_context()
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {api_token}")
            req.add_header("User-Agent", "Mozilla/5.0 (compatible; SkillInstaller/1.0)")

            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                data = json.loads(response.read().decode('utf-8'))

                if not data.get('success'):
                    print_error("SkillsMP API returned error")
                    return False

                skills_data = data.get('data', {})
                skills = skills_data.get('skills', [])
                pagination = skills_data.get('pagination', {})

                if skills:
                    total = pagination.get('total', len(skills))
                    print_info(f"Found {total} skill(s), showing top {len(skills)}:\n")

                    for skill in skills[:10]:
                        name = skill.get('name', 'Unknown')
                        author = skill.get('author', '')
                        description = skill.get('description', '')
                        github_url = skill.get('githubUrl', '')
                        stars = skill.get('stars', 0)

                        desc_short = (description[:80] + '...') if len(description) > 80 else description

                        print(f"  {Colors.GREEN}•{Colors.RESET} {name}")
                        if author:
                            print(f"    Author: {author}")
                        if desc_short:
                            print(f"    {desc_short}")
                        if stars > 0:
                            print(f"    ⭐ {stars} stars")
                        if github_url:
                            print(f"    📦 Install: python install_skill.py {github_url}")
                        print()
                else:
                    print_warning("No skills found")
                    return True

            return True

        except urllib.error.HTTPError as e:
            if e.code == 401:
                print_error("SkillsMP API: Invalid API key")
            else:
                print_error(f"HTTP Error {e.code}: {e.reason}")
            return False
        except urllib.error.URLError as e:
            print_error(f"URL Error: {e.reason}")
            return False
        except Exception as e:
            print_error(f"SkillsMP search failed: {e}")
            return False

    def _search_skillsmp_ai(self, query: str) -> bool:
        """
        从 SkillsMP AI 语义搜索技能

        API: /api/v1/skills/ai-search
        适用于自然语言查询，如"有哪些技能"、"操作 word 文档的技能"

        Args:
            query: 自然语言查询

        Returns:
            bool: 是否成功
        """
        print_header(f"🔍 AI Semantic Search: {query}")

        api_token = "sk_live_skillsmp_EYZZIK2d-mZJ2d7PzC7LHBrJx6X2CbjWILeala6LQUs"

        try:
            url = f"https://skillsmp.com/api/v1/skills/ai-search?q={urllib.parse.quote(query)}"
            print_info(f"Using AI Semantic Search...\n")

            ssl_context = ssl._create_unverified_context()
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {api_token}")
            req.add_header("User-Agent", "Mozilla/5.0 (compatible; SkillInstaller/1.0)")

            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                data = json.loads(response.read().decode('utf-8'))

                if not data.get('success'):
                    print_error("SkillsMP API returned error")
                    return False

                skills_data = data.get('data', {})
                # AI 搜索返回结构: {"data": [...]} 每项包含 skill 对象
                ai_results = skills_data.get('data', [])

                if not ai_results:
                    print_warning("No skills found")
                    return True

                print_info(f"Found {len(ai_results)} skill(s):\n")

                seen_skills = set()
                for result in ai_results[:10]:
                    skill = result.get('skill', {})
                    if not skill:
                        continue

                    skill_id = skill.get('id', '')
                    if skill_id in seen_skills:
                        continue
                    seen_skills.add(skill_id)

                    name = skill.get('name', 'Unknown')
                    author = skill.get('author', '')
                    description = skill.get('description', '')
                    github_url = skill.get('githubUrl', '')
                    stars = skill.get('stars', 0)
                    score = result.get('score', 0)

                    desc_short = (description[:80] + '...') if len(description) > 80 else description

                    print(f"  {Colors.GREEN}•{Colors.RESET} {name}")
                    if score:
                        print(f"    Relevance: {score:.2f}")
                    if author:
                        print(f"    Author: {author}")
                    if desc_short:
                        print(f"    {desc_short}")
                    if stars > 0:
                        print(f"    ⭐ {stars} stars")
                    if github_url:
                        print(f"    📦 Install: python install_skill.py {github_url}")
                    print()

            return True

        except urllib.error.HTTPError as e:
            if e.code == 401:
                print_error("SkillsMP API: Invalid API key")
            else:
                print_error(f"HTTP Error {e.code}: {e.reason}")
            return False
        except urllib.error.URLError as e:
            print_error(f"URL Error: {e.reason}")
            return False
        except Exception as e:
            print_error(f"SkillsMP AI search failed: {e}")
            return False

    def explore_skills(self, query: str) -> bool:
        """
        探索技能（使用 AI 语义搜索）

        用于模糊查询场景，如：
        - "有哪些技能"
        - "技能分类"
        - "操作 word 文档的技能有哪些"

        Args:
            query: 自然语言查询

        Returns:
            bool: 是否成功
        """
        print_header(f"🔍 Exploring Skills: {query}")
        print_info("Using AI Semantic Search for natural language queries...\n")

        return self._search_skillsmp_ai(query)

    def search_skills(self, query: str) -> bool:
        """
        Search for skills from multiple sources

        搜索优先级：
        1. skills.sh - 专门的技能目录
        2. SkillsMP - 技能市场（支持 AI 语义搜索）
        3. npm registry - npm 包
        4. GitHub - 流行仓库

        Args:
            query: Search query

        Returns:
            bool: True if search succeeded
        """
        print_header(f"🔍 Skill Search: {query}")
        print_info("Searching multiple sources...\n")

        # 1. 优先搜索 skills.sh（专门的技能目录）
        skills_sh_success = self._search_skills_sh(query)

        # 2. 搜索 SkillsMP（技能市场）
        skillsmp_success = self._search_skillsmp_keyword(query)

        # 3. Search npm
        npm_success = self._search_npm(query)

        # 4. Search GitHub
        github_success = self._search_github(query)

        # Provide manual search options
        print_header("📚 Manual Search Options")
        print_info("Browse these websites for skills:")
        print()
        print(f"  • https://skills.sh/          - Official skills directory")
        print(f"  • https://skillsmp.com/       - SkillsMP Marketplace")
        print(f"  • https://github.com/topics/agent-skills  - GitHub topic")
        print(f"  • https://github.com/topics/claude-skills  - Claude skills")
        print(f"  • https://www.npmjs.com/search?q=agent+skill  - npm packages")
        print()

        return skills_sh_success or skillsmp_success or github_success or npm_success


def main():
    parser = argparse.ArgumentParser(
        description="npx-style skill installer - Download and install agent skills via HTTP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Install from npm registry
  python /skills/find-skills/scripts/install_skill.py create-react-app

  # Install specific version from npm
  python /skills/find-skills/scripts/install_skill.py create-react-app@5.0.1

  # Install from GitHub
  python /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills

  # Install from GitHub with specific tag
  python /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills@v1.0.0

  # Install skill subdirectory from GitHub
  python /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills@vercel-react-best-practices

  # Install from direct URL
  python /skills/find-skills/scripts/install_skill.py https://example.com/skill.tar.gz

  # Install from local tarball file
  python /skills/find-skills/scripts/install_skill.py /path/to/skill.tar.gz
  python /skills/find-skills/scripts/install_skill.py ./my-skill.tgz

  # Search for skills
  python /skills/find-skills/scripts/install_skill.py -s "react performance"

  # Explore skills with AI semantic search (for natural language queries)
  python /skills/find-skills/scripts/install_skill.py -e "操作 word 文档的技能有哪些"
  python /skills/find-skills/scripts/install_skill.py -e "有哪些类型的技能"

  # List installed skills
  python /skills/find-skills/scripts/install_skill.py -l

  # Install to custom directory
  python /skills/find-skills/scripts/install_skill.py -d /path/to/skills <package>
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
        help="Search for available skills (keyword search)"
    )
    parser.add_argument(
        "-e", "--explore",
        metavar="QUERY",
        help="Explore skills using AI semantic search (for natural language queries like '有哪些技能')"
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

        # Explore skills (AI semantic search)
        if args.explore:
            success = installer.explore_skills(args.explore)
            return 0 if success else 1

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
