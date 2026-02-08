# Python 沙箱安全执行器（路径重定向方案）

这是一个安全的 Python 代码执行沙箱，使用**路径重定向和权限控制**在受限环境中运行用户代码，防止访问系统文件和执行危险操作。

## 🚀 快速开始

```python
from sandbox.pycode_executor import CodeExecutor

# 创建沙箱执行器
executor = CodeExecutor(
    root_dir="/tmp/sandbox",
    timeout=30,
    readable_paths=["/usr/lib", "/opt"],  # 可选：只读白名单
    writable_paths=["/tmp/cache"]          # 可选：读写白名单
)

# 执行代码字符串
result = executor.execute('python -c "print(\'Hello World\')"')
print(result.output)  # Hello World
print(result.exit_code)  # 0

# 执行脚本文件
result = executor.execute('python /skills/script.py arg1 arg2')
```

## 🔒 安全特性

### 核心安全机制

#### 1. 路径重定向（Path Redirection）
所有文件操作自动重定向到沙箱目录，**无需 chroot**，完全透明的路径隔离：

```
相对路径  → 自动加 root_dir 前缀
绝对路径  → 按优先级检查后重定向到 root_dir
```

**路径处理优先级顺序**：
1. **root_dir 内**：可读写
2. **readable_paths**：只读访问（如 .venv、/usr/lib）
3. **writable_paths**：可读写（如 /tmp/cache）
4. **其他绝对路径**：自动重定向到 `root_dir/`
5. **相对路径**：自动重定向到 `root_dir/`

#### 2. 受限的文件操作
包装所有文件操作接口，确保路径检查：

- ✅ `open()` - 受限的文件打开函数
- ✅ `os` 模块 - 所有路径操作都经过重定向
- ✅ `os.path` 模块 - 15+ 函数全部包装
- ✅ `tarfile` 模块 - 防止绕过限制
- ✅ `pathlib.Path` - 所有操作都受限

#### 3. AST 语法层检查
- ❌ 禁止执行系统命令 (`os.system`, `subprocess`, `os.popen`)
- ❌ 禁止动态导入危险模块 (`ctypes`, `importlib`, `pickle`)
- ❌ 禁止危险内置函数 (`exec`, `eval`, `compile`)
- ❌ 禁止进程操作 (`fork`, `multiprocessing`, `threading`)
- ❌ 禁止绕过文件限制的模块 (`io`, `codecs`)

#### 4. 进程隔离
- 🚧 每个执行在独立子进程，彻底隔离
- 🚧 子进程崩溃不影响主进程
- 🚧 使用 `multiprocessing.Queue` 传递结果
- 🚧 超时保护（`signal.SIGALRM`）

## 📋 支持的执行格式

### 1. 直接执行代码字符串
```bash
python -c "print('Hello World')"
```

### 2. 执行脚本文件
```bash
python /skills/script.py [arg1] [arg2] ...
```

## 🛠️ 使用示例

### 基本文件操作（路径重定向）
```python
# 所有路径自动重定向到 root_dir
code = '''
from pathlib import Path
p = Path("/tmp/test.txt")  # 实际创建在 root_dir/tmp/test.txt
p.write_text("Hello Sandbox")
print("File created:", p.exists())
'''
result = executor.execute(f'python -c "{code}"')
```

### 白名单路径访问
```python
executor = CodeExecutor(
    root_dir="/tmp/sandbox",
    readable_paths=["/usr/lib/python3.12"],  # 可以读取系统库
    writable_paths=["/tmp/cache"]             # 可以写入缓存目录
)

# 可以访问只读白名单
code = '''
import os
# 可以读取 readable_paths 中的文件
libs = os.listdir("/usr/lib/python3.12")
print(f"Found {len(libs)} system files")
'''
result = executor.execute(f'python -c "{code}"')
```

### 目录操作（全部重定向）
```python
code = '''
import os
import tarfile

# 所有路径都被重定向
os.makedirs("/skills/test", exist_ok=True)
with open("/skills/test/data.txt", "w") as f:
    f.write("Hello")

# tarfile 也被包装，不会绕过限制
with tarfile.open("/skills/test.tar.gz", "w:gz") as tar:
    tar.add("/skills/test/data.txt")

# os.path 所有函数都重定向
exists = os.path.exists("/skills/test/data.txt")
print(f"File exists: {exists}")
items = os.listdir("/skills/test")
print(f"Directory contents: {items}")
'''
result = executor.execute(f'python -c "{code}"')
```

### 路径遍历测试（无法逃逸）
```python
code = '''
import os
# 尝试访问父目录
try:
    with open("../../etc/passwd", "r") as f:
        print(f.read())
except FileNotFoundError:
    print("Access blocked: path redirected to root_dir")

# 验证实际路径
print(f"Current: {os.getcwd()}")
print(f"/tmp/test → {os.path.abspath('/tmp/test')}")
'''
# 输出: Access blocked: path redirected to root_dir
#       /tmp/test → /your/root_dir/tmp/test
```

### 超时保护
```python
code = '''
import time
print("Starting sleep...")
time.sleep(60)  # 超过默认超时时间
print("Woke up")
'''
result = executor.execute(f'python -c "{code}"')
# 输出: 执行超时（超过 30 秒）
```

## 🏗️ 架构设计

### 路径重定向模型

```
用户代码: open("/tmp/file.txt", "w")
    ↓
restricted_open() 拦截
    ↓
路径重定向逻辑:
    1. 检查是否在 root_dir 内 → 不在
    2. 检查是否在 readable_paths → 不在
    3. 检查是否在 writable_paths → 不在
    4. 重定向到 root_dir/tmp/file.txt
    ↓
original_open(root_dir/tmp/file.txt, "w")
```

### 模块包装层次

```
用户代码调用:
    ├─ open() → restricted_open()
    ├─ os.xxx() → RestrictedOS → redirect_path() → os.xxx()
    ├─ os.path.xxx() → RestrictedOsPath → redirect_path() → os.path.xxx()
    ├─ tarfile.open() → RestrictedTarfile → redirect_path() → tarfile.open()
    └─ pathlib.Path → _RestrictedPath → restricted_open()
```

### 核心组件

#### 1. restricted_open()
```python
def restricted_open(file, mode='r', *args, **kwargs):
    """
    路径处理顺序：
    1. root_dir 内 → 可读写
    2. readable_paths → 只读
    3. writable_paths → 可读写
    4. 其他绝对路径 → 重定向到 root_dir
    5. 相对路径 → 重定向到 root_dir
    """
```

#### 2. redirect_path()
```python
def redirect_path(path_str):
    """
    统一的路径重定向函数
    - 用于所有模块包装器
    - 确保路径处理一致性
    """
```

#### 3. RestrictedOS
```python
class RestrictedOS:
    """
    包装 os 模块的所有文件操作函数：
    - mkdir, makedirs, remove, rmdir, removedirs
    - rename, replace, renames, listdir
    - 所有函数都先调用 redirect_path()
    """
```

#### 4. RestrictedOsPath
```python
class RestrictedOsPath:
    """
    包装 os.path 模块的 15+ 函数：
    - exists, isfile, isdir, getsize
    - join, dirname, basename, split
    - abspath, realpath, relpath
    - getmtime, getatime, getctime
    - isabs, splitext
    """
```

#### 5. RestrictedTarfile
```python
class RestrictedTarfile:
    """
    包装 tarfile 模块：
    - tarfile.open() → 防止绕过限制
    - tarfile.is_tarfile()
    """
```

### 进程隔离架构

```
主进程（Main Process）
    ↓
1. 代码解析和 AST 安全检查
    ↓
2. 创建子进程（multiprocessing.Process）
    ↓
子进程（Child Process）
    ↓
3. 注入受限模块到 sys.modules:
   - sys.modules['os'] = RestrictedOS
   - sys.modules['os.path'] = RestrictedOsPath
   - sys.modules['tarfile'] = RestrictedTarfile
   - sys.modules['pathlib'] = RestrictedPathlib
    ↓
4. 编译和执行代码
    ↓
5. 捕获输出和异常
    ↓
6. 结果通过 Queue 传回主进程
    ↓
7. 恢复原始模块（finally 块）
    ↓
主进程
    ↓
8. 等待子进程完成（带超时）
    ↓
9. 返回 ExecuteResponse
```

## ✅ 已包装的函数列表

### os 模块（9个）
- `os.mkdir()` - 创建目录
- `os.makedirs()` - 递归创建目录
- `os.remove()` - 删除文件
- `os.rmdir()` - 删除目录
- `os.removedirs()` - 递归删除目录
- `os.rename()` - 重命名文件（带权限检查）
- `os.replace()` - 替换文件（带权限检查）
- `os.renames()` - 递归重命名（带权限检查）
- `os.listdir()` - 列出目录内容

### os.path 模块（15个）
- `exists()` - 检查路径是否存在
- `isfile()` - 检查是否是文件
- `isdir()` - 检查是否是目录
- `join()` - 连接路径
- `dirname()` - 获取目录名
- `basename()` - 获取基础文件名
- `split()` - 分割路径
- `splitext()` - 分割扩展名
- `abspath()` - 获取绝对路径
- `realpath()` - 获取真实路径
- `relpath()` - 获取相对路径
- `isabs()` - 检查是否是绝对路径
- `getsize()` - 获取文件大小
- `getmtime()` - 获取修改时间
- `getatime()` - 获取访问时间
- `getctime()` - 获取创建时间

### tarfile 模块（2个）
- `tarfile.open()` - 打开 tarball（重定向路径）
- `tarfile.is_tarfile()` - 检查是否是 tarball

### pathlib.Path
- 所有操作都经过 `restricted_open()`

### 内置函数
- `open()` → `restricted_open()`

## 🎯 设计优势

### 1. 无需 chroot
- ✅ 不需要 root 权限
- ✅ 不影响系统库访问（.venv 可以用）
- ✅ 网络功能正常
- ✅ 完全透明的路径重定向

### 2. 统一的路径处理
- ✅ 所有文件操作使用相同的重定向逻辑
- ✅ 严格按优先级顺序检查
- ✅ 无歧义的路径解析

### 3. 全面的模块包装
- ✅ 覆盖所有常见文件操作
- ✅ 防止绕过限制
- ✅ 保持 API 兼容性

### 4. 进程级隔离
- ✅ 子进程崩溃不影响主进程
- ✅ 独立的内存空间
- ✅ 超时保护

### 5. 灵活的权限控制
- ✅ root_dir 内完全访问
- ✅ readable_paths 只读访问
- ✅ writable_paths 读写访问
- ✅ 其他路径自动重定向

## ⚠️ 安全注意事项

### 已知限制
1. **进程隔离**：虽然有路径重定向，但仍依赖进程隔离
2. **网络访问**：没有网络访问限制
3. **符号链接**：符号链接可能指向沙箱外
4. **硬链接**：硬链接可能访问外部文件

### 使用建议
- ✅ 定期审查代码逻辑
- ✅ 监控资源使用
- ✅ 设置合理的超时时间
- ✅ 谨慎配置 readable_paths 和 writable_paths
- ✅ 在生产环境配合容器使用

## 🐛 故障排除

### 文件操作失败

**症状**：`FileNotFoundError` 或 `PermissionError`
**检查**：
- 路径是否在 readable_paths/writable_paths 中
- 是否尝试写入只读路径
- 路径重定向是否符合预期

**调试**：
```python
import os
print(f"Real path: {os.path.abspath('/test/file.txt')}")
# 输出: /your/root_dir/test/file.txt
```

### 模块导入问题

**症状**：`ImportError` 或 `AttributeError`
**原因**：模块被安全检查阻止
**解决**：移除危险模块导入

### 超时问题

**症状**：`执行超时（超过 X 秒）`
**解决**：
1. 增加超时时间
2. 检查代码逻辑
3. 添加进度输出

## 📊 性能考虑

- **进程创建开销**：每次执行创建新进程，约 10-50ms
- **内存使用**：每个子进程独立内存，约 10-50MB
- **路径检查开销**：每个文件操作增加约 0.1-1ms
- **并发性能**：可同时运行多个子进程（受系统资源限制）

## 🧪 测试覆盖

项目包含全面的测试套件（45+ 测试用例）：

- ✅ 文件操作测试（创建、读取、写入、删除）
- ✅ 路径重定向测试（绝对、相对、嵌套路径）
- ✅ 权限控制测试（root_dir、readable_paths、writable_paths）
- ✅ 安全检查测试（危险函数、模块）
- ✅ 标准库可用性测试（json、datetime、re 等）
- ✅ 边界情况测试（空文件、大文件、特殊字符）
- ✅ os/os.path/tarfile 测试
- ✅ 脚本执行测试

运行测试：
```bash
python tests/test_sandbox/test_comprehensive.py
```

## 🔄 版本历史

### v3.0.0（路径重定向方案）
- ✨ 完全移除 chroot
- ✨ 实现统一的路径重定向机制
- ✨ 包装 os、os.path、tarfile 模块
- ✨ 严格的路径处理优先级
- ✨ 支持 readable_paths 和 writable_paths
- 🐛 修复所有已知安全问题
- 📚 完善文档和测试

### v2.0.0（进程隔离方案 - 已废弃）
- ~ 使用子进程隔离~
- ~ 使用 os.chdir() 隔离工作目录~

### v1.0.0（旧方案 - 已废弃）
- ~ 使用 threading.local() + monkey patching~

## 📄 许可证

MIT License - 详见项目根目录 LICENSE 文件

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进沙箱安全性。
