# Python 沙箱文件系统隔离方案对比

## 方案 1: os.chroot()

### 原理
```python
os.chroot(root_dir)  # 改变进程的根目录
os.chdir('/')        # 切换到新根目录
```

### 优点
- ✅ **真正的文件系统隔离**：无法访问 `root_dir` 之外的任何文件
- ✅ **简单直接**：只需要两行代码
- ✅ **跨平台**：Linux 和 macOS 都支持

### 缺点
- ❌ **必须需要 root 权限**（或 CAP_SYS_CHROOT）
- ❌ **需要完整的环境**：需要在 `root_dir` 内复制：
  - Python 解释器
  - 所有依赖的 .so 文件
  - 标准库
- ❌ **维护复杂**：需要管理 chroot 环境内的所有依赖

### 实现示例
```python
import os
import subprocess

def setup_chroot_env(root_dir):
    """设置 chroot 环境（需要 root）"""
    # 1. 复制 Python 到 chroot 环境
    python_path = '/usr/bin/python3'
    subprocess.run(['cp', python_path, f'{root_dir}/bin/python'])

    # 2. 复制必要的库文件
    subprocess.run(['cp', '-r', '/usr/lib', f'{root_dir}/usr/lib'])

    # 3. 执行 chroot
    os.chroot(root_dir)
    os.chdir('/')
```

### 结论
**不推荐**：需要 root 权限，且环境设置复杂

---

## 方案 2: 函数级权限控制（当前方案）

### 原理
```python
# 替换 open、Path、os 等模块为受限版本
restricted_open = _create_restricted_open(root_dir)
safe_globals['open'] = restricted_open
```

### 优点
- ✅ **不需要特殊权限**
- ✅ **跨平台**：Linux/macOS/Windows 都可用
- ✅ **灵活**：可以精确控制读写权限
- ✅ **简单**：不需要设置额外环境

### 缺点
- ⚠️ **需要拦截 import**：防止用户重新导入原始模块
- ⚠️ **不是 100% 安全**：可能有绕过方法（如使用 ctypes）

### 改进方案
```python
# 1. 在 AST 检查中拦截所有 import
# 2. 只允许使用预定义的受限模块

def _check_code_safety(self, code):
    """AST 安全检查 - 拦截危险导入"""
    tree = ast.parse(code)

    class ImportBlocker(ast.NodeVisitor):
        def visit_Import(self, node):
            for alias in node.names:
                if alias.name in ['os', 'pathlib']:
                    raise SyntaxError(
                        f"不允许导入 '{alias.name}'，请使用提供的受限版本"
                    )
        def visit_ImportFrom(self, node):
            if node.module in ['os', 'pathlib']:
                raise SyntaxError(
                    f"不允许从 '{node.module}' 导入，请使用提供的受限版本"
                )

    ImportBlocker().visit(tree)
```

### 结论
**推荐作为基础方案**，但需要配合 AST 检查拦截 import

---

## 方案 3: RestrictedPython 库

### 原理
```python
from RestrictedPython import compile_restricted

code = compile_restricted(user_code, '<sandbox>', 'exec')
exec(code, restricted_globals)
```

### 优点
- ✅ **成熟的解决方案**：久经考验
- ✅ **编译时限制**：比运行时更安全
- ✅ **功能丰富**：提供了多种安全策略

### 缺点
- ⚠️ **需要安装第三方库**
- ⚠️ **学习曲线**：需要了解其 API
- ⚠️ **不能直接限制文件操作**：需要额外定制

### 安装
```bash
pip install RestrictedPython
```

### 结论
**推荐用于生产环境**

---

## 方案 4: Docker 容器（最强隔离）

### 原理
```bash
docker run -v $root_dir:/workspace -w /workspace python:3.12
```

### 优点
- ✅ **最强的隔离**：完整的容器级别隔离
- ✅ **资源限制**：可以限制 CPU、内存等
- ✅ **网络隔离**：可以禁用网络
- ✅ **成熟的生态系统**

### 缺点
- ❌ **需要安装 Docker**
- ⚠️ **启动开销**：每个容器启动需要时间

### Python 代码示例
```python
import docker

client = docker.from_env()
result = client.containers.run(
    "python:3.12",
    "python -c 'print(\"hello\")'",
    volumes={str(root_dir): {'bind': '/workspace', 'mode': 'rw'}},
    working_dir='/workspace',
    mem_limit='100m',
    network_disabled=True,
    remove=True
)
```

### 结论
**生产环境推荐**

---

## 推荐方案（分层策略）

### 1. 开发环境
使用**函数级权限控制 + AST 检查**
- 不需要额外依赖
- 快速迭代

### 2. 生产环境
使用**Docker 容器**
- 最强的隔离
- 可靠的安全保障

### 3. 混合方案
```python
def execute_safely(code, root_dir):
    """分层安全策略"""
    # 第一层：AST 检查（快速失败）
    check_ast_safety(code)

    # 第二层：函数级限制（防止逃逸）
    result = execute_with_restrictions(code, root_dir)

    # 可选：第三层：Docker 容器（生产环境）
    # result = execute_in_docker(code, root_dir)

    return result
```

---

## 当前问题

测试结果显示：
- ❌ `from pathlib import Path` 会绕过限制（重新导入原始 Path）
- ❌ `import os` 会绕过限制

**解决方案**：在 AST 检查中拦截这些导入

---

## 下一步行动

### 选择 1: 完善当前方案（推荐）
- 在 AST 检查中拦截 `import os` 和 `import pathlib`
- 提供文档说明使用内置的受限版本

### 选择 2: 切换到 RestrictedPython
- 更成熟，但需要迁移代码

### 选择 3: 使用 Docker（生产环境）
- 最安全，但需要 Docker 环境

**你想选择哪个方案？**
