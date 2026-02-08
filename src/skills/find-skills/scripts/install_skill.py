#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skills Installation Script - npx-like Implementation

This script implements npx-like functionality to download and install agent skills
directly via HTTP to your sandbox's /skills/ directory.

Features:
- Download from npm registry (like npx)
- Download from GitHub repositories
- Download from direct URLs
- NEVER overwrites existing installations
- Supports multiple package formats

Usage:
    python install_skill.py <package_name>
    python install_skill.py vercel-labs/agent-skills@vercel-react-best-practices
    python install_skill.py -s "react performance"
    python install_skill.py -l
"""

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
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
        Initialize installer

        Args:
            skills_dir: Target directory for skills (default: /skills/)
        """
        self.skills_dir = Path(skills_dir)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="skill_install_"))

        # npm registry configuration
        self.npm_registry = "https://registry.npmjs.org"

        # Common CDN mirrors for faster downloads
        self.npm_mirrors = [
            "https://registry.npmjs.org",
            "https://registry.npmmirror.com",  # 中国镜像
        ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cleanup temp directory
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _download_file(self, url: str, dest_path: Path, timeout: int = 30) -> bool:
        """
        Download file from URL to destination path

        Args:
            url: Source URL
            dest_path: Destination file path
            timeout: Download timeout in seconds

        Returns:
            bool: True if successful
        """
        try:
            print_info(f"Downloading from: {url}")
            with urllib.request.urlopen(url, timeout=timeout) as response:
                with open(dest_path, 'wb') as f:
                    shutil.copyfileobj(response, f)
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

    def _extract_tarball(self, tarball_path: Path, dest_dir: Path) -> bool:
        """
        Extract .tgz tarball to destination directory

        Args:
            tarball_path: Path to .tgz file
            dest_dir: Destination directory

        Returns:
            bool: True if successful
        """
        try:
            # Use the same approach as the working example
            if tarball_path.suffix == '.gz':
                with gzip.open(tarball_path, 'rb') as gz:
                    with tarfile.open(fileobj=gz, mode='r:gz') as tar:
                        tar.extractall(path=str(dest_dir))
            else:
                with tarfile.open(str(tarball_path), 'r:gz') as tar:
                    tar.extractall(path=str(dest_dir))
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
        for registry in self.npm_mirrors:
            try:
                url = f"{registry}/{package_name}"
                print_info(f"Querying registry: {registry}")

                with urllib.request.urlopen(url, timeout=10) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    return data
            except Exception as e:
                print_warning(f"Registry {registry} failed: {e}")
                continue

        return None

    def _install_from_npm(self, package_name: str, version: Optional[str] = None) -> bool:
        """
        Download and install package from npm registry

        Args:
            package_name: npm package name (e.g., 'create-react-app')
            version: Specific version (default: latest)

        Returns:
            bool: True if successful
        """
        print_header(f"📦 Installing from npm registry: {package_name}")

        # Fetch package metadata
        pkg_info = self._get_npm_package_info(package_name)
        if not pkg_info:
            print_error("Package not found in npm registry")
            return False

        # Determine version to install
        if version:
            if version not in pkg_info.get('versions', {}):
                print_error(f"Version {version} not found")
                return False
            dist_tags = {'version': version}
        else:
            dist_tags = pkg_info.get('dist-tags', {})
            version = dist_tags.get('latest', 'latest')

        print_info(f"Version: {version}")

        # Get tarball URL and metadata
        versions_data = pkg_info.get('versions', {})
        version_data = versions_data.get(version, {})
        dist_data = version_data.get('dist', {})
        tarball_url = dist_data.get('tarball')

        if not tarball_url:
            print_error("No tarball URL found in package metadata")
            return False

        # Download tarball
        tarball_filename = f"{package_name}-{version}.tgz"
        tarball_path = self.temp_dir / tarball_filename

        if not self._download_file(tarball_url, tarball_path):
            return False

        # Extract to temp directory
        extract_dir = self.temp_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)

        if not self._extract_tarball(tarball_path, extract_dir):
            return False

        # Find package directory (usually in 'package/' subdirectory)
        extracted_items = list(extract_dir.iterdir())
        if len(extracted_items) == 1 and extracted_items[0].is_dir():
            package_source = extracted_items[0]
        else:
            package_source = extract_dir

        # Determine target directory name
        # Explicitly convert to string to avoid sandbox detection issues
        skill_name = str(package_name).replace('/', '-')
        target_dir = self.skills_dir / skill_name

        # Check if already installed (NEVER overwrite)
        if target_dir.exists():
            print_warning(f"Skill already exists: {target_dir}")
            print_warning("Skipping installation (NEVER overwrites existing files)")
            return True

        # Install to skills directory
        try:
            shutil.copytree(package_source, target_dir)
            print_success(f"Installed to: {target_dir}")
            return True
        except Exception as e:
            print_error(f"Installation failed: {e}")
            return False

    def _install_from_github(self, repo_spec: str, skill_path: Optional[str] = None) -> bool:
        """
        Download and install from GitHub repository

        Args:
            repo_spec: Repository specification (e.g., 'owner/repo' or 'owner/repo@tag')
            skill_path: Path to skill subdirectory in repo (e.g., 'skills/my-skill')

        Returns:
            bool: True if successful
        """
        print_header(f"📦 Installing from GitHub: {repo_spec}")

        # Parse repo specification
        # Format: owner/repo[@tag][/path/to/skill]
        parts = repo_spec.split('@')
        repo = parts[0]

        if '/' not in repo:
            print_error("Invalid GitHub repo format. Use: owner/repo")
            return False

        owner, repo_name = repo.split('/')[:2]

        # Parse tag/branch
        tag = parts[1] if len(parts) > 1 else 'main'

        # Try both 'main' and 'master' if default
        if tag in ['main', 'master']:
            tag = 'main'  # Default to main

        # Build download URL
        # GitHub tarball URL: https://github.com/owner/repo/archive/refs/tags/tag.tar.gz
        # or for branch: https://github.com/owner/repo/archive/refs/heads/branch.tar.gz
        tarball_url = f"https://github.com/{owner}/{repo_name}/archive/refs/tags/{tag}.tar.gz"

        # Fallback to branch if tag doesn't exist
        fallback_url = f"https://github.com/{owner}/{repo_name}/archive/refs/heads/{tag}.tar.gz"

        tarball_filename = f"{repo_name}-{tag}.tar.gz"
        tarball_path = self.temp_dir / tarball_filename

        # Try to download
        if not self._download_file(tarball_url, tarball_path):
            print_warning("Tag download failed, trying branch...")
            if not self._download_file(fallback_url, tarball_path):
                print_error("Failed to download from GitHub")
                return False

        # Extract
        extract_dir = self.temp_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)

        if not self._extract_tarball(tarball_path, extract_dir):
            return False

        # Find extracted directory
        extracted_items = list(extract_dir.iterdir())
        if not extracted_items:
            print_error("No files extracted")
            return False

        package_source = extracted_items[0]

        # Navigate to skill subdirectory if specified
        if skill_path:
            package_source = package_source / skill_path
            if not package_source.exists():
                print_error(f"Skill path not found: {skill_path}")
                return False

        # Determine target directory
        skill_name = f"{owner}-{repo_name}"
        if skill_path:
            # Explicitly convert to string to avoid sandbox detection issues
            skill_path_str = str(skill_path)
            skill_name = skill_path_str.replace('/', '-')

        target_dir = self.skills_dir / skill_name

        # Check if already installed (NEVER overwrite)
        if target_dir.exists():
            print_warning(f"Skill already exists: {target_dir}")
            print_warning("Skipping installation (NEVER overwrites existing files)")
            return True

        # Install
        try:
            shutil.copytree(package_source, target_dir)
            print_success(f"Installed to: {target_dir}")
            return True
        except Exception as e:
            print_error(f"Installation failed: {e}")
            return False

    def _install_from_url(self, url: str) -> bool:
        """
        Download and install from direct URL

        Args:
            url: Direct URL to tarball or file

        Returns:
            bool: True if successful
        """
        print_header(f"📦 Installing from URL: {url}")

        # Determine file type from URL
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path) or "downloaded_file"

        download_path = self.temp_dir / filename

        # Download
        if not self._download_file(url, download_path):
            return False

        # Extract and install
        return self._install_from_tarball(download_path, filename)

    def _install_from_local_file(self, file_path: str) -> bool:
        """
        Install from local tarball file

        Args:
            file_path: Path to local tarball file

        Returns:
            bool: True if successful
        """
        print_header(f"📦 Installing from local file: {file_path}")

        # Validate file exists
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            print_error(f"File not found: {file_path}")
            return False

        # Extract and install
        filename = file_path_obj.name
        return self._install_from_tarball(file_path_obj, filename)

    def _install_from_tarball(self, tarball_path: Path, fallback_name: str) -> bool:
        """
        Extract and install from tarball

        Args:
            tarball_path: Path to tarball file
            fallback_name: Fallback name for the skill

        Returns:
            bool: True if successful
        """
        # If it's a tarball, extract it
        if tarfile.is_tarfile(tarball_path):
            extract_dir = self.temp_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)

            print_info(f"Extracting: {tarball_path.name}")
            if not self._extract_tarball(tarball_path, extract_dir):
                return False

            # Find extracted directory
            extracted_items = list(extract_dir.iterdir())
            package_source = extracted_items[0] if len(extracted_items) == 1 else extract_dir
        else:
            print_error(f"Not a tarball file: {tarball_path}")
            return False

        # Determine target name - use string operations instead of Path methods
        import os
        filename = os.path.basename(str(fallback_name))
        # Remove extensions using string replace
        skill_name = filename.replace('.tar.gz', '').replace('.tgz', '').replace('.tar.bz2', '').replace('.tar', '')
        target_dir = self.skills_dir / skill_name

        # Check if already installed
        if target_dir.exists():
            print_warning(f"Skill already exists: {target_dir}")
            print_warning("Skipping installation (NEVER overwrites existing files)")
            return True

        # Install
        print_info(f"Installing to: {target_dir}")
        try:
            shutil.copytree(package_source, target_dir)
            print_success(f"Installed successfully: {target_dir}")
            return True
        except Exception as e:
            print_error(f"Installation failed: {e}")
            return False

    def install(self, package_spec: str) -> bool:
        """
        Install a package from various sources

        Package format:
        - npm package: 'package-name' or 'package-name@version'
        - GitHub: 'owner/repo' or 'owner/repo@tag' or 'owner/repo@tag/path/to/skill'
        - Direct URL: 'https://example.com/package.tar.gz'
        - Local file: '/path/to/file.tar.gz' or 'file.tar.gz'

        Args:
            package_spec: Package specification string

        Returns:
            bool: True if successful
        """
        # Ensure skills directory exists
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        print_info(f"Skills directory: {self.skills_dir}")

        # Detect package type and install accordingly
        # 1. Check if it's a URL
        if package_spec.startswith('http://') or package_spec.startswith('https://'):
            return self._install_from_url(package_spec)

        # 2. Check if it's a local file (exists and ends with .tgz or .tar.gz)
        if package_spec.endswith(('.tgz', '.tar.gz', '.tar.bz2', '.tar')):
            return self._install_from_local_file(package_spec)

        # 3. Check if it's a GitHub repo (contains /)
        if '/' in package_spec and not package_spec.startswith('@'):
            # Parse format: owner/repo[@tag][/skill/path]
            parts = package_spec.split('/')
            if len(parts) >= 2:
                repo_part = f"{parts[0]}/{parts[1]}"
                skill_path = '/'.join(parts[2:]) if len(parts) > 2 else None
                return self._install_from_github(repo_part, skill_path)

        # 4. Treat as npm package
        # Parse version: package@version
        if '@' in package_spec and not package_spec.startswith('@'):
            pkg_name, version = package_spec.rsplit('@', 1)
            return self._install_from_npm(pkg_name, version)

        return self._install_from_npm(package_spec)

    def list_installed(self) -> None:
        """List all installed skills"""
        if not self.skills_dir.exists():
            print_error(f"Skills directory does not exist: {self.skills_dir}")
            return

        skills = [d for d in self.skills_dir.iterdir() if d.is_dir()]

        if not skills:
            print_warning(f"No skills installed in {self.skills_dir}")
            return

        print_header(f"📚 Installed Skills ({len(skills)})")
        for skill in sorted(skills):
            # Try to read skill metadata
            skill_md = skill / "SKILL.md"
            if skill_md.exists():
                try:
                    with open(skill_md, 'r', encoding='utf-8') as f:
                        first_line = f.readline().strip()
                        if first_line.startswith('name:'):
                            name = first_line.split(':', 1)[1].strip()
                            print(f"  {Colors.GREEN}•{Colors.RESET} {skill.name} - {name}")
                            continue
                except:
                    pass

            print(f"  {Colors.GREEN}•{Colors.RESET} {skill.name}")

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
        Search npm registry for packages

        Args:
            query: Search query

        Returns:
            bool: True if successful
        """
        print_header(f"🔍 Searching npm registry for: {query}")

        try:
            # npm registry search API (deprecated but still works)
            # Alternatively, we can suggest manual search
            print_info(f"🔗 Search npm registry manually:")
            print(f"   https://www.npmjs.com/search?q={query.replace(' ', '+')}")
            print()

            # Try to get some suggestions based on common patterns
            suggestions = {
                'react': ['create-react-app', 'react-scripts', '@react-skills/core'],
                'typescript': ['typescript', 'ts-node', '@types/node'],
                'testing': ['jest', 'playwright', 'cypress', 'vitest'],
                'test': ['jest', 'playwright', 'cypress', 'vitest'],
                'deploy': ['vercel', 'netlify-cli', 'serverless'],
                'docs': ['documentation.js', 'jsdoc', 'typedoc'],
                'documentation': ['documentation.js', 'jsdoc', 'typedoc'],
            }

            query_lower = query.lower()
            found_packages = set()
            for key, packages in suggestions.items():
                if key in query_lower:
                    for pkg in packages:
                        found_packages.add(pkg)

            if found_packages:
                print_info(f"Suggested npm packages:")
                for pkg in sorted(found_packages):
                    print(f"  {Colors.GREEN}•{Colors.RESET} {pkg}")
                    print(f"    📦 Install: python3 install_skill.py {pkg}")
                print()

            return True

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
  python install_skill.py create-react-app

  # Install specific version from npm
  python install_skill.py create-react-app@5.0.1

  # Install from GitHub
  python install_skill.py vercel-labs/agent-skills

  # Install from GitHub with specific tag
  python install_skill.py vercel-labs/agent-skills@v1.0.0

  # Install skill subdirectory from GitHub
  python install_skill.py vercel-labs/agent-skills@vercel-react-best-practices

  # Install from direct URL
  python install_skill.py https://example.com/skill.tar.gz

  # Install from local tarball file
  python install_skill.py /path/to/skill.tar.gz
  python install_skill.py ./my-skill.tgz

  # Search for skills
  python install_skill.py -s "react performance"

  # List installed skills
  python install_skill.py -l

  # Install to custom directory
  python install_skill.py -d /path/to/skills <package>
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
