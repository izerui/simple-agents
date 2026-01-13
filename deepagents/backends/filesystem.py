"""FilesystemBackend: Read and write files directly from the filesystem.

Security and search upgrades:
- Secure path resolution with root containment (sandboxed to thread_dir)
- Prevent symlink-following on file I/O using O_NOFOLLOW when available
- Ripgrep-powered grep with JSON parsing, plus Python fallback with regex
  and optional glob include filtering, while preserving virtual path behavior
"""

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import wcmatch.glob as wcglob

from deepagents.backends.protocol import (
    BackendProtocol,
    EditResult,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    WriteResult, ExecuteResponse,
)
from deepagents.backends.utils import (
    check_empty_content,
    format_content_with_line_numbers,
    perform_string_replacement,
)


class FilesystemBackend(BackendProtocol): # class FilesystemBackend(SandboxBackendProtocol):  支持执行命令
    """Backend that reads and writes files directly from the filesystem.

    All file operations are relative to thread_dir, providing sandbox isolation.
    Incoming and returned paths are virtual paths (relative to thread_dir, starting with /).
    Content is read/written as plain text, and metadata (timestamps) are derived from filesystem stats.
    """

    def __init__(
        self,
        thread_dir: str | Path | None = None,
        max_file_size_mb: int = 10,
        thread_id: str | None = None,
    ) -> None:
        """Initialize filesystem backend.

        Args:
            thread_dir: Root directory for file operations. If provided,
                       all file paths will be resolved relative to this directory.
                       If not provided, uses the current working directory.
            max_file_size_mb: Maximum file size in MB
            thread_id: Thread ID (for session identification)
        """
        self.thread_id = thread_id
        # Simplified path handling: use strings instead of Path objects
        # Normalize thread_dir, remove ./ prefix
        thread_dir_str = str(thread_dir) if thread_dir else "."
        if thread_dir_str.startswith("./"):
            thread_dir_str = thread_dir_str[2:]
        elif thread_dir_str == ".":
            thread_dir_str = ""
        self.thread_dir = thread_dir_str
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

    def get_thread_id(self) -> str | None:
        """Get the thread ID for this backend."""
        return self.thread_id

    def prepend_thread_dir(self, key: str) -> str:
        """Concatenate thread_dir prefix and perform security checks.

        Joins the input virtual path with thread_dir to form an actual path.
        Supports various path formats:
        - Absolute virtual paths starting with / (relative to thread_dir)
        - Relative paths starting with ./
        - Direct filenames (relative)

        Does not support path traversal (like ../), raises ValueError.

        Args:
            key: File path

        Returns:
            Actual path string under thread_dir

        Raises:
            ValueError: If path traversal is attempted (using ../)
        """
        # Normalize input path, only remove / as virtual path marker (does not affect hidden dirs)
        if key.startswith("/"):
            key = key[1:]

        # Remove ./ as relative path marker (but keep hidden dir .)
        if key.startswith("./"):
            key = key[2:]

        # Check for path traversal
        if "../" in key or key.startswith(".."):
            raise ValueError("Path traversal not allowed")

        # Join path
        if not self.thread_dir:
            return key
        elif self.thread_dir.endswith("/") or key.startswith("/"):
            return self.thread_dir + key
        else:
            return self.thread_dir + "/" + key

    def remove_thread_dir_prefix(self, abs_path: str) -> str:
        """Remove thread_dir prefix.

        Converts an actual path to a virtual path relative to thread_dir.
        Regardless of where the actual path is, the return is always relative to thread_dir.

        Args:
            abs_path: Actual path string

        Returns:
            Virtual path string (relative to thread_dir, starting with /)
        """
        # Ensure thread_dir ends with / for easy joining
        if not self.thread_dir:
            return "/" + abs_path if not abs_path.startswith("/") else abs_path
        thread_dir = self.thread_dir if self.thread_dir.endswith("/") else self.thread_dir + "/"

        # Remove thread_dir prefix
        if abs_path.startswith(thread_dir):
            virtual_path = abs_path[len(thread_dir):]
        else:
            # If not under thread_dir, use original path as-is (or return /)
            virtual_path = abs_path

        # Normalize: ensure starting with / (except . and ../)
        if virtual_path and virtual_path != "." and not virtual_path.startswith("../"):
            if not virtual_path.startswith("/"):
                virtual_path = "/" + virtual_path

        return virtual_path

    def ls_info(self, path: str) -> list[FileInfo]:
        """List files and directories in the specified directory (non-recursive).

        Args:
            path: Virtual path of the directory to list files from.

        Returns:
            List of FileInfo-like dicts for files and directories directly in the directory.
            Directories have a trailing / in their path and is_dir=True.
        """
        abs_dir_path = Path(self.prepend_thread_dir(path))

        if not abs_dir_path.exists() or not abs_dir_path.is_dir():
            return []

        results: list[FileInfo] = []

        # List only direct children (non-recursive)
        try:
            for child_path in abs_dir_path.iterdir():
                try:
                    is_file = child_path.is_file()
                    is_dir = child_path.is_dir()
                except OSError:
                    continue

                abs_path = str(child_path)

                # Use remove_thread_dir_prefix method to convert to virtual path
                virt_path = self.remove_thread_dir_prefix(abs_path)

                if is_file:
                    try:
                        st = child_path.stat()
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
                        st = child_path.stat()
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

    def read(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
    ) -> str:
        """Read file content with line numbers.

        Args:
            file_path: Virtual file path.
            offset: Line offset to start reading from (0-indexed).
            limit: Maximum number of lines to read.

        Returns:
            Formatted file content with line numbers, or error message.
        """
        resolved_path = Path(self.prepend_thread_dir(file_path))

        if not resolved_path.exists() or not resolved_path.is_file():
            return f"Error: File '{file_path}' not found"

        try:
            # Open with O_NOFOLLOW where available to avoid symlink traversal
            fd = os.open(resolved_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "r", encoding="utf-8") as f:
                content = f.read()

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

    def write(
        self,
        file_path: str,
        content: str,
    ) -> WriteResult:
        """Create a new file with content.
        Returns WriteResult. External storage sets files_update=None.
        """
        resolved_path = Path(self.prepend_thread_dir(file_path))

        if resolved_path.exists():
            # In async version, write overwrites. Original filesystem.py prevented overwrite.
            # Assuming we follow AsyncFilesystemBackend behavior: overwrite is allowed.
            # However, strictly following fs_async logic: just try to create/overwrite.
            pass

        try:
            # Create parent directories if needed
            try:
                resolved_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass  # Parent might already exist

            # Prefer O_NOFOLLOW to avoid writing through symlinks
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(resolved_path, flags, 0o644)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)

            return WriteResult(path=self.remove_thread_dir_prefix(file_path), files_update=None)
        except (OSError, UnicodeEncodeError) as e:
            return WriteResult(error=f"Error writing file '{self.remove_thread_dir_prefix(file_path)}': {e}")

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        """Edit a file by replacing string occurrences.
        Returns EditResult. External storage sets files_update=None.
        """
        resolved_path = Path(self.prepend_thread_dir(file_path))

        if not resolved_path.exists() or not resolved_path.is_file():
            return EditResult(error=f"Error: File '{file_path}' not found")

        try:
            # Read securely
            fd = os.open(resolved_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "r", encoding="utf-8") as f:
                content = f.read()

            result = perform_string_replacement(content, old_string, new_string, replace_all)

            if isinstance(result, str):
                return EditResult(error=result)

            new_content, occurrences = result

            # Write securely
            flags = os.O_WRONLY | os.O_TRUNC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(resolved_path, flags)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new_content)

            return EditResult(path=self.remove_thread_dir_prefix(file_path), files_update=None, occurrences=int(occurrences))
        except (OSError, UnicodeDecodeError, UnicodeEncodeError) as e:
            return EditResult(error=f"Error editing file '{self.remove_thread_dir_prefix(file_path)}': {e}")

    def grep_raw(
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

        if not base_full.exists():
            return []

        # Try ripgrep first
        results = self._ripgrep_search(pattern, base_full, glob)
        if results is None:
            results = self._python_search(pattern, base_full, glob)

        matches: list[GrepMatch] = []
        for fpath, items in results.items():
            for line_num, line_text in items:
                matches.append({"path": fpath, "line": int(line_num), "text": line_text})
        return matches

    def _ripgrep_search(self, pattern: str, base_full: Path, include_glob: str | None) -> dict[str, list[tuple[int, str]]] | None:
        cmd = ["rg", "--json"]
        if include_glob:
            cmd.extend(["--glob", include_glob])
        cmd.extend(["--", pattern, str(base_full)])

        try:
            proc = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (TimeoutError, FileNotFoundError):
            return None

        results: dict[str, list[tuple[int, str]]] = {}
        for line in proc.stdout.splitlines():
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
                # Convert actual path to virtual path
                virt = self.remove_thread_dir_prefix(str(p))
            except Exception:
                continue
            ln = pdata.get("line_number")
            lt = pdata.get("lines", {}).get("text", "").rstrip("\n")
            if ln is None:
                continue
            results.setdefault(virt, []).append((int(ln), lt))

        return results

    def _python_search(self, pattern: str, base_full: Path, include_glob: str | None) -> dict[str, list[tuple[int, str]]]:
        try:
            regex = re.compile(pattern)
        except re.error:
            return {}

        results: dict[str, list[tuple[int, str]]] = {}
        root = base_full if base_full.is_dir() else base_full.parent

        for fp in root.rglob("*"):
            if not fp.is_file():
                continue
            if include_glob and not wcglob.globmatch(fp.name, include_glob, flags=wcglob.BRACE):
                continue
            try:
                if fp.stat().st_size > self.max_file_size_bytes:
                    continue
            except OSError:
                continue
            try:
                content = fp.read_text()
            except (UnicodeDecodeError, PermissionError, OSError):
                continue
            for line_num, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    try:
                        # Convert actual path to virtual path
                        virt_path = self.remove_thread_dir_prefix(str(fp))
                    except Exception:
                        continue
                    results.setdefault(virt_path, []).append((line_num, line))

        return results

    def glob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        if pattern.startswith("/"):
            pattern = pattern.lstrip("/")

        search_path = Path(self.thread_dir) if path == "/" else Path(self.prepend_thread_dir(path))

        if not search_path.exists() or not search_path.is_dir():
            return []

        results: list[FileInfo] = []
        try:
            # Use recursive globbing to match files in subdirectories as tests expect
            for matched_path in search_path.rglob(pattern):
                try:
                    is_file = matched_path.is_file()
                except OSError:
                    continue
                if not is_file:
                    continue

                abs_path = str(matched_path)
                virt = self.remove_thread_dir_prefix(abs_path)
                try:
                    st = matched_path.stat()
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

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload multiple files to the filesystem.

        Args:
            files: List of (path, content) tuples where content is bytes.

        Returns:
            List of FileUploadResponse objects, one per input file.
            Response order matches input order.
        """
        responses: list[FileUploadResponse] = []
        for path, content in files:
            try:
                resolved_path = Path(self.prepend_thread_dir(path))

                # Create parent directories if needed
                try:
                    resolved_path.parent.mkdir(parents=True, exist_ok=True)
                except OSError:
                    pass  # Parent might already exist

                flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                if hasattr(os, "O_NOFOLLOW"):
                    flags |= os.O_NOFOLLOW
                fd = os.open(resolved_path, flags, 0o644)
                with os.fdopen(fd, "wb") as f:
                    f.write(content)

                responses.append(FileUploadResponse(path=path, error=None))
            except FileNotFoundError:
                responses.append(FileUploadResponse(path=path, error="file_not_found"))
            except PermissionError:
                responses.append(FileUploadResponse(path=path, error="permission_denied"))
            except (ValueError, OSError) as e:
                # ValueError from prepend_thread_dir for path traversal, OSError for other file errors
                if isinstance(e, ValueError) or "invalid" in str(e).lower():
                    responses.append(FileUploadResponse(path=path, error="invalid_path"))
                else:
                    # Generic error fallback
                    responses.append(FileUploadResponse(path=path, error="invalid_path"))

        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download multiple files from the filesystem.

        Args:
            paths: List of file paths to download.

        Returns:
            List of FileDownloadResponse objects, one per input path.
        """
        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                resolved_path = Path(self.prepend_thread_dir(path))
                # Use flags to optionally prevent symlink following if
                # supported by the OS
                fd = os.open(resolved_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                with os.fdopen(fd, "rb") as f:
                    content = f.read()
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