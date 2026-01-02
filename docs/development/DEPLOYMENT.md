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

## 注意事项

- 确保 `langgraph.json` 配置文件正确设置
- 生成的 Dockerfile 会包含项目依赖和运行时配置
- 默认端口为 8123，可根据需要修改