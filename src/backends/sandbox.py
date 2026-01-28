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

注意：
- safe_open 从线程本地变量读取 root_dir，每个线程独立
- 相对路径和绝对路径（以 / 开头）都会被重定向到当前线程的 root_dir
- 完全并发安全，无需使用锁
- 使用标准 Python compile 编译代码

只支持两种标准执行格式：
1. python -c "code" - 直接执行代码字符串
2. python script.py - 执行脚本文件
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

from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import SandboxBackendProtocol, ExecuteResponse




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
        # 从线程本地变量获取 root_dir
        root_dir = getattr(_thread_local, 'root_dir', None)
        
        # 🔧 回退机制：如果没有设置 root_dir，使用原始的 open
        if root_dir is None:
            # 不是 backend.execute() 调用，回退到原始行为
            return _original_builtins_open(filename, mode, *args, **kwargs)
        
        # 🔧 特殊处理：允许访问系统临时目录
        # 某些库（如 openpyxl、pandas、tempfile）需要使用系统临时目录
        import tempfile
        temp_dir = Path(tempfile.gettempdir()).resolve()
        
        # 解析原始路径（处理符号链接和相对路径）
        resolved_original_path = Path(filename).resolve()
        
        # 检查是否是系统临时目录下的文件
        try:
            resolved_original_path.relative_to(temp_dir)
            # 是系统临时目录，允许直接访问
            return _original_builtins_open(filename, mode, *args, **kwargs)
        except ValueError:
            # 不是系统临时目录，继续处理
            pass
        
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
            raise PermissionError(
                f"安全错误：禁止访问 root_dir 外的文件\n请求路径: {filename}\n解析路径: {resolved_path}\n允许目录: {root_dir}\n注意：路径遍历（..）和符号链接已被阻止"
            )
        
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
        
        # 🔧 特殊处理：允许访问系统临时目录
        import tempfile
        temp_dir = Path(tempfile.gettempdir()).resolve()
        
        # 解析原始路径（处理符号链接和相对路径）
        resolved_original_path = Path(filename).resolve()
        
        # 检查是否是系统临时目录下的文件
        try:
            resolved_original_path.relative_to(temp_dir)
            # 是系统临时目录，允许直接访问
            return _original_os_open(filename, flags, mode, *args, **kwargs)
        except ValueError:
            # 不是系统临时目录，继续处理
            pass
        
        # 处理路径：去掉开头的斜杠，然后添加 root_dir
        path_str = str(filename).lstrip('/')
        full_path = root_dir / path_str
        
        # 🔒 安全验证：解析为绝对路径并检查是否在 root_dir 内
        resolved_path = full_path.resolve()
        
        try:
            resolved_path.relative_to(root_dir)
        except ValueError:
            # 路径不在 root_dir 内，拒绝访问
            raise PermissionError(
                f"安全错误：禁止访问 root_dir 外的文件\n请求路径: {filename}\n解析路径: {resolved_path}\n允许目录: {root_dir}"
            )
        
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

def _get_safe_import():
    """创建安全的 __import__ 函数，拦截 os 模块的导入并替换 os.open"""
    # 获取原始的 __import__（处理 __builtins__ 可能是字典或模块的情况）
    if isinstance(__builtins__, dict):
        original_import = __builtins__['__import__']
    else:
        original_import = __builtins__.__import__
    
    def safe_import(name, *args, **kwargs):
        """安全的 import 函数"""
        # 先调用原始的 import
        module = original_import(name, *args, **kwargs)
        
        # 如果导入的是 os 模块，替换 os.open
        if name == 'os' and hasattr(module, 'open'):
            # 只在沙箱执行环境中替换（检查是否有 root_dir）
            if hasattr(_thread_local, 'root_dir') and _thread_local.root_dir is not None:
                module.open = _safe_os_open_func
        
        return module
    
    return safe_import

# 全局的 safe_import 函数
_safe_import_func = _get_safe_import()






class SandboxFilesystemBackend(FilesystemBackend, SandboxBackendProtocol):
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
            virtual_mode: bool = False,
            max_file_size_mb: int = 10,
            max_output_length: int = 100000,  # 100KB
            timeout_seconds: int = 30,
            max_memory_mb: int = 512,
            **kwargs
    ) -> None:
        """初始化安全沙箱

        Args:
            root_dir: 允许读写的根目录
            virtual_mode: 虚拟模式（由父类 FilesystemBackend 使用）
            max_file_size_mb: 最大文件大小限制（MB）
            max_output_length: 最大输出长度
            timeout_seconds: 执行超时时间（秒）
            max_memory_mb: 最大内存限制（MB）
        """
        # 设置根目录
        self.root_dir = Path(root_dir) if root_dir else Path(tempfile.mkdtemp())
        self.root_dir = self.root_dir.resolve()

        self.max_output_length = max_output_length
        self.timeout_seconds = timeout_seconds
        self.max_memory_mb = max_memory_mb

        # 调用父类初始化
        super().__init__(
            root_dir=str(self.root_dir),
            virtual_mode=virtual_mode,
            max_file_size_mb=max_file_size_mb,
        )

        # 初始化安全的执行环境
        self._safe_globals = self._create_safe_globals()

    def _parse_command(self, command: str) -> tuple[Optional[str], Optional[str]]:
        """解析命令，只支持两种标准格式

        支持的格式：
        1. python -c "code" - 执行代码字符串
        2. python script.py - 执行脚本文件

        Args:
            command: 命令字符串

        Returns:
            (code, script_path) 元组
            - 如果是 python -c 格式：code 为代码字符串，script_path 为 None
            - 如果是 python script.py 格式：code 为 None，script_path 为脚本路径

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
            return code, None

        # 格式 2: python script.py
        # 支持：python script.py, python /path/to/script.py, python3 script.py
        # 所有路径都会以 root_dir 为根目录处理
        pattern_script = r'^(?:python(?:3)?|/usr/bin/python(?:3)?)\s+([^\s]+)$'
        match_script = re.match(pattern_script, command, re.IGNORECASE)

        if match_script:
            script_path = match_script.group(1).strip()
            # 🎯 所有脚本路径都以 root_dir 为根
            # 去掉开头的斜杠，因为所有路径都是相对于 root_dir 的
            script_path = script_path.lstrip('/')
            # 拼接 root_dir 前缀
            script_path = str(self.root_dir / script_path)
            return None, script_path

        # 不支持的格式
        raise ValueError(
            f"不支持的命令格式: '{command}'\n"
            f"只支持以下两种格式：\n"
            f"  1. python -c \"code\"      - 执行代码字符串\n"
            f"  2. python script.py         - 执行脚本文件\n"
            f"  3. python /path/to/script.py - 执行脚本文件（绝对路径）"
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
        
        # 同时在全局变量中注入 io 和 codecs 模块
        safe_globals['io'] = io
        safe_globals['codecs'] = codecs
        safe_globals['Path'] = Path
        
        # 注入 builtins 模块到全局变量中
        safe_globals['builtins'] = builtins

        # 保留 print 函数（内置的）
        safe_globals['print'] = print

        # 添加一些有用的常量和函数
        safe_globals['__name__'] = '__main__'
        safe_globals['__doc__'] = None

        return safe_globals



    def _set_resource_limits(self):
        """设置资源限制（内存、CPU 等）"""
        try:
            # 设置内存限制（仅在 Unix 系统上有效）
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            new_limit = self.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (new_limit, hard))

            # 设置 CPU 时间限制
            cpu_limit = self.timeout_seconds + 5  # 留一点余量
            soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, hard))

        except (ValueError, resource.error, AttributeError):
            # 在 Windows 或不支持的平台忽略错误
            pass




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
            ('pathlib', 'Path', '禁止使用 pathlib.Path 进行目录操作'),
        ]

        # 禁止的 Path 方法
        FORBIDDEN_PATH_METHODS = ['iterdir', 'glob', 'rglob', 'unlink']

        class SafetyChecker(ast.NodeVisitor):
            def __init__(self):
                self.dangerous_calls = []

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

                # 检查是否是危险调用
                if module_name and func_name:
                    for mod, func, msg in DANGEROUS_CALLS:
                        if module_name == mod and func_name == func:
                            self.dangerous_calls.append(
                                f"在 {node.lineno} 行: {msg}"
                            )

                # 检查 Path 危险方法
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in FORBIDDEN_PATH_METHODS:
                        self.dangerous_calls.append(
                            f"在 {node.lineno} 行: 禁止使用 Path.{node.func.attr}()"
                        )

                self.generic_visit(node)

        try:
            tree = ast.parse(code)
            checker = SafetyChecker()
            checker.visit(tree)

            if checker.dangerous_calls:
                error_msg = "安全错误：代码包含禁止的操作\n"
                error_msg += "\n".join(checker.dangerous_calls)
                error_msg += "\n\n原因：为了保护系统安全，禁止以下危险操作："
                error_msg += "\n  - 删除、移动、重命名文件"
                error_msg += "\n  - 修改文件权限"
                error_msg += "\n  - 列出目录内容"
                error_msg += "\n  - 遍历目录"
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
        2. python script.py - 执行脚本文件

        Args:
            command: 命令字符串（python -c "code" 或 python script.py）

        Returns:
            ExecuteResponse 包含输出、退出码和截断标志
        """
        try:
            # 步骤 1: 解析命令
            try:
                code, script_path = self._parse_command(command)
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

                try:
                    # 步骤 5: 执行代码（带超时）
                    exit_code = 0
                    
                    # 设置资源限制
                    self._set_resource_limits()
                    
                    # 执行代码
                    # 使用 locals 作为命名空间，这样导入的模块会被保存到 locals 中
                    exec(compiled_code, locals, locals)
                
                except MemoryError:
                    exit_code = -1
                    return ExecuteResponse(
                        output=f"错误: 内存使用超过限制 ({self.max_memory_mb} MB)",
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