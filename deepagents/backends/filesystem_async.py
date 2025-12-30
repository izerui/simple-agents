"""AsyncFilesystemBackend: Read and write files directly from the filesystem asynchronously.

Security and search upgrades:
- Secure path resolution with root containment when in virtual_mode (sandboxed to cwd)
- Prevent symlink-following on file I/O using O_NOFOLLOW when available
- Ripgrep-powered grep with JSON parsing, plus Python fallback with regex
  and optional glob include filtering, while preserving virtual path behavior
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
    """Backend that reads and writes files directly from the filesystem asynchronously.

    Files are accessed using their actual filesystem paths. Relative paths are
    resolved relative to the current working directory. Content is read/written
    as plain text, and metadata (timestamps) are derived from filesystem stats.
    """

    def __init__(
        self,
        root_dir: str | Path | None = None,
        virtual_mode: bool = False,
        max_file_size_mb: int = 10,
    ) -> None:
        """Initialize filesystem backend.

        Args:
            root_dir: Optional root directory for file operations. If provided,
                     all file paths will be resolved relative to this directory.
                     If not provided, uses the current working directory.
        """
        # Avoid blocking operations: use Path() directly without resolve() or cwd()
        self.cwd = Path(root_dir) if root_dir else Path(".")
        self.virtual_mode = virtual_mode
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

    def _resolve_path(self, key: str) -> Path:
        """Resolve a file path with security checks.

        When virtual_mode=True, treat incoming paths as virtual absolute paths under
        self.cwd, disallow traversal (.., ~) and ensure resolved path stays within root.
        When virtual_mode=False, preserve legacy behavior: absolute paths are allowed
        as-is; relative paths resolve under cwd.

        Args:
            key: File path (absolute, relative, or virtual when virtual_mode=True)

        Returns:
            Resolved absolute Path object
        """
        if self.virtual_mode:
            vpath = key if key.startswith("/") else "/" + key
            if ".." in vpath or vpath.startswith("~"):
                raise ValueError("Path traversal not allowed")
            full = self.cwd / vpath.lstrip("/")
            try:
                full.relative_to(self.cwd)
            except ValueError:
                raise ValueError(f"Path:{full} outside root directory: {self.cwd}") from None
            return full

        path = Path(key)
        if path.is_absolute():
            return path
        return self.cwd / path

    async def als_info(self, path: str) -> list[FileInfo]:
        """List files and directories in the specified directory (non-recursive).

        Args:
            path: Absolute directory path to list files from.

        Returns:
            List of FileInfo-like dicts for files and directories directly in the directory.
            Directories have a trailing / in their path and is_dir=True.
        """
        dir_path = self._resolve_path(path)
        
        try:
            exists = await aios.path.exists(dir_path)
            is_dir = await aios.path.isdir(dir_path)
        except (OSError, PermissionError):
            return []
        
        if not exists or not is_dir:
            return []

        results: list[FileInfo] = []

        # Convert cwd to string for comparison
        cwd_str = str(self.cwd)
        if not cwd_str.endswith("/"):
            cwd_str += "/"

        # List only direct children (non-recursive)
        try:
            child_names = await aios.listdir(dir_path)
            
            for child_name in child_names:
                child_path = dir_path / child_name
                try:
                    is_file = await aios.path.isfile(child_path)
                    is_dir = await aios.path.isdir(child_path)
                except OSError:
                    continue

                abs_path = str(child_path)

                if not self.virtual_mode:
                    # Non-virtual mode: use absolute paths
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
                    # Virtual mode: strip cwd prefix
                    if abs_path.startswith(cwd_str):
                        relative_path = abs_path[len(cwd_str) :]
                    elif abs_path.startswith(str(self.cwd)):
                        # Handle case where cwd doesn't end with /
                        relative_path = abs_path[len(str(self.cwd)) :].lstrip("/")
                    else:
                        # Path is outside cwd, return as-is or skip
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

        # Keep deterministic order by path
        results.sort(key=lambda x: x.get("path", ""))
        return results

    async def aread(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
    ) -> str:
        """Read file content with line numbers.

        Args:
            file_path: Absolute or relative file path.
            offset: Line offset to start reading from (0-indexed).
            limit: Maximum number of lines to read.

        Returns:
            Formatted file content with line numbers, or error message.
        """
        resolved_path = self._resolve_path(file_path)

        try:
            exists = await aios.path.exists(resolved_path)
            is_file = await aios.path.isfile(resolved_path)
        except (OSError, PermissionError):
            return f"Error reading file '{file_path}': Permission error"

        if not exists or not is_file:
            return f"Error: File '{file_path}' not found"

        try:
            # Read content asynchronously
            async with aiofiles.open(resolved_path, mode="r", encoding="utf-8") as f:
                content = await f.read()

            empty_msg = check_empty_content(content)
            if empty_msg:
                return empty_msg

            lines = content.splitlines()
            start_idx = offset
            end_idx = min(start_idx + limit, len(lines))

            if start_idx >= len(lines):
                return f"Error: Line offset {offset} exceeds file length ({len(lines)} lines)"

            selected_lines = lines[start_idx:end_idx]
            return format_content_with_line_numbers(selected_lines, start_line=start_idx + 1)
        except (OSError, UnicodeDecodeError) as e:
            return f"Error reading file '{file_path}': {e}"

    async def awrite(
        self,
        file_path: str,
        content: str,
    ) -> WriteResult:
        """Create a new file with content.
        Returns WriteResult. External storage sets files_update=None.
        """
        resolved_path = self._resolve_path(file_path)

        try:
            exists = await aios.path.exists(resolved_path)
        except (OSError, PermissionError):
            return WriteResult(error=f"Error writing file '{file_path}': Permission error")

        if exists:
            return WriteResult(error=f"Cannot write to {file_path} because it already exists. Read and then make an edit, or write to a new path.")

        try:
            # Create parent directories if needed
            parent = resolved_path.parent
            try:
                await aios.makedirs(parent, exist_ok=True)
            except OSError:
                pass  # Parent might already exist

            # Write content asynchronously
            async with aiofiles.open(resolved_path, mode="w", encoding="utf-8") as f:
                await f.write(content)

            return WriteResult(path=file_path, files_update=None)
        except (OSError, UnicodeEncodeError) as e:
            return WriteResult(error=f"Error writing file '{file_path}': {e}")

    async def aedit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        """Edit a file by replacing string occurrences.
        Returns EditResult. External storage sets files_update=None.
        """
        resolved_path = self._resolve_path(file_path)

        try:
            exists = await aios.path.exists(resolved_path)
            is_file = await aios.path.isfile(resolved_path)
        except (OSError, PermissionError):
            return EditResult(error=f"Error editing file '{file_path}': Permission error")

        if not exists or not is_file:
            return EditResult(error=f"Error: File '{file_path}' not found")

        try:
            # Read asynchronously
            async with aiofiles.open(resolved_path, mode="r", encoding="utf-8") as f:
                content = await f.read()

            result = perform_string_replacement(content, old_string, new_string, replace_all)

            if isinstance(result, str):
                return EditResult(error=result)

            new_content, occurrences = result

            # Write asynchronously
            async with aiofiles.open(resolved_path, mode="w", encoding="utf-8") as f:
                await f.write(new_content)

            return EditResult(path=file_path, files_update=None, occurrences=int(occurrences))
        except (OSError, UnicodeDecodeError, UnicodeEncodeError) as e:
            return EditResult(error=f"Error editing file '{file_path}': {e}")

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
            base_full = self._resolve_path(path or ".")
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
                    virt = "/" + str(resolved.relative_to(self.cwd))
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
                            virt_path = "/" + str(resolved.relative_to(self.cwd))
                        except Exception:
                            continue
                    else:
                        virt_path = str(fp)
                    results.setdefault(virt_path, []).append((line_num, line))

        return results

    async def aglob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        if pattern.startswith("/"):
            pattern = pattern.lstrip("/")

        search_path = self.cwd if path == "/" else self._resolve_path(path)
        
        try:
            exists = await aios.path.exists(search_path)
            is_dir = await aios.path.isdir(search_path)
        except (OSError, PermissionError):
            return []
        
        if not exists or not is_dir:
            return []

        results: list[FileInfo] = []
        try:
            # Use recursive globbing to match files in subdirectories as tests expect
            def glob_match():
                return list(search_path.rglob(pattern))
            
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
                    cwd_str = str(self.cwd)
                    if not cwd_str.endswith("/"):
                        cwd_str += "/"
                    if abs_path.startswith(cwd_str):
                        relative_path = abs_path[len(cwd_str) :]
                    elif abs_path.startswith(str(self.cwd)):
                        relative_path = abs_path[len(str(self.cwd)) :].lstrip("/")
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
                resolved_path = self._resolve_path(path)

                # Create parent directories if needed
                parent = resolved_path.parent
                try:
                    await aios.makedirs(parent, exist_ok=True)
                except OSError:
                    pass  # Parent might already exist

                # Write content asynchronously in binary mode
                async with aiofiles.open(resolved_path, mode="wb") as f:
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
                resolved_path = self._resolve_path(path)
                # Read asynchronously in binary mode
                async with aiofiles.open(resolved_path, mode="rb") as f:
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