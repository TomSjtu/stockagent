from __future__ import annotations

from urllib.parse import urlparse

from stockagent.config import DEFAULT_LLM_MODEL, LLMConfig
from stockagent.errors import ConfigurationError


def build_model(llm_config: LLMConfig):
    provider, separator, model_name = llm_config.model.partition(":")
    if not separator or not provider.strip() or not model_name.strip():
        raise ConfigurationError(
            f"LLM_MODEL must include a provider prefix, for example: {DEFAULT_LLM_MODEL}"
        )

    builders = {
        "openai": build_openai_model,
        "anthropic": build_anthropic_model,
    }
    builder = builders.get(provider.lower())
    if builder is None:
        raise ConfigurationError(f"Unsupported LLM provider: {provider}")
    return builder(llm_config, model_name)


def build_openai_model(llm_config: LLMConfig, model_name: str):
    from langchain_openai import ChatOpenAI

    llm_kwargs = {
        "model": model_name,
        "api_key": llm_config.api_key,
        "base_url": llm_config.base_url or None,
        "timeout": 180,
    }
    if _is_native_openai_base_url(llm_config.base_url):
        llm_kwargs["use_responses_api"] = True

    return ChatOpenAI(
        **llm_kwargs,
    )


def build_anthropic_model(llm_config: LLMConfig, model_name: str):
    pass


def _is_native_openai_base_url(base_url: str | None) -> bool:
    """Responses API is only safe on native OpenAI endpoints."""
    if not base_url:
        return True
    normalized_base_url = base_url
    if "://" not in normalized_base_url:
        normalized_base_url = "https://" + normalized_base_url
    host = urlparse(normalized_base_url).hostname or ""
    return host == "api.openai.com" or host.endswith(".openai.com")
