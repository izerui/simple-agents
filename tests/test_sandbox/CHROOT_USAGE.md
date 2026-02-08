# Python 沙箱执行器 - 使用指南

## 概述

本沙箱执行器提供**两种隔离模式**：

1. **chroot 模式** - 真正的文件系统隔离（需要 root 权限）
2. **兼容模式** - 函数级权限控制（不需要 root 权限）

---

## 模式对比

| 特性 | chroot 模式 | 兼容模式 |
|------|-----------|---------|
| **隔离强度** | ⭐⭐⭐⭐⭐ 完全隔离 | ⭐⭐⭐ 函数级限制 |
| **需要权限** | ❌ 需要 root | ✅ 普通用户 |
| **root_dir 外读取** | ❌ 完全无法访问 | ✅ 允许只读 |
| **root_dir 外写入** | ❌ 完全无法访问 | ❌ 被拦截 |
| **配置复杂度** | ⭐ 简单 | ⭐ 简单 |
| **适用场景** | 生产环境 | 开发环境 |

---

## 使用方法

### 1. chroot 模式（需要 root）

```python
from src.sandbox.pycode_executor import CodeExecutor

# 创建执行器（启用 chroot）
executor = CodeExecutor(
    root_dir="/tmp/my_sandbox",
    timeout=30,
    use_chroot=True  # 启用 chroot 模式
)

# 执行代码
result = executor.execute('python -c "print(\'Hello from sandbox!\')"')
print(result.output)
```

**运行要求：**
```bash
# 使用 sudo 运行
sudo python your_script.py

# 或者设置 setuid 位（需要额外配置）
sudo chown root:root your_script.py
sudo chmod 4755 your_script.py
```

**隔离效果：**
- ✅ 无法访问 `root_dir` 外的任何文件
- ✅ `/etc/passwd` → `root_dir/etc/passwd`
- ✅ `/tmp/` → `root_dir/tmp/`

---

### 2. 兼容模式（不需要 root）

```python
from src.sandbox.pycode_executor import CodeExecutor

# 创建执行器（禁用 chroot）
executor = CodeExecutor(
    root_dir="/tmp/my_sandbox",
    timeout=30,
    use_chroot=False  # 禁用 chroot 模式
)

# 执行代码
result = executor.execute('python -c "print(\'Hello from sandbox!\')"')
print(result.output)
```

**运行要求：**
```bash
# 普通用户直接运行
python your_script.py
```

**隔离效果：**
- ✅ `root_dir` 内：允许读写
- ✅ `root_dir` 外：只允许只读
- ❌ 写入外部文件会被拦截

---

## 安全性说明

### chroot 模式安全性

**优点：**
- ✅ **真正的文件系统隔离**：内核级别的隔离
- ✅ **无法绕过**：即使使用 ctypes 也无法访问外部文件
- ✅ **透明隔离**：用户代码无需修改

**注意事项：**
- ⚠️ 需要设置完整的 chroot 环境（Python 解释器、库等）
- ⚠️ 需要 root 权限
- ⚠️ 在 macOS 上功能有限（相比 Linux）

### 兼容模式安全性

**优点：**
- ✅ 不需要特殊权限
- ✅ 跨平台兼容
- ✅ 简单易用

**注意事项：**
- ⚠️ 理论上可以通过 ctypes 绕过（需要进一步限制）
- ⚠️ 需要拦截 `import os`、`import pathlib` 等
- ⚠️ AST 检查可能有遗漏

---

## 测试

### 运行测试

```bash
# 测试兼容模式（不需要 root）
python test_sandbox/test_chroot_mode.py

# 测试 chroot 模式（需要 root）
sudo python test_sandbox/test_chroot_mode.py
```

### 测试结果

**兼容模式测试：**
```
✅ 兼容模式生效：可以读取外部文件
✅ 函数级限制生效：无法写入外部文件
✅ 正常：可以在 root_dir 内写入
```

---

## 推荐配置

### 开发环境
```python
# 使用兼容模式，方便调试
executor = CodeExecutor(
    root_dir="./sandbox",
    timeout=30,
    use_chroot=False
)
```

### 生产环境
```python
# 使用 chroot 模式，最高安全性
executor = CodeExecutor(
    root_dir="/var/sandbox",
    timeout=30,
    use_chroot=True
)
```

### 混合方案
```python
# 自动检测是否有 root 权限
import os

has_root = (os.geteuid() == 0)
executor = CodeExecutor(
    root_dir="/tmp/sandbox",
    timeout=30,
    use_chroot=has_root  # 自动选择模式
)
```

---

## 常见问题

### Q1: chroot 模式报错 "Operation not permitted"
**A:** chroot 需要 root 权限，请使用 `sudo` 运行

### Q2: chroot 后代码报错找不到模块
**A:** 需要在 `root_dir` 内创建完整的 Python 环境，包括：
- Python 解释器
- 标准库
- 所有依赖的 `.so` 文件

### Q3: 兼容模式能否完全防止逃逸？
**A:** 不能 100% 保证，但对于大多数场景已经足够。生产环境建议使用 chroot 模式或 Docker

### Q4: 能否使用 Docker 代替？
**A:** 可以！Docker 提供更强的隔离，推荐生产环境使用

---

## 总结

| 场景 | 推荐方案 |
|------|---------|
| 本地开发 | 兼容模式（use_chroot=False） |
| CI/CD | chroot 模式（use_chroot=True） |
| 生产环境 | Docker 容器 |
| 最高安全性 | chroot + seccomp + Docker |
