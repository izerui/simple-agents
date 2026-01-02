# 开发部署文档

本文档介绍 Simple Agents 项目的开发和部署流程。

## Docker 部署

### 生成 Dockerfile

使用 LangGraph CLI 生成 Dockerfile：

```simple-agents/DEPLOYMENT.md#L7
langgraph dockerfile -c langgraph.json --base-image langchain/langgraph-api:3.12 ./Dockerfile
```

该命令会根据 `langgraph.json` 配置文件在项目根目录生成 `Dockerfile`。

### 构建和运行 Docker 镜像

```simple-agents/DEPLOYMENT.md#L15-16
docker build -t simple-agents .
docker run -p 8123:8123 simple-agents
```

## GitHub Actions CI/CD

### 工作流配置

项目使用 GitHub Actions 进行自动化的构建、推送和部署。工作流文件位于 `.github/workflows/build-push-deploy.yml`。

### 触发条件

- 推送到 `master` 分支时自动触发
- 可以通过 `workflow_dispatch` 手动触发

### 主要步骤

1. **检出代码**：获取仓库代码和历史记录
2. **设置 Python 环境**：使用 Python 3.12
3. **安装依赖**：使用 uv 包管理器安装项目依赖
4. **生成 Dockerfile**：使用 LangGraph CLI 根据 `langgraph.json` 生成 Dockerfile
5. **提取版本号**：从 `pyproject.toml` 中读取项目版本
6. **构建并推送镜像**：构建 Docker 镜像并推送到 Harbor 仓库
7. **部署到 Kubernetes**：重启指定的 deployment

### 配置的 Secrets

需要在 GitHub 仓库中配置以下 Secrets：

- `HARBOR_USERNAME`：Harbor 仓库用户名
- `HARBOR_PASSWORD`：Harbor 仓库密码
- `KUBE_CONFIG`：Kubernetes 集群配置文件内容

### Docker 镜像标签

构建的镜像会打上两个标签：
- `serv999.com/feike/simple-agents:latest`：最新版本
- `serv999.com/feike/simple-agents:<版本号>`：具体版本号

### 部署目标

部署到 Kubernetes 集群的 `platform-yunji` 命名空间下的 `simple-agents` deployment。

## 注意事项

- 确保 `langgraph.json` 配置文件正确设置
- 生成的 Dockerfile 会包含项目依赖和运行时配置
- 默认端口为 8123，可根据需要修改
- 部署前确保 Kubernetes 集群配置正确
- 修改部署 namespace 或 deployment 名称时需同步更新工作流文件