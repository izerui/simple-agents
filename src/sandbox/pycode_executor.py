# -*- coding: utf-8 -*-
"""
安全沙箱后端（只支持标准执行格式）

实现基于 os.chroot() 的真正文件系统隔离：
- root_dir 变成新的根目录 /
- 无法访问 root_dir 外的任何文件
- 需要 root 权限运行

新进程隔离方案：
- 每次代码执行在独立子进程中进行
- 使用 os.chroot() 将 root_dir 设为新的根目录
- 使用 multiprocessing.Queue 进行进程间通信
- 彻底解决多线程安全问题

安全拦截机制（多重保护）：
1. chroot 文件系统隔离：
   - 内核级别的文件系统隔离
   - /etc/passwd 实际访问的是 root_dir/etc/passwd
   - 无法通过任何方式访问 root_dir 外的文件
2. AST 语法层检查：阻止危险函数调用（os.system, subprocess等）
3. 进程隔离：每个执行在独立子进程，避免污染主进程
4. 超时保护：防止无限循环和资源耗尽
5. 输出限制：防止输出过大

只支持两种标准执行格式：
1. python -c "code" - 直接执行代码字符串
2. python script.py [args...] - 执行脚本文件(支持参数)
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
        script_args,
        result_queue,
        timeout
):
    """
    在子进程中执行代码

    Args:
        code: 要执行的代码
        root_dir: 沙箱根目录
        script_args: 脚本参数
        result_queue: 结果队列（用于传递结果回主进程）
        timeout: 超时时间（秒）
    """
    try:
        # 使用 chroot 进行文件系统隔离（需要 root 权限）
        try:
            # 先切换到 root_dir
            os.chdir(root_dir)
            # 执行 chroot，将 root_dir 作为新的根目录
            os.chroot(root_dir)
            # 切换到新根目录
            os.chdir('/')
            print("  [子进程] Chroot 设置成功")
        except PermissionError:
            # 如果没有 root 权限，返回错误
            print("  [子进程] ✗ Chroot 权限错误")
            result_queue.put(ExecuteResult(
                output="错误: chroot 需要 root 权限，请使用 sudo 运行",
                exit_code=-1,
                error="chroot 需要 root 权限"
            ))
            return

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

        safe_globals = {
            '__builtins__': builtins,
            '__name__': '__main__',
            '__file__': '<sandbox>',
            'print': print,
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

        # 添加系统模块（chroot 已隔离，可以直接使用）
        safe_globals['sys'] = sys
        safe_globals['os'] = os
        safe_globals['Path'] = Path

        # 设置 sys.argv
        if script_args:
            safe_globals['sys'].argv = script_args
        else:
            safe_globals['sys'].argv = ['-c']

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
            except RecursionError:
                print("  [子进程] ✗ 递归错误")
                exit_code = -1
            except Exception as e:
                # 执行错误
                print("  [子进程] ✗ 执行异常: {0}".format(type(e).__name__))
                exit_code = 1
                tb_str = traceback.format_exc()

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
        result_queue.put(ExecuteResult(
            output="执行超时: {0}".format(str(e)),
            exit_code=-1,
            error=str(e)
        ))
    except MemoryError as e:
        print("  [子进程] ✗ 内存错误")
        result_queue.put(ExecuteResult(
            output="错误: 内存使用超过限制",
            exit_code=-1,
            error=str(e)
        ))
    except RecursionError as e:
        print("  [子进程] ✗ 递归错误")
        result_queue.put(ExecuteResult(
            output="错误: 递归深度超过限制（可能导致无限递归）",
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
    安全沙箱执行器（基于 os.chroot 隔离）

    使用子进程隔离执行环境，每个代码执行在独立进程中，
    通过 os.chroot() 进行真正的文件系统隔离，彻底解决安全问题。
    """

    def __init__(self, root_dir=None, timeout=30, max_output_length=100 * 1024):
        """
        初始化沙箱执行器

        Args:
            root_dir: 沙箱根目录（如果为 None，使用系统临时目录）
            timeout: 执行超时时间（秒）
            max_output_length: 最大输出长度（字节）

        注意：
            - 必须使用 root 权限运行（sudo）
            - root_dir 将成为新的根目录 /
            - 无法访问 root_dir 外的任何文件
        """
        self.root_dir = Path(root_dir)
        # self.root_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.max_output_length = max_output_length

    def _parse_command(self, command):
        """
        解析命令字符串

        支持格式：
        1. python -c "code" - 执行代码字符串
        2. python script.py [args...] - 执行脚本文件

        Returns:
            (code, script_path, script_args)
            - code: 代码字符串（如果是脚本，为 None）
            - script_path: 脚本路径（如果是代码字符串，为 None）
            - script_args: 脚本参数列表
        """
        parts = command.strip().split()

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

        注意：由于 chroot 已提供文件系统隔离，open() 函数可以正常使用

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
                            'os': ['system', 'popen', 'spawn', 'fork', 'forkpty'],
                            'subprocess': ['run', 'call', 'Popen', 'check_output'],
                            'commands': ['getoutput', 'getstatusoutput'],
                            'ctypes': None,  # ctypes 模块的所有函数都危险
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

                    # 危险模块列表
                    dangerous_modules = [
                        'subprocess', 'commands', 'ctypes', 'importlib',
                        'pickle', 'marshal', 'shelve',
                        'multiprocessing', 'threading', 'signal',
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

                # 危险模块列表
                dangerous_modules = [
                    'subprocess', 'commands', 'ctypes', 'importlib',
                    'pickle', 'marshal', 'shelve',
                    'multiprocessing', 'threading', 'signal',
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
                args=(code, str(self.root_dir), script_args, result_queue, self.timeout)
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