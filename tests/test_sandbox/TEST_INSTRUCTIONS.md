# chroot 沙箱测试指南

## 快速测试

```bash
# 方式 1: 直接运行 Python
sudo python test_sandbox/test_chroot_only.py

# 方式 2: 使用测试脚本
sudo bash test_sandbox/run_chroot_tests.sh
```

---

## 预期测试结果

### 测试 1: 无法访问 /etc/passwd
```
✅ 正确：无法访问系统的 /etc/passwd
```

### 测试 2: 无法写入 /tmp/
```
✅ 正确：无法写入 /tmp/
```

### 测试 3: 可以在 sandbox 内读写文件
```
✅ 正确：可以在 sandbox 内读写文件
```

### 测试 4: pathlib 模块正常工作
```
✅ 正确：pathlib 在 sandbox 内正常工作
```

### 测试 5: os 模块正常工作
```
显示 sandbox 内的文件列表
```

---

## 手动验证

### 验证 1: 文件系统隔离

```python
from src.sandbox.pycode_executor import CodeExecutor

executor = CodeExecutor(root_dir="/tmp/test_sandbox")

# 尝试访问外部文件
result = executor.execute('python -c "open(\'/etc/passwd\', \'r\').read()"')
print(result.exit_code)  # 应该 != 0

# 检查文件是否真的被隔离
import os
if os.path.exists('/tmp/test_sandbox/etc/passwd'):
    print("✅ chroot 生效：/etc/passwd 被重定向到 sandbox")
```

### 验证 2: 在 sandbox 内正常工作

```python
# 创建文件
result = executor.execute('python -c "open(\'test.txt\', \'w\').write(\'hello!\')"')

# 读取文件
result = executor.execute('python -c "print(open(\'test.txt\').read())"')
print(result.output)  # 应该输出: hello!

# 检查文件位置
import os
print(os.path.exists('/tmp/test_sandbox/test.txt'))  # 应该是 True
```

---

## 故障排查

### 问题: "chroot 需要 root 权限"

**解决方案**:
```bash
# 使用 sudo
sudo python your_script.py

# 或者检查当前用户
whoami  # 应该是 root
id -u   # 应该是 0
```

### 问题: 测试失败但没有明确错误

**检查步骤**:
1. 确认有 root 权限
2. 确认 sandbox 目录存在
3. 查看详细输出
4. 检查系统日志

```bash
# 检查权限
sudo -v

# 查看详细错误
sudo python test_sandbox/test_chroot_only.py 2>&1 | tee test_output.log
```

---

## 性能测试

```python
import time
from src.sandbox.pycode_executor import CodeExecutor

executor = CodeExecutor(root_dir="/tmp/sandbox")

# 测试执行速度
start = time.time()
for i in range(10):
    executor.execute('python -c "print(1 + 1)"')
end = time.time()

print(f"平均执行时间: {(end - start) / 10:.3f} 秒")
```

---

## 安全验证

### 验证隔离强度

```python
# 这些操作都应该失败
tests = [
    'open("/etc/passwd", "w").write("x")',  # 写入系统文件
    'open("/tmp/hack.txt", "w").write("x")',  # 写入 /tmp
    'import os; os.system("cat /etc/hosts")',  # 执行命令
]

for test in tests:
    result = executor.execute(f'python -c "{test}"')
    print(f"测试: {test[:50]}")
    print(f"  退出码: {result.exit_code} (应该 != 0)")
    print()
```

---

## 下一步

测试通过后，可以：

1. **集成到项目**
   ```python
   from src.sandbox.pycode_executor import CodeExecutor

   executor = CodeExecutor(root_dir="/app/sandbox")
   result = executor.execute(user_code)
   ```

2. **配置日志**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **设置资源限制**（可选）
   ```python
   # 使用 ulimit 或 cgroup 限制内存
   # 或使用 Docker 容器
   ```
