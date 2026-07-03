from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from stockagent.config import (
    DEFAULT_LLM_MODEL,
    LLMConfig,
    apply_llm_environment,
    load_llm_config,
)
from stockagent.errors import ConfigurationError


class LLMConfigTest(unittest.TestCase):
    def test_load_llm_config_requires_api_key(self) -> None:
        old_key = os.environ.pop("LLM_API_KEY", None)
        try:
            with patch("stockagent.config.load_dotenv", return_value=None):
                with self.assertRaises(ConfigurationError):
                    load_llm_config()
        finally:
            if old_key is not None:
                os.environ["LLM_API_KEY"] = old_key

    def test_apply_llm_environment_sets_openai_base_url(self) -> None:
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        old_base = os.environ.pop("OPENAI_BASE_URL", None)
        try:
            apply_llm_environment(
                LLMConfig(
                    api_key="test-key",
                    base_url="https://example.test/v1",
                    model=DEFAULT_LLM_MODEL,
                )
            )

            self.assertEqual(os.environ["OPENAI_API_KEY"], "test-key")
            self.assertEqual(os.environ["OPENAI_BASE_URL"], "https://example.test/v1")
        finally:
            if old_key is not None:
                os.environ["OPENAI_API_KEY"] = old_key
            else:
                os.environ.pop("OPENAI_API_KEY", None)
            if old_base is not None:
                os.environ["OPENAI_BASE_URL"] = old_base
            else:
                os.environ.pop("OPENAI_BASE_URL", None)

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
