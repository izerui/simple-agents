"""模型配置文件补丁，用于动态压缩阈值。

该模块通过修补 LangChain 的 _ConfigurableModel 来支持基于运行时配置中模型名称的动态
max_input_tokens。

用法:
    在 graph.py 中导入此模块即可启用基于模型的动态压缩阈值。
"""
import os
from contextvars import ContextVar

from langchain.chat_models.base import _ConfigurableModel
from langchain_core.runnables import RunnableConfig

# 用于存储运行时配置以供 profile 访问的上下文变量
_current_config: ContextVar[dict | None] = ContextVar("current_config", default=None)

# 模型上下文窗口配置（单位：tokens）
# 可根据实际模型能力调整
MODEL_MAX_TOKENS = {
    # DeepSeek 系列
    "deepseek-v3": 131072 * 0.7,
    "deepseek-v3.2": 98304 * 0.7,
    "deepseek-v3.1": 98304 * 0.7,
    "deepseek-r1": 98304 * 0.7,
    # Qwen 系列
    "qwen3-max": 1000 * 0.7,
    "qwen3.5-plus": 983616 * 0.7,
    # Kimi 系列
    "kimi-k2.5": 262144 * 0.7,
    # GLM 系列
    "glm-5": 202752 * 0.7,
    "glm-4.7": 169984 * 0.7,
    # MiniMax 系列
    "MiniMax-M2.5": 196608 * 0.7,
    "MiniMax/MiniMax-M2.5": 204800 * 0.7,
}


def apply_patches():
    """应用所有必要的补丁以启用基于模型的动态压缩阈值。

    Patch 1: _ConfigurableModel._model
        - 在创建底层模型时，将 runtime config 存入 contextvar
        - 这样后续可以在同一请求中访问 config

    Patch 2: _DeepAgentsSummarizationMiddleware._get_profile_limits
        - 从 contextvar 获取运行时 config 中的 model 名称
        - 根据 model 名称自动返回对应的 max_input_tokens
        - 如果未传递 model，则使用环境变量 MODEL_MODEL_ID
        - 如果都没有，则使用环境变量 MODEL_MAX_INPUT_TOKENS
    """
    # ========== Patch 1: _ConfigurableModel._model ==========
    # 目的：将客户端传递的 runtime config 存入 contextvar，供后续读取
    _original_model_method = _ConfigurableModel._model

    def _patched_model_method(self, config: RunnableConfig | None = None):
        # 将 config 存入 contextvar，设置 token 用于后续清理
        token = _current_config.set(config)
        try:
            # 调用原始方法创建底层模型
            model = _original_model_method(self, config)
        finally:
            # 请求结束后清理 contextvar
            _current_config.reset(token)
        return model

    _ConfigurableModel._model = _patched_model_method  # type: ignore[assignment]

    # ========== Patch 2: _DeepAgentsSummarizationMiddleware._get_profile_limits ==========
    # 目的：根据运行时使用的模型自动判断 max_input_tokens，实现动态压缩阈值
    try:
        from deepagents.middleware.summarization import _DeepAgentsSummarizationMiddleware

        _original_get_profile_limits = _DeepAgentsSummarizationMiddleware._get_profile_limits

        def _patched_get_profile_limits(self):
            """根据模型名称返回对应的 max_input_tokens。

            优先级:
            1. 从 runtime config 获取 model 名称
            2. 使用环境变量 MODEL_MODEL_ID
            3. 使用环境变量 MODEL_MAX_INPUT_TOKENS
            """
            model_name = None

            # 1. 尝试从 runtime config 获取 model
            runtime_config = _current_config.get()
            if runtime_config is not None:
                configurable = runtime_config.get("configurable", {})
                model_name = configurable.get("model")

            # 2. 如果没有传递 model，使用环境变量中的默认模型
            if not model_name:
                model_name = os.getenv('MODEL_MODEL_ID', '')

            # 3. 根据 model 名称前缀匹配返回对应的 max_tokens
            if model_name:
                model_lower = model_name.lower()
                sorted_keys = sorted(MODEL_MAX_TOKENS.keys(), key=len, reverse=True)
                for key in sorted_keys:
                    if model_lower.startswith(key):
                        return MODEL_MAX_TOKENS[key]

            # 4. 如果都没有（model 未匹配或没有 model 名称），使用环境变量中的 max_input_tokens
            max_input_tokens_default = int(os.getenv('MODEL_MAX_INPUT_TOKENS', '80000'))
            return max_input_tokens_default

        _DeepAgentsSummarizationMiddleware._get_profile_limits = _patched_get_profile_limits
    except ImportError:
        # deepagents 在某些上下文中可能不可用
        pass


# 模块导入时自动应用补丁
apply_patches()
