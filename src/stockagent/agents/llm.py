from __future__ import annotations

from urllib.parse import urlparse

from stockagent.config import DEFAULT_LLM_MODEL, LLMConfig
from stockagent.errors import ConfigurationError


def build_model(llm_config: LLMConfig):
    """Build the configured chat model or reject an unsupported provider prefix."""
    provider, separator, model_name = llm_config.model.partition(":")
    if not separator or not provider.strip() or not model_name.strip():
        raise ConfigurationError(
            f"LLM_MODEL must include a provider prefix, for example: {DEFAULT_LLM_MODEL}"
        )

    builders = {
        "openai": build_openai_model,
    }
    builder = builders.get(provider.lower())
    if builder is None:
        raise ConfigurationError(f"Unsupported LLM provider: {provider}")
    return builder(llm_config, model_name)


def build_openai_model(llm_config: LLMConfig, model_name: str):
    """Build the OpenAI-compatible LangChain model for a parsed model name."""
    from langchain_openai import ChatOpenAI

    llm_kwargs = {
        "model": model_name,
        "api_key": llm_config.api_key,
        "base_url": llm_config.base_url or None,
        "timeout": 180,
    }
    # base_url 为空或主机名为 *.openai.com 时，在 llm_kwargs 中加入 use_responses_api=True
    if _is_native_openai_base_url(llm_config.base_url):
        llm_kwargs["use_responses_api"] = True
    else:
        # Compatible endpoints do not always preserve tool-call indexes across
        # streamed chunks. Fall back to one complete response for tool requests
        # so arguments and call IDs cannot be split into separate calls.
        llm_kwargs["disable_streaming"] = "tool_calling"

    return ChatOpenAI(
        **llm_kwargs,
    )


def _is_native_openai_base_url(base_url: str | None) -> bool:
    """Responses API is only safe on native OpenAI endpoints."""
    if not base_url:
        return True
    normalized_base_url = base_url
    if "://" not in normalized_base_url:
        normalized_base_url = "https://" + normalized_base_url
    host = urlparse(normalized_base_url).hostname or ""
    return host == "api.openai.com" or host.endswith(".openai.com")
