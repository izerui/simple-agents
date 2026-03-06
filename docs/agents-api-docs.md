# Webapp Agents API 文档

> 版本: 0.1.0 | OpenAPI: 3.1.0

## 目录

- [概述](#概述)
- [认证](#认证)
- [API 端点](#api-端点)
  - [Assistants (助手)](#assistants-助手)
  - [Threads (线程)](#threads-线程)
  - [Thread Runs (线程运行)](#thread-runs-线程运行)
  - [Stateless Runs (无状态运行)](#stateless-runs-无状态运行)
  - [Crons (定时任务)](#crons-定时任务)
  - [Store (存储)](#store-存储)
  - [A2A (Agent-to-Agent 协议)](#a2a-agent-to-agent-协议)
  - [MCP (Model Context Protocol)](#mcp-model-context-protocol)
  - [System (系统)](#system-系统)
  - [Webapp (Web 应用)](#webapp-web-应用)
  - [Models (模型)](#models-模型)
- [数据模型](#数据模型)
- [错误处理](#错误处理)

---

## 概述

Webapp Agents API 是一个基于 LangGraph 的智能代理服务 API，提供以下核心功能：

- **Assistants**: 配置化的图实例，代表一个 AI 助手
- **Threads**: 包含一组运行累积输出的线程
- **Runs**: 在线程上调用图/助手的执行过程
- **Crons**: 按计划周期性运行的定时任务
- **Store**: 跨线程的持久化键值存储（长期记忆）
- **A2A**: Agent-to-Agent 协议端点
- **MCP**: Model Context Protocol 端点

---

## 认证

本 API 当前无认证要求（securitySchemes 为空）。

---

## API 端点

### Assistants (助手)

助手是一个配置化的图实例。

#### 创建助手

```http
POST /assistants
```

**请求体**: `AssistantCreate`

```json
{
  "graph_id": "research",           // 必需，图的 ID
  "assistant_id": "uuid",           // 可选，不提供则自动生成
  "name": "助手名称",                // 可选，默认 "Untitled"
  "description": "助手描述",         // 可选
  "config": {},                     // 可选，图配置
  "context": {},                    // 可选，静态上下文
  "metadata": {},                   // 可选，元数据
  "if_exists": "raise"              // 可选，"raise" 或 "do_nothing"
}
```

**响应**: `Assistant` 对象

---

#### 搜索助手

```http
POST /assistants/search
```

**请求体**: `AssistantSearchRequest`

```json
{
  "graph_id": "research",           // 可选，按图 ID 过滤
  "name": "名称子串",               // 可选，模糊匹配
  "metadata": {},                   // 可选，元数据精确匹配
  "limit": 10,                      // 可选，默认 10，最大 1000
  "offset": 0,                      // 可选，默认 0
  "sort_by": "created_at",          // 可选，排序字段
  "sort_order": "desc",             // 可选，"asc" 或 "desc"
  "select": ["assistant_id", "name"] // 可选，指定返回字段
}
```

**响应**: `Assistant[]` 数组

---

#### 统计助手数量

```http
POST /assistants/count
```

**请求体**: `AssistantCountRequest`

```json
{
  "graph_id": "research",
  "name": "名称",
  "metadata": {}
}
```

**响应**: `integer` (数量)

---

#### 获取助手

```http
GET /assistants/{assistant_id}
```

**路径参数**:
- `assistant_id` (UUID, 必需): 助手 ID

**响应**: `Assistant` 对象

---

#### 更新助手

```http
PATCH /assistants/{assistant_id}
```

**路径参数**:
- `assistant_id` (UUID, 必需): 助手 ID

**请求体**: `AssistantPatch`

```json
{
  "graph_id": "research",
  "config": {},
  "context": {},
  "metadata": {},
  "name": "新名称",
  "description": "新描述"
}
```

**响应**: `Assistant` 对象

---

#### 删除助手

```http
DELETE /assistants/{assistant_id}
```

**路径参数**:
- `assistant_id` (UUID, 必需): 助手 ID

**查询参数**:
- `delete_threads` (boolean, 可选): 是否同时删除关联线程，默认 `false`

**响应**: 200 成功

---

#### 获取助手图

```http
GET /assistants/{assistant_id}/graph
```

**查询参数**:
- `xray` (boolean|integer, 可选): 是否包含子图，可指定深度

**响应**: 图结构对象

---

#### 获取助手子图

```http
GET /assistants/{assistant_id}/subgraphs
```

**查询参数**:
- `recurse` (boolean, 可选): 是否递归获取，默认 `false`

**响应**: `Subgraphs` 对象

---

#### 按命名空间获取子图

```http
GET /assistants/{assistant_id}/subgraphs/{namespace}
```

---

#### 获取助手 Schema

```http
GET /assistants/{assistant_id}/schemas
```

**响应**: `GraphSchema` 对象

---

#### 获取助手版本列表

```http
POST /assistants/{assistant_id}/versions
```

**响应**: `Assistant[]` (版本列表)

---

#### 设置最新版本

```http
POST /assistants/{assistant_id}/latest?version={version}
```

**查询参数**:
- `version` (integer, 必需): 目标版本号

**响应**: `Assistant` 对象

---

### Threads (线程)

线程包含一组运行的累积输出。

#### 创建线程

```http
POST /threads
```

**请求体**: `ThreadCreate`

```json
{
  "thread_id": "uuid",              // 可选，不提供则自动生成
  "metadata": {},                   // 可选，元数据
  "if_exists": "raise",             // 可选，"raise" 或 "do_nothing"
  "ttl": {                          // 可选，TTL 配置
    "strategy": "delete",           // "delete" 或 "keep_latest"
    "ttl": 60                       // 分钟数
  },
  "supersteps": []                  // 可选，初始状态更新
}
```

**响应**: `Thread` 对象

---

#### 搜索线程

```http
POST /threads/search
```

**请求体**: `ThreadSearchRequest`

```json
{
  "ids": ["uuid1", "uuid2"],        // 可选，线程 ID 列表
  "metadata": {},                   // 可选，元数据过滤
  "values": {},                     // 可选，状态值过滤
  "status": "idle",                 // 可选，"idle"|"busy"|"interrupted"|"error"
  "limit": 10,
  "offset": 0,
  "sort_by": "created_at",
  "sort_order": "desc",
  "select": ["thread_id", "status"],
  "extract": {                      // 可选，提取特定值
    "last_msg": "values.messages[-1]"
  }
}
```

**响应**: `Thread[]` 数组

---

#### 统计线程数量

```http
POST /threads/count
```

---

#### 清理线程

```http
POST /threads/prune
```

**请求体**: `ThreadPruneRequest`

```json
{
  "thread_ids": ["uuid1", "uuid2"],
  "strategy": "delete"              // "delete" 或 "keep_latest"
}
```

**响应**: `ThreadPruneResponse`

```json
{
  "pruned_count": 2
}
```

---

#### 获取线程

```http
GET /threads/{thread_id}
```

**查询参数**:
- `include` (string, 可选): 逗号分隔的额外字段，如 `ttl`

**响应**: `Thread` 对象

---

#### 更新线程

```http
PATCH /threads/{thread_id}
```

**请求体**: `ThreadPatch`

---

#### 删除线程

```http
DELETE /threads/{thread_id}
```

---

#### 获取线程状态

```http
GET /threads/{thread_id}/state
```

**查询参数**:
- `subgraphs` (boolean, 可选): 是否包含子图状态

**响应**: `ThreadState` 对象

---

#### 更新线程状态

```http
POST /threads/{thread_id}/state
```

**请求体**: `ThreadStateUpdate`

```json
{
  "values": {},                     // 要更新的值
  "checkpoint": {},                 // 可选，检查点配置
  "as_node": "node_name"            // 可选，模拟节点执行
}
```

---

#### 获取指定检查点状态

```http
GET /threads/{thread_id}/state/{checkpoint_id}
```

```http
POST /threads/{thread_id}/state/checkpoint
```

---

#### 获取线程历史

```http
GET /threads/{thread_id}/history
```

**查询参数**:
- `limit` (integer, 可选): 默认 10
- `before` (string, 可选): 分页游标

**响应**: `ThreadState[]` 数组

---

```http
POST /threads/{thread_id}/history
```

**请求体**: `ThreadStateSearch`

---

#### 复制线程

```http
POST /threads/{thread_id}/copy
```

**响应**: 新的 `Thread` 对象

---

#### 加入线程流

```http
GET /threads/{thread_id}/stream
```

**Headers**:
- `Last-Event-ID` (string, 可选): 最后接收到的事件 ID

**查询参数**:
- `stream_modes` (string|array, 可选): `"lifecycle"`|`"run_modes"`|`"state_update"`

**响应**: `text/event-stream` (SSE 流)

---

### Thread Runs (线程运行)

运行是在线程上调用图/助手的过程，会更新线程状态。

#### 列出运行

```http
GET /threads/{thread_id}/runs
```

**查询参数**:
- `limit` (integer, 可选): 默认 10
- `offset` (integer, 可选): 默认 0
- `status` (string, 可选): `"pending"`|`"error"`|`"success"`|`"timeout"`|`"interrupted"`
- `select` (array, 可选): 指定返回字段

**响应**: `Run[]` 数组

---

#### 创建后台运行

```http
POST /threads/{thread_id}/runs
```

**请求体**: `RunCreateStateful`

```json
{
  "assistant_id": "uuid",           // 必需，助手 ID 或图名
  "input": {},                      // 可选，输入数据
  "command": {},                    // 可选，Command 对象
  "config": {},                     // 可选，配置
  "context": {},                    // 可选，上下文
  "metadata": {},                   // 可选，元数据
  "interrupt_before": [],           // 可选，执行前中断的节点
  "interrupt_after": [],            // 可选，执行后中断的节点
  "stream_mode": ["values"],        // 可选，流模式
  "stream_subgraphs": false,        // 可选，是否流式子图
  "stream_resumable": false,        // 可选，是否可恢复流
  "multitask_strategy": "enqueue",  // 可选，并发策略
  "if_not_exists": "reject",        // 可选，线程不存在时处理
  "durability": "async"             // 可选，持久化级别
}
```

**响应**: `Run` 对象

**Headers**:
- `Content-Location`: 运行 URL

---

#### 创建运行并流式输出

```http
POST /threads/{thread_id}/runs/stream
```

**请求体**: `RunCreateStateful`

**响应**: `text/event-stream` (SSE 流)

---

#### 创建运行并等待输出

```http
POST /threads/{thread_id}/runs/wait
```

**请求体**: `RunCreateStateful`

**响应**: 最终输出 JSON

---

#### 获取运行

```http
GET /threads/{thread_id}/runs/{run_id}
```

**响应**: `Run` 对象

---

#### 删除运行

```http
DELETE /threads/{thread_id}/runs/{run_id}
```

---

#### 加入运行

```http
GET /threads/{thread_id}/runs/{run_id}/join
```

**查询参数**:
- `cancel_on_disconnect` (boolean, 可选): 断开时取消运行，默认 `false`

**响应**: 运行结果 JSON

---

#### 加入运行流

```http
GET /threads/{thread_id}/runs/{run_id}/stream
```

**Headers**:
- `Last-Event-ID` (string, 可选): 恢复流的事件 ID

**查询参数**:
- `stream_mode` (string, 可选): 流模式
- `cancel_on_disconnect` (boolean, 可选): 默认 `false`

**响应**: `text/event-stream` (SSE 流)

---

#### 取消运行

```http
POST /threads/{thread_id}/runs/{run_id}/cancel
```

**查询参数**:
- `wait` (boolean, 可选): 是否等待取消完成，默认 `false`
- `action` (string, 可选): `"interrupt"` 或 `"rollback"`，默认 `"interrupt"`

---

### Stateless Runs (无状态运行)

无状态运行不持久化状态或记忆。

#### 创建无状态运行并流式输出

```http
POST /runs/stream
```

**请求体**: `RunCreateStateless`

```json
{
  "assistant_id": "uuid",           // 必需
  "input": {},
  "command": {},
  "config": {},
  "on_completion": "delete",        // "delete" 或 "keep"
  "durability": "async"
}
```

**响应**: `text/event-stream` (SSE 流)

---

#### 创建无状态运行并等待输出

```http
POST /runs/wait
```

**请求体**: `RunCreateStateless`

**响应**: 最终输出 JSON

---

#### 创建后台无状态运行

```http
POST /runs
```

**请求体**: `RunCreateStateless`

**响应**: 运行信息

---

#### 批量创建运行

```http
POST /runs/batch
```

**请求体**: `RunBatchCreate` (RunCreateStateless 数组)

---

#### 批量取消运行

```http
POST /runs/cancel
```

**查询参数**:
- `action` (string, 可选): `"interrupt"` 或 `"rollback"`

**请求体**: `RunsCancel`

```json
{
  // 方式一：按状态过滤
  "status": "pending",              // "pending"|"running"|"all"
  
  // 方式二：指定运行
  "thread_id": "uuid",
  "run_ids": ["uuid1", "uuid2"]
}
```

---

### Crons (定时任务)

定时任务是按给定计划周期性运行的任务。

#### 创建线程定时任务

```http
POST /threads/{thread_id}/runs/crons
```

**请求体**: `ThreadCronCreate`

---

#### 创建无状态定时任务

```http
POST /runs/crons
```

**请求体**: `CronCreate`

```json
{
  "assistant_id": "uuid",           // 必需
  "schedule": "0 9 * * *",          // 必需，cron 格式
  "end_time": "2025-12-31T23:59:59Z", // 可选，结束时间
  "input": {},
  "config": {},
  "enabled": true,
  "on_run_completed": "delete"      // "delete" 或 "keep"
}
```

**响应**: `Cron` 对象

---

#### 搜索定时任务

```http
POST /runs/crons/search
```

**请求体**: `CronSearch`

---

#### 统计定时任务数量

```http
POST /runs/crons/count
```

---

#### 更新定时任务

```http
PATCH /runs/crons/{cron_id}
```

**请求体**: `CronPatch`

---

#### 删除定时任务

```http
DELETE /runs/crons/{cron_id}
```

---

### Store (存储)

Store 是跨线程的持久化键值存储（长期记忆）。

#### 存储或更新项目

```http
PUT /store/items
```

**请求体**: `StorePutRequest`

```json
{
  "namespace": ["users", "user123"], // 必需，命名空间路径
  "key": "preferences",              // 必需，键
  "value": {                         // 必需，值
    "theme": "dark",
    "language": "zh-CN"
  },
  "index": ["theme", "language"],    // 可选，索引字段，false 禁用
  "ttl": 43200                       // 可选，TTL（分钟）
}
```

**响应**: 204 成功

---

#### 获取项目

```http
GET /store/items?key={key}&namespace[]={ns1}&namespace[]={ns2}
```

**查询参数**:
- `key` (string, 必需): 项目键
- `namespace` (array, 可选): 命名空间
- `refresh_ttl` (boolean, 可选): 是否刷新 TTL

**响应**: `Item` 对象

---

#### 删除项目

```http
DELETE /store/items
```

**请求体**: `StoreDeleteRequest`

```json
{
  "namespace": ["users", "user123"],
  "key": "preferences"
}
```

---

#### 搜索项目

```http
POST /store/items/search
```

**请求体**: `StoreSearchRequest`

```json
{
  "namespace_prefix": ["users"],    // 可选，命名空间前缀
  "filter": {},                     // 可选，键值过滤
  "query": "主题设置",               // 可选，自然语言搜索
  "limit": 10,
  "offset": 0,
  "refresh_ttl": true               // 可选，是否刷新 TTL
}
```

**响应**: `SearchItemsResponse`

```json
{
  "items": [
    {
      "namespace": ["users", "user123"],
      "key": "preferences",
      "value": { "theme": "dark" },
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-15T12:00:00Z"
    }
  ]
}
```

---

#### 列出命名空间

```http
POST /store/namespaces
```

**请求体**: `StoreListNamespacesRequest`

```json
{
  "prefix": ["users"],              // 可选，前缀过滤
  "suffix": [],                     // 可选，后缀过滤
  "max_depth": 3,                   // 可选，最大深度
  "limit": 100,
  "offset": 0
}
```

**响应**: `ListNamespaceResponse` (二维字符串数组)

---

### A2A (Agent-to-Agent 协议)

A2A 协议端点，用于将助手暴露为 A2A 兼容的代理。

#### A2A JSON-RPC

```http
POST /a2a/{assistant_id}
```

**路径参数**:
- `assistant_id` (UUID, 必需): 助手 ID

**Headers**:
- `Accept` (必需): 
  - 流式模式: `text/event-stream`
  - 其他模式: `application/json`

**请求体**: JSON-RPC 2.0 请求

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "message/send",         // 或 "message/stream"|"tasks/get"|"tasks/cancel"
  "params": {
    "message": {
      "role": "user",
      "parts": [
        { "kind": "text", "text": "你好" },
        { "kind": "data", "data": { "locale": "zh-CN" } }
      ],
      "messageId": "msg-1",
      "contextId": "thread-uuid"    // 可选，对应 LangGraph thread_id
    }
  }
}
```

**支持的方法**:

| 方法 | 说明 |
|------|------|
| `message/send` | 发送消息并等待最终任务结果 |
| `message/stream` | 发送消息并接收 SSE 流式响应 |
| `tasks/get` | 按ID获取任务状态 |
| `tasks/cancel` | 请求取消任务（当前不支持） |

**响应示例**:

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "kind": "task",
    "id": "run-uuid",
    "contextId": "thread-uuid",
    "status": { "state": "completed" },
    "artifacts": [
      {
        "artifactId": "artifact-uuid",
        "name": "Assistant Response",
        "parts": [{ "kind": "text", "text": "你好！有什么可以帮助你的？" }]
      }
    ]
  }
}
```

---

### MCP (Model Context Protocol)

MCP 端点，用于将代理暴露为 MCP 服务器。

#### MCP POST

```http
POST /mcp/
```

**Headers**:
- `Accept` (必需): `application/json, text/event-stream`

**请求体**: JSON-RPC 2.0 消息

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "initialize",
  "params": {
    "clientInfo": { "name": "test_client", "version": "1.0.0" },
    "protocolVersion": "2024-11-05",
    "capabilities": {}
  }
}
```

**响应**: JSON-RPC 响应或 202 (通知)

---

#### MCP GET

```http
GET /mcp/
```

**响应**: 405 (不支持流式)

---

#### 终止 MCP 会话

```http
DELETE /mcp/
```

**响应**: 404 (无状态实现)

---

### System (系统)

系统端点用于健康检查、指标和服务器信息。

#### 服务器信息

```http
GET /info
```

**响应**:

```json
{
  "version": "0.1.0",
  "langgraph_py_version": "0.x.x",
  "flags": {},
  "metadata": {}
}
```

---

#### 系统指标

```http
GET /metrics?format={format}
```

**查询参数**:
- `format` (string, 可选): `"prometheus"` (默认) 或 `"json"`

**响应**: Prometheus 格式或 JSON 格式的指标

---

#### API 文档

```http
GET /docs
```

**响应**: HTML 格式的本地 API 文档

---

#### 健康检查

```http
GET /ok?check_db={0|1}
```

**查询参数**:
- `check_db` (integer, 可选): 是否检查数据库连接，0=否，1=是

**响应**:

```json
{
  "ok": true
}
```

---

### Webapp (Web 应用)

#### 下载文件

```http
GET /webapp/download/{thread_id}?path={path}
```

**路径参数**:
- `thread_id` (string, 必需): 对话线程 ID

**查询参数**:
- `path` (string, 必需): 文件路径（相对于 thread_dir）

**响应**: 文件内容流式响应

---

#### 提取文件路径

```http
POST /webapp/extract-file-paths
```

**请求体**: `ExtractFilePathsRequest`

```json
{
  "content": "AI 回复内容..."
}
```

**响应**: `ApiResponse`

```json
{
  "success": true,
  "err_message": null,
  "data": ["/path/to/file1", "/path/to/file2"]
}
```

---

### Models (模型)

#### 获取可用模型列表

```http
GET /webapp/models
```

**响应**: `ModelListResponse`

```json
{
  "success": true,
  "err_message": null,
  "data": [
    {
      "name": "gpt-4",
      "provider": "openai",
      "base_url": "https://api.openai.com/v1",
      "is_default": true
    },
    {
      "name": "claude-3-opus",
      "provider": "anthropic",
      "base_url": null,
      "is_default": false
    }
  ]
}
```

---

## 数据模型

### Assistant

```typescript
interface Assistant {
  assistant_id: string;          // UUID
  graph_id: "research";          // 图 ID
  config: Config;                // 配置
  context: object;               // 静态上下文
  created_at: string;            // ISO 8601 日期时间
  updated_at: string;
  metadata: object;
  version: number;               // 版本号
  name: string;                  // 助手名称
  description: string | null;    // 描述
}
```

### Thread

```typescript
interface Thread {
  thread_id: string;             // UUID
  created_at: string;
  updated_at: string;
  state_updated_at: string;
  metadata: object;
  config: object;
  status: "idle" | "busy" | "interrupted" | "error";
  values: object;                // 当前状态值
  interrupts: object;            // 当前中断
  ttl?: {                        // TTL 信息（可选）
    strategy: "delete" | "keep_latest";
    ttl_minutes: number;
    expires_at: string;
  };
}
```

### Run

```typescript
interface Run {
  run_id: string;                // UUID
  thread_id: string;
  assistant_id: string;
  created_at: string;
  updated_at: string;
  status: "pending" | "running" | "error" | "success" | "timeout" | "interrupted";
  metadata: object;
  kwargs: object;
  multitask_strategy: "reject" | "rollback" | "interrupt" | "enqueue";
}
```

### ThreadState

```typescript
interface ThreadState {
  values: object | object[];
  next: string[];                // 下一步要执行的节点
  tasks: Task[];
  checkpoint: CheckpointConfig;
  metadata: object;
  created_at: string;
  parent_checkpoint: object;
  interrupts: Interrupt[];
}
```

### Cron

```typescript
interface Cron {
  cron_id: string;
  assistant_id: string | null;
  thread_id: string;
  end_time: string;
  schedule: string;              // cron 格式
  created_at: string;
  updated_at: string;
  user_id: string | null;
  payload: object;
  next_run_date: string | null;
  metadata: object;
  enabled: boolean;
}
```

### Item (Store)

```typescript
interface Item {
  namespace: string[];
  key: string;
  value: object;
  created_at: string;
  updated_at: string;
}
```

### GraphSchema

```typescript
interface GraphSchema {
  graph_id: "research";
  input_schema: object;          // 输入 JSON Schema
  output_schema: object;         // 输出 JSON Schema
  state_schema: object;          // 状态 JSON Schema
  config_schema: object;         // 配置 JSON Schema
  context_schema: object;        // 上下文 JSON Schema
}
```

### CheckpointConfig

```typescript
interface CheckpointConfig {
  thread_id: string;
  checkpoint_ns: string;
  checkpoint_id: string;
  checkpoint_map: object;
}
```

### Command

```typescript
interface Command {
  update: object | array | null;   // 状态更新
  resume: any;                     // 恢复中断的值
  goto: Send | Send[] | string | string[] | null; // 导航目标
}
```

### Interrupt

```typescript
interface Interrupt {
  id: string | null;
  value: object;
}
```

---

## 错误处理

### 错误响应格式

```json
{
  "detail": "Human-readable error message"
}
```

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 204 | 成功（无内容） |
| 400 | 请求格式错误 |
| 404 | 资源未找到 |
| 405 | 方法不允许 |
| 409 | 冲突（如重复创建） |
| 422 | 验证错误 |
| 500 | 服务器内部错误 |

### 验证错误详情

```json
{
  "detail": [
    {
      "loc": ["body", "assistant_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## 流式响应 (SSE)

所有流式端点返回 Server-Sent Events (SSE) 格式：

```
id: 1
event: message
data: {"type": "values", "values": {...}}

id: 2
event: message
data: {"type": "values", "values": {...}}

```

### Stream Modes

| 模式 | 说明 |
|------|------|
| `values` | 状态值更新 |
| `messages` | 消息更新 |
| `messages-tuple` | 消息元组 |
| `tasks` | 任务状态 |
| `checkpoints` | 检查点 |
| `updates` | 增量更新 |
| `events` | 事件 |
| `debug` | 调试信息 |
| `custom` | 自定义模式 |

---

## 附录

### Cron 表达式格式

```
┌───────────── 分钟 (0 - 59)
│ ┌───────────── 小时 (0 - 23)
│ │ ┌───────────── 日 (1 - 31)
│ │ │ ┌───────────── 月 (1 - 12)
│ │ │ │ ┌───────────── 星期几 (0 - 6) (星期日 = 0)
│ │ │ │ │
* * * * *
```

**示例**:
- `0 9 * * *` - 每天上午 9:00
- `*/30 * * * *` - 每 30 分钟
- `0 0 * * 0` - 每周日午夜

### Multitask Strategy

| 策略 | 说明 |
|------|------|
| `reject` | 拒绝新运行 |
| `rollback` | 回滚当前运行 |
| `interrupt` | 中断当前运行 |
| `enqueue` | 排队等待（默认） |

### Durability Modes

| 模式 | 说明 |
|------|------|
| `sync` | 同步检查点 |
| `async` | 异步检查点（默认） |
| `exit` | 退出时检查点 |

---

*文档生成时间: 2026-03-05*