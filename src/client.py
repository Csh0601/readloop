"""LLM 客户端 -- DeepSeek V3 (primary, fast & low-cost) + Claude Sonnet 4.6 (fallback)"""
import json
import re

from openai import OpenAI

from .config import (
    CLAUDE_API_KEY,
    CLAUDE_BASE_URL,
    CLAUDE_MODEL,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    MAX_TOKENS,
    TEMPERATURE,
)


class LLMClient:
    def __init__(self):
        self._claude = None
        if CLAUDE_API_KEY:
            self._claude = OpenAI(
                api_key=CLAUDE_API_KEY,
                base_url=CLAUDE_BASE_URL,
                timeout=600.0,  # 10 min, avoid client-side timeout
            )

        self._deepseek = None
        if DEEPSEEK_API_KEY:
            self._deepseek = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,
                timeout=600.0,
            )

    def chat(self, prompt: str, max_tokens: int = MAX_TOKENS) -> str:
        """DeepSeek first (fast & stable), Claude fallback"""
        if self._deepseek:
            try:
                return self._call(
                    self._deepseek, DEEPSEEK_MODEL, prompt, min(max_tokens, 8192)
                )
            except Exception as e:
                print(f"  [DeepSeek failed: {e}, trying Claude]")

        if self._claude:
            return self._call(self._claude, CLAUDE_MODEL, prompt, max_tokens)

        raise RuntimeError("No LLM client available")

    def chat_with_meta(self, prompt: str, max_tokens: int = MAX_TOKENS) -> tuple[str, str]:
        """Call LLM and return (response_text, model_name_used)."""
        if self._deepseek:
            try:
                text = self._call(
                    self._deepseek, DEEPSEEK_MODEL, prompt, min(max_tokens, 8192)
                )
                return text, DEEPSEEK_MODEL
            except Exception as e:
                print(f"  [DeepSeek failed: {e}, trying Claude]")

        if self._claude:
            return self._call(self._claude, CLAUDE_MODEL, prompt, max_tokens), CLAUDE_MODEL

        raise RuntimeError("No LLM client available")

    def chat_json(self, prompt: str, max_tokens: int = MAX_TOKENS) -> dict:
        """Call LLM and parse response as JSON. Retries once on parse failure."""
        text = self.chat(prompt, max_tokens)
        try:
            return _extract_json(text)
        except (json.JSONDecodeError, ValueError):
            # Retry with explicit instruction
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
            raise RuntimeError(f"{model}: no choices returned")
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError(f"{model}: empty content")
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
    # Try extracting from ```json ... ``` block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return _try_parse_json(match.group(1).strip())
    # Try finding first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        return _try_parse_json(text[start:end + 1])
    raise ValueError(f"No JSON found in response: {text[:200]}")
