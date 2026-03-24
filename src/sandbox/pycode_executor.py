# -*- coding: utf-8 -*-
"""
受限 Python 执行器（只支持标准执行格式）

实现基于受限 open() 函数的文件访问控制：
1. 相对路径
 - 自动添加 root_dir 前缀
2. 绝对路径
 - 在root_dir内可读写
 - 只读白名单内可读
 - 读写白名单内可读写
 - 自动添加 root_dir 前缀后可读写

进程隔离方案：
- 每次代码执行在独立子进程中进行
- 使用 multiprocessing.Queue 进行进程间通信
- 不需要 root 权限

限制机制：
1. 受限 open() 函数：控制文件访问权限
2. 受限 os/pathlib/io/shutil 模块：统一文件访问语义
3. 进程隔离：每个执行在独立子进程，避免污染主进程
4. 超时保护：防止无限循环和资源耗尽
5. 输出限制：防止输出过大

可用和禁用的 os 函数：
✅ 可用：os.remove, os.rmdir, os.mkdir, os.listdir, os.path.exists 等
⚠️ 受限：os.open 仅支持受控路径；os.write、os.fdopen 未开放

支持三种标准执行格式：
1. python -c "单行pyscript" - 直接执行代码字符串
2. python script.py [args...] - 执行脚本文件(支持参数)
3. python << 'EOF' - 使用 heredoc 执行多行代码（推荐）

heredoc 格式优势：
- 支持多行代码，无需所有代码写在同一行
- 代码中可直接使用单引号、双引号，无需转义
- 代码可读性更好
"""
import sys
import io
import json
import os
import re
import signal
import shlex
import shutil
import traceback
import tempfile
from datetime import datetime
from pathlib import Path
from multiprocessing import Process, Queue
from deepagents.backends.protocol import ExecuteResponse


class ExecuteResult:
    """子进程执行结果"""

    def __init__(self, output, exit_code, error=None):
        self.output = output
        self.exit_code = exit_code
        self.error = error


class OutputCapture:
    """捕获 print 和其他输出"""

    def __init__(self):
        self.stdout_buffer = io.StringIO()
        self.stderr_buffer = io.StringIO()
        self._original_stdout = None
        self._original_stderr = None

    def __enter__(self):
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = self.stdout_buffer
        sys.stderr = self.stderr_buffer
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr

    def get_output(self):
        """获取所有输出"""
        output = ""
        # 添加 stdout 和 stderr
        stdout = self.stdout_buffer.getvalue()
        stderr = self.stderr_buffer.getvalue()
        output += stdout
        if stderr:
            output += "\n[错误输出]\n{0}".format(stderr)
        return output

    def append_stdout(self, message):
        """向 stdout 捕获缓冲追加调试信息"""
        self.stdout_buffer.write(message)
        if message and not message.endswith("\n"):
            self.stdout_buffer.write("\n")


def _execute_in_subprocess(
        code,
        root_dir,
        script_path,
        script_args,
        result_queue,
        timeout,
        writable_paths,
        readable_paths
):
    """
    在子进程中执行代码

    Args:
        code: 要执行的代码
        root_dir: 沙箱根目录
        script_path: 脚本文件名（如 'test.py'），如果是代码字符串则为 None
        script_args: 脚本参数列表
        result_queue: 结果队列（用于传递结果回主进程）
        timeout: 超时时间（秒）
        writable_paths: 可写路径列表
        readable_paths: 只读白名单路径列表
    """
    try:
        with OutputCapture() as output_capture:
            # 切换工作目录
            os.chdir(root_dir)
            print("开始执行 Python 任务")
            print("工作目录: /")
            if script_path:
                print("执行方式: script")
                print("脚本路径: {0}".format(script_path))
            else:
                print("执行方式: inline")

            # 设置超时信号
            def timeout_handler(signum, frame):
                raise TimeoutError("代码执行超时（超过 {0} 秒）".format(timeout))

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout)

            source_name = script_path if script_path else '<sandbox>'

            # 编译代码
            try:
                compiled_code = compile(code, source_name, 'exec')
            except SyntaxError as e:
                output_capture.append_stdout("语法错误: {0}".format(str(e)))
                result_queue.put(ExecuteResult(
                    output=output_capture.get_output(),
                    exit_code=-1,
                    error=str(e)
                ))
                return

            # 准备执行环境
            import builtins

            # 预先导入 os.path（避免在 RestrictedOS.__getattr__ 中导入导致递归）
            import os.path as _original_os_path

            # 创建受限制的 open 函数
            original_open = open
            root_path = Path(root_dir).resolve()
            writable_resolved = [Path(p).resolve() for p in writable_paths]
            readable_resolved = [Path(p).resolve() for p in readable_paths]

            def _is_within(path_obj, parent):
                try:
                    path_obj.relative_to(parent)
                    return True
                except ValueError:
                    return False

            def _resolve_path(path_str):
                file_path = Path(path_str).expanduser()
                if file_path.is_absolute():
                    return file_path.resolve()
                return (root_path / file_path).resolve()

            def _classify_path(resolved_path):
                if _is_within(resolved_path, root_path):
                    return 'root'
                for wp in writable_resolved:
                    if _is_within(resolved_path, wp):
                        return 'writable'
                for rp in readable_resolved:
                    if _is_within(resolved_path, rp):
                        return 'readable'
                return 'other'

            def _remap_external_absolute(file_path):
                return root_path / file_path.relative_to(file_path.anchor)

            def _redirect_for_read(path_str):
                file_path = Path(path_str).expanduser()
                if file_path.is_absolute():
                    resolved = file_path.resolve()
                    if _classify_path(resolved) == 'other':
                        return _remap_external_absolute(file_path)
                    return resolved
                return root_path / file_path

            def _redirect_for_write(path_str):
                file_path = Path(path_str).expanduser()
                if file_path.is_absolute():
                    resolved = file_path.resolve()
                    location = _classify_path(resolved)
                    if location == 'readable':
                        raise PermissionError("只读路径，禁止写入: {0}".format(path_str))
                    if location == 'other':
                        return _remap_external_absolute(file_path)
                    return resolved
                return root_path / file_path

            def _resolve_for_operation(path_str, operation):
                if operation == 'read':
                    return _redirect_for_read(path_str)
                if operation in ('write', 'delete'):
                    return _redirect_for_write(path_str)
                raise ValueError("不支持的操作类型: {0}".format(operation))

            def redirect_path(path_str):
                """
                读取类路径使用统一重定向规则：
                - 相对路径落到 root_dir
                - root_dir/readable/writable 内保持原位
                - 其他绝对路径映射到 root_dir
                """
                return str(_resolve_for_operation(path_str, 'read'))

            def restricted_open(file, mode='r', *args, **kwargs):
                """
                受限的 open 函数，严格按照顺序检查：

                路径处理顺序：
                1. 相对路径：自动添加 root_dir 前缀

                绝对路径检查顺序：
                2. 在root_dir内：可读写
                3. 只读白名单（readable_paths）内：只读
                4. 读写白名单（writable_paths）内：可读写
                5. 其他绝对路径：自动添加 root_dir 前缀后可读写
                """
                mode_str = mode if isinstance(mode, str) else 'r'
                is_writing = any(c in mode_str for c in ['w', 'a', '+', 'x'])
                operation = 'write' if is_writing else 'read'
                final_path = str(_resolve_for_operation(file, operation))

                # 写入模式下自动创建父目录
                if is_writing and final_path:
                    parent_dir = Path(final_path).parent
                    if not parent_dir.exists():
                        parent_dir.mkdir(parents=True, exist_ok=True)

                return original_open(final_path, mode, *args, **kwargs)

            # 创建受限的 Path 类
            class _RestrictedPath(Path):
                """受限的 Path 类，所有操作都经过权限检查"""
                def __new__(cls, *args, **kwargs):
                    # 创建 Path 实例
                    if len(args) == 1 and isinstance(args[0], _RestrictedPath):
                        return args[0]
                    return super(_RestrictedPath, cls).__new__(cls, *args, **kwargs)

                def open(self, mode='r', *args, **kwargs):
                    return restricted_open(str(self), mode, *args, **kwargs)

                def write_text(self, data, *args, **kwargs):
                    with self.open('w', *args, **kwargs) as f:
                        return f.write(data)

                def read_text(self, *args, **kwargs):
                    with self.open('r', *args, **kwargs) as f:
                        return f.read()

                def write_bytes(self, data, *args, **kwargs):
                    with self.open('wb', *args, **kwargs) as f:
                        return f.write(data)

                def read_bytes(self, *args, **kwargs):
                    with self.open('rb', *args, **kwargs) as f:
                        return f.read()

                def exists(self):
                    return os.path.exists(redirect_path(str(self)))

                def is_file(self):
                    return os.path.isfile(redirect_path(str(self)))

                def is_dir(self):
                    return os.path.isdir(redirect_path(str(self)))

                def stat(self, *args, **kwargs):
                    return os.stat(redirect_path(str(self)), *args, **kwargs)

                def lstat(self, *args, **kwargs):
                    return os.lstat(redirect_path(str(self)), *args, **kwargs)

                def mkdir(self, mode=0o777, parents=False, exist_ok=False):
                    target = str(_resolve_for_operation(str(self), 'write'))
                    if parents:
                        return os.makedirs(target, mode=mode, exist_ok=exist_ok)
                    return os.mkdir(target, mode=mode)

                def rmdir(self):
                    target = str(_resolve_for_operation(str(self), 'delete'))
                    return os.rmdir(target)

                def unlink(self, missing_ok=False):
                    target = str(_resolve_for_operation(str(self), 'delete'))
                    try:
                        return os.unlink(target)
                    except FileNotFoundError:
                        if missing_ok:
                            return None
                        raise

                def rename(self, target):
                    src = str(_resolve_for_operation(str(self), 'read'))
                    dst = str(_resolve_for_operation(str(target), 'write'))
                    return self.__class__(os.rename(src, dst))

                def replace(self, target):
                    src = str(_resolve_for_operation(str(self), 'read'))
                    dst = str(_resolve_for_operation(str(target), 'write'))
                    return self.__class__(os.replace(src, dst))

                def touch(self, mode=0o666, exist_ok=True):
                    target = str(_resolve_for_operation(str(self), 'write'))
                    parent_dir = Path(target).parent
                    if not parent_dir.exists():
                        parent_dir.mkdir(parents=True, exist_ok=True)
                    if exist_ok:
                        try:
                            os.utime(target, None)
                        except OSError:
                            pass
                        else:
                            return None

                    flags = os.O_CREAT | os.O_WRONLY
                    if not exist_ok:
                        flags |= os.O_EXCL
                    fd = os.open(target, flags, mode)
                    os.close(fd)
                    return None

                def chmod(self, mode, *, follow_symlinks=True):
                    target = str(_resolve_for_operation(str(self), 'write'))
                    return os.chmod(target, mode, follow_symlinks=follow_symlinks)

                def symlink_to(self, target_is_directory=False):
                    raise AttributeError("Path.symlink_to 未开放")

                def hardlink_to(self, target):
                    raise AttributeError("Path.hardlink_to 未开放")

                def iterdir(self):
                    target = str(_resolve_for_operation(str(self), 'read'))
                    for entry in os.listdir(target):
                        yield self.__class__(str(Path(target) / entry))

                def glob(self, pattern):
                    target = Path(_resolve_for_operation(str(self), 'read'))
                    for entry in target.glob(pattern):
                        yield self.__class__(str(entry))

                def rglob(self, pattern):
                    target = Path(_resolve_for_operation(str(self), 'read'))
                    for entry in target.rglob(pattern):
                        yield self.__class__(str(entry))

            # 创建受限的 pathlib 模块
            import pathlib as _original_pathlib

            class _RestrictedPathlibModule:
                """受限的 pathlib 模块"""
                Path = _RestrictedPath
                PurePath = _original_pathlib.PurePath
                PosixPath = _original_pathlib.PosixPath if hasattr(_original_pathlib, 'PosixPath') else _RestrictedPath
                WindowsPath = _original_pathlib.WindowsPath if hasattr(_original_pathlib, 'WindowsPath') else _RestrictedPath

            class RestrictedPathlib:
                """受限的 pathlib 模块包装器"""
                def __init__(self):
                    object.__setattr__(self, '_module', _RestrictedPathlibModule())

                def __getattr__(self, name):
                    return getattr(self._module, name)

                def __setattr__(self, name, value):
                    raise AttributeError("不能修改 pathlib 模块")

            # 创建受限的 os 模块
            class RestrictedOS:
                """受限的 os 模块，只禁用真正危险的函数，其他函数会进行路径重定向"""

                def _redirect_path_args(self, args):
                    """重定向函数参数中的路径"""
                    if not args:
                        return args
                    redirected = [redirect_path(args[0])] + list(args[1:])
                    return tuple(redirected)

                def mkdir(self, path, *args, **kwargs):
                    redirected_path = str(_resolve_for_operation(path, 'write'))
                    return os.mkdir(redirected_path, *args, **kwargs)

                def makedirs(self, path, *args, **kwargs):
                    redirected_path = str(_resolve_for_operation(path, 'write'))
                    return os.makedirs(redirected_path, *args, **kwargs)

                def remove(self, path, *args, **kwargs):
                    redirected_path = str(_resolve_for_operation(path, 'delete'))
                    return os.remove(redirected_path, *args, **kwargs)

                def unlink(self, path, *args, **kwargs):
                    redirected_path = str(_resolve_for_operation(path, 'delete'))
                    return os.unlink(redirected_path, *args, **kwargs)

                def rmdir(self, path, *args, **kwargs):
                    redirected_path = str(_resolve_for_operation(path, 'delete'))
                    return os.rmdir(redirected_path, *args, **kwargs)

                def removedirs(self, path, *args, **kwargs):
                    redirected_path = str(_resolve_for_operation(path, 'delete'))
                    return os.removedirs(redirected_path, *args, **kwargs)

                def listdir(self, path):
                    return os.listdir(redirect_path(path))

                def stat(self, path, *args, **kwargs):
                    return os.stat(redirect_path(path), *args, **kwargs)

                def lstat(self, path, *args, **kwargs):
                    return os.lstat(redirect_path(path), *args, **kwargs)

                def rename(self, src, dst, *args, **kwargs):
                    src_redirected = str(_resolve_for_operation(src, 'read'))
                    dst_redirected = str(_resolve_for_operation(dst, 'write'))
                    return os.rename(src_redirected, dst_redirected, *args, **kwargs)

                def replace(self, src, dst, *args, **kwargs):
                    src_redirected = str(_resolve_for_operation(src, 'read'))
                    dst_redirected = str(_resolve_for_operation(dst, 'write'))
                    return os.replace(src_redirected, dst_redirected, *args, **kwargs)

                def renames(self, src, dst, *args, **kwargs):
                    src_redirected = str(_resolve_for_operation(src, 'read'))
                    dst_redirected = str(_resolve_for_operation(dst, 'write'))
                    return os.renames(src_redirected, dst_redirected, *args, **kwargs)

                def scandir(self, path='.'):
                    redirected_path = str(_resolve_for_operation(path, 'read'))
                    return os.scandir(redirected_path)

                def walk(self, top, *args, **kwargs):
                    redirected_top = str(_resolve_for_operation(top, 'read'))
                    return os.walk(redirected_top, *args, **kwargs)

                def open(self, path, flags, mode=0o777, *, dir_fd=None):
                    if dir_fd is not None:
                        raise NotImplementedError("受限 os.open 暂不支持 dir_fd")

                    write_flags = (
                        os.O_WRONLY |
                        os.O_RDWR |
                        os.O_APPEND |
                        os.O_CREAT |
                        os.O_TRUNC
                    )
                    operation = 'write' if flags & write_flags else 'read'
                    redirected_path = str(_resolve_for_operation(path, operation))
                    return os.open(redirected_path, flags, mode)

                def chmod(self, path, mode, *, dir_fd=None, follow_symlinks=True):
                    if dir_fd is not None:
                        raise NotImplementedError("受限 os.chmod 暂不支持 dir_fd")
                    redirected_path = str(_resolve_for_operation(path, 'write'))
                    return os.chmod(redirected_path, mode, follow_symlinks=follow_symlinks)

                def utime(self, path, times=None, *, ns=None, dir_fd=None, follow_symlinks=True):
                    if dir_fd is not None:
                        raise NotImplementedError("受限 os.utime 暂不支持 dir_fd")
                    redirected_path = str(_resolve_for_operation(path, 'write'))
                    kwargs = {'follow_symlinks': follow_symlinks}
                    if ns is not None:
                        kwargs['ns'] = ns
                        return os.utime(redirected_path, None if times is None else times, **kwargs)
                    return os.utime(redirected_path, times, **kwargs)

                def truncate(self, path, length):
                    if isinstance(path, int):
                        return os.truncate(path, length)
                    redirected_path = str(_resolve_for_operation(path, 'write'))
                    return os.truncate(redirected_path, length)

                def symlink(self, src, dst, *args, **kwargs):
                    raise AttributeError("os.symlink 未开放")

                def link(self, src, dst, *args, **kwargs):
                    raise AttributeError("os.link 未开放")

                def __getattr__(self, name):
                    if name == 'path':
                        class RestrictedOsPath:
                            """受限的 os.path 模块，确保所有路径都经过重定向"""

                            def __init__(self):
                                object.__setattr__(self, '_module', _original_os_path)

                            def exists(self, path):
                                return self._module.exists(redirect_path(path))

                            def isfile(self, path):
                                return self._module.isfile(redirect_path(path))

                            def isdir(self, path):
                                return self._module.isdir(redirect_path(path))

                            def join(self, *paths):
                                if not paths:
                                    return ''
                                joined = self._module.join(*paths)
                                return redirect_path(joined)

                            def dirname(self, path):
                                return self._module.dirname(redirect_path(path))

                            def basename(self, path):
                                return self._module.basename(path)

                            def split(self, path):
                                return self._module.split(redirect_path(path))

                            def splitext(self, path):
                                return self._module.splitext(path)

                            def abspath(self, path):
                                return self._module.abspath(redirect_path(path))

                            def realpath(self, path):
                                return self._module.realpath(redirect_path(path))

                            def relpath(self, path, start=None):
                                redirected_path = redirect_path(path)
                                if start is not None:
                                    start = redirect_path(start)
                                return self._module.relpath(redirected_path, start)

                            def isabs(self, path):
                                return self._module.isabs(path)

                            def getsize(self, path):
                                return self._module.getsize(redirect_path(path))

                            def getmtime(self, path):
                                return self._module.getmtime(redirect_path(path))

                            def getatime(self, path):
                                return self._module.getatime(redirect_path(path))

                            def getctime(self, path):
                                return self._module.getctime(redirect_path(path))

                            def __getattr__(self, name):
                                return getattr(self._module, name)

                            def __setattr__(self, name, value):
                                raise AttributeError("不能修改 os.path 模块")

                        return RestrictedOsPath()

                    if name in ['write', 'fdopen']:
                        raise AttributeError(f"os.{name} 未开放")

                    return getattr(os, name)

                def __setattr__(self, name, value):
                    raise AttributeError("不能修改 os 模块")

            import sys as _sys
            import tarfile as _original_tarfile
            import zipfile as _original_zipfile
            import io as _original_io
            import shutil as _original_shutil

            class _RestrictedTarFileClass(_original_tarfile.TarFile):
                """受限的 TarFile 类，重定向路径"""
                def __init__(self, name=None, mode='r', fileobj=None, *args, **kwargs):
                    if name is not None and fileobj is None:
                        name = redirect_path(name)
                    super().__init__(name, mode, fileobj, *args, **kwargs)

            class RestrictedTarfile:
                """受限的 tarfile 模块，确保文件路径被重定向"""
                TarFile = _RestrictedTarFileClass
                TarFileCompat = _RestrictedTarFileClass

                def open(self, name, mode='r', *args, **kwargs):
                    redirected_name = redirect_path(name)
                    return _original_tarfile.open(redirected_name, mode, *args, **kwargs)

                def is_tarfile(self, name):
                    redirected_name = redirect_path(name)
                    return _original_tarfile.is_tarfile(redirected_name)

                def __getattr__(self, name):
                    return getattr(_original_tarfile, name)

                def __setattr__(self, name, value):
                    raise AttributeError("不能修改 tarfile 模块")

            class _RestrictedZipFile(_original_zipfile.ZipFile):
                """受限的 ZipFile 类，重定向路径"""
                def __init__(self, file, mode='r', compression=_original_zipfile.ZIP_STORED,
                             allowZip64=True, *args, **kwargs):
                    if isinstance(file, str):
                        file = redirect_path(file)
                    super().__init__(file, mode, compression, allowZip64, *args, **kwargs)

            class RestrictedZipfile:
                """受限的 zipfile 模块，确保文件路径被重定向"""
                ZipFile = _RestrictedZipFile
                ZIP_STORED = _original_zipfile.ZIP_STORED
                ZIP_DEFLATED = _original_zipfile.ZIP_DEFLATED
                ZIP_BZIP2 = _original_zipfile.ZIP_BZIP2
                ZIP_LZMA = _original_zipfile.ZIP_LZMA

                @staticmethod
                def is_zipfile(filename, *args, **kwargs):
                    if isinstance(filename, (str, os.PathLike)):
                        filename = redirect_path(filename)
                    return _original_zipfile.is_zipfile(filename, *args, **kwargs)

                def __getattr__(self, name):
                    return getattr(_original_zipfile, name)

                def __setattr__(self, name, value):
                    raise AttributeError("不能修改 zipfile 模块")

            class RestrictedIo:
                """受限的 io 模块，确保 open() 使用路径重定向"""
                open = restricted_open
                StringIO = _original_io.StringIO
                BytesIO = _original_io.BytesIO
                BufferedIOBase = _original_io.BufferedIOBase

                def __getattr__(self, name):
                    return getattr(_original_io, name)

                def __setattr__(self, name, value):
                    raise AttributeError("不能修改 io 模块")

            class RestrictedShutil:
                """受限的 shutil 模块，确保读写路径遵守同一套规则"""
                def copy(self, src, dst, *args, **kwargs):
                    src = str(_resolve_for_operation(src, 'read'))
                    dst = str(_resolve_for_operation(dst, 'write'))
                    return _original_shutil.copy(src, dst, *args, **kwargs)

                def copy2(self, src, dst, *args, **kwargs):
                    src = str(_resolve_for_operation(src, 'read'))
                    dst = str(_resolve_for_operation(dst, 'write'))
                    return _original_shutil.copy2(src, dst, *args, **kwargs)

                def copytree(self, src, dst, *args, **kwargs):
                    src = str(_resolve_for_operation(src, 'read'))
                    dst = str(_resolve_for_operation(dst, 'write'))
                    return _original_shutil.copytree(src, dst, *args, **kwargs)

                def move(self, src, dst, *args, **kwargs):
                    src = str(_resolve_for_operation(src, 'read'))
                    dst = str(_resolve_for_operation(dst, 'write'))
                    return _original_shutil.move(src, dst, *args, **kwargs)

                def rmtree(self, path, *args, **kwargs):
                    path = str(_resolve_for_operation(path, 'delete'))
                    return _original_shutil.rmtree(path, *args, **kwargs)

                def __getattr__(self, name):
                    return getattr(_original_shutil, name)

                def __setattr__(self, name, value):
                    raise AttributeError("不能修改 shutil 模块")

            _original_builtins_open = builtins.open
            builtins.open = restricted_open

            safe_globals = {
                '__builtins__': builtins,
                '__name__': '__main__',
                '__file__': source_name,
                'print': print,
                'open': restricted_open,
                'range': range,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'bool': bool,
                'type': type,
            }

            safe_globals['sys'] = sys
            restricted_os = RestrictedOS()
            safe_globals['os'] = restricted_os
            safe_globals['Path'] = _RestrictedPath
            restricted_pathlib = RestrictedPathlib()
            safe_globals['pathlib'] = restricted_pathlib

            restricted_tarfile = RestrictedTarfile()
            restricted_zipfile = RestrictedZipfile()
            restricted_io = RestrictedIo()
            restricted_shutil = RestrictedShutil()

            safe_globals['tarfile'] = restricted_tarfile
            safe_globals['zipfile'] = restricted_zipfile
            safe_globals['io'] = restricted_io
            safe_globals['shutil'] = restricted_shutil

            _original_os = _sys.modules.get('os')
            _sys.modules['os'] = restricted_os

            _original_pathlib = _sys.modules.get('pathlib')
            _sys.modules['pathlib'] = restricted_pathlib

            _original_tarfile_module = _sys.modules.get('tarfile')
            _sys.modules['tarfile'] = restricted_tarfile

            _original_zipfile_module = _sys.modules.get('zipfile')
            _sys.modules['zipfile'] = restricted_zipfile

            _original_io_module = _sys.modules.get('io')
            _sys.modules['io'] = restricted_io

            _original_shutil_module = _sys.modules.get('shutil')
            _sys.modules['shutil'] = restricted_shutil

            if script_path:
                safe_globals['sys'].argv = [script_path] + script_args
            else:
                safe_globals['sys'].argv = ['-c'] + script_args

            locals_dict = safe_globals.copy()
            exit_code = 0
            try:
                exec(compiled_code, locals_dict, locals_dict)
                print("✓ 代码执行完成")
            except SystemExit as e:
                exit_code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
                print("SystemExit: {0}".format(exit_code))
            except MemoryError:
                print("✗ 内存错误")
                exit_code = -1
                traceback.print_exc()
            except RecursionError:
                print("✗ 递归错误")
                exit_code = -1
                traceback.print_exc()
            except Exception as e:
                print("✗ 执行异常: {0}".format(type(e).__name__))
                exit_code = 1
                traceback.print_exc()
            finally:
                builtins.open = _original_builtins_open

                if _original_os is not None:
                    _sys.modules['os'] = _original_os
                elif 'os' in _sys.modules:
                    del _sys.modules['os']

                if _original_pathlib is not None:
                    _sys.modules['pathlib'] = _original_pathlib
                elif 'pathlib' in _sys.modules:
                    del _sys.modules['pathlib']

                if _original_tarfile_module is not None:
                    _sys.modules['tarfile'] = _original_tarfile_module
                elif 'tarfile' in _sys.modules:
                    del _sys.modules['tarfile']

                if _original_zipfile_module is not None:
                    _sys.modules['zipfile'] = _original_zipfile_module
                elif 'zipfile' in _sys.modules:
                    del _sys.modules['zipfile']

                if _original_io_module is not None:
                    _sys.modules['io'] = _original_io_module
                elif 'io' in _sys.modules:
                    del _sys.modules['io']

                if _original_shutil_module is not None:
                    _sys.modules['shutil'] = _original_shutil_module
                elif 'shutil' in _sys.modules:
                    del _sys.modules['shutil']

            output = output_capture.get_output()
            result_queue.put(ExecuteResult(
                output=output,
                exit_code=exit_code
            ))

    except TimeoutError as e:
        tb_str = traceback.format_exc()
        result_queue.put(ExecuteResult(
            output="执行超时: {0}\n\n{1}".format(str(e), tb_str),
            exit_code=-1,
            error=str(e)
        ))
    except MemoryError as e:
        tb_str = traceback.format_exc()
        result_queue.put(ExecuteResult(
            output="错误: 内存使用超过限制\n\n{0}".format(tb_str),
            exit_code=-1,
            error=str(e)
        ))
    except RecursionError as e:
        tb_str = traceback.format_exc()
        result_queue.put(ExecuteResult(
            output="错误: 递归深度超过限制（可能导致无限递归）\n\n{0}".format(tb_str),
            exit_code=-1,
            error=str(e)
        ))
    except Exception as e:
        tb_str = traceback.format_exc()
        result_queue.put(ExecuteResult(
            output="执行错误:\n{0}: {1}\n{2}".format(type(e).__name__, str(e), tb_str),
            exit_code=1,
            error=str(e)
        ))
    finally:
        # 取消超时信号
        try:
            signal.alarm(0)
        except Exception:
            pass


class CodeExecutor:
    """
    受限 Python 执行器（基于受限 open() 函数）

    权限控制：
    - root_dir 内：可读写
    - readable_paths：只读
    - writable_paths：可读写
    - 其他绝对路径：自动加 root_dir 前缀
    - 相对路径：自动加 root_dir 前缀
    """

    def __init__(self, root_dir=None, timeout=30, max_output_length=100 * 1024,
                 writable_paths=None, readable_paths=None):
        """
        初始化沙箱执行器

        Args:
            root_dir: 沙箱根目录
            timeout: 执行超时时间（秒）
            max_output_length: 最大输出长度（字节）
            writable_paths: 额外的可写路径列表
            readable_paths: 只读白名单路径列表（如 .venv）
        """
        self.root_dir = Path(root_dir).resolve()
        # self.root_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.max_output_length = max_output_length
        self.writable_paths = [Path(p).resolve() for p in (writable_paths or [])]
        self.readable_paths = [Path(p).resolve() for p in (readable_paths or [])]

        # writable_paths 添加白名单，用于解决 os.path.exists() 函数无法访问 /dev/null 等问题
        # 注意: 系统路径已经是绝对路径，不需要调用 resolve() 以避免阻塞调用
        self.writable_paths.append(Path('/var/folders'))
        self.writable_paths.append(Path(tempfile.gettempdir()))  # tempfile.gettempdir() 返回绝对路径
        self.writable_paths.append(Path('/private/var/folders'))

        # readable_paths 增加白名单，mimetypes 模块需要
        self.readable_paths.append(Path('/etc/apache2/mime.types'))
        self.readable_paths.append(Path('/etc/mime.types'))
        self.readable_paths.append(Path('/private/etc/apache2/mime.types'))
        self.readable_paths.append(Path('/private/etc/mime.types'))

        # 动态添加当前 Python 环境的 lib 目录到白名单
        import sys
        self.readable_paths.append(Path(sys.prefix))
        self.python_prefix = Path(sys.prefix).resolve()

        # 添加 .venv 到只读白名单，python-pptx 等库需要访问模板文件
        # .venv 在项目根目录下，而不是在沙箱 root_dir 下
        # 注意: 使用 absolute() 而不是 resolve() 以避免阻塞调用
        self.project_root = Path(__file__).parent.parent.parent.resolve()
        venv_path = self.project_root / '.venv'
        self.venv_path = venv_path.resolve() if venv_path.exists() else None
        if venv_path.exists():
            self.readable_paths.append(venv_path)

    @staticmethod
    def _is_within(path_obj: Path, parent: Path) -> bool:
        try:
            path_obj.relative_to(parent)
            return True
        except ValueError:
            return False

    def _classify_host_path(self, resolved_path: Path) -> str:
        if self._is_within(resolved_path, self.root_dir):
            return 'root'
        for wp in self.writable_paths:
            if self._is_within(resolved_path, wp):
                return 'writable'
        for rp in self.readable_paths:
            if self._is_within(resolved_path, rp):
                return 'readable'
        return 'other'

    def _resolve_script_source_path(self, script_path: str) -> Path:
        """解析脚本源码路径，遵循沙箱文件系统语义。"""
        script_file = Path(script_path).expanduser()
        if script_file.is_absolute():
            resolved = script_file.resolve()
            if self._classify_host_path(resolved) != 'other':
                return resolved
            return (self.root_dir / script_file.relative_to(script_file.anchor)).resolve()
        return (self.root_dir / script_file).resolve()

    def _virtualize_path_text(self, text: str) -> str:
        """将 root_dir 下的宿主机路径回写为沙箱虚拟路径。"""
        if not text:
            return text

        rewritten = text
        replacement_pairs = [
            (str(self.root_dir), os.sep),
            (str(self.project_root), os.sep),
            (str(self.python_prefix), "/.python"),
        ]
        if self.venv_path is not None:
            replacement_pairs.insert(2, (str(self.venv_path), "/.venv"))

        for source, target in sorted(replacement_pairs, key=lambda item: len(item[0]), reverse=True):
            normalized_source = source.rstrip(os.sep)
            if not normalized_source:
                continue
            rewritten = rewritten.replace(normalized_source + os.sep, target.rstrip(os.sep) + os.sep)
            rewritten = rewritten.replace(source, target)
        return rewritten

    def _append_debug(self, debug_logs: list[str], message: str) -> None:
        debug_logs.append(self._virtualize_path_text(message))

    def _snapshot_root_files(self) -> dict[str, dict[str, object]]:
        """记录 root_dir 中文件的元信息，用于执行后给出摘要。"""
        snapshot: dict[str, dict[str, object]] = {}
        if not self.root_dir.exists():
            return snapshot

        for path in self.root_dir.rglob("*"):
            if not path.is_file():
                continue
            stat = path.stat()
            virtual_path = "/" + str(path.relative_to(self.root_dir)).replace(os.sep, "/")
            snapshot[virtual_path] = {
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        return snapshot

    @staticmethod
    def _format_file_changes(
        before: dict[str, dict[str, object]],
        after: dict[str, dict[str, object]],
    ) -> list[str]:
        lines: list[str] = []
        created = sorted(path for path in after if path not in before)
        updated = sorted(
            path for path in after
            if path in before and (
                after[path]["mtime_ns"] != before[path]["mtime_ns"]
                or after[path]["size"] != before[path]["size"]
            )
        )

        if created:
            lines.append("生成文件:")
            for path in created:
                lines.append(
                    "- {0} ({1} bytes)".format(path, after[path]["size"])
                )

        if updated:
            lines.append("更新文件:")
            for path in updated:
                lines.append(
                    "- {0} ({1} bytes)".format(path, after[path]["size"])
                )

        return lines

    def _parse_command(self, command, debug_logs=None):
        """
        解析命令字符串

        支持格式：
        1. python -c "单行pyscript" - 执行代码字符串
        2. python script.py [args...] - 执行脚本文件
        3. python << 'EOF' - 使用 heredoc 执行多行代码

        Returns:
            (code, script_path, script_args)
            - code: 代码字符串（如果是脚本，为 None）
            - script_path: 脚本路径（如果是代码字符串，为 None）
            - script_args: 脚本参数列表
        """
        command = command.strip()

        # 检查是否是 heredoc 格式: python << 'EOF' 或 python << "EOF"
        # 只检查第一行
        first_line = command.split('\n')[0] if '\n' in command else command
        heredoc_match = re.match(r'^python\s*<<\s*[\'"]?(\w+)[\'"]?\s*$', first_line, re.IGNORECASE)
        if heredoc_match:
            # 对于真正的 heredoc，我们期望在后续行中找到代码
            # 但这里我们实际上接收到的是完整的命令字符串
            # 如果命令中包含换行符和 EOF 标记，则解析
            if '\n' in command:
                delimiter = heredoc_match.group(1)
                # 查找分隔符位置
                delimiter_pattern = rf'^{re.escape(delimiter)}\s*$'
                lines = command.split('\n', 1)  # 分割第一行和剩余内容
                if len(lines) == 2:
                    content = lines[1]
                    # 查找结束标记
                    for i, line in enumerate(content.split('\n')):
                        if re.match(delimiter_pattern, line):
                            # 找到结束标记
                            code = '\n'.join(content.split('\n')[:i])
                            return code.strip(), None, []
                    # 没有找到结束标记，整个内容都是代码
                    return content.strip(), None, []

        # 标准的简单命令解析
        parts = command.split()

        if not parts or parts[0] != 'python':
            raise ValueError("命令必须以 'python' 开头")

        if len(parts) < 2:
            raise ValueError("命令格式错误")

        if parts[1] == '-c':
            # 格式: python -c "code"
            if len(parts) < 3:
                raise ValueError("-c 参数后缺少代码字符串")

            # 找到引号之间的代码
            command_str = ' '.join(parts[2:])

            # 处理引号
            if command_str.startswith('"') and command_str.endswith('"'):
                code = command_str[1:-1]
            elif command_str.startswith("'") and command_str.endswith("'"):
                code = command_str[1:-1]
            else:
                raise ValueError("代码字符串必须用引号括起来")

            # 检查是否包含多行代码
            if '\n' in code:
                raise ValueError(
                    "python -c 不支持多行代码。\n"
                    "请使用以下格式之一：\n"
                    "  1. python script.py [args...]  - 执行脚本文件\n"
                    "  2. python << 'EOF'             - 使用 heredoc 执行多行代码\n"
                    "示例:\n"
                    "  python << 'EOF'\n"
                    "  print('第一行')\n"
                    "  print('第二行')\n"
                    "  EOF"
                )

            return code, None, []

        else:
            # 格式: python script.py [args...]
            # 使用 shlex.split 正确处理带引号和转义的参数
            try:
                # shlex.split 会正确处理：
                # - "hello world" -> ['hello world']
                # - "say \"hello\"" -> ['say "hello"']
                # - 'single quotes' -> ['single quotes']
                parsed_parts = shlex.split(command)
            except ValueError as e:
                # 如果 shlex 解析失败（如不匹配的引号），回退到简单分割
                if debug_logs is not None:
                    self._append_debug(debug_logs, "shlex 解析失败，回退到简单分割: {0}".format(e))
                parsed_parts = command.split()

            if len(parsed_parts) < 2:
                raise ValueError("命令格式错误")

            script_path = parsed_parts[1]
            script_args = parsed_parts[2:] if len(parsed_parts) > 2 else []

            return None, script_path, script_args

    def _read_script_file(self, script_path, debug_logs=None):
        """
        读取脚本文件内容

        Args:
            script_path: 脚本文件路径（相对于 root_dir）

        Returns:
            脚本内容
        """
        if debug_logs is not None:
            self._append_debug(debug_logs, "→ 读取脚本文件: {0}".format(script_path))

        full_path = self._resolve_script_source_path(script_path)

        if not full_path.exists():
            if debug_logs is not None:
                self._append_debug(debug_logs, "✗ 文件不存在: {0}".format(full_path))
            raise FileNotFoundError(str(full_path))

        content = full_path.read_text(encoding='utf-8')
        if debug_logs is not None:
            self._append_debug(debug_logs, "✓ 文件读取成功 ({0} 字节)".format(len(content)))
        return content

    def execute(self, command):
        """
        执行受限的 Python 代码或脚本文件

        Args:
            command: 命令字符串（python -c "单行script" 或 python script.py [args...]）

        Returns:
            ExecuteResponse 包含输出、退出码和截断标志
        """
        try:
            debug_logs: list[str] = []
            # 步骤 1: 解析命令
            try:
                code, script_path, script_args = self._parse_command(command, debug_logs)
            except ValueError as e:
                return ExecuteResponse(
                    output=self._merge_debug_output(
                        debug_logs,
                        "命令格式错误:\n{0}".format(str(e))
                    ),
                    exit_code=-1,
                    truncated=False
                )

            # 步骤 2: 如果是脚本文件，读取内容
            if script_path:
                try:
                    code = self._read_script_file(script_path, debug_logs)
                except FileNotFoundError as e:
                    return ExecuteResponse(
                        output=self._merge_debug_output(
                            debug_logs,
                            "错误: 脚本文件不存在: {0}\n详细信息: {1}".format(script_path, str(e))
                        ),
                        exit_code=-1,
                        truncated=False
                    )
                except Exception as e:
                    self._append_debug(debug_logs, "✗ 读取文件失败")
                    return ExecuteResponse(
                        output=self._merge_debug_output(
                            debug_logs,
                            "错误: 读取脚本文件失败: {0}\n详细信息: {1}".format(script_path, str(e))
                        ),
                        exit_code=-1,
                        truncated=False
                    )

            # 去除代码两端的空白
            code = code.strip()

            if not code:
                self._append_debug(debug_logs, "✗ 代码为空")
                return ExecuteResponse(
                    output=self._merge_debug_output(debug_logs, "错误: 没有提供要执行的代码"),
                    exit_code=-1,
                    truncated=False
                )

            before_file_snapshot = self._snapshot_root_files()

            # 步骤 3: 创建子进程执行代码
            result_queue = Queue()
            process = Process(
                target=_execute_in_subprocess,
                args=(
                    code,
                    str(self.root_dir),
                    script_path,  # 添加脚本路径
                    script_args,
                    result_queue,
                    self.timeout,
                    [str(p) for p in self.writable_paths],
                    [str(p) for p in self.readable_paths]
                )
            )

            # 启动子进程
            process.start()

            # 等待子进程完成（带超时）
            process.join(timeout=self.timeout + 5)  # 额外给 5 秒用于清理

            # 检查子进程状态
            if process.is_alive():
                # 子进程超时，强制终止
                process.terminate()
                process.join(timeout=2)
                if process.is_alive():
                    process.kill()
                    process.join()

                return ExecuteResponse(
                    output="执行超时（超过 {0} 秒）".format(self.timeout),
                    exit_code=-1,
                    truncated=False
                )

            # 获取执行结果
            if not result_queue.empty():
                result = result_queue.get()
            else:
                # 子进程异常退出但没有返回结果
                self._append_debug(debug_logs, "✗ 进程异常退出")
                return ExecuteResponse(
                    output=self._merge_debug_output(debug_logs, "错误: 子进程异常退出，没有返回结果"),
                    exit_code=-1,
                    truncated=False
                )

            # 步骤 4: 检查输出长度并截断
            output = self._merge_debug_output(debug_logs, result.output)
            after_file_snapshot = self._snapshot_root_files()
            summary_lines = [
                "执行结束: exit_code={0}".format(result.exit_code),
                "完成时间: {0}".format(datetime.now().isoformat(timespec="seconds")),
            ]
            summary_lines.extend(self._format_file_changes(before_file_snapshot, after_file_snapshot))
            if output and not output.endswith("\n"):
                output += "\n"
            output += "\n".join(summary_lines) + "\n"
            truncated = False

            if len(output) > self.max_output_length:
                output = output[:self.max_output_length]
                truncated = True
                output += "\n\n... [输出被截断，超过最大长度限制] ..."

            return ExecuteResponse(
                output=output,
                exit_code=result.exit_code,
                truncated=truncated
            )

        except Exception as e:
            # 捕获任何未预期的异常
            debug_logs = locals().get("debug_logs", [])
            self._append_debug(debug_logs, "✗ 系统异常")
            import traceback
            return ExecuteResponse(
                output=self._merge_debug_output(
                    debug_logs,
                    "系统异常: {0}\n{1}".format(str(e), traceback.format_exc())
                ),
                exit_code=-1,
                truncated=False
            )

    def _merge_debug_output(self, debug_logs: list[str], output: str) -> str:
        sections = []
        if debug_logs:
            sections.append("\n".join(debug_logs))
        if output:
            sections.append(self._virtualize_path_text(output))
        return "\n".join(sections)


if __name__ == '__main__':
    sandbox_root = Path("/tmp/sandbox_test").resolve()
    writable_root = Path("/tmp/sandbox_test_writable").resolve()
    readable_root = Path("/tmp/sandbox_test_readable").resolve()
    external_script = Path("/tmp/sandbox_test_external.py").resolve()

    sandbox_root.mkdir(parents=True, exist_ok=True)
    writable_root.mkdir(parents=True, exist_ok=True)
    readable_root.mkdir(parents=True, exist_ok=True)
    (readable_root / "input.txt").write_text("readonly-data", encoding="utf-8")

    executor = CodeExecutor(
        root_dir=sandbox_root,
        timeout=10,
        writable_paths=[str(writable_root)],
        readable_paths=[str(readable_root)],
    )

    tests = [
        (
            "测试 1: 简单输出",
            'python -c "print(\'Hello from sandbox!\')"',
        ),
        (
            "测试 2: 相对路径写入 root_dir",
            'python -c "open(\'test.txt\', \'w\').write(\'test\'); print(open(\'test.txt\').read())"',
        ),
        (
            "测试 3: 只读白名单可读不可写",
            'python -c "print(open(\'/tmp/sandbox_test_readable/input.txt\').read()); '
            'open(\'/tmp/sandbox_test_readable/input.txt\', \'w\').write(\'overwrite\')"',
        ),
        (
            "测试 4: 可写白名单允许写入",
            'python -c "open(\'/tmp/sandbox_test_writable/output.txt\', \'w\').write(\'writable-data\'); '
            'print(open(\'/tmp/sandbox_test_writable/output.txt\').read())"',
        ),
        (
            "测试 5: 外部绝对路径写入自动重定向到 root_dir",
            'python -c "open(\'/tmp/sandbox_test_redirected.txt\', \'w\').write(\'redirected\'); '
            'print(open(\'/tmp/sandbox_test_redirected.txt\').read())"',
        ),
        (
            "测试 6: 目录遍历从 root_dir 开始",
            'python -c "import os; print(next(os.walk(\'.\'))[0])"',
        ),
        (
            "测试 7: os.open 遵守路径重定向",
            'python -c "import os; fd = os.open(\'/tmp/sandbox_test_fd.txt\', os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644); os.close(fd); print(os.path.exists(\'/tmp/sandbox_test_fd.txt\'))"',
        ),
        (
            "测试 8: 外部脚本执行但相对输出仍落在 root_dir",
            'python /tmp/sandbox_test_external.py',
        ),
        (
            "测试 9: os.chmod 与 Path.touch 受控",
            'python -c "import os, pathlib; pathlib.Path(\'/tmp/sandbox_test_touch.txt\').touch(); '
            'os.chmod(\'/tmp/sandbox_test_writable/output.txt\', 0o600); '
            'print(pathlib.Path(\'/tmp/sandbox_test_touch.txt\').exists()); '
            'print(oct(os.stat(\'/tmp/sandbox_test_writable/output.txt\').st_mode & 0o777))"',
        ),
        (
            "测试 10: 超时保护",
            'python -c "import time; time.sleep(15)"',
        ),
    ]

    external_script.write_text(
        "import os\n"
        "print(open('/tmp/sandbox_test_readable/input.txt').read())\n"
        "open('external_result.txt', 'w').write('external-write')\n"
        "print(open('external_result.txt').read())\n"
        "print(os.path.exists('external_result.txt'))\n",
        encoding="utf-8",
    )

    for title, command in tests:
        print("\n=== {0} ===".format(title))
        result = executor.execute(command)
        print("exit_code:", result.exit_code)
        print(result.output)

    redirected_output = sandbox_root / "tmp/sandbox_test_redirected.txt"
    if redirected_output.exists():
        print("\n重定向文件:", redirected_output)
        print(redirected_output.read_text(encoding="utf-8"))

    external_output = sandbox_root / "external_result.txt"
    if external_output.exists():
        print("\n外部脚本输出文件:", external_output)
        print(external_output.read_text(encoding="utf-8"))

    fd_output = sandbox_root / "tmp/sandbox_test_fd.txt"
    if fd_output.exists():
        print("\nos.open 输出文件:", fd_output)

    touch_output = sandbox_root / "tmp/sandbox_test_touch.txt"
    if touch_output.exists():
        print("\nPath.touch 输出文件:", touch_output)
