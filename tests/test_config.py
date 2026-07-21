from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from stockagent.config import (
    DEFAULT_EDGAR_IDENTITY,
    DEFAULT_LLM_MODEL,
    AppConfig,
    LLMConfig,
    load_app_config,
    load_llm_config,
)
from stockagent.errors import ConfigurationError


class LLMConfigTest(unittest.TestCase):
    def test_load_app_config_composes_all_service_settings(self) -> None:
        environment_names = (
            "LLM_API_KEY",
            "LLM_BASE_URL",
            "LLM_MODEL",
            "TAVILY_API_KEY",
            "EDGAR_IDENTITY",
        )
        old_values = {name: os.environ.get(name) for name in environment_names}
        try:
            os.environ.update(
                {
                    "LLM_API_KEY": "llm-key",
                    "LLM_BASE_URL": "https://llm.example.test/v1",
                    "LLM_MODEL": "openai:test-model",
                    "TAVILY_API_KEY": "tavily-key",
                    "EDGAR_IDENTITY": "Stock Agent contact@example.test",
                }
            )

            with patch("stockagent.config.load_dotenv", return_value=None):
                config = load_app_config()

            self.assertEqual(
                config,
                AppConfig(
                    llm=LLMConfig(
                        api_key="llm-key",
                        base_url="https://llm.example.test/v1",
                        model="openai:test-model",
                    ),
                    edgar_identity="Stock Agent contact@example.test",
                    tavily_api_key="tavily-key",
                ),
            )
        finally:
            for name, old_value in old_values.items():
                if old_value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = old_value

    def test_load_app_config_requires_tavily_api_key(self) -> None:
        old_api_key = os.environ.get("LLM_API_KEY")
        old_tavily_api_key = os.environ.pop("TAVILY_API_KEY", None)
        try:
            os.environ["LLM_API_KEY"] = "llm-key"

            with patch("stockagent.config.load_dotenv", return_value=None):
                with self.assertRaisesRegex(ConfigurationError, "TAVILY_API_KEY"):
                    load_app_config()
        finally:
            if old_api_key is None:
                os.environ.pop("LLM_API_KEY", None)
            else:
                os.environ["LLM_API_KEY"] = old_api_key
            if old_tavily_api_key is not None:
                os.environ["TAVILY_API_KEY"] = old_tavily_api_key

    def test_load_app_config_uses_default_edgar_identity(self) -> None:
        environment_names = ("LLM_API_KEY", "TAVILY_API_KEY", "EDGAR_IDENTITY")
        old_values = {name: os.environ.get(name) for name in environment_names}
        try:
            os.environ["LLM_API_KEY"] = "llm-key"
            os.environ["TAVILY_API_KEY"] = "tavily-key"
            os.environ.pop("EDGAR_IDENTITY", None)

            with patch("stockagent.config.load_dotenv", return_value=None):
                config = load_app_config()

            self.assertEqual(config.edgar_identity, DEFAULT_EDGAR_IDENTITY)
        finally:
            for name, old_value in old_values.items():
                if old_value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = old_value

    def test_load_llm_config_requires_api_key(self) -> None:
        old_key = os.environ.pop("LLM_API_KEY", None)
        try:
            with patch("stockagent.config.load_dotenv", return_value=None):
                with self.assertRaises(ConfigurationError):
                    load_llm_config()
        finally:
            if old_key is not None:
                os.environ["LLM_API_KEY"] = old_key

    def test_load_llm_config_uses_default_model_when_env_is_missing(self) -> None:
        old_api_key = os.environ.get("LLM_API_KEY")
        old_model = os.environ.pop("LLM_MODEL", None)
        try:
            os.environ["LLM_API_KEY"] = "test-key"
            with patch("stockagent.config.load_dotenv", return_value=None):
                config = load_llm_config()

            self.assertEqual(config.model, DEFAULT_LLM_MODEL)
        finally:
            if old_api_key is None:
                os.environ.pop("LLM_API_KEY", None)
            else:
                os.environ["LLM_API_KEY"] = old_api_key
            if old_model is not None:
                os.environ["LLM_MODEL"] = old_model


if __name__ == "__main__":
    unittest.main()
