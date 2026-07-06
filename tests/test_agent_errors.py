from __future__ import annotations

import unittest
from unittest.mock import patch

from stockagent.agents.errors import LLMResponseError, LLMTimeoutError
from stockagent.agents.orchestrator import (
    _build_model,
    _is_native_openai_base_url,
    build_openai_model,
    run_stock_analysis_agent,
)
from stockagent.config import DEFAULT_LLM_MODEL, LLMConfig
from stockagent.errors import ConfigurationError


class FakeAgent:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def invoke(self, _payload: dict) -> dict:
        raise self.exc


class AgentErrorsTest(unittest.TestCase):
    def test_native_openai_base_url_detection(self) -> None:
        self.assertTrue(_is_native_openai_base_url(None))
        self.assertTrue(_is_native_openai_base_url(""))
        self.assertTrue(_is_native_openai_base_url("https://api.openai.com/v1"))
        self.assertTrue(_is_native_openai_base_url("api.openai.com/v1"))
        self.assertFalse(_is_native_openai_base_url("https://relay.example.com/v1"))
        self.assertFalse(_is_native_openai_base_url("http://localhost:1234/v1"))

    def test_build_model_routes_openai_provider_to_openai_builder(self) -> None:
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://example.test/v1",
            model=DEFAULT_LLM_MODEL,
        )

        with patch(
            "stockagent.agents.orchestrator.build_openai_model",
            return_value="openai-model",
        ) as build_openai_model:
            model = _build_model(llm_config)

        build_openai_model.assert_called_once_with(llm_config, "gpt-5.5")
        self.assertEqual(model, "openai-model")

    def test_build_model_keeps_anthropic_provider_interface(self) -> None:
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="",
            model="anthropic:claude-sonnet-4-6",
        )

        with patch(
            "stockagent.agents.orchestrator.build_anthropic_model",
            return_value="anthropic-model",
        ) as build_anthropic_model:
            model = _build_model(llm_config)

        build_anthropic_model.assert_called_once_with(llm_config, "claude-sonnet-4-6")
        self.assertEqual(model, "anthropic-model")

    def test_build_model_requires_provider_prefix(self) -> None:
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="",
            model="custom-model",
        )

        with self.assertRaises(ConfigurationError):
            _build_model(llm_config)

    def test_build_model_rejects_unknown_provider(self) -> None:
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="",
            model="custom:model",
        )

        with self.assertRaises(ConfigurationError):
            _build_model(llm_config)

    def test_run_stock_analysis_agent_wraps_timeout_errors(self) -> None:
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://example.test/v1",
            model=DEFAULT_LLM_MODEL,
        )

        with patch(
            "stockagent.agents.orchestrator.create_stock_analysis_agent",
            return_value=FakeAgent(TimeoutError("request timed out")),
        ):
            with self.assertRaises(LLMTimeoutError) as context:
                run_stock_analysis_agent("NVDA", 3, llm_config)

        self.assertEqual(context.exception.model, DEFAULT_LLM_MODEL)

    def test_run_stock_analysis_agent_wraps_non_timeout_errors(self) -> None:
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://example.test/v1",
            model=DEFAULT_LLM_MODEL,
        )

        with patch(
            "stockagent.agents.orchestrator.create_stock_analysis_agent",
            return_value=FakeAgent(RuntimeError("bad response")),
        ):
            with self.assertRaises(LLMResponseError):
                run_stock_analysis_agent("NVDA", 3, llm_config)

    def test_build_openai_model_enables_responses_api_for_native_openai(self) -> None:
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model=DEFAULT_LLM_MODEL,
        )

        with patch("langchain_openai.ChatOpenAI", return_value="chat-openai") as chat_openai:
            model = build_openai_model(llm_config, "gpt-5.5")

        chat_openai.assert_called_once_with(
            model="gpt-5.5",
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            timeout=60,
            use_responses_api=True,
        )
        self.assertEqual(model, "chat-openai")

    def test_build_openai_model_disables_responses_api_for_custom_base_url(self) -> None:
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://relay.example.com/v1",
            model=DEFAULT_LLM_MODEL,
        )

        with patch("langchain_openai.ChatOpenAI", return_value="chat-openai") as chat_openai:
            model = build_openai_model(llm_config, "gpt-5.5")

        chat_openai.assert_called_once_with(
            model="gpt-5.5",
            api_key="test-key",
            base_url="https://relay.example.com/v1",
            timeout=60,
        )
        self.assertEqual(model, "chat-openai")


if __name__ == "__main__":
    unittest.main()
