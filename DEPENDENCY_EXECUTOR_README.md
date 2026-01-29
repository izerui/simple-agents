# 依赖安装执行器 (DependencyExecutor)

## 概述

`DependencyExecutor` 是一个专门用于执行 Python 依赖管理命令的安全执行器。它提供了受控的方式来安装和查询依赖包，同时确保环境的安全性。

## 文件结构

- `src/sandbox/dependency_executor.py` - 依赖安装执行器的核心实现
- `src/sandbox/sandbox_filesystem.py` - 集成了依赖安装执行器的沙箱后端

## 主要特性

### 支持的命令

1. **安装单个包（仅限新安装，不允许升级或重装）**
   ```bash
   uv pip install <package>
   uv pip install requests numpy pandas
   uv pip install --index-url https://pypi.org/simple/ requests
   uv pip install --dry-run requests
   uv pip install --verbose requests
   ```

2. **查询已安装的包**
   ```bash
   uv pip list
   uv pip show <package>
   uv pip freeze
   uv pip check
   ```

### 安全限制

为了确保环境安全和可预测性，以下操作被**明确禁止**：

- ❌ **批量安装**：不支持 `uv pip install -r requirements.txt`
- ❌ **卸载操作**：不支持 `uv pip uninstall <package>`
- ❌ **升级已安装的包**：不支持 `--upgrade` 或 `-U` 选项
- ❌ **强制重新安装**：不支持 `--force-reinstall` 或 `--reinstall` 选项
- ❌ **升级策略**：不支持 `--upgrade-strategy` 选项
- ❌ **忽略已安装版本**：不支持 `--ignore-installed` 选项
- ❌ **非 uv pip 命令**：只支持 `uv pip` 相关命令

**设计理念**：只允许安装新的依赖包，禁止任何可能改变现有环境状态的操作，确保环境的稳定性和可预测性。

### 安全特性

- **命令验证**：所有命令在执行前都会经过严格验证
- **超时控制**：默认 5 分钟超时，可配置
- **输出截断**：限制输出长度（默认 100KB），防止内存溢出
- **错误处理**：完善的错误捕获和友好的错误消息

## 使用方法

### 通过 SandboxFilesystemBackend 使用（推荐）

```python
from src.sandbox.sandbox_filesystem import SandboxFilesystemBackend

# 创建沙箱后端
sandbox = SandboxFilesystemBackend(
    root_dir="/path/to/workspace",
    max_output_length=50000,
)

# 统一入口：execute 方法会自动判断使用哪个执行器
# 1. 依赖安装命令 -> 自动使用 DependencyExecutor
response = sandbox.execute("uv pip install requests")
print(response.output)
print("退出码:", response.exit_code)

# 2. Python 代码执行 -> 自动使用 CodeExecutor
response = sandbox.execute('python -c "print(\'Hello\')"')
print(response.output)

# 3. Python 脚本执行 -> 自动使用 CodeExecutor
response = sandbox.execute("python script.py")
print(response.output)
```

### 直接使用 DependencyExecutor

```python
from src.sandbox.dependency_executor import DependencyExecutor

# 初始化执行器
executor = DependencyExecutor(
    root_dir="/path/to/workspace",
    max_output_length=50000,  # 50KB
    timeout=300,  # 5分钟
)

# 安装包
response = executor.execute("uv pip install requests")
print(response.output)
print("退出码:", response.exit_code)

# 查询已安装的包
response = executor.execute("uv pip list")
print(response.output)

# 查看包详情
response = executor.execute("uv pip show requests")
print(response.output)
```

### SandboxFilesystemBackend 统一入口

`SandboxFilesystemBackend.execute()` 方法提供了统一的执行入口，会根据命令类型自动选择合适的执行器：

#### 自动路由规则

1. **uv pip 命令** → `DependencyExecutor`
   - 命令以 `uv pip` 开头（不区分大小写）
   - 用于依赖安装和查询操作

2. **python 命令** → `CodeExecutor`
   - 其他命令格式
   - 用于 Python 代码执行

#### 使用示例

```python
from src.sandbox.sandbox_filesystem import SandboxFilesystemBackend

sandbox = SandboxFilesystemBackend(
    root_dir="/path/to/workspace",
    max_output_length=50000,
)

# 统一使用 execute 方法，无需手动选择执行器
response = sandbox.execute("uv pip install requests")  # 自动路由到 DependencyExecutor
response = sandbox.execute('python -c "print(1+1)"')   # 自动路由到 CodeExecutor
response = sandbox.execute("python script.py")         # 自动路由到 CodeExecutor
```

## 命令验证规则

### 必须满足的条件

1. 命令必须以 `uv pip` 开头
2. 子命令必须是以下之一：`install`, `list`, `show`, `freeze`, `check`
3. `install` 命令不能使用 `-r` 或 `--requirement` 选项
4. 不能包含 `uninstall` 操作

### 有效的命令示例

```bash
# 基本安装
uv pip install requests

# 安装多个包
uv pip install requests numpy pandas

# 带安全选项的安装（不会改变现有环境）
uv pip install --verbose requests
uv pip install --index-url https://pypi.org/simple/ requests
uv pip install --dry-run requests
uv pip install --no-deps requests
```

# 查询命令
uv pip list
uv pip show requests
uv pip freeze
uv pip check
```

### 无效的命令示例

```bash
# 不支持批量安装
uv pip install -r requirements.txt
uv pip install --requirement requirements.txt

# 不支持卸载
uv pip uninstall requests

# 不支持升级（会改变现有环境）
uv pip install --upgrade requests
uv pip install -U requests

# 不支持强制重装
uv pip install --force-reinstall requests
uv pip install --reinstall requests

# 不支持升级策略
uv pip install --upgrade-strategy eager requests

# 不支持忽略已安装版本
uv pip install --ignore-installed requests

# 不支持其他命令
python -c "print(1)"
pip install requests
ls -la
```

## API 参考

### SandboxFilesystemBackend.execute（统一入口）

```python
def execute(self, command: str) -> ExecuteResponse
```

**描述：** 统一的命令执行入口，自动路由到合适的执行器

**参数：**
- `command`: 命令字符串（支持 uv pip 或 python 命令）

**返回：**
- `ExecuteResponse` 对象

**路由规则：**
- 命令以 `uv pip` 开头 → 使用 `DependencyExecutor`
- 其他命令 → 使用 `CodeExecutor`

**示例：**
```python
# 依赖管理
response = sandbox.execute("uv pip install requests")
response = sandbox.execute("uv pip list")
response = sandbox.execute("uv pip show requests")

# Python 代码执行
response = sandbox.execute('python -c "print(1+1)"')
response = sandbox.execute("python script.py")
```

### DependencyExecutor 类

#### 构造函数

```python
def __init__(
    root_dir: Optional[Union[str, Path]] = None,
    max_output_length: int = 100000,
    timeout: int = 300,
    **kwargs
)
```

**参数：**
- `root_dir`: 工作目录（用于相对路径），默认为当前目录
- `max_output_length`: 最大输出长度（字节），默认 100KB
- `timeout`: 命令执行超时时间（秒），默认 300 秒（5 分钟）

#### 方法

##### execute

```python
def execute(self, command: str) -> ExecuteResponse
```

**参数：**
- `command`: 依赖安装命令字符串

**返回：**
- `ExecuteResponse` 对象，包含：
  - `output`: 命令输出（stdout + stderr）
  - `exit_code`: 退出码（0 表示成功）

##### _parse_command（内部方法）

```python
def _parse_command(self, command: str) -> tuple[bool, Optional[str]]
```

验证命令格式。

**参数：**
- `command`: 命令字符串

**返回：**
- `(is_valid, error_message)` 元组

#### DependencyExecutor._truncate_output（内部方法）

```python
def _truncate_output(self, output: str) -> str
```

截断输出到最大长度。

### ExecuteResponse 类

```python
class ExecuteResponse:
    output: str           # 命令输出
    exit_code: int | None # 退出码
```

## 测试

测试文件位于：`tests/sandbox_test/test_dependency_executor.py`

运行测试：

```bash
python3 tests/sandbox_test/test_dependency_executor.py
```

测试覆盖：
- ✅ 有效的命令格式验证
- ✅ 无效的命令格式拒绝
- ✅ 多个包安装
- ✅ 带选项的命令
- ✅ 输出截断
- ✅ 超时处理
- ✅ 错误处理

## 示例程序

完整的示例程序位于：`tests/sandbox_test/example_dependency_install.py`

运行示例：

```bash
python3 tests/sandbox_test/example_dependency_install.py
```

## 注意事项

1. **uv 必须安装**：执行器依赖 `uv` 命令，确保系统中已安装
2. **权限要求**：执行安装操作可能需要适当的权限
3. **虚拟环境**：建议在虚拟环境中使用，避免污染系统 Python
4. **超时设置**：根据网络环境调整超时时间
5. **输出限制**：大量输出的命令可能被截断

## 设计理念

- **安全性优先**：通过严格的命令验证和操作限制来保护环境，禁止任何可能改变现有状态的操作
- **统一接口**：通过 `SandboxFilesystemBackend.execute()` 提供统一的执行入口，自动路由到合适的执行器
- **简单易用**：提供清晰的 API 和友好的错误消息
- **可配置性**：允许自定义超时、输出限制等参数
- **职责分离**：与 `CodeExecutor` 分离，专门处理依赖管理
- **环境稳定性**：只允许安装新包，确保现有环境不会被意外破坏

## 更新日志

### v1.0.0 (当前版本)

- ✅ 初始版本
- ✅ 支持安全的包安装和查询操作
- ✅ 禁止批量安装和卸载操作
- ✅ 禁止升级、强制重装等破坏性操作
- ✅ 完善的命令验证和错误处理
- ✅ 超时控制和输出截断
- ✅ 完整的测试覆盖