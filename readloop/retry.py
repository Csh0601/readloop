"""Exponential backoff retry for LLM API calls."""
from __future__ import annotations

import random
import time
import logging
from collections.abc import Callable
from typing import TypeVar

_log = logging.getLogger(__name__)

T = TypeVar("T")

# HTTP status codes worth retrying
_RETRYABLE_MESSAGES = ("rate limit", "429", "timeout", "timed out", "503", "502", "connection")


def _is_retryable(exc: Exception) -> bool:
    """Check if an exception is transient and worth retrying."""
    msg = str(exc).lower()
    return any(term in msg for term in _RETRYABLE_MESSAGES)


def with_retry(
    fn: Callable[..., T],
    *args,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    **kwargs,
) -> T:
    """Call fn with exponential backoff on retryable errors.

    Non-retryable errors are raised immediately.
    """
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries or not _is_retryable(exc):
                raise

            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay * 0.3)
            wait = delay + jitter
            _log.info(
                "Retry %d/%d after %.1fs (error: %s)",
                attempt + 1, max_retries, wait, exc,
            )
            time.sleep(wait)

    raise last_exc  # type: ignore[misc]  # unreachable but satisfies type checker
