# Python 沙箱执行器 - chroot 模式

## 概述

基于 **os.chroot()** 的真正文件系统隔离沙箱。

### 特性

- ✅ **内核级文件系统隔离**：无法访问 root_dir 外的任何文件
- ✅ **简单直接**：只需要 root 权限，无需复杂配置
- ✅ **跨平台**：支持 Linux 和 macOS
- ✅ **透明隔离**：用户代码无需修改

---

## 工作原理

```python
# 执行前
os.chroot(root_dir)  # 将 root_dir 设为新的根目录
os.chdir('/')        # 切换到新根目录

# 执行后
/etc/passwd         # 实际访问 root_dir/etc/passwd
/tmp/               # 实际访问 root_dir/tmp/
```

---

## 使用方法

### 基本用法

```python
from src.sandbox.pycode_executor import CodeExecutor

# 创建执行器（需要 root 权限）
executor = CodeExecutor(
    root_dir="/tmp/my_sandbox",
    timeout=30
)

# 执行代码
result = executor.execute('python -c "print(\'Hello!\')"')
print(result.output)
```

### 运行要求

```bash
# 必须使用 root 权限运行
sudo python your_script.py
```

---

## 测试

运行完整测试：

```bash
sudo python test_sandbox/test_chroot_only.py
```

测试内容：
- ✅ 无法访问 `/etc/passwd`
- ✅ 无法写入 `/tmp/`
- ✅ 可以在 sandbox 内读写文件
- ✅ pathlib 模块正常工作
- ✅ os 模块正常工作

---

## 安全性

### 隔离保证

| 操作 | chroot 模式 | 说明 |
|------|-----------|------|
| 访问 `/etc/passwd` | ❌ 无法访问 | 实际访问 `root_dir/etc/passwd` |
| 写入 `/tmp/` | ❌ 无法写入 | 实际写入 `root_dir/tmp/` |
| 使用 pathlib | ✅ 正常 | chroot 已隔离 |
| 使用 ctypes | ⚠️ 理论可逃逸 | 需要通过 AST 检查拦截 |

### 多重保护

1. **chroot 文件系统隔离**（内核级）
2. **AST 语法检查**（阻止 os.system、subprocess 等）
3. **进程隔离**（每个执行在独立子进程）
4. **超时保护**（防止无限循环）

---

## 与其他方案对比

| 方案 | 隔离强度 | 需要权限 | 配置复杂度 |
|------|---------|---------|----------|
| chroot | ⭐⭐⭐⭐ | root | ⭐ 简单 |
| Docker | ⭐⭐⭐⭐⭐ | root | ⭐⭐ 中等 |
| 函数级限制 | ⭐⭐ | 无 | ⭐⭐⭐ 复杂 |
| seccomp | ⭐⭐⭐⭐ | 无 | ⭐⭐⭐⭐ 很复杂 |

---

## 常见问题

### Q: 为什么需要 root 权限？
A: `os.chroot()` 是特权操作，需要 CAP_SYS_CHROOT 权限（通常是 root）

### Q: chroot 后 Python 解释器能正常工作吗？
A: 可以！因为 Python 解释器已经在内存中加载，chroot 不影响已加载的代码

### Q: 能逃逸吗？
A: 理论上可以通过 ctypes 调用系统调用逃逸，但 AST 检查会拦截 ctypes 导入

### Q: macOS 和 Linux 有区别吗？
A: 基本相同，但 macOS 的 chroot 功能略有限制

---

## 示例

### 示例 1: 执行简单代码

```python
executor = CodeExecutor(root_dir="/tmp/sandbox")
result = executor.execute('python -c "print(1 + 1)"')
print(result.output)  # 输出: 2
```

### 示例 2: 文件操作

```python
# 在 sandbox 内创建文件
result = executor.execute('python -c "open(\'data.txt\', \'w\').write(\'secret\')"')

# 文件实际位置: /tmp/sandbox/data.txt
# 外部无法访问: /etc/passwd → /tmp/sandbox/etc/passwd
```

### 示例 3: 超时保护

```python
executor = CodeExecutor(root_dir="/tmp/sandbox", timeout=5)
result = executor.execute('python -c "import time; time.sleep(100)"')
# 5 秒后自动终止
```

---

## 总结

**chroot 模式适合的场景：**
- ✅ 有 root 权限的环境
- ✅ 需要强文件系统隔离
- ✅ 简单易用的解决方案

**不适合的场景：**
- ❌ 没有 root 权限
- ❌ 需要网络隔离（chroot 不隔离网络）
- ❌ 需要资源限制（需要 cgroup）

**推荐：生产环境结合 Docker 使用**
