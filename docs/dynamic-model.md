# LangChain 动态模型配置设计

本文档介绍如何使用 LangChain 的 `init_chat_model` 实现运行时动态切换模型。

## 1. 核心机制

LangChain 的 `init_chat_model` 支持 `configurable_fields` 参数，创建一个 `_ConfigurableModel` 实例，该实例可以在运行时通过 `config` 参数动态覆盖模型配置。

### 服务端配置 (graph.py)

```python
from langchain.chat_models import init_chat_model

# 使用环境变量作为默认值
chat_model = init_chat_model(
    model=os.getenv('MODEL_MODEL_ID'),
    model_provider=os.getenv('MODEL_PROVIDER'),
    base_url=os.getenv('MODEL_BASE_URL'),
    api_key=os.getenv('MODEL_API_KEY'),
    temperature=0.0,
    streaming=True,
    configurable_fields=("model", "model_provider", "base_url", "api_key"),
)
```

### 客户端调用

```python
from langgraph_sdk.schema import Config

config = Config(
    configurable={
        "model_provider": "openai",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-your-api-key",
        "model": "deepseek-v3.2",
    }
)

# 传递 config 到 stream 方法
async for chunk in client.chat_stream(message="你好", config=config):
    await handler.receive_chunk(chunk)
```

## 2. 配置优先级

运行时配置的优先级规则：

1. **客户端传递的 config**（最高优先级）
2. **服务端初始化时的默认值**（来自环境变量或代码）
3. **LangChain 各 provider 的默认环境变量**（最低优先级）

```python
# 实际合并逻辑 (_ConfigurableModel._model 方法)
params = {**self._default_config, **self._model_params(config)}
```

- 如果客户端传递了某个参数 → 使用客户端的值
- 如果客户端没有传递 → 使用服务端的默认值

## 3. 环境变量说明

### 服务端环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| MODEL_PROVIDER | 模型 provider | `openai`, `anthropic`, `deepseek` |
| MODEL_BASE_URL | API 基础地址 | `https://api.openai.com/v1` |
| MODEL_API_KEY | API 密钥 | `sk-xxx` |
| MODEL_MODEL_ID | 模型名称 | `gpt-4o`, `claude-sonnet-4-5` |

### LangChain 各 Provider 的默认环境变量

LangChain 不会根据 `model_provider` 自动推断读取 `{model_provider}_api_key`。每个 provider 有固定的环境变量名：

| Provider | API Key 环境变量 |
|----------|------------------|
| openai | `OPENAI_API_KEY` |
| anthropic | `ANTHROPIC_API_KEY` |
| deepseek | `DEEPSEEK_API_KEY` |
| google_vertexai | `GOOGLE_API_KEY` |
| azure_openai | `AZURE_OPENAI_API_KEY` |
| ... | ... |

**注意**: 当在服务端使用 `init_chat_model` 初始化模型时，如果传入了 `api_key` 参数，则不会读取 LangChain 的默认环境变量。

## 4. 动态切换示例

### 切换不同的模型

```python
# 使用 OpenAI (DashScope 兼容)
config1 = Config(
    configurable={
        "model_provider": "openai",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-xxx",
        "model": "qwen-plus",
    }
)

# 使用 Anthropic (智谱 AI 兼容)
config2 = Config(
    configurable={
        "model_provider": "anthropic",
        "base_url": "https://open.bigmodel.cn/api/anthropic",
        "api_key": "your-anthropic-key",
        "model": "claude-sonnet-4-5",
    }
)
```

### 运行时获取模型信息

服务端返回的 metadata 中包含实际使用的模型信息：

```python
async for chunk in client.chat_stream(message="你好", config=config):
    # chunk.data[1] 包含 metadata
    metadata = chunk.data[1]
    print(f"模型: {metadata.get('ls_model_name')}")
    print(f"Provider: {metadata.get('ls_provider')}")
```

返回的 metadata 字段：
- `ls_model_name`: 实际使用的模型名称
- `ls_provider`: LangChain 推断的 provider
- `model_provider`: 配置的 provider
- `base_url`: 配置的 API 地址
- `model`: 配置的模型名称

## 5. 注意事项

1. **configurable_fields 必须设置**: 只有在 `init_chat_model` 中设置了 `configurable_fields` 参数，这些字段才支持运行时覆盖。

2. **服务端模型必须支持流式**: 设置 `streaming=True`，否则无法使用流式输出。

3. **API Key 安全**: 客户端传递的 API Key 会覆盖服务端默认值，确保传输过程安全（建议使用 HTTPS）。

4. **provider 推断**: LangChain 会根据模型名称前缀自动推断 provider（如 `gpt-` -> `openai`，`claude-` -> `anthropic`）。

## 6. 动态压缩阈值

当运行时动态切换模型时，SummarizationMiddleware 会根据模型名称自动调整压缩阈值。

### 压缩阈值映射表

| 模型 | 最大输入 tokens | 压缩触发阈值 (85%) |
|------|---------------|-------------------|
| deepseek-v3 | 131072 | 111411 |
| deepseek-v3.2 | 98304 | 83558 |
| deepseek-v3.1 | 98304 | 83558 |
| deepseek-r1 | 98304 | 83558 |
| qwen3-max | 258048 | 219340 |
| qwen3.5-plus | 983616 | 836073 |
| kimi-k2.5 | 262144 | 222822 |
| glm-5 | 202752 | 172339 |
| glm-4.7 | 169984 | 144486 |
| MiniMax-M2.5 | 196608 | 167116 |

### 实现原理

在 `deepagents/middleware/_summarization_helper.py` 中，`DeepAgentsLCSummarizationMiddleware._get_profile_limits` 方法支持动态获取 max_input_tokens，优先级为：

1. **客户端传递** - 从 `runtime.context.max_input_tokens` 获取（最高优先级）
2. **映射表** - 根据运行时模型名称查询映射表
3. **model.profile** - 从模型配置中获取默认值

```python
def _get_profile_limits(self) -> int | None:
    """Retrieve max input token limit with dynamic support."""
    # 1. 优先从 contextvar 获取动态 max_input_tokens
    max_input_tokens = _current_max_input_tokens.get()
    if max_input_tokens is not None:
        return max_input_tokens

    # 2. 从 model.profile 获取默认值
    return super()._get_profile_limits()
```

通过 contextvar 机制，在 `wrap_model_call` 和 `awrap_model_call` 方法开头从 `runtime.context` 提取 `max_input_tokens` 并设置，供后续所有调用点使用。

### 使用方式

运行时切换模型时，压缩阈值会自动调整：

```python
# 使用默认模型（压缩阈值较低，如 qwen3-max 为 219340 tokens）
config1 = Config(configurable={"thread_id": "xxx"})

# 运行时切换到其他模型（压缩阈值自动调整，如 qwen3.5-plus 为 836073 tokens）
config2 = Config(configurable={
    "thread_id": "xxx",
    "model": "qwen3.5-plus"
})
```

#### 客户端自定义 max_input_tokens

客户端可以通过 `runtime.context` 传递自定义的 `max_input_tokens`，优先级最高：

```python
# 客户端传递自定义压缩阈值
config = Config(configurable={
    "thread_id": "xxx",
    "max_input_tokens": 1000  # 强制使用 1000 tokens 作为压缩阈值
})
```

### 并发安全

压缩阈值是在 `_get_profile_limits` 调用时动态计算的，不会在运行时修改 model 对象，因此支持并发调用不同模型。
