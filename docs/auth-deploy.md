# Agent 服务开启鉴权 —— 运维操作步骤

`<KEY>` 由负责人单独提供，下面所有出现 `<KEY>` 的地方都填这同一个值。

请按顺序执行。

## 第 1 步：两台 agents-api 服务器更新镜像

```bash
docker compose pull agents-api
docker compose up -d agents-api
```

## 第 2 步：paper-rag

1. 线上 `.env` 中新增一行：

   ```
   LANGGRAPH_API_KEY=<KEY>
   ```

2. 发布最新代码，然后重启服务。

## 第 3 步：mcd_admin_web

1. `.env.production` 末尾新增一行：

   ```
   VITE_LANGGRAPH_API_KEY=<KEY>
   ```

2. 重新打包，然后发布 `dist`：

   ```bash
   npm run build
   ```

   必须重新打包才能生效，只改服务器上的环境变量没用。

## 第 4 步：两台 agents-api 服务器开启鉴权

1. `.env` 中新增一行：

   ```
   LANGGRAPH_API_KEY=<KEY>
   ```

2. `docker-compose.yml` 中，在 `agents-api` 的 `environment` 下新增一行（与其他变量对齐，单引号和里面的内容原样照抄）：

   ```yaml
               LANGGRAPH_AUTH: '{"path": "/deps/simple-agents/src/graph.py:auth"}'
   ```

3. 重启：

   ```bash
   docker compose up -d agents-api
   ```

## 第 5 步：验证（两台服务器都要做）

```bash
# 应输出包含 "Using auth of type=custom"
docker compose logs agents-api | grep "auth of type"

# 应输出 401 或 403（不同版本返回码不同，都表示被拒绝）
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8123/assistants/search -H 'content-type: application/json' -d '{}'

# 应输出 200
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8123/assistants/search -H 'content-type: application/json' -H "x-api-key: <KEY>" -d '{}'
```

然后检查业务：
- paper-rag：论文评价能正常返回。
- mcd_admin_web：AI 助手能正常对话。

## 附：关闭 browser-service 和 postgres 的对外端口（两台服务器都要做）

可以和上面的步骤分开，单独执行。

1. `docker-compose.yml` 中，把 `browser-service` 和 `postgres` 下的 `ports` 整段注释掉：

   ```yaml
       postgres:
           # ports:
           #     - "5433:5432"

       browser-service:
           # ports:
           #     - "2025:2025"
   ```

2. 重启：

   ```bash
   docker compose up -d postgres browser-service
   ```

3. 从**外网**验证，两条命令都应连接失败：

   ```bash
   nc -zv -w 5 <服务器公网IP> 2025
   nc -zv -w 5 <服务器公网IP> 5433
   ```

4. 确认 agents-api 的抓取网页和对话功能都正常。

## 回滚

删掉 `docker-compose.yml` 中的 `LANGGRAPH_AUTH` 一行，然后执行：

```bash
docker compose up -d agents-api
```
