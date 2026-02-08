# chroot 沙箱中使用外部文件

## 问题

在 chroot 模式下，**无法访问 root_dir 外的任何文件**：

```python
# 执行命令
python /skills/find-skills/scripts/install_skill.py

# chroot 后变成
python /path/to/root_dir/skills/find-skills/scripts/install_skill.py
# ❌ 这个文件不存在！
```

---

## 解决方案：使用 `setup_files()` 预复制文件

### 方法 1: 映射单个文件

```python
from src.sandbox.pycode_executor import CodeExecutor

executor = CodeExecutor(root_dir="/tmp/sandbox")

# 将实际文件复制到沙箱的指定位置
executor.setup_files({
    '/skills/script.py': 'src/skills/find-skills/scripts/script.py',
})

# 现在可以执行了
result = executor.execute('python /skills/script.py')
```

### 方法 2: 映射整个目录

```python
executor = CodeExecutor(root_dir="/tmp/sandbox")

# 复制整个目录
executor.setup_files({
    '/skills/': 'src/skills/',
    '/data/': 'data/',
})

# 可以访问目录下的所有文件
result = executor.execute('python /skills/find-skills/scripts/script.py')
```

### 方法 3: 使用绝对路径映射

```python
executor = CodeExecutor(root_dir="/tmp/sandbox")

# 使用绝对路径（需要以 / 开头）
executor.setup_files({
    '/usr/bin/python3': '/usr/bin/python3',
    '/lib/python3.12': '/usr/lib/python3.12',
})
```

---

## 实际示例

### 示例 1: 使用 find-skills

```python
from src.sandbox.pycode_executor import CodeExecutor

executor = CodeExecutor(root_dir="/tmp/sandbox")

# 预复制 find-skills 目录
executor.setup_files({
    '/skills/find-skills/': 'src/skills/find-skills/',
})

# 执行安装脚本
result = executor.execute(
    'python /skills/find-skills/scripts/install_skill.py -s "claude-code-review"'
)

print(result.output)
```

### 示例 2: 在你的代码中集成

```python
class SandboxExecutor:
    def __init__(self, root_dir):
        self.executor = CodeExecutor(root_dir=root_dir)

        # 初始化时复制常用文件
        self.executor.setup_files({
            '/skills/': 'src/skills/',
            '/data/': 'data/',
            '/config/': 'config/',
        })

    def run(self, command):
        """执行命令"""
        return self.executor.execute(command)

# 使用
sandbox = SandboxExecutor("/tmp/sandbox")
result = sandbox.run('python /skills/find-skills/scripts/install_skill.py -s "test"')
```

---

## 工作原理

```
chroot 前:
  /skills/find-skills/  →  src/skills/find-skills/  (实际文件)

chroot 后:
  /skills/find-skills/  →  /tmp/sandbox/skills/find-skills/  (沙箱内文件)
  /etc/passwd          →  /tmp/sandbox/etc/passwd
  /                    →  /tmp/sandbox/
```

---

## 注意事项

### 1. 文件复制是一次性的

```python
# 复制文件
executor.setup_files({'/file.txt': 'data.txt'})

# 修改原始文件
with open('data.txt', 'w') as f:
    f.write('new content')

# 沙箱内仍然是旧内容（需要重新复制）
executor.setup_files({'/file.txt': 'data.txt'})  # 重新复制
```

### 2. 目录复制是递归的

```python
# 会复制整个目录树
executor.setup_files({
    '/skills/': 'src/skills/',  # 复制所有子目录和文件
})
```

### 3. 覆盖行为

```python
# 目标已存在时会被覆盖
executor.setup_files({
    '/file.txt': 'data.txt',  # 每次都会复制
})
```

---

## 高级用法

### 动态文件列表

```python
def setup_sandbox(project_root, sandbox_root):
    """自动设置沙箱环境"""
    executor = CodeExecutor(root_dir=sandbox_root)

    # 自动发现需要复制的目录
    mappings = {}

    # 常用目录
    for dir_name in ['skills', 'data', 'config', 'src']:
        src_path = Path(project_root) / dir_name
        if src_path.exists():
            mappings[f'/{dir_name}/'] = str(src_path)

    # 应用映射
    executor.setup_files(mappings)

    return executor

# 使用
executor = setup_sandbox(
    project_root="/Users/liuyuhua/PycharmProjects/simple-agents",
    sandbox_root="/tmp/sandbox"
)
```

### 按需复制

```python
class LazySandbox:
    def __init__(self, root_dir):
        self.executor = CodeExecutor(root_dir=root_dir)
        self.copied = set()

    def ensure_file(self, sandbox_path, actual_path):
        """按需复制文件"""
        if sandbox_path not in self.copied:
            self.executor.setup_files({sandbox_path: actual_path})
            self.copied.add(sandbox_path)

    def run(self, command):
        """执行命令前确保需要的文件存在"""
        # 解析命令中的文件路径
        if '/skills/' in command:
            self.ensure_file('/skills/', 'src/skills/')

        return self.executor.execute(command)
```

---

## 总结

| 问题 | 解决方案 |
|------|---------|
| 无法访问外部文件 | 使用 `setup_files()` 预复制 |
| 文件更新后不同步 | 重新调用 `setup_files()` |
| 需要复制大量文件 | 使用目录映射 |
| 想要自动化 | 编写包装类 |

**记住**: chroot 是**真正的文件系统隔离**，必须提前规划好需要访问的文件！
