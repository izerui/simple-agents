"""注册自定义的 langchain model providers。

这个模块用于注册 langchain 官方 init_chat_model 不支持的模型 providers，
例如 langchain-qwq (ChatQwQ, ChatQwen)。

使用方法：
    # 在导入 init_chat_model 之前导入此模块
    from src.utils.register_providers import register_all_providers
    register_all_providers()

    # 然后就可以使用 init_chat_model
    from langchain.chat_models import init_chat_model
    model = init_chat_model('qwq-plus', model_provider='qwq')
    model = init_chat_model('qwen3-max', model_provider='qwen')
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 标记是否已注册
_REGISTERED = False


def _create_qwen_model(cls, model: str, **kwargs):
    """创建 ChatQwen/ChatQwQ 模型实例，正确处理参数映射。

    ChatQwen/ChatQwQ 使用 api_base 和 api_key（不是 openai_api_base/openai_api_key），
    而 init_chat_model 传入的是 base_url 和 api_key。
    """
    # 映射参数名：init_chat_model 的参数 -> langchain_qwq 的参数
    # 注意：ChatQwen 的验证逻辑检查的是 api_base，不是 openai_api_base
    if 'base_url' in kwargs:
        kwargs['api_base'] = kwargs.pop('base_url')
    # api_key 名称相同，不需要映射

    return cls(model=model, **kwargs)


def register_qwq_provider() -> bool:
    """注册 qwq provider（阿里云 QwQ 推理模型）。

    Returns:
        bool: 是否成功注册
    """
    try:
        from langchain.chat_models.base import _BUILTIN_PROVIDERS, _get_chat_model_creator

        if 'qwq' in _BUILTIN_PROVIDERS:
            logger.debug("qwq provider already registered")
            return True

        # 注册 qwq provider
        _BUILTIN_PROVIDERS['qwq'] = (
            'langchain_qwq',
            'ChatQwQ',
            _create_qwen_model
        )

        # 清除缓存以使新 provider 生效
        _get_chat_model_creator.cache_clear()

        logger.info("✅ Registered 'qwq' provider for init_chat_model")
        return True

    except ImportError as e:
        logger.warning(f"⚠️ Failed to register qwq provider: {e}")
        logger.warning("   Make sure langchain-qwq is installed: pip install langchain-qwq")
        return False
    except Exception as e:
        logger.error(f"❌ Error registering qwq provider: {e}")
        return False


def register_qwen_provider() -> bool:
    """注册 qwen provider（阿里云 Qwen 系列模型）。

    Returns:
        bool: 是否成功注册
    """
    try:
        from langchain.chat_models.base import _BUILTIN_PROVIDERS, _get_chat_model_creator

        if 'qwen' in _BUILTIN_PROVIDERS:
            logger.debug("qwen provider already registered")
            return True

        # 注册 qwen provider
        _BUILTIN_PROVIDERS['qwen'] = (
            'langchain_qwq',
            'ChatQwen',
            _create_qwen_model
        )

        # 清除缓存
        _get_chat_model_creator.cache_clear()

        logger.info("✅ Registered 'qwen' provider for init_chat_model")
        return True

    except ImportError as e:
        logger.warning(f"⚠️ Failed to register qwen provider: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error registering qwen provider: {e}")
        return False


def register_all_providers() -> dict[str, bool]:
    """注册所有自定义 providers。

    Returns:
        dict[str, bool]: 每个 provider 的注册结果
    """
    global _REGISTERED

    if _REGISTERED:
        logger.debug("Providers already registered")
        return {}

    results = {
        'qwq': register_qwq_provider(),
        'qwen': register_qwen_provider(),
    }

    _REGISTERED = True
    return results


def is_provider_registered(provider: str) -> bool:
    """检查 provider 是否已注册。

    Args:
        provider: provider 名称

    Returns:
        bool: 是否已注册
    """
    try:
        from langchain.chat_models.base import _BUILTIN_PROVIDERS
        return provider in _BUILTIN_PROVIDERS
    except ImportError:
        return False


def get_available_providers() -> list[str]:
    """获取所有可用的 model providers。

    Returns:
        list[str]: 可用的 provider 列表
    """
    register_all_providers()

    try:
        from langchain.chat_models.base import _BUILTIN_PROVIDERS
        return sorted(_BUILTIN_PROVIDERS.keys())
    except ImportError:
        return []


if __name__ == '__main__':
    # 测试注册
    print("Registering custom providers...")
    results = register_all_providers()

    print("\nRegistration results:")
    for provider, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {provider}")

    print("\nAvailable providers:")
    for provider in get_available_providers():
        print(f"  - {provider}")
