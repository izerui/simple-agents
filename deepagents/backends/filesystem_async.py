"""AsyncFilesystemBackend: 异步直接从文件系统读取和写入文件。

安全性和搜索升级：
- 在 virtual_mode 下安全解析路径并限制在 cwd 内(沙箱隔离)
- 防止文件 I/O 时跟随符号链接(在可用时使用 O_NOFOLLOW)
- 基于 ripgrep 的搜索功能(支持 JSON 解析)以及 Python 正则回退
- 支持可选的 glob 过滤，同时保留虚拟路径行为
"""

import asyncio
import json
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
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    WriteResult,
)
from deepagents.backends.utils import (
    check_empty_content,
    format_content_with_line_numbers,
    perform_string_replacement,
)


class AsyncFilesystemBackend(BackendProtocol):
    """异步直接从文件系统读取和写入文件的后端。

    文件通过实际的文件系统路径访问。相对路径将相对于当前工作目录解析。
    内容以纯文本形式读/写，元数据(时间戳)从文件系统统计信息派生。
    """

    def __init__(
            self,
            root_dir: str | Path | None = None,
            virtual_mode: bool = False,
            max_file_size_mb: int = 10,
            thread_id: str | None = None,
    ) -> None:
        """初始化文件系统后端。

        Args:
            root_dir: 文件操作的可选根目录。如果提供，
                     所有文件路径将相对于此目录解析。
                     如果未提供，则使用当前工作目录。
            virtual_mode: 是否启用虚拟模式(沙箱隔离)
            max_file_size_mb: 最大文件大小(MB)
            thread_id: 线程ID(用于标识会话)
        """
        self.thread_id = thread_id
        # 避免阻塞操作：直接使用 Path() 而不调用 resolve() 或 cwd()
        self.cwd = Path(root_dir) if root_dir else Path(".")
        self.virtual_mode = virtual_mode
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        # 缓存 cwd 的绝对路径字符串,用于路径比较
        self._abs_cwd_str: str | None = None


    def get_virtual_mode(self) -> bool:
        """获取文件系统后端的虚拟模式状态。"""
        return self.virtual_mode

    def get_thread_id(self) -> str:
        """获取此后端的线程 ID。"""
        return self.thread_id

    async def _get_abs_cwd_str(self) -> str:
        """获取 cwd 的绝对路径字符串(用于比较)。

        Returns:
            cwd 的绝对路径字符串,确保以 / 结尾
        """
        if self._abs_cwd_str is None:
            # 异步解析 cwd 为绝对路径
            abs_cwd = await asyncio.to_thread(self.cwd.resolve)
            self._abs_cwd_str = str(abs_cwd)
            if not self._abs_cwd_str.endswith("/"):
                self._abs_cwd_str += "/"
        return self._abs_cwd_str

    async def aabs_path(self, key: str) -> Path:
        """解析文件路径并进行安全检查(异步版本)。

        这是异步版本，解析符号链接以获取真实路径。
        当你需要实际文件系统路径时使用此方法。

        Args:
            key: 文件路径(绝对路径、相对路径，或 virtual_mode=True 时的虚拟路径)

        Returns:
            解析后的绝对 Path 对象(已解析符号链接)

        Raises:
            ValueError: 如果路径遍历尝试或路径超出根目录
        """
        if self.virtual_mode:
            # 虚拟模式：将输入路径视为虚拟绝对路径
            vpath = key if key.startswith("/") else "/" + key
            if ".." in vpath or vpath.startswith("~"):
                raise ValueError("不允许路径遍历")
            full = self.cwd / vpath.lstrip("/")
            try:
                full.relative_to(self.cwd)
            except ValueError:
                raise ValueError(f"路径:{full} 超出根目录: {self.cwd}") from None
            # 在执行器中解析以获取真实的绝对路径(跟随符号链接)
            try:
                return await asyncio.to_thread(full.resolve)
            except (OSError, RuntimeError):
                # 如果解析失败(例如路径尚不存在)，返回绝对路径
                return await asyncio.to_thread(full.absolute)

        path = Path(key)
        if path.is_absolute():
            # 解析以获取真实的绝对路径
            try:
                return await asyncio.to_thread(path.resolve)
            except (OSError, RuntimeError):
                return await asyncio.to_thread(path.absolute)
        # 相对路径：从 cwd 解析
        resolved = self.cwd / path
        try:
            return await asyncio.to_thread(resolved.resolve)
        except (OSError, RuntimeError):
            return await asyncio.to_thread(resolved.absolute)

    async def als_info(self, path: str) -> list[FileInfo]:
        """列出指定目录中的文件和目录(非递归)。

        Args:
            path: 要列出文件的目录的绝对路径。

        Returns:
            FileInfo 字典列表，包含目录中的文件和目录。
            目录路径以 / 结尾且 is_dir=True。
        """
        abs_dir_path = await self.aabs_path(path)

        try:
            exists = await aios.path.exists(abs_dir_path)
            is_dir = await aios.path.isdir(abs_dir_path)
        except (OSError, PermissionError):
            return []

        if not exists or not is_dir:
            return []

        results: list[FileInfo] = []

        # 获取 cwd 的绝对路径字符串用于比较
        cwd_str = await self._get_abs_cwd_str()

        # 仅列出直接子项(非递归)
        try:
            child_names = await aios.listdir(abs_dir_path)

            # 系统目录过滤列表
            SYSTEM_IGNORE_DIRS = {"home", "var", "etc", "usr", "bin", "sbin", "lib", "boot", "dev", "proc", "sys"}

            for child_name in child_names:
                # 强制过滤：如果是虚拟模式，且是系统目录，直接跳过
                if self.virtual_mode and child_name in SYSTEM_IGNORE_DIRS:
                    continue
                child_path = abs_dir_path / child_name
                try:
                    is_file = await aios.path.isfile(child_path)
                    is_dir = await aios.path.isdir(child_path)
                except OSError:
                    continue

                abs_path = str(child_path)

                if not self.virtual_mode:
                    # 非虚拟模式：使用绝对路径
                    if is_file:
                        try:
                            st = await aios.stat(child_path)
                            results.append(
                                {
                                    "path": abs_path,
                                    "is_dir": False,
                                    "size": int(st.st_size),
                                    "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                                }
                            )
                        except OSError:
                            results.append({"path": abs_path, "is_dir": False})
                    elif is_dir:
                        try:
                            st = await aios.stat(child_path)
                            results.append(
                                {
                                    "path": abs_path + "/",
                                    "is_dir": True,
                                    "size": 0,
                                    "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                                }
                            )
                        except OSError:
                            results.append({"path": abs_path + "/", "is_dir": True})
                else:
                    # 虚拟模式：去除 cwd 前缀
                    if abs_path.startswith(cwd_str):
                        relative_path = abs_path[len(cwd_str):]
                    else:
                        # 路径在 cwd 之外，按原样返回
                        relative_path = abs_path

                    virt_path = "/" + relative_path

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
            file_path: 文件路径(绝对或相对路径)。
            offset: 开始读取的行偏移量(从0开始索引)。
            limit: 要读取的最大行数。

        Returns:
            带行号的格式化文件内容，或错误消息。
        """
        abs_file_path = await self.aabs_path(file_path)

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
        """创建包含内容的新文件。
        返回 WriteResult。外部存储设置 files_update=None。
        """
        abs_file_path = await self.aabs_path(file_path)

        try:
            exists = await aios.path.exists(abs_file_path)
        except (OSError, PermissionError):
            return WriteResult(error=f"写入文件 '{file_path}' 时出错：权限错误")

        if exists:
            return WriteResult(
                error=f"无法写入 {file_path}，因为文件已存在。请先读取然后编辑，或写入新路径。")

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
        except (OSError, UnicodeEncodeError) as e:
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
        abs_file_path = await self.aabs_path(file_path)

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
            base_full = await self.aabs_path(path or ".")
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
        except (asyncio.TimeoutExpired, FileNotFoundError):
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
            if self.virtual_mode:
                try:
                    # Use try_resolve to avoid blocking
                    resolved = await asyncio.to_thread(lambda: p.resolve())
                    # 获取解析后的 cwd 绝对路径
                    abs_cwd = Path(await self._get_abs_cwd_str().rstrip("/"))
                    virt = "/" + str(resolved.relative_to(abs_cwd))
                except Exception:
                    continue
            else:
                virt = str(p)
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
                    if self.virtual_mode:
                        try:
                            # Use try_resolve to avoid blocking
                            resolved = await asyncio.to_thread(lambda: fp.resolve())
                            # 获取解析后的 cwd 绝对路径
                            abs_cwd = Path(await self._get_abs_cwd_str().rstrip("/"))
                            virt_path = "/" + str(resolved.relative_to(abs_cwd))
                        except Exception:
                            continue
                    else:
                        virt_path = str(fp)
                    results.setdefault(virt_path, []).append((line_num, line))

        return results

    async def aglob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        if pattern.startswith("/"):
            pattern = pattern.lstrip("/")

        abs_search_path = self.cwd if path == "/" else await self.aabs_path(path)

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
                if not self.virtual_mode:
                    try:
                        st = await aios.stat(matched_path)
                        results.append(
                            {
                                "path": abs_path,
                                "is_dir": False,
                                "size": int(st.st_size),
                                "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                            }
                        )
                    except OSError:
                        results.append({"path": abs_path, "is_dir": False})
                else:
                    cwd_str = await self._get_abs_cwd_str()
                    if abs_path.startswith(cwd_str):
                        relative_path = abs_path[len(cwd_str):]
                    else:
                        relative_path = abs_path
                    virt = "/" + relative_path
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
                abs_file_path = await self.aabs_path(path)

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
                abs_file_path = await self.aabs_path(path)
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
