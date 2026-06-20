from __future__ import annotations

from stockagent.errors import StockAgentError


class ProviderError(StockAgentError):
    """Base class for external data provider failures."""


class NoDataError(ProviderError):
    """A provider returned no usable data for the requested symbol and period."""

    def __init__(self, ticker: str, provider: str, detail: str = "") -> None:
        self.ticker = ticker
        self.provider = provider
        self.detail = detail

        message = f"No data for {ticker!r} from {provider}"
        if detail:
            message += f": {detail}"
        super().__init__(message)


class ProviderRateLimitError(ProviderError):
    """A provider throttled the request."""


class ProviderNotConfiguredError(ProviderError, ValueError):
    """A selected provider is missing required configuration."""


class ProviderResponseError(ProviderError):
    """A provider response could not be fetched, parsed, or normalized."""

    def __init__(self, ticker: str, provider: str, detail: str = "") -> None:
        self.ticker = ticker
        self.provider = provider
        self.detail = detail

        message = f"Invalid response for {ticker!r} from {provider}"
        if detail:
            message += f": {detail}"
        super().__init__(message)
