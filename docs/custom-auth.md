# LangSmith Custom Auth 实践指南详细分析

## 一、概述

Custom Auth 文档是一个**实践指南**，专注于如何在 LangSmith 应用中实现自定义认证功能。与 auth 文档的概念性解释不同，本文档提供了具体的实现步骤、代码示例和配置方法 [1]。

**适用范围**：
- ✅ LangSmith 云部署
- ✅ 自托管部署
- ❌ 不适用于在自定义服务器中独立使用 LangGraph 开源库

---

## 二、实现自定义认证的完整流程

### 2.1 为什么需要自定义认证？

**问题**：
- 没有自定义 `@auth.authenticate` 处理器时，LangGraph 只能看到 API 密钥的所有者（通常是开发者）
- 请求不会被限定到单个最终用户
- 无法实现用户级别的访问控制

**解决方案**：
- 实现自定义认证处理器
- 传播自定义令牌和用户信息
- 实现细粒度的用户级别访问控制

### 2.2 实现步骤

#### 步骤 1：创建认证文件（auth.py）

**基本结构**：
```python
from langgraph_sdk import Auth
import requests

auth = Auth()

def is_valid_key(api_key: str) -> bool:
    """验证 API 密钥的有效性"""
    # 实现 API 密钥验证逻辑
    # 可以查询数据库、调用外部 API 等
    is_valid = # your API key validation logic
    return is_valid

@auth.authenticate
async def authenticate(headers: dict) -> Auth.types.MinimalUserDict:
    """认证处理器"""
    # 1. 从请求头中获取凭证
    api_key = headers.get(b"x-api-key")
    
    # 2. 验证凭证
    if not api_key or not is_valid_key(api_key):
        raise Auth.exceptions.HTTPException(
            status_code=401, 
            detail="Invalid API key"
        )
    
    # 3. 从安全密钥存储中获取用户特定的令牌
    user_tokens = await fetch_user_tokens(api_key)
    
    # 4. 返回用户信息
    return {
        "identity": api_key,  # 必需：用户唯一标识符
        "github_token": user_tokens.github_token,  # 可选：自定义字段
        "jira_token": user_tokens.jira_token,      # 可选：自定义字段
        # 可以添加任何自定义字段/秘密
    }
```

**关键点**：

1. **处理器签名**：
   - 使用 `@auth.authenticate` 装饰器
   - 接收 `headers` 参数（类型为 `dict[bytes, bytes]`）
   - 返回 `Auth.types.MinimalUserDict` 类型

2. **凭证验证**：
   - 从 `headers.get(b"x-api-key")` 获取 API 密钥
   - 注意：headers 的键是字节类型（`b"x-api-key"`）
   - 可以实现任何验证逻辑（数据库查询、外部 API 调用等）

3. **用户信息返回**：
   - `identity` 字段是必需的（用户唯一标识符）
   - 可以添加任何自定义字段（OAuth tokens、角色、组织 ID 等）
   - 这些字段将在授权和 agent 中可用

#### 步骤 2：配置 langgraph.json

**配置文件结构**：
```json
{
    "dependencies": ["."],
    "graphs": {
        "agent": "./agent.py:graph"
    },
    "env": ".env",
    "auth": {
        "path": "./auth.py:my_auth"
    }
}
```

**关键配置**：
- `auth.path`：指定认证文件的路径和认证对象
- 格式：`./文件名:变量名`
- 示例：`./auth.py:my_auth` 表示从 `auth.py` 文件中导入 `my_auth` 对象

**完整的 auth.py 示例**：
```python
from langgraph_sdk import Auth

# 创建 Auth 实例
my_auth = Auth()

@my_auth.authenticate
async def authenticate(headers: dict) -> Auth.types.MinimalUserDict:
    # 认证逻辑
    pass
```

#### 步骤 3：客户端集成

一旦服务器设置了认证，客户端必须包含相应的授权信息。

---

## 三、客户端集成详解

### 3.1 Python 客户端（langgraph-sdk）

**基本用法**：
```python
from langgraph_sdk import get_client

# 在实际应用中，你会通过认证提供者生成签名的令牌
my_token = "your-token"

# 创建客户端，包含认证头
client = get_client(
    url="http://localhost:2024",
    headers={"Authorization": f"Bearer {my_token}"}
)

# 使用客户端
threads = await client.threads.search()
```

**关键点**：
- 使用 `get_client()` 创建客户端
- 在 `headers` 参数中传递 `Authorization` 头
- 令牌格式：`Bearer {token}`（标准 OAuth 2.0 格式）

### 3.2 Python RemoteGraph

**基本用法**：
```python
from langgraph.pregel.remote import RemoteGraph

# 在实际应用中，你会通过认证提供者生成签名的令牌
my_token = "your-token"

# 创建 RemoteGraph，包含认证头
remote_graph = RemoteGraph(
    "agent",  # graph ID
    url="http://localhost:2024",
    headers={"Authorization": f"Bearer {my_token}"}
)

# 使用 RemoteGraph
result = await remote_graph.ainvoke(...)
```

**关键点**：
- 使用 `RemoteGraph` 类连接到远程部署的图
- 需要指定 `graph_id`（第一个参数）
- 在 `headers` 参数中传递认证信息

### 3.3 JavaScript 客户端（@langchain/langgraph-sdk）

**基本用法**：
```javascript
import { Client } from "@langchain/langgraph-sdk";

// 在实际应用中，你会通过认证提供者生成签名的令牌
const my_token = "your-token";

// 创建客户端，包含认证头
const client = new Client({
    apiUrl: "http://localhost:2024",
    defaultHeaders: { 
        Authorization: `Bearer ${my_token}` 
    },
});

// 使用客户端
const threads = await client.threads.search();
```

**关键点**：
- 使用 `Client` 类
- 在 `defaultHeaders` 中传递认证信息
- 使用模板字符串（`` `Bearer ${my_token}` ``）

### 3.4 JavaScript RemoteGraph

**基本用法**：
```javascript
import { RemoteGraph } from "@langchain/langgraph/remote";

// 在实际应用中，你会通过认证提供者生成签名的令牌
const my_token = "your-token";

// 创建 RemoteGraph，包含认证头
const remoteGraph = new RemoteGraph({
    graphId: "agent",
    url: "http://localhost:2024",
    headers: { 
        Authorization: `Bearer ${my_token}` 
    },
});

// 使用 RemoteGraph
const result = await remoteGraph.invoke(...);
```

### 3.5 CURL 命令行

**基本用法**：
```bash
curl -H "Authorization: Bearer ${your-token}" http://localhost:2024/threads
```

**关键点**：
- 使用 `-H` 参数添加请求头
- 令牌格式：`Bearer ${token}`
- 可以使用环境变量：`${your-token}`

---

## 四、Agent 认证详解

### 4.1 核心概念

**问题**：Agent 需要代表用户访问外部资源（如 GitHub、Jira、数据库等）

**解决方案**：
1. 在认证阶段返回用户的凭证（OAuth tokens、API keys 等）
2. 这些凭证会被添加到运行上下文中
3. Agent 从上下文中获取凭证并访问外部资源

### 4.2 实现步骤

#### 步骤 1：在认证处理器中返回用户凭证

```python
@auth.authenticate
async def authenticate(headers: dict) -> Auth.types.MinimalUserDict:
    api_key = headers.get(b"x-api-key")
    
    # 验证 API 密钥
    if not api_key or not is_valid_key(api_key):
        raise Auth.exceptions.HTTPException(
            status_code=401, 
            detail="Invalid API key"
        )
    
    # 从安全密钥存储中获取用户特定的令牌
    user_tokens = await fetch_user_tokens(api_key)
    
    # 返回用户信息，包括外部服务的凭证
    return {
        "identity": api_key,
        "github_token": user_tokens.github_token,    # GitHub OAuth token
        "jira_token": user_tokens.jira_token,        # Jira API token
        "slack_token": user_tokens.slack_token,      # Slack bot token
        # 可以添加任何其他凭证
    }
```

**关键点**：
- 从安全的密钥存储中获取用户凭证（不要硬编码）
- 返回的凭证可以是任何类型（OAuth tokens、API keys、密码等）
- 这些凭证将被加密存储在运行上下文中

#### 步骤 2：在 Agent 中使用凭证

```python
def my_node(state, config):
    """Agent 节点函数"""
    
    # 1. 从配置中获取用户信息
    user_config = config["configurable"].get("langgraph_auth_user")
    
    if user_config is None:
        # 处理未认证的情况
        return {"error": "User not authenticated"}
    
    # 2. 获取特定的凭证
    github_token = user_config.get("github_token", "")
    jira_token = user_config.get("jira_token", "")
    
    # 3. 使用凭证访问外部服务
    if github_token:
        # 使用 GitHub token
        from github import Github
        g = Github(github_token)
        repo = g.get_repo("owner/repo")
        # 执行操作...
    
    if jira_token:
        # 使用 Jira token
        from jira import JIRA
        jira = JIRA(token_auth=jira_token)
        # 执行操作...
    
    return {"result": "Success"}
```

**关键点**：
- 用户信息存储在 `config["configurable"]["langgraph_auth_user"]` 中
- 使用 `.get()` 方法安全地获取凭证（避免 KeyError）
- 在使用凭证前检查是否存在
- 不要在日志中记录敏感凭证

### 4.3 安全最佳实践

**⚠️ 重要警告**：
> **不要在图状态中存储秘密！**

**正确做法**：
```python
# ✅ 正确：从配置中获取凭证
def my_node(state, config):
    user_config = config["configurable"].get("langgraph_auth_user")
    token = user_config.get("github_token")
    # 使用 token...
```

**错误做法**：
```python
# ❌ 错误：不要在状态中存储凭证
def my_node(state):
    # 不要这样做！
    state["github_token"] = "secret_token"
    # ...
```

**其他安全建议**：
1. **使用安全的密钥存储**：
   - 使用环境变量
   - 使用密钥管理服务（AWS Secrets Manager、Azure Key Vault 等）
   - 不要在代码中硬编码凭证

2. **凭证轮换**：
   - 定期轮换 OAuth tokens
   - 实现凭证过期机制
   - 提供凭证刷新接口

3. **最小权限原则**：
   - 只请求必要的权限
   - 使用有限制的 tokens
   - 为不同用户分配不同的权限级别

4. **日志安全**：
   - 不要在日志中记录敏感信息
   - 使用日志过滤机制
   - 审计日志应记录谁访问了什么，但不记录凭证

---

## 五、Studio 用户授权

### 5.1 问题背景

**默认行为**：
- 如果添加了自定义授权，它也会应用于从 Studio 发起的交互
- 这意味着开发者可能无法访问自己部署的图

**解决方案**：
- 检测 Studio 用户
- 为 Studio 用户提供不同的访问权限
- 允许开发者访问托管在 LangSmith SaaS 上的图

### 5.2 实现方法

#### 方法 1：使用 is_studio_user() 函数（推荐）

**版本要求**：langgraph-sdk >= 0.1.73

```python
from langgraph_sdk.auth import is_studio_user, Auth

auth = Auth()

# ... 设置认证处理器等

@auth.on
async def add_owner(
    ctx: Auth.types.AuthContext,
    value: dict
) -> dict:
    """为所有资源添加所有者"""
    
    # 检查是否是 Studio 用户
    if is_studio_user(ctx.user):
        # Studio 用户：返回空过滤器（允许访问所有资源）
        return {}
    
    # 普通用户：应用访问限制
    filters = {"owner": ctx.user.identity}
    metadata = value.setdefault("metadata", {})
    metadata.update(filters)
    return filters
```

**关键点**：
- `is_studio_user(ctx.user)` 返回布尔值
- Studio 用户返回 `True`，普通用户返回 `False`
- 为 Studio 用户返回空过滤器 `{}`（允许访问所有资源）

#### 方法 2：使用 isinstance() 检查（旧版本兼容）

**适用版本**：langgraph-sdk < 0.1.73

```python
from langgraph_sdk.auth import Auth
from langgraph_sdk.auth.types import StudioUser

auth = Auth()

@auth.on
async def add_owner(
    ctx: Auth.types.AuthContext,
    value: dict
) -> dict:
    """为所有资源添加所有者"""
    
    # 检查是否是 Studio 用户
    if isinstance(ctx.user, StudioUser):
        # Studio 用户：返回空过滤器
        return {}
    
    # 普通用户：应用访问限制
    filters = {"owner": ctx.user.identity}
    metadata = value.setdefault("metadata", {})
    metadata.update(filters)
    return filters
```

### 5.3 使用场景

**适用场景**：
- ✅ 允许开发者访问托管在 LangSmith SaaS 上的图
- ✅ 在开发/调试期间绕过访问限制
- ✅ 为管理员提供特殊权限

**不适用场景**：
- ❌ 生产环境中的普通用户
- ❌ 需要严格访问控制的环境

**安全考虑**：
- 只在必要时使用
- 确保只有可信的开发者能访问 Studio
- 考虑为 Studio 用户添加审计日志

---

## 六、完整的实践示例

### 6.1 简单的 API 密钥认证

**auth.py**：
```python
from langgraph_sdk import Auth

auth = Auth()

# 简单的 API 密钥验证
VALID_API_KEYS = {
    "key_user1": "user1",
    "key_user2": "user2",
}

def is_valid_key(api_key: str) -> bool:
    return api_key in VALID_API_KEYS

@auth.authenticate
async def authenticate(headers: dict) -> Auth.types.MinimalUserDict:
    api_key = headers.get(b"x-api-key")
    
    if not api_key or not is_valid_key(api_key):
        raise Auth.exceptions.HTTPException(
            status_code=401, 
            detail="Invalid API key"
        )
    
    # 将字节转换为字符串
    api_key_str = api_key.decode("utf-8")
    
    return {
        "identity": VALID_API_KEYS[api_key_str],
        "is_authenticated": True
    }
```

### 6.2 JWT 令牌认证

**auth.py**：
```python
from langgraph_sdk import Auth
import jwt
import os

auth = Auth()

JWT_SECRET = os.getenv("JWT_SECRET")

@auth.authenticate
async def authenticate(headers: dict) -> Auth.types.MinimalUserDict:
    # 获取 Authorization 头
    auth_header = headers.get(b"authorization")
    
    if not auth_header:
        raise Auth.exceptions.HTTPException(
            status_code=401, 
            detail="Missing authorization header"
        )
    
    # 解析 Bearer token
    try:
        scheme, token = auth_header.decode("utf-8").split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid scheme")
    except ValueError:
        raise Auth.exceptions.HTTPException(
            status_code=401, 
            detail="Invalid authorization header format"
        )
    
    # 验证 JWT
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise Auth.exceptions.HTTPException(
            status_code=401, 
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise Auth.exceptions.HTTPException(
            status_code=401, 
            detail="Invalid token"
        )
    
    return {
        "identity": payload["user_id"],
        "email": payload.get("email"),
        "role": payload.get("role", "user"),
        "permissions": payload.get("permissions", [])
    }
```

### 6.3 OAuth 2.0 集成

**auth.py**：
```python
from langgraph_sdk import Auth
import httpx
import os

auth = Auth()

OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
OAUTH_INTROSPECT_URL = os.getenv("OAUTH_INTROSPECT_URL")

async def validate_oauth_token(token: str) -> dict:
    """通过 OAuth 2.0 introspection 端点验证令牌"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            OAUTH_INTROSPECT_URL,
            data={"token": token},
            auth=(OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET)
        )
        response.raise_for_status()
        return response.json()

@auth.authenticate
async def authenticate(headers: dict) -> Auth.types.MinimalUserDict:
    # 获取 Authorization 头
    auth_header = headers.get(b"authorization")
    
    if not auth_header:
        raise Auth.exceptions.HTTPException(
            status_code=401, 
            detail="Missing authorization header"
        )
    
    # 解析 Bearer token
    try:
        scheme, token = auth_header.decode("utf-8").split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid scheme")
    except ValueError:
        raise Auth.exceptions.HTTPException(
            status_code=401, 
            detail="Invalid authorization header format"
        )
    
    # 验证 OAuth token
    token_info = await validate_oauth_token(token)
    
    if not token_info.get("active"):
        raise Auth.exceptions.HTTPException(
            status_code=401, 
            detail="Token is inactive or expired"
        )
    
    return {
        "identity": token_info["sub"],
        "email": token_info.get("email"),
        "scope": token_info.get("scope", "").split(),
        "client_id": token_info.get("client_id")
    }
```

### 6.4 带有 Agent 认证的完整示例

**auth.py**：
```python
from langgraph_sdk import Auth
import asyncpg
import os

auth = Auth()

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db_connection():
    """获取数据库连接"""
    return await asyncpg.connect(DATABASE_URL)

async def fetch_user_tokens(api_key: str) -> dict:
    """从数据库获取用户的令牌"""
    conn = await get_db_connection()
    try:
        # 查询用户信息和令牌
        row = await conn.fetchrow(
            """
            SELECT u.id, u.email, 
                   github.github_token,
                   jira.jira_token
            FROM users u
            LEFT JOIN user_github_tokens github ON u.id = github.user_id
            LEFT JOIN user_jira_tokens jira ON u.id = jira.user_id
            WHERE u.api_key = $1
            """,
            api_key
        )
        
        if not row:
            return None
        
        return {
            "user_id": row["id"],
            "email": row["email"],
            "github_token": row["github_token"],
            "jira_token": row["jira_token"]
        }
    finally:
        await conn.close()

def is_valid_key(api_key: str) -> bool:
    """验证 API 密钥格式"""
    # 基本格式验证
    if not api_key or len(api_key) < 32:
        return False
    return True

@auth.authenticate
async def authenticate(headers: dict) -> Auth.types.MinimalUserDict:
    api_key = headers.get(b"x-api-key")
    
    if not api_key or not is_valid_key(api_key.decode("utf-8")):
        raise Auth.exceptions.HTTPException(
            status_code=401, 
            detail="Invalid API key"
        )
    
    # 从数据库获取用户令牌
    user_tokens = await fetch_user_tokens(api_key.decode("utf-8"))
    
    if not user_tokens:
        raise Auth.exceptions.HTTPException(
            status_code=401, 
            detail="Invalid API key"
        )
    
    return {
        "identity": user_tokens["user_id"],
        "email": user_tokens["email"],
        "github_token": user_tokens["github_token"],
        "jira_token": user_tokens["jira_token"]
    }
```

**agent.py**：
```python
from github import Github
from jira import JIRA

def github_node(state, config):
    """使用 GitHub 的节点"""
    user_config = config["configurable"].get("langgraph_auth_user")
    
    if not user_config:
        return {"error": "Not authenticated"}
    
    github_token = user_config.get("github_token")
    
    if not github_token:
        return {"error": "GitHub token not found"}
    
    try:
        # 使用用户的 GitHub token
        g = Github(github_token)
        repo = g.get_repo("owner/repo")
        issues = repo.get_issues(state="open")
        
        return {
            "github_issues": [
                {"title": issue.title, "number": issue.number}
                for issue in list(issues)[:5]
            ]
        }
    except Exception as e:
        return {"error": f"GitHub API error: {str(e)}"}

def jira_node(state, config):
    """使用 Jira 的节点"""
    user_config = config["configurable"].get("langgraph_auth_user")
    
    if not user_config:
        return {"error": "Not authenticated"}
    
    jira_token = user_config.get("jira_token")
    
    if not jira_token:
        return {"error": "Jira token not found"}
    
    try:
        # 使用用户的 Jira token
        jira = JIRA(token_auth=jira_token)
        issues = jira.search_issues("assignee = currentUser()", maxResults=5)
        
        return {
            "jira_issues": [
                {"key": issue.key, "summary": issue.fields.summary}
                for issue in issues
            ]
        }
    except Exception as e:
        return {"error": f"Jira API error: {str(e)}"}
```

---

## 七、常见问题和解决方案

### 7.1 认证失败

**问题**：所有请求都返回 401 Unauthorized

**可能原因**：
1. API 密钥格式错误
2. headers 键类型错误（使用了字符串而不是字节）
3. 认证处理器未正确配置

**解决方案**：
```python
# ❌ 错误：使用字符串
api_key = headers.get("x-api-key")  # 返回 None

# ✅ 正确：使用字节
api_key = headers.get(b"x-api-key")  # 返回值
```

### 7.2 Agent 无法访问用户信息

**问题**：`config["configurable"].get("langgraph_auth_user")` 返回 `None`

**可能原因**：
1. 认证处理器未正确配置
2. langgraph.json 中的路径错误
3. 认证处理器抛出异常

**解决方案**：
```python
# 检查配置
# langgraph.json
{
    "auth": {
        "path": "./auth.py:my_auth"  # 确保路径正确
    }
}

# 在认证处理器中添加日志
@auth.authenticate
async def authenticate(headers: dict):
    print(f"Headers: {headers}")  # 调试信息
    # ...
```

### 7.3 Studio 用户无法访问

**问题**：开发者无法在 Studio 中访问自己部署的图

**解决方案**：
```python
from langgraph_sdk.auth import is_studio_user

@auth.on
async def add_owner(ctx, value):
    if is_studio_user(ctx.user):
        return {}  # 允许 Studio 用户访问所有资源
    
    # 普通用户的访问控制
    filters = {"owner": ctx.user.identity}
    metadata = value.setdefault("metadata", {})
    metadata.update(filters)
    return filters
```

### 7.4 凭证安全问题

**问题**：担心凭证泄露

**最佳实践**：
1. 使用环境变量存储敏感信息
2. 使用密钥管理服务
3. 不要在日志中记录凭证
4. 定期轮换凭证
5. 使用最小权限原则

---

## 八、总结

### 8.1 核心要点

1. **自定义认证的必要性**：
   - 实现用户级别的访问控制
   - 支持 agent 代表用户访问外部资源
   - 集成企业认证系统

2. **实现步骤**：
   - 创建认证文件（auth.py）
   - 实现 `@auth.authenticate` 处理器
   - 配置 langgraph.json
   - 集成客户端

3. **Agent 认证**：
   - 在认证时返回用户凭证
   - 在 agent 中从配置获取凭证
   - 不要在状态中存储凭证

4. **Studio 用户处理**：
   - 使用 `is_studio_user()` 检测
   - 为 Studio 用户提供特殊权限
   - 仅用于开发/调试场景

### 8.2 与 auth 文档的关系

```
auth 文档（概念层）
    ↓
    ├── 解释认证和授权的概念
    ├── 描述系统架构
    └── 提供完整的 API 参考
         ↓
         ↓ 引导至
         ↓
custom-auth 文档（实践层）
    ↓
    ├── 提供具体实现步骤
    ├── 展示代码示例
    └── 解决常见集成问题
```

### 8.3 使用建议

**学习路径**：
1. 先阅读 auth 文档，理解概念和架构
2. 再阅读 custom-auth 文档，学习实现方法
3. 参考完整示例，实现自己的认证系统

**实施建议**：
- 从简单的 API 密钥认证开始
- 逐步添加更复杂的功能（OAuth、Agent 认证等）
- 始终考虑安全性和性能
- 进行充分的测试

---

### 来源

[1] **Add custom authentication** - LangSmith 文档  
URL: https://docs.langchain.com/langsmith/custom-auth  
内容：如何在 LangSmith 部署中添加自定义认证的实践指南，包括认证处理器实现、Agent 认证和 Studio 用户授权