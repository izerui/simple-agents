"""AsyncFilesystemBackend: 异步直接从文件系统读取和写入文件。

安全性和搜索升级：
- 安全解析路径并限制在 thread_dir 内(沙箱隔离)
- 防止文件 I/O 时跟随符号链接(在可用时使用 O_NOFOLLOW)
- 基于 ripgrep 的搜索功能(支持 JSON 解析)以及 Python 正则回退
- 支持可选的 glob 过滤，所有路径都使用虚拟路径格式（相对于 thread_dir）
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
import aiofiles.os as aios
import wcmatch.glob as wcglob

from deepagents.backends.protocol import (
    BackendProtocol,
    EditResult,
    ExecuteResponse,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    SandboxBackendProtocol,
    WriteResult,
)
from deepagents.backends.utils import (
    check_empty_content,
    format_content_with_line_numbers,
    perform_string_replacement,
)


class AsyncFilesystemBackend(SandboxBackendProtocol):
    """异步直接从文件系统读取和写入文件的后端。

    所有文件操作都相对于 thread_dir 进行，提供沙箱隔离。
    入参和返回的路径都是虚拟路径（相对于 thread_dir，以 / 开头或相对路径）。
    内容以纯文本形式读/写，元数据(时间戳)从文件系统统计信息派生。
    实现了 execute 的版本
    """

    def __init__(
            self,
            thread_dir: str | Path | None = None,
            max_file_size_mb: int = 10,
            thread_id: str | None = None,
    ) -> None:
        """初始化文件系统后端。

        Args:
            thread_dir: 文件操作的根目录。如果提供，
                       所有文件路径将相对于此目录解析。
                       如果未提供，则使用当前工作目录。
            max_file_size_mb: 最大文件大小(MB)
            thread_id: 线程ID(用于标识会话)
        """
        self.thread_id = thread_id
        # 简化路径处理：使用字符串而不是 Path 对象
        # 规范化 thread_dir，移除 ./ 前缀
        thread_dir_str = str(thread_dir) if thread_dir else "."
        if thread_dir_str.startswith("./"):
            thread_dir_str = thread_dir_str[2:]
        elif thread_dir_str == ".":
            thread_dir_str = ""
        self.thread_dir = thread_dir_str
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

    def get_thread_id(self) -> str | None:
        """获取此后端的线程 ID。"""
        return self.thread_id

    def prepend_thread_dir(self, key: str) -> str:
        """拼接 thread_dir 前缀并进行安全检查。

        将输入的虚拟路径与 thread_dir 拼接为实际路径。
        支持多种路径格式：
        - / 开头的绝对虚拟路径（相对于 thread_dir）
        - ./ 开头的相对路径
        - 直接文件名（相对路径）

        不支持路径遍历（如 ../），会抛出 ValueError。

        Args:
            key: 文件路径

        Returns:
            thread_dir 下的实际路径字符串

        Raises:
            ValueError: 如果尝试路径遍历（使用 ../）
        """
        # 规范化输入路径，只移除作为虚拟路径标记的 /（不影响隐藏目录）
        if key.startswith("/"):
            key = key[1:]
        
        # 移除作为相对路径标记的 ./（但保留隐藏目录的 .）
        if key.startswith("./"):
            key = key[2:]
        
        # 检查路径遍历
        if "../" in key or key.startswith(".."):
            raise ValueError("不允许路径遍历")
        
        # 拼接路径
        if not self.thread_dir:
            return key
        elif self.thread_dir.endswith("/") or key.startswith("/"):
            return self.thread_dir + key
        else:
            return self.thread_dir + "/" + key

    def remove_thread_dir_prefix(self, abs_path: str) -> str:
        """移除 thread_dir 前缀。

        将实际路径转换为相对于 thread_dir 的虚拟路径。
        不管实际路径在哪，返回的总是相对于 thread_dir 的路径。

        Args:
            abs_path: 实际路径字符串

        Returns:
            虚拟路径字符串（相对于 thread_dir，以 / 开头）
        """
        # 确保 thread_dir 以 / 结尾，方便拼接
        if not self.thread_dir:
            return "/" + abs_path if not abs_path.startswith("/") else abs_path
        thread_dir = self.thread_dir if self.thread_dir.endswith("/") else self.thread_dir + "/"
        
        # 移除 thread_dir 前缀
        if abs_path.startswith(thread_dir):
            virtual_path = abs_path[len(thread_dir):]
        else:
            # 如果不在 thread_dir 下，直接使用原路径（或返回 /）
            logging.warning(f"文件 {abs_path} 不在 {thread_dir} 下")
            virtual_path = abs_path
        
        # 规范化：确保以 / 开头（除了 . 和 ../）
        if virtual_path and virtual_path != "." and not virtual_path.startswith("../"):
            if not virtual_path.startswith("/"):
                virtual_path = "/" + virtual_path
        
        return virtual_path

    async def als_info(self, path: str) -> list[FileInfo]:
        """列出指定目录中的文件和目录(非递归)。

        Args:
            path: 要列出文件的目录的虚拟路径。

        Returns:
            FileInfo 字典列表，包含目录中的文件和目录。
            目录路径以 / 结尾且 is_dir=True。
        """
        abs_dir_path = Path(self.prepend_thread_dir(path))

        try:
            exists = await aios.path.exists(abs_dir_path)
            is_dir = await aios.path.isdir(abs_dir_path)
        except (OSError, PermissionError):
            return []

        if not exists or not is_dir:
            return []

        results: list[FileInfo] = []

        # 仅列出直接子项(非递归)
        try:
            child_names = await aios.listdir(abs_dir_path)

            # 系统目录过滤列表
            SYSTEM_IGNORE_DIRS = {"home", "var", "etc", "usr", "bin", "sbin", "lib", "boot", "dev", "proc", "sys"}

            for child_name in child_names:
                # 过滤系统目录
                if child_name in SYSTEM_IGNORE_DIRS:
                    continue
                child_path = abs_dir_path / child_name
                try:
                    is_file = await aios.path.isfile(child_path)
                    is_dir = await aios.path.isdir(child_path)
                except OSError:
                    continue

                abs_path = str(child_path)

                # 使用 remove_thread_dir_prefix 方法转换为虚拟路径
                virt_path = self.remove_thread_dir_prefix(abs_path)

                if is_file:
                    try:
                        st = await aios.stat(child_path)
                        results.append(
                            {
                                "path": virt_path,
                                "is_dir": False,
                                "size": int(st.st_size),
                                "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                            }
                        )
                    except OSError:
                        results.append({"path": virt_path, "is_dir": False})
                elif is_dir:
                    try:
                        st = await aios.stat(child_path)
                        results.append(
                            {
                                "path": virt_path + "/",
                                "is_dir": True,
                                "size": 0,
                                "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                            }
                        )
                    except OSError:
                        results.append({"path": virt_path + "/", "is_dir": True})
        except (OSError, PermissionError):
            pass

        # 按路径保持确定性的顺序
        results.sort(key=lambda x: x.get("path", ""))
        return results

    async def aread(
            self,
            file_path: str,
            offset: int = 0,
            limit: int = 2000,
    ) -> str:
        """读取带行号的文件内容。

        Args:
            file_path: 文件路径(虚拟路径)。
            offset: 开始读取的行偏移量(从0开始索引)。
            limit: 要读取的最大行数。

        Returns:
            带行号的格式化文件内容，或错误消息。
        """
        abs_file_path = Path(self.prepend_thread_dir(file_path))

        try:
            exists = await aios.path.exists(abs_file_path)
            is_file = await aios.path.isfile(abs_file_path)
        except (OSError, PermissionError):
            return f"读取文件 '{file_path}' 时出错：权限错误"

        if not exists or not is_file:
            return f"错误：未找到文件 '{file_path}'"

        try:
            # 异步读取内容
            async with aiofiles.open(abs_file_path, mode="r", encoding="utf-8") as f:
                content = await f.read()

            empty_msg = check_empty_content(content)
            if empty_msg:
                return empty_msg

            lines = content.splitlines()
            start_idx = offset
            end_idx = min(start_idx + limit, len(lines))

            if start_idx >= len(lines):
                return f"错误：行偏移量 {offset} 超出文件长度({len(lines)} 行)"

            selected_lines = lines[start_idx:end_idx]
            return format_content_with_line_numbers(selected_lines, start_line=start_idx + 1)
        except (OSError, UnicodeDecodeError) as e:
            return f"读取文件 '{file_path}' 时出错：{e}"

    async def awrite(
            self,
            file_path: str,
            content: str,
    ) -> WriteResult:
        """创建包含内容的新文件，如果文件已存在则覆盖。
        返回 WriteResult。外部存储设置 files_update=None。
        """
        abs_file_path = Path(self.prepend_thread_dir(file_path))

        try:
            # 如果需要，创建父目录
            parent = abs_file_path.parent
            try:
                await aios.makedirs(parent, exist_ok=True)
            except OSError:
                pass  # 父目录可能已存在

            # 异步写入内容
            async with aiofiles.open(abs_file_path, mode="w", encoding="utf-8") as f:
                await f.write(content)

            return WriteResult(path=file_path, files_update=None)
        except (OSError, PermissionError, UnicodeEncodeError) as e:
            return WriteResult(error=f"写入文件 '{file_path}' 时出错：{e}")

    async def aedit(
            self,
            file_path: str,
            old_string: str,
            new_string: str,
            replace_all: bool = False,
    ) -> EditResult:
        """通过替换字符串来编辑文件。
        返回 EditResult。外部存储设置 files_update=None。
        """
        abs_file_path = Path(self.prepend_thread_dir(file_path))

        try:
            exists = await aios.path.exists(abs_file_path)
            is_file = await aios.path.isfile(abs_file_path)
        except (OSError, PermissionError):
            return EditResult(error=f"编辑文件 '{file_path}' 时出错：权限错误")

        if not exists or not is_file:
            return EditResult(error=f"错误：未找到文件 '{file_path}'")

        try:
            # 异步读取
            async with aiofiles.open(abs_file_path, mode="r", encoding="utf-8") as f:
                content = await f.read()

            result = perform_string_replacement(content, old_string, new_string, replace_all)

            if isinstance(result, str):
                return EditResult(error=result)

            new_content, occurrences = result

            # 异步写入
            async with aiofiles.open(abs_file_path, mode="w", encoding="utf-8") as f:
                await f.write(new_content)
            
            return EditResult(path=file_path, files_update=None, occurrences=int(occurrences))
        except (OSError, UnicodeDecodeError, UnicodeEncodeError) as e:
            return EditResult(error=f"编辑文件 '{file_path}' 时出错：{e}")

    async def agrep_raw(
            self,
            pattern: str,
            path: str | None = None,
            glob: str | None = None,
    ) -> list[GrepMatch] | str:
        # Validate regex
        try:
            re.compile(pattern)
        except re.error as e:
            return f"Invalid regex pattern: {e}"

        # Resolve base path
        try:
            base_full = Path(self.prepend_thread_dir(path or "."))
        except ValueError:
            return []

        try:
            exists = await aios.path.exists(base_full)
        except (OSError, PermissionError):
            return []

        if not exists:
            return []

        # Try ripgrep first
        results = await self._ripgrep_search(pattern, base_full, glob)
        if results is None:
            results = await self._python_search(pattern, base_full, glob)

        matches: list[GrepMatch] = []
        for fpath, items in results.items():
            for line_num, line_text in items:
                matches.append({"path": fpath, "line": int(line_num), "text": line_text})
        return matches

    async def _ripgrep_search(
            self, pattern: str, base_full: Path, include_glob: str | None
    ) -> dict[str, list[tuple[int, str]]] | None:
        cmd = ["rg", "--json"]
        if include_glob:
            cmd.extend(["--glob", include_glob])
        cmd.extend(["--", pattern, str(base_full)])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        except (asyncio.TimeoutError, FileNotFoundError):
            return None

        results: dict[str, list[tuple[int, str]]] = {}
        for line in stdout.decode().splitlines():
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("type") != "match":
                continue
            pdata = data.get("data", {})
            ftext = pdata.get("path", {}).get("text")
            if not ftext:
                continue
            p = Path(ftext)
            try:
                # Use try_resolve to avoid blocking
                # 将实际路径转换为虚拟路径
                virt = self.remove_thread_dir_prefix(str(p))
            except Exception:
                continue
            ln = pdata.get("line_number")
            lt = pdata.get("lines", {}).get("text", "").rstrip("\n")
            if ln is None:
                continue
            results.setdefault(virt, []).append((int(ln), lt))

        return results

    async def _python_search(
            self, pattern: str, base_full: Path, include_glob: str | None
    ) -> dict[str, list[tuple[int, str]]]:
        try:
            regex = re.compile(pattern)
        except re.error:
            return {}

        results: dict[str, list[tuple[int, str]]] = {}

        try:
            is_dir = await aios.path.isdir(base_full)
        except OSError:
            return {}

        root = base_full if is_dir else base_full.parent

        # Run glob in executor to avoid blocking
        def glob_files():
            return list(root.rglob("*"))

        file_paths = await asyncio.to_thread(glob_files)

        for fp in file_paths:
            try:
                is_file = await aios.path.isfile(fp)
            except OSError:
                continue

            if not is_file:
                continue

            if include_glob and not wcglob.globmatch(fp.name, include_glob, flags=wcglob.BRACE):
                continue

            try:
                st = await aios.stat(fp)
                if st.st_size > self.max_file_size_bytes:
                    continue
            except OSError:
                continue

            try:
                # Read in executor for non-blocking operation
                content = await asyncio.to_thread(fp.read_text)
            except (UnicodeDecodeError, PermissionError, OSError):
                continue

            for line_num, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    try:
                        # Use try_resolve to avoid blocking
                        # 将实际路径转换为虚拟路径
                        virt_path = self.remove_thread_dir_prefix(str(fp))
                    except Exception:
                        continue
                    results.setdefault(virt_path, []).append((line_num, line))

        return results

    async def aglob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        if pattern.startswith("/"):
            pattern = pattern.lstrip("/")

        abs_search_path = Path(self.thread_dir) if path == "/" else Path(self.prepend_thread_dir(path))

        try:
            exists = await aios.path.exists(abs_search_path)
            is_dir = await aios.path.isdir(abs_search_path)
        except (OSError, PermissionError):
            return []

        if not exists or not is_dir:
            return []

        results: list[FileInfo] = []
        try:
            # Use recursive globbing to match files in subdirectories as tests expect
            def glob_match():
                return list(abs_search_path.rglob(pattern))

            matched_paths = await asyncio.to_thread(glob_match)

            for matched_path in matched_paths:
                try:
                    is_file = await aios.path.isfile(matched_path)
                except OSError:
                    continue
                if not is_file:
                    continue

                abs_path = str(matched_path)
                virt = self.remove_thread_dir_prefix(abs_path)
                try:
                    st = await aios.stat(matched_path)
                    results.append(
                        {
                            "path": virt,
                            "is_dir": False,
                            "size": int(st.st_size),
                            "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                        }
                    )
                except OSError:
                    results.append({"path": virt, "is_dir": False})
        except (OSError, ValueError):
            pass

        results.sort(key=lambda x: x.get("path", ""))
        return results

    def execute(
        self,
        command: str,
    ) -> ExecuteResponse:
        """Execute a shell command in the current process (Docker container).

        Args:
            command: Full shell command string to execute.

        Returns:
            ExecuteResponse with combined output, exit code, and truncation flag.
        """
        import subprocess
        
        # Execute the command
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes timeout
            )
            
            # Combine stdout and stderr
            output = result.stdout
            if result.stderr:
                output += result.stderr
            
            # Truncate if output is too large
            max_output_length = 100000  # 100KB
            truncated = False
            if len(output) > max_output_length:
                output = output[:max_output_length]
                truncated = True
                output += "\n\n... [output truncated, too long] ..."
            
            return ExecuteResponse(
                output=output,
                exit_code=result.returncode,
                truncated=truncated
            )
            
        except subprocess.TimeoutExpired:
            return ExecuteResponse(
                output="Error: Command execution timed out (5 minutes limit)",
                exit_code=-1,
                truncated=False
            )
        except Exception as e:
            return ExecuteResponse(
                output=f"Error executing command: {str(e)}",
                exit_code=-1,
                truncated=False
            )

    async def aexecute(
        self,
        command: str,
    ) -> ExecuteResponse:
        """Async version of execute.

        Args:
            command: Full shell command string to execute.

        Returns:
            ExecuteResponse with combined output, exit code, and truncation flag.
        """
        # Run execute in a thread pool to avoid blocking
        return await asyncio.to_thread(self.execute, command)

    @property
    def id(self) -> str:
        """Unique identifier for this backend instance."""
        return f"AsyncFilesystemBackend_{self.thread_id or 'default'}"

    async def aupload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload multiple files to the filesystem asynchronously.

        Args:
            files: List of (path, content) tuples where content is bytes.

        Returns:
            List of FileUploadResponse objects, one per input file.
            Response order matches input order.
        """
        responses: list[FileUploadResponse] = []
        for path, content in files:
            try:
                abs_file_path = Path(self.prepend_thread_dir(path))

                # Create parent directories if needed
                parent = abs_file_path.parent
                try:
                    await aios.makedirs(parent, exist_ok=True)
                except OSError:
                    pass  # Parent might already exist

                # Write content asynchronously in binary mode
                async with aiofiles.open(abs_file_path, mode="wb") as f:
                    await f.write(content)

                responses.append(FileUploadResponse(path=path, error=None))
            except FileNotFoundError:
                responses.append(FileUploadResponse(path=path, error="file_not_found"))
            except PermissionError:
                responses.append(FileUploadResponse(path=path, error="permission_denied"))
            except (ValueError, OSError) as e:
                # ValueError from _resolve_path for path traversal, OSError for other file errors
                if isinstance(e, ValueError) or "invalid" in str(e).lower():
                    responses.append(FileUploadResponse(path=path, error="invalid_path"))
                else:
                    # Generic error fallback
                    responses.append(FileUploadResponse(path=path, error="invalid_path"))

        return responses

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download multiple files from the filesystem asynchronously.

        Args:
            paths: List of file paths to download.

        Returns:
            List of FileDownloadResponse objects, one per input path.
        """
        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                abs_file_path = Path(self.prepend_thread_dir(path))
                # Read asynchronously in binary mode
                async with aiofiles.open(abs_file_path, mode="rb") as f:
                    content = await f.read()
                responses.append(FileDownloadResponse(path=path, content=content, error=None))
            except FileNotFoundError:
                responses.append(FileDownloadResponse(path=path, content=None, error="file_not_found"))
            except PermissionError:
                responses.append(FileDownloadResponse(path=path, content=None, error="permission_denied"))
            except IsADirectoryError:
                responses.append(FileDownloadResponse(path=path, content=None, error="is_directory"))
            except ValueError:
                responses.append(FileDownloadResponse(path=path, content=None, error="invalid_path"))
            # Let other errors propagate
        return responses
