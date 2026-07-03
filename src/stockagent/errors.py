from __future__ import annotations


class StockAgentError(Exception):
    """Base class for expected StockAgent runtime errors."""


class ConfigurationError(StockAgentError):
    """Required runtime configuration is missing or invalid."""
