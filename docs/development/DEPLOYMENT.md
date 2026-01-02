# 开发部署文档

本文档介绍 Simple Agents 项目的开发和部署流程。

## 项目配置

### pyproject.toml 配置

项目使用 `pyproject.toml` 作为构建配置文件。由于项目包含多个顶级包（`core` 和 `deepagents`），需要明确配置 setuptools 的包发现规则：

```simple-agents/pyproject.toml#L36-41
[tool.setuptools.packages.find]
where = ["."]
include = ["core*", "deepagents*"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"
```

**注意事项**：
- `include` 字段指定要包含的 Python 包
- `files` 目录包含静态资源文件，不是 Python 包，因此不包含在构建配置中
- 如果添加了新的 Python 包，需要更新 `include` 列表

## Docker 部署

### 生成 Dockerfile

使用 LangGraph CLI 生成 Dockerfile：

```simple-agents/DEPLOYMENT.md#L8
langgraph dockerfile -c langgraph.json --base-image langchain/langgraph-api:3.12 ./Dockerfile
```

该命令会根据 `langgraph.json` 配置文件在项目根目录生成 `Dockerfile`。

### 构建和运行 Docker 镜像

```simple-agents/DEPLOYMENT.md#L15-16
docker build -t simple-agents .
docker run -p 8123:8123 simple-agents
```

### 从 Docker Hub 拉取镜像

如果要从 Docker Hub 拉取并运行已推送的镜像：

```simple-agents/docs/development/DEPLOYMENT.md#L22-24
docker pull izerui/simple-agents:latest
docker run -p 8123:8123 izerui/simple-agents:latest
```

## 注意事项

### 通用注意事项
- 确保 `langgraph.json` 配置文件正确设置，包括 `python_version` 字段
- 生成的 Dockerfile 会包含项目依赖和运行时配置
- 默认端口为 8123，可根据需要修改

### 构建相关
- 项目要求 Python >=3.12，生成 Dockerfile 时必须指定使用 `--base-image langchain/langgraph-api:3.12`
- `pyproject.toml` 中配置了多包结构，添加新包时需更新 `[tool.setuptools.packages.find]` 部分
- `files` 目录包含静态资源，不应包含在 Python 包配置中

### 部署相关
- 部署前确保 Kubernetes 集群配置正确
- 修改部署 namespace 或 deployment 名称时需同步更新工作流文件
- Pull Request 不会触发部署，只会构建和推送镜像到仓库
- deploy job 依赖于 build-and-push job 成功完成后才会执行
- 需要确保 `KUBE_CONFIG` Secret 包含有效的 Kubernetes 集群访问凭证