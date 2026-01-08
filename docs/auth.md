# LangSmith Auth 架构详细解释

## 一、核心概念：认证 vs 授权

### 1.1 基本定义

在 LangSmith 的安全架构中，有两个核心但经常被混淆的概念：

**认证（Authentication，简称 AuthN）**
- **问题**：验证"你是谁"
- **作用**：确认用户的身份
- **实现方式**：通过 `@auth.authenticate` 处理器
- **执行时机**：作为中间件在每个请求上运行
- **典型验证手段**：API 密钥、JWT token、OAuth 等

**授权（Authorization，简称 AuthZ）**
- **问题**：确定"你能做什么"
- **作用**：验证用户对特定资源的权限
- **实现方式**：通过 `@auth.on` 处理器系列
- **执行时机**：在认证成功后，针对每个资源操作
- **典型控制手段**：基于角色、权限、资源所有者等

### 1.2 两者的关系

```
请求流程：
客户端请求 → 认证（AuthN）→ 授权（AuthZ）→ 资源访问
              ↓              ↓
         验证身份        验证权限
         你是谁？        你能做什么？
```

**关键点**：
- 认证是授权的前提——必须先知道"你是谁"，才能判断"你能做什么"
- 认证只执行一次（每个请求），授权可能执行多次（针对不同资源）
- 认证失败返回 401（Unauthorized），授权失败返回 403（Forbidden）

---

## 二、系统架构组件

LangSmith 的认证和授权系统由三个主要组件构成：

### 2.1 认证提供者（Authentication Provider / Identity Provider）

**职责**：
- 管理用户身份和凭证
- 处理用户注册、登录、密码重置等
- 在认证成功后颁发令牌（JWT、session token 等）
- 维护用户数据库和身份信息

**常见实现**：
- **第三方服务**：Auth0、Supabase Auth、Okta
- **自建服务**：自己的认证服务器
- **简单实现**：API 密钥存储（适合小型应用）

**不负责**：
- 不直接访问业务资源
- 不执行业务逻辑
- 不存储用户凭证（由认证提供者管理）

### 2.2 Agent 服务器（Agent Server / Resource Server）

**职责**：
- 包含业务逻辑和受保护的资源
- 验证来自认证提供者的令牌
- 基于用户身份和权限执行访问控制
- 处理实际的业务请求

**关键特性**：
- **不存储用户凭证**：只验证令牌，不管理密码
- **执行授权逻辑**：通过 `@auth.on` 处理器实现
- **资源保护**：确保只有授权用户能访问特定资源

**在 LangGraph 中的实现**：
```python
# 你的 LangGraph 应用就是 Agent Server
# 它通过 @auth.authenticate 和 @auth.on 处理器实现安全功能
```

### 2.3 客户端应用（Client Application / Frontend）

**职责**：
- 收集用户凭证（用户名/密码、API 密钥等）
- 将凭证发送到认证提供者
- 接收认证提供者颁发的令牌
- 在请求中包含令牌发送到 Agent 服务器

**典型形式**：
- Web 应用（React、Vue 等）
- 移动应用（iOS、Android）
- API 客户端（CLI 工具、其他服务）

### 2.4 组件交互流程

```
完整认证和授权流程：

1. 用户 → 客户端：输入凭证
2. 客户端 → 认证提供者：发送凭证
3. 认证提供者 → 客户端：返回令牌（JWT/API key）
4. 客户端 → Agent 服务器：发送请求 + 令牌
5. Agent 服务器 → @auth.authenticate：验证令牌
6. @auth.authenticate → Agent 服务器：返回用户信息
7. Agent 服务器 → @auth.on 处理器：检查权限
8. @auth.on 处理器 → Agent 服务器：允许/拒绝访问
9. Agent 服务器 → 客户端：返回结果或错误
```

**LangGraph 的角色**：
- **步骤 5-6**：由 `@auth.authenticate` 处理器实现
- **步骤 7-8**：由 `@auth.on` 处理器系列实现

---

## 三、认证机制详解

### 3.1 认证处理器（@auth.authenticate）

**核心作用**：
- 作为中间件在每个请求上运行
- 验证请求中的凭证
- 返回用户信息或抛出异常

**函数签名**：
```python
@auth.authenticate
async def authenticate(
    headers: dict[bytes, bytes],  # 请求头
    # 可选参数：
    # request: Request,           # ASGI 请求对象
    # path: str,                  # 请求路径
    # method: str,                # HTTP 方法
    # path_params: dict,          # 路径参数
    # query_params: dict,         # 查询参数
    # authorization: str | None   # Authorization 头
) -> Auth.types.MinimalUserDict:
    pass
```

**返回值结构**：
```python
{
    "identity": "user-123",              # 必需：唯一用户标识符
    "is_authenticated": True,            # 可选：默认为 True
    "permissions": ["read", "write"],    # 可选：用于基于权限的授权
    # 可以添加任何自定义字段
    "role": "admin",
    "org_id": "org-456",
    "github_token": "ghp_xxx",           # 用于 agent 认证
    "jira_token": "jira_xxx"
}
```

### 3.2 认证失败处理

**抛出异常**：
```python
# 方式 1：HTTP 异常
raise Auth.exceptions.HTTPException(
    status_code=401,
    detail="Invalid API key"
)

# 方式 2：断言错误
assert is_valid_key(api_key), "Invalid API key"
```

### 3.3 用户信息的可用性

认证成功后，用户信息在两个地方可用：

**1. 在授权处理器中**：
```python
@auth.on.threads.read
async def on_thread_read(
    ctx: Auth.types.AuthContext,  # 包含用户信息
    value: dict
):
    user_identity = ctx.user.identity
    permissions = ctx.user.permissions
```

**2. 在应用代码中**：
```python
def my_node(state, config):
    # 从配置中获取用户信息
    user_info = config["configurable"]["langgraph_auth_user"]
    user_identity = user_info["identity"]
```

---

## 四、授权机制详解

### 4.1 授权处理器的核心功能

授权处理器可以做三件事：

**1. 添加元数据**（在创建/更新时）
```python
metadata = value.setdefault("metadata", {})
metadata["owner"] = ctx.user.identity
```

**2. 过滤资源**（在读取/搜索时）
```python
# 返回过滤字典，限制用户只能访问特定资源
return {"owner": ctx.user.identity}
```

**3. 拒绝访问**
```python
raise Auth.exceptions.HTTPException(
    status_code=403,
    detail="Access denied"
)
```

### 4.2 过滤操作详解

授权处理器可以返回：
- `None` 或 `True`：允许访问所有资源
- `False`：拒绝访问所有资源（返回 403）
- **过滤字典**：限制访问特定资源

**过滤操作符**：

**1. 精确匹配（$eq）**
```python
# 简写形式
{"owner": user_id}

# 完整形式
{"owner": {"$eq": user_id}}
```

**2. 列表成员（$contains）**
```python
# 检查 user_id 是否在 allowed_users 列表中
{"allowed_users": {"$contains": user_id}}

# 检查多个用户是否都在列表中
{"allowed_users": {"$contains": [user_id_1, user_id_2]}}
```

**3. 逻辑 AND**
```python
# 多个条件必须同时满足
{
    "owner": org_id,
    "allowed_users": {"$contains": user_id}
}
# 只匹配 owner 是 org_id 且 allowed_users 包含 user_id 的资源
```

---

## 五、三层授权处理器系统

LangGraph 提供了三层授权处理器，从通用到具体：

### 5.1 全局处理器（@auth.on）

**匹配范围**：所有资源和所有操作

**用途**：
- 实现默认的访问控制策略
- 拒绝未明确允许的请求
- 实现通用的访问模式（如单所有者资源）

**示例**：
```python
@auth.on
async def global_handler(
    ctx: Auth.types.AuthContext,
    value: dict
):
    # 为所有资源添加所有者
    metadata = value.setdefault("metadata", {})
    metadata["owner"] = ctx.user.identity
    return {"owner": ctx.user.identity}
```

### 5.2 资源处理器（@auth.on.threads）

**匹配范围**：特定资源的所有操作

**支持的资源**：
- `@auth.on.threads`：对话线程
- `@auth.on.assistants`：助手
- `@auth.on.crons`：定时任务

**用途**：
- 为特定资源类型实现统一的访问控制
- 覆盖全局处理器的行为

**示例**：
```python
@auth.on.threads
async def on_threads(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.threads.value  # 所有线程操作的联合类型
):
    # 只对线程资源添加所有者
    metadata = value.setdefault("metadata", {})
    metadata["owner"] = ctx.user.identity
    return {"owner": ctx.user.identity}
```

### 5.3 操作处理器（@auth.on.threads.create）

**匹配范围**：特定资源的特定操作

**支持的操作**（以 threads 为例）：
- `@auth.on.threads.create`：创建线程
- `@auth.on.threads.read`：读取线程
- `@auth.on.threads.update`：更新线程
- `@auth.on.threads.delete`：删除线程
- `@auth.on.threads.search`：搜索线程
- `@auth.on.threads.create_run`：创建运行

**用途**：
- 为特定操作实现细粒度的访问控制
- 覆盖全局处理器和资源处理器

**示例**：
```python
@auth.on.threads.create
async def on_thread_create(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.threads.create.value  # 特定于创建的类型
):
    # 检查权限
    if "threads:write" not in ctx.permissions:
        raise Auth.exceptions.HTTPException(
            status_code=403,
            detail="User lacks the required permissions"
        )

    # 添加所有者
    metadata = value.setdefault("metadata", {})
    metadata["owner"] = ctx.user.identity
    return {"owner": ctx.user.identity}
```

### 5.4 处理器优先级

**规则**：最具体的处理器优先

```
优先级顺序（从高到低）：
1. 操作处理器（@auth.on.threads.create）
2. 资源处理器（@auth.on.threads）
3. 全局处理器（@auth.on）
```

**匹配示例**：
```python
# 假设有以下处理器：

@auth.on
async def global_handler(ctx, value):
    print("全局处理器")
    return {"owner": ctx.user.identity}

@auth.on.threads
async def threads_handler(ctx, value):
    print("线程资源处理器")
    return {"owner": ctx.user.identity}

@auth.on.threads.create
async def thread_create_handler(ctx, value):
    print("线程创建处理器")
    return {"owner": ctx.user.identity}

# 请求匹配结果：
# POST /threads          → thread_create_handler（最具体）
# GET  /threads/{id}     → threads_handler
# POST /assistants       → global_handler（没有更具体的处理器）
```

**关键点**：
- 如果注册了更具体的处理器，更通用的处理器不会被调用
- 每个请求只调用一个最匹配的处理器
- 可以混合使用不同层级的处理器

---

## 六、常见访问模式

### 6.1 单所有者资源模式

**场景**：每个资源只属于一个用户，如聊天机器人应用

**实现**：
```python
@auth.on
async def owner_only(
    ctx: Auth.types.AuthContext,
    value: dict
):
    # 在创建时添加所有者
    metadata = value.setdefault("metadata", {})
    metadata["owner"] = ctx.user.identity

    # 在读取时过滤
    return {"owner": ctx.user.identity}
```

**效果**：
- 用户只能看到自己创建的资源
- 用户不能访问其他用户的资源
- 适用于大多数单用户应用场景

### 6.2 基于权限的访问控制

**场景**：不同角色有不同的权限，如管理员、普通用户

**认证阶段**：
```python
@auth.authenticate
async def authenticate(headers: dict):
    # 验证凭证
    api_key = headers.get(b"x-api-key")
    user = get_user_by_api_key(api_key)

    # 返回用户信息和权限
    return {
        "identity": user.id,
        "permissions": user.permissions,  # ["threads:read", "threads:write"]
        "role": user.role
    }
```

**授权阶段**：
```python
@auth.on.threads.create
async def create_thread(
    ctx: Auth.types.AuthContext,
    value: dict
):
    # 检查权限
    if "threads:write" not in ctx.permissions:
        raise Auth.exceptions.HTTPException(
            status_code=403,
            detail="Unauthorized"
        )

    # 添加所有者
    metadata = value.setdefault("metadata", {})
    metadata["owner"] = ctx.user.identity
    return {"owner": ctx.user.identity}

@auth.on.threads.read
async def read_thread(
    ctx: Auth.types.AuthContext,
    value: dict
):
    # 检查权限（读或写都可以）
    if "threads:read" not in ctx.permissions and "threads:write" not in ctx.permissions:
        raise Auth.exceptions.HTTPException(
            status_code=403,
            detail="Unauthorized"
        )

    return {"owner": ctx.user.identity}
```

### 6.3 组织级别访问控制

**场景**：资源属于组织，用户通过组织成员身份访问

**认证阶段**：
```python
@auth.authenticate
async def authenticate(headers: dict):
    user = get_user(headers.get(b"x-api-key"))
    return {
        "identity": user.id,
        "org_id": user.organization_id,  # 组织 ID
        "role": user.role
    }
```

**授权阶段**：
```python
@auth.on
async def org_level_access(
    ctx: Auth.types.AuthContext,
    value: dict
):
    # 使用组织 ID 而不是用户 ID
    metadata = value.setdefault("metadata", {})
    metadata["org_id"] = ctx.user.org_id

    return {"org_id": ctx.user.org_id}
```

**效果**：
- 同一组织的所有用户可以访问相同的资源
- 适用于团队协作场景

### 6.4 混合访问控制

**场景**：结合多种访问模式

```python
@auth.on.assistants.create
async def create_assistant(
    ctx: Auth.types.AuthContext,
    value: dict
):
    # 管理员可以为组织创建助手
    if ctx.user.role == "admin":
        metadata = value.setdefault("metadata", {})
        metadata["org_id"] = ctx.user.org_id
        return {"org_id": ctx.user.org_id}

    # 普通用户只能为自己创建助手
    else:
        metadata = value.setdefault("metadata", {})
        metadata["owner"] = ctx.user.identity
        return {"owner": ctx.user.identity}
```

---

## 七、默认安全模型

### 7.1 LangSmith 托管版本

**默认行为**：
- 使用 LangSmith API 密钥
- 要求在 `x-api-key` 头中提供有效的 API 密钥
- 支持自定义认证处理器

**自定义认证**：
- 所有计划都支持自定义认证
- 可以覆盖默认的 API 密钥认证

### 7.2 自托管版本

**默认行为**：
- 没有默认认证
- 完全灵活，可以实现任何安全模型
- 开发者控制认证和授权的所有方面

**建议**：
- 至少实现基本的认证机制
- 根据应用需求选择合适的访问控制策略

---

## 八、Agent 认证

### 8.1 委托访问概念

**问题**：Agent 需要代表用户访问外部资源（如 GitHub、Jira）

**解决方案**：
- 在认证阶段返回用户的凭证（如 OAuth tokens）
- 这些凭证会被添加到运行上下文中
- Agent 可以从上下文中获取凭证并访问外部资源

### 8.2 实现方式

**认证阶段**：
```python
@auth.authenticate
async def authenticate(headers: dict):
    api_key = headers.get(b"x-api-key")
    user = get_user(api_key)

    # 返回用户的 OAuth tokens
    return {
        "identity": user.id,
        "github_token": user.github_token,  # GitHub OAuth token
        "jira_token": user.jira_token       # Jira API token
    }
```

**Agent 使用**：
```python
def my_node(state, config):
    # 获取用户信息
    user_info = config["configurable"]["langgraph_auth_user"]

    # 使用用户的 GitHub token
    github_token = user_info["github_token"]
    github_client = Github(github_token)

    # 代表用户执行操作
    repo = github_client.get_repo("owner/repo")
    # ...
```

### 8.3 安全注意事项

**最佳实践**：
- 不要在日志中记录敏感凭证
- 使用安全的密钥存储
- 考虑使用临时凭证
- 实现凭证轮换机制

---

## 九、类型安全

LangGraph 为每个处理器提供了类型提示：

```python
# 操作处理器：最具体的类型
@auth.on.threads.create
async def on_thread_create(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.threads.create.value  # ThreadsCreate 类型
):
    pass

# 资源处理器：联合类型
@auth.on.threads
async def on_threads(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.threads.value  # 所有线程操作的联合类型
):
    pass

# 全局处理器：最通用的类型
@auth.on
async def on_all(
    ctx: Auth.types.AuthContext,
    value: dict  # 所有可能操作的联合类型
):
    pass
```

**优势**：
- 更具体的处理器提供更好的类型提示
- IDE 可以提供更准确的自动完成
- 减少运行时类型错误

---

## 十、总结

### 10.1 架构层次

```
LangSmith Auth 架构层次：

1. 概念层
   ├── 认证（AuthN）：验证"你是谁"
   └── 授权（AuthZ）：确定"你能做什么"

2. 组件层
   ├── 认证提供者：管理用户身份
   ├── Agent 服务器：保护资源和执行业务逻辑
   └── 客户端应用：收集凭证和发送请求

3. 实现层
   ├── @auth.authenticate：认证处理器
   └── @auth.on.*：授权处理器系列
       ├── 全局处理器（@auth.on）
       ├── 资源处理器（@auth.on.threads）
       └── 操作处理器（@auth.on.threads.create）

4. 模式层
   ├── 单所有者资源
   ├── 基于权限的访问
   └── 组织级别访问
```

### 10.2 关键要点

1. **认证和授权是分离的**：认证验证身份，授权验证权限
2. **三层处理器系统**：从通用到具体，最具体的优先
3. **灵活的访问控制**：支持多种访问模式
4. **类型安全**：每个处理器都有类型提示
5. **Agent 认证**：支持委托访问，Agent 可以代表用户操作

### 10.3 实施建议

**对于简单应用**：
- 使用单所有者资源模式
- 实现基本的 API 密钥认证
- 使用全局处理器

**对于复杂应用**：
- 实现基于权限的访问控制
- 使用操作处理器实现细粒度控制
- 考虑组织级别的访问控制
- 实现 Agent 认证以支持外部资源访问

**对于企业应用**：
- 集成企业认证提供者（Auth0、Okta）
- 实现完整的 RBAC（基于角色的访问控制）
- 使用多层处理器实现复杂的安全策略
- 实现审计日志和监控

---

### 来源

[1] **Authentication & access control** - LangSmith 文档  
URL: https://docs.langchain.com/langsmith/auth  
内容：LangSmith 认证和授权系统的完整架构说明，包括核心概念、系统架构、认证和授权机制详解