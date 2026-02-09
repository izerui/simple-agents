# -*- coding: utf-8 -*-
"""
安全沙箱后端（只支持标准执行格式）

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

安全拦截机制（多重保护）：
1. 受限 open() 函数：控制文件访问权限
2. 受限 os 模块：禁用危险函数，允许安全函数
3. AST 语法层检查：阻止危险函数调用（os.system, subprocess等）
4. 进程隔离：每个执行在独立子进程，避免污染主进程
5. 超时保护：防止无限循环和资源耗尽
6. 输出限制：防止输出过大

可用和禁用的 os 函数：
✅ 可用：os.remove, os.rmdir, os.mkdir, os.listdir, os.path.exists 等
❌ 禁用：os.open, os.write, os.fdopen（使用内置 open() 代替）

支持三种标准执行格式：
1. python -c "code" - 直接执行代码字符串
2. python script.py [args...] - 执行脚本文件(支持参数)
3. python << 'EOF' - 使用 heredoc 执行多行代码（推荐）

heredoc 格式优势：
- 支持多行代码，无需所有代码写在同一行
- 代码中可直接使用单引号、双引号，无需转义
- 代码可读性更好
"""
import sys
import io
import os
import ast
import signal
import traceback
import tempfile
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
        # 切换工作目录
        os.chdir(root_dir)
        print("  [子进程] 工作目录: {0}".format(os.getcwd()))

        # 设置超时信号
        def timeout_handler(signum, frame):
            raise TimeoutError("代码执行超时（超过 {0} 秒）".format(timeout))

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)

        # 编译代码
        try:
            compiled_code = compile(code, '<sandbox>', 'exec')
            print("  [子进程] 代码编译成功")
        except SyntaxError as e:
            print("  [子进程] ✗ 代码编译失败")
            result_queue.put(ExecuteResult(
                output="语法错误: {0}".format(str(e)),
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

        def redirect_path(path_str):
            """
            路径重定向函数：
            1. root_dir 内的路径：保持不变
            2. writable_paths 中的路径：保持不变
            3. readable_paths 中的路径：保持不变
            4. 其他绝对路径：自动加 root_dir 前缀
            5. 相对路径：自动加 root_dir 前缀

            Returns:
                重定向后的路径字符串
            """
            file_path = Path(path_str).expanduser()

            if file_path.is_absolute():
                resolved = file_path.resolve()

                # 1. 检查是否在 root_dir 内
                if str(resolved).startswith(str(root_path)):
                    return path_str

                # 2. 检查是否在 readable_paths 中（只读白名单）
                for rp in readable_resolved:
                    if str(resolved).startswith(str(rp)):
                        return path_str

                # 3. 检查是否在 writable_paths 中（读写白名单）
                for wp in writable_resolved:
                    if str(resolved).startswith(str(wp)):
                        return path_str

                # 4. 其他绝对路径：自动加 root_dir 前缀 (注意： 这里逻辑不可变更)
                new_path = root_path / file_path.relative_to(file_path.anchor)
                return str(new_path)
            else:
                # 相对路径：强制加 root_dir 前缀
                new_path = root_path / file_path
                return str(new_path)

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
            file_path = Path(file).expanduser()
            mode_str = mode if isinstance(mode, str) else 'r'
            is_writing = any(c in mode_str for c in ['w', 'a', '+', 'x'])

            # 确定最终路径
            final_path = None
            if file_path.is_absolute():
                resolved = file_path.resolve()

                # 1. 检查是否在 root_dir 内
                if str(resolved).startswith(str(root_path)):
                    final_path = file

                # 2. 检查是否在 readable_paths 中（只读白名单）
                elif any(str(resolved).startswith(str(rp)) for rp in readable_resolved):
                    if is_writing:
                        raise PermissionError("只读路径，禁止写入: {0}".format(file))
                    final_path = file

                # 3. 检查是否在 writable_paths 中（读写白名单）
                elif any(str(resolved).startswith(str(wp)) for wp in writable_resolved):
                    final_path = file

                # 4. 其他绝对路径：自动加 root_dir 前缀
                else:
                    final_path = str(root_path / file_path.relative_to(file_path.anchor))
            else:
                # 相对路径：强制加 root_dir 前缀
                final_path = str(root_path / file_path)

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
                # 将第一个参数（通常是路径）进行重定向
                redirected = [redirect_path(args[0])] + list(args[1:])
                return tuple(redirected)

            def mkdir(self, path, *args, **kwargs):
                """创建目录，自动重定向路径"""
                redirected_path = redirect_path(path)
                return os.mkdir(redirected_path, *args, **kwargs)

            def makedirs(self, path, *args, **kwargs):
                """递归创建目录，自动重定向路径"""
                redirected_path = redirect_path(path)
                return os.makedirs(redirected_path, *args, **kwargs)

            def remove(self, path, *args, **kwargs):
                """删除文件，自动重定向路径"""
                redirected_path = redirect_path(path)
                return os.remove(redirected_path, *args, **kwargs)

            def rmdir(self, path, *args, **kwargs):
                """删除目录，自动重定向路径"""
                redirected_path = redirect_path(path)
                return os.rmdir(redirected_path, *args, **kwargs)

            def removedirs(self, path, *args, **kwargs):
                """递归删除目录，自动重定向路径"""
                redirected_path = redirect_path(path)
                return os.removedirs(redirected_path, *args, **kwargs)

            def listdir(self, path):
                """列出目录内容，自动重定向路径"""
                redirected_path = redirect_path(path)
                return os.listdir(redirected_path)

            def stat(self, path, *args, **kwargs):
                """获取文件状态，自动重定向路径"""
                redirected_path = redirect_path(path)
                return os.stat(redirected_path, *args, **kwargs)

            def lstat(self, path, *args, **kwargs):
                """获取文件状态（不跟随符号链接），自动重定向路径"""
                redirected_path = redirect_path(path)
                return os.lstat(redirected_path, *args, **kwargs)

            def rename(self, src, dst, *args, **kwargs):
                """重命名文件，自动重定向路径并严格按顺序检查权限"""
                # 重定向路径
                src_redirected = redirect_path(src)
                dst_redirected = redirect_path(dst)

                # 解析目标路径并检查权限
                dst_resolved = Path(dst_redirected).resolve()

                # 1. 检查目标是否在 root_dir 内 -> 允许
                if str(dst_resolved).startswith(str(root_path)):
                    pass  # 在 root_dir 内，允许操作
                # 2. 检查目标是否在 readable_paths 中 -> 禁止写入
                elif any(str(dst_resolved).startswith(str(rp)) for rp in readable_resolved):
                    raise PermissionError("只读路径，禁止写入: {0}".format(dst))
                # 3. 检查目标是否在 writable_paths 中 -> 允许
                elif any(str(dst_resolved).startswith(str(wp)) for wp in writable_resolved):
                    pass  # 在 writable_paths 内，允许操作
                # 4. 其他情况（已重定向到 root_dir）-> 允许
                else:
                    pass  # 已经被 redirect_path 重定向到 root_dir

                return os.rename(src_redirected, dst_redirected, *args, **kwargs)

            def replace(self, src, dst, *args, **kwargs):
                """替换文件，自动重定向路径并严格按顺序检查权限"""
                src_redirected = redirect_path(src)
                dst_redirected = redirect_path(dst)

                # 解析目标路径并检查权限
                dst_resolved = Path(dst_redirected).resolve()

                # 1. 检查目标是否在 root_dir 内 -> 允许
                if str(dst_resolved).startswith(str(root_path)):
                    pass  # 在 root_dir 内，允许操作
                # 2. 检查目标是否在 readable_paths 中 -> 禁止写入
                elif any(str(dst_resolved).startswith(str(rp)) for rp in readable_resolved):
                    raise PermissionError("只读路径，禁止写入: {0}".format(dst))
                # 3. 检查目标是否在 writable_paths 中 -> 允许
                elif any(str(dst_resolved).startswith(str(wp)) for wp in writable_resolved):
                    pass  # 在 writable_paths 内，允许操作
                # 4. 其他情况（已重定向到 root_dir）-> 允许
                else:
                    pass  # 已经被 redirect_path 重定向到 root_dir

                return os.replace(src_redirected, dst_redirected, *args, **kwargs)

            def renames(self, src, dst, *args, **kwargs):
                """递归重命名文件，自动重定向路径并严格按顺序检查权限"""
                src_redirected = redirect_path(src)
                dst_redirected = redirect_path(dst)

                # 解析目标路径并检查权限
                dst_resolved = Path(dst_redirected).resolve()

                # 1. 检查目标是否在 root_dir 内 -> 允许
                if str(dst_resolved).startswith(str(root_path)):
                    pass  # 在 root_dir 内，允许操作
                # 2. 检查目标是否在 readable_paths 中 -> 禁止写入
                elif any(str(dst_resolved).startswith(str(rp)) for rp in readable_resolved):
                    raise PermissionError("只读路径，禁止写入: {0}".format(dst))
                # 3. 检查目标是否在 writable_paths 中 -> 允许
                elif any(str(dst_resolved).startswith(str(wp)) for wp in writable_resolved):
                    pass  # 在 writable_paths 内，允许操作
                # 4. 其他情况（已重定向到 root_dir）-> 允许
                else:
                    pass  # 已经被 redirect_path 重定向到 root_dir

                return os.renames(src_redirected, dst_redirected, *args, **kwargs)

            def symlink(self, src, dst, *args, **kwargs):
                """创建符号链接，自动重定向路径"""
                # 符号链接需要特殊处理
                raise AttributeError("os.symlink 被禁用（安全限制）")

            def link(self, src, dst, *args, **kwargs):
                """创建硬链接，自动重定向路径"""
                raise AttributeError("os.link 被禁用（安全限制）")

            def __getattr__(self, name):
                # 特殊处理 os.path 模块
                if name == 'path':
                    # 使用预先导入的 os.path 模块（避免递归）
                    # 创建受限的 os.path 包装器
                    class RestrictedOsPath:
                        """受限的 os.path 模块，确保所有路径都经过重定向"""

                        def __init__(self):
                            object.__setattr__(self, '_module', _original_os_path)

                        def exists(self, path):
                            """检查路径是否存在，自动重定向路径"""
                            redirected_path = redirect_path(path)
                            return self._module.exists(redirected_path)

                        def isfile(self, path):
                            """检查是否是文件，自动重定向路径"""
                            redirected_path = redirect_path(path)
                            return self._module.isfile(redirected_path)

                        def isdir(self, path):
                            """检查是否是目录，自动重定向路径"""
                            redirected_path = redirect_path(path)
                            return self._module.isdir(redirected_path)

                        def join(self, *paths):
                            """连接路径，最后一个参数会被重定向"""
                            if not paths:
                                return ''
                            # os.path.join 连接所有路径
                            joined = self._module.join(*paths)
                            # 只重定向最后一个完整路径
                            return redirect_path(joined)

                        def dirname(self, path):
                            """获取目录名，自动重定向路径"""
                            redirected_path = redirect_path(path)
                            return self._module.dirname(redirected_path)

                        def basename(self, path):
                            """获取基础文件名（不需要重定向）"""
                            return self._module.basename(path)

                        def split(self, path):
                            """分割路径，自动重定向路径"""
                            redirected_path = redirect_path(path)
                            return self._module.split(redirected_path)

                        def splitext(self, path):
                            """分割扩展名（不需要重定向）"""
                            return self._module.splitext(path)

                        def abspath(self, path):
                            """获取绝对路径，自动重定向路径"""
                            redirected_path = redirect_path(path)
                            return self._module.abspath(redirected_path)

                        def realpath(self, path):
                            """获取真实路径，自动重定向路径"""
                            redirected_path = redirect_path(path)
                            return self._module.realpath(redirected_path)

                        def relpath(self, path, start=None):
                            """获取相对路径，自动重定向路径"""
                            redirected_path = redirect_path(path)
                            if start is not None:
                                start = redirect_path(start)
                            return self._module.relpath(redirected_path, start)

                        def isabs(self, path):
                            """检查是否是绝对路径（不需要重定向）"""
                            return self._module.isabs(path)

                        def getsize(self, path):
                            """获取文件大小，自动重定向路径"""
                            redirected_path = redirect_path(path)
                            return self._module.getsize(redirected_path)

                        def getmtime(self, path):
                            """获取修改时间，自动重定向路径"""
                            redirected_path = redirect_path(path)
                            return self._module.getmtime(redirected_path)

                        def getatime(self, path):
                            """获取访问时间，自动重定向路径"""
                            redirected_path = redirect_path(path)
                            return self._module.getatime(redirected_path)

                        def getctime(self, path):
                            """获取创建时间，自动重定向路径"""
                            redirected_path = redirect_path(path)
                            return self._module.getctime(redirected_path)

                        def __getattr__(self, name):
                            """其他方法和属性直接转发到原始模块"""
                            return getattr(self._module, name)

                        def __setattr__(self, name, value):
                            raise AttributeError("不能修改 os.path 模块")

                    return RestrictedOsPath()

                # 只禁用直接文件描述符操作（避免绕过 restricted_open）
                # 其他函数（remove、rmdir、mkdir 等）在 root_dir 内是安全的
                if name in ['open', 'write', 'fdopen']:
                    raise AttributeError(f"os.{name} 被禁用，请使用 open() 函数")

                # 返回原始 os 模块的属性
                return getattr(os, name)

            def __setattr__(self, name, value):
                raise AttributeError("不能修改 os 模块")

        # 在替换 sys.modules 之前，先导入所有原始模块
        import sys as _sys
        import tarfile as _original_tarfile
        import zipfile as _original_zipfile
        import io as _original_io

        # 受限的 tarfile 模块
        class _RestrictedTarFileClass(_original_tarfile.TarFile):
            """受限的 TarFile 类，重定向路径"""
            def __init__(self, name=None, mode='r', fileobj=None, *args, **kwargs):
                # 重定向路径
                if name is not None and fileobj is None:
                    name = redirect_path(name)
                super().__init__(name, mode, fileobj, *args, **kwargs)

        class RestrictedTarfile:
            """受限的 tarfile 模块，确保文件路径被重定向"""

            # 将 TarFile 类作为类属性（不是方法）
            TarFile = _RestrictedTarFileClass
            TarFileCompat = _RestrictedTarFileClass

            def open(self, name, mode='r', *args, **kwargs):
                """打开 tarfile，自动重定向路径"""
                redirected_name = redirect_path(name)
                return _original_tarfile.open(redirected_name, mode, *args, **kwargs)

            def is_tarfile(self, name):
                """检查文件是否是 tarfile，自动重定向路径"""
                redirected_name = redirect_path(name)
                return _original_tarfile.is_tarfile(redirected_name)

            def __getattr__(self, name):
                """其他属性和方法直接返回原始值"""
                return getattr(_original_tarfile, name)

            def __setattr__(self, name, value):
                raise AttributeError("不能修改 tarfile 模块")

        # 受限的 zipfile 模块
        class _RestrictedZipFile(_original_zipfile.ZipFile):
            """受限的 ZipFile 类，重定向路径"""
            def __init__(self, file, mode='r', compression=_original_zipfile.ZIP_STORED,
                         allowZip64=True, *args, **kwargs):
                # 重定向路径（仅当 file 是字符串路径时）
                if isinstance(file, str):
                    file = redirect_path(file)
                super().__init__(file, mode, compression, allowZip64, *args, **kwargs)

        class RestrictedZipfile:
            """受限的 zipfile 模块，确保文件路径被重定向"""

            # ZipFile 类作为类属性
            ZipFile = _RestrictedZipFile

            # 常量
            ZIP_STORED = _original_zipfile.ZIP_STORED
            ZIP_DEFLATED = _original_zipfile.ZIP_DEFLATED
            ZIP_BZIP2 = _original_zipfile.ZIP_BZIP2
            ZIP_LZMA = _original_zipfile.ZIP_LZMA

            @staticmethod
            def is_zipfile(filename, *args, **kwargs):
                """检查文件是否是 zip 文件"""
                return _original_zipfile.is_zipfile(filename, *args, **kwargs)

            def __getattr__(self, name):
                """其他属性和方法直接返回原始值"""
                return getattr(_original_zipfile, name)

            def __setattr__(self, name, value):
                raise AttributeError("不能修改 zipfile 模块")

        # 受限的 io 模块（拦截 io.open）
        class RestrictedIo:
            """受限的 io 模块，确保 open() 使用路径重定向"""

            open = restricted_open  # 使用受限的 open 函数
            StringIO = _original_io.StringIO
            BytesIO = _original_io.BytesIO
            BufferedIOBase = _original_io.BufferedIOBase

            def __getattr__(self, name):
                """其他属性和方法直接返回原始值"""
                return getattr(_original_io, name)

            def __setattr__(self, name, value):
                raise AttributeError("不能修改 io 模块")

        # 替换 builtins.open，让所有第三方库都使用受限的 open 函数
        _original_builtins_open = builtins.open
        builtins.open = restricted_open

        safe_globals = {
            '__builtins__': builtins,
            '__name__': '__main__',
            '__file__': '<sandbox>',
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

        # 添加受限的系统模块
        safe_globals['sys'] = sys

        # 创建受限的 os 模块实例
        restricted_os = RestrictedOS()
        safe_globals['os'] = restricted_os

        # 同时也需要替换 pathlib 模块
        safe_globals['Path'] = _RestrictedPath
        restricted_pathlib = RestrictedPathlib()
        safe_globals['pathlib'] = restricted_pathlib

        # 创建受限的文件相关模块实例
        restricted_tarfile = RestrictedTarfile()
        restricted_zipfile = RestrictedZipfile()
        restricted_io = RestrictedIo()

        safe_globals['tarfile'] = restricted_tarfile
        safe_globals['zipfile'] = restricted_zipfile
        safe_globals['io'] = restricted_io

        # 将受限模块注入到 sys.modules，防止 import 绕过限制
        # 注意：这需要在当前进程中修改 sys.modules
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

        # 设置 sys.argv
        if script_path:
            # 脚本执行：argv[0] = 脚本名，argv[1:] = 参数
            safe_globals['sys'].argv = [script_path] + script_args
        else:
            # 代码字符串执行：argv[0] = '-c'
            safe_globals['sys'].argv = ['-c'] + script_args

        # 创建局部命名空间
        locals_dict = safe_globals.copy()

        # 执行代码
        print("  [子进程] 执行代码")
        with OutputCapture() as output_capture:
            exit_code = 0
            try:
                exec(compiled_code, locals_dict, locals_dict)
                print("  [子进程] ✓ 代码执行完成")
            except SystemExit as e:
                # 正常退出
                exit_code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
                print("  [子进程] SystemExit: {0}".format(exit_code))
            except MemoryError:
                print("  [子进程] ✗ 内存错误")
                exit_code = -1
                traceback.print_exc()  # 输出完整堆栈
            except RecursionError:
                print("  [子进程] ✗ 递归错误")
                exit_code = -1
                traceback.print_exc()  # 输出完整堆栈
            except Exception as e:
                # 执行错误
                print("  [子进程] ✗ 执行异常: {0}".format(type(e).__name__))
                exit_code = 1
                traceback.print_exc()  # 输出完整堆栈
            finally:
                # 恢复原始的 builtins.open
                builtins.open = _original_builtins_open

                # 恢复原始的 os、pathlib、tarfile、zipfile、io、docx 模块
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

        # 获取输出
        output = output_capture.get_output()

        # 发送结果
        print("  [子进程] 发送结果")
        result_queue.put(ExecuteResult(
            output=output,
            exit_code=exit_code
        ))

    except TimeoutError as e:
        print("  [子进程] ✗ 超时")
        tb_str = traceback.format_exc()
        result_queue.put(ExecuteResult(
            output="执行超时: {0}\n\n{1}".format(str(e), tb_str),
            exit_code=-1,
            error=str(e)
        ))
    except MemoryError as e:
        print("  [子进程] ✗ 内存错误")
        tb_str = traceback.format_exc()
        result_queue.put(ExecuteResult(
            output="错误: 内存使用超过限制\n\n{0}".format(tb_str),
            exit_code=-1,
            error=str(e)
        ))
    except RecursionError as e:
        print("  [子进程] ✗ 递归错误")
        tb_str = traceback.format_exc()
        result_queue.put(ExecuteResult(
            output="错误: 递归深度超过限制（可能导致无限递归）\n\n{0}".format(tb_str),
            exit_code=-1,
            error=str(e)
        ))
    except Exception as e:
        print("  [子进程] ✗ 未预期异常")
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
    安全沙箱执行器（基于受限 open() 函数）

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
        self.root_dir = Path(root_dir)
        # self.root_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.max_output_length = max_output_length
        self.writable_paths = [Path(p).resolve() for p in (writable_paths or [])]
        self.readable_paths = [Path(p).resolve() for p in (readable_paths or [])]

        # writable_paths 添加白名单，用于解决 os.path.exists() 函数无法访问 /dev/null 等问题
        #  Path('/var/folders'),  # macOS 临时目录父目录
        #     Path(tempfile.gettempdir()).resolve(),  # 添加系统临时目录
        self.writable_paths.append(Path('/var/folders'))
        self.writable_paths.append(Path(tempfile.gettempdir()).resolve())
        self.writable_paths.append(Path('/private/var/folders'))

        # readable_paths 增加 白名单，mimetypes 模块需要
        self.readable_paths.append(Path('/etc/apache2/mime.types'))
        self.readable_paths.append(Path('/etc/mime.types'))
        self.readable_paths.append(Path('/private/etc/apache2/mime.types'))
        self.readable_paths.append(Path('/private/etc/mime.types'))

        # 添加 .venv 到只读白名单，python-pptx 等库需要访问模板文件
        # .venv 在项目根目录下，而不是在沙箱 root_dir 下
        project_root = Path(__file__).parent.parent.parent.resolve()
        venv_path = project_root / '.venv'
        if venv_path.exists():
            self.readable_paths.append(venv_path)

    def _parse_command(self, command):
        """
        解析命令字符串

        支持格式：
        1. python -c "code" - 执行代码字符串
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
        heredoc_match = re.match(r'^python\s*<<\s*[\'"]?(\w+)[\'"]?\s*$', command, re.IGNORECASE)
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

            return code, None, []

        else:
            # 格式: python script.py [args...]
            script_path = parts[1]
            script_args = parts[2:] if len(parts) > 2 else []
            return None, script_path, script_args

    def _read_script_file(self, script_path):
        """
        读取脚本文件内容

        Args:
            script_path: 脚本文件路径（相对于 root_dir）

        Returns:
            脚本内容
        """
        print("→ 读取脚本文件: {0}".format(script_path))

        # 去掉开头的 /，将绝对路径转换为相对路径
        if script_path.startswith('/'):
            script_path = script_path.lstrip('/')

        full_path = self.root_dir / script_path
        if not full_path.exists():
            print("✗ 文件不存在: {0}".format(full_path))
            raise FileNotFoundError(str(full_path))

        content = full_path.read_text(encoding='utf-8')
        print("✓ 文件读取成功 ({0} 字节)".format(len(content)))
        return content

    def _check_code_safety(self, code):
        """
        检查代码安全性（AST 检查）

        阻止危险操作：
        1. os.system, subprocess, os.popen 等危险函数
        2. 动态导入（importlib）
        3. 危险内置函数（exec, eval, compile）

        注意：文件访问通过受限的 open() 函数控制

        Args:
            code: 要检查的代码

        Raises:
            SyntaxError: 如果代码不安全
        """
        print("→ 安全检查")
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            print("✗ 语法错误")
            raise SyntaxError("语法错误: {0}".format(str(e)))

        class SafetyChecker(ast.NodeVisitor):
            """AST 安全检查器"""

            def __init__(self):
                self.unsafe_calls = []
                self.unsafe_imports = []

            def visit_Call(self, node):
                """检查函数调用"""
                # 检查危险函数调用
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id

                    # 危险函数列表（open 在 root_dir 内允许使用）
                    if func_name in ['exec', 'eval', 'compile']:
                        self.unsafe_calls.append(
                            "行 {0}: 调用危险函数 '{1}'".format(node.lineno, func_name)
                        )

                # 检查 module.function 调用
                elif isinstance(node.func, ast.Attribute):
                    attr_name = node.func.attr

                    # 检查 os.system, subprocess.call 等
                    if isinstance(node.func.value, ast.Name):
                        module_name = node.func.value.id

                        # 危险的模块.函数组合
                        dangerous_combos = {
                            # 只阻止真正危险的系统操作
                            # rename, replace 已经过路径重定向包装，可以使用
                            'os': ['system', 'popen', 'spawn', 'fork', 'forkpty', 'chmod', 'chown', 'link', 'symlink', 'putenv', 'unsetenv'],
                            'subprocess': ['run', 'call', 'Popen', 'check_output'],
                            'commands': ['getoutput', 'getstatusoutput'],
                            'ctypes': None,  # ctypes 模块的所有函数都危险
                            'codecs': ['open'],  # codecs.open 可能绕过限制（io 已实现受限版本，安全）
                        }

                        if module_name in dangerous_combos:
                            if dangerous_combos[module_name] is None:
                                # 模块本身就很危险
                                self.unsafe_calls.append(
                                    "行 {0}: 调用危险模块 '{1}' 的函数".format(node.lineno, module_name)
                                )
                            elif attr_name in dangerous_combos[module_name]:
                                self.unsafe_calls.append(
                                    "行 {0}: 调用危险函数 '{1}.{2}'".format(node.lineno, module_name, attr_name)
                                )

                # 继续遍历子节点
                self.generic_visit(node)

            def visit_Import(self, node):
                """检查 import 语句"""
                for alias in node.names:
                    module_name = alias.name

                    # 危险模块列表（io, zipfile, tarfile 已实现受限版本，安全）
                    dangerous_modules = [
                        'subprocess', 'commands', 'ctypes', 'importlib',
                        'pickle', 'marshal', 'shelve',
                        'multiprocessing', 'threading', 'signal',
                        'codecs',  # 可能绕过文件限制
                    ]

                    if module_name in dangerous_modules or any(
                            module_name.startswith(m + '.') for m in dangerous_modules
                    ):
                        self.unsafe_imports.append(
                            "行 {0}: 导入危险模块 '{1}'".format(node.lineno, module_name)
                        )

                self.generic_visit(node)

            def visit_ImportFrom(self, node):
                """检查 from ... import 语句"""
                module_name = node.module if node.module else ''

                # 危险模块列表（io, zipfile, tarfile 已实现受限版本，安全）
                dangerous_modules = [
                    'subprocess', 'commands', 'ctypes', 'importlib',
                    'pickle', 'marshal', 'shelve',
                    'multiprocessing', 'threading', 'signal',
                    'codecs',  # 可能绕过文件限制
                    'pathlib',  # 防止导入原始 Path 绕过限制
                ]

                if module_name in dangerous_modules or any(
                        module_name.startswith(m + '.') for m in dangerous_modules
                ):
                    self.unsafe_imports.append(
                        "行 {0}: 导入危险模块 '{1}'".format(node.lineno, module_name)
                    )

                # 检查是否导入 os.system, os.popen 等
                if module_name == 'os':
                    for alias in node.names:
                        if alias.name in ['system', 'popen', 'spawn', 'fork', 'forkpty']:
                            self.unsafe_imports.append(
                                "行 {0}: 导入危险函数 'os.{1}'".format(node.lineno, alias.name)
                            )

                self.generic_visit(node)

        # 运行安全检查
        checker = SafetyChecker()
        checker.visit(tree)

        # 报告安全问题
        if checker.unsafe_calls or checker.unsafe_imports:
            print("✗ 安全检查失败")
            error_msg = "安全检查失败，发现以下危险操作：\n"
            error_msg += "\n".join(checker.unsafe_calls + checker.unsafe_imports)
            raise SyntaxError(error_msg)

        print("✓ 安全检查通过")

    def execute(self, command):
        """
        执行受限的 Python 代码或脚本文件

        Args:
            command: 命令字符串（python -c "code" 或 python script.py [args...]）

        Returns:
            ExecuteResponse 包含输出、退出码和截断标志
        """
        print("═ 执行命令")
        try:
            # 步骤 1: 解析命令
            try:
                code, script_path, script_args = self._parse_command(command)
                print("→ 解析命令: {0}".format("脚本文件" if script_path else "代码字符串"))
            except ValueError as e:
                print("✗ 命令格式错误")
                return ExecuteResponse(
                    output="命令格式错误:\n{0}".format(str(e)),
                    exit_code=-1,
                    truncated=False
                )

            # 步骤 2: 如果是脚本文件，读取内容
            if script_path:
                try:
                    code = self._read_script_file(script_path)
                except FileNotFoundError as e:
                    return ExecuteResponse(
                        output="错误: 脚本文件不存在: {0}\n详细信息: {1}".format(script_path, str(e)),
                        exit_code=-1,
                        truncated=False
                    )
                except Exception as e:
                    print("✗ 读取文件失败")
                    return ExecuteResponse(
                        output="错误: 读取脚本文件失败: {0}\n详细信息: {1}".format(script_path, str(e)),
                        exit_code=-1,
                        truncated=False
                    )

            # 去除代码两端的空白
            code = code.strip()

            if not code:
                print("✗ 代码为空")
                return ExecuteResponse(
                    output="错误: 没有提供要执行的代码",
                    exit_code=-1,
                    truncated=False
                )

            # 步骤 3: 检查代码安全性（AST 检查）
            try:
                self._check_code_safety(code)
            except (SyntaxError, ValueError) as e:
                return ExecuteResponse(
                    output="安全检查失败:\n{0}".format(str(e)),
                    exit_code=-1,
                    truncated=False
                )

            # 步骤 4: 创建子进程执行代码
            print("→ 启动子进程")
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
                print("✗ 执行超时")
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
            print("→ 获取执行结果")
            if not result_queue.empty():
                result = result_queue.get()
            else:
                # 子进程异常退出但没有返回结果
                print("✗ 子进程异常退出")
                return ExecuteResponse(
                    output="错误: 子进程异常退出，没有返回结果",
                    exit_code=-1,
                    truncated=False
                )

            # 步骤 5: 检查输出长度并截断
            print("→ 处理输出")
            output = result.output
            truncated = False

            if len(output) > self.max_output_length:
                output = output[:self.max_output_length]
                truncated = True
                output += "\n\n... [输出被截断，超过最大长度限制] ..."

            print("✓ 执行完成 (退出码: {0})".format(result.exit_code))
            return ExecuteResponse(
                output=output,
                exit_code=result.exit_code,
                truncated=truncated
            )

        except Exception as e:
            # 捕获任何未预期的异常
            print("✗ 系统异常")
            import traceback
            return ExecuteResponse(
                output="系统异常: {0}\n{1}".format(str(e), traceback.format_exc()),
                exit_code=-1,
                truncated=False
            )


if __name__ == '__main__':
    # 测试代码
    executor = CodeExecutor(root_dir="/tmp/sandbox_test", timeout=10)

    # 测试 1: 简单输出
    result = executor.execute('python -c "print(\'Hello from sandbox!\')"')
    print("测试 1: {0}".format(result.output))

    # 测试 2: 文件操作
    result = executor.execute(
        'python -c "from pathlib import Path; Path(\'test.txt\').write_text(\'test\'); print(Path(\'test.txt\').read_text())"')
    print("测试 2: {0}".format(result.output))

    # 测试 3: 超时
    result = executor.execute('python -c "import time; time.sleep(15)"')
    print("测试 3: {0}".format(result.output))

    # 测试 4: 危险操作
    result = executor.execute('python -c "import os; os.system(\'ls\')"')
    print("测试 4: {0}".format(result.output))