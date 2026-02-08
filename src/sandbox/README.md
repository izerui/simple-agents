# Python 沙箱安全执行器（新进程隔离方案）

这是一个安全的 Python 代码执行沙箱，使用**新进程隔离方案**在受限环境中运行用户代码，防止访问系统文件和执行危险操作。

## 🚀 快速开始

```python
from sandbox.pycode_executor import CodeExecutor

# 创建沙箱执行器
executor = CodeExecutor(root_dir="/tmp/sandbox", timeout=30)

# 执行代码字符串
result = executor.execute('python -c "print(\'Hello World\')"')
print(result.output)  # Hello World
print(result.exit_code)  # 0

# 执行脚本文件
result = executor.execute('python script.py arg1 arg2')
```

## 🔒 安全特性

### 新进程隔离架构
- **进程级隔离**：每次代码执行在独立子进程中进行，彻底隔离执行环境
- **工作目录切换**：子进程使用 `os.chdir()` 切换到 `root_dir`，实现工作目录隔离
- **进程间通信**：使用 `multiprocessing.Queue` 传递执行结果
- **超时保护**：使用 `signal.SIGALRM` 实现超时控制，防止无限循环
- **自动清理**：子进程结束后自动释放资源，避免资源泄漏

### 多重安全保护

#### 1. AST 语法层检查
- ❌ 禁止执行系统命令 (`os.system`, `subprocess`, `os.popen`)
- ❌ 禁止动态导入危险模块 (`ctypes`, `importlib`)
- ❌ 禁止环境变量访问 (`os.environ`)
- ❌ 禁止进程操作 (`fork`, `multiprocessing`, `threading`)
- ❌ 禁止反序列化库 (`pickle`, `marshal`, `shelve`)

#### 2. 进程隔离
- 🚧 每个执行在独立子进程，互不干扰
- 🚧 子进程崩溃不影响主进程
- 🚧 内存隔离，防止内存污染

#### 3. 资源限制
- 📊 输出长度限制（默认 100KB）
- ⏱️ 执行超时保护（默认 30 秒）
- 💾 异常捕获和错误隔离

## 📋 支持的执行格式

### 1. 直接执行代码字符串
```bash
python -c "print('Hello World')"
```

### 2. 执行脚本文件
```bash
python script.py [arg1] [arg2] ...
```

## 🛠️ 使用示例

### 基本文件操作
```python
# 创建文件
code = '''
from pathlib import Path
p = Path("test.txt")
p.write_text("Hello Sandbox")
print("File created:", p.exists())
'''
result = executor.execute(f'python -c """{code}"""')
```

### 目录操作
```python
# 创建目录和子文件
code = '''
import os
os.makedirs("subdir", exist_ok=True)
with open("subdir/data.txt", "w") as f:
    f.write("Nested content")
print("Directory contents:", os.listdir("."))
'''
result = executor.execute(f'python -c """{code}"""')
```

### 路径遍历测试
```python
# 尝试访问父目录（会被 os.chdir 隔离，无法逃逸）
code = '''
import os
print("Current directory:", os.getcwd())
try:
    with open("../outside.txt", "r") as f:
        print(f.read())
except IOError as e:
    print("Access blocked:", str(e))
'''
result = executor.execute(f'python -c """{code}"""')
# 输出: Current directory: /tmp/sandbox
#       Access blocked: ... （因为实际访问的是 /tmp/sandbox/../outside.txt）
```

### 超时保护
```python
# 执行超时的代码
code = '''
import time
print("Starting sleep...")
time.sleep(60)  # 休眠 60 秒，超过默认超时时间
print("Woke up")
'''
result = executor.execute(f'python -c """{code}"""')
# 输出: 执行超时: 代码执行超时（超过 30 秒）
```

## 🏗️ 架构设计

### 新进程隔离模型

```
主进程（Main Process）
    ↓
1. 代码解析和 AST 安全检查
    ↓
2. 创建子进程（multiprocessing.Process）
    ↓
子进程（Child Process）
    ↓
3. os.chdir(root_dir) - 切换工作目录
    ↓
4. 编译和执行代码
    ↓
5. 捕获输出和异常
    ↓
6. 结果通过 Queue 传回主进程
    ↓
主进程
    ↓
7. 等待子进程完成（带超时）
    ↓
8. 返回 ExecuteResponse
```

### 与旧方案对比

| 特性 | 旧方案（线程 + Monkey Patching） | 新方案（进程隔离） |
|------|--------------------------------|------------------|
| 隔离级别 | 线程级 | 进程级 |
| 工作目录切换 | 无（路径重定向） | os.chdir() |
| 函数替换 | builtins.open, os.open | 无需替换 |
| 复杂度 | 高（递归风险） | 低（清晰简洁） |
| 安全性 | 中等（线程干扰） | 高（完全隔离） |
| 性能 | 高（同进程） | 中等（进程创建开销） |
| 兼容性 | 需要 monkey patching | 标准 Python 特性 |

### 优势

1. **彻底隔离**：进程级隔离，完全独立
2. **简洁可靠**：无需 monkey patching，避免递归问题
3. **标准特性**：使用 Python 标准 multiprocessing 模块
4. **易于维护**：代码结构清晰，易于理解和扩展
5. **安全增强**：子进程崩溃不影响主进程

### 权衡

- **进程创建开销**：每次执行创建新进程，有一定开销
- **内存占用**：每个子进程独立内存空间
- **适用场景**：适合执行用户代码的场景，不适合高频小任务

## ⚠️ 安全注意事项

### 已知限制
1. **CPU 密集型任务**：依赖超时保护，但仍可能占用 CPU
2. **内存限制**：依赖操作系统的内存管理
3. **网络访问**：没有网络访问限制
4. **符号链接**：符号链接可能指向沙箱外（建议限制）

### 使用建议
- ✅ 在生产环境中，建议结合容器或虚拟机使用
- ✅ 定期更新和审查安全策略
- ✅ 监控资源使用情况
- ✅ 对敏感操作进行额外验证
- ✅ 设置合理的超时时间

## 🔍 安全审计要点

### 代码审查清单
- [x] 进程隔离机制是否正确实现
- [x] os.chdir() 是否在子进程开始时调用
- [x] AST 安全检查是否覆盖所有危险操作
- [x] 超时机制是否可靠
- [x] 异常处理是否完善
- [x] 进程间通信是否安全
- [x] 子进程是否正确清理资源

### 渗透测试建议
1. **路径遍历测试**：尝试 `../../../etc/passwd`（会被 os.chdir 隔离）
2. **符号链接测试**：创建指向外部的符号链接
3. **硬链接测试**：尝试创建硬链接到外部文件
4. **进程测试**：尝试 fork、multiprocessing（AST 层阻止）
5. **网络测试**：验证网络访问是否被适当限制
6. **超时测试**：验证超时机制是否有效

### 性能考虑
- **进程创建开销**：每次执行创建新进程，约 10-50ms
- **内存使用**：每个子进程独立内存，约 10-50MB
- **并发性能**：可同时运行多个子进程（受系统资源限制）
- **通信开销**：Queue 传递结果，开销较小

## 🐛 故障排除

### 子进程异常退出

**症状**：`错误: 子进程异常退出，没有返回结果`
**原因**：子进程崩溃或被强制终止
**解决**：
1. 检查代码是否有语法错误
2. 检查是否有未捕获的异常
3. 查看系统日志了解崩溃原因

### 超时问题

**症状**：`执行超时（超过 X 秒）`
**原因**：代码执行时间过长或无限循环
**解决**：
1. 增加超时时间
2. 检查代码逻辑
3. 添加进度输出

### 安全检查失败

**症状**：`安全检查失败，发现以下危险操作：...`
**原因**：代码包含了被禁止的危险操作
**解决**：
1. 移除危险函数调用
2. 使用安全的替代方案
3. 联系管理员审查代码

### 文件操作失败

**症状**：文件读写失败
**检查点**：
- 当前工作目录：是否在 root_dir 内
- 文件权限：是否有读写权限
- 路径格式：使用相对路径

## 📄 许可证

MIT License - 详见项目根目录 LICENSE 文件

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进沙箱安全性。

## 🔄 版本历史

### v2.0.0（新进程隔离方案）
- ✨ 使用子进程隔离执行环境
- ✨ 移除 monkey patching 机制
- ✨ 使用 os.chdir() 隔离工作目录
- ✨ 简化代码结构
- 🐛 修复多线程安全问题
- 📚 更新文档

### v1.0.0（旧方案）
- 🎉 初始版本
- 使用 threading.local() + monkey patching
- 支持基本的沙箱功能