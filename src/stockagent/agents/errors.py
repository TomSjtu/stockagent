from __future__ import annotations

from stockagent.errors import StockAgentError


class AgentError(StockAgentError):
    """Base class for agent orchestration failures."""


class AgentOutputError(AgentError):
    """An agent result is missing or violates its output contract."""


class LLMError(AgentError):
    """Base class for language-model call failures."""


class LLMTimeoutError(LLMError):
    """The configured language model did not respond before timing out."""

    def __init__(self, model: str, detail: str = "") -> None:
        self.model = model
        self.detail = detail

        message = f"LLM request timed out for model {model!r}"
        if detail:
            message += f": {detail}"
        super().__init__(message)


class LLMResponseError(LLMError):
    """The configured language model request failed."""

    def __init__(self, model: str, detail: str = "") -> None:
        self.model = model
        self.detail = detail

        message = f"LLM request failed for model {model!r}"
        if detail:
            message += f": {detail}"
        super().__init__(message)


def classify_llm_error(exc: Exception, model: str) -> LLMError:
    """Classify an unexpected model-call exception for the orchestration boundary."""
    if _is_timeout_error(exc):
        return LLMTimeoutError(model=model, detail=str(exc))
    return LLMResponseError(model=model, detail=str(exc))


def _is_timeout_error(exc: BaseException) -> bool:
    """Detect timeout failures anywhere in an exception cause or context chain."""
    current: BaseException | None = exc
    seen: set[int] = set()
    # 第三方异常可形成 cause/context 环；按对象身份去重，确保分类本身不会卡住
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        error_name = current.__class__.__name__.lower()
        if "timeout" in error_name:
            return True
        current = current.__cause__ or current.__context__
    return False
