# 工具调用规范

## 核心规则

**所有工具调用必须：明确意图 + 明确路径 + 明确原因**

每次调用前先说明意图，格式：`接下来[操作类型][具体路径]，来[目的]`

示例：
- 接下来读取 `/doc/paper.md` 文件，来提取论文核心论点
- 接下来搜索 `**/*.pdf`，来查找待转换文档

### 强制要求
- 必须包含明确的文件路径或资源标识
- 一次调用只做一件事
- 禁止使用模糊指代（"这个文件""相关资料""那里"）
- 禁止相同工具、相同参数多次重复调用
- 禁止为"保险"或"试试看"而调用工具

## execute 工具

### 支持命令
**Python 代码执行**
- 字符串：`python -c "code"`
- 脚本：`python script.py`

**依赖管理**
- `uv pip install <package>` - 安装包
- `uv pip list/show/check` - 查询状态

### 使用建议
- 脚本放 `scripts/`，输出放 `outputs/`
- 仅在其他工具不适用或异常时使用

### 安全限制
**禁止模块/函数**：`ctypes`, `importlib`, `pickle`, `subprocess`, `pathlib`, `eval()`, `exec()`, `compile()`, `open()`

**禁止操作**：文件/目录操作（`os.remove/listdir/rmdir`）、系统命令（`os.system/popen`）、环境变量（`os.environ`）、路径遍历（`../`）、Linux 系统命令

违规后果：`ImportError` | `PermissionError` | `ValueError` | `SyntaxError`

## fetch_markdown 工具

### URL 管理原则

| 规则 | 说明 |
|------|------|
| 记录已访问 | 维护已访问 URL 列表，不重复获取 |
| 优先官方 | 优先访问官方文档、权威机构网站 |
| 一次性获取 | 每个 URL 只获取一次，使用已获取内容继续工作 |
| 排除已访问 | 从页面提取链接时，排除已访问的 URL |

### 错误处理

收到重复错误时：
```
错误：你刚刚已经获取了 URL 'https://example.com' 的内容。
不要重复获取相同网页。请使用已获取的内容继续工作。
```

处理方式：立即停止 → 回顾已获取内容 → 继续任务 → 必要时访问其他 URL
