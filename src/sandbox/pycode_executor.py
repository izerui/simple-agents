# -*- coding: utf-8 -*-
"""
安全沙箱后端（只支持标准执行格式）

实现文件操作权限控制：
- root_dir 内：允许读写
- root_dir 外：只允许只读

文件操作限制机制：
1. 线程本地变量 + Monkey patching：使用 threading.local() 存储每个线程的 root_dir，
   并替换 builtins.open 为线程安全的 safe_open
2. 所有路径（相对路径和绝对路径）都会被重定向到当前线程的 root_dir

安全拦截机制（多重保护）：
- builtins.open → _safe_open_func
- io.open → _safe_open_func
- codecs.open → _safe_open_func
- os.open → _safe_os_open_func

✅ pathlib.Path 安全性说明：
Path 对象的所有文件 I/O 方法（read_text, write_text, open 等）最终都调用 io.open，
因此都会被安全拦截机制保护。Path 对象可以安全使用，不会导致沙箱外目录遍历。

注意：
- safe_open 从线程本地变量读取 root_dir，每个线程独立
- 相对路径和绝对路径（以 / 开头）都会被重定向到当前线程的 root_dir
- 完全并发安全，无需使用锁
- 使用标准 Python compile 编译代码
- Path.resolve() 用于解析符号链接和路径遍历（..），防止沙箱逃逸

只支持两种标准执行格式：
1. python -c "code" - 直接执行代码字符串
2. python script.py [args...] - 执行脚本文件(支持参数)
 """
import sys
import io
import os
import resource
import builtins
import threading
from pathlib import Path
import tempfile
from typing import Optional, Union, Any, Dict
import re
import codecs
 
 # 全局线程本地变量，用于存储每个线程的 root_dir
_thread_local = threading.local()

# 全局标志，标记是否已经替换了 builtins.open
_builtins_open_patched = False

from deepagents.backends.protocol import ExecuteResponse

# 🔧 定义系统路径白名单
# 某些标准库（如 mimetypes）需要访问这些系统文件，某些库（如 openpyxl、pandas、tempfile）需要使用系统临时目录
# 这样可以避免在 safe_open 和 safe_os_open 中调用 tempfile.gettempdir() 导致死循环
# (因为 tempfile.gettempdir() 内部会调用 os.open，而 os.open 已经被替换)

_allowed_system_paths = [
    Path('/etc/apache2/mime.types'),  # mimetypes 模块需要
    Path('/etc/mime.types'),           # 某些系统的 mime.types 文件
    Path('/private/etc/apache2/mime.types'),  # macOS 上 /etc 的实际路径
    Path('/private/etc/mime.types'),           # macOS 上 /etc 的实际路径
    Path('/var/folders'),  # macOS 临时目录父目录
    Path(tempfile.gettempdir()).resolve(),  # 添加系统临时目录
]

# 🔧 预先解析所有存在的白名单路径为绝对路径
_allowed_system_paths_resolved = [path.resolve() for path in _allowed_system_paths if path.exists()]


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

    def get_output(self) -> str:
        """获取所有输出"""
        output = ""
        # 添加 stdout 和 stderr
        stdout = self.stdout_buffer.getvalue()
        stderr = self.stderr_buffer.getvalue()
        output += stdout
        if stderr:
            output += f"\n[错误输出]\n{stderr}"
        return output


def _get_safe_open():
    """创建线程安全的 safe_open 函数
    
    该函数从线程本地变量读取当前线程的 root_dir
    如果没有设置 root_dir，回退到原始的 open（避免影响其他代码）
    """
    def safe_open(filename: Union[str, Path], mode: str = 'r', *args, **kwargs):
        """线程安全的 open 函数"""
        # 🔧 特殊处理：文件描述符（整数）
        # subprocess.Popen 会使用 io.open 打开文件描述符（如管道的读端）
        # 文件描述符是系统级别的，不涉及文件路径，直接使用原始的 open
        if isinstance(filename, int):
            return _original_builtins_open(filename, mode, *args, **kwargs)
        
        # 从线程本地变量获取 root_dir
        root_dir = getattr(_thread_local, 'root_dir', None)
        
        # 🔧 回退机制：如果没有设置 root_dir，使用原始的 open
        if root_dir is None:
            # 不是 backend.execute() 调用，回退到原始行为
            return _original_builtins_open(filename, mode, *args, **kwargs)
        
        # 🔧 特殊处理：允许访问系统白名单路径
        # 某些标准库（如 mimetypes）需要访问系统文件，某些库（如 openpyxl、pandas、tempfile）需要使用系统临时目录
        # 使用模块级别预先缓存的路径列表，避免死循环
        resolved_original_path = Path(filename).resolve()
        for allowed_path in _allowed_system_paths_resolved:
            try:
                resolved_original_path.relative_to(allowed_path)
                # 是白名单路径，允许直接访问
                return _original_builtins_open(filename, mode, *args, **kwargs)
            except ValueError:
                # 不是这个白名单路径，继续检查下一个
                continue
        
        # 处理路径：去掉开头的斜杠，然后添加 root_dir
        path_str = str(filename).lstrip('/')
        full_path = root_dir / path_str
        
        # 🔒 安全验证：解析为绝对路径并检查是否在 root_dir 内
        # 使用 resolve() 解析所有符号链接和相对路径（如 ..）
        resolved_path = full_path.resolve()
        
        try:
            # 检查解析后的路径是否在 root_dir 内
            resolved_path.relative_to(root_dir)
        except ValueError:
            # 路径不在 root_dir 内，拒绝访问
            raise PermissionError(f"安全错误：禁止访问 root_dir 外的文件")
        
        # 🔧 对于写入操作，自动创建父目录
        # 支持的写入模式: 'w', 'a', 'x', 'w+', 'a+', 'x+', 'wb', 'ab', 'xb'
        write_modes = {'w', 'a', 'x'}
        mode_lower = mode.lower()
        needs_write = any(mode_lower.startswith(m) for m in write_modes) or any(m in mode_lower for m in write_modes)
        
        if needs_write:
            # 确保父目录存在
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 使用原始的 builtins.open 打开文件
        return _original_builtins_open(str(resolved_path), mode, *args, **kwargs)
    
    return safe_open

# 全局的 safe_open 函数
_safe_open_func = _get_safe_open()

# 保存原始的 builtins.open
_original_builtins_open = builtins.open

# 保存原始的 io.open
_original_io_open = io.open

# 保存原始的 codecs.open
_original_codecs_open = codecs.open

# 保存原始的 os.open
_original_os_open = os.open

def _get_safe_os_open():
    """创建线程安全的 safe_os_open 函数
    
    该函数从线程本地变量读取当前线程的 root_dir
    如果没有设置 root_dir，回退到原始的 os.open
    """
    def safe_os_open(filename: Union[str, Path], flags: int, mode: int = 0o777, *args, **kwargs) -> int:
        """线程安全的 os.open 函数"""
        # 从线程本地变量获取 root_dir
        root_dir = getattr(_thread_local, 'root_dir', None)
        
        # 🔧 回退机制：如果没有设置 root_dir，使用原始的 os.open
        if root_dir is None:
            return _original_os_open(filename, flags, mode, *args, **kwargs)
        
        # 🔧 特殊处理：允许访问系统白名单路径
        # 某些标准库（如 mimetypes）需要访问系统文件，某些库（如 openpyxl、pandas、tempfile）需要使用系统临时目录
        # 使用模块级别预先缓存的路径列表，避免死循环
        resolved_original_path = Path(filename).resolve()
        for allowed_path in _allowed_system_paths_resolved:
            try:
                resolved_original_path.relative_to(allowed_path)
                # 是白名单路径，允许直接访问
                return _original_os_open(filename, flags, mode, *args, **kwargs)
            except ValueError:
                # 不是这个白名单路径，继续检查下一个
                continue
        
        # 处理路径：去掉开头的斜杠，然后添加 root_dir
        path_str = str(filename).lstrip('/')
        full_path = root_dir / path_str
        
        # 🔒 安全验证：解析为绝对路径并检查是否在 root_dir 内
        resolved_path = full_path.resolve()
        
        try:
            resolved_path.relative_to(root_dir)
        except ValueError:
            # 路径不在 root_dir 内，拒绝访问
            raise PermissionError(f"安全错误：禁止访问 root_dir 外的文件")
        
        # 🔧 对于写入操作，自动创建父目录
        # os.O_WRONLY、os.O_RDWR、os.O_CREAT 等标志表示写入
        write_flags = {os.O_WRONLY, os.O_RDWR, os.O_CREAT, os.O_TRUNC, os.O_APPEND}
        needs_write = bool(flags & (os.O_WRONLY | os.O_RDWR))
        
        if needs_write or (flags & os.O_CREAT):
            # 确保父目录存在
            resolved_path.parent.mkdir(parents=True, exist_ok=True)

        # 使用原始的 os.open 打开文件
        return _original_os_open(str(resolved_path), flags, mode, *args, **kwargs)

    return safe_os_open

# 全局的 safe_os_open 函数
_safe_os_open_func = _get_safe_os_open()

# 🔒 保存真正的原始 os.path 模块 (在任何替换之前)
import os as _original_os_module
_original_os_path = _original_os_module.path

def _get_safe_import():
    """创建安全的 __import__ 函数，拦截 os 模块的导入并替换 os.open"""
    # 获取原始的 __import__（处理 __builtins__ 可能是字典或模块的情况）
    if isinstance(__builtins__, dict):
        original_import = __builtins__['__import__']
    else:
        original_import = __builtins__.__import__
    
    def safe_import(name, *args, **kwargs):
        """安全的 import 函数"""
        # 🚫 禁止导入 ctypes 模块（防止绕过安全限制调用系统库）
        if name == 'ctypes' or name.startswith('ctypes.'):
            raise ImportError(f"安全错误：禁止导入 '{name}' 模块")

        # 🚫 禁止导入 importlib 模块（防止动态导入被禁用的模块）
        if name == 'importlib' or name.startswith('importlib.'):
            raise ImportError(f"安全错误：禁止导入 '{name}' 模块")

        # 🚫 禁止反序列化库（扩展列表）
        UNSAFE_DESER = ['pickle', 'marshal', 'shelve', 'dill', 'yaml', 'jsonpickle']
        if name in UNSAFE_DESER or any(name.startswith(x + '.') for x in UNSAFE_DESER):
            raise ImportError(f"安全错误：禁止导入反序列化库 '{name}'")

        # 🚫 禁止多进程/多线程
        if name in ['threading', 'multiprocessing', 'signal']:
            raise ImportError(f"安全错误：禁止导入 '{name}' 模块")

        # 先调用原始的 import
        module = original_import(name, *args, **kwargs)

        # 如果导入的是 os 模块，替换 os.open 和 os.path
        if name == 'os' and hasattr(module, 'open'):
            # 只在沙箱执行环境中替换（检查是否有 root_dir）
            if hasattr(_thread_local, 'root_dir') and _thread_local.root_dir is not None:
                module.open = _safe_os_open_func

                # 🔒 创建智能的 os.path 包装器
                # 使用动态代理,只在沙箱执行时使用沙箱路径
                # 使用全局保存的原始 os.path,避免递归

                # 创建一个智能的 os.path 包装类
                class SafePathProxy:
                    """os.path 的智能代理,根据上下文选择使用沙箱路径或原始路径"""

                    def __getattr__(self, name):
                        """动态代理到原始 os.path 或沙箱版本"""
                        # ⚠️ 使用全局保存的原始 os.path,避免递归
                        original_func = getattr(_original_os_path, name)

                        # 定义需要沙箱路径的方法
                        sandbox_methods = {
                            'exists', 'isfile', 'isdir', 'getsize', 'getmtime', 'abspath', 'realpath'
                        }

                        # 如果不是需要沙箱拦截的方法,直接返回原始方法
                        if name not in sandbox_methods:
                            return original_func

                        # 创建沙箱版本的包装函数
                        def _sandbox_wrapper(*args, **kwargs):
                            # 检查是否在沙箱环境中
                            root_dir = getattr(_thread_local, 'root_dir', None)
                            if root_dir is None:
                                # 不在沙箱环境,使用原始方法
                                return original_func(*args, **kwargs)

                            # 在沙箱环境中,使用沙箱路径
                            if name == 'exists':
                                path = args[0] if args else kwargs.get('path', '')
                                path_str = str(path).lstrip('/')
                                full_path = root_dir / path_str
                                resolved_path = full_path.resolve()
                                try:
                                    resolved_path.relative_to(root_dir)
                                except ValueError:
                                    return False
                                return resolved_path.exists()

                            elif name == 'isfile':
                                path = args[0] if args else kwargs.get('path', '')
                                path_str = str(path).lstrip('/')
                                full_path = root_dir / path_str
                                resolved_path = full_path.resolve()
                                try:
                                    resolved_path.relative_to(root_dir)
                                except ValueError:
                                    return False
                                return resolved_path.is_file()

                            elif name == 'isdir':
                                path = args[0] if args else kwargs.get('path', '')
                                path_str = str(path).lstrip('/')
                                full_path = root_dir / path_str
                                resolved_path = full_path.resolve()
                                try:
                                    resolved_path.relative_to(root_dir)
                                except ValueError:
                                    return False
                                return resolved_path.is_dir()

                            elif name in ('getsize', 'getmtime'):
                                path = args[0] if args else kwargs.get('path', '')
                                path_str = str(path).lstrip('/')
                                full_path = root_dir / path_str
                                resolved_path = full_path.resolve()
                                try:
                                    resolved_path.relative_to(root_dir)
                                except ValueError:
                                    raise OSError(f"Path outside sandbox: {path}")

                                if name == 'getsize':
                                    return resolved_path.stat().st_size
                                else:
                                    return resolved_path.stat().st_mtime

                            elif name in ('abspath', 'realpath'):
                                path = args[0] if args else kwargs.get('path', '')
                                path_str = str(path).lstrip('/')
                                full_path = root_dir / path_str
                                resolved_path = full_path.resolve()
                                try:
                                    resolved_path.relative_to(root_dir)
                                except ValueError:
                                    pass
                                return str(resolved_path)

                            # 其他情况使用原始方法
                            return original_func(*args, **kwargs)

                        return _sandbox_wrapper

                # 替换 os.path
                module.path = SafePathProxy()

        # 🔒 防止 ctypes 通过 sys.modules 缓存
        if 'ctypes' in sys.modules:
            del sys.modules['ctypes']

        return module
    
    return safe_import

# 全局的 safe_import 函数
_safe_import_func = _get_safe_import()





# 注意参考python黑客技术： https://hacktricks.xsx.tw/generic-methodologies-and-resources/python/bypass-python-sandboxes
class CodeExecutor:
    """
    安全沙箱后端（只支持标准执行格式）

    特性：
    - 使用标准 Python compile 编译代码
    - root_dir 内：允许读写文件
    - root_dir 外：只允许只读文件访问
    - 超时和资源限制
    - 捕获所有输出

    只支持两种执行格式：
    1. python -c "code" - 执行代码字符串
    2. python script.py - 执行脚本文件
    """
    
    # 类级别锁，用于确保 builtins.open 只被替换一次
    _patch_lock = threading.Lock()

    def __init__(
            self,
            root_dir: Optional[Union[str, Path]] = None,
            max_output_length: int = 100000,  # 100KB
            **kwargs
    ) -> None:
        """初始化安全沙箱

        Args:
            root_dir: 允许读写的根目录
            virtual_mode: 虚拟模式（由父类 FilesystemBackend 使用）
            max_file_size_mb: 最大文件大小限制（MB）
            max_output_length: 最大输出长度
        """
        # 设置根目录
        self.root_dir = Path(root_dir) if root_dir else Path(tempfile.mkdtemp())
        self.root_dir = self.root_dir.resolve()

        self.max_output_length = max_output_length

        # 初始化安全的执行环境
        self._safe_globals = self._create_safe_globals()

    def _parse_command(self, command: str) -> tuple[Optional[str], Optional[str], list[str]]:
        """解析命令，只支持两种标准格式

        支持的格式：
        1. python -c "code" - 执行代码字符串
        2. python script.py [args...] - 执行脚本文件(支持参数)

        Args:
            command: 命令字符串

        Returns:
            (code, script_path, script_args) 元组
            - 如果是 python -c 格式：code 为代码字符串，script_path 为 None，script_args 为空列表
            - 如果是 python script.py 格式：code 为 None，script_path 为脚本路径，script_args 为参数列表

        Raises:
            ValueError: 如果命令格式不支持
        """
        command = command.strip()

        # 格式 1: python -c "code"
        # 支持：python -c "code", python3 -c "code", /usr/bin/python -c "code"
        # 支持多行代码
        pattern_c = r'^(?:python(?:3)?|/usr/bin/python(?:3)?)\s+-c\s+([\s\S]+)$'
        match_c = re.match(pattern_c, command, re.IGNORECASE | re.DOTALL)

        if match_c:
            # 提取代码字符串
            code = match_c.group(1).strip()
            # 去除外层引号（单引号或双引号）
            if (code.startswith('"') and code.endswith('"')) or \
                    (code.startswith("'") and code.endswith("'")):
                code = code[1:-1]
            return code, None, []

        # 格式 2: python script.py [args...]
        # 支持：python script.py, python /path/to/script.py, python3 script.py
        # 支持：python script.py arg1 -o output --option value (带参数的脚本)
        # 所有路径都会以 root_dir 为根目录处理
        pattern_script = r'^(?:python(?:3)?|/usr/bin/python(?:3)?)\s+(\S+)(.*)$'
        match_script = re.match(pattern_script, command, re.IGNORECASE)

        if match_script:
            script_path = match_script.group(1).strip()
            args_str = match_script.group(2).strip() if match_script.group(2) else ''
            
            # 🎯 统一处理：所有路径都先去掉开头的斜杠，然后拼接到 root_dir
            # 这样 /scripts/a.py 和 scripts/a.py 都会被当作相对于 root_dir 的路径
            script_path = script_path.lstrip('/')
            # 拼接 root_dir 前缀
            script_path = str(self.root_dir / script_path)

            # 解析参数字符串为列表(简单按空格分割，暂不支持引号)
            script_args = []
            if args_str:
                # 使用 shlex.split 来正确处理引号和转义
                import shlex
                try:
                    script_args = shlex.split(args_str)
                except ValueError:
                    # 如果 shlex.split 失败，简单按空格分割
                    script_args = args_str.split()

            return None, script_path, script_args

        # 不支持的格式
        raise ValueError(
            f"不支持的命令格式: '{command}'\n"
            f"只支持以下两种格式：\n"
            f"  1. python -c \"code\"              - 执行代码字符串\n"
            f"  2. python script.py               - 执行脚本文件\n"
            f"  3. python /path/to/script.py      - 执行脚本文件（绝对路径）\n"
            f"  4. python script.py arg1 -o out   - 执行脚本文件（带参数）"
        )

    def _read_script_file(self, script_path: str) -> str:
        """读取脚本文件内容

        Args:
            script_path: 脚本文件路径（已经是绝对路径，包含 root_dir）

        Returns:
            脚本文件内容

        Raises:
            FileNotFoundError: 如果文件不存在
            PermissionError: 如果没有读取权限
        """
        # script_path 已经在 _parse_command 中拼接了 root_dir，直接读取即可
        # 使用原始的 builtins.open 读取文件（避免被 safe_open 拦截）
        try:
            with _original_builtins_open(script_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # 如果不是 UTF-8 编码，尝试使用系统默认编码
            with _original_builtins_open(script_path, 'r') as f:
                return f.read()

    def _create_safe_globals(self) -> dict:
        """创建安全的全局变量字典（黑名单模式）

        黑名单模式：允许所有内置函数，只明确禁止危险的函数

        Returns:
            安全的全局变量字典
        """
        # 导入 builtins 模块以获取所有内置函数
        import builtins

        # ⚠️ 安全警告：黑名单模式允许更多函数，请确保在受控环境中使用
        # 创建基础的全局变量字典（复制所有内置函数）
        safe_globals = {
            '__builtins__': builtins.__dict__.copy()
        }

        # 🚫 黑名单：定义危险函数列表
        DANGEROUS_FUNCTIONS = [
            # 代码执行类（最危险）
            'eval',
            'exec',
            'compile',

            # 文件操作类（会被安全版本替换）
            'open',
            'file',  # Python 2 兼容

            # 内存操作类
            'memoryview',
            'buffer',
        ]

        # 🚫 移除危险函数
        for func_name in DANGEROUS_FUNCTIONS:
            if func_name in safe_globals['__builtins__']:
                del safe_globals['__builtins__'][func_name] 
        
        # 🔒 确保全局只替换一次所有 open 函数
        with self._patch_lock:
            global _builtins_open_patched
            if not _builtins_open_patched:
                # 替换全局的 builtins.open
                builtins.open = _safe_open_func
                # 同时替换 io.open（zipfile 等库使用 io.open）
                io.open = _safe_open_func
                # 替换 codecs.open（处理编码文件）
                codecs.open = _safe_open_func
                # 🔒 替换 os.open（防止绕过安全限制）
                os.open = _safe_os_open_func
                _builtins_open_patched = True
        
        # 🔒 添加受限的 open 函数（替换原生的 open）
        safe_globals['open'] = _safe_open_func
        safe_globals['__builtins__']['open'] = _safe_open_func
        
        # 🔒 替换 __import__ 函数，拦截 os 模块的导入
        safe_globals['__import__'] = _safe_import_func
        safe_globals['__builtins__']['__import__'] = _safe_import_func
        
        # 同时在全局变量中注入常用模块
        safe_globals['io'] = io
        safe_globals['codecs'] = codecs
        safe_globals['sys'] = sys  # 注入 sys 模块,用于访问 sys.argv
        safe_globals['Path'] = Path

        # 注入 builtins 模块到全局变量中
        safe_globals['builtins'] = builtins

        # 保留 print 函数（内置的）
        safe_globals['print'] = print

        # 添加一些有用的常量和函数
        safe_globals['__name__'] = '__main__'
        safe_globals['__doc__'] = None

        return safe_globals


    def _check_code_safety(self, code: str) -> None:
        """使用 AST 检查代码安全性，禁止危险函数调用

        Args:
            code: 要检查的 Python 代码

        Raises:
            SyntaxError: 如果代码包含语法错误
            ValueError: 如果代码包含危险操作
        """
        import ast

        # 定义禁止的危险函数调用
        # 格式: (模块名, 函数名, 错误消息)
        DANGEROUS_CALLS = [
            ('os', 'remove', '禁止使用 os.remove() 删除文件'),
            ('os', 'unlink', '禁止使用 os.unlink() 删除文件'),
            ('os', 'rmdir', '禁止使用 os.rmdir() 删除目录'),
            ('os', 'removedirs', '禁止使用 os.removedirs() 递归删除目录'),
            ('os', 'rename', '禁止使用 os.rename() 移动或重命名文件'),
            ('os', 'replace', '禁止使用 os.replace() 替换文件'),
            ('os', 'chmod', '禁止使用 os.chmod() 修改文件权限'),
            ('os', 'chown', '禁止使用 os.chown() 修改文件所有者'),
            ('os', 'listdir', '禁止使用 os.listdir() 列出目录'),
            ('os', 'scandir', '禁止使用 os.scandir() 列出目录'),
            # 🚫 禁止 os 模块执行系统命令
            ('os', 'system', '禁止使用 os.system() 执行系统命令'),
            ('os', 'popen', '禁止使用 os.popen() 执行系统命令'),
            ('os', 'spawnl', '禁止使用 os.spawnl() 创建新进程执行命令'),
            ('os', 'spawnle', '禁止使用 os.spawnle() 创建新进程执行命令'),
            ('os', 'spawnlp', '禁止使用 os.spawnlp() 创建新进程执行命令'),
            ('os', 'spawnlpe', '禁止使用 os.spawnlpe() 创建新进程执行命令'),
            ('os', 'spawnv', '禁止使用 os.spawnv() 创建新进程执行命令'),
            ('os', 'spawnve', '禁止使用 os.spawnve() 创建新进程执行命令'),
            ('os', 'spawnvp', '禁止使用 os.spawnvp() 创建新进程执行命令'),
            ('os', 'spawnvpe', '禁止使用 os.spawnvpe() 创建新进程执行命令'),
            ('os', 'posix_spawn', '禁止使用 os.posix_spawn() 创建新进程执行命令'),
            ('os', 'posix_spawnp', '禁止使用 os.posix_spawnp() 创建新进程执行命令'),
            ('os', 'execl', '禁止使用 os.execl() 替换当前进程执行命令'),
            ('os', 'execle', '禁止使用 os.execle() 替换当前进程执行命令'),
            ('os', 'execlp', '禁止使用 os.execlp() 替换当前进程执行命令'),
            ('os', 'execlpe', '禁止使用 os.execlpe() 替换当前进程执行命令'),
            ('os', 'execv', '禁止使用 os.execv() 替换当前进程执行命令'),
            ('os', 'execve', '禁止使用 os.execve() 替换当前进程执行命令'),
            ('os', 'execvp', '禁止使用 os.execvp() 替换当前进程执行命令'),
            ('os', 'execvpe', '禁止使用 os.execvpe() 替换当前进程执行命令'),
            ('os', 'fork', '禁止使用 os.fork() 创建子进程'),
            ('os', 'forkpty', '禁止使用 os.forkpty() 创建伪终端子进程'),
            ('os', 'startfile', '禁止使用 os.startfile() 执行文件或程序'),
            # ✅ pathlib.Path 已放开 - 所有文件操作通过 io.open 拦截保护
            # 🚫 禁止获取环境变量
            ('os', 'getenv', '禁止使用 os.getenv() 获取环境变量'),
            ('os', 'getenvb', '禁止使用 os.getenvb() 获取环境变量'),
            ('os', 'putenv', '禁止使用 os.putenv() 修改环境变量'),
            ('os', 'unsetenv', '禁止使用 os.unsetenv() 修改环境变量'),
            # 🚫 禁止动态导入 ctypes
            ('__builtins__', '__import__', '禁止使用 __import__() 动态导入 ctypes 模块'),
            ('builtins', '__import__', '禁止使用 __import__() 动态导入 ctypes 模块'),
            # 🚫 禁止 importlib 动态导入
            ('importlib', 'import_module', '禁止使用 importlib.import_module() 动态导入模块'),
            ('importlib', '__import__', '禁止使用 importlib.__import__() 动态导入模块'),
            ('importlib.util', 'spec_from_file_location', '禁止使用 importlib.util.spec_from_file_location() 导入模块'),
            ('importlib.util', 'module_from_spec', '禁止使用 importlib.util.module_from_spec() 创建模块'),
            # 🚫 禁止 subprocess 调用外部命令
            ('subprocess', 'run', '禁止使用 subprocess.run() 调用外部命令'),
            ('subprocess', 'call', '禁止使用 subprocess.call() 调用外部命令'),
            ('subprocess', 'Popen', '禁止使用 subprocess.Popen() 调用外部命令'),
            ('subprocess', 'check_call', '禁止使用 subprocess.check_call() 调用外部命令'),
            ('subprocess', 'check_output', '禁止使用 subprocess.check_output() 调用外部命令'),
            ('subprocess', 'getoutput', '禁止使用 subprocess.getoutput() 调用外部命令'),
            ('subprocess', 'getstatusoutput', '禁止使用 subprocess.getstatusoutput() 调用外部命令'),
        ]

        # 🚫 禁止的 Path 危险方法
        # 这些方法直接调用系统底层接口,不经过 open() 拦截
        # 安全的文件 I/O 方法 (read_text, write_text, open, exists 等) 通过 io.open 保护
        FORBIDDEN_PATH_METHODS = [
            'iterdir',      # 列出目录内容
            'glob',         # 通配符匹配
            'rglob',        # 递归通配符匹配
            'unlink',       # 删除文件
            'rmdir',        # 删除空目录
            'mkdir',        # 创建目录
            'rename',       # 重命名文件
            'replace',      # 替换文件
            'touch',        # 创建文件
            'chmod',        # 修改权限
            'stat',         # 获取文件状态（可能泄露沙箱外文件信息）
            'lstat',        # 获取符号链接状态（不解析链接）
            'readlink',     # 读取符号链接目标（可能探测沙箱外路径）
            'symlink',      # 创建符号链接
            'hardlink_to',  # 创建硬链接
            'link_to',      # 创建链接
            'absolute',     # 绝对路径（可能导致沙箱外访问）
            'cwd',          # 获取系统当前工作目录（泄露系统信息，而非沙箱路径）
            'home',         # 获取用户主目录（泄露系统信息，可能指向沙箱外敏感目录）
            'expanduser',   # 展开用户路径（可能指向沙箱外敏感目录）
        ]

        class SafetyChecker(ast.NodeVisitor):
            def __init__(self):
                self.dangerous_calls = []

            def visit_Subscript(self, node):
                """检测字典订阅操作，如 os.environ['KEY']"""
                # 检查是否是 os.environ['xxx'] 的形式
                if isinstance(node.value, ast.Attribute):
                    if (isinstance(node.value.value, ast.Name) and 
                        node.value.value.id == 'os' and 
                        node.value.attr == 'environ'):
                        self.dangerous_calls.append(
                            f"在 {node.lineno} 行: 禁止使用 os.environ[] 获取环境变量"
                        )
                self.generic_visit(node)

            def visit_Attribute(self, node):
                """检测属性访问，如 os.environ"""
                # 检查是否访问了 os.environ 属性
                if isinstance(node.value, ast.Name):
                    if node.value.id == 'os' and node.attr == 'environ':
                        self.dangerous_calls.append(
                            f"在 {node.lineno} 行: 禁止访问 os.environ 获取环境变量"
                        )
                self.generic_visit(node)

            def visit_Call(self, node):
                # 检查函数调用
                func_name = None
                module_name = None

                # 处理 os.remove() 这样的调用
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        module_name = node.func.value.id
                    func_name = node.func.attr

                # 处理 Path().iterdir() 这样的调用
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                
                # 🚫 特殊处理：检测 __import__('ctypes') 这样的调用
                if isinstance(node.func, ast.Name):
                    if node.func.id == '__import__':
                        # 检查参数中是否包含 'ctypes'
                        if node.args and isinstance(node.args[0], ast.Constant):
                            import_name = node.args[0].value
                            if import_name == 'ctypes' or (isinstance(import_name, str) and import_name.startswith('ctypes')):
                                self.dangerous_calls.append(
                                    f"在 {node.lineno} 行: 禁止动态导入 ctypes 模块"
                                )

                # 检查是否是危险调用
                if module_name and func_name:
                    for mod, func, msg in DANGEROUS_CALLS:
                        if module_name == mod and func_name == func:
                            self.dangerous_calls.append(
                                f"在 {node.lineno} 行: {msg}"
                            )

                # 🚫 检查 Path 危险方法调用
                if isinstance(node.func, ast.Attribute):
                    # 检查是否是 Path 对象的方法调用
                    # 需要检查 node.func.value 是否是 Path 或 path-like 对象
                    func_name = node.func.attr

                    if func_name in FORBIDDEN_PATH_METHODS:
                        # 尝试确定是否是 Path 对象
                        is_path_call = False

                        # 情况1: Path().method()
                        if isinstance(node.func.value, ast.Call):
                            if isinstance(node.func.value.func, ast.Name):
                                if node.func.value.func.id == 'Path':
                                    is_path_call = True
                            elif isinstance(node.func.value.func, ast.Attribute):
                                if node.func.value.func.attr == 'Path':
                                    is_path_call = True

                        # 情况2: path_variable.method() (变量名包含 path)
                        elif isinstance(node.func.value, ast.Name):
                            if 'path' in node.func.value.id.lower():
                                is_path_call = True

                        if is_path_call:
                            self.dangerous_calls.append(
                                f"在 {node.lineno} 行: 禁止使用 Path.{func_name}() (可能绕过沙箱安全限制)"
                            )

                self.generic_visit(node)

        try:
            tree = ast.parse(code)
            checker = SafetyChecker()
            checker.visit(tree)

            if checker.dangerous_calls:
                error_msg = "安全错误：代码包含禁止的操作\n"
                error_msg += "\n".join(checker.dangerous_calls)
                raise ValueError(error_msg)
        except SyntaxError as e:
            raise SyntaxError(f"代码语法错误：{str(e)}")

    def _compile_code(self, code: str):
        """编译 Python 代码

        Args:
            code: 要编译的 Python 代码

        Returns:
            编译后的代码对象

        Raises:
            SyntaxError: 如果代码包含语法错误
        """
        # 使用标准 Python compile 编译代码
        try:
            compiled_code = compile(
                code,
                filename='<sandbox>',
                mode='exec'
            )

            return compiled_code
        except SyntaxError as e:
            raise SyntaxError(
                f"代码编译失败：{str(e)}"
            )

    def execute(self, command: str) -> ExecuteResponse:
        """执行受限的 Python 代码或脚本文件

        只支持两种格式：
        1. python -c "code" - 执行代码字符串
        2. python script.py [args...] - 执行脚本文件(支持参数)

        Args:
            command: 命令字符串（python -c "code" 或 python script.py [args...]）

        Returns:
            ExecuteResponse 包含输出、退出码和截断标志
        """
        try:
            # 步骤 1: 解析命令
            try:
                code, script_path, script_args = self._parse_command(command)
            except ValueError as e:
                return ExecuteResponse(
                    output=f"命令格式错误:\n{str(e)}",
                    exit_code=-1,
                    truncated=False
                )

            # 步骤 2: 如果是脚本文件，读取内容
            if script_path:
                try:
                    code = self._read_script_file(script_path)
                except FileNotFoundError as e:
                    return ExecuteResponse(
                        output=f"错误: 脚本文件不存在: {script_path}\n详细信息: {str(e)}",
                        exit_code=-1,
                        truncated=False
                    )
                except PermissionError as e:
                    return ExecuteResponse(
                        output=f"错误: 没有权限读取脚本文件: {script_path}\n详细信息: {str(e)}",
                        exit_code=-1,
                        truncated=False
                    )
                except Exception as e:
                    return ExecuteResponse(
                        output=f"错误: 读取脚本文件失败: {script_path}\n详细信息: {str(e)}",
                        exit_code=-1,
                        truncated=False
                    )

            # 去除代码两端的空白
            code = code.strip()

            if not code:
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
                    output=f"安全检查失败:\n{str(e)}",
                    exit_code=-1,
                    truncated=False
                )

            # 步骤 4: 编译代码
            try:
                compiled_code = self._compile_code(code)
            except SyntaxError as e:
                return ExecuteResponse(
                    output=f"语法错误: {str(e)}",
                    exit_code=-1,
                    truncated=False
                )

            # 步骤 4: 准备执行环境
            # 创建输出捕获器
            with OutputCapture() as output_capture:
                # 创建局部命名空间，初始化为 safe_globals 的副本
                # 这样导入的模块会被保存到这个字典中
                locals: Dict[str, Any] = self._safe_globals.copy()

                # 🔧 步骤 4.5: 设置线程本地变量（每个线程独立的 root_dir）
                # 这解决了多用户并发执行时的文件访问问题
                _thread_local.root_dir = self.root_dir

                # 🔧 步骤 4.6: 设置 sys.argv（用于脚本参数）
                # 如果是脚本文件执行，设置 sys.argv [脚本名, 参数1, 参数2, ...]
                # 如果是代码字符串执行，设置 sys.argv 为 ['-c']
                if script_path:
                    # 🎯 移除各种路径前缀：//, /, ./, ../, ../../../ 等
                    converted_args = []
                    for arg in script_args:
                        cleaned_arg = arg

                        # 移除所有连续的 ../
                        while cleaned_arg.startswith('../'):
                            cleaned_arg = cleaned_arg[3:]

                        # 移除其他路径前缀
                        for prefix in ['//', './', '/']:
                            if cleaned_arg.startswith(prefix):
                                cleaned_arg = cleaned_arg[len(prefix):]
                                break  # 只移除第一个匹配的前缀

                        converted_args.append(cleaned_arg)

                    locals['sys'].argv = [script_path] + converted_args
                else:
                    # 代码字符串：sys.argv = ['-c']
                    locals['sys'].argv = ['-c']

                try:
                    # 步骤 5: 执行代码（带超时）
                    exit_code = 0
                    

                    # 使用 locals 作为命名空间，这样导入的模块会被保存到 locals 中
                    exec(compiled_code, locals, locals)
                
                except SystemExit as e:
                    # SystemExit 表示程序主动退出，需要正确处理退出码
                    # e.code 可能是整数或 None（表示退出码为 0）
                    exit_code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
                    
                    # 获取输出（不附加错误信息，因为 SystemExit 是正常的退出）
                    output = output_capture.get_output()
                    
                    # 检查输出长度
                    truncated = len(output) > self.max_output_length
                    if truncated:
                        output = output[:self.max_output_length]
                        output += "\n\n... [输出被截断，超过最大长度限制] ..."
                    
                    return ExecuteResponse(
                        output=output,
                        exit_code=exit_code,
                        truncated=truncated
                    )
                except MemoryError:
                    exit_code = -1
                    return ExecuteResponse(
                        output="错误: 内存使用超过限制",
                        exit_code=exit_code,
                        truncated=False
                    )
                except RecursionError:
                    exit_code = -1
                    return ExecuteResponse(
                        output="错误: 递归深度超过限制（可能导致无限递归）",
                        exit_code=exit_code,
                        truncated=False
                    )
                except Exception as e:
                    # 捕获执行过程中的其他异常
                    import traceback
                    tb_str = traceback.format_exc()
                    exit_code = 1

                    # 获取输出并附加错误信息
                    output = output_capture.get_output()
                    output += f"\n[执行错误]\n{type(e).__name__}: {str(e)}\n{tb_str}"

                    # 检查输出长度
                    truncated = len(output) > self.max_output_length
                    if truncated:
                        output = output[:self.max_output_length]
                        output += "\n\n... [输出被截断，超过最大长度限制] ..."

                    return ExecuteResponse(
                        output=output,
                        exit_code=exit_code,
                        truncated=truncated
                    )
                finally:
                    # 🔧 清理线程本地变量（无论成功或失败）
                    try:
                        del _thread_local.root_dir
                    except (AttributeError, KeyError):
                        pass

            # 步骤 6: 获取输出
            output = output_capture.get_output()

            # 🔧 调试信息：如果完全没有输出，添加提示
            if not output or output.strip() == "":
                output = "[代码执行完成，但没有任何输出]\n提示：如果脚本使用了 print() 但没有看到输出，可能是:\n1. 输出被重定向到了文件而非 stdout\n2. 脚本在执行过程中遇到了静默错误\n3. 脚本仍在后台运行（如果超时机制未生效）"

            # 步骤 7: 检查输出长度并截断
            truncated = False
            if len(output) > self.max_output_length:
                output = output[:self.max_output_length]
                truncated = True
                output += "\n\n... [输出被截断，超过最大长度限制] ..."

            return ExecuteResponse(
                output=output,
                exit_code=exit_code,
                truncated=truncated
            )

        except Exception as e:
            # 捕获任何未预期的异常
            import traceback
            return ExecuteResponse(
                output=f"系统异常: {str(e)}\n{traceback.format_exc()}",
                exit_code=-1,
                truncated=False
            )