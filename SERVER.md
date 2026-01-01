# LangGraph 服务器管理

## 🚀 快速开始

### 启动服务器

```bash
./start_server.sh
```

### 停止服务器

```bash
./stop_server.sh
```

### 访问服务器

启动成功后，访问：
- **本地**: http://localhost:2024
- **Studio**: https://studio.langchain.com

---

## 📋 服务器脚本

### start_server.sh

启动 LangGraph 开发服务器

**功能：**
- 检查 `.env` 和 `langgraph.json` 文件
- 自动激活虚拟环境
- 验证 `langgraph` CLI 安装
- 启动开发服务器

**使用：**
```bash
./start_server.sh
```

### stop_server.sh

停止运行中的 LangGraph 服务器

**功能：**
- 查找所有 LangGraph 进程
- 优雅关闭（SIGTERM）
- 强制关闭（必要时 SIGKILL）

**使用：**
```bash
./stop_server.sh
```

---

## 🔧 常用命令

| 操作 | 命令 |
|------|------|
| 启动服务器 | `./start_server.sh` |
| 停止服务器 | `./stop_server.sh` |
| 查看进程 | `ps aux \| grep langgraph` |
| 查看端口 | `lsof -i :2024` |

---

## ⚠️ 常见问题

### 权限被拒绝

```bash
bash: ./start_server.sh: Permission denied
```

**解决：**
```bash
chmod +x *.sh
```

### 端口已被占用

```bash
OSError: [Errno 48] Address already in use
```

**解决：**
```bash
lsof -i :2024
kill <PID>
```

### `.env` 文件未找到

```bash
Error: .env file not found!
```

**解决：**
```bash
touch .env
# 添加必要的环境变量
```

### `langgraph` 命令未找到

```bash
Error: langgraph CLI not found!
```

**解决：**
```bash
source .venv/bin/activate
pip install langgraph-cli
```

---

## 💡 最佳实践

### 开发流程

```bash
# 启动服务器
./start_server.sh

# 修改代码（自动重载）

# 完成后停止
./stop_server.sh
```

### 后台运行

```bash
# 后台运行
nohup ./start_server.sh > server.log 2>&1 &

# 查看日志
tail -f server.log

# 停止服务器
./stop_server.sh
```

---

## 📚 更多文档

- 项目 README: [README.md](README.md)
- 测试指南: [tests/agents/QUICKSTART.md](tests/agents/QUICKSTART.md)

---

**现在启动服务器吧！**

```bash
./start_server.sh
```
