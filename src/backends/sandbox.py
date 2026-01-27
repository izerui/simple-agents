# -*- coding: utf-8 -*-
"""
基于 RestrictedPython 的安全沙箱后端 V2（只支持标准执行格式）

实现文件操作权限控制：
- root_dir 内：允许读写
- root_dir 外：只允许只读

只支持两种标准执行格式：
1. python -c "code" - 直接执行代码字符串
2. python script.py - 执行脚本文件
"""
import sys
import io
import signal
import resource
from pathlib import Path
import tempfile
from typing import Optional, Union, Any, Dict
import re

try:
    from RestrictedPython import compile_restricted, safe_builtins
    from RestrictedPython.PrintCollector import PrintCollector
    from RestrictedPython.Guards import safer_getattr, full_write_guard, guarded_iter_unpack_sequence
except ImportError:
    raise ImportError(
        "请先安装 RestrictedPython: pip install RestrictedPython\n"
        "项目地址: https://github.com/zopefoundation/RestrictedPython"
    )

from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import SandboxBackendProtocol, ExecuteResponse


class TimeoutException(Exception):
    """执行超时异常"""
    pass


def timeout_handler(signum, frame):
    """超时信号处理器"""
    raise TimeoutException("代码执行超时")


class RestrictedOutputCapture:
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
    
    def get_output(self, print_collector=None) -> str:
        """获取所有输出
        
        Args:
            print_collector: RestrictedPython 的 PrintCollector 实例
        """
        # 如果有 PrintCollector 实例，先调用它获取收集的输出
        output = ""
        if print_collector and hasattr(print_collector, '__call__'):
            try:
                collected = print_collector()
                if collected:
                    output += collected
            except Exception:
                pass
        
        # 添加 stdout 和 stderr
        stdout = self.stdout_buffer.getvalue()
        stderr = self.stderr_buffer.getvalue()
        output += stdout
        if stderr:
            output += f"\n[错误输出]\n{stderr}"
        return output


class FileAccessControl:
    """文件访问控制类"""
    
    def __init__(self, root_dir: Path):
        """初始化文件访问控制
        
        Args:
            root_dir: 允许读写的根目录
        """
        self.root_dir = root_dir.resolve()
    
    def is_inside_root_dir(self, file_path: Path) -> bool:
        """检查文件路径是否在 root_dir 内
        
        Args:
            file_path: 文件路径
            
        Returns:
            True 如果在 root_dir 内，False 否则
        """
        try:
            # 解析为绝对路径并解析符号链接
            resolved_path = file_path.resolve()
            # 检查是否在 root_dir 内
            resolved_path.relative_to(self.root_dir)
            return True
        except (ValueError, RuntimeError):
            # ValueError: 路径不在 root_dir 内
            # RuntimeError: 符号链接循环等
            return False
    
    def get_file_mode_permission(self, mode: str):
        """判断文件模式的读写权限
        
        Args:
            mode: 文件打开模式（如 'r', 'w', 'a', 'rb', 'wb' 等）
            
        Returns:
            (can_read, can_write) 元组
        """
        mode = mode.lower()
        
        # 默认可以读取
        can_read = 'r' in mode or '+' in mode
        
        # 判断是否可以写入
        can_write = any(c in mode for c in ['w', 'a'])
        
        return can_read, can_write
    
    def validate_file_access(self, file_path: Union[str, Path], mode: str = 'r') -> Path:
        """验证文件访问权限并返回验证后的绝对路径
        
        Args:
            file_path: 文件路径
            mode: 文件打开模式
            
        Returns:
            验证后的绝对路径
            
        Raises:
            PermissionError: 如果权限不足
            FileNotFoundError: 如果文件不存在且尝试读取
        """
        file_path = Path(file_path)
        
        # 如果是相对路径，先转换为绝对路径（相对于 root_dir）
        if not file_path.is_absolute():
            file_path = (self.root_dir / file_path).resolve()
        else:
            file_path = file_path.resolve()
        
        can_read, can_write = self.get_file_mode_permission(mode)
        
        # 检查是否在 root_dir 内
        is_inside = self.is_inside_root_dir(file_path)
        
        if not is_inside:
            # 🔒 安全修复：完全禁止 root_dir 外的访问
            raise PermissionError(
                f"禁止访问 root_dir 外的文件: {file_path}\n"
                f"出于安全考虑，沙箱只允许访问 root_dir 内的文件"
            )
        else:
            # root_dir 内：允许所有操作
            # 如果是写入模式，确保父目录存在
            if can_write:
                parent_dir = file_path.parent
                if not parent_dir.exists():
                    # 再次确认父目录在 root_dir 内
                    try:
                        parent_dir.relative_to(self.root_dir)
                    except ValueError:
                        raise PermissionError(
                            f"只能在 root_dir 内创建目录: {parent_dir}"
                        )
                    # 尝试创建父目录
                    try:
                        parent_dir.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        raise PermissionError(
                            f"无法创建目录 {parent_dir}: {str(e)}"
                        )
        
        # 返回验证后的绝对路径
        return file_path


class RestrictedPythonBackend(FilesystemBackend, SandboxBackendProtocol):
    """
    基于 RestrictedPython 的安全沙箱后端 V2（只支持标准执行格式）
    
    特性：
    - 使用 RestrictedPython 编译受限代码
    - root_dir 内：允许读写文件
    - root_dir 外：只允许只读文件访问
    - 超时和资源限制
    - 捕获所有输出
    
    只支持两种执行格式：
    1. python -c "code" - 直接执行代码字符串
    2. python script.py - 执行脚本文件
    """
    
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
        """初始化 RestrictedPython 沙箱
        
        Args:
            root_dir: 允许读写的根目录
            virtual_mode: 虚拟模式
            max_file_size_mb: 最大文件大小限制（MB）
            max_output_length: 最大输出长度
            timeout_seconds: 执行超时时间（秒）
            max_memory_mb: 最大内存限制（MB）
        """
        # 设置根目录
        self.root_dir = Path(root_dir) if root_dir else Path(tempfile.mkdtemp())
        self.root_dir = self.root_dir.resolve()
        
        # 确保根目录存在
        self.root_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_output_length = max_output_length
        self.timeout_seconds = timeout_seconds
        self.max_memory_mb = max_memory_mb
        
        # 初始化文件访问控制
        self.file_access_control = FileAccessControl(self.root_dir)
        
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
        pattern_script = r'^(?:python(?:3)?|/usr/bin/python(?:3)?)\s+([^\s]+)$'
        match_script = re.match(pattern_script, command, re.IGNORECASE)
        
        if match_script:
            script_path = match_script.group(1).strip()
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
            script_path: 脚本文件路径
            
        Returns:
            脚本文件内容
            
        Raises:
            FileNotFoundError: 如果文件不存在
            PermissionError: 如果没有读取权限
        """
        # 验证并获取绝对路径
        validated_path = self.file_access_control.validate_file_access(script_path, 'r')
        
        # 读取文件内容
        try:
            with open(str(validated_path), 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # 如果不是 UTF-8 编码，尝试使用系统默认编码
            with open(str(validated_path), 'r') as f:
                return f.read()
    
    def _create_safe_globals(self) -> dict:
        """创建安全的全局变量字典
        
        Returns:
            安全的全局变量字典
        """
        # 创建基础的全局变量字典
        safe_globals = {
            '__builtins__': {
                'None': None,
                'True': True,
                'False': False,
                'int': int,
                'float': float,
                'str': str,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'bool': bool,
                'len': len,
                'range': range,
                'type': type,
                'isinstance': isinstance,
                'hasattr': hasattr,
                'getattr': getattr,
                'setattr': setattr,
                'delattr': delattr,
                'min': min,
                'max': max,
                'sum': sum,
                'abs': abs,
                'round': round,
                'sorted': sorted,
                'reversed': reversed,
                'enumerate': enumerate,
                'zip': zip,
                'map': map,
                'filter': filter,
                'all': all,
                'any': any,
                'print': print,
                '__import__': __import__,
            }
        }
        
        # 添加受限的 open 函数
        safe_open = self._create_safe_open()
        safe_globals['open'] = safe_open
        safe_globals['__builtins__']['open'] = safe_open
        
        # 添加其他安全的全局函数
        safe_globals['print'] = print
        
        # RestrictedPython 需要的特殊全局函数
        # _print_: 用于捕获 print 输出
        safe_globals['_print_'] = PrintCollector
        # _getattr_: 安全的属性访问
        safe_globals['_getattr_'] = safer_getattr
        # _write_: 安全的属性写入
        safe_globals['_write_'] = full_write_guard
        # _getitem_: 安全的索引访问（用于 obj[key] 这样的操作）
        safe_globals['_getitem_'] = lambda obj, key: obj[key]
        # _getiter_: 安全的迭代器获取（用于 for 循环）
        safe_globals['_getiter_'] = iter
        # _unpack_sequence_: 序列解包（用于 a, b = [1, 2] 这样的操作）
        safe_globals['_unpack_sequence_'] = guarded_iter_unpack_sequence
        # _iter_unpack_sequence_: 迭代器序列解包（用于 a, b = (x for x in ...) 这样的操作）
        safe_globals['_iter_unpack_sequence_'] = guarded_iter_unpack_sequence
        
        # 添加一些有用的常量和函数
        safe_globals['__name__'] = '__main__'
        safe_globals['__doc__'] = None
        
        return safe_globals
    
    def _create_safe_open(self):
        """创建受限的 open 函数"""
        file_access_control = self.file_access_control
        
        def safe_open(filename: Union[str, Path], mode: str = 'r', *args, **kwargs):
            """受限的 open 函数
            
            权限规则：
            - root_dir 内：允许所有读写操作
            - root_dir 外：只允许只读操作
            
            Args:
                filename: 文件名
                mode: 打开模式
                *args, **kwargs: 其他参数
                
            Returns:
                文件对象
                
            Raises:
                PermissionError: 权限不足
                FileNotFoundError: 文件不存在
            """
            # 验证文件访问权限并获取验证后的绝对路径
            validated_path = file_access_control.validate_file_access(filename, mode)
            
            # 使用验证后的路径打开文件
            return open(str(validated_path), mode, *args, **kwargs)
        
        return safe_open
    
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
    
    def _compile_restricted_code(self, code: str):
        """编译受限的 Python 代码
        
        Args:
            code: 要编译的 Python 代码
            
        Returns:
            编译后的代码对象
            
        Raises:
            SyntaxError: 如果代码包含受限语法
        """
        # 使用 RestrictedPython 编译代码
        compiled_code = compile_restricted(
            code,
            filename='<restricted>',
            mode='exec'
        )
        
        # 检查编译是否成功
        if compiled_code is None:
            raise SyntaxError(
                "代码编译失败：包含受限的语法或不安全的操作"
            )
        
        return compiled_code
    
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
            
            # 步骤 3: 编译受限代码
            try:
                compiled_code = self._compile_restricted_code(code)
            except SyntaxError as e:
                return ExecuteResponse(
                    output=f"语法错误: {str(e)}",
                    exit_code=-1,
                    truncated=False
                )
            
            # 步骤 4: 准备执行环境
            # 创建输出捕获器
            with RestrictedOutputCapture() as output_capture:
                # 创建局部命名空间
                restricted_locals: Dict[str, Any] = {}
                
                # 步骤 5: 执行代码（带超时）
                exit_code = 0
                
                try:
                    # 设置资源限制
                    self._set_resource_limits()
                    
                    # 设置超时信号（仅在 Unix 系统上）
                    if hasattr(signal, 'SIGALRM'):
                        signal.signal(signal.SIGALRM, timeout_handler)
                        signal.alarm(self.timeout_seconds)
                    
                    # 执行受限代码
                    try:
                        exec(compiled_code, self._safe_globals, restricted_locals)
                    finally:
                        # 取消超时信号
                        if hasattr(signal, 'SIGALRM'):
                            signal.alarm(0)
                            
                except TimeoutException:
                    exit_code = -1
                    return ExecuteResponse(
                        output=f"错误: 代码执行超时（超过 {self.timeout_seconds} 秒）",
                        exit_code=exit_code,
                        truncated=False
                    )
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
                    
                    # 获取 PrintCollector 实例
                    print_collector = restricted_locals.get('_print')
                    
                    # 获取输出并附加错误信息
                    output = output_capture.get_output(print_collector)
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
            
            # 步骤 6: 获取输出（包括 PrintCollector 收集的输出）
            print_collector = restricted_locals.get('_print')
            output = output_capture.get_output(print_collector)
            
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