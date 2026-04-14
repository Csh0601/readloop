"""ReadLoop structured exceptions."""


class ReadLoopError(Exception):
    """Base exception for all ReadLoop errors."""


class ConfigError(ReadLoopError):
    """Configuration missing or invalid (API keys, paths, etc.)."""


class LLMError(ReadLoopError):
    """LLM API call failed after retries."""

    def __init__(self, message: str, model: str = "", cause: Exception | None = None):
        self.model = model
        self.cause = cause
        super().__init__(message)


class ExtractionError(ReadLoopError):
    """Failed to extract structured data from LLM output."""


class PaperError(ReadLoopError):
    """Failed to read or process a paper."""
