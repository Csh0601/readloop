"""LLM 客户端 -- DeepSeek V3 (primary) + Claude Sonnet 4.6 (fallback), with retry."""
from __future__ import annotations

import json
import logging
import re

import httpx
from openai import OpenAI

from .config import (
    CLAUDE_API_KEY,
    CLAUDE_BASE_URL,
    CLAUDE_MODEL,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    LLM_TRUST_ENV,
    MAX_TOKENS,
    TEMPERATURE,
)
from .exceptions import ConfigError, LLMError
from .retry import with_retry

_log = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self._claude = None
        if CLAUDE_API_KEY:
            self._claude = OpenAI(
                api_key=CLAUDE_API_KEY,
                base_url=CLAUDE_BASE_URL,
                http_client=httpx.Client(timeout=600.0, trust_env=LLM_TRUST_ENV),
            )

        self._deepseek = None
        if DEEPSEEK_API_KEY:
            self._deepseek = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,
                http_client=httpx.Client(timeout=600.0, trust_env=LLM_TRUST_ENV),
            )

        if not self._claude and not self._deepseek:
            raise ConfigError(
                "No LLM API key configured. "
                "Set DEEPSEEK_API_KEY or CLAUDE_API_KEY in your .env file."
            )

    def chat(self, prompt: str, max_tokens: int = MAX_TOKENS) -> str:
        """DeepSeek first (fast & stable), Claude fallback. Each call retries on transient errors."""
        if self._deepseek:
            try:
                return with_retry(
                    self._call,
                    self._deepseek, DEEPSEEK_MODEL, prompt, min(max_tokens, 8192),
                )
            except Exception as e:
                _log.warning("DeepSeek failed: %s, trying Claude", e)

        if self._claude:
            return with_retry(
                self._call,
                self._claude, CLAUDE_MODEL, prompt, max_tokens,
            )

        raise LLMError("All LLM backends failed")

    def chat_with_meta(self, prompt: str, max_tokens: int = MAX_TOKENS) -> tuple[str, str]:
        """Call LLM and return (response_text, model_name_used)."""
        if self._deepseek:
            try:
                text = with_retry(
                    self._call,
                    self._deepseek, DEEPSEEK_MODEL, prompt, min(max_tokens, 8192),
                )
                return text, DEEPSEEK_MODEL
            except Exception as e:
                _log.warning("DeepSeek failed: %s, trying Claude", e)

        if self._claude:
            text = with_retry(
                self._call,
                self._claude, CLAUDE_MODEL, prompt, max_tokens,
            )
            return text, CLAUDE_MODEL

        raise LLMError("All LLM backends failed")

    def chat_json(self, prompt: str, max_tokens: int = MAX_TOKENS) -> dict:
        """Call LLM and parse response as JSON. Retries once on parse failure."""
        text = self.chat(prompt, max_tokens)
        try:
            return _extract_json(text)
        except (json.JSONDecodeError, ValueError):
            retry_prompt = (
                "Your previous response was not valid JSON. "
                "Please respond with ONLY valid JSON, no markdown fences, no extra text.\n\n"
                + prompt
            )
            text = self.chat(retry_prompt, max_tokens)
            return _extract_json(text)

    def _call(
        self, client: OpenAI, model: str, prompt: str, max_tokens: int
    ) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMPERATURE,
            max_tokens=max_tokens,
        )
        if not response.choices:
            raise LLMError(f"No choices returned", model=model)
        content = response.choices[0].message.content
        if not content:
            raise LLMError(f"Empty content returned", model=model)
        return content


def _clean_trailing_commas(s: str) -> str:
    """Remove trailing commas before } or ] (common LLM JSON error)."""
    return re.sub(r',\s*([\]}])', r'\1', s)


def _try_parse_json(s: str) -> dict:
    """Try json.loads, falling back to trailing-comma cleanup."""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return json.loads(_clean_trailing_commas(s))


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences and trailing commas."""
    text = text.strip()
    if text.startswith("{"):
        return _try_parse_json(text)
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return _try_parse_json(match.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        return _try_parse_json(text[start:end + 1])
    raise ValueError(f"No JSON found in response: {text[:200]}")
